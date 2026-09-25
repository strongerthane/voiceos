"""
VoiceOS Desktop Interface Implementation

This module handles the desktop interface with compact/expanded modes,
dark theme, blue desktop background, smooth animations, and voice coordination.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


class ModeState:
    """Track the current state of the interface modes."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_expanded: bool = bool(config.get('init_expanded', False))
        self.is_compact: bool = not self.is_expanded
        self.mode_transition: str = "none"  # "compact_to_expanded", "expanded_to_compact", "none"
        self.timer_start: bool = False
        self.transition_active: bool = False
        self.current_screen_content: List[str] = []

    @property
    def current_mode(self) -> str:
        """String name of the currently active mode."""
        return 'expanded' if self.is_expanded else 'compact'

    def switch_to_expanded(self) -> bool:
        """Start a compact -> expanded transition (True if it was started)."""
        if self.is_expanded or self.transition_active:
            return False

        self.mode_transition = "compact_to_expanded"
        self.timer_start = True
        self.transition_active = True
        os.environ['VOICEOS_ANIMATION_ACTIVE'] = 'true'  # Signal animation to start
        return True

    def switch_to_compact(self) -> bool:
        """Start an expanded -> compact transition (True if it was started)."""
        if self.is_compact or self.transition_active:
            return False

        self.mode_transition = "expanded_to_compact"
        self.timer_start = True
        self.transition_active = True
        os.environ['VOICEOS_ANIMATION_ACTIVE'] = 'true'  # Signal animation to start
        return True

    def set_mode(self, mode: str) -> bool:
        """Request a switch to 'compact' or 'expanded'."""
        if mode == 'expanded':
            return self.switch_to_expanded()
        if mode == 'compact':
            return self.switch_to_compact()
        return False

    def complete_mode_change(self):
        """Commit the pending transition and clear the animation signal."""
        if not self.transition_active:
            return
        self.is_expanded = (self.mode_transition == "compact_to_expanded")
        self.is_compact = not self.is_expanded
        self.transition_active = False
        self.mode_transition = "none"
        self.timer_start = False
        os.environ['VOICEOS_ANIMATION_ACTIVE'] = 'false'


class _VisibilityFlag:
    """Tiny mutable visibility flag standing in for the compact bar widget."""

    def __init__(self, visible: bool = True):
        self.visible = bool(visible)

    def set_visibility(self, visible: bool):
        self.visible = bool(visible)


