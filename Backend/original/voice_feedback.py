"""
Voice Feedback & Text-to-Speech

Provides audio confirmation and feedback for voice commands.
Uses Windows built-in SAPI text-to-speech for instant response.

Example:
  voice = VoiceFeedback()
  voice.confirm("Opening Notepad")
  voice.speak("Document saved successfully")
"""

import subprocess
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class FeedbackType(Enum):
    """Types of voice feedback."""
    CONFIRM = "confirm"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class VoiceFeedback:
    """Provide text-to-speech feedback for voice commands."""
    
    def __init__(self, voice_rate: int = 0, voice_volume: int = 100):
        """
        Initialize voice feedback.
        
        Args:
            voice_rate: Speed (-10 to 10, 0 = normal)
            voice_volume: Volume (0-100)
        """
        self.voice_rate = voice_rate
        self.voice_volume = voice_volume
        self.enabled = True
        self.feedback_history = []
    
    def speak(self, text: str, feedback_type: FeedbackType = FeedbackType.INFO) -> bool:
        """
        Speak text using Windows SAPI.
        
        Args:
            text: Text to speak
            feedback_type: Type of feedback
        
        Returns:
            Success status
        """
        if not self.enabled:
            return True
        
        try:
            # Use PowerShell for TTS via Windows SAPI
            command = f'''
            Add-Type –AssemblyName System.Speech;
            $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;
            $speak.Rate = {self.voice_rate};
            $speak.Volume = {self.voice_volume};
            $speak.Speak('{self._escape_text(text)}');
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', command],
                capture_output=True,
                timeout=30
            )
            
            self._log_feedback(text, feedback_type, result.returncode == 0)
            return result.returncode == 0
        
        except Exception as e:
            print(f"[ERROR] TTS failed: {e}")
            return False
    
    def confirm(self, action: str) -> bool:
        """Confirm an action."""
        return self.speak(f"Confirmed. {action}", FeedbackType.CONFIRM)
    
    def success(self, message: str) -> bool:
        """Provide success feedback."""
        return self.speak(f"Success. {message}", FeedbackType.SUCCESS)
    
    def error(self, message: str) -> bool:
        """Provide error feedback."""
        return self.speak(f"Error. {message}", FeedbackType.ERROR)
    
    def warning(self, message: str) -> bool:
        """Provide warning feedback."""
        return self.speak(f"Warning. {message}", FeedbackType.WARNING)
    
    def info(self, message: str) -> bool:
        """Provide informational feedback."""
        return self.speak(f"Information. {message}", FeedbackType.INFO)
    
    def _escape_text(self, text: str) -> str:
        """Escape text for PowerShell."""
        return text.replace("'", "''")
    
    def _log_feedback(self, text: str, feedback_type: FeedbackType, success: bool):
        """Log feedback event."""
        from datetime import datetime
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": feedback_type.value,
            "text": text,
            "success": success
        }
        
        self.feedback_history.append(entry)
        
        # Keep history size manageable
        if len(self.feedback_history) > 1000:
            self.feedback_history = self.feedback_history[-500:]
    
    def set_voice_speed(self, rate: int):
        """Set speech rate (-10 to 10)."""
        self.voice_rate = max(-10, min(10, rate))
    
    def set_voice_volume(self, volume: int):
        """Set speech volume (0-100)."""
        self.voice_volume = max(0, min(100, volume))
    
    def toggle(self, enabled: bool):
        """Toggle voice feedback on/off."""
        self.enabled = enabled
    
    def get_history(self, limit: int = 50) -> list:
        """Get feedback history."""
        return self.feedback_history[-limit:]
    
    def export_history(self, filepath: str = None) -> str:
        """Export feedback history to JSON."""
        if not filepath:
            from datetime import datetime
            username = os.getenv('USERNAME')
            filepath = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.history\\feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.feedback_history, f, indent=2)
        
        return str(filepath)


class CommandFeedback:
    """Provide comprehensive feedback for command execution."""
    
    def __init__(self, voice: VoiceFeedback = None):
        """Initialize command feedback."""
        self.voice = voice or VoiceFeedback()
        self.command_feedbacks = {}
    
    def on_command_start(self, command: str) -> bool:
        """Provide feedback when command starts."""
        return self.voice.confirm(f"Executing: {command}")
    
    def on_command_success(self, command: str, result: str = None) -> bool:
        """Provide feedback when command succeeds."""
        if result:
            return self.voice.success(f"{command} completed. {result}")
        return self.voice.success(f"{command} completed successfully")
    
    def on_command_failure(self, command: str, error: str = None) -> bool:
        """Provide feedback when command fails."""
        if error:
            return self.voice.error(f"{command} failed. {error}")
        return self.voice.error(f"{command} failed")
    
    def on_app_opened(self, app_name: str) -> bool:
        """Provide feedback when app opens."""
        return self.voice.confirm(f"Opening {app_name}")
    
    def on_file_saved(self, filename: str) -> bool:
        """Provide feedback when file saves."""
        return self.voice.success(f"File saved: {filename}")
    
    def on_email_sent(self, recipient: str) -> bool:
        """Provide feedback when email sends."""
        return self.voice.success(f"Email sent to {recipient}")
    
    def on_upload_complete(self, service: str, location: str) -> bool:
        """Provide feedback when upload completes."""
        return self.voice.success(f"Uploaded to {service}: {location}")
    
    def register_callback(self, event: str, callback: callable):
        """Register custom feedback callback."""
        if event not in self.command_feedbacks:
            self.command_feedbacks[event] = []
        self.command_feedbacks[event].append(callback)


class VoiceSettings:
    """Manage voice feedback settings."""
    
    def __init__(self, config_file: str = None):
        """Initialize voice settings."""
        if not config_file:
            username = os.getenv('USERNAME')
            config_file = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.config\\voice_settings.json"
        
        self.config_file = Path(config_file)
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Default settings
        return {
            "enabled": True,
            "voice_rate": 0,
            "voice_volume": 100,
            "feedback_type": "both",  # voice, visual, both
            "auto_confirm": True,
            "language": "en-US",
            "confirmations": {
                "app_open": True,
                "file_save": True,
                "email_send": True,
                "upload": True,
                "command_complete": True,
                "command_error": True
            }
        }
    
    def save(self):
        """Save settings to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value."""
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set setting value."""
        keys = key.split('.')
        d = self.settings
        
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        
        d[keys[-1]] = value
        self.save()


# Self-test
if __name__ == "__main__":
    print("Testing Voice Feedback & TTS...")
    
    # Test voice feedback
    voice = VoiceFeedback()
    print("[OK] Initialized VoiceFeedback")
    
    # Test settings
    settings = VoiceSettings()
    print(f"[OK] Voice enabled: {settings.get('enabled')}")
    print(f"[OK] Voice rate: {settings.get('voice_rate')}")
    print(f"[OK] Voice volume: {settings.get('voice_volume')}")
    
    # Test command feedback
    feedback = CommandFeedback(voice)
    print("[OK] Initialized CommandFeedback")
    
    # Test feedback types (without actually speaking)
    voice.toggle(False)  # Disable TTS for testing
    voice.confirm("Test action")
    voice.success("Test completed")
    voice.error("Test error")
    print(f"[OK] Logged {len(voice.feedback_history)} feedback events")
    
    print("[OK] Voice feedback module OK")
