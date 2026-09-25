# VoiceOS Core Backend Module - Updated Implementation
#
# Single source of truth for command execution lives in verify.py
# (verify_execution_result). This module orchestrates tasks, tracks state
# via CompactState, and pushes status updates to the UI layer.

import os
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, Optional
import json

# Import core verification utilities
from state import CompactState
from verify import (
    VerificationResult,
    command_succeeds,
    output_contains,
    file_exists,
    verify_execution_result,
    prepare_verification_response,
    is_verification_passed
)


class TaskItem:
    """Represents a task in the VoiceOS system"""

    def __init__(self, id: str, description: str, command: str,
                 verification_config: Dict[str, Any]):
        self.id = id
        self.task_id = id                       # alias kept for older call sites
        self.description = description
        self.command = command
        self.verification_config = verification_config
        self.status = "pending"                 # Task is pending by default
        self.completed = False
        self.start_time = None                  # set when execution begins
        self.last_verification = None          # latest verification result

    def update_status(self, new_status: str):
        """Update task status descriptor"""
        self.status = new_status
        if new_status in ('PASS', 'FAIL', 'ERROR'):
            self.completed = True

    # Backward-compatible alias (older code called status_update)
    def status_update(self, new_status: str):
        self.update_status(new_status)

    def update_verification_status(self, verification_result):
        """Update task with latest verification result (dataclass or dict)"""
        if isinstance(verification_result, dict):
            self.last_verification = dict(verification_result)
        else:
            self.last_verification = verification_result


class VoiceOSWorkflow:
    """Core workflow orchestrator with verification integration"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.tasks: Dict[str, TaskItem] = {}
        self.state = CompactState()
        self._build_initial_components()

    def _build_initial_components(self):
        """Create initial verification components"""
        self.base_verifiers = {
            'default': command_succeeds(""),
        }

    def add_task(self, task_id: str, description: str, command: str,
                 verification_type: str = "command_succeeds",
                 verification_config: Optional[Dict[str, Any]] = None) -> TaskItem:
        """
        Add a new task to the system.

        Args:
            task_id: Unique task identifier
            description: Human-readable description
            command: Shell command to execute (or path, for file_exists)
            verification_type: One of 'command_succeeds'|'file_exists'|'output_contains'
            verification_config: Optional full verification config; overrides type
        """
        task = TaskItem(
            id=task_id,
            description=description,
            command=command,
            verification_config=self._make_verifier_config(verification_type, command,
                                                           verification_config)
        )
        self.tasks[task_id] = task
        return task

    def _make_verifier_config(self, verifier_type: str, command: str,
                              verification_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create verifier configuration based on type"""
        if isinstance(verification_config, dict) and verification_config.get("type"):
            return dict(verification_config)   # full config supplied by the caller
        if verifier_type == "command_succeeds":
            return command_succeeds(command)
        elif verifier_type == "file_exists":
            # for this type the 'command' slot carries the path to check
            return file_exists(command)
        elif verifier_type == "output_contains":
            # requires an explicit verification_config with file_path/content;
            # a misconfigured dict yields an honest FAIL from the engine
            return output_contains("", "")
        else:
            return command_succeeds(command)

    def execute_task(self, task_id: str) -> VerificationResult:
        """Execute a task and return verification result"""
        if task_id not in self.tasks:
            return VerificationResult(
                status="ERROR",
                task_id=task_id,
                description=f"Task {task_id} not found"
            )

        task = self.tasks[task_id]
        task.start_time = time.time()
        self.state.set_active_step(task_id)

        try:
            result = verify_execution_result(
                task.verification_config,
                task_id,
                working_dir=self.config.get("working_dir", "")
            )
        except Exception as e:
            # the engine converts normal failures into ERROR results itself;
            # this guard covers a fundamentally broken config (e.g. None)
            result = VerificationResult(
                status="ERROR",
                task_id=task_id,
                description=f"Verification engine raised: {e}",
                error_indicators={"exception": str(e)}
            )

        task.update_status(result.status)
        task.update_verification_status(result)
        self.state.record_status(result.status)
        self.state.set_active_step(None)

        return result

    def get_task_status(self, task_id: str) -> str:
        """Get current status of a task"""
        task = self.tasks.get(task_id)
        return task.status if task else "not_found"

    def get_tasks_by_status(self, status: str) -> list:
        """Get all tasks with a given status"""
        return [task_id for task_id, task in self.tasks.items()
                if getattr(task, 'status', '') == status]


