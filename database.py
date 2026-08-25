import sqlite3
from contextlib import contextmanager

DB_PATH = "bot_data.db"


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Казна: доноры и их сумма
        c.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                total_amount REAL DEFAULT 0
            )
        """)
        # Уровни/XP
        c.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0
            )
        """)
        # Предупреждения (модерация)
        c.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
