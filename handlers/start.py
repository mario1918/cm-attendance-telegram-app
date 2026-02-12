"""Start command and main menu handler."""
from telegram import Update
from telegram.ext import ContextTypes

import db
from handlers.common import (
    CB_ADMIN_MENU,
    CB_ATTENDANCE,
    CB_MAIN_MENU,
    CB_MANAGE_STUDENTS,
    admin_menu_keyboard,
    main_menu_keyboard,
    manage_students_keyboard,
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — authenticate teacher and show main menu."""
    telegram_user_id = update.effective_user.id
    teacher = await db.get_teacher_by_telegram_id(telegram_user_id)

    if not teacher:
        await update.message.reply_text(
            "⛔ You are not registered as a teacher.\n"
            "Please contact an admin to register your Telegram account."
        )
        return

    context.user_data["teacher"] = teacher
    is_admin = bool(teacher["is_admin"])

    await update.message.reply_text(
        f"Welcome, {teacher['name']}! 👋\n\nChoose an option below:",
        reply_markup=main_menu_keyboard(is_admin),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    teacher = context.user_data.get("teacher")
    if not teacher:
        teacher = await db.get_teacher_by_telegram_id(update.effective_user.id)
        if not teacher:
            await query.edit_message_text("⛔ You are not registered as a teacher.")
            return
        context.user_data["teacher"] = teacher

    is_admin = bool(teacher["is_admin"])

    if data == CB_MAIN_MENU:
        await query.edit_message_text(
            f"Welcome, {teacher['name']}! 👋\n\nChoose an option below:",
            reply_markup=main_menu_keyboard(is_admin),
        )
    elif data == CB_MANAGE_STUDENTS:
        await query.edit_message_text(
            "👥 Manage Students\n\nChoose an action:",
            reply_markup=manage_students_keyboard(),
        )
    elif data == CB_ADMIN_MENU:
        if not is_admin:
            await query.edit_message_text("⛔ You don't have admin access.")
            return
        await query.edit_message_text(
            "⚙️ Admin Menu\n\nChoose an action:",
            reply_markup=admin_menu_keyboard(),
        )
