import os
import base64
import time
import json
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
OUTPUT_FILE = 'emails.txt'
CHECK_INTERVAL = 60
SEEN_IDS_FILE = 'seen_ids.json'

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_ids(seen_ids):
    with open(SEEN_IDS_FILE, 'w') as f:
        json.dump(list(seen_ids), f)

def get_email_text(payload):
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                break
    elif payload['mimeType'] == 'text/plain':
        data = payload['body'].get('data', '')
        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return body.strip()

def get_header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return 'Unknown'

def check_new_emails(service, seen_ids):
    results = service.users().messages().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=20
    ).execute()
    messages = results.get('messages', [])
    new_count = 0
    for msg in messages:
        msg_id = msg['id']
        if msg_id in seen_ids:
            continue
        full_msg = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()
        headers = full_msg['payload']['headers']
        subject = get_header(headers, 'Subject')
        sender  = get_header(headers, 'From')
        date    = get_header(headers, 'Date')
        body    = get_email_text(full_msg['payload'])
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write(f"Saved at : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"From     : {sender}\n")
            f.write(f"Date     : {date}\n")
            f.write(f"Subject  : {subject}\n")
            f.write("-" * 60 + "\n")
            f.write(body + "\n\n")
        seen_ids.add(msg_id)
        new_count += 1
        print(f"  Saved: {subject[:60]}")
    return new_count, seen_ids

def main():
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    print("Connected!")
    seen_ids = load_seen_ids()
    print(f"Starting email monitor (checking every {CHECK_INTERVAL}s)")
    print(f"Saving emails to: {OUTPUT_FILE}\n")
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking inbox...")
        try:
            count, seen_ids = check_new_emails(service, seen_ids)
            save_seen_ids(seen_ids)
            if count == 0:
                print("  No new emails.")
            else:
                print(f"  Saved {count} new email(s).")
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()


