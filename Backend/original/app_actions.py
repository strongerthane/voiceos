"""
App Actions — Execute actions within opened applications.

Handles compound commands like:
  "open notepad and write hello"
  "open calculator and add 5 and 3"
  "open word and create a document about AI"

Supports:
- Text input via clipboard and keyboard automation
- Auto-saving content locally
- Emailing saved files
- Uploading to cloud storage (OneDrive, Google Drive)
- Opening browser fallback if app not found
"""

import os
import re
import time
import subprocess
import base64
import smtplib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class AppActions:
    """Execute actions within applications."""

    @staticmethod
    def _copy_to_clipboard(text: str) -> bool:
        """Copy text to clipboard using available method."""
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                pass

        if os.name != "nt":
            return False

        try:
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            script = (
                "$value = [Text.Encoding]::UTF8.GetString("
                f"[Convert]::FromBase64String('{encoded}')); "
                "Set-Clipboard -Value $value"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=10, check=False
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _launch_app(app_path: str) -> bool:
        """Launch an app path without interpolating it into a shell command."""
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["cmd.exe", "/c", "start", "", app_path],
                    close_fds=True
                )
            else:
                subprocess.Popen([app_path])
            return True
        except OSError:
            return False

    @staticmethod
    def _paste_into_app(app_name: str) -> bool:
        """Activate the requested app and paste; never type into another window."""
        if os.name != "nt":
            return False

        try:
            target = base64.b64encode(app_name.encode("utf-8")).decode("ascii")
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$target = [Text.Encoding]::UTF8.GetString("
                f"[Convert]::FromBase64String('{target}')); "
                "$shell = New-Object -ComObject WScript.Shell; "
                "if (-not $shell.AppActivate($target)) { exit 2 }; "
                "Start-Sleep -Milliseconds 250; "
                "$shell.SendKeys('^v')"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=10, check=False
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def __init__(self, save_dir: Optional[str] = None):
        """
        Initialize app actions handler.
        
        Args:
            save_dir: Directory to save created files. Defaults to Documents/VoiceOS
        """
        if save_dir is None:
            docs_dir = os.path.expanduser("~\\Documents")
            self.save_dir = os.path.join(docs_dir, "VoiceOS")
        else:
            self.save_dir = save_dir
        
        os.makedirs(self.save_dir, exist_ok=True)

    def parse_compound_action(self, target: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Parse compound actions like 'open notepad and write hello'.
        
        Returns intent with action_type and params, or None if not a compound action.
        """
        # Pattern: "open <app> and <action> <content>"
        patterns = [
            (r"^open\s+(.+?)\s+and\s+write\s+(.+)$", "write"),
            (r"^open\s+(.+?)\s+and\s+type\s+(.+)$", "write"),
            (r"^open\s+(.+?)\s+and\s+create\s+(.+)$", "create"),
            (r"^open\s+(.+?)\s+and\s+(?:add|calculate)\s+(.+)$", "calculate"),
            (r"^open\s+(.+?)\s+and\s+search\s+(.+)$", "search"),
        ]
        
        # Try to match the query string if available
        test_str = " ".join(query.strip().split())
        
        for pattern, action_type in patterns:
            m = re.match(pattern, test_str, re.IGNORECASE)
            if m:
                app_name = m.group(1).strip()
                content = m.group(2).strip() if len(m.groups()) > 1 else ""
                return {
                    "app": app_name,
                    "action_type": action_type,
                    "content": content
                }
        
        return None

    def execute_write_action(self, app_name: str, content: str, app_path: str) -> Tuple[bool, str]:
        """
        Open an app and write content to it, then save.
        
        Args:
            app_name: Name of the application
            content: Text to write
            app_path: Path to the executable
        
        Returns:
            (success, detail_message)
        """
        try:
            if not self._launch_app(app_path):
                return False, f"Could not launch {app_name}."
            time.sleep(1.5)

            if not self._copy_to_clipboard(content):
                return False, "Could not copy dictated text to the clipboard."
            if not self._paste_into_app(app_name):
                return False, (
                    f"Opened {app_name}, but could not safely activate it to paste. "
                    "The text was not sent to another window."
                )

            if app_name.lower() in ("notepad", "text", "editor", "wordpad"):
                success, filepath = self.save_text_locally(content, "note", "txt")
                if not success:
                    return False, f"Text was pasted into {app_name}, but saving locally failed: {filepath}"
                return True, f"Opened {app_name}, typed your text, and saved a copy to {filepath}."
            
            return True, f"Opened {app_name} and wrote '{content}'"
        
        except Exception as e:
            return False, f"Failed to execute action in {app_name}: {e}"

    def execute_create_action(self, app_name: str, request: str, app_path: str) -> Tuple[bool, str]:
        """
        Open an app and create content as requested.
        Similar to write but for more complex creation requests.
        """
        try:
            if not self._launch_app(app_path):
                return False, f"Could not launch {app_name}."
            time.sleep(2)
            
            # For Word/Office, could use more sophisticated creation
            if app_name.lower() in ("word", "excel", "office", "powerpoint"):
                # Just notify that app is open
                return True, f"Opened {app_name}. Ready to create: {request}"
            else:
                # For text editors, just write the request as a template
                if self._copy_to_clipboard(request) and self._paste_into_app(app_name):
                    return True, f"Opened {app_name} and started creating: {request}"
                else:
                    return False, f"Failed to paste content into {app_name}"
        
        except Exception as e:
            return False, f"Failed to create in {app_name}: {e}"

    def save_text_locally(self, content: str, app_name: str = "text", 
                         extension: str = "txt") -> Tuple[bool, str]:
        """
        Save text content to a local file.
        
        Args:
            content: Text to save
            app_name: Name of app/context
            extension: File extension (txt, md, html, etc.)
        
        Returns:
            (success, filepath)
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{app_name}_{timestamp}.{extension}"
            filepath = os.path.join(self.save_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, filepath
        except Exception as e:
            return False, f"Failed to save: {e}"

    def open_app_in_browser_fallback(self, app_name: str) -> str:
        """
        If app not found, open a web search for it instead.
        
        Returns the search URL.
        """
        from urllib.parse import quote_plus
        search_url = f"https://www.microsoft.com/en-us/search/result?q={quote_plus(app_name)}+download"
        return search_url


# Test functionality
if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    actions = AppActions()
    
    # Test parsing compound actions
    test_queries = [
        "open notepad and write hello world",
        "open calculator and add 5 and 3",
        "open word and create a document about AI",
    ]
    
    print("Testing compound action parsing...")
    for query in test_queries:
        result = actions.parse_compound_action("", query)
        if result:
            print(f"[OK] '{query}' -> {result}")
        else:
            print(f"[SKIP] '{query}' (not compound)")
    
    # Test save functionality
    print("\nTesting local file saving...")
    success, filepath = actions.save_text_locally("Hello from VoiceOS!", "test", "txt")
    if success:
        print(f"[OK] Saved to {filepath}")
    else:
        print(f"[ERROR] {filepath}")
    
    print("\n[OK] App actions module OK")

    @staticmethod
    def email_file(filepath: str, recipient_email: str, subject: str = "VoiceOS File", 
                   sender_email: str = None, sender_password: str = None) -> Tuple[bool, str]:
        """
        Email a saved file to a recipient.
        
        Args:
            filepath: Path to file to email
            recipient_email: Recipient's email address
            subject: Email subject
            sender_email: Sender's email (from voiceos_config.json or environment)
            sender_password: Sender's app password (from voiceos_config.json or environment)
        
        Returns:
            (success, message)
        """
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"
        
        # Get credentials from environment if not provided
        if not sender_email:
            sender_email = os.getenv("VOICEOS_EMAIL_SENDER")
        if not sender_password:
            sender_password = os.getenv("VOICEOS_EMAIL_PASSWORD")
        
        if not sender_email or not sender_password:
            return False, "Email credentials not configured. Set VOICEOS_EMAIL_SENDER and VOICEOS_EMAIL_PASSWORD environment variables."
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            body = f"VoiceOS has automatically saved and emailed your file.\n\nFile: {os.path.basename(filepath)}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach file
            with open(filepath, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(filepath)}')
                msg.attach(part)
            
            # Send via Gmail SMTP (supports app passwords)
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
            return True, f"Email sent to {recipient_email}"
        
        except Exception as e:
            return False, f"Email failed: {str(e)}"
    
    @staticmethod
    def upload_to_onedrive(filepath: str, folder_name: str = "VoiceOS") -> Tuple[bool, str]:
        """
        Upload saved file to OneDrive (Windows built-in).
        
        Args:
            filepath: Path to file to upload
            folder_name: OneDrive folder name (default: VoiceOS)
        
        Returns:
            (success, message)
        """
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"
        
        try:
            # OneDrive is typically at: C:\Users\[user]\OneDrive
            username = os.getenv('USERNAME')
            onedrive_path = Path(f"C:\\Users\\{username}\\OneDrive\\{folder_name}")
            
            if not onedrive_path.exists():
                onedrive_path.mkdir(parents=True, exist_ok=True)
            
            # Copy file to OneDrive
            dest_path = onedrive_path / os.path.basename(filepath)
            with open(filepath, 'rb') as src:
                with open(dest_path, 'wb') as dst:
                    dst.write(src.read())
            
            return True, f"Uploaded to OneDrive: {dest_path}"
        
        except Exception as e:
            return False, f"OneDrive upload failed: {str(e)}"
    
    @staticmethod
    def upload_to_google_drive(filepath: str, folder_id: str = None) -> Tuple[bool, str]:
        """
        Upload saved file to Google Drive (requires google-auth-oauthlib).
        
        Args:
            filepath: Path to file to upload
            folder_id: Google Drive folder ID (optional)
        
        Returns:
            (success, message)
        """
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"
        
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            return False, "Google Drive upload requires: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        
        try:
            # Get credentials (requires OAuth setup)
            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            creds = None
            
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    return False, "Google Drive credentials not configured. Run OAuth setup first."
            
            # Upload file
            service = build('drive', 'v3', credentials=creds)
            file_metadata = {'name': os.path.basename(filepath)}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(filepath, resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            return True, f"Uploaded to Google Drive: {file.get('id')}"
        
        except Exception as e:
            return False, f"Google Drive upload failed: {str(e)}"
