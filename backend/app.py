import sys
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from flask import Flask, request, jsonify, render_template
try:
    from importlib import import_module
    CORS = import_module('flask_cors').CORS
except ImportError:
    def CORS(app, *args, **kwargs):
        return app
from database import get_db, init_db
from auth import auth_manager
from ai_engine import ai_engine
from config import TIER_LIMITS
from werkzeug.security import generate_password_hash

app = Flask(__name__, template_folder='../templates', static_folder='../frontend')
CORS(app)

# ========== PAGES ==========

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# ========== AUTH ==========

@app.route('/api/signup', methods=['POST'])
def signup():
    d = request.get_json()
    if not all([d.get('email'), d.get('username'), d.get('password')]):
        return jsonify({"error": "All fields required"}), 400
    ok, msg = auth_manager.signup(d['email'], d['username'], d['password'])
    return jsonify({"message": msg} if ok else {"error": msg}), (201 if ok else 400)

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    ok, result = auth_manager.login(d.get('email',''), d.get('password',''))
    return jsonify({"message": "Login successful", "user": result} if ok else {"error": result}), (200 if ok else 401)

# ========== CHAT ==========

@app.route('/api/chat/sessions')
def get_sessions():
    user_id = request.args.get('user_id')
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, title, created_at FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    rows = c.fetchall()
    conn.close()
    return jsonify({"sessions": [{"id": r['id'], "title": r['title'], "created_at": r['created_at']} for r in rows]})

@app.route('/api/chat/new-session', methods=['POST'])
def new_session():
    d = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO chat_sessions (user_id, title) VALUES (?, ?)', (d.get('user_id'), d.get('title', 'New Chat')))
    conn.commit()
    sid = c.lastrowid
    conn.close()
    return jsonify({"session_id": sid}), 201

@app.route('/api/chat/messages')
def get_messages():
    sid = request.args.get('session_id')
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT user_message, ai_response, confidence_score, created_at FROM messages WHERE session_id = ? ORDER BY created_at', (sid,))
    rows = c.fetchall()
    conn.close()
    return jsonify({"messages": [{"user_message": r['user_message'], "ai_response": r['ai_response'], "confidence": r['confidence_score'], "created_at": r['created_at']} for r in rows]})

@app.route('/api/chat/send', methods=['POST'])
def send_message():
    d = request.get_json()
    user_id = d.get('user_id')
    session_id = d.get('session_id')
    message = d.get('message', '').strip()

    if not message:
        return jsonify({"error": "Message is empty"}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT tier, messages_today FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()

    if user:
        limit = TIER_LIMITS.get(user['tier'], 20)
        if user['messages_today'] >= limit:
            conn.close()
            return jsonify({"error": f"Daily limit of {limit} messages reached. Upgrade your tier!"}), 429

    response, confidence, ask_feedback = ai_engine.generate_response(message, user_id)

    c.execute(
        'INSERT INTO messages (session_id, user_message, ai_response, confidence_score) VALUES (?, ?, ?, ?)',
        (session_id, message, response, confidence)
    )
    c.execute('UPDATE users SET messages_today = messages_today + 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"response": response, "confidence": confidence, "ask_feedback": ask_feedback})

@app.route('/api/feedback', methods=['POST'])
def feedback():
    d = request.get_json()
    if not d.get('is_correct') and d.get('correct_answer'):
        ai_engine.learn(d.get('user_query', ''), d['correct_answer'])
        return jsonify({"message": "Thank you! I learned from your correction."})
    return jsonify({"message": "Thanks for the feedback!"})

# ========== MEMORY ==========

@app.route('/api/memory')
def get_memories():
    user_id = request.args.get('user_id')
    return jsonify({"memories": ai_engine.get_memories(user_id)})

@app.route('/api/memory/delete', methods=['POST'])
def delete_memory():
    d = request.get_json()
    ai_engine.delete_memory(d.get('memory_id'), d.get('user_id'))
    return jsonify({"message": "Memory deleted"})

# ========== ADMIN ==========

def is_admin(admin_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT is_admin FROM users WHERE id = ?', (admin_id,))
    user = c.fetchone()
    conn.close()
    return user and user['is_admin']

@app.route('/api/admin/users')
def admin_users():
    if not is_admin(request.args.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, email, username, tier, is_admin, is_banned, messages_today, created_at FROM users')
    rows = c.fetchall()
    conn.close()
    return jsonify({"users": [{"id": r['id'], "email": r['email'], "username": r['username'], "tier": r['tier'], "is_admin": bool(r['is_admin']), "is_banned": bool(r['is_banned']), "messages_today": r['messages_today'], "created_at": r['created_at']} for r in rows]})

@app.route('/api/admin/ban', methods=['POST'])
def admin_ban():
    d = request.get_json()
    if not is_admin(d.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_banned = ? WHERE id = ?', (1 if d.get('ban') else 0, d.get('user_id')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Updated"})

@app.route('/api/admin/delete-user', methods=['POST'])
def admin_delete():
    d = request.get_json()
    if not is_admin(d.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (d.get('user_id'),))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route('/api/admin/reset-password', methods=['POST'])
def admin_reset():
    d = request.get_json()
    if not is_admin(d.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(d.get('new_password','')), d.get('user_id')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Password reset"})

@app.route('/api/admin/set-tier', methods=['POST'])
def admin_set_tier():
    d = request.get_json()
    if not is_admin(d.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET tier = ? WHERE id = ?', (d.get('tier'), d.get('user_id')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Tier updated"})

@app.route('/api/admin/training-data')
def admin_training():
    if not is_admin(request.args.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, user_query, correct_answer, usage_count, created_at FROM training_data ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return jsonify({"training_data": [{"id": r['id'], "query": r['user_query'], "answer": r['correct_answer'], "usage_count": r['usage_count'], "created_at": r['created_at']} for r in rows]})

@app.route('/api/admin/add-training', methods=['POST'])
def admin_add_training():
    d = request.get_json()
    if not is_admin(d.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO training_data (user_query, correct_answer) VALUES (?, ?)', (d.get('query'), d.get('answer')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Training data added"})

@app.route('/api/admin/conversations')
def admin_conversations():
    if not is_admin(request.args.get('admin_id')):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT m.user_message, m.ai_response, m.confidence_score, m.created_at, u.username, u.email
        FROM messages m
        JOIN chat_sessions cs ON m.session_id = cs.id
        JOIN users u ON cs.user_id = u.id
        ORDER BY m.created_at DESC LIMIT 100
    ''')
    rows = c.fetchall()
    conn.close()
    return jsonify({"conversations": [{"user_message": r['user_message'], "ai_response": r['ai_response'], "confidence": r['confidence_score'], "created_at": r['created_at'], "username": r['username'], "email": r['email']} for r in rows]})

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    init_db()
    print("\n=============================")
    print("AI Chatbot is starting...")
    print("Open http://localhost:5000")
    print("=============================\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
