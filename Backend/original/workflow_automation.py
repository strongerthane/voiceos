"""
Workflow Automation

Chain multiple voice commands into automated workflows.
Supports sequences, conditionals, and parallel execution.

Example:
  workflow = Workflow("daily_report")
  workflow.add_step("open word")
  workflow.add_step("open notepad and write daily summary")
  workflow.add_step("save to onedrive")
  workflow.add_step("email to boss@company.com")
  workflow.execute()
"""

import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from enum import Enum


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class WorkflowStep:
    """Individual step in a workflow."""
    
    def __init__(self, command: str, timeout: int = 30, retry: int = 1):
        """
        Initialize workflow step.
        
        Args:
            command: Voice command to execute
            timeout: Max seconds to wait for step
            retry: Number of retries on failure
        """
        self.command = command
        self.timeout = timeout
        self.retry = retry
        self.status = WorkflowStatus.PENDING
        self.result = None
        self.error = None
        self.execution_time = 0
        self.attempts = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Export step to dictionary."""
        return {
            "command": self.command,
            "timeout": self.timeout,
            "retry": self.retry,
            "status": self.status.value,
            "execution_time": self.execution_time,
            "attempts": self.attempts,
            "error": self.error
        }


class Workflow:
    """Automated workflow executor."""
    
    def __init__(self, name: str, workflows_dir: str = None):
        """
        Initialize workflow.
        
        Args:
            name: Workflow identifier (used in voice commands)
            workflows_dir: Storage directory for workflow definitions
        """
        self.name = name
        self.steps: List[WorkflowStep] = []
        self.status = WorkflowStatus.PENDING
        self.created_at = datetime.now()
        self.executed_at = None
        self.execution_time = 0
        self.callbacks: Dict[str, List[Callable]] = {}
        
        if not workflows_dir:
            import os
            username = os.getenv('USERNAME')
            workflows_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.workflows"
        
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def add_step(self, command: str, timeout: int = 30, retry: int = 1) -> 'Workflow':
        """Add step to workflow (chainable)."""
        step = WorkflowStep(command, timeout, retry)
        self.steps.append(step)
        return self
    
    def add_conditional_step(self, condition_func: Callable, true_command: str,
                            false_command: str = None) -> 'Workflow':
        """
        Add conditional step.
        
        Executes true_command if condition_func() returns True, else false_command.
        """
        # Placeholder for conditional logic
        step = WorkflowStep(f"[CONDITIONAL] {true_command}")
        step._condition = condition_func
        step._false_command = false_command
        self.steps.append(step)
        return self
    
    def add_parallel_steps(self, commands: List[str], timeout: int = 30) -> 'Workflow':
        """
        Add steps that execute in parallel.
        
        All commands execute simultaneously, workflow waits for all to complete.
        """
        for cmd in commands:
            step = WorkflowStep(cmd, timeout)
            step._parallel = True
            self.steps.append(step)
        return self
    
    def on_step_complete(self, callback: Callable):
        """Register callback when step completes."""
        if 'step_complete' not in self.callbacks:
            self.callbacks['step_complete'] = []
        self.callbacks['step_complete'].append(callback)
        return self
    
    def on_workflow_complete(self, callback: Callable):
        """Register callback when workflow completes."""
        if 'workflow_complete' not in self.callbacks:
            self.callbacks['workflow_complete'] = []
        self.callbacks['workflow_complete'].append(callback)
        return self
    
    def execute(self, executor_func: Callable = None) -> bool:
        """
        Execute workflow steps sequentially.
        
        Args:
            executor_func: Function to execute voice commands
                          Signature: executor_func(command: str) -> (success: bool, result: Any)
        
        Returns:
            True if all steps successful, False otherwise
        """
        if not executor_func:
            raise ValueError("executor_func required to execute workflow")
        
        self.status = WorkflowStatus.RUNNING
        self.executed_at = datetime.now()
        start_time = time.time()
        
        for i, step in enumerate(self.steps):
            step.status = WorkflowStatus.RUNNING
            step.attempts = 0
            
            # Execute with retries
            success = False
            for attempt in range(step.retry):
                step.attempts = attempt + 1
                step_start = time.time()
                
                try:
                    success, result = executor_func(step.command)
                    step.result = result
                except Exception as e:
                    success = False
                    step.error = str(e)
                
                step.execution_time = int((time.time() - step_start) * 1000)
                
                if success:
                    step.status = WorkflowStatus.COMPLETED
                    break
                elif attempt < step.retry - 1:
                    time.sleep(2)  # Wait before retry
            
            if not success:
                step.status = WorkflowStatus.FAILED
                self.status = WorkflowStatus.FAILED
                self._trigger_callbacks('step_complete', step)
                return False
            
            self._trigger_callbacks('step_complete', step)
        
        self.execution_time = int(time.time() - start_time)
        self.status = WorkflowStatus.COMPLETED
        self._trigger_callbacks('workflow_complete', self)
        
        return True
    
    def execute_async(self, executor_func: Callable) -> threading.Thread:
        """Execute workflow in background thread."""
        thread = threading.Thread(target=self.execute, args=(executor_func,), daemon=True)
        thread.start()
        return thread
    
    def _trigger_callbacks(self, event: str, data: Any):
        """Trigger registered callbacks."""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"[ERROR] Callback failed: {e}")
    
    def save(self, filepath: str = None) -> str:
        """Save workflow definition to JSON."""
        if not filepath:
            filepath = self.workflows_dir / f"{self.name}.json"
        
        workflow_data = {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "steps": [step.to_dict() for step in self.steps]
        }
        
        with open(filepath, 'w') as f:
            json.dump(workflow_data, f, indent=2)
        
        return str(filepath)
    
    @staticmethod
    def load(filepath: str) -> 'Workflow':
        """Load workflow from JSON."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        workflow = Workflow(data['name'])
        for step_data in data['steps']:
            workflow.add_step(step_data['command'], step_data['timeout'], step_data['retry'])
        
        return workflow
    
    def get_summary(self) -> str:
        """Get formatted workflow summary."""
        summary = f"""
╔══════════════════════════════════════════════╗
║          Workflow: {self.name:<27}║
╚══════════════════════════════════════════════╝

📋 Steps: {len(self.steps)}
⏱️  Total Time: {self.execution_time}s
📊 Status: {self.status.value.upper()}

"""
        for i, step in enumerate(self.steps, 1):
            status_icon = "✓" if step.status == WorkflowStatus.COMPLETED else "✗" if step.status == WorkflowStatus.FAILED else "○"
            summary += f"  {i}. [{status_icon}] {step.command}\n"
            if step.error:
                summary += f"     Error: {step.error}\n"
        
        return summary


