# VoiceOS v0.1.0-beta.1 · Windows x64

An early Windows beta of this community VoiceOS project, with a slim transparent
black notch, a reactive voice waveform, and supported desktop and web commands.

## Download and run

Download `VoiceOS-0.1.0-beta.1-windows-x64.zip`, extract the whole folder, then
open `VoiceOS.exe`. Python installation and API keys are not required for basic
commands. Follow the short microphone setup. Keep `_internal` beside the EXE.

Click the top-center notch and try “open YouTube” or “open Notepad”. Use Ctrl+T
to type, Ctrl+, for Settings, and Esc to quit after focusing the notch.

## Included

- Transparent top-edge notch with a smooth audio-reactive waveform.
- sounddevice microphone input, online speech recognition, and Windows TTS.
- App launching, web navigation/search, and email drafts with a review step.
- Optional Ollama answers or your own OpenAI-compatible cloud API configuration.
- First-run microphone selection/test, encrypted local key storage, and diagnostics.

## Before trying the beta

Windows 10/11 x64 only. The executable is unsigned and may trigger Windows
reputation warnings. Check the published SHA-256; no Windows protections are
disabled. It has been tested on the developer's machine, not a clean second PC.

Voice recognition sends speech to Google's online service. Ollama can keep AI
answers local, but does not make speech recognition offline. Cloud AI uses your
own provider account. No developer keys or contacts are included.

Some actions depend on installed software and default app associations. This
supports specific commands; it is not a general autonomous computer operator.
The advanced helper modules are experimental. Review drafts before sending.

Please report reproducible problems at the repository's Issues page. Include
Windows version and steps, but never include keys or private configuration files.

Independent community project; not affiliated with voiceos.com.
