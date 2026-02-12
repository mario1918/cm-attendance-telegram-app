"""Shared constants, helpers, and cancel handler."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

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
        [InlineKeyboardButton("📋 Take Attendance", callback_data=CB_ATTENDANCE)],
        [InlineKeyboardButton("👥 Manage Students", callback_data=CB_MANAGE_STUDENTS)],
    ]
    if is_admin:
        buttons.append(
            [InlineKeyboardButton("⚙️ Admin Menu", callback_data=CB_ADMIN_MENU)]
        )
    return InlineKeyboardMarkup(buttons)


def manage_students_keyboard() -> InlineKeyboardMarkup:
    """Build the manage students sub-menu."""
    buttons = [
        [InlineKeyboardButton("➕ Add Student", callback_data=CB_ADD_STUDENT)],
        [InlineKeyboardButton("❌ Remove Student", callback_data=CB_REMOVE_STUDENT)],
        [InlineKeyboardButton("✏️ Edit Student Name", callback_data=CB_EDIT_STUDENT)],
        [InlineKeyboardButton("🔄 Move Student", callback_data=CB_MOVE_STUDENT)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_MAIN_MENU)],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the admin menu."""
    buttons = [
        [InlineKeyboardButton("📊 Download Report", callback_data=CB_DOWNLOAD_REPORT)],
        [InlineKeyboardButton("➕ Register Teacher", callback_data=CB_REGISTER_TEACHER)],
        [InlineKeyboardButton("❌ Remove Teacher", callback_data=CB_REMOVE_TEACHER)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_MAIN_MENU)],
    ]
    return InlineKeyboardMarkup(buttons)


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel any conversation and return to main menu."""
    query = update.callback_query
    if query:
        await query.answer()
        teacher = context.user_data.get("teacher", {})
        is_admin = teacher.get("is_admin", False)
        await query.edit_message_text(
            "Action cancelled. Returning to main menu.",
            reply_markup=main_menu_keyboard(is_admin),
        )
    else:
        teacher = context.user_data.get("teacher", {})
        is_admin = teacher.get("is_admin", False)
        await update.message.reply_text(
            "Action cancelled. Returning to main menu.",
            reply_markup=main_menu_keyboard(is_admin),
        )
    return ConversationHandler.END
