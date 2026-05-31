import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = 'chatbot.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        username TEXT NOT NULL,
        tier TEXT DEFAULT 'free',
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        messages_today INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT DEFAULT 'New Chat',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        user_message TEXT,
        ai_response TEXT,
        confidence_score REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS training_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_query TEXT,
        correct_answer TEXT,
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        memory_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    conn.commit()

    admins = [
        ('admin1@chatbot.com', 'Admin One', 'admin123'),
        ('admin2@chatbot.com', 'Admin Two', 'admin123')
    ]
    for email, username, password in admins:
        try:
            c.execute(
                'INSERT INTO users (email, username, password_hash, tier, is_admin) VALUES (?, ?, ?, ?, ?)',
                (email, username, generate_password_hash(password), 'plus', 1)
            )
            conn.commit()
        except:
            pass

    conn.close()
    print("Database ready!")
