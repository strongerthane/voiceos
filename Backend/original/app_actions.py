"""
App Actions — Execute actions within opened applications.

Handles compound commands like:
  "open notepad and write hello"
  "open calculator and add 5 and 3"
  "open word and create a document about AI"

Supports:
- Text input via clipboard and keyboard automation
- Auto-saving content locally
- Opening browser fallback if app not found
"""

import os
import re
import time
import subprocess
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

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
        
        # Fallback: use Windows PowerShell
        try:
            # Escape quotes for PowerShell
            escaped = text.replace('"', '\"')
            cmd = f'powershell -Command "Set-Clipboard -Value \'{escaped}\'"'
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
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
        test_str = query.lower().strip()
        
        for pattern, action_type in patterns:
            m = re.match(pattern, test_str)
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
            # Launch the application
            proc = subprocess.Popen(f'start "" "{app_path}"', shell=True)
            time.sleep(2)  # Wait for app to open
            
            # Copy content to clipboard
            if not self._copy_to_clipboard(content):
                return False, f"Failed to copy text to clipboard"
            
            # Send paste command
            subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                          '[System.Windows.Forms.SendKeys]::SendWait(\"^v\")"',
                          shell=True, capture_output=True)
            
            # Auto-save for text editors
            if app_name.lower() in ("notepad", "text", "editor", "wordpad"):
                time.sleep(0.5)
                # Save file
                subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                              '[System.Windows.Forms.SendKeys]::SendWait(\"^s\")"',
                              shell=True, capture_output=True)
                time.sleep(1)
                
                # Save to default location
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(self.save_dir, f"note_{timestamp}.txt")
                
                # Type the filename
                if self._copy_to_clipboard(filename):
                    subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                                  '[System.Windows.Forms.SendKeys]::SendWait(\"^a\")"',
                                  shell=True, capture_output=True)
                    subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                                  '[System.Windows.Forms.SendKeys]::SendWait(\"^v\")"',
                                  shell=True, capture_output=True)
                    time.sleep(0.5)
                    
                    # Press Enter to save
                    subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                                  '[System.Windows.Forms.SendKeys]::SendWait(\"{ENTER}\")"',
                                  shell=True, capture_output=True)
                
                return True, f"Opened {app_name} and wrote '{content[:50]}...'. Saved to {filename}"
            
            return True, f"Opened {app_name} and wrote '{content}'"
        
        except Exception as e:
            return False, f"Failed to execute action in {app_name}: {e}"

    def execute_create_action(self, app_name: str, request: str, app_path: str) -> Tuple[bool, str]:
        """
        Open an app and create content as requested.
        Similar to write but for more complex creation requests.
        """
        try:
            subprocess.Popen(f'start "" "{app_path}"', shell=True)
            time.sleep(2)
            
            # For Word/Office, could use more sophisticated creation
            if app_name.lower() in ("word", "excel", "office", "powerpoint"):
                # Just notify that app is open
                return True, f"Opened {app_name}. Ready to create: {request}"
            else:
                # For text editors, just write the request as a template
                if self._copy_to_clipboard(request):
                    subprocess.run('powershell -Command "Add-Type -AssemblyName System.Windows.Forms; '
                                  '[System.Windows.Forms.SendKeys]::SendWait(\"^v\")"',
                                  shell=True, capture_output=True)
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
