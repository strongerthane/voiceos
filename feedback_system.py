"""
Real-time Feedback System for VoiceOS Desktop UI
This module enhances the UI with real-time feedback for verification status
"""

import time
import threading
from datetime import datetime

class VerificationStatusIndicator:
    """Real-time UI element to show verification status"""

    def __init__(self, position=(100, 50), size=(200, 20)):
        self.position = position
        self.size = size
        self.current_status = "idle"
        self.status_history = []
        self.last_update = 0
        self.pending_updates = 0
        self.visible = True
        self.animation_state = "default"

    def update_status(self, new_status, verification_id=None):
        """Update the verification status with animation"""
        self.current_status = new_status
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Track this update for animation
        self.pending_updates += 1
        self.status_history.append({
            'status': new_status,
            'timestamp': timestamp,
            'action': verification_id
        })

        # Update animation state
        if new_status == "idle":
            self.animation_state = "pulsing_idle"
        elif new_status == "processing":
            self.animation_state = "spinning_loading"
        elif new_status == "success":
            self.animation_state = "pulsing_success"
        elif new_status == "error":
            self.animation_state = "pulsing_error"
        else:
            self.animation_state = "default"

        self.last_update = time.time()
        print(f"🔄 Updated verification status: {new_status}")

    def get_display_text(self):
        """Get the text to display in the UI"""
        time_ago = int(time.time() - self.last_update)
        time_str = ""
        if time_ago < 1:
            time_str = "near"
        elif time_ago < 5:
            time_str = "recently"
        elif time_ago < 15:
            time_str = "10s ago"
        elif time_ago < 60:
            time_str = f"{time_ago//10}s ago"
        else:
            time_str = f"{time_ago//60}m ago"

        return f"{self.current_status.upper()} ({time_str})"

class VoiceOSUIFeedbackSystem:
    """System to manage real-time verification feedback in UI"""

    def __init__(self, ui_controller):
        self.ui_controller = ui_controller
        self.indicator = VerificationStatusIndicator()
        self.is_active = False
        self.feedback_thread = None
        self.running = True

    def start_feedback_system(self):
        """Start the feedback system thread"""
        if not self.is_active:
            self.is_active = True
            self.feedback_thread = threading.Thread(target=self._feedback_loop)
            self.feedback_thread.start()
            print("✅ Real-time feedback system activated")

    def _feedback_loop(self):
        """Thread that handles continuous status updates"""
        print("📈 Starting real-time feedback loop")
        while self.running and self.is_active:
            try:
                # Simulate checking for new verification updates
                time.sleep(0.5)

                # In a real implementation, this would poll the verification system
                # For demonstration, we'll update with sample status changes
                if self.ui_controller:
                    # Check if there are any verification-related state changes
                    if hasattr(self.ui_controller, 'last_verification_status'):
                        new_status = self.ui_controller.last_verification_status
                        self.indicator.update_status(new_status)

                # Update UI with current status
                display_text = self.indicator.get_display_text()
                print(f"💬 UI Feedback: {display_text}")

            except Exception as e:
                print(f"⚠️  Feedback loop error: {e}")
                time.sleep(1)

        print("🛑 Real-time feedback system stopped")

    def stop_feedback_system(self):
        """Stop the feedback system"""
        self.is_active = False
        if self.feedback_thread:
            self.running = False
            self.feedback_thread.join(timeout=2)
        print("⏹️  Real-time feedback system stopped")

# Example implementation for integration
def create_verification_indicator(ui_controller):
    """Create and return a verification status indicator"""
    indicator = VerificationStatusIndicator(position=(50, 850), size=(300, 40))

    # Initialize with starting status
    indicator.update_status("idle", "initial_start")

    # Return both the indicator and a function to update it
    def update_verification_status(status, verification_id=None):
        """Update the verification status indicator"""
        indicator.update_status(status, verification_id)

    return indicator, update_verification_status

def simulate_verification_process(ui_controller, update_callback):
    """Simulate a verification process and update UI in real-time"""
    print("🚀 Starting verification process simulation")
    update_callback("processing", "verification_001")

    time.sleep(2)

    # Simulate successful verification
    update_callback("success", "verification_001")

    print("✓ Verification completed successfully")

# Example usage
def test_feedback_system():
    """Test the real-time feedback system"""
    print("=" * 60)
    print("Testing VoiceOS Real-Time Feedback System")
    print("=" * 60)

    # Create mock UI controller
    class MockUIController:
        def __init__(self):
            self.last_verification_status = "idle"

        def trigger_verification(self, status):
            """Simulate triggering a verification with new status"""
            self.last_verification_status = status

    mock_ui = MockUIController()

    # Create feedback system
    feedback_system = VoiceOSUIFeedbackSystem(mock_ui)
    indicator, update_callback = create_verification_indicator(mock_ui)

    # Start feedback system
    feedback_system.start_feedback_system()

    # Simulate verification process
    for i in range(3):
        feedback_system.indicator.update_status("processing" if i < 2 else "success")
        time.sleep(1)

    # Test different statuses
    test_statuses = ["idle", "processing", "success", "error", "success"]
    for status in test_statuses:
        mock_ui.trigger_verification(status)
        time.sleep(0.5)

    # Stop feedback system
    feedback_system.stop_feedback_system()
    print("=" * 60)
    print("✅ Feedback system test completed")
    return True