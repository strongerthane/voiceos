# VoiceOS Backend Core Module Implementation (Task #14)
# Backend core modules with verification integration for VoiceOS.
#
# Task execution and verification now live in core.py / verify.py (single
# source of truth); this module wires them into UI feedback and re-exports
# the workflow classes for backward compatibility.

import json
from typing import Any, Dict

from verify import VerificationResult
from core import TaskItem, VoiceOSWorkflow  # noqa: F401  (re-exported)


class VoiceOSUIFeedbackController:
    """Middleware to handle UI feedback from backend verification results"""

    def __init__(self, ui_manager):
        """
        Initialize the feedback controller.

        Args:
            ui_manager: UI manager instance for status updates and visual feedback
        """
        self.ui_manager = ui_manager
        self.last_verification_result = None

    def process_verification_result(self, verification_result, task_id: str) -> str:
        """
        Process a verification result (VerificationResult or plain dict) and
        update the UI accordingly.

        Args:
            verification_result: VerificationResult dataclass or result dict
            task_id: The task ID associated with this verification

        Returns:
            JSON payload string describing the verification result.
        """
        # Normalize to a plain dict (accept dataclass or dict input)
        if isinstance(verification_result, VerificationResult):
            data = {
                "status": verification_result.status,
                "task_id": verification_result.task_id,
                "description": verification_result.description,
            }
        elif isinstance(verification_result, dict):
            data = verification_result
        else:
            data = {"status": "unknown", "task_id": task_id,
                    "description": str(verification_result)}

        verification_payload = json.dumps(data)

        # Extract key information for UI display
        status = data.get('status', 'unknown')
        result_task_id = data.get('task_id', task_id) or task_id
        description = data.get('description', 'No description')

        # Resolve the UI mode defensively — ui_manager stubs may not define
        # mode_manager at all, and that must never crash the backend.
        mode = "unknown"
        mode_manager = getattr(self.ui_manager, "mode_manager", None)
        if mode_manager is not None:
            is_expanded = bool(getattr(mode_manager, "is_expanded", False))
            is_compact = bool(getattr(mode_manager, "is_compact", not is_expanded))
            mode = 'expanded' if is_expanded else ('compact' if is_compact else 'unknown')

        # Update the UI with verification status (best-effort)
        try:
            self.ui_manager.update_ui_state(
                mode=mode,
                visual_state=status,
                last_verification=result_task_id
            )
        except Exception:
            pass  # UI stubs may not implement update_ui_state

        self.last_verification_result = data
        print(f"📊 Verification Result for Task {result_task_id}: {status} - {description}")

        return verification_payload


def create_verification_workflow(config: Dict[str, Any]) -> VoiceOSWorkflow:
    """Create a VoiceOSWorkflow instance with verification capabilities"""
    return VoiceOSWorkflow(config)


def detect_verification_status_from_result(verification_result: VerificationResult) -> str:
    """
    Determine the UI feedback status based on verification result.

    Args:
        verification_result: The VerificationResult object

    Returns:
        One of 'success' | 'error' | 'processing'
    """
    if verification_result.status == "PASS":
        return "success"
    elif verification_result.status in ("FAIL", "ERROR"):
        return "error"
    else:
        return "processing"


# Example usage for testing
def test_verification_integration() -> bool:
    """Test the backend verification integration end-to-end"""
    print("🔧 Testing Backend Verification Integration...")

    try:
        # Create workflow instance
        config = {
            'output_dir': '/path/to/results',
            'timeout': 30
        }

        workflow = create_verification_workflow(config)

        # Add a test task
        workflow.add_task(
            task_id="test_verification_001",
            description="Test system responsiveness",
            command="echo verification_success",
            verification_type="command_succeeds"
        )

        # Execute the task
        print("Executing verification task...")
        result = workflow.execute_task("test_verification_001")

        # Display result
        print(f"Task Status: {result.status}")
        print(f"Description: {result.description}")
        if result.status == "PASS":
            print("✅ Verification PASSED")
        else:
            print("❌ Verification FAILED")
            return False

        # UI status mapping
        assert detect_verification_status_from_result(result) == "success"
        fail_probe = VerificationResult(status="FAIL", task_id="probe",
                                         description="probe result")
        assert detect_verification_status_from_result(fail_probe) == "error"

        # ---- Feedback controller with a stub UI that has NO mode_manager ----
        class StubUI:
            def __init__(self):
                self.updates = []

            def update_ui_state(self, **kwargs):
                self.updates.append(kwargs)

        stub = StubUI()
        controller = VoiceOSUIFeedbackController(stub)

        # dict input
        payload = controller.process_verification_result(
            {"status": "PASS", "task_id": "t1", "description": "ok"}, "t1")
        assert '"status": "PASS"' in payload, payload

        # dataclass input (the real VerificationResult from above)
        payload2 = controller.process_verification_result(result,
                                                           "test_verification_001")
        assert '"PASS"' in payload2, payload2
        assert stub.updates, "UI should have been notified"
        assert stub.updates[-1]["visual_state"] == "PASS"

        # a UI whose update_ui_state raises must not crash the backend
        class BrokenUI:
            mode_manager = None

            def update_ui_state(self, **kwargs):
                raise RuntimeError("UI layer down")

        VoiceOSUIFeedbackController(BrokenUI()).process_verification_result(
            {"status": "PASS", "task_id": "t9", "description": "still fine"}, "t9")

        # task status tracking through the workflow
        assert workflow.get_task_status("test_verification_001") == "PASS"
        assert workflow.get_tasks_by_status("PASS") == ["test_verification_001"]

        return True

    except Exception as e:
        print(f"❌ Verification integration test raised: {e}")
        return False


# Main execution
if __name__ == "__main__":
    print("Starting VoiceOS Backend Verification Integration Test")
    success = test_verification_integration()
    if success:
        print("✓ Backend verification integration successful!")
    else:
        print("❌ Backend verification integration failed!")
