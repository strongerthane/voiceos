"""Regression checks for packaged paths, settings and provider selection."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


class BetaTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='VoiceOS-beta-test-')
        self.env = patch.dict(os.environ, {'VOICEOS_CONFIG_DIR': self.folder.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows DPAPI')
    def test_saved_key_is_encrypted_and_never_serialized_in_config(self):
        from beta_setup import save_settings
        from secure_store import load_api_key
        synthetic_key = 'synthetic-release-test-value'
        save_settings({'api_key': synthetic_key, 'tts': False}, key=synthetic_key)
        folder = Path(self.folder.name)
        self.assertNotIn(synthetic_key, (folder / 'ai_config.json').read_text())
        self.assertNotIn(synthetic_key.encode(), (folder / 'provider-key.bin').read_bytes())
        self.assertEqual(load_api_key(), synthetic_key)
        self.assertTrue((folder / 'setup-complete').exists())

    def test_frozen_contacts_and_outputs_are_persistent(self):
        from user_paths import config_file, actions_dir
        from task_actions import load_contacts
        folder = Path(self.folder.name)
        (folder / 'voiceos_contacts.json').write_text(json.dumps({'Example': 'person@example.com'}))
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(config_file('voiceos_contacts.json'), folder / 'voiceos_contacts.json')
            self.assertEqual(actions_dir(), folder / 'Actions')
            self.assertEqual(load_contacts(), {'example': 'person@example.com'})

    def test_selected_microphone_is_used(self):
        import voice_io
        with patch('ai_router.load_ai_config', return_value={'input_device': 4}), patch.object(voice_io, '_record_utterance', return_value=object()) as capture, patch.object(voice_io, 'transcribe_audio', return_value='test words'):
            self.assertEqual(voice_io.listen(), 'test words')
            self.assertEqual(capture.call_args.kwargs['device'], 4)

    def test_fixed_recording_uses_stream_and_trims_final_audio_block(self):
        import numpy as np
        import voice_io
        import sounddevice
        levels = []
        def stream(**kwargs):
            value = Mock()
            def enter():
                kwargs['callback'](np.full((1024, 1), 100, dtype=np.int16), 1024, None, None)
                kwargs['callback'](np.full((1024, 1), 200, dtype=np.int16), 1024, None, None)
                return value
            value.__enter__ = Mock(side_effect=enter)
            value.__exit__ = Mock(return_value=False)
            return value
        with patch.object(sounddevice, 'InputStream', side_effect=stream), patch.object(sounddevice, 'rec') as rec:
            audio = voice_io.record_audio_data(0.1, sample_rate=16000, on_level=levels.append)
        self.assertEqual(len(audio.frame_data), 1600 * 2)
        self.assertEqual(np.frombuffer(audio.frame_data, dtype=np.int16)[-1], 200)
        self.assertEqual(levels[-1], 0.0)
        rec.assert_not_called()

    def test_local_mode_never_calls_cloud_even_for_hard_questions(self):
        from ai_router import HybridRouter
        local, remote = Mock(), Mock()
        local.cfg = {'ai_mode': 'local'}
        local.is_available.return_value = True
        local.generate.return_value = 'Local answer'
        result = HybridRouter(local=local, remote=remote).ask('Explain the history of computers?')
        self.assertEqual(result['source'], 'local')
        remote.generate.assert_not_called()

    def test_commands_mode_never_probes_or_calls_ai(self):
        from ai_router import HybridRouter
        local, remote, parser = Mock(), Mock(), Mock()
        local.cfg = {'ai_mode': 'commands'}
        parser.answer.return_value = 'Try a command.'
        result = HybridRouter(local=local, remote=remote, offline_parser=parser).ask('Hello')
        self.assertEqual(result['source'], 'offline')
        local.is_available.assert_not_called()
        local.generate.assert_not_called()
        remote.generate.assert_not_called()

    def test_cloud_mode_routes_short_questions_to_selected_provider(self):
        from ai_router import HybridRouter
        local, remote = Mock(), Mock()
        local.cfg = {'ai_mode': 'cloud'}
        remote.is_configured = True
        remote.generate.return_value = 'Cloud answer'
        result = HybridRouter(local=local, remote=remote).ask('Hello')
        self.assertEqual(result['source'], 'api')
        local.is_available.assert_not_called()
        local.generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
