"""Take attendance flow — toggle students present/absent for today."""
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import db
from handlers.common import CB_ATTENDANCE, CB_DONE, CB_MAIN_MENU, main_menu_keyboard


async def attendance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the student list with attendance toggles for today."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher:
        await query.edit_message_text("⛔ Session expired. Please /start again.")
        return

    today = date.today().isoformat()
    context.user_data["attendance_date"] = today

    students = await db.get_students_by_teacher(teacher["id"])
    if not students:
        await query.edit_message_text(
            "You have no students in your class yet.\n"
            "Use 'Manage Students' to add students first.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_MAIN_MENU)]]
            ),
        )
        return

    present_ids = await db.get_attendance_for_date(teacher["id"], today)
    context.user_data["present_ids"] = present_ids

    keyboard = _build_attendance_keyboard(students, present_ids)
    await query.edit_message_text(
        f"📋 Attendance for {today}\n\nTap a student name to toggle present/absent:",
        reply_markup=keyboard,
    )


def _build_attendance_keyboard(
    students: list[dict], present_ids: set[int]
) -> InlineKeyboardMarkup:
    """Build inline keyboard with student names and ✓/✗ indicators."""
    buttons = []
    for s in students:
        status = "✅" if s["id"] in present_ids else "⬜"
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{status} {s['name']}",
                    callback_data=f"toggle_{s['id']}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton("✔️ Done", callback_data=CB_DONE)])
    buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_MAIN_MENU)])
    return InlineKeyboardMarkup(buttons)


async def attendance_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a student's attendance for today."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher:
        await query.edit_message_text("⛔ Session expired. Please /start again.")
        return

    student_id = int(query.data.replace("toggle_", ""))
    today = context.user_data.get("attendance_date", date.today().isoformat())
    present_ids: set = context.user_data.get("present_ids", set())

    if student_id in present_ids:
        await db.remove_attendance(student_id, today)
        present_ids.discard(student_id)
    else:
        await db.mark_attendance(student_id, today)
        present_ids.add(student_id)

    context.user_data["present_ids"] = present_ids

    students = await db.get_students_by_teacher(teacher["id"])
    keyboard = _build_attendance_keyboard(students, present_ids)

    await query.edit_message_text(
        f"📋 Attendance for {today}\n\nTap a student name to toggle present/absent:",
        reply_markup=keyboard,
    )


async def attendance_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish taking attendance and show summary."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher:
        await query.edit_message_text("⛔ Session expired. Please /start again.")
        return

    today = context.user_data.get("attendance_date", date.today().isoformat())
    present_ids: set = context.user_data.get("present_ids", set())
    students = await db.get_students_by_teacher(teacher["id"])

    present_names = [s["name"] for s in students if s["id"] in present_ids]
    absent_names = [s["name"] for s in students if s["id"] not in present_ids]

    summary = f"✅ Attendance saved for {today}\n\n"
    summary += f"**Present ({len(present_names)}):**\n"
    summary += "\n".join(f"  • {n}" for n in present_names) if present_names else "  None"
    summary += f"\n\n**Absent ({len(absent_names)}):**\n"
    summary += "\n".join(f"  • {n}" for n in absent_names) if absent_names else "  None"

    is_admin = bool(teacher["is_admin"])
    await query.edit_message_text(
        summary,
        reply_markup=main_menu_keyboard(is_admin),
        parse_mode="Markdown",
    )

    context.user_data.pop("present_ids", None)
    context.user_data.pop("attendance_date", None)
