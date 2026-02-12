"""Telegram CM Attendance Bot — entry point."""
import logging

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

import db
from config import BOT_TOKEN
from handlers.admin import (
    download_report_conversation,
    register_teacher_conversation,
    remove_teacher_conversation,
)
from handlers.attendance import attendance_done, attendance_start, attendance_toggle
from handlers.common import CB_ADMIN_MENU, CB_ATTENDANCE, CB_DONE, CB_MAIN_MENU, CB_MANAGE_STUDENTS
from handlers.start import main_menu_callback, start_command
from handlers.students import (
    add_student_conversation,
    edit_student_conversation,
    move_student_conversation,
    remove_student_conversation,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application):
    """Initialize the database on startup."""
    await db.init_db()
    logger.info("Database initialized.")


def main():
    """Build and run the bot."""
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # /start command
    application.add_handler(CommandHandler("start", start_command))

    # Conversation handlers (must be added before generic callback handlers)
    application.add_handler(add_student_conversation())
    application.add_handler(remove_student_conversation())
    application.add_handler(edit_student_conversation())
    application.add_handler(move_student_conversation())
    application.add_handler(download_report_conversation())
    application.add_handler(register_teacher_conversation())
    application.add_handler(remove_teacher_conversation())

    # Attendance handlers
    application.add_handler(CallbackQueryHandler(attendance_start, pattern=f"^{CB_ATTENDANCE}$"))
    application.add_handler(CallbackQueryHandler(attendance_toggle, pattern=r"^toggle_\d+$"))
    application.add_handler(CallbackQueryHandler(attendance_done, pattern=f"^{CB_DONE}$"))

    # Main menu navigation (generic — added last)
    application.add_handler(
        CallbackQueryHandler(
            main_menu_callback,
            pattern=f"^({CB_MAIN_MENU}|{CB_MANAGE_STUDENTS}|{CB_ADMIN_MENU})$",
        )
    )

    logger.info("Bot starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
