# VoiceOS

VoiceOS is a compact desktop voice assistant with a top-of-screen liquid-glass interface, reactive listening waveform, sounddevice microphone capture, NVIDIA GLM/OpenAI-compatible AI routing, and text-to-speech responses.

## Features

- **Desktop App Launcher**: Opens any installed application on your computer by voice (e.g., "open notepad", "launch chrome")
- **Web Search & Navigation**: Search the web and open websites
- **YouTube Deep-Linking**: Play specific videos directly (e.g., "play lofi beats on youtube")
- **Email Drafting**: Compose emails through your default mail client (human presses Send)
- **Claude Code Integration**: Delegate code/file creation to Claude CLI
- **Offline Actions**: Open apps, websites, and search without AI backends
- **Hybrid AI Tiers**: Easy questions → Ollama (local), hard questions → OpenAI-compatible API

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