class VerifySystemManager:
    """Manages verification operations and integrates with UI feedback system"""

    def __init__(self, ui_manager=None,
                 workflow: Optional[VoiceOSWorkflow] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the verification system.

        Args:
            ui_manager: Reference to UI manager for status updates and visual
                        feedback (may be None for headless use)
            workflow: Optional existing VoiceOSWorkflow to manage
            config: Config used only when creating an internal workflow
        """
        self.ui_manager = ui_manager
        if workflow is None:
            workflow = VoiceOSWorkflow(config or {})
        self.workflow = workflow
        self.config = workflow.config        # backward-compatible alias
        self.active_verifications = {}       # track in-flight verifications

    @property
    def tasks(self) -> Dict[str, TaskItem]:
        return self.workflow.tasks

    def add_task(self, task_id: str, description: str, command: str,
                 verification_type: str = "command_succeeds",
                 verification_config: Optional[Dict[str, Any]] = None) -> TaskItem:
        """Convenience passthrough to the workflow"""
        return self.workflow.add_task(task_id, description, command,
                                       verification_type, verification_config)

    def execute_verification_and_notify(self, task_id: str) -> VerificationResult:
        """
        Execute verification for a task and notify UI of the result.

        UI callbacks are best-effort: a stubbed or mismatched ui_manager can
        never crash the backend.
        """
        print(f"🔍 Executing verification for task: {task_id}")

        if task_id not in self.tasks:
            result = VerificationResult(
                status="ERROR",
                task_id=task_id,
                description=f"Task {task_id} not found in workflow"
            )
            self._notify(task_id, "ERROR: Task not found", "verification_failure", result)
            return result

        self.active_verifications[task_id] = True
        try:
            result = self.workflow.execute_task(task_id)
        finally:
            self.active_verifications.pop(task_id, None)

        self._notify(task_id, f"{result.status}: {result.description}",
                     "verification_update", result)
        print(f"📈 Task [{task_id}] verification completed: {result.status}")
        return result

    def _notify(self, task_id: str, message: str, kind: str,
                result: VerificationResult):
        """Push status to the UI manager; never raise on a UI mismatch"""
        if self.ui_manager is None:
            return
        try:
            self.ui_manager.trigger_verification(task_id, message, kind)
        except Exception:
            pass
        try:
            self.ui_manager.update_feedback_from_verification(
                task_id, result.status, result.description,
                getattr(result, "target", "")
            )
        except Exception:
            pass


# --------------------------------------------------------------------------
# Smoke test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    print("VoiceOS Core Backend - smoke test")
    wf = VoiceOSWorkflow({"timeout": 10})

    # 1) command verification
    wf.add_task("task_cmd", "Run echo command", "echo core_engine_ok")
    r = wf.execute_task("task_cmd")
    print(f"  command_succeeds: {r.status} - {r.description}")
    assert r.status == "PASS", f"expected PASS, got {r.status}"

    # 2) command that fails
    wf.add_task("task_fail", "Force a failure", "exit 3")
    r = wf.execute_task("task_fail")
    print(f"  failing command: {r.status} (expected FAIL)")

    # 3) file_exists PASS/FAIL via a temp file
    tmp = Path(tempfile.gettempdir()) / "voiceos_core_test.txt"
    tmp.write_text("verification marker present\n", encoding="utf-8")
    wf.add_task("task_file", "Check file exists", "", "file_exists",
                {"type": "file_exists", "path": str(tmp)})
    r = wf.execute_task("task_file")
    print(f"  file_exists (expected PASS): {r.status}")
    assert r.status == "PASS"

    wf.add_task("task_file_missing", "Check missing file", "", "file_exists",
                {"type": "file_exists", "path": "Z:/no/such/file.xyz"})
    r = wf.execute_task("task_file_missing")
    print(f"  file_exists (expected FAIL): {r.status}")
    assert r.status == "FAIL"

    # 4) output_contains on the temp file
    wf.add_task("task_output", "Check file content", "", "output_contains",
                {"type": "output_contains", "file_path": str(tmp),
                 "expected_content": "verification marker"})
    r = wf.execute_task("task_output")
    print(f"  output_contains (expected PASS): {r.status}")
    assert r.status == "PASS"

    # 5) headless VerifySystemManager (no UI attached)
    mgr = VerifySystemManager()
    mgr.add_task("mgr_cmd", "Manager echo", "echo manager_ok")
    r = mgr.execute_verification_and_notify("mgr_cmd")
    print(f"  manager verify: {r.status} - {r.description}")
    assert r.status == "PASS"

    # 6) unknown task produces ERROR, not a crash
    r = mgr.execute_verification_and_notify("nonexistent_task")
    print(f"  unknown task: {r.status} (expected ERROR)")
    assert r.status == "ERROR"

    counts = wf.state.status_counts
    print(f"  state counts: {counts}")
    # 3 PASS (task_cmd, task_file, task_output), 2 FAIL, 0 ERROR on wf itself
    assert counts['pass'] == 3, counts
    assert counts['fail'] == 2, counts
    assert counts['error'] == 0, counts

    print("✓ core module smoke test OK")
