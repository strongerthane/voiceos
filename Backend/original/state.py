#!/usr/bin/env python3
"""
VoiceOS State Management Module

Tracks compact/expanded mode state, active step, and task status counts so
the UI can reflect backend state changes in real time.

This module intentionally has no external dependencies so any part of the
backend (core, verification, UI bridge) can import it safely.
"""

from datetime import datetime
from typing import Dict, Any, Optional


class CompactState:
    """Lightweight state container shared between the backend and the UI layer."""

    def __init__(self, mode: str = 'compact'):
        self.mode = mode                      # 'compact' or 'expanded'
        self.active_step: Optional[str] = None  # id of the currently active task/step
        self.status_counts: Dict[str, int] = {
            'pending': 0,
            'pass': 0,
            'fail': 0,
            'error': 0,
        }
        self.last_update = datetime.now()
        self.history: list = []               # short log of recent state transitions

    # ------------------------------------------------------------------ mode
    def set_mode(self, mode: str) -> None:
        """Set the current UI mode ('compact' or 'expanded')."""
        if mode not in ('compact', 'expanded'):
            raise ValueError(f"Invalid mode: {mode!r} (expected 'compact' or 'expanded')")
        self._record('mode', f"{self.mode} -> {mode}")
        self.mode = mode

    # ------------------------------------------------------------------ steps
    def set_active_step(self, step_id: Optional[str]) -> None:
        """Mark a task/step id as currently executing (or None when idle)."""
        self._record('active_step', f"{self.active_step} -> {step_id}")
        self.active_step = step_id

    # ----------------------------------------------------------------- counts
    def record_status(self, status: str) -> None:
        """Increment the counter for a task execution status."""
        status = status.lower()
        if status in ('pass', 'success', 'ok'):
            key = 'pass'
        elif status in ('fail', 'failed'):
            key = 'fail'
        elif status in ('error',):
            key = 'error'
        else:
            key = 'pending'
        self.status_counts[key] = self.status_counts.get(key, 0) + 1
        self._record('status', status)

    # ------------------------------------------------------------------ misc
    def to_dict(self) -> Dict[str, Any]:
        """Serializable snapshot of the current state."""
        return {
            'mode': self.mode,
            'active_step': self.active_step,
            'status_counts': dict(self.status_counts),
            'last_update': self.last_update.isoformat(),
        }

    def _record(self, category: str, detail: str) -> None:
        self.last_update = datetime.now()
        self.history.append({
            'timestamp': self.last_update.isoformat(),
            'category': category,
            'detail': detail,
        })
        # Keep the history bounded
        if len(self.history) > 100:
            self.history = self.history[-100:]


if __name__ == "__main__":
    # Quick self-test of the state module
    state = CompactState()
    state.set_mode('expanded')
    state.set_active_step('task_001')
    state.record_status('PASS')
    state.record_status('FAIL')
    state.record_status('ERROR')
    print("CompactState self-test:")
    print(f"  mode: {state.mode}")
    print(f"  active_step: {state.active_step}")
    print(f"  counts: {state.status_counts}")
    assert state.mode == 'expanded'
    assert state.status_counts['pass'] == 1
    assert state.status_counts['fail'] == 1
    assert state.status_counts['error'] == 1
    print("✓ state module OK")
