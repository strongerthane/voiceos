# VoiceOS UI Implementation Framework
# This module implements rigid rectangular element designs supporting compact/expanded mode transitions
# Directly connects with state management and verification systems

"""
UI Design Specification:
- Dark mode interface with blue desktop background (hex #0078D7)
- Compact mode: 40px bar across top showing voice activity with animated ripple effects
- Expanded mode: Full application window with layered elements and smooth transitions
- All animations must use easing functions for smooth transitions
- Every state change must have visual feedback indicators
- Voice flow elements must appear/disappear smoothly during voice interaction
"""

import time
from typing import Optional, Tuple


# UI_COMPONENT_LEVEL_1
class RectangularComponent:
    """Base class for all rectangular UI elements"""

    def __init__(self,
                 title: str,
                 position: Tuple[float, float],
                 dimensions: Tuple[int, int],
                 parent: Optional['RectangularComponent'] = None,
                 style: Optional[dict] = None):

        self.title = title
        self.position = position
        self.dimensions = dimensions
        self.parent = parent
        self.style = style or {}
        self.is_visible = True
        self.animation_state = "default"
        self.transition_duration = 0.3  # seconds
        self.last_updated = time.time()
        self.z_order = 1  # stacking order

    def appear(self, action: str = "fade_in", duration: Optional[float] = None):
        """Show the component with animation"""
        if duration is None:
            duration = self.transition_duration

        self.animation_state = f"animating_{action}"
        self.is_visible = True
        print(f"👁️ {self.title} appearing ({action}) with {duration}s duration")
        # Would trigger actual GUI animation here

    def disappear(self, action: str = "fade_out", duration: Optional[float] = None):
        """Hide the component with animation"""
        if duration is None:
            duration = self.transition_duration

        self.animation_state = f"animating_{action}"
        self.is_visible = False
        print(f"👀 {self.title} disappearing ({action}) with {duration}s duration")
        # Would trigger actual GUI animation here

    def update_style(self, **new_style):
        """Update component styling properties"""
        self.style.update(new_style)

    def set_position(self, new_position: Tuple[float, float]):
        """Change component position"""
        self.position = new_position
        print(f"📍 {self.title} moved to {new_position}")


