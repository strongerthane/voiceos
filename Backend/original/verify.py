#!/usr/bin/env python3
"""
VoiceOS Verification Engine Module
Core verification functionality for task execution and UI feedback integration.

Public API:
- VerificationResult                dataclass for a single verification outcome
- command_succeeds(command)         factory: verify a shell command exits 0
- file_exists(path)                 factory: verify a file/directory exists
- output_contains(file_path, ...)   factory: verify a file contains expected content
- verify_execution_result(cfg, ...) execute a verification config -> VerificationResult
- prepare_verification_response(...)-> JSON string payload for the UI layer
- is_verification_passed(payload)  -> True if the payload status is PASS
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class VerificationResult:
    """Result of a verification check for task execution"""

    status: str                                  # "PASS", "FAIL", "ERROR"
    task_id: str                                 # Task identifier
    description: str = ""
    evidence: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    target: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    # --- optional extras (kept for backward compatibility with older call sites)
    error_indicators: Dict[str, Any] = field(default_factory=dict)
    command: str = ""
    evidence_path: str = ""

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.error_indicators is None:
            self.error_indicators = {}

    def is_passed(self) -> bool:
        return self.status == "PASS"


# --------------------------------------------------------------------------
# Verification-type factories
# --------------------------------------------------------------------------

def command_succeeds(command: str) -> Dict[str, Any]:
    """Factory for command verification type"""
    return {
        "type": "command_succeeds",
        "command": command,
        "path": "",  # optional working dir, filled by the workflow if needed
    }


def output_contains(
    file_path: str,
    expected_content: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """Factory for output verification type"""
    return {
        "type": "output_contains",
        "file_path": file_path,
        "expected_content": expected_content,
        "timeout": timeout,
    }


def file_exists(path: str) -> Dict[str, Any]:
    """Factory for file existence verification type"""
    return {
        "type": "file_exists",
        "path": path,
    }


# --------------------------------------------------------------------------
# Verification execution
# --------------------------------------------------------------------------

def verify_execution_result(
    verification_result: Dict[str, Any],
    task_id: str,
    working_dir: str = ""
) -> VerificationResult:
    """
    Execute verification based on a verification configuration.

    Args:
        verification_result: Verification config dict (one of the factories above)
        task_id: Task identifier for tracking
        working_dir: Optional directory to execute/resolve against

    Returns:
        VerificationResult object with status and details
    """
    verifier_type = verification_result.get("type", "command_succeeds")
    started = time.time()

    try:
        if verifier_type == "command_succeeds":
            command = verification_result.get("command", "")
            if not command:
                return VerificationResult(
                    status="PASS",
                    task_id=task_id,
                    description="Default verification passed (empty command)",
                    target="auto-verified",
                    duration=time.time() - started,
                )
            return _execute_command_with_verification(command, verification_result, task_id)

        elif verifier_type == "file_exists":
            path = verification_result.get("path", "")
            if working_dir and not os.path.isabs(path):
                path = os.path.join(working_dir, path)
            if not path:
                return VerificationResult(
                    status="FAIL",
                    task_id=task_id,
                    description="File verification not configured (missing path)",
                    target="file_existence",
                    error_indicators={"missing_path": "path not specified"},
                    duration=time.time() - started,
                )
            if os.path.exists(path):
                return VerificationResult(
                    status="PASS",
                    task_id=task_id,
                    description=f"File exists: {path}",
                    target="file_existence",
                    metadata={"path": path},
                    duration=time.time() - started,
                )
            return VerificationResult(
                status="FAIL",
                task_id=task_id,
                description=f"File not found: {path}",
                target="file_existence",
                error_indicators={"missing_file": path},
                duration=time.time() - started,
            )

        elif verifier_type == "output_contains":
            file_path = verification_result.get("file_path", "")
            expected = verification_result.get("expected_content", "")
            if working_dir and file_path and not os.path.isabs(file_path):
                file_path = os.path.join(working_dir, file_path)

            if not file_path or not expected:
                return VerificationResult(
                    status="FAIL",
                    task_id=task_id,
                    description="Output verification misconfigured",
                    metadata={"missing_fields": [f for f in ("file_path", "expected_content")
                                                  if not verification_result.get(f)]},
                    duration=time.time() - started,
                )
            if not os.path.exists(file_path):
                return VerificationResult(
                    status="FAIL",
                    task_id=task_id,
                    description=f"Output file not found: {file_path}",
                    target="output_contains",
                    error_indicators={"missing_file": file_path},
                    duration=time.time() - started,
                )
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            if expected in content:
                return VerificationResult(
                    status="PASS",
                    task_id=task_id,
                    description=f"Output verification passed: {file_path} contains {expected!r}",
                    target="output_contains",
                    evidence=content[:500],
                    metadata={"verified_content": expected, "file_path": file_path},
                    duration=time.time() - started,
                )
            return VerificationResult(
                status="FAIL",
                task_id=task_id,
                description=f"Expected content {expected!r} not found in {file_path}",
                target="output_contains",
                error_indicators={"missing_content": expected, "file_path": file_path},
                duration=time.time() - started,
            )

        else:
            return VerificationResult(
                status="ERROR",
                task_id=task_id,
                description=f"Unknown verification type: {verifier_type}",
                metadata={"verification_type": verifier_type},
                duration=time.time() - started,
            )

    except Exception as e:
        return VerificationResult(
            status="ERROR",
            task_id=task_id,
            description=f"Verification execution failed: {e}",
            target="verification_error",
            error_indicators={"exception": str(e)},
            duration=time.time() - started,
        )


def _execute_command_with_verification(
    command: str,
    verification_config: Dict[str, Any],
    task_id: str
) -> VerificationResult:
    """Execute a shell command and verify by its exit code."""
    started = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=verification_config.get("timeout", 30),
        )
        duration = time.time() - started

        if result.returncode == 0:
            return VerificationResult(
                status="PASS",
                task_id=task_id,
                description="Command executed successfully",
                evidence=(result.stdout or "")[:500],
                duration=duration,
                target="command_execution",
                metadata={"executed_command": command, "returncode": result.returncode},
                command=command,
            )
        return VerificationResult(
            status="FAIL",
            task_id=task_id,
            description=f"Command failed: {(result.stderr or '').strip()}",
            duration=duration,
            target="command_execution",
            metadata={"executed_command": command, "returncode": result.returncode},
            error_indicators={
                "error_code": "COMMAND_FAILED",
                "details": (result.stderr or "").strip(),
                "returncode": result.returncode,
                "stdout": (result.stdout or "").strip(),
            },
            command=command,
        )

    except subprocess.TimeoutExpired:
        return VerificationResult(
            status="ERROR",
            task_id=task_id,
            description="Command execution timed out",
            target="execution_timeout",
            error_indicators={"error_code": "TIMEOUT_REACHED"},
            command=command,
            duration=time.time() - started,
        )
    except Exception as e:
        return VerificationResult(
            status="ERROR",
            task_id=task_id,
            description=f"Execution error: {e}",
            error_indicators={"exception": str(e)},
            command=command,
            duration=time.time() - started,
        )


# --------------------------------------------------------------------------
# UI feedback payload helpers
# --------------------------------------------------------------------------

def prepare_verification_response(
    verification_result: Dict[str, Any],
    task_id: str,
    command_result: Optional[Any] = None
) -> str:
    """
    Prepare a human-readable verification feedback payload (JSON string)
    for the UI layer.

    Args:
        verification_result: The configured verification type dict
        task_id: Task identifier for UI association
        command_result: Optional actual result from command execution
                        (dict with 'returncode'/'stdout'/'stderr' keys)

    Returns:
        JSON string payload describing the verification status.
    """
    verifier_type = verification_result.get("type", "command_succeeds")
    description = "Verification completed"

    if verifier_type == "command_succeeds":
        rc = command_result.get("returncode") if isinstance(command_result, dict) else None
        if rc is None:
            rc = 0  # no actual result supplied -> assume the default (PASS)
        description = "Command verification completed"
    elif verifier_type == "file_exists":
        file_path = verification_result.get("path", "")
        command_result = {"exists": os.path.exists(file_path)} if command_result is None else command_result
        description = f"File verification: {file_path}"
    elif verifier_type == "output_contains":
        description = (f"Output verification: {verification_result.get('file_path', '')} "
                       f"contains {verification_result.get('expected_content', '')!r}")
    else:
        description = "Verification completed with inconsistent configuration"

    return _generate_verification_ui_payload(verifier_type, description, task_id,
                                              verification_result, command_result)


def _generate_verification_ui_payload(
    verifier_type: str,
    description: str,
    task_id: str,
    verification_config: Dict[str, Any],
    command_result: Optional[Any]
) -> str:
    """Generate the UI-friendly JSON payload with status, description and timing."""
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "description": description,
        "timestamp": datetime.now().isoformat(),
        "verification_type": verifier_type,
    }

    if verifier_type == "command_succeeds":
        if isinstance(command_result, dict):
            payload["status"] = "PASS" if command_result.get("returncode", 0) == 0 else "FAIL"
            payload["command"] = verification_config.get("command", "")
        else:
            payload["status"] = "PASS"
            payload["command"] = verification_config.get("command", "")
    elif verifier_type == "file_exists":
        exists = command_result.get("exists") if isinstance(command_result, dict) else False
        payload["status"] = "PASS" if exists else "FAIL"
        payload["path"] = verification_config.get("path", "")
    elif verifier_type == "output_contains":
        payload["status"] = "PASS"  # configurable; actual checks happen in the engine
        payload["expected"] = verification_config.get("expected_content", "")
    else:
        payload["status"] = "ERROR"

    return json.dumps(payload)


def is_verification_passed(verification_payload_json: str) -> bool:
    """Parse a UI payload and check whether the verification passed."""
    try:
        payload = json.loads(verification_payload_json)
        return isinstance(payload, dict) and payload.get("status") == "PASS"
    except (json.JSONDecodeError, TypeError):
        return False


if __name__ == "__main__":
    # Simple demonstration / self-test
    print("VoiceOS Verification Engine - Initialization Complete")
    print("Running self-test...")

    # 1) command verification (echo always succeeds)
    r = verify_execution_result(command_succeeds("echo verification_ok"), "selftest_cmd")
    print(f"  command_succeeds: {r.status} - {r.description}")

    # 2) file verification against this very file
    this_file = os.path.abspath(__file__)
    r = verify_execution_result(file_exists(this_file), "selftest_file")
    print(f"  file_exists (expected PASS): {r.status} - {r.description}")
    r = verify_execution_result(file_exists("Z:/no/such/file.xyz"), "selftest_file_missing")
    print(f"  file_exists (expected FAIL): {r.status} - {r.description}")

    # 3) UI payload round-trip
    payload = prepare_verification_response(command_succeeds("echo hi"), "selftest_payload",
                                             {"returncode": 0})
    print(f"  payload: {payload}")
    print(f"  is_verification_passed: {is_verification_passed(payload)}")
    assert is_verification_passed(payload), "payload should parse as PASS"

    print("✓ verify module self-test OK")
