"""Shared constants, helpers, and cancel handler."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)

# Callback data prefixes
CB_ATTENDANCE = "att"
CB_MANAGE_STUDENTS = "mgst"
CB_ADD_STUDENT = "addst"
CB_REMOVE_STUDENT = "rmst"
CB_EDIT_STUDENT = "edst"
CB_MOVE_STUDENT = "mvst"
CB_ADMIN_MENU = "admin"
CB_DOWNLOAD_REPORT = "dlrpt"
CB_REGISTER_TEACHER = "regt"
CB_REMOVE_TEACHER = "rmt"
CB_MAIN_MENU = "mainmenu"
CB_DONE = "done"
CB_CONFIRM_YES = "yes"
CB_CONFIRM_NO = "no"

# Conversation states
(
    STATE_WAITING_STUDENT_NAME,
    STATE_WAITING_NEW_NAME,
    STATE_SELECT_STUDENT_TO_EDIT,
    STATE_SELECT_STUDENT_TO_REMOVE,
    STATE_CONFIRM_REMOVE_STUDENT,
    STATE_SELECT_STUDENT_TO_MOVE,
    STATE_SELECT_TARGET_TEACHER,
    STATE_WAITING_TEACHER_NAME,
    STATE_WAITING_TEACHER_ID,
    STATE_WAITING_TEACHER_ADMIN,
    STATE_SELECT_TEACHER_TO_REMOVE,
    STATE_CONFIRM_REMOVE_TEACHER,
    STATE_SELECT_TEACHER_FOR_REPORT,
    STATE_SELECT_MONTH_FOR_REPORT,
) = range(14)


def main_menu_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    buttons = [
        [InlineKeyboardButton("📋 تسجيل الحضور", callback_data=CB_ATTENDANCE)],
        [InlineKeyboardButton("👥 إدارة الطلاب", callback_data=CB_MANAGE_STUDENTS)],
    ]
    if is_admin:
        buttons.append(
            [InlineKeyboardButton("⚙️ قائمة المشرف", callback_data=CB_ADMIN_MENU)]
        )
    return InlineKeyboardMarkup(buttons)


def manage_students_keyboard() -> InlineKeyboardMarkup:
    """Build the manage students sub-menu."""
    buttons = [
        [InlineKeyboardButton("➕ إضافة طالب", callback_data=CB_ADD_STUDENT)],
        [InlineKeyboardButton("❌ حذف طالب", callback_data=CB_REMOVE_STUDENT)],
        [InlineKeyboardButton("✏️ تعديل اسم طالب", callback_data=CB_EDIT_STUDENT)],
        [InlineKeyboardButton("🔄 نقل طالب", callback_data=CB_MOVE_STUDENT)],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data=CB_MAIN_MENU)],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the admin menu."""
    buttons = [
        [InlineKeyboardButton("📊 تحميل التقرير", callback_data=CB_DOWNLOAD_REPORT)],
        [InlineKeyboardButton("➕ تسجيل معلم", callback_data=CB_REGISTER_TEACHER)],
        [InlineKeyboardButton("❌ حذف معلم", callback_data=CB_REMOVE_TEACHER)],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data=CB_MAIN_MENU)],
    ]
    return InlineKeyboardMarkup(buttons)


async def delete_previous_bot_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete all tracked bot messages from the chat."""
    msg_ids = context.user_data.pop("bot_message_ids", [])
    for msg_id in msg_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except BadRequest:
            pass


def track_bot_message(context: ContextTypes.DEFAULT_TYPE, message_id: int) -> None:
    """Add a bot message ID to the tracking list."""
    ids = context.user_data.setdefault("bot_message_ids", [])
    ids.append(message_id)


async def send_and_track(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """Delete previous bot messages, delete the user's message, send a new reply_text, and track it."""
    chat_id = update.effective_chat.id
    await delete_previous_bot_messages(chat_id, context)
    # Delete the user's message to keep the chat clean
    try:
        await update.message.delete()
    except BadRequest:
        pass
    msg = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    track_bot_message(context, msg.message_id)
    return msg


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel any conversation and return to main menu."""
    query = update.callback_query
    teacher = context.user_data.get("teacher", {})
    is_admin = teacher.get("is_admin", False)
    if query:
        await query.answer()
        await query.edit_message_text(
            "تم الإلغاء. العودة للقائمة الرئيسية.",
            reply_markup=main_menu_keyboard(is_admin),
        )
    else:
        chat_id = update.effective_chat.id
        await delete_previous_bot_messages(chat_id, context)
        try:
            await update.message.delete()
        except BadRequest:
            pass
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text="تم الإلغاء. العودة للقائمة الرئيسية.",
            reply_markup=main_menu_keyboard(is_admin),
        )
        track_bot_message(context, msg.message_id)
    return ConversationHandler.END
