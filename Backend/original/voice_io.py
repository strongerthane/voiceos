"""VoiceOS voice input (sounddevice) and Windows System.Speech output.

Microphone capture uses ``sounddevice`` to record 16-bit mono PCM, and
``to_audio_data`` wraps it in SpeechRecognition's native
``AudioData`` object, preserving the existing transcription path.
"""

from __future__ import annotations

import queue
import subprocess
import time
from typing import Callable, Dict, List, Optional


SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16 PCM
BLOCKSIZE = 1_024


def list_input_devices() -> List[Dict[str, object]]:
    """Return usable input devices via sounddevice."""
    import sounddevice as sd

    return [
        {"index": index, "name": device["name"],
         "channels": int(device["max_input_channels"]),
         "default_samplerate": float(device["default_samplerate"])}
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]


def to_audio_data(pcm: bytes, sample_rate: int) -> "object":
    """Convert signed 16-bit PCM into SpeechRecognition ``AudioData``."""
    import speech_recognition as sr
    return sr.AudioData(pcm, sample_rate, SAMPLE_WIDTH)


def record_audio_data(
    duration: float = 5.0,
    *,
    device: Optional[object] = None,
    sample_rate: int = SAMPLE_RATE,
    on_level: Optional[Callable[[float], None]] = None,
) -> "object":
    """Record a fixed duration and return it as SpeechRecognition AudioData."""
    import numpy as np
    import sounddevice as sd

    frame_count = max(1, int(duration * sample_rate))

    def callback(indata, frames, timing, status):
        if status:
            print(f"microphone status: {status}")
        level = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
        if on_level:
            on_level(min(1.0, level / 4_000.0))

    recording = sd.rec(frame_count, samplerate=sample_rate, channels=CHANNELS,
                       dtype="int16", device=device, callback=callback)
    sd.wait()
    if on_level:
        on_level(0.0)
    return to_audio_data(recording.tobytes(), sample_rate)


def _record_utterance(
    timeout: float,
    phrase_time_limit: float,
    *,
    device: Optional[object] = None,
    sample_rate: int = SAMPLE_RATE,
    on_level: Optional[Callable[[float], None]] = None,
) -> "object":
    """Record from first speech until a short silence, as ``AudioData``.

    The callback feeds a queue so nothing touches Tk from the audio thread. A
    brief ambient calibration creates a per-device speech threshold.
    """
    import numpy as np
    import sounddevice as sd

    chunks: "queue.Queue[tuple[bytes, float]]" = queue.Queue()

    def callback(indata, frames, timing, status):
        if status:
            print(f"microphone status: {status}")
        chunk = indata.copy()
        rms = float(np.sqrt(np.mean(np.square(chunk.astype(np.float32)))))
        chunks.put((chunk.tobytes(), rms))
        if on_level:
            on_level(min(1.0, rms / 4_000.0))

    ambient: List[float] = []
    collected: List[bytes] = []
    started = False
    last_voice = 0.0
    listen_started = time.monotonic()
    phrase_started = 0.0

    with sd.InputStream(samplerate=sample_rate, channels=CHANNELS,
                        dtype="int16", blocksize=BLOCKSIZE, device=device,
                        callback=callback):
        calibration_until = listen_started + 0.40
        while time.monotonic() < calibration_until:
            try:
                _, rms = chunks.get(timeout=0.10)
                ambient.append(rms)
            except queue.Empty:
                pass

        noise_floor = float(np.median(ambient)) if ambient else 0.0
        threshold = max(180.0, noise_floor * 3.0)
        while True:
            now = time.monotonic()
            if not started and now - listen_started >= timeout:
                raise TimeoutError("no speech detected before timeout")
            if started and now - phrase_started >= phrase_time_limit:
                break
            try:
                pcm, rms = chunks.get(timeout=0.12)
            except queue.Empty:
                continue
            if not started:
                if rms >= threshold:
                    started = True
                    phrase_started = now
                    last_voice = now
                    collected.append(pcm)
            else:
                collected.append(pcm)
                if rms >= threshold:
                    last_voice = now
                elif now - last_voice >= 0.80:
                    break

    if on_level:
        on_level(0.0)
    if not collected:
        raise TimeoutError("no speech captured")
    return to_audio_data(b"".join(collected), sample_rate)


def transcribe_audio(audio: "object", recognizer: Optional["object"] = None) -> str:
    """Run an AudioData object through the existing SpeechRecognition pipeline."""
    import speech_recognition as sr
    recognizer = recognizer or sr.Recognizer()
    return recognizer.recognize_google(audio)


def listen(
    timeout: float = 6.0,
    phrase_time_limit: float = 10.0,
    *,
    device: Optional[object] = None,
    on_level: Optional[Callable[[float], None]] = None,
) -> Optional[str]:
    """Capture one utterance with sounddevice and return its transcription."""
    try:
        import sounddevice  # noqa: F401 - gives a clear missing-package error
        import speech_recognition  # noqa: F401
    except ImportError as exc:
        print(f"Speech-to-text unavailable: {exc}")
        return None

    try:
        print("Listening…")
        audio = _record_utterance(timeout, phrase_time_limit, device=device,
                                  on_level=on_level)
    except Exception as exc:
        if on_level:
            on_level(0.0)
        print(f"No speech captured ({exc})")
        return None

    try:
        text = transcribe_audio(audio)
        print(f"Heard: {text}")
        return text
    except Exception as exc:
        print(f"Could not transcribe ({exc})")
        return None


def say(text: str, rate: int = 1) -> bool:
    """Speak through Windows System.Speech (SAPI). Returns True on success."""
    if not text:
        return False
    safe = str(text).replace("'", "").replace('"', "")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Add-Type -AssemblyName System.Speech; "
             "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
             f"$s.Rate = {rate}; $s.Speak('{safe}')"],
            check=False, timeout=max(15, len(safe) // 8), capture_output=True,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Text-to-speech failed ({exc})")
        return False


if __name__ == "__main__":
    print("VoiceOS sounddevice diagnostics")
    for microphone in list_input_devices():
        print(f"  [{microphone['index']}] {microphone['name']}")
