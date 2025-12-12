# Telegram AI Bot (Full)

This repository contains a full-featured Telegram AI bot built with python-telegram-bot and OpenAI.

Features:
- Chat with OpenAI (chat completions)
- Per-user short memory (in-memory)
- Menu buttons (Reply keyboard)
- Inline buttons for retry/clear memory
- Voice message handling (convert via ffmpeg + pydub -> Whisper transcription)
- Image receiving (saved; `/analyze` placeholder for image analysis)
- File receiving and basic text file summarization
- Ready for deploy to Render / Railway / Deta

## Setup (local)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install ffmpeg (required for voice processing):
   - Debian/Ubuntu: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`
   - Windows: download from https://ffmpeg.org
3. Set environment variables (or create a `.env` file):
   ```env
   TELEGRAM_TOKEN=your_telegram_token_here
   OPENAI_API_KEY=sk-...
   ```
4. Run:
   ```bash
   python bot.py
   ```

## Deploy
- Use Render / Railway / Deta / Cloud Run
- Provide the environment variables in the service settings.
- Start command: `python bot.py`

## Notes
- Image analysis is a placeholder: full image understanding requires an OpenAI Vision/Responses API and different payloads.
- For production you should persist user memory to a database and secure files/cleanup.
