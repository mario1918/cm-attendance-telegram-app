"""Admin features — register/remove teachers, download attendance reports."""
import warnings
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
        await query.edit_message_text("⛔ مطلوب صلاحيات المشرف.")
        return ConversationHandler.END

    teachers = await db.get_all_teachers()
    if not teachers:
        await query.edit_message_text("لا يوجد معلمون.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"rptteacher_{t['id']}")]
        for t in teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "📊 تحميل التقرير\n\nاختر صف المعلم:",
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
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "اختر الشهر للتقرير:",
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
        await query.edit_message_text("خطأ: فُقدت بيانات المعلم.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    await query.edit_message_text("⏳ جاري إنشاء التقرير، يرجى الانتظار...")

    import calendar
    month_name = calendar.month_name[month]

    all_teachers = await db.get_all_teachers()
    target_teacher = next((t for t in all_teachers if t["id"] == teacher_id), None)
    teacher_name = target_teacher["name"] if target_teacher else "Unknown"

    buffer = await generate_attendance_report(teacher_id, year, month)
    filename = f"حضور_{teacher_name}_{month_name}_{year}.xlsx"

    teacher = context.user_data.get("teacher")
    is_admin = bool(teacher["is_admin"]) if teacher else False

    await query.message.reply_document(
        document=buffer,
        filename=filename,
        caption=f"📊 تقرير الحضور لـ {teacher_name} — {month_name} {year}",
    )
    await query.message.reply_text(
        "تم إرسال التقرير! اختر من الخيارات:",
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
        per_message=True,
    )


# ── Register Teacher ─────────────────────────────────────────────────────────

async def register_teacher_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt admin to type the new teacher's name."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    if not teacher or not teacher["is_admin"]:
        await query.edit_message_text("⛔ مطلوب صلاحيات المشرف.")
        return ConversationHandler.END

    await query.edit_message_text(
        "➕ تسجيل معلم\n\nاكتب اسم المعلم الجديد (أو /cancel للعودة):"
    )
    return STATE_WAITING_TEACHER_NAME


async def register_teacher_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save name and ask for Telegram user ID."""
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("الاسم لا يمكن أن يكون فارغاً. اكتب اسماً صحيحاً:")
        return STATE_WAITING_TEACHER_NAME

    context.user_data["new_teacher_name"] = name
    await update.message.reply_text(
        f"اسم المعلم: {name}\n\n"
        "الآن اكتب معرّف تيليجرام للمعلم (رقم).\n"
        "يمكن للمعلم معرفة معرّفه بمراسلة @userinfobot على تيليجرام."
    )
    return STATE_WAITING_TEACHER_ID


async def register_teacher_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Telegram ID and ask if admin."""
    text = update.message.text.strip()
    try:
        telegram_id = int(text)
    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم صحيح لمعرّف تيليجرام:")
        return STATE_WAITING_TEACHER_ID

    # Check if already registered
    existing = await db.get_teacher_by_telegram_id(telegram_id)
    if existing:
        await update.message.reply_text(
            f"المعلم بمعرّف تيليجرام {telegram_id} مسجّل مسبقاً باسم '{existing['name']}'.",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    context.user_data["new_teacher_telegram_id"] = telegram_id

    buttons = [
        [
            InlineKeyboardButton("نعم", callback_data="admin_yes"),
            InlineKeyboardButton("لا", callback_data="admin_no"),
        ]
    ]
    await update.message.reply_text(
        "هل يجب أن يكون لهذا المعلم صلاحيات مشرف?",
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
    role = "معلم مشرف" if is_admin else "معلم"
    await query.edit_message_text(
        f"✅ تم تسجيل {name} ك{role} (معرّف تيليجرام: {telegram_id}).",
        reply_markup=admin_menu_keyboard(),
    )
    return ConversationHandler.END


def register_teacher_conversation() -> ConversationHandler:
    """Build ConversationHandler for registering a teacher."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
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
        await query.edit_message_text("⛔ مطلوب صلاحيات المشرف.")
        return ConversationHandler.END

    teachers = await db.get_all_teachers()
    # Don't allow removing yourself
    other_teachers = [t for t in teachers if t["id"] != teacher["id"]]

    if not other_teachers:
        await query.edit_message_text(
            "لا يوجد معلمون آخرون لحذفهم.",
            reply_markup=admin_menu_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(f"{t['name']} {'(مشرف)' if t['is_admin'] else ''}", callback_data=f"rmtsel_{t['id']}")]
        for t in other_teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "❌ حذف معلم\n\nاختر المعلم المراد حذفه:",
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
        await query.edit_message_text("المعلم غير موجود.", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END

    context.user_data["pending_remove_teacher"] = target

    buttons = [
        [
            InlineKeyboardButton("✅ نعم، احذف", callback_data=CB_CONFIRM_YES),
            InlineKeyboardButton("❌ لا، إلغاء", callback_data=CB_CONFIRM_NO),
        ]
    ]
    await query.edit_message_text(
        f"هل أنت متأكد من حذف المعلم '{target['name']}'?\n"
        "سيتم أيضاً حذف جميع طلابه وسجلات حضورهم.",
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
                f"✅ تم حذف المعلم '{target['name']}'.",
                reply_markup=admin_menu_keyboard(),
            )
        else:
            await query.edit_message_text("خطأ: فُقدت بيانات المعلم.", reply_markup=admin_menu_keyboard())
    else:
        context.user_data.pop("pending_remove_teacher", None)
        await query.edit_message_text(
            "تم إلغاء الحذف.",
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
        per_message=True,
    )
