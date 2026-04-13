# Email Assistant

An automated email assistant built with **LangGraph**, **FastAPI**, and **OpenAI**. It polls your Gmail for unread emails, categorizes them, and performs actions like drafting replies or scheduling meetings based on the content, with a human-in-the-loop approval step via Telegram.

## Features

- **Gmail Integration**: Automated polling of unread primary emails.
- **Intelligent Categorization**: Uses LLM to decide if an email needs a draft reply, a calendar meeting, or can be ignored.
- **Human-in-the-Loop**: Sends approval requests to Telegram before executing sensitive actions.
- **Automated Actions**:
  - Creates Gmail drafts.
  - Schedules Google Calendar meetings.
  - Marks processed emails as read.

## Project Structure

```text
google_client_secrets.json  # Google OAuth credentials (get from Google Cloud)
google_token.json           # Generated OAuth token (not in version control)
graph.py                   # LangGraph workflow definition
main.py                    # FastAPI server & Gmail polling loop
requirements.txt           # Python dependencies
tools/
    google_tools.py        # Gmail and Calendar API wrappers
    telegram_tools.py      # Telegram Bot integration
```

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MratDev/email_assistant.git
   cd email_assistant
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**:
   - Create a `.env` file in the root directory with the following variables:
     ```env
     OPENAI_API_KEY=your_openai_api_key
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token
     TELEGRAM_CHAT_ID=your_telegram_chat_id
     ```
   - Place your `google_client_secrets.json` in the root directory. You can obtain this from the [Google Cloud Console](https://console.cloud.google.com/).

5. **Authenticate Google Service**:
   Run the application once to trigger the OAuth flow and generate `google_token.json`.

## Usage

Start the FastAPI server:
```bash
uvicorn main:app --reload
```

The application will start polling your Gmail and sending approval requests to your Telegram bot for any actionable emails found.

## Tools and Technologies

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenAI GPT-4o](https://openai.com/)
- [Google APIs](https://developers.google.com/gmail/api)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (via httpx)