class UIManager:
    """Main interface management for VoiceOS"""

    def __init__(self, config: Dict[str, Any]):
        self.state_manager = self._load_state_manager(config)
        self.mode_manager = ModeState(config)
        self.theme = config.get('theme', 'dark')
        self.compact_mode_bar = config.get('compact_bar', 'compact')
        self.background_color = config.get('background_color', '#0078D7')
        self.visual_state = config.get('visual_state', 'active')
        self.last_mode_change: float = 0.0
        self.voice_feedback_theme = None

        # Animation / transition bookkeeping (previously read uninitialized)
        self.timer_start: bool = False
        self.transition_active: bool = False
        self.bar = _VisibilityFlag(True)

        # Initialize core components
        self._initialize_components(config)

    def _load_state_manager(self, config: Dict[str, Any]):
        """Load the state-management component (provided by state.py)."""
        from state import CompactState
        return CompactState()

    def _initialize_components(self, config: Dict[str, Any]):
        """Initialize all UI components"""
        # Core UI components
        self.main_display = None
        self.verbosity_mode = config.get('verbosity', 2)  # Voice level
        self.animation_enabled = config.get('animate', True)
        self.sound_enabled = config.get('sound', True)
        self.sidebar_visibility = config.get('sidebar_visible', False)

        # UI layouts
        self.compact_UI = self._build_compact_ui()
        self.expanded_UI = self._build_expanded_ui()

        # Animation system
        self.animation_system = self._init_animation_system()
        self.current_mode = self.mode_manager.current_mode

    def _build_compact_ui(self) -> Dict[str, Any]:
        """Create compact audio interface elements"""
        return {
            "mode": "compact",
            "visible_elements": ["microphone_bar", "status_indicator", "mode_indicator"],
            "elements": [
                "Top bar (Desktop height, 40px)",
                "Voice activity indicators",
                "Status cards (minimal)",
                "Timer overlay (if in use)",
                "Voice feedback notification area"
            ],
            "background": self.background_color,
            "theme": self.theme
        }

    def _build_expanded_ui(self) -> Dict[str, Any]:
        """Create expanded interface elements"""
        return {
            "mode": "expanded",
            "visible_elements": [
                "main_window",
                "side_panel",
                "top_bar",
                "sidebar",
                "status_cards",
                "tool_tabs",
                "animation_panels"
            ],
            "background": self.background_color,
            "theme": self.theme,
            "features": [
                "Full desktop interface",
                "moving elements as needed",
                "animation flows",
                "voice interactions"
            ]
        }

    def _init_animation_system(self):
        """Initialize animation and transition system"""
        def animate(event_type: str, duration: float = 0.3):
            if not self.animation_enabled:
                return

            if duration <= 0:
                print(f"LAG: {event_type} transition happening instantly")
                return

            print(f"{event_type} animation start - will take {duration}s")
            # In actual implementation, this would coordinate visual animations

        return animate

    # ------------------------------------------------------------------ modes
    def switch_to_expanded(self) -> bool:
        """Run the compact -> expanded transition and commit it."""
        if not self.mode_manager.switch_to_expanded():
            return False
        self._animate_event('mode_change', 'fade')
        self.mode_manager.complete_mode_change()
        self.current_mode = self.mode_manager.current_mode
        return True

    def switch_to_compact(self) -> bool:
        """Run the expanded -> compact transition and commit it."""
        if not self.mode_manager.switch_to_compact():
            return False
        self._animate_event('mode_change', 'fade')
        self.mode_manager.complete_mode_change()
        self.current_mode = self.mode_manager.current_mode
        return True

    def toggle_mode_state(self) -> str:
        """Toggle between compact and expanded modes; returns the new mode."""
        if self.mode_manager.is_compact:
            self.switch_to_expanded()
        else:
            self.switch_to_compact()
        return self.mode_manager.current_mode

    # ------------------------------------------------------------------ state
    def get_visual_state(self) -> str:
        """Check current visual state for display decisions"""
        return self.visual_state

    def update_voice_feedback_theme(self, theme: str):
        """Update theme based on voice feedback needs"""
        self.voice_feedback_theme = theme
        if self.animation_enabled and self.mode_manager.is_compact:
            self.transition_active = True  # Trigger visual transition

    def sync_with_verification_system(self, verification_result):
        """Sync visual feedback with verifier results (dict or dataclass)."""
        if isinstance(verification_result, dict):
            status = verification_result.get('status')
        else:
            status = getattr(verification_result, 'status', None)

        if status in ['PASS', 'completed']:
            self.update_visual_state("success")
        elif status in ['FAIL', 'failed']:
            self.update_visual_state("error")

    def update_visual_state(self, state: str):
        """Update visual state of UI components"""
        self.visual_state = state
        self.bar.set_visibility(state in ['active', 'error', 'success'])

    def get_current_ui_configuration(self) -> Dict[str, Any]:
        """Get current UI configuration for display systems"""
        return {
            'current_mode': self.mode_manager.current_mode,
            'display_mode': 'compact' if self.mode_manager.is_compact else 'expanded',
            'theme': self.theme,
            'animation_state': self.mode_manager.transition_active,
            'feedback_theme': self.voice_feedback_theme,
            'background_color': self.background_color,
            'last_updated': time.time()
        }

    def get_mode_summary(self) -> Dict[str, Any]:
        """Return current UI mode summary"""
        return {
            'current_mode': self.mode_manager.current_mode,
            'transition': self.mode_manager.mode_transition,
            'animation_active': self.mode_manager.transition_active,
            'show_feedback': self.current_mode == 'compact' and self.voice_feedback_theme is not None
        }

    # ------------------------------------------------------------- animation
    def activate_voice_interaction(self):
        """Activate UI for voice input - show relevant elements"""
        self._animate_event('voice_activation', 'highlight')
        self.visual_state = 'voice_interactive'

    def deactivate_voice_interaction(self):
        """Deactivate UI from voice input mode"""
        self._animate_event('voice_deactivation', 'highlight')
        self.voice_feedback_theme = 'default'

    def _animate_event(self, event: str, effect: str = 'fade'):
        """Internal animation dispatcher"""
        self.trigger_animation(event, 0.3 if effect == 'fade' else 0.05)

    def trigger_animation(self, animation_type: str, duration: float = 1.0):
        """Trigger a specific animation; failures are logged, never raised."""
        try:
            if self.animation_enabled:
                self.animation_system(animation_type, duration)
            self.last_mode_change = time.time()
        except Exception as e:
            print(f"Animation error: {animation_type} - {e}")


