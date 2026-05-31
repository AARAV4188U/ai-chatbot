from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

class AuthManager:

    @staticmethod
    def signup(email, username, password):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute(
                'INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)',
                (email, username, generate_password_hash(password))
            )
            conn.commit()
            conn.close()
            return True, "Account created successfully"
        except:
            return False, "Email already exists"

    @staticmethod
    def login(email, password):
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE email = ?', (email,))
            user = c.fetchone()
            conn.close()

            if not user:
                return False, "Email not found"
            if user['is_banned']:
                return False, "Account is banned"
            if not check_password_hash(user['password_hash'], password):
                return False, "Wrong password"

            return True, {
                "user_id": user['id'],
                "email": user['email'],
                "username": user['username'],
                "tier": user['tier'],
                "is_admin": bool(user['is_admin'])
            }
        except Exception as e:
            return False, str(e)

auth_manager = AuthManager()
