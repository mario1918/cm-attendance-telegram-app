"""Seed the first admin teacher into the database."""
import argparse
import sqlite3
from config import DB_PATH


def seed_admin(name: str, telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            teacher_id INTEGER NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            UNIQUE(student_id, date)
        )
    """)

    try:
        cursor.execute(
            "INSERT INTO teachers (telegram_user_id, name, is_admin) VALUES (?, ?, 1)",
            (telegram_id, name),
        )
        conn.commit()
        print(f"تم تسجيل المعلم المشرف '{name}' (معرّف تيليجرام: {telegram_id}) بنجاح.")
    except sqlite3.IntegrityError:
        print(f"المعلم بمعرّف تيليجرام {telegram_id} مسجّل مسبقاً.")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="تسجيل أول معلم مشرف.")
    parser.add_argument("--name", required=True, help="اسم المعلم")
    parser.add_argument("--telegram-id", required=True, type=int, help="معرّف تيليجرام للمعلم")
    args = parser.parse_args()
    seed_admin(args.name, args.telegram_id)
