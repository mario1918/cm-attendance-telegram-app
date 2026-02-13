"""Student management flows — add, remove, edit, move students."""
import warnings

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
    CB_ADD_STUDENT,
    CB_CONFIRM_NO,
    CB_CONFIRM_YES,
    CB_EDIT_STUDENT,
    CB_MAIN_MENU,
    CB_MOVE_STUDENT,
    CB_REMOVE_STUDENT,
    STATE_CONFIRM_REMOVE_STUDENT,
    STATE_SELECT_STUDENT_TO_EDIT,
    STATE_SELECT_STUDENT_TO_MOVE,
    STATE_SELECT_STUDENT_TO_REMOVE,
    STATE_SELECT_TARGET_TEACHER,
    STATE_WAITING_NEW_NAME,
    STATE_WAITING_STUDENT_NAME,
    cancel_handler,
    main_menu_keyboard,
    manage_students_keyboard,
)


# ── Add Student ──────────────────────────────────────────────────────────────

async def add_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt teacher to type the student's name."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ إضافة طالب\n\nاكتب اسم الطالب (أو /cancel للعودة):"
    )
    return STATE_WAITING_STUDENT_NAME


async def add_student_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the new student."""
    teacher = context.user_data.get("teacher")
    if not teacher:
        await update.message.reply_text("⛔ انتهت الجلسة. يرجى كتابة /start من جديد.")
        return ConversationHandler.END

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("الاسم لا يمكن أن يكون فارغاً. اكتب اسماً صحيحاً:")
        return STATE_WAITING_STUDENT_NAME

    await db.add_student(name, teacher["id"])
    is_admin = bool(teacher["is_admin"])
    await update.message.reply_text(
        f"✅ تمت إضافة الطالب '{name}' إلى صفك.",
        reply_markup=manage_students_keyboard(),
    )
    return ConversationHandler.END


def add_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for adding a student."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
        return ConversationHandler(
            entry_points=[CallbackQueryHandler(add_student_start, pattern=f"^{CB_ADD_STUDENT}$")],
            states={
                STATE_WAITING_STUDENT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_student_name_received),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel_handler),
                CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
            ],
            per_message=False,
        )


# ── Remove Student ───────────────────────────────────────────────────────────

async def remove_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show student list for removal."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    students = await db.get_students_by_teacher(teacher["id"])

    if not students:
        await query.edit_message_text(
            "لا يوجد طلاب لحذفهم.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"rmsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "❌ حذف طالب\n\nاختر الطالب المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_STUDENT_TO_REMOVE


async def remove_student_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for confirmation before removing."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.replace("rmsel_", ""))
    student = await db.get_student_by_id(student_id)
    if not student:
        await query.edit_message_text("الطالب غير موجود.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_remove_student"] = student

    buttons = [
        [
            InlineKeyboardButton("✅ نعم، احذف", callback_data=CB_CONFIRM_YES),
            InlineKeyboardButton("❌ لا، إلغاء", callback_data=CB_CONFIRM_NO),
        ]
    ]
    await query.edit_message_text(
        f"هل أنت متأكد من حذف '{student['name']}'?\n"
        "سيتم أيضاً حذف جميع سجلات حضوره.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_CONFIRM_REMOVE_STUDENT


async def remove_student_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process removal confirmation."""
    query = update.callback_query
    await query.answer()

    if query.data == CB_CONFIRM_YES:
        student = context.user_data.pop("pending_remove_student", None)
        if student:
            await db.remove_student(student["id"])
            await query.edit_message_text(
                f"✅ تم حذف الطالب '{student['name']}'.",
                reply_markup=manage_students_keyboard(),
            )
        else:
            await query.edit_message_text("خطأ: فُقدت بيانات الطالب.", reply_markup=manage_students_keyboard())
    else:
        context.user_data.pop("pending_remove_student", None)
        await query.edit_message_text(
            "تم إلغاء الحذف.",
            reply_markup=manage_students_keyboard(),
        )
    return ConversationHandler.END


