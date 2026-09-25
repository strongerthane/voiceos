# VoiceOS

VoiceOS is a compact desktop voice assistant with a top-of-screen liquid-glass interface, reactive listening waveform, sounddevice microphone capture, NVIDIA GLM/OpenAI-compatible AI routing, and text-to-speech responses.

## Features

### Core Features
- **Desktop App Launcher**: Opens any installed application on your computer by voice (e.g., "open notepad", "launch chrome")
- **Web Search & Navigation**: Search the web and open websites
- **YouTube Deep-Linking**: Play specific videos directly (e.g., "play lofi beats on youtube")
- **Email Drafting**: Compose emails through your default mail client (human presses Send)
- **Claude Code Integration**: Delegate code/file creation to Claude CLI
- **Offline Actions**: Open apps, websites, and search without AI backends
- **Hybrid AI Tiers**: Easy questions → Ollama (local), hard questions → OpenAI-compatible API

### Advanced Features
- **📊 Command History & Analytics**: Track all voice commands, success rates, execution times, and usage patterns
- **🔄 Workflow Automation**: Chain multiple commands into automated workflows with retries and conditional execution
- **🎯 Smart App Plugins**: Specialized handlers for Word, Excel, Outlook, PowerPoint (send emails, create documents, etc.)
- **🔍 Desktop Search**: Full-text search across all saved files with advanced filtering
- **📅 Command Scheduling**: Schedule commands to run at specific times, daily, weekly, or on custom schedules
- **🔊 Voice Feedback (TTS)**: Real-time audio confirmations and responses via Windows SAPI
- **📁 Automated File Organization**: Auto-sort files by date, app type, or custom tags with archiving

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- A working microphone
- An API key for the provider you configure (keep it local; never commit it)

## Setup

1. Clone the repository:

   ```bat
   git clone https://github.com/strongerthane/voiceos.git
   cd voiceos
   ```

2. Create and activate a virtual environment:

   ```bat
   py -3 -m venv Backend\original\.venv
   Backend\original\.venv\Scripts\activate
   ```

3. Install the required packages:

   ```bat
   python -m pip install --upgrade pip
   python -m pip install sounddevice numpy SpeechRecognition requests
   ```

   PyAudio and Windows Voice Access are not required.

## Configure AI access

VoiceOS reads API settings from environment variables. Set the provider URL, model, and key according to `Backend/original/AI_SETUP.md`. For example, set your key only in the current terminal session:

```bat
set VOICEOS_API_KEY=your-key-here
```

Do not put real keys in Python files, JSON files, screenshots, or Git commits. The repository ignores `.env` files and common credential filenames.

## Run with Ollama (local and private)

