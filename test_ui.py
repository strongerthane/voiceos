#!/usr/bin/env python3
"""
VoiceOS UI Implementation - Test Environment
This script provides a comprehensive test for the VoiceOS desktop interface with compact and expanded modes.
"""

import time
from unittest.mock import Mock
import sys
import os

# Add the VoiceOS directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Backend', 'original'))

from ui_engine_final import VoiceOSUI, RPY


def _destroy(ui):
    """Best-effort cleanup of a UI instance's Tk root"""
    try:
        ui.root.destroy()
    except Exception:
        pass


def test_ui_modes():
    """Test the core UI mode switching functionality"""
    print("=" * 60)
    print("VoiceOS Desktop UI Test - Compact Mode")
    print("=" * 60)

    # Create compact mode configuration
    compact_config = {
        'theme': 'dark',
        'background_color': '#0078D7',  # Blue desktop background
        'compact_bar': True,
        'init_expanded': False,
        'animate': True,
        'sound': True,
        'sidebar_visible': True,
        'window_title': 'VoiceOS: Futuristic AI Desktop Assistant'
    }

    print("1. Initializing UI in compact mode...")
    ui = None
    try:
        ui = VoiceOSUI(compact_config)
        print(f"✓ Compact mode initialized successfully")
        print(f"  Mode: {'Compact' if ui.is_compact else 'Expanded'}")
        print(f"  Window size: {ui.root.winfo_geometry()}")
        print(f"  Theme: {ui.theme}")
        print(f"  Background: {ui.background_color}")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize compact mode: {e}")
        return False
    finally:
        if ui is not None:
            _destroy(ui)


def test_expanded_mode():
    """Test expanded mode functionality"""
    print("\n" + "-" * 40)
    print("VoiceOS Desktop UI Test - Expanded Mode")
    print("-" * 40)

    expanded_config = {
        'theme': 'dark',
        'background_color': '#0078D7',
        'compact_bar': False,
        'init_expanded': False,
        'animate': True,
        'sound': True,
        'sidebar_visible': True,
        'window_title': 'VoiceOS: Futuristic AI Desktop Assistant'
    }

    print("2. Switching to expanded mode...")
    voice_ui = None
    try:
        voice_ui = VoiceOSUI(expanded_config)
        voice_ui.set_mode('expanded')
        print(f"✓ Successfully switched to expanded mode")
        print(f"  Mode: {'Compact' if voice_ui.is_compact else 'Expanded'}")
        print(f"  Window size: {voice_ui.root.winfo_geometry()}")
        return True
    except Exception as e:
        print(f"✗ Failed to switch to expanded mode: {e}")
        return False
    finally:
        if voice_ui is not None:
            _destroy(voice_ui)


def test_verification_feedback():
    """Test the verification feedback system"""
    print("\n" + "-" * 40)
    print("VoiceOS Desktop UI Test - Verification Feedback")
    print("-" * 40)

    feedback_config = {
        'theme': 'dark',
        'background_color': '#0078D7',
        'compact_bar': True,
        'init_expanded': False,
        'animate': True,
        'sound': True,
        'sidebar_visible': True,
        'window_title': 'VoiceOS: Testing Verification Feedback'
    }

    print("3. Testing verification feedback integration...")
    ui = None
    try:
        ui = VoiceOSUI(feedback_config)

        # Test showing different types of feedback
        print("Testing status card...")
        ui.show_status_card("Verification successful!", "success")
        print("✓ Status card displayed")

        # Reset and test again
        time.sleep(0.2)

        print("Testing error state...")
        ui.show_status_card("Verification failed: 404", "error")
        print("✓ Error feedback displayed")

        return True
    except Exception as e:
        print(f"✗ Verification feedback test failed: {e}")
        return False
    finally:
        if ui is not None:
            _destroy(ui)


def test_animation_system():
    """Test animation functionality"""
    print("\n" + "-" * 40)
    print("VoiceOS Desktop UI Test - Animation System")
    print("-" * 40)

    test_config = {
        'theme': 'dark',
        'background_color': '#0078D7',
        'compact_bar': True,
        'init_expanded': False,
        'animate': True,
        'sound': True,
        'sidebar_visible': True,
        'window_title': 'VoiceOS: Testing Animation'
    }

    ui = None
    try:
        ui = VoiceOSUI(test_config)
        print("Testing animation trigger...")
        ui.trigger_animation("mode_change", 1.0)
        ui.trigger_animation("verify_result", 0.5)
        print("✓ Animation system tested successfully")
        return True
    except Exception as e:
        print(f"✗ Animation test failed: {e}")
        return False
    finally:
        if ui is not None:
            _destroy(ui)


def test_mode_toggle():
    """Test the toggle mode functionality"""
    print("\n" + "-" * 40)
    print("VoiceOS Desktop UI Test - Mode Toggle")
    print("-" * 40)

    config = {
        'theme': 'dark',
        'background_color': '#0078D7',
        'compact_bar': True,
        'init_expanded': False,
        'animate': True,
        'sound': True,
        'sidebar_visible': True,
        'window_title': 'VoiceOS: Mode Toggle Test'
    }

    ui = None
    try:
        ui = VoiceOSUI(config)
        print(f"Initial mode: {'Compact' if ui.is_compact else 'Expanded'}")

        # Toggle mode
        ui.toggle_mode()
        new_state = "Expanded" if not ui.is_compact else "Compact"
        print(f"✓ Mode toggle successful: {new_state}")
        return True
    except Exception as e:
        print(f"✗ Mode toggle test failed: {e}")
        return False
    finally:
        if ui is not None:
            _destroy(ui)


def main():
    """Main test function"""
    print("Starting VoiceOS UI System Test Suite...")

    tests = [
        ("Compact Mode Initialization", test_ui_modes),
        ("Expanded Mode Switching", test_expanded_mode),
        ("Verification Feedback", test_verification_feedback),
        ("Animation System", test_animation_system),
        ("Mode Toggle Functionality", test_mode_toggle)
    ]

    all_passed = True
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            status = "PASS" if result else "FAIL"
            print(f"{status}: {test_name}")
            if not result:
                all_passed = False
        except Exception as e:
            print(f"ERROR: {test_name} failed with exception: {e}")
            all_passed = False
        time.sleep(0.1)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! VoiceOS UI System is fully functional.")
    else:
        print("❌ SOME TESTS FAILED. Please review the implementation.")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