def remove_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for removing a student."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_student_start, pattern=f"^{CB_REMOVE_STUDENT}$")],
        states={
            STATE_SELECT_STUDENT_TO_REMOVE: [
                CallbackQueryHandler(remove_student_selected, pattern=r"^rmsel_\d+$"),
            ],
            STATE_CONFIRM_REMOVE_STUDENT: [
                CallbackQueryHandler(remove_student_confirmed, pattern=f"^({CB_CONFIRM_YES}|{CB_CONFIRM_NO})$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_message=True,
    )


# ── Edit Student Name ────────────────────────────────────────────────────────

async def edit_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show student list for editing."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    students = await db.get_students_by_teacher(teacher["id"])

    if not students:
        await query.edit_message_text(
            "لا يوجد طلاب لتعديل أسمائهم.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"edsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "✏️ تعديل اسم طالب\n\nاختر الطالب لتغيير اسمه:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_STUDENT_TO_EDIT


async def edit_student_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for the new name."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.replace("edsel_", ""))
    student = await db.get_student_by_id(student_id)
    if not student:
        await query.edit_message_text("الطالب غير موجود.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_edit_student"] = student
    await query.edit_message_text(
        f"الاسم الحالي: {student['name']}\n\nاكتب الاسم الجديد (أو /cancel للإلغاء):"
    )
    return STATE_WAITING_NEW_NAME


async def edit_student_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the new name."""
    new_name = update.message.text.strip()
    if not new_name:
        await update.message.reply_text("الاسم لا يمكن أن يكون فارغاً. اكتب اسماً صحيحاً:")
        return STATE_WAITING_NEW_NAME

    student = context.user_data.pop("pending_edit_student", None)
    if not student:
        await update.message.reply_text("خطأ: فُقدت بيانات الطالب.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    await db.update_student_name(student["id"], new_name)
    await update.message.reply_text(
        f"✅ تم تغيير اسم الطالب من '{student['name']}' إلى '{new_name}'.",
        reply_markup=manage_students_keyboard(),
    )
    return ConversationHandler.END


def edit_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for editing a student name."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
        return ConversationHandler(
            entry_points=[CallbackQueryHandler(edit_student_start, pattern=f"^{CB_EDIT_STUDENT}$")],
            states={
                STATE_SELECT_STUDENT_TO_EDIT: [
                    CallbackQueryHandler(edit_student_selected, pattern=r"^edsel_\d+$"),
                ],
                STATE_WAITING_NEW_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_student_new_name),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel_handler),
                CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
            ],
            per_message=False,
        )


# ── Move Student ─────────────────────────────────────────────────────────────

async def move_student_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show student list for moving."""
    query = update.callback_query
    await query.answer()

    teacher = context.user_data.get("teacher")
    students = await db.get_students_by_teacher(teacher["id"])

    if not students:
        await query.edit_message_text(
            "لا يوجد طلاب لنقلهم.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"mvsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "🔄 نقل طالب\n\nاختر الطالب لنقله إلى صف آخر:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_STUDENT_TO_MOVE


async def move_student_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of other teachers to move the student to."""
    query = update.callback_query
    await query.answer()

    student_id = int(query.data.replace("mvsel_", ""))
    student = await db.get_student_by_id(student_id)
    if not student:
        await query.edit_message_text("الطالب غير موجود.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_move_student"] = student

    teacher = context.user_data.get("teacher")
    all_teachers = await db.get_all_teachers()
    other_teachers = [t for t in all_teachers if t["id"] != teacher["id"]]

    if not other_teachers:
        await query.edit_message_text(
            "لا يوجد معلمون آخرون لنقل هذا الطالب إليهم.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"mvto_{t['id']}")]
        for t in other_teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        f"نقل '{student['name']}'\n\nاختر صف المعلم المراد النقل إليه:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return STATE_SELECT_TARGET_TEACHER


async def move_student_target_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Move the student to the selected teacher."""
    query = update.callback_query
    await query.answer()

    target_teacher_id = int(query.data.replace("mvto_", ""))
    student = context.user_data.pop("pending_move_student", None)

    if not student:
        await query.edit_message_text("خطأ: فُقدت بيانات الطالب.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    all_teachers = await db.get_all_teachers()
    target_teacher = next((t for t in all_teachers if t["id"] == target_teacher_id), None)
    target_name = target_teacher["name"] if target_teacher else "Unknown"

    await db.move_student(student["id"], target_teacher_id)
    await query.edit_message_text(
        f"✅ تم نقل الطالب '{student['name']}' إلى صف {target_name}.",
        reply_markup=manage_students_keyboard(),
    )
    return ConversationHandler.END


def move_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for moving a student."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(move_student_start, pattern=f"^{CB_MOVE_STUDENT}$")],
        states={
            STATE_SELECT_STUDENT_TO_MOVE: [
                CallbackQueryHandler(move_student_selected, pattern=r"^mvsel_\d+$"),
            ],
            STATE_SELECT_TARGET_TEACHER: [
                CallbackQueryHandler(move_student_target_selected, pattern=r"^mvto_\d+$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=f"^{CB_MAIN_MENU}$"),
        ],
        per_message=True,
    )
