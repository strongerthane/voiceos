"""Standalone Windows beta entry point; no Python installation required."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback

from user_paths import user_dir

VERSION = '0.1.0-beta.1'


def diagnostics(record=False, smoke=False):
    """Exercise bundled libraries without external actions or cloud requests."""
    checks = {}
    errors = []
    def check(name, function):
        try:
            checks[name] = function()
        except Exception as exc:
            checks[name] = False
            errors.append({'check': name, 'error_type': type(exc).__name__})
    import numpy as np
    from aperture_renderer import ApertureRenderer
    from voice_io import list_input_devices, to_audio_data, transcribe_audio, record_audio_data
    from task_actions import IntentParser, TaskExecutor
    from unittest.mock import patch
    from ai_router import load_ai_config
    check('configuration', lambda: isinstance(load_ai_config(), dict))
    def audio_check():
        audio = to_audio_data(np.zeros(1600, dtype=np.int16).tobytes(), 16000)
        class OfflineRecognizer:
            def recognize_google(self, value):
                assert value.sample_rate == 16000 and value.sample_width == 2 and len(value.frame_data) == 3200
                return 'pipeline-ok'
        return transcribe_audio(audio, recognizer=OfflineRecognizer()) == 'pipeline-ok'
    check('speech_audio_pipeline', audio_check)
    check('microphone_count', lambda: len(list_input_devices()))
    def render_check():
        image = ApertureRenderer().render(236, 30)
        return image.mode == 'RGBA' and image.getpixel((0, 29))[3] == 0
    check('renderer', render_check)
    def action_check():
        with patch('app_discovery.merge_discovered_apps', side_effect=lambda apps: apps):
            parser = IntentParser()
        intent = parser.parse('open youtube')
        return bool(intent and TaskExecutor(dry_run=True).execute(intent).get('ok'))
    check('action_pipeline_dry_run', action_check)
    if record:
        check('recorded_pcm_bytes', lambda: len(record_audio_data(2, device=load_ai_config().get('input_device')).frame_data))
    if smoke:
        def ui_check():
            from assistant import VoiceAssistant
            from floating_ui import VoiceOSUI
            ui = VoiceOSUI({'window_title': 'VoiceOS beta launch check'})
            ui.attach_assistant(VoiceAssistant(tts=False))
            native = bool(ui._native)
            ui.root.after(1200, ui.root.destroy)
            ui.root.mainloop()
            return native
        check('native_window_launch', ui_check)
    passed = not errors and all(value is not False for value in checks.values())
    return {'version': VERSION, 'frozen': bool(getattr(sys, 'frozen', False)), 'passed': passed, 'checks': checks, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description='VoiceOS Windows beta')
    parser.add_argument('--settings', action='store_true')
    parser.add_argument('--diagnose', action='store_true')
    parser.add_argument('--record-test', action='store_true', help='Record two seconds locally; no upload or audio file')
    parser.add_argument('--smoke-test', action='store_true', help='Launch UI briefly and close automatically')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        if sys.stdout:
            print(VERSION)
        return 0
    if args.diagnose or args.smoke_test or args.record_test:
        result = diagnostics(args.record_test, args.smoke_test)
        report = args.report or user_dir() / 'diagnostics.json'
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        if sys.stdout:
            print(json.dumps(result, indent=2))
        return 0 if result['passed'] else 1
    from beta_setup import show_setup
    if args.settings or (getattr(sys, 'frozen', False) and not (user_dir() / 'setup-complete').exists()):
        if not show_setup():
            return 0
    from assistant import VoiceAssistant
    from floating_ui import VoiceOSUI
    while True:
        ui = VoiceOSUI({'window_title': 'VoiceOS beta'})
        ui.attach_assistant(VoiceAssistant())
        settings = [False]
        def open_settings(_=None):
            settings[0] = True
            ui.root.destroy()
        ui.root.bind('<Control-comma>', open_settings)
        ui.root.mainloop()
        if not settings[0] or not show_setup():
            return 0


if __name__ == '__main__':
    # Windowed builds have no stdout/stderr. Keep prints and tracebacks private
    # and out of the release archive; retain no command transcript on disk.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    try:
        raise SystemExit(main())
    except Exception:
        user_dir().mkdir(parents=True, exist_ok=True)
        # Only traceback locations and types, never exception values or keys.
        details = ''.join(traceback.format_list(traceback.extract_tb(sys.exc_info()[2])))
        (user_dir() / 'startup-error.txt').write_text(details + '\n' + sys.exc_info()[0].__name__, encoding='utf-8')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, 'VoiceOS could not start. Details are saved in %LOCALAPPDATA%\\VoiceOS\\startup-error.txt.', 'VoiceOS', 16)
        raise SystemExit(1)
