"""Student management flows — add, remove, edit, move students."""
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
        "➕ Add Student\n\nType the student's name (or /cancel to go back):"
    )
    return STATE_WAITING_STUDENT_NAME


async def add_student_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the new student."""
    teacher = context.user_data.get("teacher")
    if not teacher:
        await update.message.reply_text("⛔ Session expired. Please /start again.")
        return ConversationHandler.END

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty. Please type a valid name:")
        return STATE_WAITING_STUDENT_NAME

    await db.add_student(name, teacher["id"])
    is_admin = bool(teacher["is_admin"])
    await update.message.reply_text(
        f"✅ Student '{name}' added to your class.",
        reply_markup=manage_students_keyboard(),
    )
    return ConversationHandler.END


def add_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for adding a student."""
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
            "You have no students to remove.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"rmsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "❌ Remove Student\n\nSelect the student to remove:",
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
        await query.edit_message_text("Student not found.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_remove_student"] = student

    buttons = [
        [
            InlineKeyboardButton("✅ Yes, remove", callback_data=CB_CONFIRM_YES),
            InlineKeyboardButton("❌ No, cancel", callback_data=CB_CONFIRM_NO),
        ]
    ]
    await query.edit_message_text(
        f"Are you sure you want to remove '{student['name']}'?\n"
        "This will also delete all their attendance records.",
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
                f"✅ Student '{student['name']}' has been removed.",
                reply_markup=manage_students_keyboard(),
            )
        else:
            await query.edit_message_text("Error: student data lost.", reply_markup=manage_students_keyboard())
    else:
        context.user_data.pop("pending_remove_student", None)
        await query.edit_message_text(
            "Removal cancelled.",
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
        per_message=False,
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
            "You have no students to edit.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"edsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "✏️ Edit Student Name\n\nSelect the student to rename:",
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
        await query.edit_message_text("Student not found.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_edit_student"] = student
    await query.edit_message_text(
        f"Current name: {student['name']}\n\nType the new name (or /cancel):"
    )
    return STATE_WAITING_NEW_NAME


async def edit_student_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the new name."""
    new_name = update.message.text.strip()
    if not new_name:
        await update.message.reply_text("Name cannot be empty. Please type a valid name:")
        return STATE_WAITING_NEW_NAME

    student = context.user_data.pop("pending_edit_student", None)
    if not student:
        await update.message.reply_text("Error: student data lost.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    await db.update_student_name(student["id"], new_name)
    await update.message.reply_text(
        f"✅ Student renamed from '{student['name']}' to '{new_name}'.",
        reply_markup=manage_students_keyboard(),
    )
    return ConversationHandler.END


def edit_student_conversation() -> ConversationHandler:
    """Build ConversationHandler for editing a student name."""
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
            "You have no students to move.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(s["name"], callback_data=f"mvsel_{s['id']}")]
        for s in students
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        "🔄 Move Student\n\nSelect the student to move to another class:",
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
        await query.edit_message_text("Student not found.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    context.user_data["pending_move_student"] = student

    teacher = context.user_data.get("teacher")
    all_teachers = await db.get_all_teachers()
    other_teachers = [t for t in all_teachers if t["id"] != teacher["id"]]

    if not other_teachers:
        await query.edit_message_text(
            "There are no other teachers to move this student to.",
            reply_markup=manage_students_keyboard(),
        )
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(t["name"], callback_data=f"mvto_{t['id']}")]
        for t in other_teachers
    ]
    buttons.append([InlineKeyboardButton("🔙 Cancel", callback_data=CB_MAIN_MENU)])

    await query.edit_message_text(
        f"Moving '{student['name']}'\n\nSelect the destination teacher's class:",
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
        await query.edit_message_text("Error: student data lost.", reply_markup=manage_students_keyboard())
        return ConversationHandler.END

    all_teachers = await db.get_all_teachers()
    target_teacher = next((t for t in all_teachers if t["id"] == target_teacher_id), None)
    target_name = target_teacher["name"] if target_teacher else "Unknown"

    await db.move_student(student["id"], target_teacher_id)
    await query.edit_message_text(
        f"✅ Student '{student['name']}' moved to {target_name}'s class.",
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
        per_message=False,
    )