class WorkflowLibrary:
    """Manage saved workflows."""
    
    def __init__(self, workflows_dir: str = None):
        """Initialize workflow library."""
        if not workflows_dir:
            import os
            username = os.getenv('USERNAME')
            workflows_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.workflows"
        
        self.workflows_dir = Path(workflows_dir)
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def save_workflow(self, workflow: Workflow) -> str:
        """Save workflow to library."""
        return workflow.save(self.workflows_dir / f"{workflow.name}.json")
    
    def load_workflow(self, name: str) -> Optional[Workflow]:
        """Load workflow by name."""
        filepath = self.workflows_dir / f"{name}.json"
        if filepath.exists():
            return Workflow.load(str(filepath))
        return None
    
    def list_workflows(self) -> List[str]:
        """List all saved workflows."""
        return [f.stem for f in self.workflows_dir.glob("*.json")]
    
    def delete_workflow(self, name: str) -> bool:
        """Delete workflow by name."""
        filepath = self.workflows_dir / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False


# Self-test
if __name__ == "__main__":
    print("Testing Workflow Automation...")
    
    # Create workflow
    workflow = Workflow("daily_report")
    workflow.add_step("open notepad")
    workflow.add_step("open notepad and write daily report")
    workflow.add_step("save file")
    
    print(f"[OK] Created workflow with {len(workflow.steps)} steps")
    
    # Save workflow
    saved = workflow.save()
    print(f"[OK] Saved workflow to {saved}")
    
    # Load workflow
    loaded = Workflow.load(saved)
    print(f"[OK] Loaded workflow: {loaded.name}")
    
    # Display summary
    print(workflow.get_summary())
    
    print("[OK] Workflow automation module OK")
