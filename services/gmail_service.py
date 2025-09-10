from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GMAIL_SCOPES
from models import User


class GmailService:
    def __init__(self):
        self.client_config = {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        }

    def get_auth_url(self) -> str:
        """Generate OAuth2 authorization URL"""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=GMAIL_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url

    async def handle_oauth_callback(self, code: str) -> dict:
        """Handle OAuth callback and save user credentials"""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=GMAIL_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI
        )
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Get user info
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile['emailAddress']
        
        # Save or update user
        user, created = await User.get_or_create(
            email=email_address,
            defaults={
                'gmail_token': credentials.token,
                'gmail_refresh_token': credentials.refresh_token,
                'is_active': True
            }
        )
        
        if not created:
            user.gmail_token = credentials.token
            user.gmail_refresh_token = credentials.refresh_token
            user.is_active = True
            await user.save()
        
        return {'user_id': user.id, 'email': email_address}

    async def get_credentials(self, user: User) -> Credentials:
        """Get valid credentials for a user"""
        creds = Credentials(
            token=user.gmail_token,
            refresh_token=user.gmail_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET
        )
        
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Update stored tokens
                user.gmail_token = creds.token
                await user.save()
        
        return creds

    async def get_service(self, user: User):
        """Get Gmail API service for a user"""
        credentials = await self.get_credentials(user)
        return build('gmail', 'v1', credentials=credentials)

    async def list_messages(self, user: User, query: str = 'is:unread', max_results: int = 10) -> list:
        """List Gmail messages for a user"""
        try:
            service = await self.get_service(user)
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except Exception as e:
            print(f"Error listing messages: {e}")
            return []

    async def get_message(self, user: User, message_id: str) -> dict:
        """Get a specific Gmail message"""
        try:
            service = await self.get_service(user)
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract relevant information
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            
            # Get message body
            body = self.extract_message_body(message['payload'])
            
            return {
                'id': message['id'],
                'subject': subject,
                'sender': sender,
                'body': body,
                'raw_message': message
            }
        except Exception as e:
            print(f"Error getting message: {e}")
            return None

    def extract_message_body(self, payload) -> str:
        """Extract text body from Gmail message payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
                elif part['mimeType'] == 'text/html' and not body:
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body

    async def send_email(self, user: User, to_email: str, subject: str, body: str, reply_to_message_id: str = None) -> bool:
        """Send an email"""
        try:
            service = await self.get_service(user)
            
            message = MIMEMultipart()
            message['To'] = to_email
            message['Subject'] = subject
            
            if reply_to_message_id:
                # Get original message for proper threading
                original_message = await self.get_message(user, reply_to_message_id)
                if original_message:
                    message['In-Reply-To'] = reply_to_message_id
                    message['References'] = reply_to_message_id
            
            message.attach(MIMEText(body, 'plain'))
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            send_message = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    async def mark_as_read(self, user: User, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            service = await self.get_service(user)
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            return True
        except Exception as e:
            print(f"Error marking message as read: {e}")
            return False