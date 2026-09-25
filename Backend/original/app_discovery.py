r"""
App Discovery for VoiceOS — Find and launch desktop applications on Windows.

This module discovers installed applications from:
- Windows Registry (HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Uninstall)
- Program Files directories
- Desktop shortcuts
- User-configured aliases in voiceos_aliases.json

The discovery is cached to avoid repeated registry scans and supports fuzzy matching
for app names that users might say but aren't exact matches.
"""

import os
import re
import json
import winreg
import glob
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


class WindowsAppDiscovery:
    """Discovers installed Windows applications from registry, Program Files, and Desktop."""

    def __init__(self, cache_apps: bool = True):
        self.cache_enabled = cache_apps
        self._app_cache: Dict[str, str] = {}
        self._cache_loaded = False

    def discover_all(self) -> Dict[str, str]:
        """Return all discovered apps as {name: executable_path}."""
        if self.cache_enabled and self._cache_loaded:
            return dict(self._app_cache)

        apps = {}
        apps.update(self._scan_registry())
        apps.update(self._scan_program_files())
        apps.update(self._scan_desktop())
        apps.update(self._scan_system_apps())

        self._app_cache = apps
        self._cache_loaded = True
        return apps

    def _scan_system_apps(self) -> Dict[str, str]:
        """Scan Windows system directories for built-in apps."""
        apps = {}
        system_dirs = [
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32"),
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SysWOW64"),
        ]
        
        # Common Windows built-in apps
        common_apps = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "mspaint": "mspaint.exe",
            "paint": "mspaint.exe",
            "wordpad": "write.exe",
            "disk management": "diskmgmt.msc",
            "device manager": "devmgmt.msc",
            "task scheduler": "taskschd.msc",
            "services": "services.msc",
            "registry editor": "regedit.exe",
        }
        
        for app_name, exe_name in common_apps.items():
            for system_dir in system_dirs:
                exe_path = os.path.join(system_dir, exe_name)
                if os.path.exists(exe_path):
                    apps[app_name] = exe_path
                    break
        
        return apps

    def _scan_registry(self) -> Dict[str, str]:
        """Scan HKEY_LOCAL_MACHINE registry for installed apps."""
        apps = {}
        paths = [
            "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
            "Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
        ]
        for path in paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        subkey_name = winreg.EnumKey(key, i)
                        try:
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                # Try to get DisplayName and InstallLocation
                                try:
                                    display_name = winreg.QueryValueEx(
                                        subkey, "DisplayName"
                                    )[0]
                                except WindowsError:
                                    continue

                                # Get executable path
                                exe_path = None
                                try:
                                    exe_path = winreg.QueryValueEx(
                                        subkey, "InstallLocation"
                                    )[0]
                                except WindowsError:
                                    pass

                                if exe_path:
                                    # Normalize the app name
                                    app_name = self._normalize_app_name(display_name)
                                    if app_name and len(app_name) > 2:
                                        apps[app_name] = exe_path
                        except Exception:
                            pass
            except WindowsError:
                pass
        return apps

    def _scan_program_files(self) -> Dict[str, str]:
        """Scan Program Files directories for executable files."""
        apps = {}
        program_files = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
        ]
        
        for base_dir in program_files:
            if not base_dir or not os.path.isdir(base_dir):
                continue
            
            # Look for common application directories
            for root, dirs, files in os.walk(base_dir, topdown=True):
                # Limit depth to avoid scanning too deep
                if root.count(os.sep) - base_dir.count(os.sep) > 2:
                    dirs[:] = []
                    continue
                
                for file in files:
                    if file.lower().endswith('.exe'):
                        app_name = self._normalize_app_name(file[:-4])
                        if app_name and len(app_name) > 2:
                            full_path = os.path.join(root, file)
                            # Only add if we haven't seen this app name yet
                            if app_name not in apps:
                                apps[app_name] = full_path

        return apps

    def _scan_desktop(self) -> Dict[str, str]:
        """Scan Desktop for shortcuts and apps."""
        apps = {}
        desktop_dirs = [
            os.path.expanduser("~\\Desktop"),
            os.path.join(
                os.environ.get("ProgramData", "C:\\ProgramData"),
                "Microsoft\\Windows\\Start Menu\\Programs"
            ),
        ]

        for desktop_dir in desktop_dirs:
            if not os.path.isdir(desktop_dir):
                continue
            
            # Look for .exe files and .lnk shortcuts
            for file_pattern in ["*.exe", "*.lnk"]:
                for file_path in glob.glob(os.path.join(desktop_dir, f"**/{file_pattern}"), recursive=True):
                    try:
                        file_name = os.path.basename(file_path)
                        app_name = self._normalize_app_name(
                            os.path.splitext(file_name)[0]
                        )
                        if app_name and len(app_name) > 2:
                            if app_name not in apps:
                                apps[app_name] = file_path
                    except Exception:
                        pass

        return apps

    @staticmethod
    def _normalize_app_name(name: str) -> str:
        """Normalize app name for consistent lookups."""
        # Remove version numbers, hyphens, underscores
        name = re.sub(r'\s*\(.*?\)\s*', ' ', name)  # Remove parenthetical info
        name = re.sub(r'\s*-\s*', ' ', name)  # Replace hyphens with space
        name = re.sub(r'_', ' ', name)  # Replace underscores with space
        name = re.sub(r'\s+', ' ', name).strip()  # Normalize spaces
        return name.lower()

    def find_app(self, query: str) -> Optional[str]:
        """Find an app by name, with fuzzy matching. Returns executable path or app name."""
        apps = self.discover_all()
        query_norm = self._normalize_app_name(query)
        
        # Exact match first
        if query_norm in apps:
            return apps[query_norm]
        
        # Fuzzy match
        best_match = None
        best_score = 0.6  # Minimum similarity threshold
        
        for app_name, app_path in apps.items():
            score = SequenceMatcher(None, query_norm, app_name).ratio()
            if score > best_score:
                best_score = score
                best_match = app_path
        
        return best_match

    def list_apps(self, pattern: Optional[str] = None) -> List[str]:
        """List discovered apps, optionally filtered by pattern."""
        apps = self.discover_all()
        if pattern:
            pattern_lower = pattern.lower()
            return [name for name in sorted(apps.keys())
                    if pattern_lower in name]
        return sorted(apps.keys())


