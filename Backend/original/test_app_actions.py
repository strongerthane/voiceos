"""Regression tests for compound app text input."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app_actions import AppActions
from task_actions import IntentParser


class AppActionsTests(unittest.TestCase):
    def test_type_action_preserves_dictated_case_and_punctuation(self):
        actions = AppActions(save_dir=".")
        intent = actions.parse_compound_action(
            "",
            "Open Notepad and type Hello, World!"
        )

        self.assertEqual(
            intent,
            {
                "app": "Notepad",
                "action_type": "write",
                "content": "Hello, World!",
            },
        )

    def test_intent_parser_preserves_dictated_content(self):
        parser = IntentParser(
            sites={"example": "https://example.com"},
            apps={"notepad": "notepad"},
            contacts={},
        )

        intent = parser.parse("Open Notepad and type Hello, World!")

        self.assertEqual(intent["content"], "Hello, World!")

    @patch.object(AppActions, "_paste_into_app", return_value=True)
    @patch.object(AppActions, "_copy_to_clipboard", return_value=True)
    @patch.object(AppActions, "_launch_app", return_value=True)
    @patch("app_actions.time.sleep")
    def test_notepad_text_is_saved_without_sending_enter(
        self, _sleep, launch, copy, paste
    ):
        actions = AppActions(save_dir=".")
        with patch.object(
            actions,
            "save_text_locally",
            return_value=(True, r"C:\VoiceOS\note.txt"),
        ) as save:
            success, detail = actions.execute_write_action(
                "notepad", "Hello, World!", "notepad.exe"
            )

        self.assertTrue(success, detail)
        launch.assert_called_once_with("notepad.exe")
        copy.assert_called_once_with("Hello, World!")
        paste.assert_called_once_with("notepad")
        save.assert_called_once_with("Hello, World!", "note", "txt")
        self.assertNotIn("ENTER", detail.upper())

    @patch("app_actions.subprocess.run", return_value=SimpleNamespace(returncode=0))
    @patch("app_actions.os.name", "nt")
    def test_paste_activates_target_and_sends_only_paste_shortcut(self, run):
        self.assertTrue(AppActions._paste_into_app("Notepad"))
        arguments = run.call_args.args[0]
        script = arguments[-1]

        self.assertIn("AppActivate($target)", script)
        self.assertIn("SendKeys('^v')", script)
        self.assertNotIn("ENTER", script.upper())
        self.assertFalse(run.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
