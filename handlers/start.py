"""Start command and main menu handler."""
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import db
from handlers.common import (
    CB_ADMIN_MENU,
    CB_ATTENDANCE,
    CB_MAIN_MENU,
    CB_MANAGE_STUDENTS,
    admin_menu_keyboard,
    delete_previous_bot_messages,
    main_menu_keyboard,
    manage_students_keyboard,
    track_bot_message,
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — authenticate teacher and show main menu."""
    telegram_user_id = update.effective_user.id
    teacher = await db.get_teacher_by_telegram_id(telegram_user_id)

    chat_id = update.effective_chat.id
    await delete_previous_bot_messages(chat_id, context)
    # Delete the user's /start command message
    try:
        await update.message.delete()
    except BadRequest:
        pass

    if not teacher:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⛔ أنت غير مسجّل كمعلم.\n"
                 "يرجى التواصل مع المشرف لتسجيل حسابك.",
        )
        track_bot_message(context, msg.message_id)
        return

    context.user_data["teacher"] = teacher
    is_admin = bool(teacher["is_admin"])

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"مرحباً، {teacher['name']}! 👋\n\nاختر من الخيارات أدناه:",
        reply_markup=main_menu_keyboard(is_admin),
    )
    track_bot_message(context, msg.message_id)


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button presses."""
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass
    data = query.data

    teacher = context.user_data.get("teacher")
    if not teacher:
        teacher = await db.get_teacher_by_telegram_id(update.effective_user.id)
        if not teacher:
            await query.edit_message_text("⛔ أنت غير مسجّل كمعلم.")
            return
        context.user_data["teacher"] = teacher

    is_admin = bool(teacher["is_admin"])

    try:
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
    except BadRequest:
        pass