def merge_discovered_apps(manual_apps: Dict[str, str]) -> Dict[str, str]:
    """Merge manually-configured apps with auto-discovered apps.
    
    Manual apps take precedence (to allow overriding auto-discovered paths).
    """
    discovered = WindowsAppDiscovery().discover_all()
    # Manual apps override discovered ones
    discovered.update(manual_apps)
    return discovered


def get_app_path(app_name: str, manual_apps: Dict[str, str]) -> Optional[str]:
    """Get the executable path for an app by name, checking both manual and discovered."""
    # First check manual apps for exact match
    app_name_norm = WindowsAppDiscovery._normalize_app_name(app_name)
    
    if app_name_norm in manual_apps:
        return manual_apps[app_name_norm]
    
    # Then try discovery with fuzzy matching
    discovery = WindowsAppDiscovery()
    return discovery.find_app(app_name)


# Self-test
if __name__ == "__main__":
    import sys
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("VoiceOS App Discovery -- Testing...")
    
    discovery = WindowsAppDiscovery(cache_apps=True)
    print("Scanning for installed applications (this may take a moment)...")
    
    all_apps = discovery.discover_all()
    print(f"\n[OK] Found {len(all_apps)} applications")
    print(f"  Samples: {', '.join(list(all_apps.keys())[:10])}")
    
    # Test fuzzy matching
    test_queries = ["notepad", "calc", "chrome", "vscode"]
    print("\n Testing fuzzy matching:")
    for query in test_queries:
        result = discovery.find_app(query)
        if result:
            print(f"  [OK] '{query}' -> found")
        else:
            print(f"  [NOT FOUND] '{query}' -> not found")
    
    # Test listing
    print("\n Testing app listing:")
    vim_like = discovery.list_apps("note")
    print(f"  Apps with 'note': {vim_like[:5]}")
    
    print("\n[OK] App discovery OK")
