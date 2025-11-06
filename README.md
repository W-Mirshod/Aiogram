# Aiogram Gemini Telegram Bot

## Features
- User registration and language selection (English, Russian, Uzbek)
- Topic prompt and Google Gemini API integration for answers
- 3 queries per user per minute (rate limit)
- All queries and answers saved in SQLite database
- Shows other users and their queries on /start
- Docker and Docker Compose support

## Setup

1. Clone the repository and enter the directory:
   ```bash
   git clone <repo-url>
   cd Aiogram
   ```

2. Create a `.env` file with your credentials:
   ```env
   API_TOKEN=your_telegram_bot_token
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. (Optional) Install dependencies locally:
   ```bash
   pip install -r requirements.txt
   ```

4. Run with Docker Compose:
   ```bash
   ./run.sh
   ```

## File Structure
- `main.py` — Bot source code
- `requirements.txt` — Python dependencies
- `.env` — Environment variables (not committed)
- `Dockerfile` — Docker build file
- `docker-compose.yml` — Docker Compose config
- `run.sh` — Script to build and run the bot
- `.gitignore` — Files and folders to ignore in git

## Notes
- The database file `bot.db` is created automatically and ignored by git.
- Make sure your `.env` file is present before running.