class UIManager:
    """Main interface management system"""

    def __init__(self, config: dict):
        self.config = config
        self.compact_mode = config.get('compact_mode', True)
        self.expanded_mode = config.get('expanded_mode', False)
        self.available_colors = ['#0078D7', '#1A73E8', '#3367D6']  # blue variants
        self.current_color = config.get('current_color', self.available_colors[0])
        self.mode_transitions = {
            'compact': 'shrink_from_window',
            'expanded': 'grow_to_fullscreen'
        }
        self.animation_stack = []
        self.active_interface = None
        self.visual_feedback = None
        self.current_state = None
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all UI components in proper order"""
        self.create_base_UI_structure()
        self.register_voice_indicators()
        self.setup_animation_system()
        self.create_status_cards()
        self.create_compact_interface()  # ensures self.compact_bar exists from the start

    def create_base_UI_structure(self):
        """Build foundational UI elements"""
        self.base_elements = {
            "desktop_background": RectangularComponent(
                "Desktop Background",
                (0, 0),
                (1920, 1080),
                style={"color": self.current_color, "background": "#1a1a2e"}  # dark blue background
            ),
            "menu_tree": RectangularComponent(
                "Context Tree",
                (50, 250),
                (400, 600),
                style={"border": "1px solid #fff", "background": "rgba(255,255,255,0.1)"}
            ),
            "action_buttons": RectangularComponent(
                "Action Buttons",
                (600, 350),
                (450, 80),
                style={"buttons": 8}
            )
        }

    def create_compact_interface(self):
        """Build the minimal interface for compact mode"""
        print("🔧 Building compact mode UI elements...")

        # Create the distinctive top bar
        self.compact_bar = RectangularComponent(
            "Dynamic Island Bar",
            (0, 0),
            (1920, 40),
            style={
                "border": "1px solid #fff",
                "background": "rgba(0, 64, 80, 0.9)",
                "animation": "pulsing_voice_activity",
                "display": "adaptive"
            }
        )

        # Add compact-mode specific elements
        self.compact_elements = [
            "🎙️ Voice Activity: ",
            "🎯 Target Indicators",
            "📊 Status Indicators",
            "🔔 Element Correlation"
        ]

    def create_expanded_interface(self):
        """Build the full interface for expanded mode"""
        print("🔧 Building expanded mode UI elements...")

        # Create a comprehensive expanded UI layout
        self.expanded_UI = {
            "main_window": RectangularComponent(
                "Main Application Window",
                (50, 50),
                (1800, 800),
                style={
                    "background": "white",
                    "shadow": "4px 4px 12px rgba(0,0,0,0.3)",
                    "maximum_size": (1800, 800)
                }
            ),
            "side_panel": RectangularComponent(
                "Navigation Panel",
                (50, 130),
                (250, 750),
                style={
                    "background": "rgba(0, 100, 200, 0.7)",
                    "color": "white",
                    "dynamic_elements": True
                }
            ),
            "content_area": RectangularComponent(
                "Content Area",
                (300, 130),
                (1500, 680),
                style={"padding": "25px"}
            ),
            "overlay_panels": [  # For modal dialogs and status
                RectangularComponent(
                    "Confirmation Card",
                    (100, 800),
                    (1600, 200),
                    style={
                        "border_radius": "12px",
                        "opacity": "0.95",
                        "transition": "sliding_from_bottom"
                    }
                ),
                RectangularComponent(
                    "Progress Card",
                    (100, 830),
                    (1600, 150),
                    style={"border": "1px solid #ddd", "transition": "fade"}
                )
            ]
        }

    def register_voice_indicators(self):
        """Register voice-activity visual indicators."""
        self.voice_indicators = [
            "🎙️ Voice Activity Ripple",
            "🔊 Volume Meter",
            "📋 Transcript Overlay",
        ]
        print(f"📻 Registered {len(self.voice_indicators)} voice indicators")

    def setup_animation_system(self):
        """Initialize the named-animation registry."""
        self.animation_registry = {
            "voice_bubble": "expand",
            "voice_feedback": "ripple",
            "mode_expansion": "grow",
            "mode_compaction": "shrink",
            "hover_pulse": "pulse",
        }

    def create_status_cards(self):
        """Create persistent status indicators"""
        self.status_cards = {
            "success_card": RectangularComponent(
                "Success",
                (50, 950),
                (800, 60),
                style={"border": "2px solid #4CAF50", "background": "#e8f5e9"}
            ),
            "warning_card": RectangularComponent(
                "Warning",
                (1350, 950),
                (150, 60),
                style={"border": "2px solid #ff9800", "background": "#ffebee"}
            ),
            "error_card": RectangularComponent(
                "Error",
                (2100, 950),
                (170, 60),
                style={"border": "2px solid #f44336", "background": "#ffebee"}
            )
        }

    # ------------------------------------------------------------------ modes
    def set_mode(self, mode: str):
        """Set the interface mode ('compact' or 'expanded')."""
        if mode == 'expanded':
            self.enable_expanded_mode()
        elif mode == 'compact':
            self.enable_compact_mode()

    def enable_expanded_mode(self):
        """Switch to the expanded view mode"""
        self.compact_mode = False
        self.expanded_mode = True
        self.active_interface = "expanded_UI"

        if not hasattr(self, 'expanded_UI'):
            self.create_expanded_interface()

        self.trigger_animation("mode_expansion", 0.7)
        print("🔄 Switched to expanded mode with animated transition")

    def enable_compact_mode(self):
        """Switch to the compact view mode"""
        self.compact_mode = True
        self.expanded_mode = False
        self.active_interface = "compact_bar"

        if not hasattr(self, 'compact_bar'):
            self.create_compact_interface()

        self.trigger_animation("mode_compaction", 0.5)
        print("🔄 Switched to compact mode (Dynamic Island bar)")

    def activate_voice_mode(self, mode: str):
        """Activate voice interface mode"""
        print(f"🗣️ Activating voice mode: {mode}")
        self.active_interface = mode
        self.set_visual_feedback("voice_feedback")
        self.trigger_animation("voice_bubble", 0.5)

    def set_visual_feedback(self, feedback_type: str):
        """Set the visual feedback mode (e.g. 'voice_feedback')."""
        self.visual_feedback = feedback_type
        print(f"💡 Visual feedback: {feedback_type}")

    def trigger_animation(self, animation_type: str, duration: float = 1.0):
        """Queue a named animation through the animation stack."""
        effect = "fade"
        if hasattr(self, "animation_registry"):
            effect = self.animation_registry.get(animation_type, "fade")
        self.animation_stack.append(
            {"type": animation_type, "effect": effect, "duration": duration}
        )
        print(f"🎞️ Animation '{animation_type}' ({effect}) queued for {duration}s")

    # ------------------------------------------------------------------ state
    def update_ui_state(self, state: str):
        """Update UI according to current state"""
        self.current_state = state
        if "compact" in state:
            self.set_mode("compact")
            self._transition_to_compact()
        elif "expanded" in state:
            self.set_mode("expanded")
            self._transition_to_expanded()

    def _transition_to_compact(self):
        """Compact-mode transition implementation"""
        print(f"📏 Switching to compact mode with {self.mode_transitions['compact']} transition")
        for element in self.base_elements.values():
            if hasattr(element, 'disappear'):
                element.disappear()
        self.create_compact_interface()
        print("✓ Compact mode active")

    def _transition_to_expanded(self):
        """Expanded-mode transition implementation"""
        print("🚀 Initiating expanded mode transition...")
        self.create_expanded_interface()
        self.transition_duration = 0.7
        self.trigger_animation("mode_expansion", 1.0)
        print("✅ Expanded mode activated with full interaction capabilities")

    def trigger_voice_feedback(self):
        """Show visual feedback for voice activity"""
        self.last_voice_duration = 0  # Reset
        self.trigger_animation("voice_feedback", 0.2)
        print("💬 Voice feedback triggered: ripple animation active")

    def update_ui_specific(self, element_type: str, new_config: dict):
        """Specific update method for UI elements"""
        if element_type == "dynamic_island":
            self.compact_bar.style.update(new_config.get("modern_style", {}))
            self.trigger_animation("hover_pulse", 2.0)


# File I/O Operations Extension
def file_creation_pattern():
    """Documented file creation approach for VoiceOS structure"""
    return {
        "ui_main.py": "Root UI component driver",
        "ui_core/": "Core UI component definitions",
        "ui_core/rectangular_component.py": "Base UI element implementation",
        "ui_core/price_manager.py": "UI state management",
        "ui_core/animation_engine.py": "Animation system",
        "ui_core/voice_sync.py": "Voice-activated interaction patterns",
        "ui_core/status_indicators.py": "Status card systems for feedback",
        "ui_core/transition_manager.py": "Mode transition framework"
    }


# Test utility function
def test_ui_element():
    """Simple UI test function"""
    component = RectangularComponent(
        "Test Button",
        (100, 100),
        (200, 150)
    )

    print("Testing UI component: ", end="")
    component.appear("fade_in", 0.3)
    component.is_visible = True
    print("Component appears successfully")


def initialize_ui_system(config: dict) -> RectangularComponent:
    """Initialize full UI system with specified configuration"""
    manager = UIManager(config)
    manager.enable_expanded_mode()  # Start with expanded mode
    return manager.compact_bar


if __name__ == "__main__":
    # Test routine
    config = {
        'compact_mode': True,
        'expanded_mode': False,
        'current_color': '#0078D7',
        'is_maximized': False,
        'initial_mode': 'compact'
    }

    ui_manager = UIManager(config)
    print("VoiceOS UI Manager initialized successfully")
    assert ui_manager.compact_bar is not None
    print(f"Current mode: {'compact' if ui_manager.compact_mode else 'expanded'}")

    # Demonstrate UI transitions
    ui_manager.update_ui_state("expanded")
    assert ui_manager.expanded_mode is True
    print(f"Mode status after expansion: {ui_manager.expanded_mode}")

    ui_manager.update_ui_state("compact_requested")
    assert ui_manager.compact_mode is True
    print(f"Mode after compact request: {ui_manager.compact_mode}")

    # Test voice interaction
    ui_manager.activate_voice_mode("voice")
    ui_manager.trigger_voice_feedback()
    assert ui_manager.visual_feedback == "voice_feedback"
    print("Voice mode active successfully")

    # Element-specific updates flow through the animation system
    ui_manager.update_ui_specific("dynamic_island", {"modern_style": {"glow": "soft"}})
    assert ui_manager.compact_bar.style.get("glow") == "soft"

    # Component-level helper
    test_ui_element()

    # Full system bootstrap helper
    assert initialize_ui_system(config) is not None

    print("✓ ui_engine module self-test OK")
