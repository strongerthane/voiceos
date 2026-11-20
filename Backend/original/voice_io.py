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
CALIBRATION_SECONDS = 0.5      # short, so user doesn't speak during it
THRESHOLD_FLOOR = 3.0          # lower floor = more sensitive
THRESHOLD_MULTIPLIER = 1.05    # closer to noise floor = more sensitive
TARGET_PEAK = 28000            # peak-normalize to ~85% of int16 full scale


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


def find_working_device(min_rms: float = 2.0, test_duration: float = 0.5) -> Optional[object]:
    """Auto-detect an input device that is actually receiving audio.

    Opens each input device briefly and measures RMS. Returns the device
    with the highest average RMS if any device shows audio activity
    (avg_rms >= min_rms), otherwise returns None so the caller can use
    the default device and let calibration handle it.
    """
    import numpy as np
    import sounddevice as sd

    best_idx: Optional[int] = None
    best_rms = 0.0

    for info in list_input_devices():
        idx = info["index"]
        rms_values: List[float] = []

        def callback(indata, frames, timing, status):
            if status:
                return
            rms = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
            rms_values.append(rms)

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="int16", blocksize=BLOCKSIZE,
                                device=idx, callback=callback):
                time.sleep(test_duration)
        except Exception:
            continue

        if rms_values:
            avg_rms = float(np.mean(rms_values))
            print(f"[VoiceOS] device [{idx}] {info['name'][:40]} avg_rms={avg_rms:.1f}", flush=True)
            if avg_rms > best_rms:
                best_rms = avg_rms
                best_idx = idx

    if best_rms >= min_rms and best_idx is not None:
        print(f"[VoiceOS] using microphone device [{best_idx}] "
              f"(avg_rms={best_rms:.1f})", flush=True)
        return best_idx

    print(f"[VoiceOS] best device avg_rms={best_rms:.1f} < {min_rms}; using default", flush=True)
    return None


def to_audio_data(pcm: bytes, sample_rate: int, gain: float = 1.0) -> "object":
    """Convert signed 16-bit PCM into SpeechRecognition ``AudioData``.

    Applies an optional fixed gain multiplier, or peak-normalizes when
    ``gain`` is 0 (scales the loudest sample to ``TARGET_PEAK``).
    """
    import numpy as np
    import speech_recognition as sr

    arr = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    if gain == 0.0:
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        if peak > 0:
            gain = TARGET_PEAK / peak
    if gain != 1.0:
        arr = np.clip(arr * gain, -32768, 32767).astype("<i2")
        pcm = arr.tobytes()
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
            on_level(min(1.0, level / 2_000.0))

    recording = sd.rec(frame_count, samplerate=sample_rate, channels=CHANNELS,
                       dtype="int16", device=device, callback=callback)
    sd.wait()
    if on_level:
        on_level(0.0)
    return to_audio_data(recording.tobytes(), sample_rate, gain=0.0)


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
            on_level(min(1.0, rms / 2_000.0))

    ambient: List[float] = []
    collected: List[bytes] = []
    started = False
    last_voice = 0.0
    listen_started = time.monotonic()
    phrase_started = 0.0

    with sd.InputStream(samplerate=sample_rate, channels=CHANNELS,
                        dtype="int16", blocksize=BLOCKSIZE, device=device,
                        callback=callback):
        calibration_until = listen_started + CALIBRATION_SECONDS
        while time.monotonic() < calibration_until:
            try:
                _, rms = chunks.get(timeout=0.10)
                ambient.append(rms)
            except queue.Empty:
                pass

        noise_floor = float(np.median(ambient)) if ambient else 50.0
        threshold = max(THRESHOLD_FLOOR, noise_floor * THRESHOLD_MULTIPLIER)
        print(f"[VoiceOS] calibration: noise_floor={noise_floor:.1f} threshold={threshold:.1f} device={device}", flush=True)
        if noise_floor < 2.0:
            print("[VoiceOS] WARNING: noise floor is near zero — no microphone audio detected. "
                  "Check Windows microphone privacy settings and ensure the mic is not muted.", flush=True)
        print("Listening…", flush=True)
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
                    print(f"[VoiceOS] speech started rms={rms:.1f}", flush=True)
                    phrase_started = now
                    last_voice = now
                    collected.append(pcm)
            else:
                collected.append(pcm)
                if rms >= threshold:
                    last_voice = now
                elif now - last_voice >= 1.0:
                    print(f"[VoiceOS] speech ended rms={rms:.1f}", flush=True)
                    break

    if on_level:
        on_level(0.0)
    if not collected:
        raise TimeoutError("no speech captured")
    return to_audio_data(b"".join(collected), sample_rate, gain=0.0)


def transcribe_audio(audio: "object", recognizer: Optional["object"] = None) -> str:
    """Run an AudioData object through the existing SpeechRecognition pipeline."""
    import speech_recognition as sr
    recognizer = recognizer or sr.Recognizer()
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        raise ValueError(
            "Google Speech could not understand the audio. "
            "Try speaking more clearly or check your microphone level."
        )
    except sr.RequestError as exc:
        raise ValueError(f"Google Speech request failed: {exc}")


def listen(
    timeout: float = 5.0,
    phrase_time_limit: float = 8.0,
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

    # Auto-detect a working microphone when no device is specified.
    # (Calibration in _record_utterance handles threshold per-device.)

    try:
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
        print(f"Could not transcribe ({type(exc).__name__}: {exc})")
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
