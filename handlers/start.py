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
            "⛔ أنت غير مسجّل كمعلم.\n"
            "يرجى التواصل مع المشرف لتسجيل حسابك."
        )
        return

    context.user_data["teacher"] = teacher
    is_admin = bool(teacher["is_admin"])

    await update.message.reply_text(
        f"مرحباً، {teacher['name']}! 👋\n\nاختر من الخيارات أدناه:",
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
            await query.edit_message_text("⛔ أنت غير مسجّل كمعلم.")
            return
        context.user_data["teacher"] = teacher

    is_admin = bool(teacher["is_admin"])

    if data == CB_MAIN_MENU:
        await query.edit_message_text(
            f"مرحباً، {teacher['name']}! 👋\n\nاختر من الخيارات أدناه:",
            reply_markup=main_menu_keyboard(is_admin),
        )
    elif data == CB_MANAGE_STUDENTS:
        await query.edit_message_text(
            "👥 إدارة الطلاب\n\nاختر إجراء:",
            reply_markup=manage_students_keyboard(),
        )
    elif data == CB_ADMIN_MENU:
        if not is_admin:
            await query.edit_message_text("⛔ ليس لديك صلاحيات المشرف.")
            return
        await query.edit_message_text(
            "⚙️ قائمة المشرف\n\nاختر إجراء:",
            reply_markup=admin_menu_keyboard(),
        )