VoiceOS can use Ollama instead of a cloud API. Install Ollama from [ollama.com](https://ollama.com), then open a new terminal and download a model:

```bat
ollama pull llama3.2:3b
```

Leave Ollama running in the background. VoiceOS automatically checks `http://localhost:11434` and uses `llama3.2:3b` by default. To choose another local model, set these variables before launching:

```bat
set VOICEOS_OLLAMA_URL=http://localhost:11434
set VOICEOS_OLLAMA_MODEL=llama3.2:3b
VoiceOS.cmd
```

You can confirm that Ollama is available with:

```bat
ollama list
```

No API key is needed for the Ollama tier. If Ollama is unavailable, the assistant can still perform its local action handlers; cloud-backed answers require the API configuration described above.

## Run VoiceOS

From the repository folder, double-click `VoiceOS.cmd`, or run:

```bat
VoiceOS.cmd
```

You can also launch the UI directly:

```bat
Backend\original\.venv\Scripts\python.exe Backend\original\ui_engine_final.py
```

The assistant appears as a compact bar at the top of the screen. Activate the microphone to listen, then use the confirmation card for consequential actions.

## Test the microphone

Run the diagnostics before first use:

```bat
Backend\original\.venv\Scripts\python.exe Backend\original\voice_diagnostics.py
```

To test recording and transcription as well:

```bat
Backend\original\.venv\Scripts\python.exe Backend\original\voice_diagnostics.py --transcribe
```

If no microphone is detected, check Windows microphone permissions under **Settings → Privacy & security → Microphone**, then rerun the diagnostic.

## Project layout

- `Backend/original/ui_engine_final.py` — application entry point
- `Backend/original/floating_ui.py` — liquid-glass floating interface
- `Backend/original/voice_io.py` — sounddevice capture, SpeechRecognition audio conversion, and TTS
- `Backend/original/voice_diagnostics.py` — microphone and transcription checks
- `Backend/original/app_discovery.py` — Windows app discovery and launcher
- `Backend/original/app_actions.py` — execute actions within opened applications
- `Backend/original/task_actions.py` — intent parsing and action execution
- `Backend/original/assistant.py` — main AI routing and command handling
- `VoiceOS.cmd` — one-click Windows launcher

## Opening Desktop Applications

VoiceOS automatically discovers installed applications on your Windows computer. You can open any app by name:

```
"open notepad"
"launch calculator"
"start chrome"
"open microsoft edge"
```

### Compound App Actions

Go beyond just opening apps—execute actions *within* the app using a single voice command:

```
"open notepad and write hello world"     -> Opens Notepad, writes text, auto-saves
"open calculator and add 5 and 3"        -> Opens Calculator, saves calculation
"open word and create a document"        -> Opens Word with creation prompt
"open notepad and type my reminder"      -> Opens Notepad and types text
```

VoiceOS automatically saves created content to `Documents\VoiceOS\` with timestamps:
```
note_20260925_134131.txt
calculator_calc_20260925_134134.txt
```

### App Discovery

The app launcher scans:
- Windows Registry for installed software
- Program Files and Program Files (x86)
- Desktop and Start Menu shortcuts
- Built-in Windows system applications (Notepad, Calculator, Paint, etc.)

Apps are cached on first run for fast access. App names are normalized and support fuzzy matching, so you can say variations like "calc" for Calculator or "notepad" for Notepad.

### Fallback to Browser

If an app isn't installed locally, VoiceOS automatically opens a web search:

```
"open blender"  -> App not found → Opens web search to download it
```

### Custom App Aliases

To customize app names or add shortcuts, create a `voiceos_aliases.json` file in `Backend/original/`:

```json
{
  "apps": {
    "myapp": "C:\\Path\\To\\MyApp.exe",
    "word": "C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE"
  },
  "sites": {
    "mysite": "https://example.com"
  }
}
```

Custom aliases take precedence over auto-discovered apps, so you can override names or add specific paths.

### Saved Files Location

All files created via voice commands are saved to:
```
Documents\VoiceOS\
```

### Email & Cloud Storage

Files can be automatically emailed or uploaded to cloud storage:

**Email Files:**
```python
from app_actions import AppActions

AppActions.email_file(
    filepath="Documents/VoiceOS/note_20260925_143000.txt",
    recipient_email="friend@example.com",
    subject="My VoiceOS Note"
)
```

**Upload to OneDrive (Built-in Windows):**
```python
AppActions.upload_to_onedrive(
    filepath="Documents/VoiceOS/note_20260925_143000.txt",
    folder_name="VoiceOS"  # Creates VoiceOS folder in OneDrive if it doesn't exist
)
```

**Upload to Google Drive:**
```python
AppActions.upload_to_google_drive(
    filepath="Documents/VoiceOS/note_20260925_143000.txt",
    folder_id="your-google-drive-folder-id"  # Optional
)
```

**Configuration:**

Add to `voiceos_aliases.json`:
```json
{
  "email": {
    "enabled": true,
    "sender_email": "your-email@gmail.com",
    "app_password": "your-app-password"
  },
  "cloud_storage": {
    "onedrive_enabled": true,
    "onedrive_folder": "VoiceOS",
    "google_drive_enabled": false,
    "google_drive_folder_id": null
  }
}
```

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

## Advanced Features

### 📊 Command History & Analytics

Track all voice commands, success rates, and usage patterns:

```python
from voice_history import VoiceHistory

history = VoiceHistory()

# Log command execution
history.log_command(
    "open notepad and write reminder",
    action="app_action",
    success=True,
    execution_time_ms=1250,
    app_opened="Notepad"
)

# Get today's statistics
stats = history.get_today_stats()
# Output: {
#   "total_commands": 5,
#   "successful_commands": 5,
#   "failed_commands": 0,
#   "success_rate": 100.0,
#   "avg_execution_time_ms": 1250
# }

# Get most used apps
apps = history.get_most_used_apps(days=7)
# Output: [("Notepad", 15), ("Chrome", 12), ("Word", 8)]

# View dashboard
print(history.get_dashboard_summary())
```

### 🔄 Workflow Automation

Chain multiple commands into powerful automated workflows:

```python
from workflow_automation import Workflow, WorkflowLibrary

# Create workflow
workflow = Workflow("daily_report")
workflow.add_step("open word")
workflow.add_step("open word and write daily summary")
workflow.add_step("save to onedrive")
workflow.add_step("email to boss@company.com")

# Execute workflow
def executor(command):
    # Your command executor function
    return True, "Success"

workflow.execute(executor)

# Or run in background
thread = workflow.execute_async(executor)

# Save and load workflows
workflow.save()
loaded = Workflow.load("~/.workflows/daily_report.json")

# Library management
library = WorkflowLibrary()
workflows = library.list_workflows()
```

### 🎯 Smart App Plugins

Specialized handlers for Microsoft Office and Outlook:

```python
from app_plugins import WordPlugin, ExcelPlugin, OutlookPlugin, PowerPointPlugin

# Word automation
word = WordPlugin()
word.open()
word.create_document("My Report")
word.insert_text("This is my report content")
word.insert_table(rows=5, cols=3)
word.save_as("C:\\temp\\report.docx")
word.close()

# Excel automation
excel = ExcelPlugin()
excel.open()
excel.create_workbook()
excel.set_cell(1, 1, "Name")
excel.set_cell(1, 2, "Value")
excel.create_chart()
excel.save_as("C:\\temp\\data.xlsx")
excel.close()

# Outlook automation
outlook = OutlookPlugin()
outlook.open()
outlook.send_email(
    to="recipient@company.com",
    subject="Meeting Notes",
    body="Please review the attached notes"
)
outlook.create_appointment("Team Meeting", "2026-09-30 10:00:00", 60)
outlook.close()

# PowerPoint automation
ppt = PowerPointPlugin()
ppt.open()
ppt.create_presentation()
ppt.add_slide("Introduction", "My Presentation")
ppt.add_slide("Content", "Here is the main content")
ppt.save_as("C:\\temp\\presentation.pptx")
ppt.close()
```

### 🔍 Desktop Search & File Organization

Search and organize all VoiceOS files:

```python
from desktop_search import DesktopSearch, FileOrganizer

# Search files
search = DesktopSearch()
results = search.find_files("report", file_type="docx", days=7)
# Search by app
notepad_files = search.find_by_app("notepad")
# Get recent files
recent = search.find_recent(limit=10)
# Export search index
search.export_index()

# Auto-organize files
organizer = FileOrganizer(organize_by="date_app")
# Creates structure: YYYY/MM/app_name/files
summary = organizer.auto_organize(dry_run=False)
# {
#   "total_files": 45,
#   "organized": 42,
#   "errors": 0,
#   "moves": [...]
# }

# Tag files
organizer.create_tags(file_path, ["important", "report", "2026-Q3"])
tags = organizer.get_tags(file_path)

# Archive old files
old_files = organizer.get_cleanup_suggestions(days_old=90)
organizer.archive_files("C:\\Archive", old_files, cleanup=True)
```

### 📅 Command Scheduling

Schedule voice commands to run at specific times:

```python
from command_scheduler import CommandScheduler

scheduler = CommandScheduler()

# Schedule daily at 9:30 AM
scheduler.schedule_daily("09:30:00", "open outlook")

# Schedule weekly
scheduler.schedule_weekly("MON 14:00:00", "open word and create weekly report")

# Schedule once
scheduler.schedule_once("2026-09-30 15:00:00", "open notepad")

# Schedule in N seconds
scheduler.schedule_in(300, "open calculator")

# Start scheduler (runs in background)
def executor(command):
    # Your command executor
    return True

scheduler.start(executor)

# View upcoming
print(scheduler.get_summary())

# Cancel command
scheduler.cancel_command(cmd_id)

# Stop scheduler
scheduler.stop()
```

### 🔊 Voice Feedback (Text-to-Speech)

Real-time audio confirmations:

```python
from voice_feedback import VoiceFeedback, CommandFeedback, VoiceSettings

# Basic voice feedback
voice = VoiceFeedback(voice_rate=0, voice_volume=100)
voice.confirm("Opening Notepad")
voice.success("File saved successfully")
voice.error("Failed to open application")
voice.info("Processing your command")

# Command-specific feedback
feedback = CommandFeedback(voice)
feedback.on_command_start("open word")
feedback.on_app_opened("Notepad")
feedback.on_file_saved("report.docx")
feedback.on_email_sent("boss@company.com")
feedback.on_upload_complete("OneDrive", "Documents/VoiceOS")

# Configure voice settings
settings = VoiceSettings()
settings.set("voice_rate", 2)  # Faster
settings.set("voice_volume", 80)
settings.set("confirmations.app_open", True)
settings.set("confirmations.file_save", True)
settings.save()

# Toggle on/off
voice.toggle(False)  # Disable TTS
```

### Example Advanced Commands

```
# Workflows
"run daily report workflow"
"execute backup workflow"

# Scheduling
"schedule open outlook daily at 9 AM"
"remind me to review this file tomorrow at 2 PM"
"schedule open word weekly on monday at 10 AM"

# Search
"find all documents from last week"
"search for reports in my VoiceOS files"
"show me notepad files from today"

# Organization
"organize my voiceos files"
"archive files older than 3 months"
"tag this file as important"

# Analytics
"show my command dashboard"
"what's my success rate this week"
"what apps did I use most today"

# Feedback
"speak this out loud: Meeting at 3 PM"
"confirm when you open the app"
"disable voice feedback"
```

### Example Commands

```
"open notepad"                         # Opens built-in Notepad
"launch chrome"                        # Opens Google Chrome
"start task manager"                   # Opens Task Manager
"run file explorer"                    # Opens File Explorer
"open notepad and write my ideas"      # Writes and saves text
"open calculator and add 5 and 3"      # Saves calculation
"open word and create a report"        # Opens with creation prompt
"open blender"                         # Not found → Opens download page
```

