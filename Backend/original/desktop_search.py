"""
Desktop Search & File Organization

Search and organize VoiceOS saved files with intelligent categorization.
Supports full-text search, filtering, and automatic file sorting.

Example:
  search = DesktopSearch()
  results = search.find_files("report", file_type="docx")
  organizer = FileOrganizer()
  organizer.auto_organize()  # Sorts by date, app type, tags
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import shutil


class DesktopSearch:
    """Search and discover saved VoiceOS files."""
    
    def __init__(self, search_dir: str = None):
        """Initialize desktop search."""
        if not search_dir:
            username = os.getenv('USERNAME')
            search_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS"
        
        self.search_dir = Path(search_dir)
        self.index = {}
    
    def find_files(self, query: str, file_type: str = None, 
                   days: int = None, app_filter: str = None) -> List[Path]:
        """
        Search for files using multiple criteria.
        
        Args:
            query: Search term (filename or content snippet)
            file_type: Filter by extension (e.g., "txt", "docx")
            days: Only files from past N days
            app_filter: Only files opened by specific app
        
        Returns:
            List of matching file paths
        """
        results = []
        
        if not self.search_dir.exists():
            return results
        
        start_date = None
        if days:
            start_date = datetime.now() - timedelta(days=days)
        
        for file_path in self.search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Filter by extension
            if file_type and file_path.suffix.lstrip('.').lower() != file_type.lower():
                continue
            
            # Filter by date
            if start_date:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < start_date:
                    continue
            
            # Filter by app (check filename pattern)
            if app_filter:
                if app_filter.lower() not in file_path.stem.lower():
                    continue
            
            # Search in filename
            if query.lower() in file_path.name.lower():
                results.append(file_path)
                continue
            
            # Search in file content (if text file)
            if file_path.suffix in ['.txt', '.md', '.json']:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        if query.lower() in content:
                            results.append(file_path)
                except:
                    pass
        
        return sorted(results, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def find_recent(self, limit: int = 10) -> List[Path]:
        """Get recently modified files."""
        if not self.search_dir.exists():
            return []
        
        files = [f for f in self.search_dir.rglob("*") if f.is_file()]
        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
    
    def find_by_app(self, app_name: str) -> List[Path]:
        """Find all files created by specific app."""
        return self.find_files("", app_filter=app_name)
    
    def find_by_date(self, year: int, month: int = None, day: int = None) -> List[Path]:
        """Find files by date."""
        results = []
        
        if not self.search_dir.exists():
            return results
        
        for file_path in self.search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            if file_date.year != year:
                continue
            if month and file_date.month != month:
                continue
            if day and file_date.day != day:
                continue
            
            results.append(file_path)
        
        return sorted(results, key=lambda x: x.stat().st_mtime, reverse=True)
    
    def get_file_info(self, filepath: Path) -> Dict[str, Any]:
        """Get detailed file information."""
        stat = filepath.stat()
        
        return {
            "path": str(filepath),
            "name": filepath.name,
            "size_bytes": stat.st_size,
            "size_kb": stat.st_size / 1024,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "app": self._extract_app_name(filepath.stem),
            "extension": filepath.suffix
        }
    
    def _extract_app_name(self, filename: str) -> str:
        """Extract app name from filename."""
        # Assumes format: "app_YYYYMMDD_HHMMSS"
        parts = filename.split('_')
        if len(parts) >= 3:
            return parts[0]
        return "unknown"
    
    def create_index(self) -> Dict[str, Any]:
        """Create searchable index of all files."""
        self.index = {
            "created": datetime.now().isoformat(),
            "files": {},
            "apps": {},
            "dates": {}
        }
        
        for file_path in self.search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            file_info = self.get_file_info(file_path)
            self.index["files"][str(file_path)] = file_info
            
            # Index by app
            app = file_info["app"]
            if app not in self.index["apps"]:
                self.index["apps"][app] = []
            self.index["apps"][app].append(str(file_path))
            
            # Index by date
            date = file_info["modified"].split('T')[0]
            if date not in self.index["dates"]:
                self.index["dates"][date] = []
            self.index["dates"][date].append(str(file_path))
        
        return self.index
    
    def export_index(self, filepath: str = None) -> str:
        """Export search index to JSON."""
        if not self.index:
            self.create_index()
        
        if not filepath:
            filepath = self.search_dir / f"search_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.index, f, indent=2)
        
        return str(filepath)


class FileOrganizer:
    """Automatically organize saved files."""
    
    def __init__(self, files_dir: str = None, organize_by: str = "date_app"):
        """
        Initialize file organizer.
        
        Args:
            files_dir: Root directory to organize
            organize_by: Organization strategy
                        - "date_app": YYYY/MM/app_name/
                        - "app_date": app_name/YYYY/MM/
                        - "type": filetype/
                        - "flat": No subfolders
        """
        if not files_dir:
            username = os.getenv('USERNAME')
            files_dir = f"C:\\Users\\{username}\\Documents\\VoiceOS"
        
        self.files_dir = Path(files_dir)
        self.organize_by = organize_by
    
    def auto_organize(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Automatically organize files.
        
        Args:
            dry_run: If True, only show what would be done (don't actually move)
        
        Returns:
            Summary of changes
        """
        summary = {
            "total_files": 0,
            "organized": 0,
            "errors": 0,
            "moves": []
        }
        
        if not self.files_dir.exists():
            return summary
        
        # Get all files (excluding subdirectories)
        files = [f for f in self.files_dir.iterdir() if f.is_file()]
        summary["total_files"] = len(files)
        
        for file_path in files:
            try:
                dest_path = self._get_destination(file_path)
                
                if dest_path != file_path:
                    if not dry_run:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(file_path), str(dest_path))
                    
                    summary["moves"].append({
                        "from": str(file_path),
                        "to": str(dest_path)
                    })
                    summary["organized"] += 1
            except Exception as e:
                summary["errors"] += 1
                print(f"[ERROR] Failed to organize {file_path}: {e}")
        
        return summary
    
    def _get_destination(self, file_path: Path) -> Path:
        """Determine destination path based on organization strategy."""
        stat = file_path.stat()
        file_date = datetime.fromtimestamp(stat.st_mtime)
        year = file_date.strftime("%Y")
        month = file_date.strftime("%m")
        app = self._extract_app_name(file_path.stem)
        file_type = file_path.suffix.lstrip('.')
        
        if self.organize_by == "date_app":
            return self.files_dir / year / month / app / file_path.name
        
        elif self.organize_by == "app_date":
            return self.files_dir / app / year / month / file_path.name
        
        elif self.organize_by == "type":
            return self.files_dir / file_type / file_path.name
        
        else:  # "flat"
            return file_path
    
    def _extract_app_name(self, filename: str) -> str:
        """Extract app name from filename."""
        parts = filename.split('_')
        if len(parts) >= 3:
            return parts[0]
        return "other"
    
    def create_tags(self, filepath: Path, tags: List[str]) -> bool:
        """
        Add tags to a file (stored in .tags file).
        
        Args:
            filepath: File to tag
            tags: List of tags
        
        Returns:
            Success status
        """
        try:
            tags_file = filepath.parent / f".{filepath.stem}.tags"
            with open(tags_file, 'w') as f:
                json.dump({"file": filepath.name, "tags": tags}, f)
            return True
        except Exception:
            return False
    
    def get_tags(self, filepath: Path) -> List[str]:
        """Get tags for a file."""
        try:
            tags_file = filepath.parent / f".{filepath.stem}.tags"
            if tags_file.exists():
                with open(tags_file, 'r') as f:
                    data = json.load(f)
                    return data.get("tags", [])
        except Exception:
            pass
        
        return []
    
    def get_cleanup_suggestions(self, days_old: int = 90) -> List[Path]:
        """Get files that could be archived or deleted."""
        if not self.files_dir.exists():
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        old_files = []
        
        for file_path in self.files_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_date < cutoff_date:
                old_files.append(file_path)
        
        return sorted(old_files, key=lambda x: x.stat().st_mtime)
    
    def archive_files(self, archive_path: str, files: List[Path] = None, 
                     cleanup: bool = False) -> bool:
        """
        Archive files to a separate location.
        
        Args:
            archive_path: Destination archive directory
            files: Specific files to archive (if None, archives old files)
            cleanup: If True, delete original files after archiving
        
        Returns:
            Success status
        """
        try:
            archive_dir = Path(archive_path)
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            if files is None:
                files = self.get_cleanup_suggestions()
            
            for file_path in files:
                dest = archive_dir / file_path.name
                shutil.copy2(str(file_path), str(dest))
                
                if cleanup:
                    file_path.unlink()
            
            return True
        except Exception:
            return False


# Self-test
if __name__ == "__main__":
    print("Testing Desktop Search & File Organization...")
    
    search = DesktopSearch()
    print("[OK] Initialized DesktopSearch")
    
    # Test search (won't find anything without files)
    results = search.find_files("test")
    print(f"[OK] Search found {len(results)} files")
    
    # Test index creation
    index = search.create_index()
    print(f"[OK] Created index with {len(index['files'])} files")
    
    # Test file organizer
    organizer = FileOrganizer(organize_by="date_app")
    print("[OK] Initialized FileOrganizer")
    
    # Test dry-run
    summary = organizer.auto_organize(dry_run=True)
    print(f"[OK] Dry-run would organize {summary['organized']} files")
    
    print("[OK] Desktop search & file organization module OK")
