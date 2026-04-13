import os
import json
import base64
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar'
]

def get_credentials():
    creds = None
    token_path = 'google_token.json'
    creds_path = 'google_client_secrets.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def get_calendar_service():
    creds = get_credentials()
    return build('calendar', 'v3', credentials=creds)

def get_unread_primary_emails():
    """Fetches unread emails from the Primary category."""
    service = get_gmail_service()
    
    # Query for unread emails in the primary inbox
    query = 'is:unread category:primary'
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    email_data = []
    if not messages:
        return email_data
        
    for msg in messages:
        msg_id = msg['id']
        msg_detail = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Extract headers
        headers = msg_detail.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        
        # Extract body
        body = ""
        if 'parts' in msg_detail['payload']:
            parts = msg_detail['payload']['parts']
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8')
        elif 'body' in msg_detail['payload'] and 'data' in msg_detail['payload']['body']:
            data = msg_detail['payload']['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8')
            
        email_data.append({
            'id': msg_id,
            'subject': subject,
            'sender': sender,
            'body': body
        })
        
    return email_data

def mark_email_as_read(msg_id):
    """Removes the UNREAD label from a specific email."""
    service = get_gmail_service()
    service.users().messages().modify(
        userId='me', 
        id=msg_id, 
        body={'removeLabelIds': ['UNREAD']}
    ).execute()
    return True

def create_gmail_draft(sender, subject, body):
    """Creates a draft email."""
    service = get_gmail_service()
    message = EmailMessage()
    
    message.set_content(body)
    # Typically drafting to the original sender
    message['To'] = sender
    message['From'] = 'me'
    message['Subject'] = f"Re: {subject}"
    
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {'message': {'raw': encoded_message}}
    
    draft = service.users().drafts().create(userId='me', body=create_message).execute()
    return draft

def schedule_calendar_meeting(summary, description, start_time, end_time, attendees=None):
    """
    Schedules a meeting in google calendar.
    start_time and end_time MUST be ISO formatted strings: '2023-10-15T09:00:00-07:00'
    """
    service = get_calendar_service()
    
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
        },
        'attendees': [{'email': attendee} for attendee in (attendees or [])]
    }
    
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event
