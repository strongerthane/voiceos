"""
Command Scheduling

Schedule voice commands to run at specific times.
Supports cron-like scheduling and one-off delays.

Example:
  scheduler = CommandScheduler()
  scheduler.schedule_at("2026-09-25 14:30:00", "open notepad and write reminder")
  scheduler.schedule_recurring("0 9 * * MON", "open outlook")
  scheduler.start()  # Start scheduler daemon
"""

import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import os


class ScheduleType(Enum):
    """Types of schedules."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"


class ScheduledCommand:
    """Represents a scheduled command."""
    
    def __init__(self, command: str, schedule_type: ScheduleType, 
                 schedule_time: str, cmd_id: str = None):
        """
        Initialize scheduled command.
        
        Args:
            command: Voice command to execute
            schedule_type: Type of schedule
            schedule_time: When to run (e.g., "2026-09-25 14:30:00" or "09:30")
            cmd_id: Unique command ID
        """
        self.cmd_id = cmd_id or datetime.now().timestamp()
        self.command = command
        self.schedule_type = schedule_type
        self.schedule_time = schedule_time
        self.created_at = datetime.now()
        self.last_executed = None
        self.next_execution = self._calculate_next_execution()
        self.enabled = True
        self.execution_count = 0
        self.last_result = None
    
    def _calculate_next_execution(self) -> Optional[datetime]:
        """Calculate next execution time."""
        try:
            if self.schedule_type == ScheduleType.ONCE:
                return datetime.fromisoformat(self.schedule_time)
            
            elif self.schedule_type == ScheduleType.DAILY:
                # Time format: "HH:MM:SS"
                hour, minute, second = map(int, self.schedule_time.split(':'))
                now = datetime.now()
                next_run = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                return next_run
            
            elif self.schedule_type == ScheduleType.WEEKLY:
                # Format: "MON 09:30:00"
                parts = self.schedule_time.split()
                day_name = parts[0]
                time_str = parts[1]
                
                hour, minute, second = map(int, time_str.split(':'))
                days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
                target_day = days.index(day_name.upper())
                
                now = datetime.now()
                current_day = now.weekday()
                days_ahead = target_day - current_day
                
                if days_ahead <= 0:
                    days_ahead += 7
                
                next_run = now + timedelta(days=days_ahead)
                next_run = next_run.replace(hour=hour, minute=minute, second=second, microsecond=0)
                
                return next_run
            
        except Exception as e:
            print(f"[ERROR] Failed to calculate next execution: {e}")
        
        return None
    
    def is_due(self) -> bool:
        """Check if command is due to execute."""
        if not self.enabled or not self.next_execution:
            return False
        
        return datetime.now() >= self.next_execution
    
    def mark_executed(self, result: Any = None):
        """Mark command as executed."""
        self.last_executed = datetime.now()
        self.execution_count += 1
        self.last_result = result
        
        # Update next execution for recurring commands
        if self.schedule_type in [ScheduleType.DAILY, ScheduleType.WEEKLY]:
            self.next_execution = self._calculate_next_execution()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary."""
        return {
            "id": str(self.cmd_id),
            "command": self.command,
            "schedule_type": self.schedule_type.value,
            "schedule_time": self.schedule_time,
            "created_at": self.created_at.isoformat(),
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "next_execution": self.next_execution.isoformat() if self.next_execution else None,
            "enabled": self.enabled,
            "execution_count": self.execution_count
        }


