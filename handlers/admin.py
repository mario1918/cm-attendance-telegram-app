"""Admin features — register/remove teachers, download attendance reports."""
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import db
from handlers.common import (
    CB_CONFIRM_NO,
    CB_CONFIRM_YES,
    CB_DOWNLOAD_REPORT,
    CB_MAIN_MENU,
    CB_REGISTER_TEACHER,
    CB_REMOVE_TEACHER,
    STATE_CONFIRM_REMOVE_TEACHER,
    STATE_SELECT_MONTH_FOR_REPORT,
    STATE_SELECT_TEACHER_FOR_REPORT,
    STATE_SELECT_TEACHER_TO_REMOVE,
    STATE_WAITING_TEACHER_ADMIN,
    STATE_WAITING_TEACHER_ID,
    STATE_WAITING_TEACHER_NAME,
    admin_menu_keyboard,
    cancel_handler,
    main_menu_keyboard,
)
from report import generate_attendance_report


# ── Download Report ──────────────────────────────────────────────────────────

async def download_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of teachers to generate a report for."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher or not teacher["is_admin"]:
        await query.edit_message_text("⛔ Admin access required.")
        return ConversationHandler.END

    teachers = await db.get_all_teachers()
    if not teachers:
        await query.edit_message_text("No teachers found.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"rptteacher_{t['id']}")]
        for t in teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "📊 Download Report\n\nSelect the teacher's class:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_TEACHER_FOR_REPORT


async def report_teacher_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show month selection after teacher is chosen."""
    query = update.callback_query
    await query.answer()

    teacher_id = int(query.data.replace("rptteacher_", ""))
    context.user_data["report_teacher_id"] = teacher_id

    today = date.today()
    # Offer current month and previous 5 months
    months = []
    for i in range(6):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        import calendar
        month_name = calendar.month_name[m]
        months.append((y, m, f"{month_name} {y}"))

    buttons = [
        [InlineKeyboardButton(label, callback_data=f"rptmonth_{y}_{m}")]
        for y, m, label in months
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "Select the month for the report:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_MONTH_FOR_REPORT


async def report_month_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generate and send the Excel report."""
    query = update.callback_query
    await query.answer()

    parts = query.data.replace("rptmonth_", "").split("_")
    year, month = int(parts[0]), int(parts[1])
    teacher_id = context.user_data.get("report_teacher_id")

    if not teacher_id:
        await query.edit_message_text("Error: teacher data lost.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    await query.edit_message_text("⏳ Generating report, please wait...")

    import calendar
    month_name = calendar.month_name[month]

    all_teachers = await db.get_all_teachers()
    target_teacher = next((t for t in all_teachers if t["id"] == teacher_id), None)
    teacher_name = target_teacher["name"] if target_teacher else "Unknown"

    buffer = await generate_attendance_report(teacher_id, year, month)
    filename = f"Attendance_{teacher_name}_{month_name}_{year}.xlsx"

    teacher = context.user_data.get("teacher")
    is_admin = bool(teacher["is_admin"]) if teacher else False

    await query.message.reply_document(
        document=buffer,
        filename=filename,
        caption=f"📊 Attendance report for {teacher_name} — {month_name} {year}",
    )
    await query.message.reply_text(
        "Report sent! Choose an option:",
        reply_markup=main_menu_keyboard(is_admin),
    )

    context.user_data.pop("report_teacher_id", None)
    return ConversationHandler.END


def download_report_conversation() -> ConversationHandler:
    """Build ConversationHandler for downloading a report."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(download_report_start, pattern=f"^{CB_DOWNLOAD_REPORT}$")],
        states={
            STATE_SELECT_TEACHER_FOR_REPORT: [
                CallbackQueryHandler(report_teacher_selected, pattern=r"^rptteacher_\d+$"),
            ],
            STATE_SELECT_MONTH_FOR_REPORT: [
                CallbackQueryHandler(report_month_selected, pattern=r"^rptmonth_\d+_\d+$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_message=False,
    )


# ── Register Teacher ─────────────────────────────────────────────────────────

async def register_teacher_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt admin to type the new teacher's name."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher or not teacher["is_admin"]:
        await query.edit_message_text("⛔ Admin access required.")
        return ConversationHandler.END

    await query.edit_message_text(
        "➕ Register Teacher\n\nType the new teacher's name (or /cancel):"
    )
    return STATE_WAITING_TEACHER_NAME


async def register_teacher_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save name and ask for Telegram user ID."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty. Please type a valid name:")
        return STATE_WAITING_TEACHER_NAME

    context.user_data["new_teacher_name"] = name
    await update.message.reply_text(
        f"Teacher name: {name}\n\n"
        "Now type the teacher's Telegram user ID (a number).\n"
        "The teacher can find their ID by messaging @userinfobot on Telegram."
    )
    return STATE_WAITING_TEACHER_ID


async def register_teacher_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Telegram ID and ask if admin."""
    text = update.message.text.strip()
    try:
        telegram_id = int(text)
    except ValueError:
        await update.message.reply_text("Please enter a valid number for the Telegram user ID:")
        return STATE_WAITING_TEACHER_ID

    # Check if already registered
    existing = await db.get_teacher_by_telegram_id(telegram_id)
    if existing:
        await update.message.reply_text(
            f"A teacher with Telegram ID {telegram_id} is already registered as '{existing['name']}'.",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["new_teacher_telegram_id"] = telegram_id

    buttons = [
        [
            InlineKeyboardButton("Yes", callback_data="admin_yes"),
            InlineKeyboardButton("No", callback_data="admin_no"),
        ]
    ]
    await update.message.reply_text(
        "Should this teacher have admin privileges?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_WAITING_TEACHER_ADMIN


async def register_teacher_admin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finalize teacher registration."""
    query = update.callback_query
    await query.answer()

    is_admin = query.data == "admin_yes"
    name = context.user_data.pop("new_teacher_name", "Unknown")
    telegram_id = context.user_data.pop("new_teacher_telegram_id", 0)

    await db.add_teacher(telegram_id, name, is_admin)
    role = "admin teacher" if is_admin else "teacher"
    await query.edit_message_text(
        f"✅ {name} registered as {role} (Telegram ID: {telegram_id}).",
        reply_markup=admin_menu_keyboard(),
    )
    return ConversationHandler.END


def register_teacher_conversation() -> ConversationHandler:
    """Build ConversationHandler for registering a teacher."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(register_teacher_start, pattern=f"^{CB_REGISTER_TEACHER}$")],
        states={
            STATE_WAITING_TEACHER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_teacher_name_received),
            ],
            STATE_WAITING_TEACHER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_teacher_id_received),
            ],
            STATE_WAITING_TEACHER_ADMIN: [
                CallbackQueryHandler(register_teacher_admin_selected, pattern=r"^admin_(yes|no)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_message=False,
    )


# ── Remove Teacher ───────────────────────────────────────────────────────────

async def remove_teacher_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of teachers for removal."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher or not teacher["is_admin"]:
        await query.edit_message_text("⛔ Admin access required.")
        return ConversationHandler.END

    teachers = await db.get_all_teachers()
    # Don't allow removing yourself
    other_teachers = [t for t in teachers if t["id"] != teacher["id"]]

    if not other_teachers:
        await query.edit_message_text(
            "No other teachers to remove.",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{t['name']} {'(admin)' if t['is_admin'] else ''}", callback_data=f"rmtsel_{t['id']}")]
        for t in other_teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "❌ Remove Teacher\n\nSelect the teacher to remove:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_TEACHER_TO_REMOVE


async def remove_teacher_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for confirmation."""
    query = update.callback_query
    await query.answer()

    teacher_id = int(query.data.replace("rmtsel_", ""))
    teachers = await db.get_all_teachers()
    target = next((t for t in teachers if t["id"] == teacher_id), None)

    if not target:
        await query.edit_message_text("Teacher not found.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    context.user_data["pending_remove_teacher"] = target

    buttons = [
        [
            InlineKeyboardButton("✅ Yes, remove", callback_data=CB_CONFIRM_YES),
            InlineKeyboardButton("❌ No, cancel", callback_data=CB_CONFIRM_NO),
        ]
    ]
    await query.edit_message_text(
        f"Are you sure you want to remove teacher '{target['name']}'?\n"
        "This will also delete all their students and attendance records.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_CONFIRM_REMOVE_TEACHER


async def remove_teacher_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process teacher removal."""
    query = update.callback_query
    await query.answer()

    if query.data == CB_CONFIRM_YES:
        target = context.user_data.pop("pending_remove_teacher", None)
        if target:
            await db.remove_teacher(target["id"])
            await query.edit_message_text(
                f"✅ Teacher '{target['name']}' has been removed.",
                reply_markup=admin_menu_keyboard(),
            )
        else:
            await query.edit_message_text("Error: teacher data lost.", reply_markup=admin_menu_keyboard())
    else:
        context.user_data.pop("pending_remove_teacher", None)
        await query.edit_message_text(
            "Removal cancelled.",
            reply_markup=admin_menu_keyboard(),
        )
    return ConversationHandler.END


def remove_teacher_conversation() -> ConversationHandler:
    """Build ConversationHandler for removing a teacher."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_teacher_start, pattern=f"^{CB_REMOVE_TEACHER}$")],
        states={
            STATE_SELECT_TEACHER_TO_REMOVE: [
                CallbackQueryHandler(remove_teacher_selected, pattern=r"^rmtsel_\d+$"),
            ],
            STATE_CONFIRM_REMOVE_TEACHER: [
                CallbackQueryHandler(remove_teacher_confirmed, pattern=f"^({CB_CONFIRM_YES}|{CB_CONFIRM_NO})$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_message=False,
    )
