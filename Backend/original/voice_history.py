"""
Voice Command History & Analytics

Tracks all voice commands, success rates, execution times, and usage patterns.
Provides dashboard for user insights and performance metrics.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import Counter


class VoiceHistory:
    """Track and analyze voice command history."""
    
    def __init__(self, history_dir: str = None):
        """Initialize history tracker."""
        if not history_dir:
            username = os.getenv('USERNAME')
            history_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS\\.history"
        
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.history_dir / "voiceos_history.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                command TEXT NOT NULL,
                action TEXT,
                success BOOLEAN,
                execution_time_ms INTEGER,
                app_opened TEXT,
                file_saved TEXT,
                error_message TEXT,
                user_rating INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_commands INTEGER,
                successful_commands INTEGER,
                failed_commands INTEGER,
                most_used_app TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_command(self, command: str, action: str = None, success: bool = True,
                   execution_time_ms: int = 0, app_opened: str = None,
                   file_saved: str = None, error_message: str = None) -> int:
        """
        Log a voice command to history.
        
        Returns:
            Command ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO commands 
            (timestamp, command, action, success, execution_time_ms, app_opened, file_saved, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, command, action, success, execution_time_ms, app_opened, file_saved, error_message))
        
        conn.commit()
        cmd_id = cursor.lastrowid
        conn.close()
        
        return cmd_id
    
    def rate_command(self, cmd_id: int, rating: int):
        """Rate a command (1-5 stars)."""
        if not 1 <= rating <= 5:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE commands SET user_rating = ? WHERE id = ?', (rating, cmd_id))
        conn.commit()
        conn.close()
        
        return True
    
    def get_today_stats(self) -> Dict[str, Any]:
        """Get today's command statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN success=1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),
                   AVG(execution_time_ms)
            FROM commands
            WHERE DATE(timestamp) = ?
        ''', (today,))
        
        result = cursor.fetchone()
        conn.close()
        
        total, successful, failed, avg_time = result
        
        return {
            "date": str(today),
            "total_commands": total or 0,
            "successful_commands": successful or 0,
            "failed_commands": failed or 0,
            "success_rate": (successful / total * 100) if total else 0,
            "avg_execution_time_ms": int(avg_time) if avg_time else 0
        }
    
    def get_most_used_apps(self, days: int = 7) -> List[Tuple[str, int]]:
        """Get most frequently used apps in past N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).date()
        
        cursor.execute('''
            SELECT app_opened, COUNT(*) as count
            FROM commands
            WHERE app_opened IS NOT NULL AND DATE(timestamp) >= ?
            GROUP BY app_opened
            ORDER BY count DESC
            LIMIT 10
        ''', (start_date,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_most_used_commands(self, days: int = 7, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most frequently used commands."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).date()
        
        cursor.execute('''
            SELECT command, COUNT(*) as count
            FROM commands
            WHERE DATE(timestamp) >= ?
            GROUP BY command
            ORDER BY count DESC
            LIMIT ?
        ''', (start_date, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_command_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent command history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, timestamp, command, action, success, execution_time_ms, app_opened, file_saved, user_rating
            FROM commands
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_success_rate(self, days: int = 7) -> float:
        """Get success rate for past N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).date()
        
        cursor.execute('''
            SELECT COUNT(*), SUM(CASE WHEN success=1 THEN 1 ELSE 0 END)
            FROM commands
            WHERE DATE(timestamp) >= ?
        ''', (start_date,))
        
        total, successful = cursor.fetchone()
        conn.close()
        
        return (successful / total * 100) if total else 0
    
    def export_analytics(self, output_file: str = None) -> str:
        """Export analytics report to JSON."""
        if not output_file:
            output_file = self.history_dir / f"analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        analytics = {
            "generated": datetime.now().isoformat(),
            "today": self.get_today_stats(),
            "success_rate_7days": self.get_success_rate(7),
            "success_rate_30days": self.get_success_rate(30),
            "most_used_apps_7days": [{"app": app, "count": count} for app, count in self.get_most_used_apps(7)],
            "most_used_commands": [{"command": cmd, "count": count} for cmd, count in self.get_most_used_commands()],
            "recent_history": self.get_command_history(20)
        }
        
        with open(output_file, 'w') as f:
            json.dump(analytics, f, indent=2)
        
        return str(output_file)
    
    def get_dashboard_summary(self) -> str:
        """Get formatted dashboard summary."""
        today = self.get_today_stats()
        most_used = self.get_most_used_apps(7)
        success_rate = self.get_success_rate(7)
        
        dashboard = f"""
╔══════════════════════════════════════════════╗
║         VoiceOS Command Dashboard            ║
╚══════════════════════════════════════════════╝

📊 TODAY'S STATS
  Total Commands:      {today['total_commands']}
  Successful:          {today['successful_commands']}
  Failed:              {today['failed_commands']}
  Success Rate:        {today['success_rate']:.1f}%
  Avg Execution Time:  {today['avg_execution_time_ms']}ms

🚀 MOST USED APPS (7 days)
"""
        for i, (app, count) in enumerate(most_used[:5], 1):
            dashboard += f"  {i}. {app}: {count} times\n"
        
        dashboard += f"\n📈 7-DAY SUCCESS RATE: {success_rate:.1f}%\n"
        
        return dashboard


# Self-test
if __name__ == "__main__":
    history = VoiceHistory()
    
    print("Testing Voice History...")
    
    # Log test commands
    cmd_id = history.log_command(
        "open notepad and write test",
        action="app_action",
        success=True,
        execution_time_ms=1250,
        app_opened="Notepad",
        file_saved="note_20260925_134500.txt"
    )
    print(f"[OK] Logged command ID: {cmd_id}")
    
    # Rate command
    history.rate_command(cmd_id, 5)
    print(f"[OK] Rated command")
    
    # Get stats
    today = history.get_today_stats()
    print(f"[OK] Today's stats: {today['total_commands']} commands, {today['success_rate']:.1f}% success")
    
    # Export analytics
    analytics_file = history.export_analytics()
    print(f"[OK] Exported analytics to {analytics_file}")
    
    # Display dashboard
    print(history.get_dashboard_summary())
    
    print("[OK] Voice history module OK")
