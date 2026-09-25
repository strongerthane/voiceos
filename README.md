# VoiceOS

VoiceOS is a compact desktop voice assistant with a top-of-screen liquid-glass interface, reactive listening waveform, sounddevice microphone capture, NVIDIA GLM/OpenAI-compatible AI routing, and text-to-speech responses.

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
- `VoiceOS.cmd` — one-click Windows launcher
