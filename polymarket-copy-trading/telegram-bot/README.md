# Telegram Bot

Lightweight Telegram interface for Polymarket Copy Trading.

## Setup

1. **Install dependencies:**
```bash
cd telegram-bot
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Create Telegram bot:**
   - Talk to [@BotFather](https://t.me/botfather)
   - Create new bot with `/newbot`
   - Copy token to `.env`

4. **Run bot:**
```bash
python -m bot.main
```

## Available Commands

- `/start` - Register or login
- `/menu` - Show main menu  
- `/traders` - View top traders
- `/dashboard` - View your portfolio
- `/copies` - Manage copy relationships
- `/settings` - Account settings
- `/help` - Show help

## Features

✅ User registration via Telegram
✅ Authentication with JWT
✅ Main menu with inline keyboard
✅ Command handlers for all features
✅ Error handling and logging
✅ Admin commands support
✅ Database integration
✅ Backend API client

## Production Deployment

For production, set `USE_TELEGRAM_WEBHOOK=true` and configure `TELEGRAM_WEBHOOK_URL`.

## File Structure

```
telegram-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot application
│   ├── config.py            # Configuration
│   ├── database.py          # Database session
│   ├── api_client.py        # Backend API client
│   ├── middleware.py        # Auth middleware
│   └── handlers/
│       ├── __init__.py
│       ├── basic.py         # Basic commands
│       ├── trading.py       # Trading commands
│       └── errors.py        # Error handler
├── requirements.txt
├── .env.example
└── README.md
```
