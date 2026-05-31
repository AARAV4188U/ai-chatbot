from difflib import SequenceMatcher
from database import get_db
import random
import re

class AIEngine:

    def similarity(self, a, b):
        a = re.sub(r'[^\w\s]', '', a.lower().strip())
        b = re.sub(r'[^\w\s]', '', b.lower().strip())
        return SequenceMatcher(None, a, b).ratio() * 100

    def find_best_match(self, query):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id, user_query, correct_answer FROM training_data')
            rows = c.fetchall()
            conn.close()

            if not rows:
                return None, 0

            best = None
            best_score = 0
            for row in rows:
                score = self.similarity(query, row['user_query'])
                if score > best_score:
                    best_score = score
                    best = row
            return best, best_score
        except:
            return None, 0

    def generate_response(self, query, user_id=None):
        match, score = self.find_best_match(query)

        if match and score >= 75:
            return match['correct_answer'], round(min(score, 95), 2), False
        elif match and score >= 50:
            return match['correct_answer'], round(score, 2), True
        else:
            responses = [
                "I'm not sure about that yet. Can you teach me the correct answer?",
                "That's a great question! I'm still learning. What's the correct answer?",
                "I don't have enough information on that topic yet. Can you help me learn?",
                "I'm not confident about this one. Could you provide the correct answer?"
            ]
            return random.choice(responses), 25.0, True

    def learn(self, query, answer):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id FROM training_data WHERE user_query = ?', (query,))
            existing = c.fetchone()
            if existing:
                c.execute(
                    'UPDATE training_data SET correct_answer = ?, usage_count = usage_count + 1 WHERE id = ?',
                    (answer, existing['id'])
                )
            else:
                c.execute(
                    'INSERT INTO training_data (user_query, correct_answer) VALUES (?, ?)',
                    (query, answer)
                )
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def get_memories(self, user_id):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id, memory_text, created_at FROM user_memories WHERE user_id = ?', (user_id,))
            rows = c.fetchall()
            conn.close()
            return [{"id": r['id'], "text": r['memory_text'], "created_at": r['created_at']} for r in rows]
        except:
            return []

    def delete_memory(self, memory_id, user_id):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM user_memories WHERE id = ? AND user_id = ?', (memory_id, user_id))
            conn.commit()
            conn.close()
            return True
        except:
            return False

ai_engine = AIEngine()