class CommandScheduler:
    """Schedule and execute voice commands."""
    
    def __init__(self, schedule_dir: str = None):
        """Initialize scheduler."""
        if not schedule_dir:
            username = os.getenv('USERNAME')
            schedule_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.schedules"
        
        self.schedule_dir = Path(schedule_dir)
        self.schedule_dir.mkdir(parents=True, exist_ok=True)
        
        self.scheduled_commands: Dict[str, ScheduledCommand] = {}
        self.running = False
        self.thread = None
        self.executor_func = None
        self.callbacks = {}
        
        self._load_schedules()
    
    def schedule_once(self, datetime_str: str, command: str) -> str:
        """
        Schedule command to run once at specific time.
        
        Args:
            datetime_str: Datetime string (e.g., "2026-09-25 14:30:00")
            command: Voice command
        
        Returns:
            Command ID
        """
        cmd = ScheduledCommand(command, ScheduleType.ONCE, datetime_str)
        self.scheduled_commands[str(cmd.cmd_id)] = cmd
        self.save_schedules()
        return str(cmd.cmd_id)
    
    def schedule_daily(self, time_str: str, command: str) -> str:
        """
        Schedule command to run daily at specific time.
        
        Args:
            time_str: Time string (e.g., "09:30:00")
            command: Voice command
        
        Returns:
            Command ID
        """
        cmd = ScheduledCommand(command, ScheduleType.DAILY, time_str)
        self.scheduled_commands[str(cmd.cmd_id)] = cmd
        self.save_schedules()
        return str(cmd.cmd_id)
    
    def schedule_weekly(self, day_time_str: str, command: str) -> str:
        """
        Schedule command to run weekly.
        
        Args:
            day_time_str: Day and time (e.g., "MON 09:30:00")
            command: Voice command
        
        Returns:
            Command ID
        """
        cmd = ScheduledCommand(command, ScheduleType.WEEKLY, day_time_str)
        self.scheduled_commands[str(cmd.cmd_id)] = cmd
        self.save_schedules()
        return str(cmd.cmd_id)
    
    def schedule_in(self, delay_seconds: int, command: str) -> str:
        """
        Schedule command to run after N seconds.
        
        Args:
            delay_seconds: Delay in seconds
            command: Voice command
        
        Returns:
            Command ID
        """
        run_time = (datetime.now() + timedelta(seconds=delay_seconds)).isoformat()
        cmd = ScheduledCommand(command, ScheduleType.ONCE, run_time)
        self.scheduled_commands[str(cmd.cmd_id)] = cmd
        self.save_schedules()
        return str(cmd.cmd_id)
    
    def cancel_command(self, cmd_id: str) -> bool:
        """Cancel a scheduled command."""
        if cmd_id in self.scheduled_commands:
            del self.scheduled_commands[cmd_id]
            self.save_schedules()
            return True
        return False
    
    def enable_command(self, cmd_id: str, enabled: bool) -> bool:
        """Enable or disable a scheduled command."""
        if cmd_id in self.scheduled_commands:
            self.scheduled_commands[cmd_id].enabled = enabled
            self.save_schedules()
            return True
        return False
    
    def start(self, executor_func: Callable):
        """
        Start scheduler daemon.
        
        Args:
            executor_func: Function to execute commands (signature: executor_func(cmd: str) -> bool)
        """
        if self.running:
            return
        
        self.executor_func = executor_func
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop scheduler daemon."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run(self):
        """Scheduler loop (runs in background thread)."""
        while self.running:
            try:
                for cmd_id, scheduled_cmd in list(self.scheduled_commands.items()):
                    if scheduled_cmd.is_due():
                        success = False
                        
                        if self.executor_func:
                            try:
                                success = self.executor_func(scheduled_cmd.command)
                            except Exception as e:
                                print(f"[ERROR] Failed to execute scheduled command: {e}")
                        
                        scheduled_cmd.mark_executed(success)
                        
                        # Trigger callback
                        if 'command_executed' in self.callbacks:
                            for callback in self.callbacks['command_executed']:
                                try:
                                    callback(scheduled_cmd)
                                except Exception:
                                    pass
                        
                        # Remove one-time commands
                        if scheduled_cmd.schedule_type == ScheduleType.ONCE:
                            del self.scheduled_commands[cmd_id]
                        
                        self.save_schedules()
                
                time.sleep(30)  # Check every 30 seconds
            
            except Exception as e:
                print(f"[ERROR] Scheduler error: {e}")
    
    def save_schedules(self) -> str:
        """Save schedules to file."""
        filepath = self.schedule_dir / "schedules.json"
        
        data = {
            "saved_at": datetime.now().isoformat(),
            "commands": [cmd.to_dict() for cmd in self.scheduled_commands.values()]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return str(filepath)
    
    def _load_schedules(self):
        """Load schedules from file."""
        filepath = self.schedule_dir / "schedules.json"
        
        if not filepath.exists():
            return
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            for cmd_data in data.get('commands', []):
                cmd = ScheduledCommand(
                    cmd_data['command'],
                    ScheduleType[cmd_data['schedule_type'].upper()],
                    cmd_data['schedule_time'],
                    cmd_data['id']
                )
                cmd.enabled = cmd_data.get('enabled', True)
                self.scheduled_commands[cmd_data['id']] = cmd
        
        except Exception as e:
            print(f"[ERROR] Failed to load schedules: {e}")
    
    def get_upcoming(self, limit: int = 10) -> List[ScheduledCommand]:
        """Get upcoming scheduled commands."""
        upcoming = sorted(
            self.scheduled_commands.values(),
            key=lambda c: c.next_execution or datetime.max
        )
        return upcoming[:limit]
    
    def get_summary(self) -> str:
        """Get formatted schedule summary."""
        upcoming = self.get_upcoming(5)
        
        summary = f"""
╔══════════════════════════════════════════════╗
║       Scheduled Commands ({len(self.scheduled_commands)} total)      ║
╚══════════════════════════════════════════════╝

📅 UPCOMING
"""
        for cmd in upcoming:
            status = "✓" if cmd.enabled else "✗"
            time_str = cmd.next_execution.strftime("%Y-%m-%d %H:%M:%S") if cmd.next_execution else "N/A"
            summary += f"  [{status}] {time_str}: {cmd.command}\n"
        
        return summary
    
    def register_callback(self, event: str, callback: Callable):
        """Register callback for scheduler events."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)


# Self-test
if __name__ == "__main__":
    print("Testing Command Scheduling...")
    
    scheduler = CommandScheduler()
    print("[OK] Initialized CommandScheduler")
    
    # Schedule test commands
    cmd_id_1 = scheduler.schedule_daily("09:30:00", "open outlook")
    print(f"[OK] Scheduled daily command: {cmd_id_1}")
    
    cmd_id_2 = scheduler.schedule_weekly("MON 14:00:00", "open word")
    print(f"[OK] Scheduled weekly command: {cmd_id_2}")
    
    cmd_id_3 = scheduler.schedule_in(60, "open notepad")
    print(f"[OK] Scheduled command in 60 seconds: {cmd_id_3}")
    
    # Get upcoming
    upcoming = scheduler.get_upcoming(3)
    print(f"[OK] Retrieved {len(upcoming)} upcoming commands")
    
    # Display summary
    print(scheduler.get_summary())
    
    print("[OK] Command scheduling module OK")