# Main UI Controller class
class UIController:
    """
    Main UI Controller that handles interface interactions,
    mode switching, visual display states, and verification feedback.
    """

    def __init__(self, config: Dict[str, Any]):
        self.ui_manager = UIManager(config)
        self.accounts_manager = None  # Will initialize with account system later
        self.audio_services = None

        self.setup_initial_state()

    def setup_initial_state(self):
        """Setup initial UI state based on configuration"""
        if self.ui_manager.mode_manager.is_expanded:
            print("Initialized in expanded mode")
        else:
            print("Initialized in compact mode")

        # Show initial UI state
        current_ui = self.ui_manager.get_visual_state()
        print(f"Current visual state: {current_ui}")

    def configure_voice_services(self, audio_services):
        """Configure voice service integration"""
        self.audio_services = audio_services
        print("Voice services configured successfully")

    def set_visual_style(self, theme: str = "dark", color: str = "#0078D7"):
        """Set consistent theme across all UI elements"""
        self.ui_manager.theme = theme
        self.ui_manager.background_color = color
        self.ui_manager.mode_manager.config['background_color'] = color
        print(f"Visual style updated to {theme} theme with color {color}")

    def toggle_mode(self) -> str:
        """Toggle between compact and expanded modes"""
        new_mode = self.ui_manager.toggle_mode_state()
        print(f"Mode switched to {new_mode}")
        return new_mode


# Configuration options for UI styling
UI_CONFIG_OFFICIAL = {
    'theme': 'dark',
    'background_color': '#0078D7',
    'compact_bar': 'true',
    'init_expanded': False,
    'animate': True,
    'sound': True,
    'sidebar_visible': True,
    'theme_base': 'visual-slate'
}


if __name__ == "__main__":
    print("ui_main module self-test")
    cfg = dict(UI_CONFIG_OFFICIAL)

    ui = UIManager(cfg)
    assert ui.current_mode == 'compact', ui.current_mode
    assert ui.mode_manager.is_compact and not ui.mode_manager.is_expanded
    assert ui.get_mode_summary()['current_mode'] == 'compact'
    print("✓ UIManager initialized in compact mode")

    # compact -> expanded -> compact round trip
    assert ui.switch_to_expanded() is True
    assert ui.mode_manager.is_expanded
    assert ui.mode_manager.current_mode == 'expanded'
    assert ui.switch_to_compact() is True
    assert ui.mode_manager.is_compact
    print("✓ Mode round trip committed")

    # redundant switch requests are refused, not fatal
    assert ui.switch_to_compact() is False

    # verification sync drives the visual state
    ui.sync_with_verification_system({'status': 'PASS'})
    assert ui.visual_state == 'success', ui.visual_state
    assert ui.bar.visible is True
    ui.sync_with_verification_system({'status': 'FAIL'})
    assert ui.visual_state == 'error'
    print("✓ Verification sync drives visual state")

    # animation paths never crash
    ui.trigger_animation("mode_change", 0.5)
    ui.activate_voice_interaction()
    assert ui.visual_state == 'voice_interactive'
    ui.deactivate_voice_interaction()
    assert ui.voice_feedback_theme == 'default'
    print("✓ Animation and voice interaction paths clean")

    # controller-level flows
    controller = UIController(cfg)
    assert controller.toggle_mode() == 'expanded'
    assert controller.ui_manager.mode_manager.is_expanded
    controller.set_visual_style("dark", "#0078D7")
    controller.configure_voice_services({"microphone": "default"})
    print("✓ UIController toggling and styling work")

    print("✓ ui_main module self-test OK")
