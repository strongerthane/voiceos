"""
Smart App Plugins

Specialized handlers for common applications like Word, Excel, Outlook, etc.
Enables more sophisticated voice interactions with specific apps.

Example:
  word_plugin = WordPlugin()
  word_plugin.create_document("My Report", template="professional_report")
  word_plugin.insert_table(rows=5, cols=3)
  word_plugin.save_as("C:\\temp\\report.docx")
"""

import subprocess
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime


class AppPlugin(ABC):
    """Base class for app-specific plugins."""
    
    def __init__(self, app_name: str, app_path: str = None):
        """Initialize app plugin."""
        self.app_name = app_name
        self.app_path = app_path
        self.is_open = False
    
    @abstractmethod
    def open(self) -> bool:
        """Open application."""
        pass
    
    @abstractmethod
    def close(self) -> bool:
        """Close application."""
        pass
    
    def execute_command(self, command: str) -> Tuple[bool, str]:
        """Execute PowerShell command."""
        try:
            result = subprocess.run(
                ['powershell', '-Command', command],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout
        except Exception as e:
            return False, str(e)


class WordPlugin(AppPlugin):
    """Microsoft Word automation."""
    
    def __init__(self):
        """Initialize Word plugin."""
        super().__init__("Word")
        self.doc = None
    
    def open(self) -> bool:
        """Open Word application."""
        try:
            import win32com.client
            self.word = win32com.client.Dispatch("Word.Application")
            self.word.Visible = True
            self.is_open = True
            return True
        except ImportError:
            return False
    
    def close(self) -> bool:
        """Close Word application."""
        if self.is_open and self.word:
            self.word.Quit()
            self.is_open = False
            return True
        return False
    
    def create_document(self, title: str = None, template: str = None) -> bool:
        """Create new Word document."""
        if not self.is_open:
            self.open()
        
        try:
            self.doc = self.word.Documents.Add()
            
            if title:
                # Add title
                self.doc.Range().InsertBefore(title + "\n")
                self.doc.Range().Font.Size = 14
                self.doc.Range().Font.Bold = True
            
            return True
        except Exception as e:
            print(f"Error creating document: {e}")
            return False
    
    def insert_text(self, text: str) -> bool:
        """Insert text into document."""
        if not self.doc:
            return False
        
        try:
            self.doc.Range().InsertAfter(text)
            return True
        except Exception:
            return False
    
    def insert_table(self, rows: int, cols: int) -> bool:
        """Insert table into document."""
        if not self.doc:
            return False
        
        try:
            range_obj = self.doc.Range()
            self.doc.Tables.Add(range_obj, rows, cols)
            return True
        except Exception:
            return False
    
    def save_as(self, filepath: str, format: str = "docx") -> bool:
        """Save document."""
        if not self.doc:
            return False
        
        try:
            if format.lower() == "pdf":
                self.doc.SaveAs2(filepath, FileFormat=17)  # wdFormatPDF
            else:
                self.doc.SaveAs2(filepath)
            return True
        except Exception as e:
            print(f"Error saving document: {e}")
            return False


class ExcelPlugin(AppPlugin):
    """Microsoft Excel automation."""
    
    def __init__(self):
        """Initialize Excel plugin."""
        super().__init__("Excel")
        self.workbook = None
        self.sheet = None
    
    def open(self) -> bool:
        """Open Excel application."""
        try:
            import win32com.client
            self.excel = win32com.client.Dispatch("Excel.Application")
            self.excel.Visible = True
            self.is_open = True
            return True
        except ImportError:
            return False
    
    def close(self) -> bool:
        """Close Excel application."""
        if self.is_open and self.excel:
            self.excel.Quit()
            self.is_open = False
            return True
        return False
    
    def create_workbook(self) -> bool:
        """Create new Excel workbook."""
        if not self.is_open:
            self.open()
        
        try:
            self.workbook = self.excel.Workbooks.Add()
            self.sheet = self.workbook.ActiveSheet
            return True
        except Exception as e:
            print(f"Error creating workbook: {e}")
            return False
    
    def set_cell(self, row: int, col: int, value: Any) -> bool:
        """Set cell value."""
        if not self.sheet:
            return False
        
        try:
            self.sheet.Cells(row, col).Value = value
            return True
        except Exception:
            return False
    
    def create_chart(self, chart_type: int = 1) -> bool:
        """Create chart in workbook."""
        if not self.workbook:
            return False
        
        try:
            self.workbook.Charts.Add()
            return True
        except Exception:
            return False
    
    def save_as(self, filepath: str, format: str = "xlsx") -> bool:
        """Save workbook."""
        if not self.workbook:
            return False
        
        try:
            if format.lower() == "csv":
                self.workbook.SaveAs(filepath, FileFormat=6)
            elif format.lower() == "pdf":
                self.workbook.ExportAsFixedFormat(0, filepath)
            else:
                self.workbook.SaveAs(filepath)
            return True
        except Exception as e:
            print(f"Error saving workbook: {e}")
            return False


class OutlookPlugin(AppPlugin):
    """Microsoft Outlook automation."""
    
    def __init__(self):
        """Initialize Outlook plugin."""
        super().__init__("Outlook")
        self.outlook = None
    
    def open(self) -> bool:
        """Open Outlook application."""
        try:
            import win32com.client
            self.outlook = win32com.client.Dispatch("Outlook.Application")
            self.is_open = True
            return True
        except ImportError:
            return False
    
    def close(self) -> bool:
        """Close Outlook application."""
        if self.is_open:
            self.is_open = False
            return True
        return False
    
    def send_email(self, to: str, subject: str, body: str, 
                   cc: str = None, bcc: str = None) -> bool:
        """Send email from Outlook."""
        if not self.is_open:
            self.open()
        
        try:
            mail_item = self.outlook.CreateItem(0)  # olMailItem
            mail_item.To = to
            mail_item.Subject = subject
            mail_item.Body = body
            if cc:
                mail_item.CC = cc
            if bcc:
                mail_item.BCC = bcc
            
            mail_item.Send()
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def create_appointment(self, subject: str, start_time: str, 
                          duration_minutes: int = 60) -> bool:
        """Create calendar appointment."""
        if not self.is_open:
            self.open()
        
        try:
            app_item = self.outlook.CreateItem(1)  # olAppointmentItem
            app_item.Subject = subject
            app_item.Start = start_time
            app_item.Duration = duration_minutes
            app_item.Save()
            return True
        except Exception as e:
            print(f"Error creating appointment: {e}")
            return False


class PowerPointPlugin(AppPlugin):
    """Microsoft PowerPoint automation."""
    
    def __init__(self):
        """Initialize PowerPoint plugin."""
        super().__init__("PowerPoint")
        self.presentation = None
    
    def open(self) -> bool:
        """Open PowerPoint application."""
        try:
            import win32com.client
            self.ppt = win32com.client.Dispatch("PowerPoint.Application")
            self.ppt.Visible = True
            self.is_open = True
            return True
        except ImportError:
            return False
    
    def close(self) -> bool:
        """Close PowerPoint application."""
        if self.is_open and self.ppt:
            self.ppt.Quit()
            self.is_open = False
            return True
        return False
    
    def create_presentation(self) -> bool:
        """Create new presentation."""
        if not self.is_open:
            self.open()
        
        try:
            self.presentation = self.ppt.Presentations.Add()
            return True
        except Exception as e:
            print(f"Error creating presentation: {e}")
            return False
    
    def add_slide(self, title: str, subtitle: str = None) -> bool:
        """Add slide to presentation."""
        if not self.presentation:
            return False
        
        try:
            slide_layout = self.presentation.SlideLayouts(0)  # Title Slide
            slide = self.presentation.Slides.AddSlide(len(self.presentation.Slides) + 1, slide_layout)
            
            slide.Shapes.Title.TextFrame.TextRange.Text = title
            if subtitle:
                slide.Shapes[1].TextFrame.TextRange.Text = subtitle
            
            return True
        except Exception:
            return False
    
    def save_as(self, filepath: str, format: str = "pptx") -> bool:
        """Save presentation."""
        if not self.presentation:
            return False
        
        try:
            if format.lower() == "pdf":
                self.presentation.SaveAs(filepath, 32)  # ppSaveAsPDF
            else:
                self.presentation.SaveAs(filepath)
            return True
        except Exception as e:
            print(f"Error saving presentation: {e}")
            return False


class PluginManager:
    """Manage app plugins."""
    
    def __init__(self):
        """Initialize plugin manager."""
        self.plugins: Dict[str, AppPlugin] = {
            "word": WordPlugin(),
            "excel": ExcelPlugin(),
            "outlook": OutlookPlugin(),
            "powerpoint": PowerPointPlugin(),
        }
    
    def get_plugin(self, app_name: str) -> Optional[AppPlugin]:
        """Get plugin by app name."""
        return self.plugins.get(app_name.lower())
    
    def list_plugins(self) -> List[str]:
        """List available plugins."""
        return list(self.plugins.keys())


# Self-test
if __name__ == "__main__":
    print("Testing Smart App Plugins...")
    
    # Test Word plugin
    word = WordPlugin()
    print(f"[OK] Initialized Word plugin")
    
    # Note: win32com requires full setup, just testing instantiation
    print(f"[OK] Word plugin ready for: create_document, insert_text, insert_table, save_as")
    
    # Test Excel plugin
    excel = ExcelPlugin()
    print(f"[OK] Excel plugin ready for: create_workbook, set_cell, create_chart, save_as")
    
    # Test Outlook plugin
    outlook = OutlookPlugin()
    print(f"[OK] Outlook plugin ready for: send_email, create_appointment")
    
    # Test PowerPoint plugin
    ppt = PowerPointPlugin()
    print(f"[OK] PowerPoint plugin ready for: create_presentation, add_slide, save_as")
    
    # Test plugin manager
    manager = PluginManager()
    print(f"[OK] Available plugins: {manager.list_plugins()}")
    
    print("[OK] Smart app plugins module OK")
