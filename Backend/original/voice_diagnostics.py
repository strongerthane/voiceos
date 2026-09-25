"""Repeatable sounddevice microphone checks for VoiceOS.

Run from Backend/original:
    python voice_diagnostics.py
    python voice_diagnostics.py --transcribe
"""

from __future__ import annotations

import argparse

from voice_io import list_input_devices, record_audio_data, transcribe_audio


class _PipelineProbe:
    """Offline recognizer replacement proving AudioData reaches the pipeline."""

    def recognize_google(self, audio):
        assert audio.sample_rate > 0
        assert audio.sample_width == 2
        assert audio.frame_data
        return "pipeline-ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceOS microphone diagnostics")
    parser.add_argument("--transcribe", action="store_true",
                        help="also make a live Google SpeechRecognition request")
    args = parser.parse_args()

    devices = list_input_devices()
    print("Available input devices:")
    for device in devices:
        print(f"  [{device['index']}] {device['name']} ({device['channels']} channel(s))")
    if not devices:
        print("FAIL: no input devices reported by sounddevice")
        return 1

    print("Recording two seconds from the default input…")
    audio = record_audio_data(2.0)
    print(f"PASS: captured {len(audio.frame_data)} bytes at {audio.sample_rate} Hz")

    result = transcribe_audio(audio, recognizer=_PipelineProbe())
    print(f"PASS: SpeechRecognition AudioData dispatch -> {result}")

    if args.transcribe:
        print("Requesting live transcription…")
        print(transcribe_audio(audio))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
