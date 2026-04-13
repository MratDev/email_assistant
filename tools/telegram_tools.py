import os
import httpx

def send_approval_message(text, markup=None):
    """
    Sends a message to the configured TELEGRAM_CHAT_ID.
    markup: An optional inline keyboard to render interactive buttons.
    Returns the message_id of the sent message.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Telegram credentials missing!")
        return None
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    if markup:
        payload["reply_markup"] = markup
        
    response = httpx.post(url, json=payload)
    response.raise_for_status()
    
    data = response.json()
    if data.get("ok"):
        return data["result"]["message_id"]
    return None
