"""Persistent user files live outside the packaged application."""
import os
from pathlib import Path
import sys


def user_dir() -> Path:
    override = os.environ.get('VOICEOS_CONFIG_DIR')
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'VoiceOS'


def config_file(name: str) -> Path:
    # Preserve existing source checkouts; frozen apps never load bundled secrets.
    legacy = Path(__file__).resolve().parent / name
    if not getattr(sys, 'frozen', False) and legacy.is_file() and not os.environ.get('VOICEOS_CONFIG_DIR'):
        return legacy
    return user_dir() / name


def actions_dir() -> Path:
    if getattr(sys, 'frozen', False) or os.environ.get('VOICEOS_CONFIG_DIR'):
        return user_dir() / 'Actions'
    return Path(__file__).resolve().parents[2] / 'VoiceOS_Actions'
