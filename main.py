import os
import json
import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from dotenv import load_dotenv
import httpx
from langgraph.types import Command

# Load environment logic
load_dotenv()

from graph import graph
from tools.google_tools import get_unread_primary_emails
from tools.telegram_tools import send_approval_message

# We need to store mapping of telegram message ID to thread ID
# so when user clicks 'Approve', we know which thread to resume.
# Also store pending interrupts.
PENDING_APPROVALS = {}

async def poll_gmail():
    """Background task to poll Gmail every minute."""
    print("Started Gmail polling...")
    while True:
        try:
            emails = get_unread_primary_emails()
            for email in emails:
                thread_id = email['id']
                # Start LangGraph thread if we aren't already tracking it
                config = {"configurable": {"thread_id": thread_id}}
                state = graph.get_state(config)
                
                # Check if it was ever started
                if state and state.next:
                    # It's already in progress or paused
                    continue
                if state and not state.next and state.values:
                    # It already finished
                    continue
                
                print(f"Processing new email: {email['subject']}")
                
                initial_state = {
                    "email_id": thread_id,
                    "email_subject": email['subject'],
                    "email_sender": email['sender'],
                    "email_body": email['body']
                }
                
                # Run graph until it pauses (hits human_review interrupt)
                result = graph.invoke(initial_state, config)
                
                # If there's an interrupt, handle it
                if '__interrupt__' in result and len(result['__interrupt__']) > 0:
                    interrupt_val = result['__interrupt__'][0].value
                    intent = interrupt_val['intent']
                    
                    if intent == 'draft':
                        text = (
                            f"<b>Email:</b> {interrupt_val['subject']}\n"
                            f"<b>Action:</b> Create Draft\n\n"
                            f"<b>Draft Body:</b>\n{interrupt_val['draft_body']}\n\n"
                            f"Do you approve?"
                        )
                    elif intent == 'meeting':
                        details = interrupt_val['meeting_details']
                        text = (
                            f"<b>Email:</b> {interrupt_val['subject']}\n"
                            f"<b>Action:</b> Schedule Meeting\n"
                            f"<b>Title:</b> {details.get('summary')}\n"
                            f"<b>Start:</b> {details.get('start_time')}\n\n"
                            f"Do you approve?"
                        )
                    else:
                        text = f"Action unknown for {interrupt_val['subject']}"
                        
                    # Create inline keyboard for Approve / Reject
                    markup = {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Approve", "callback_data": f"approve_{thread_id}"},
                                {"text": "❌ Reject", "callback_data": f"reject_{thread_id}"}
                            ]
                        ]
                    }
                    
                    msg_id = send_approval_message(text, markup)
                    if msg_id:
                        PENDING_APPROVALS[msg_id] = thread_id
            
        except Exception as e:
            print(f"Error polling emails: {e}")
            
        await asyncio.sleep(60)

async def poll_telegram():
    """Background task to poll Telegram for callback queries (local use workaround)."""
    print("Started Telegram polling...")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    offset = 0
    timeout = 30
    
    async with httpx.AsyncClient(timeout=timeout+5) as client:
        while True:
            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout={timeout}"
                response = await client.get(url)
                data = response.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        if "callback_query" in update:
                            query = update["callback_query"]
                            cb_data = query["data"]
                            
                            action, thread_id = cb_data.split("_", 1)
                            config = {"configurable": {"thread_id": thread_id}}
                            
                            if action == "approve":
                                resume_data = {"approved": True}
                            else:
                                resume_data = {"approved": False}
                                
                            try:
                                print(f"Resuming thread {thread_id} with {resume_data}")
                                graph.invoke(Command(resume=resume_data), config)
                                send_approval_message(
                                    f"Action <b>{'approved' if action == 'approve' else 'rejected'}</b> for email.",
                                    markup=None
                                )
                            except Exception as e:
                                print(f"Failed to resume graph: {e}")
            except httpx.ReadTimeout:
                continue
            except Exception as e:
                print(f"Error polling Telegram: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background polling tasks
    gmail_task = asyncio.create_task(poll_gmail())
    telegram_task = asyncio.create_task(poll_telegram())
    yield
    # Shutdown
    gmail_task.cancel()
    telegram_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
