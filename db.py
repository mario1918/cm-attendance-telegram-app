"""Database layer — async CRUD operations for teachers, students, and attendance."""
import aiosqlite
from config import DB_PATH


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                teacher_id INTEGER NOT NULL,
                FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(student_id, date)
            )
        """)
        await db.commit()


# ── Teacher queries ──────────────────────────────────────────────────────────

async def get_teacher_by_telegram_id(telegram_user_id: int) -> dict | None:
    """Return teacher dict or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM teachers WHERE telegram_user_id = ?", (telegram_user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_teachers() -> list[dict]:
    """Return list of all teachers."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM teachers ORDER BY name") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def add_teacher(telegram_user_id: int, name: str, is_admin: bool = False) -> int:
    """Insert a new teacher. Returns the new teacher id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO teachers (telegram_user_id, name, is_admin) VALUES (?, ?, ?)",
            (telegram_user_id, name, 1 if is_admin else 0),
        )
        await db.commit()
        return cursor.lastrowid


async def remove_teacher(teacher_id: int):
    """Delete a teacher and cascade-delete their students and attendance."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
        await db.commit()


# ── Student queries ──────────────────────────────────────────────────────────

async def get_students_by_teacher(teacher_id: int) -> list[dict]:
    """Return students belonging to a teacher."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM students WHERE teacher_id = ? ORDER BY name", (teacher_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_student_by_id(student_id: int) -> dict | None:
    """Return a single student or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM students WHERE id = ?", (student_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def add_student(name: str, teacher_id: int) -> int:
    """Add a student to a teacher's class. Returns student id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO students (name, teacher_id) VALUES (?, ?)", (name, teacher_id)
        )
        await db.commit()
        return cursor.lastrowid


async def remove_student(student_id: int):
    """Delete a student and their attendance records."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM students WHERE id = ?", (student_id,))
        await db.commit()


async def update_student_name(student_id: int, new_name: str):
    """Rename a student."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE students SET name = ? WHERE id = ?", (new_name, student_id))
        await db.commit()


async def move_student(student_id: int, new_teacher_id: int):
    """Move a student to a different teacher's class."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE students SET teacher_id = ? WHERE id = ?", (new_teacher_id, student_id)
        )
        await db.commit()


# ── Attendance queries ───────────────────────────────────────────────────────

async def mark_attendance(student_id: int, date: str):
    """Mark a student as present for a given date (YYYY-MM-DD). Ignores duplicates."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO attendance (student_id, date) VALUES (?, ?)",
            (student_id, date),
        )
        await db.commit()


async def remove_attendance(student_id: int, date: str):
    """Remove attendance record for a student on a given date."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, date),
        )
        await db.commit()


async def get_attendance_for_date(teacher_id: int, date: str) -> set[int]:
    """Return set of student_ids that are marked present for a teacher's class on a date."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT a.student_id FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE s.teacher_id = ? AND a.date = ?
            """,
            (teacher_id, date),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}


async def get_attendance_for_month(teacher_id: int, year: int, month: int) -> list[dict]:
    """Return attendance records for a teacher's class for a given month.
    Returns list of dicts with keys: student_id, student_name, date.
    """
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT s.id as student_id, s.name as student_name, a.date
            FROM students s
            LEFT JOIN attendance a ON s.id = a.student_id AND a.date LIKE ?
            WHERE s.teacher_id = ?
            ORDER BY s.name, a.date
            """,
            (f"{month_str}%", teacher_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_attendance_dates_for_month(teacher_id: int, year: int, month: int) -> list[str]:
    """Return sorted distinct dates (YYYY-MM-DD) where at least one attendance record exists
    for the given teacher's class in the given month.
    """
    month_str = f"{year}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT DISTINCT a.date
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE s.teacher_id = ? AND a.date LIKE ?
            ORDER BY a.date ASC
            """,
            (teacher_id, f"{month_str}%"),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
