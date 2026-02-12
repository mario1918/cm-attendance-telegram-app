# Telegram CM Attendance App

A Telegram bot for a church ministry school that allows teachers to take attendance of their students.

## Features

- **Take Attendance** — Teachers see their student list as inline buttons; tap to toggle present/absent for today.
- **Manage Students** — Add, remove, edit student names, or move a student to another teacher's class.
- **Admin Reports** — Admin teachers can download a monthly Excel attendance report for any teacher's class.
- **Teacher Management** — Admins can register or remove teachers.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts to create your bot.
3. Copy the bot token.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and paste your bot token:

```
BOT_TOKEN=your_telegram_bot_token_here
```

### 4. Seed the First Admin

Before running the bot, you need to register the first admin teacher. Find your Telegram user ID by messaging **@userinfobot** on Telegram, then run:

```bash
python seed_admin.py --name "Your Name" --telegram-id YOUR_TELEGRAM_USER_ID
```

### 5. Run the Bot

```bash
python bot.py
```

## Usage

- `/start` — Open the main menu.
- Teachers are identified by their Telegram user ID (must be registered in the database).
- Admin teachers have access to additional options: downloading reports and managing teachers.

## Report Format

The Excel report contains:
- **Header**: Teacher name, month/year
- **Rows**: One per student
- **Columns**: Student Name | Day 1 | Day 2 | … | Day 31 | Total
- **Cells**: ✓ for present, blank for absent
