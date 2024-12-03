import sys
import os
import platform
import subprocess
import pygame
import traceback
from collections import defaultdict
import asyncio
from shazamio import Shazam
import nest_asyncio
from PIL import Image, ImageQt
import requests
from io import BytesIO
import webbrowser
import csv
from io import StringIO
from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QFrame, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyle, QFileDialog, QMessageBox,
    QDialog, QToolButton, QMenu, QGridLayout, QSpacerItem, QSizePolicy,
    QTextEdit, QGroupBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QAction, QPalette

# Constants
SUPPORTED_EXTENSIONS = {'.sm', '.ssc'}
SUPPORTED_AUDIO = {'.ogg', '.mp3', '.wav'}
METADATA_FIELDS = ['TITLE', 'SUBTITLE', 'ARTIST', 'GENRE', 'MUSIC']
SUPPORTED_ENCODINGS = ['utf-8-sig', 'utf-8', 'shift-jis', 'latin1', 'cp1252']
COLUMN_WIDTHS = {
    'checkbox': 30,
    'actions': 130,
    'type': 75,
    'parent_dir': 160,
    'title': 250,
    'subtitle': 250,
    'artist': 250,
    'genre': 250,
    'status': 30,
    'commit': 80,
    'id': 0
}
SHAZAM_BUTTON_NORMAL = {
    "text": "Shazam Mode: OFF",
    "style": "QPushButton { background-color: #4a90e2; }"
}
SHAZAM_BUTTON_ACTIVE = {
    "text": "SHAZAM ON!",
    "style": "QPushButton { background-color: lightgreen; }"
}
MODERN_LIGHT_STYLE = """
    QMainWindow, QDialog {
        background-color: #f0f0f0;
    }
    QTableWidget {
        background-color: white;
        alternate-background-color: #f7f7f7;
        selection-background-color: #0078d7;
        selection-color: white;
        gridline-color: #e0e0e0;
    }
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        padding: 5px 15px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #1084e3;
    }
    QPushButton:pressed {
        background-color: #006cc1;
    }
    QPushButton:disabled {
        background-color: #cccccc;
    }
    QPushButton#commitButton {
        background-color: #cccccc;
        color: black;
    }
    QPushButton#commitButton[committed="true"] {
        background-color: lightgreen;
        color: black;
    }
    QPushButton#commitButton:hover {
        background-color: #bbbbbb;
    }
    QPushButton#commitAllButton {
        background-color: #cccccc;
        color: black;
    }
    QPushButton#commitAllButton[hasChanges="true"] {
        background-color: #0078d7;
        color: white;
    }
    QLineEdit {
        padding: 5px;
        border: 1px solid #cccccc;
        border-radius: 4px;
        background-color: white;
    }
    QLineEdit:focus {
        border: 1px solid #0078d7;
    }
    QGroupBox {
        border: 1px solid #cccccc;
        border-radius: 4px;
        margin-top: 1em;
        padding-top: 0.5em;
    }
    QGroupBox::title {
        color: #0078d7;
    }
"""

MODERN_RAINBOW_STYLE = """
    QMainWindow, QDialog {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
            stop:0 #ff8080,
            stop:0.25 #80ff80,
            stop:0.5 #8080ff,
            stop:0.75 #ffff80,
            stop:1 #ff80ff);
    }
    QTableWidget {
        background-color: rgba(255, 255, 255, 0.9);
        alternate-background-color: rgba(255, 255, 255, 0.8);
        selection-background-color: rgba(0, 120, 215, 0.7);
        selection-color: white;
        gridline-color: rgba(0, 0, 0, 0.1);
    }
    QPushButton {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
            stop:0 #ff6b6b,
            stop:0.5 #4ecdc4,
            stop:1 #45b7d1);
        color: white;
        border: none;
        padding: 5px 15px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
            stop:0 #ff8f8f,
            stop:0.5 #6ee7de,
            stop:1 #5dcee8);
    }
    QPushButton#commitButton {
        background: rgba(204, 204, 204, 0.9);
        color: black;
    }
    QPushButton#commitButton[committed="true"] {
        background: rgba(144, 238, 144, 0.9);
        color: black;
    }
    QPushButton#commitButton:hover {
        background: rgba(187, 187, 187, 0.9);
    }
    QPushButton#commitAllButton {
        background: rgba(204, 204, 204, 0.9);
        color: black;
    }
    QPushButton#commitAllButton[hasChanges="true"] {
        background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
            stop:0 #ff6b6b,
            stop:0.5 #4ecdc4,
            stop:1 #45b7d1);
        color: white;
    }
    QLineEdit {
        background-color: rgba(255, 255, 255, 0.9);
        border: 2px solid rgba(255, 255, 255, 0.5);
        border-radius: 4px;
        padding: 5px;
    }
    QGroupBox {
        background-color: rgba(255, 255, 255, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 4px;
        margin-top: 1em;
        padding-top: 0.5em;
    }
    QHeaderView::section {
        background-color: rgba(255, 255, 255, 0.8);
        padding: 5px;
        border: none;
    }
"""

class MetadataUtil:
    @staticmethod
    def read_file_with_encoding(filepath):
        for encoding in SUPPORTED_ENCODINGS:
            try:
                with open(filepath, 'r', encoding=encoding) as file:
                    return file.readlines(), encoding
            except UnicodeDecodeError:
                continue
        return None, None
        
    @staticmethod
    def read_metadata(filepath):
        content, encoding = MetadataUtil.read_file_with_encoding(filepath)
        if not content:
            return {}
            
        metadata = {}
        credits = set()
        
        for line in content:
            if line.startswith('#') and ':' in line:
                key, value = line.strip().split(':', 1)
                key = key[1:]
                value = value.rstrip(';')
                
                if key == 'CREDIT':
                    credits.add(value)
                else:
                    metadata[key] = value
        
        metadata['CREDITS'] = credits
        return metadata
        
    @staticmethod
    def write_metadata(filepath, metadata):
        content, encoding = MetadataUtil.read_file_with_encoding(filepath)
        if not content:
            return False
            
        # Track if we've found and updated each field
        updated_fields = {key: False for key in metadata}
        title_line_index = None
        
        # First pass: update existing fields and find TITLE line
        for i, line in enumerate(content):
            if line.startswith('#TITLE:'):
                title_line_index = i
            for key, value in metadata.items():
                if line.startswith(f'#{key}:'):
                    content[i] = f'#{key}:{value};\n'
                    updated_fields[key] = True
        
        # Second pass: add missing fields after TITLE
        if title_line_index is not None:
            # Insert missing fields after TITLE in reverse order to maintain order
            for key, value in reversed(metadata.items()):
                if not updated_fields[key]:
                    content.insert(title_line_index + 1, f'#{key}:{value};\n')
        
        try:
            with open(filepath, 'w', encoding=encoding) as file:
                file.writelines(content)
            return True
        except Exception:
            return False
            
class MetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.console_window = ConsoleWindow(self)  
        sys.stdout = self.console_window  # redirect stdout
        sys.stderr = self.console_window  #redirect stderr
        print("=== Console System Initialized ===")  # Test print
        print("Closing this window will close the application")  # Test print
        print("Currently a memory leak when using the noconsole option")  # Test print

        self.rainbow_mode = False
        self.setStyleSheet(MODERN_LIGHT_STYLE)
        self.setWindowTitle("StepMania Metadata Editor")
        self.setFixedSize(1600, 800)
        
        # Initialize all attributes first
        self.current_playing = None
        self.selected_entries = []
        self.file_entries = []
        self.selected_directories = set()
        self.bulk_edit_enabled = False
        self.shazam_mode = False
        self.audio_enabled = False
        self.temp_widgets = []
        self.search_credits_button = None
        self.search_frame = None
        self.table = None
        self.clear_button = None
        self.bulk_edit_btn = None
        self.shazam_btn = None
        self.commit_all_button = None
        self.search_box = None
        
        # Initialize pygame for audio
        try:
            pygame.mixer.init()
            self.audio_enabled = True
        except Exception as e:
            print(f"Warning: Audio disabled - {str(e)}")
            self.audio_enabled = False

        # Initialize sort tracking
        self.sort_reverse = {
            'pack': False,
            'title': False,
            'subtitle': False,
            'artist': False,
            'genre': False
        }
        
        # Setup UI components
        self.setup_ui()
        
        # Setup bulk edit controls after main UI
        self.setup_bulk_edit_controls()
        
        # Initialize Shazam-related attributes safely
        try:
            nest_asyncio.apply()
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.shazam = Shazam()
        except Exception as e:
            print(f"Warning: Shazam initialization failed - {str(e)}")
            self.loop = None
            self.shazam = None
        
        # Add at the start of __init__
        self.entry_counter = 1  # Start at 1 for more human-readable IDs

    def setup_ui(self):
        """Setup the main UI components"""
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        toolbar = QHBoxLayout()
        
        # Left side buttons
        left_buttons = QHBoxLayout()
        
        # Add directory picker
        self.pick_dir_btn = QPushButton("Pick Directory")
        self.pick_dir_btn.clicked.connect(self.pick_directory)
        left_buttons.addWidget(self.pick_dir_btn)
        
        # Add bulk edit toggle with consistent name
        self.bulk_edit_btn = QPushButton("Bulk Edit: OFF")
        self.bulk_edit_btn.clicked.connect(self.toggle_bulk_edit)
        left_buttons.addWidget(self.bulk_edit_btn)
        
        # Add search by credits button
        self.search_credits_button = QPushButton("Search by Credits")
        self.search_credits_button.clicked.connect(self.show_credit_search)
        left_buttons.addWidget(self.search_credits_button)
        
        toolbar.addLayout(left_buttons)
        
        # Add search box with clear directories button in the middle
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.apply_search_filter)
        search_layout.addWidget(self.search_box)
        
        # Modify clear button to be a clear directories button
        self.clear_button = QPushButton("Clear All Directories")
        self.clear_button.clicked.connect(self.clear_directories)
        self.clear_button.hide()  # Initially hidden until directories are loaded
        search_layout.addWidget(self.clear_button)
        
        toolbar.addLayout(search_layout)
        
        # Add stretch to push right-side buttons to the right
        toolbar.addStretch()
        
        # Right side buttons
        right_buttons = QHBoxLayout()
        
        # Add commit all button on the right
        self.commit_all_button = QPushButton("No Changes")
        self.commit_all_button.setObjectName("commitAllButton")
        self.commit_all_button.setEnabled(False)
        self.commit_all_button.clicked.connect(self.commit_all_changes)
        right_buttons.addWidget(self.commit_all_button)
        
        # Add Shazam toggle on the right
        self.shazam_btn = QPushButton(SHAZAM_BUTTON_NORMAL["text"])
        self.shazam_btn.setStyleSheet(SHAZAM_BUTTON_NORMAL["style"])
        self.shazam_btn.clicked.connect(self.toggle_shazam_mode)
        right_buttons.addWidget(self.shazam_btn)
        
        toolbar.addLayout(right_buttons)
        
        self.main_layout.addLayout(toolbar)
        
        # Initialize table widget before setup
        self.table = QTableWidget()
        
        # Setup table
        self.setup_table()
        self.main_layout.addWidget(self.table)
        
        # Create GitHub and help buttons frame
        github_frame = QFrame()
        github_layout = QHBoxLayout(github_frame)
        github_layout.setContentsMargins(0, 0, 0, 0)
        
        help_button = QPushButton("❓ Help")
        help_button.clicked.connect(self.show_help_dialog)
        github_layout.addWidget(help_button)
        
        github_button = QPushButton("\u25D3 GitHub")
        github_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/therzog92/SM_Metadata_Editor")
        )
        github_layout.addWidget(github_button)
        
        # Add settings button next to help button
        settings_btn = QPushButton("⚙️")
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.show_settings_dialog)
        github_layout.addWidget(settings_btn)
        
        self.main_layout.addWidget(github_frame, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Add display count indicator below toolbar
        self.display_count_frame = QFrame()
        count_layout = QHBoxLayout(self.display_count_frame)
        count_layout.setContentsMargins(4, 0, 4, 0)
        
        self.display_count_label = QLabel()
        self.display_count_label.setStyleSheet("color: #666;")  # Subtle gray color
        count_layout.addWidget(self.display_count_label)
        count_layout.addStretch()
        
        self.main_layout.addWidget(self.display_count_frame)
        self.display_count_frame.hide()  # Hidden by default
        
        # Set application-wide stylesheet for modern scrollbars
        self.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;            /* Reduced from 14px */
                margin: 0px 0px 0px 0px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:vertical {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:0.5 #357abd, stop:1 #2c5a8c);
                min-height: 30px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:vertical:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5da1e9, stop:0.5 #4a90e2, stop:1 #357abd);
            }

            QScrollBar::add-line:vertical {
                height: 0px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }

            QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }

            QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                height: 10px;           /* Reduced from 14px */
                margin: 0px 0px 0px 0px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:horizontal {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2, stop:0.5 #357abd, stop:1 #2c5a8c);
                min-width: 30px;
                border-radius: 5px;     /* Reduced from 7px */
            }

            QScrollBar::handle:horizontal:hover {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5da1e9, stop:0.5 #4a90e2, stop:1 #357abd);
            }

            QScrollBar::add-line:horizontal {
                width: 0px;
                subcontrol-position: right;
                subcontrol-origin: margin;
            }

            QScrollBar::sub-line:horizontal {
                width: 0px;
                subcontrol-position: left;
                subcontrol-origin: margin;
            }
        """)

    def setup_bulk_edit_controls(self):
        """Set up bulk edit controls"""
        self.bulk_edit_controls = QFrame()
        bulk_layout = QHBoxLayout(self.bulk_edit_controls)
        
        # Create bulk edit fields
        self.bulk_fields = {}
        for field in ['subtitle', 'artist', 'genre']:
            label = QLabel(field.capitalize())
            edit = QLineEdit()
            bulk_layout.addWidget(label)
            bulk_layout.addWidget(edit)
            self.bulk_fields[field] = edit
        
        apply_button = QPushButton("Apply to Selected")
        apply_button.clicked.connect(self.apply_bulk_edit)
        bulk_layout.addWidget(apply_button)
        
        # Add to main layout and hide initially
        self.main_layout.addWidget(self.bulk_edit_controls)
        self.bulk_edit_controls.hide()
        
    def setup_table(self):
        """Set up the main table widget"""
        self.table = QTableWidget()
        self.table.setColumnCount(11)  # Add one more column for ID
        
        # Define column indices
        self.COL_CHECKBOX = 0
        self.COL_ACTIONS = 1
        self.COL_TYPE = 2
        self.COL_PACK = 3
        self.COL_TITLE = 4
        self.COL_SUBTITLE = 5
        self.COL_ARTIST = 6
        self.COL_GENRE = 7
        self.COL_STATUS = 8
        self.COL_COMMIT = 9
        self.COL_ID = 10
        
        # Set headers
        headers = ['', 'Actions', 'Type', 'Pack', 'Title', 'Subtitle', 'Artist', 'Genre', 'Status', 'Commit', 'ID']
        self.table.setHorizontalHeaderLabels(headers)
        
        # Set edit triggers for single-click editing
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged |
            QTableWidget.EditTrigger.DoubleClicked |
            QTableWidget.EditTrigger.EditKeyPressed |
            QTableWidget.EditTrigger.AnyKeyPressed
        )
        
        # Set selection behavior
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        
        # Set lighter selection color
        self.table.setStyleSheet("""
            QTableWidget {
                selection-background-color: rgba(53, 122, 189, 0.3);
            }
        """)
        
        # Set column widths and make actions column fixed
        for col, width in enumerate(COLUMN_WIDTHS.values()):
            self.table.setColumnWidth(col, width)
            if col == 1:  # Actions column
                self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            # Make non-editable columns read-only
            if col not in [4, 5, 6, 7]:  # Not Title, Subtitle, Artist, or Genre
                self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        
        # Connect signals
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_table)
        







    def write_debug(self, message):
        """Write debug information to the app console"""
        if hasattr(self, 'console_window'):
            self.console_window.console_output.append(message)
            self.console_window.console_output.repaint()
            # Only print to standard console if not already redirected
            if sys.stdout != self.console_window:
                print(message)

    def write_operation_debug(self, operation_name, message, error=None):
        """Write operation-specific debug information"""
        debug_msg = f"Operation [{operation_name}]: {message}"
        if error:
            debug_msg += f" - Error: {error}"

        if hasattr(self, 'console_window'):
            self.console_window.console_output.append(debug_msg)
            self.console_window.console_output.repaint()
            # Only print to standard console if not already redirected
            if sys.stdout != self.console_window:
                print(debug_msg)

    def create_file_entry_with_type(self, filepaths, file_type, parent_dir, title, subtitle, artist, genre, music_file):
        """Create a file entry with specified type in the table"""
        try:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Create unique ID and increment counter
            entry_id = str(self.entry_counter)
            self.entry_counter += 1
            
            # Add empty checkbox column item and make it non-editable
            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(checkbox_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_CHECKBOX, checkbox_item)
            
            # Store entry data with ID
            entry_data = {
                'id': entry_id,
                'filepaths': filepaths,
                'original_values': {
                    'title': title,
                    'subtitle': subtitle,
                    'artist': artist,
                    'genre': genre
                }
            }
            self.file_entries.append(entry_data)
            
            # Add ID to table
            id_item = QTableWidgetItem(entry_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.COL_ID, id_item)
            
            # Create action buttons with ID reference
            action_widget = self.create_action_buttons(row, filepaths, music_file, entry_id)
            self.table.setCellWidget(row, self.COL_ACTIONS, action_widget)
            
            # Set file type and parent directory (read-only)
            type_item = QTableWidgetItem(file_type)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, type_item)
            
            pack_item = QTableWidgetItem(parent_dir)
            pack_item.setFlags(pack_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, pack_item)

            # Create editable metadata fields
            metadata_fields = {
                4: ('title', title),
                5: ('subtitle', subtitle),
                6: ('artist', artist),
                7: ('genre', genre)
            }

            for col, (field, value) in metadata_fields.items():
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

            # Add empty status and commit columns (read-only)
            status_item = QTableWidgetItem("")
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 8, status_item)
            
            commit_item = QTableWidgetItem("")
            commit_item.setFlags(commit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 9, commit_item)

            return entry_data

        except Exception as e:
            print(f"Error in create_file_entry_with_type: {str(e)}")
            traceback.print_exc()
            return None

    def on_entry_change(self, row, filepath, field):
        """Handle changes to table entries"""
        try:
            # Map field names to column indices
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7,
                'subtitle': 5
            }
            
            # Get column index for the field
            col_index = col_map.get(field)
            if col_index is None:
                print(f"Warning: Invalid field name: {field}")
                return
            
            # Get the item from the table
            item = self.table.item(row, col_index)
            if not item:
                print(f"Warning: No item found at row {row}, column {col_index}")
                return
            
            # Update status column
            status_item = QTableWidgetItem("⚠")
            status_item.setToolTip("Unsaved changes")
            self.table.setItem(row, 8, status_item)  # Status column
            
        except Exception as e:
            print(f"Error in on_entry_change: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_commit_all_button(self):
        """Update the commit all button state"""
        try:
            # Count rows with unsaved changes by checking both item and widget status
            uncommitted = 0
            for row in range(self.table.rowCount()):
                status_widget = self.table.cellWidget(row, 8)
                status_item = self.table.item(row, 8)
                
                has_warning = False
                if status_widget and isinstance(status_widget, QWidget):
                    label = status_widget.findChild(QLabel)
                    if label and label.text() == "⚠":
                        has_warning = True
                elif status_item and status_item.text() == "⚠":
                    has_warning = True
                    
                if has_warning:
                    uncommitted += 1
            
            if uncommitted > 0:
                self.commit_all_button.setText(f"Commit Changes ({uncommitted})")
                self.commit_all_button.setEnabled(True)
            else:
                self.commit_all_button.setText("No Changes")
                self.commit_all_button.setEnabled(False)
                
        except Exception as e:
            print(f"Error updating commit button: {str(e)}")
            import traceback
            traceback.print_exc()

    def commit_changes(self, row, filepaths):
        """Commit changes for a single row"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return False
                
            # Find the entry using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return False

            # Collect changes
            changes = {}
            for field, col in [
                ('title', self.COL_TITLE),
                ('subtitle', self.COL_SUBTITLE),
                ('artist', self.COL_ARTIST),
                ('genre', self.COL_GENRE)
            ]:
                item = self.table.item(row, col)
                if item and item.text() != entry['original_values'][field]:
                    changes[field.upper()] = item.text()

            if changes:
                # Write changes to all files
                success = True
                for filepath in filepaths:
                    if not MetadataUtil.write_metadata(filepath, changes):
                        success = False
                        break

                if success:
                    # Update original values
                    for field, value in changes.items():
                        entry['original_values'][field.lower()] = value

                    # Clear status and commit columns
                    self.table.removeCellWidget(row, 8)  # Status column
                    self.table.removeCellWidget(row, 9)  # Commit column
                    self.table.setItem(row, 9, QTableWidgetItem(""))
                    self.table.setItem(row, 8, QTableWidgetItem("✓"))

                    # Update commit all button
                    self.update_commit_all_button()
                    return True

            return False

        except Exception as e:
            print(f"Error in commit_changes: {str(e)}")
            traceback.print_exc()
            return False

    def commit_all_changes(self):
        """Commit all pending changes"""
        try:
            committed_count = 0
            total_rows = self.table.rowCount()
            
            for row in range(total_rows):
                # Get the ID from the current row
                id_item = self.table.item(row, self.COL_ID)
                if not id_item:
                    continue
                    
                # Find the entry using ID
                entry_id = id_item.text()
                entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
                if not entry:
                    continue

                # Check if row has uncommitted changes
                has_changes = False
                for field, col in [
                    ('title', self.COL_TITLE),
                    ('subtitle', self.COL_SUBTITLE),
                    ('artist', self.COL_ARTIST),
                    ('genre', self.COL_GENRE)
                ]:
                    item = self.table.item(row, col)
                    if item and item.text() != entry['original_values'][field]:
                        has_changes = True
                        break

                if has_changes:
                    if self.commit_changes(row, entry['filepaths']):
                        committed_count += 1

            if committed_count > 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Successfully committed changes to {committed_count} files."
                )
            else:
                QMessageBox.information(
                    self,
                    "No Changes",
                    "No changes were found to commit."
                )

        except Exception as e:
            print(f"Error in commit_all_changes: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "Error",
                f"An error occurred while committing changes: {str(e)}"
            )

    async def do_shazam_analysis(self, file_path, row):
        """Perform Shazam analysis"""
        if self.shazam_mode and row != -1:
            print("Starting Shazam analysis...")
            try:
                result = await self.analyze_single_file(file_path)
                if result and 'track' in result:
                    track = result['track']
                    shazam_data = {
                        'title': track.get('title', ''),
                        'artist': track.get('subtitle', ''),
                        'genre': track.get('genres', {}).get('primary', ''),
                        'images': {'coverart': track['share']['image']} if 'share' in track and 'image' in track['share'] else {}
                    }
                    self.show_shazam_results(row, shazam_data)
                else:
                    print("No Shazam results found")
            except Exception as e:
                print(f"Shazam analysis error: {str(e)}")
                import traceback
                traceback.print_exc()

    def play_audio(self, music_path, play_btn, entry_id):
        """Play audio file with fallback logic"""
        try:
            # Handle current playing button
            try:
                if self.current_playing:
                    pygame.mixer.music.stop()
                    self.current_playing.setText("▶")
                    if self.current_playing == play_btn:
                        self.current_playing = None
                        return
            except RuntimeError:
                self.current_playing = None
            except Exception as e:
                print(f"Error handling current playing button: {str(e)}")
                self.current_playing = None

            directory = os.path.dirname(music_path)
            base_filename = os.path.basename(music_path)
            found_playable = False
            actual_path = None

            # Priority 1: Exact filepath
            if os.path.exists(music_path):
                try:
                    pygame.mixer.music.load(music_path)
                    found_playable = True
                    actual_path = music_path
                    print(f"Using exact file: {music_path}")
                except Exception as e:
                    print(f"Failed to load exact file: {str(e)}")

            # Priority 2: Using filename as mask
            if not found_playable and base_filename:
                mask_term = os.path.splitext(base_filename)[0]
                for file in os.listdir(directory):
                    if mask_term in file and file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                        try:
                            test_path = os.path.join(directory, file)
                            pygame.mixer.music.load(test_path)
                            found_playable = True
                            actual_path = test_path
                            print(f"Using masked file: {test_path}")
                            break
                        except Exception as e:
                            print(f"Failed to load masked file {file}: {str(e)}")

            # Priority 3: Any supported audio file (smallest one)
            if not found_playable:
                audio_files = []
                for file in os.listdir(directory):
                    if file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                        file_path = os.path.join(directory, file)
                        try:
                            size = os.path.getsize(file_path)
                            audio_files.append((size, file_path))
                        except Exception as e:
                            print(f"Failed to get size for {file}: {str(e)}")

                if audio_files:
                    # Sort by size, then by path (for same-size files)
                    audio_files.sort(key=lambda x: (x[0], x[1]))
                    try:
                        pygame.mixer.music.load(audio_files[0][1])
                        found_playable = True
                        actual_path = audio_files[0][1]
                        print(f"Using smallest audio file: {actual_path} ({audio_files[0][0]} bytes)")
                    except Exception as e:
                        print(f"Failed to load smallest audio file: {str(e)}")

            if found_playable and actual_path:
                pygame.mixer.music.play()
                play_btn.setText("⏹")
                play_btn.setEnabled(True)
                self.current_playing = play_btn
                
                # If Shazam mode is active, analyze the file
                if self.shazam_mode:
                    current_row = self.find_row_by_id(entry_id)
                    if current_row != -1:
                        self.run_shazam_analysis(actual_path, current_row)
            else:
                print(f"No playable audio found in {directory}")
                play_btn.setText("\U0001F507")  # Unicode for speaker with cancellation slash
                play_btn.setEnabled(False)
                play_btn.setToolTip("No audio file found")

        except Exception as e:
            print(f"Error in play_audio: {str(e)}")
            traceback.print_exc()

    def run_shazam_analysis(self, audio_path, row):
        """Run Shazam analysis on an audio file"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                print("Debug: No ID item found for row", row)
                return
                
            entry_id = id_item.text()
            print(f"Debug: Running Shazam analysis for ID {entry_id} at row {row}")
            
            # Find current row for this ID (in case table was sorted)
            current_row = self.find_row_by_id(entry_id)
            if current_row == -1:
                print(f"Debug: Could not find row for ID {entry_id}")
                return
            
            print(f"Debug: Current row for ID {entry_id} is {current_row}")
            
            # Run Shazam analysis
            try:
                result = self.loop.run_until_complete(self.shazam.recognize(audio_path))
                print(f"Debug: Shazam result: {result}")
                
                if result and 'track' in result:
                    track = result['track']
                    shazam_data = {
                        'title': track.get('title', ''),
                        'artist': track.get('subtitle', ''),
                        'genre': track.get('genres', {}).get('primary', ''),
                        'images': {'coverart': track['share']['image']} if 'share' in track and 'image' in track['share'] else {}
                    }
                    print(f"Debug: Processed Shazam data: {shazam_data}")
                    self.show_shazam_results(current_row, shazam_data)  # Use current_row here
                else:
                    print("Debug: No Shazam results found")
                
            except Exception as e:
                print(f"Debug: Error in Shazam analysis: {str(e)}")
                traceback.print_exc()
                
        except Exception as e:
            print(f"Error in run_shazam_analysis: {str(e)}")
            traceback.print_exc()

    def open_file_location(self, directory):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(directory)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.run(['open', directory])
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Error opening directory {directory}: {str(e)}"
            )

    async def analyze_single_file(self, file_path):
        """Analyze a single file with Shazam"""
        try:
            shazam = Shazam()
            return await shazam.recognize(file_path)  # Updated from recognize_song
        except Exception as e:
            print(f"Error in Shazam analysis: {str(e)}")
            traceback.print_exc()
            return None
    
    def pick_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            try:
                # Find all SM/SSC files and their parent packs
                packs = set()
                sm_files_found = False
                
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.endswith(tuple(SUPPORTED_EXTENSIONS)):
                            sm_files_found = True
                            # Get the song directory and its parent (pack directory)
                            song_dir = os.path.dirname(os.path.join(root, file))
                            pack_dir = os.path.dirname(song_dir)
                            pack_name = os.path.basename(pack_dir)
                            
                            # Add to packs regardless of directory level
                            if pack_name:
                                packs.add((pack_name, pack_dir))
                
                if packs:
                    # Show pack selector dialog
                    dialog = PackSelectorDialog(self, {name for name, _ in packs})
                    dialog.setModal(True)
                    
                    result = dialog.exec()
                    
                    if result == QDialog.DialogCode.Accepted:
                        selected_packs = dialog.selected_packs
                        self.load_selected_packs(
                            directory,
                            {path for name, path in packs if name in selected_packs}
                        )
                elif sm_files_found:
                    # If no packs found but SM files exist, treat selected directory as a pack
                    self.load_selected_packs(os.path.dirname(directory), {directory})
                else:
                    QMessageBox.information(
                        self,
                        "No Songs Found",
                        "No StepMania files (.sm/.ssc) were found in the selected directory."
                    )
                    
            except Exception as e:
                print(f"Error in pick_directory: {str(e)}")
                import traceback
                traceback.print_exc()
                QMessageBox.warning(
                    self,
                    "Error",
                    f"An error occurred while loading directory: {str(e)}"
                )

    def load_selected_packs(self, base_directory, selected_pack_paths):
        """Load selected packs with proper error handling"""
        progress = None
        try:
            # Get unique pack names of existing directories
            existing_pack_names = {os.path.basename(dir_path) for dir_path in self.selected_directories}
            
            # Filter out packs that are already loaded (by pack name)
            new_pack_paths = {
                path for path in selected_pack_paths 
                if os.path.basename(path) not in existing_pack_names
            }
            
            if not new_pack_paths:
                QMessageBox.information(
                    self,
                    "Already Loaded",
                    "All selected packs are already loaded."
                )
                return
                
            # Get current table row count
            existing_rows = self.table.rowCount()
            
            # Create progress dialog with better styling
            progress = QMessageBox(self)
            progress.setWindowTitle("Loading")
            if existing_rows > 0:
                progress.setText(f"Reloading {existing_rows} existing songs, loading new songs...")
            else:
                progress.setText("Loading selected packs...")
            progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress.setStyleSheet("""
                QMessageBox {
                    min-width: 300px;
                    min-height: 100px;
                }
            """)
            progress.show()
            QApplication.processEvents()
            
            # Add the new pack paths to existing ones
            self.selected_directories.update(new_pack_paths)
            
            # Clear existing table but preserve file_entries
            old_entries = self.file_entries.copy()
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Track loaded songs
            loaded_songs = 0
            
            # Modify load_files_from_all_directories to update progress
            def update_progress():
                nonlocal loaded_songs
                loaded_songs += 1
                if existing_rows > 0:
                    progress.setText(f"Reloading {existing_rows} existing songs... ({loaded_songs} new songs processed)")
                else:
                    progress.setText(f"Loading songs... ({loaded_songs} songs processed)")
                QApplication.processEvents()
            
            # Pass the progress callback to load_files_from_all_directories
            self.load_files_from_all_directories(update_progress)
            
        except Exception as e:
            print(f"Error loading packs: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "Load Error",
                f"An error occurred while loading packs: {str(e)}"
            )
        finally:
            # Ensure progress dialog is properly cleaned up
            if progress:
                try:
                    progress.close()
                    progress.deleteLater()
                    QApplication.processEvents()
                except Exception as e:
                    print(f"Error cleaning up progress dialog: {str(e)}")

    def load_files_from_all_directories(self, progress_callback=None):
        """Load all StepMania files from selected directories"""
        try:
            self.table.setSortingEnabled(False)
            
            # Process existing table in chunks
            if self.table.rowCount() > 0:
                chunk_size = 100
                for i in range(0, self.table.rowCount(), chunk_size):
                    end = min(i + chunk_size, self.table.rowCount())
                    for j in range(i, end):
                        self.table.removeRow(i)
                    QApplication.processEvents()
            
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Show UI elements
            for widget in [self.clear_button, self.bulk_edit_btn, 
                          self.search_credits_button, self.search_frame]:
                if widget and hasattr(widget, 'show'):
                    widget.show()
            
            # Process files by directory
            files_by_dir = defaultdict(list)
            
            # Find all SM/SSC files in selected directories
            for pack_dir in self.selected_directories:
                for song_dir in next(os.walk(pack_dir))[1]:
                    full_song_dir = os.path.join(pack_dir, song_dir)
                    
                    # Get all files in directory
                    dir_files = os.listdir(full_song_dir)
                    
                    # Group files by base name (case insensitive)
                    grouped_files = {}
                    for file in dir_files:
                        if file.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                            base_name = os.path.splitext(file)[0].lower()
                            if base_name not in grouped_files:
                                grouped_files[base_name] = {'sm': None, 'ssc': None}
                            
                            full_path = os.path.join(full_song_dir, file)
                            if file.lower().endswith('.sm'):
                                grouped_files[base_name]['sm'] = full_path
                            elif file.lower().endswith('.ssc'):
                                grouped_files[base_name]['ssc'] = full_path
                    
                    # Process each group of files
                    for base_name, files in grouped_files.items():
                        sm_path = files['sm']
                        ssc_path = files['ssc']
                        
                        if ssc_path:  # SSC exists
                            ssc_metadata = MetadataUtil.read_metadata(ssc_path)
                            if sm_path:  # Both exist
                                files_by_dir[full_song_dir].append({
                                    'primary_file': ssc_path,
                                    'secondary_file': sm_path,
                                    'metadata': ssc_metadata,
                                    'type': 'sm+ssc'
                                })
                            else:  # SSC only
                                files_by_dir[full_song_dir].append({
                                    'primary_file': ssc_path,
                                    'metadata': ssc_metadata,
                                    'type': 'ssc'
                                })
                        elif sm_path:  # SM only
                            sm_metadata = MetadataUtil.read_metadata(sm_path)
                            files_by_dir[full_song_dir].append({
                                'primary_file': sm_path,
                                'metadata': sm_metadata,
                                'type': 'sm'
                            })
                            
            # Add files to table in chunks
            chunk_size = 50
            for directory, files in files_by_dir.items():
                for i in range(0, len(files), chunk_size):
                    chunk = files[i:i + chunk_size]
                    for file_info in chunk:
                        try:
                            metadata = file_info['metadata']
                            filepaths = [file_info['primary_file']]
                            if 'secondary_file' in file_info:
                                filepaths.append(file_info['secondary_file'])
                            
                            self.create_file_entry_with_type(
                                filepaths=filepaths,
                                file_type=file_info['type'],
                                parent_dir=os.path.basename(os.path.dirname(directory)),
                                title=metadata.get('TITLE', '').strip(),
                                subtitle=metadata.get('SUBTITLE', '').strip(),
                                artist=metadata.get('ARTIST', '').strip(),
                                genre=metadata.get('GENRE', '').strip(),
                                music_file=metadata.get('MUSIC', '')
                            )
                            
                            if progress_callback:
                                progress_callback()
                        except Exception as e:
                            print(f"Error creating file entry: {e}")
                            continue
                    QApplication.processEvents()
            
            self.table.setSortingEnabled(True)
            total_count = len(self.file_entries)
            self.update_display_count(total_count, total_count)
            
        except Exception as e:
            print(f"Error loading files: {e}")
            traceback.print_exc()

    def apply_search_filter(self):
        """Apply search filter to table entries"""
        search_text = self.search_box.text().lower()
        shown_count = 0
        total_count = len(self.file_entries)
        
        # If search is empty, show all rows and update count
        if not search_text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            self.update_display_count(total_count, total_count)
            return
        
        # For each row in the table
        for row in range(self.table.rowCount()):
            # Get searchable text from table items
            searchable_fields = []
            
            # Parent directory (Pack) - column 3
            pack_item = self.table.item(row, 3)
            if pack_item:
                searchable_fields.append(pack_item.text())
                
            # Title - column 4
            title_item = self.table.item(row, 4)
            if title_item:
                searchable_fields.append(title_item.text())
                
            # Subtitle - column 5
            subtitle_item = self.table.item(row, 5)
            if subtitle_item:
                searchable_fields.append(subtitle_item.text())
                
            # Artist - column 6
            artist_item = self.table.item(row, 6)
            if artist_item:
                searchable_fields.append(artist_item.text())
                
            # Genre - column 7
            genre_item = self.table.item(row, 7)
            if genre_item:
                searchable_fields.append(genre_item.text())
            
            # Combine all fields and search
            searchable_text = ' '.join(searchable_fields).lower()
            hide_row = search_text not in searchable_text
            
            self.table.setRowHidden(row, hide_row)
            if not hide_row:
                shown_count += 1
        
        # Update display count after filtering
        self.update_display_count(shown_count, total_count)

    def get_column_index(self, field):
        """Helper method to get column index for a field"""
        column_map = {
            'title': 4,
            'subtitle': 5,
            'artist': 6,
            'genre': 7
        }
        return column_map.get(field, 0)
    
    def toggle_bulk_edit(self):
        """Toggle bulk edit mode"""
        self.bulk_edit_enabled = not self.bulk_edit_enabled
        
        if self.bulk_edit_enabled:
            self.bulk_edit_btn.setText("Exit Bulk Edit")
            self.bulk_edit_controls.show()
            # Disable direct editing of cells during bulk edit
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        else:
            self.bulk_edit_btn.setText("Bulk Edit: OFF")
            self.bulk_edit_controls.hide()
            # Re-enable direct editing
            self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
            self.table.clearSelection()

    def apply_bulk_edit(self):
        """Apply bulk edits to selected rows"""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        
        if not selected_rows:
            return
        
        # Get values from bulk edit fields
        new_values = {
            'subtitle': self.bulk_fields['subtitle'].text(),
            'artist': self.bulk_fields['artist'].text(),
            'genre': self.bulk_fields['genre'].text()
        }
        
        # Apply to each selected row
        for row in selected_rows:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                continue
            
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            
            if entry:
                for field, value in new_values.items():
                    if value:  # Only update if value is not empty
                        col_index = self.get_column_index(field)
                        item = QTableWidgetItem(value)
                        self.table.setItem(row, col_index, item)
                        self.on_entry_change(row, entry['filepaths'], field)

    def toggle_shazam_mode(self):
        """Toggle Shazam mode on/off"""
        self.shazam_mode = not self.shazam_mode
        
        if self.shazam_mode:
            # Show information popup
            msg = QMessageBox(self)
            msg.setWindowTitle("Shazam Mode Activated!")
            msg.setText(f"🎵 Shazam Mode is now active! Here's how it works:")
            msg.setInformativeText("""
                1. Press ▶ on any song to analyze with Shazam
                                   
                2. Results will appear as follows:
                   • Matching fields will turn green
                   • Different values will show as blue suggestion buttons
                   • A "Compare Artwork" button (camera icon)
                     will appear if new jacket artwork is found

                3. To use suggestions:
                   • Left-click to accept a new value
                   • Right-click to keep the original value
                    Click "Compare Artwork" to compare and 
                     choose between current and new jacket artwork

                Remember: No changes are permanent until you click 'Commit'! :)
                """)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setIcon(QMessageBox.Icon.NoIcon)
            msg.setStyleSheet("""
                QMessageBox {
                    min-width: 300px;
                    min-height: 100px;
                }
            """)
            
            # Force the size
            msg.show()
            msg.setFixedSize(msg.sizeHint())
            msg.exec()
            
            self.shazam_btn.setText(SHAZAM_BUTTON_ACTIVE["text"])
            self.shazam_btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgreen;
                    color: black;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12pt;
                    font-weight: bold;
                    min-width: 150px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #90EE90;
                }
            """)
        else:
            self.shazam_btn.setText(SHAZAM_BUTTON_NORMAL["text"])
            self.shazam_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12pt;
                    font-weight: bold;
                    min-width: 150px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
            """)

    def show_shazam_results(self, row, shazam_data):
        """Display Shazam results for a row"""
        if not self.shazam_mode:
            return
        
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
            
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                return

            # Initialize metadata dictionary if it doesn't exist
            if 'metadata' not in entry_data:
                entry_data['metadata'] = {}

            # Store widgets temporarily to prevent deletion
            self.temp_widgets = []
            
            # Column mapping
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            print(f"Processing Shazam data: {shazam_data}")
            
            # Create suggestion buttons for each field
            for field in ['title', 'artist', 'genre']:
                if field in shazam_data and shazam_data[field]:
                    try:
                        col_index = col_map[field]
                        current_item = self.table.item(row, col_index)
                        current_value = current_item.text() if current_item else ''
                        
                        # Escape special characters in the Shazam value
                        new_value = str(shazam_data[field])
                        escaped_new_value = (new_value
                            .replace('#', r'\#')
                            .replace(':', r'\:')
                            .replace(';', r'\;')
                            .strip()
                        )
                        
                        if current_value.lower() == escaped_new_value.lower():
                            # Values match - show green confirmation but keep field editable
                            item = QTableWidgetItem(current_value)
                            item.setBackground(QColor("#f0fff0"))  # Light green background
                            self.table.setItem(row, col_index, item)
                            entry_data['metadata'][field] = current_value  # Store current value
                        else:
                            # Create container widget
                            container = QWidget()
                            layout = QVBoxLayout(container)
                            layout.setContentsMargins(4, 4, 4, 4)
                            layout.setSpacing(4)

                            # Create suggestion button
                            suggest_btn = QPushButton()
                            
                            # Add right-click functionality
                            suggest_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            suggest_btn.customContextMenuRequested.connect(
                                lambda pos, r=row, f=field, v=current_value:
                                self.reject_shazam_value(r, f, v)
                            )

                            # Keep all the existing styling and setup exactly as is
                            suggest_btn.setStyleSheet("""
                                QPushButton {
                                    background-color: #4a90e2;
                                    color: white;
                                    border: none;
                                    border-radius: 4px;
                                    padding: 8px;
                                    text-align: left;
                                    min-height: 50px;
                                }
                                QPushButton:hover {
                                    background-color: #357abd;
                                }
                            """)

                            # Create layout for button content
                            btn_layout = QVBoxLayout(suggest_btn)
                            btn_layout.setContentsMargins(4, 4, 4, 4)
                            btn_layout.setSpacing(2)
                            
                            # Add current and new value labels
                            current_label = QLabel(f"Current: {current_value}")
                            current_label.setStyleSheet("color: #ccc; font-size: 9pt;")
                            new_label = QLabel(f"New: {escaped_new_value}")
                            new_label.setStyleSheet("color: white; font-size: 10pt; font-weight: bold;")
                            
                            btn_layout.addWidget(current_label)
                            btn_layout.addWidget(new_label)

                            suggest_btn.clicked.connect(
                                lambda checked, r=row, f=field, v=escaped_new_value:
                                self.apply_shazam_value(r, f, v)
                            )
                            
                            layout.addWidget(suggest_btn)
                            self.table.setCellWidget(row, col_index, container)
                            self.temp_widgets.append(container)
                            
                            # Set row height to accommodate the taller button
                            self.table.setRowHeight(row, 70)

                    except Exception as e:
                        print(f"Error processing field {field}: {str(e)}")
                        traceback.print_exc()
                        continue

            # Add artwork button if available
            if 'images' in shazam_data and 'coverart' in shazam_data['images']:
                # Check if actions widget exists
                actions_widget = self.table.cellWidget(row, 1)
                if actions_widget:
                    actions_layout = actions_widget.layout()
                    
                    # Check if artwork button already exists
                    artwork_btn_exists = False
                    for i in range(actions_layout.count()):
                        widget = actions_layout.itemAt(i).widget()
                        if isinstance(widget, QPushButton) and widget.text() == "📸":
                            artwork_btn_exists = True
                            break
                    
                    # Only create new button if it doesn't exist
                    if not artwork_btn_exists:
                        artwork_btn = QPushButton("📸")
                        artwork_btn.setToolTip("Compare Artwork")
                        artwork_btn.setMinimumWidth(30)
                        artwork_btn.clicked.connect(
                            lambda: self.compare_artwork(
                                row,
                                shazam_data['images']['coverart'],
                                os.path.dirname(entry_data['filepaths'][0])
                            )
                        )
                        artwork_btn.setStyleSheet("""
                            QPushButton {
                                background-color: #4a90e2;
                                color: white;
                                border: none;
                                border-radius: 4px;
                                padding: 4px 8px;
                            }
                            QPushButton:hover {
                                background-color: #357abd;
                            }
                        """)
                        
                        # Add to actions cell before the stretch
                        actions_layout.insertWidget(3, artwork_btn)
                        
        except Exception as e:
            print(f"Error in show_shazam_results: {str(e)}")
            traceback.print_exc()

    def apply_shazam_value(self, row, field, value):
        """Apply a Shazam suggestion to a field"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
            
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                print(f"Warning: Could not find entry data for ID {entry_id}")
                return
            
            # Find the current row for this ID (in case table was sorted)
            current_row = self.find_row_by_id(entry_id)
            if current_row == -1:
                return
            
            # Use current_row instead of row parameter from here on
            row = current_row

            # Value is already escaped when passed from show_shazam_results
            escaped_value = str(value).strip()

            # Map field names to column indices
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            col_index = col_map.get(field)
            if col_index is None:
                print(f"Warning: Invalid field name: {field}")
                return

            # Get current value
            current_item = self.table.item(row, col_index)
            current_value = current_item.text() if current_item else ""

            # Only mark as changed if the value is different
            if current_value != escaped_value:
                # Create new editable table item with the escaped value
                new_item = QTableWidgetItem(escaped_value)
                new_item.setForeground(QColor("#FF8C00"))  # Dark orange
                new_item.setFlags(new_item.flags() | Qt.ItemFlag.ItemIsEditable)
                
                # Remove the button container and set the new editable item
                self.table.removeCellWidget(row, col_index)
                self.table.setItem(row, col_index, new_item)
                
                # Update metadata
                if 'metadata' not in entry_data:
                    entry_data['metadata'] = {}
                entry_data['metadata'][field] = escaped_value
                
                # Update commit button and status
                self.update_row_status(row, entry_data['filepaths'])
                
                # Update the commit all button
                self.update_commit_all_button()
            
            # Check for remaining suggestions and update row height
            self.check_remaining_suggestions(row, col_index)
            
        except Exception as e:
            print(f"Error applying Shazam value: {str(e)}")
            traceback.print_exc()

    def collect_credits(self):
        """Collect all unique credits from loaded files"""
        all_credits = set()  # Back to using a simple set
        has_no_credits = False
        
        for entry in self.file_entries:
            entry_has_credits = False
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if 'CREDITS' in metadata:
                    valid_credits = {credit.lower() for credit in metadata['CREDITS'] 
                                   if credit and not credit.isspace()}
                    if valid_credits:
                        entry_has_credits = True
                        all_credits.update(valid_credits)
            
            if not entry_has_credits:
                has_no_credits = True
        
        if has_no_credits:
            all_credits.add('no credits! :(')
        
        return sorted(all_credits)  # Simple sort since everything is already lowercase

    def show_credit_search(self):
        credits = self.collect_credits()
        dialog = CreditSelectorDialog(self, sorted(credits))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_credit_filter(dialog.selected_credits)

    def apply_credit_filter(self, selected_credits):
        print(f"Selected credits: {selected_credits}")  # Debug print
        shown_count = 0
        total_count = len(self.file_entries)
        
        for entry in self.file_entries:
            # Get metadata from the first filepath
            metadata = MetadataUtil.read_metadata(entry['filepaths'][0])
            song_credits = metadata.get('CREDITS', set())
            print(f"Song credits for {entry['id']}: {song_credits}")  # Debug print
            
            # Show entry if any selected credit matches any song credit
            show_entry = False
            for credit in selected_credits:
                if any(credit.lower() in song_credit.lower() for song_credit in song_credits):
                    show_entry = True
                    break
            
            row = self.find_row_by_id(entry['id'])
            print(f"Found row {row} for ID {entry['id']}")  # Debug print
            
            if row != -1:
                self.table.setRowHidden(row, not show_entry)
                if show_entry:
                    shown_count += 1
                    print(f"Showing entry with credits: {song_credits}")  # Debug print
        
        print(f"Total shown: {shown_count} out of {total_count}")  # Debug print
        self.update_display_count(shown_count, total_count)
        
        # Update status bar
        self.statusBar().showMessage("Credit filter applied")

    def clear_directories(self):
        """Clear all loaded directories and reset the table"""
        reply = QMessageBox.question(
            self,
            "Clear All Directories",
            "Are you sure you want to clear all loaded directories?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.selected_directories.clear()
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Hide buttons that should only show when files are loaded
            # Only hide widgets that exist
            if hasattr(self, 'clear_button') and self.clear_button:
                self.clear_button.hide()
            if hasattr(self, 'bulk_edit_btn') and self.bulk_edit_btn:
                self.bulk_edit_btn.hide()
            if hasattr(self, 'search_credits_button') and self.search_credits_button:
                self.search_credits_button.hide()
            if hasattr(self, 'commit_all_button') and self.commit_all_button:
                self.commit_all_button.hide()
            
            # Reset status bar and display count
            self.statusBar().showMessage("Ready")
            self.update_display_count(0, 0)

    def sort_table(self, column):
        """Sort table by clicked column header"""
        try:
            # Only handle sortable columns
            if column not in [3, 4, 5, 6, 7]:  # pack, title, subtitle, artist, genre
                return
                
            # Store current sort order
            field_map = {3: 'pack', 4: 'title', 5: 'subtitle', 6: 'artist', 7: 'genre'}
            field = field_map[column]
            self.sort_reverse[field] = not self.sort_reverse[field]
            
            # Temporarily enable sorting
            self.table.setSortingEnabled(True)
            
            # Sort using Qt's built-in functionality
            self.table.sortItems(column, Qt.SortOrder.AscendingOrder if not self.sort_reverse[field] 
                                       else Qt.SortOrder.DescendingOrder)
            
            # Immediately disable sorting after the sort is complete
            self.table.setSortingEnabled(False)
            
            # Update file_entries row references
            for entry in self.file_entries:
                for row in range(self.table.rowCount()):
                    if self.table.item(row, 3) and entry['original_values'].get('pack') == self.table.item(row, 3).text():
                        entry['row'] = row
                        break
                        
        except Exception as e:
            print(f"Sort error: {str(e)}")
            traceback.print_exc()

    def show_help_dialog(self):
        """Show the help dialog with usage instructions"""
        dialog = HelpDialog(self)
        dialog.exec()

    def show_artwork_preview(self, row, artwork_url):
        """Show artwork preview dialog with option to save"""
        try:
            # Download image
            response = requests.get(artwork_url)
            image = Image.open(BytesIO(response.content))
            
            # Create preview dialog
            preview = QDialog(self)
            preview.setWindowTitle("Album Artwork Preview")
            layout = QVBoxLayout(preview)
            
            # Convert PIL image to QPixmap
            qim = ImageQt.ImageQt(image)
            pixmap = QPixmap.fromImage(qim)
            
            # Scale pixmap if too large
            max_size = 400
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(max_size, max_size, 
                                     Qt.AspectRatioMode.KeepAspectRatio, 
                                     Qt.TransformationMode.SmoothTransformation)
            
            # Add image to dialog
            label = QLabel()
            label.setPixmap(pixmap)
            layout.addWidget(label)
            
            # Add buttons
            button_frame = QFrame()
            button_layout = QHBoxLayout(button_frame)
            
            save_btn = QPushButton("Save Artwork")
            save_btn.clicked.connect(lambda: self.save_artwork(row, image))
            button_layout.addWidget(save_btn)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(preview.accept)
            button_layout.addWidget(close_btn)
            
            layout.addWidget(button_frame)
            preview.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load artwork: {str(e)}")
            
    def save_artwork(self, row, image):
        """Save artwork to song directory and update JACKET metadata"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                print("Error: No ID found for row", row)
                return False
                
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                print(f"Error: Could not find entry data for ID {entry_id}")
                return False
               
            directory = os.path.dirname(entry_data['filepaths'][0])
            if not directory or not os.path.exists(directory):
                print(f"Error: Invalid directory for ID {entry_id}")
                return False
            
            # Look for existing jacket file
            existing_jacket = None
            for file in os.listdir(directory):
                if 'jacket' in file.lower() and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    existing_jacket = file
                    break
            
            # Use existing jacket name or default
            jacket_filename = existing_jacket if existing_jacket else 'jacket.png'
            output_path = os.path.join(directory, jacket_filename)
            image.save(output_path)
            
            # Update metadata in all associated files
            for filepath in entry_data['filepaths']:
                content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                if not content:
                    continue
                
                jacket_line_exists = False
                
                # Check if JACKET field exists
                for i, line in enumerate(content):
                    if line.startswith('#JACKET:'):
                        content[i] = f'#JACKET:{jacket_filename};\n'
                        jacket_line_exists = True
                        break
                
                # If JACKET doesn't exist, add it after TITLE
                if not jacket_line_exists:
                    for i, line in enumerate(content):
                        if line.startswith('#TITLE:'):
                            content.insert(i + 1, f'#JACKET:{jacket_filename};\n')
                            break
                
                # Write back to file
                with open(filepath, 'w', encoding=encoding) as file:
                    file.writelines(content)
            
            print(f"Successfully saved artwork to {output_path}")
            QMessageBox.information(self, "Success", "Artwork Updated")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save artwork: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            QMessageBox.warning(self, "Error", error_msg)
            return False

    def create_action_buttons(self, row, filepaths, music_file='', entry_id=None):
        """Create action buttons for a table row"""
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(5)
        
        # Open folder button
        folder_btn = QToolButton()
        folder_btn.setText("📁")
        folder_btn.setMinimumWidth(30)
        folder_btn.clicked.connect(
            lambda: self.open_file_location(os.path.dirname(filepaths[0])))
        action_layout.addWidget(folder_btn)
        
        # Play button
        play_btn = QToolButton()
        play_btn.setText("▶️")
        play_btn.setMinimumWidth(30)
        if music_file:
            # Create the full music path
            music_path = os.path.join(os.path.dirname(filepaths[0]), music_file)
            
            # Simple lambda without default arguments
            play_btn.clicked.connect(
                lambda checked, mp=music_path, pb=play_btn, eid=entry_id: 
                self.play_audio(mp, pb, eid)
            )
        else:
            play_btn.setEnabled(False)
            play_btn.setToolTip("No audio file found")
        action_layout.addWidget(play_btn)
        
        # Edit button
        edit_btn = QToolButton()
        edit_btn.setText("✏️")
        edit_btn.setMinimumWidth(30)
        edit_btn.clicked.connect(lambda: self.edit_metadata(filepaths))  # Changed to edit_metadata
        action_layout.addWidget(edit_btn)
        
        return action_widget

    def cleanup_audio(self):
        """Clean up audio resources"""
        if self.current_playing:
            try:
                pygame.mixer.music.stop()
                self.current_playing.setText("▶")
                self.current_playing = None
            except Exception as e:
                print(f"Error cleaning up audio: {str(e)}")

    def closeEvent(self, event):
        """Handle cleanup when window is closed"""
        try:
            # Stop any playing audio
            if hasattr(self, 'audio_enabled') and self.audio_enabled:
                pygame.mixer.quit()
            event.accept()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            event.accept()

    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            if pygame.get_init():
                pygame.quit()
        except:
            pass

    def check_remaining_suggestions(self, row, current_col):
        """Check if there are any remaining suggestion buttons in the row"""
        has_suggestions = False
        for col in [4, 6, 7]:  # title, artist, genre columns
            if col != current_col:
                widget = self.table.cellWidget(row, col)
                if widget and isinstance(widget, QWidget):
                    has_suggestions = True
                    break
        
        if not has_suggestions:
            self.table.setRowHeight(row, self.table.verticalHeader().defaultSectionSize())

    def compare_artwork(self, row, shazam_url, song_directory):
        """Compare local artwork with Shazam artwork"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                print("Error: No ID found for row", row)
                return
                
            # Find the entry using ID instead of row
            entry_id = id_item.text()
            entry_data = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry_data:
                print(f"Error: Could not find entry data for ID {entry_id}")
                return
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Compare Artwork")
            dialog.setMinimumWidth(500)
            layout = QVBoxLayout(dialog)
            
            # Create image comparison layout
            images_layout = QHBoxLayout()
            layout.addLayout(images_layout)
            
            # Left side (Current)
            left_frame = QFrame()
            left_layout = QVBoxLayout(left_frame)
            left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Get JACKET value from metadata
            metadata = MetadataUtil.read_metadata(entry_data['filepaths'][0])
            jacket_ref = metadata.get('JACKET', '').strip()
            local_image = None
            current_jacket_ref = None

            if jacket_ref:
                # Try to find any file containing the jacket name (without extension)
                search_term = os.path.splitext(jacket_ref)[0].lower()
                for file in os.listdir(song_directory):
                    if search_term in file.lower() and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        try:
                            local_image = Image.open(os.path.join(song_directory, file))
                            current_jacket_ref = file
                            break
                        except Exception as e:
                            print(f"Failed to load file containing {search_term}: {str(e)}")

            # If no image found from JACKET reference, look for any file with "jacket" in the name
            if not local_image:
                for file in os.listdir(song_directory):
                    if 'jacket' in file.lower() and file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        try:
                            local_image = Image.open(os.path.join(song_directory, file))
                            current_jacket_ref = file
                            break
                        except Exception as e:
                            print(f"Failed to load jacket file: {str(e)}")
            

            
            # Display current artwork if found
            if local_image:
                local_label = QLabel()
                local_pixmap = ImageQt.toqpixmap(local_image.resize((200, 200)))
                local_label.setPixmap(local_pixmap)
                left_layout.addWidget(local_label)
                left_layout.addWidget(QLabel(f"Current: {current_jacket_ref}"))
                left_layout.addWidget(QLabel(f"Size: {local_image.size[0]}x{local_image.size[1]}"))
            else:
                left_layout.addWidget(QLabel("No matching jacket artwork found"))
                if jacket_ref:
                    left_layout.addWidget(QLabel(f"(Looking for: {jacket_ref})"))
            
            images_layout.addWidget(left_frame)
            
            # Right side (Shazam)
            right_frame = QFrame()
            right_layout = QVBoxLayout(right_frame)
            right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Download and display Shazam artwork
            try:
                response = requests.get(shazam_url)
                shazam_image = Image.open(BytesIO(response.content))
                
                shazam_label = QLabel()
                shazam_pixmap = ImageQt.toqpixmap(shazam_image.resize((200, 200)))
                shazam_label.setPixmap(shazam_pixmap)
                right_layout.addWidget(shazam_label)
                right_layout.addWidget(QLabel("Shazam Artwork"))
                right_layout.addWidget(QLabel(f"Size: {shazam_image.size[0]}x{shazam_image.size[1]}"))
                
                images_layout.addWidget(right_frame)
                
                # Add buttons
                button_layout = QHBoxLayout()
                layout.addLayout(button_layout)
                
                keep_btn = QPushButton("Keep Current")
                keep_btn.clicked.connect(dialog.reject)
                button_layout.addWidget(keep_btn)
                
                update_btn = QPushButton("Update Artwork")
                update_btn.clicked.connect(lambda: self.handle_artwork_update(dialog, row, shazam_image))
                button_layout.addWidget(update_btn)
                
                dialog.exec()
                
            except Exception as e:
                error_msg = f"Error downloading Shazam artwork: {str(e)}"
                print(error_msg)
                traceback.print_exc()
                QMessageBox.warning(self, "Error", error_msg)
                
        except Exception as e:
            error_msg = f"Error comparing artwork: {str(e)}"
            print(error_msg)
            traceback.print_exc()

    def handle_artwork_update(self, dialog, row, image):
        """Handle artwork update and dialog closing"""
        if self.save_artwork(row, image):
            dialog.accept()  # Close the dialog only if save was successful

    def check_playback(self):
        """Check if playback has ended and reset button state"""
        if self.current_playing and not pygame.mixer.music.get_busy():
            self.current_playing.setText("▶")
            self.current_playing = None

    def edit_metadata(self, filepaths):
        """Open the metadata editor dialog"""
        try:
            dialog = MetadataEditorDialog(self, filepaths)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Refresh the display after changes
                self.refresh_table()
        except Exception as e:
            print(f"Error opening metadata editor: {str(e)}")
            traceback.print_exc()

    def update_row_status(self, row, filepaths):
        """Update the status and commit columns for a row"""
        try:
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return

            # Check if any values have changed
            has_changes = False
            for col, field in [
                (self.COL_TITLE, 'title'),
                (self.COL_SUBTITLE, 'subtitle'),
                (self.COL_ARTIST, 'artist'),
                (self.COL_GENRE, 'genre')
            ]:
                item = self.table.item(row, col)
                if item and item.text() != entry['original_values'][field]:
                    has_changes = True
                    break

            # Update status column
            if has_changes:
                status_label = QLabel("⚠")
                status_label.setStyleSheet("color: #FF8C00;")  # Dark orange
                status_label.setToolTip("Unsaved changes")
                
                status_container = QWidget()
                status_layout = QHBoxLayout(status_container)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                status_layout.addWidget(status_label)
                
                self.table.setCellWidget(row, 8, status_container)

                # Create commit button
                commit_container = QWidget()
                commit_layout = QHBoxLayout(commit_container)
                commit_layout.setContentsMargins(2, 2, 2, 2)
                
                commit_btn = QPushButton("Commit")
                commit_btn.setObjectName("commitButton")
                commit_btn.clicked.connect(lambda: self.commit_changes(row, filepaths))
                commit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4a90e2;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                        min-width: 60px;
                    }
                    QPushButton:hover {
                        background-color: #357abd;
                    }
                """)
                commit_layout.addWidget(commit_btn)
                self.table.setCellWidget(row, 9, commit_container)
            else:
                # Clear status and commit columns if no changes
                self.table.removeCellWidget(row, 8)  # Status column
                self.table.removeCellWidget(row, 9)  # Commit column
                self.table.setItem(row, 8, QTableWidgetItem(""))
                self.table.setItem(row, 9, QTableWidgetItem(""))

            # Update commit all button
            self.update_commit_all_button()

        except Exception as e:
            print(f"Error updating row status: {str(e)}")
            traceback.print_exc()

    def clear_search(self):
        """Clear the search box and reset display"""
        self.search_box.clear()
        self.clear_button.setVisible(False)
        
        # Show all rows
        total_count = len(self.file_entries)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)
            
        # Update display count to show all entries
        self.update_display_count(total_count, total_count)

    def on_cell_changed(self, row, col):
        """Handle cell value changes"""
        try:
            # Only process editable columns
            if col not in [self.COL_TITLE, self.COL_SUBTITLE, self.COL_ARTIST, self.COL_GENRE]:
                return
                
            # Get the ID from the current row
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                return
                
            # Find the entry in backend data using ID
            entry_id = id_item.text()
            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
            if not entry:
                return
                
            # Map column to field name
            col_to_field = {
                self.COL_TITLE: 'title',
                self.COL_SUBTITLE: 'subtitle',
                self.COL_ARTIST: 'artist',
                self.COL_GENRE: 'genre'
            }
            
            field = col_to_field.get(col)
            if not field:
                return
                
            # Get the new value
            item = self.table.item(row, col)
            if not item:
                return
                
            # Check if value has changed from original
            if item.text() != entry['original_values'][field]:
                # Update status and commit columns
                self.update_row_status(row, entry['filepaths'])
                
        except Exception as e:
            print(f"Error in on_cell_changed: {str(e)}")
            traceback.print_exc()

    def update_display_count(self, shown_count, total_count):
        """Update the display count indicator"""
        # Get unique pack names by taking the basename of each directory
        unique_packs = {os.path.basename(directory) for directory in self.selected_directories}
        pack_count = len(unique_packs)
        
        self.display_count_label.setText(
            f"Displaying {shown_count} of {total_count} songs from {pack_count} packs"
        )
        # Always show the frame, even when counts are equal
        self.display_count_frame.show()

    def reject_shazam_value(self, row, field, original_value):
        """Reject a Shazam suggestion and restore the original value"""
        try:
            col_map = {
                'title': 4,
                'artist': 6,
                'genre': 7
            }
            
            col_index = col_map.get(field)
            if col_index is None:
                return

            # Create new item with original value
            item = QTableWidgetItem(original_value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            # Remove suggestion and restore original value
            self.table.removeCellWidget(row, col_index)
            self.table.setItem(row, col_index, item)
            
            # Reset row height if no more suggestions
            has_suggestions = False
            for col in [4, 6, 7]:  # title, artist, genre columns
                if isinstance(self.table.cellWidget(row, col), QWidget):
                    has_suggestions = True
                    break
            if not has_suggestions:
                self.table.setRowHeight(row, self.table.verticalHeader().defaultSectionSize())
            
        except Exception as e:
            print(f"Error rejecting Shazam value: {str(e)}")
            traceback.print_exc()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def export_to_csv(self):
        """Export visible table data to CSV"""
        try:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save CSV File",
                "",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if file_name:
                with open(file_name, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    
                    # Write headers including all possible metadata fields
                    headers = [
                        'Type',
                        'Pack',
                        'Title',
                        'Subtitle',
                        'Artist',
                        'Genre',
                        'Credits',
                        'Music File',
                        'Banner',
                        'Background',
                        'CDTitle',
                        'Sample Start',
                        'Sample Length',
                        'Display BPM',
                        'Selectable'
                    ]
                    writer.writerow(headers)
                    
                    # Write visible rows
                    for row in range(self.table.rowCount()):
                        if not self.table.isRowHidden(row):
                            # Get the ID from the current row
                            id_item = self.table.item(row, self.COL_ID)
                            if not id_item:
                                continue
                            
                            # Find the entry using ID
                            entry_id = id_item.text()
                            entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
                            
                            if entry:
                                # Get file type from table
                                type_item = self.table.item(row, 2)
                                file_type = type_item.text() if type_item else ''
                                
                                # Read metadata from primary file
                                metadata = MetadataUtil.read_metadata(entry['filepaths'][0])
                                
                                # Format credits properly - remove empty credits and handle single credit case
                                credits = {credit for credit in metadata.get('CREDITS', set()) 
                                         if credit and not credit.isspace()}
                                credits_str = '; '.join(sorted(credits)) if len(credits) > 1 else next(iter(credits), '')
                                
                                row_data = [
                                    file_type,
                                    os.path.basename(os.path.dirname(os.path.dirname(entry['filepaths'][0]))),
                                    metadata.get('TITLE', '').strip(),
                                    metadata.get('SUBTITLE', '').strip(),
                                    metadata.get('ARTIST', '').strip(),
                                    metadata.get('GENRE', '').strip(),
                                    credits_str,
                                    metadata.get('MUSIC', '').strip(),
                                    metadata.get('BANNER', '').strip(),
                                    metadata.get('BACKGROUND', '').strip(),
                                    metadata.get('CDTITLE', '').strip(),
                                    metadata.get('SAMPLESTART', '').strip(),
                                    metadata.get('SAMPLELENGTH', '').strip(),
                                    metadata.get('DISPLAYBPM', '').strip(),
                                    metadata.get('SELECTABLE', '').strip()
                                ]
                                writer.writerow(row_data)
                
                QMessageBox.information(self, "Success", "Data exported successfully!")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to export data: {str(e)}")
            traceback.print_exc()

    def find_row_by_id(self, entry_id):
        """Find the current row number for a given entry ID"""
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, self.COL_ID)
            if id_item and id_item.text() == entry_id:
                return row
        print(f"Debug: Could not find row for ID {entry_id}")
        return -1

    def verify_row_id_mapping(self):
        """Debug helper to print current row-ID mappings"""
        print("\nCurrent Row-ID Mappings:")
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, self.COL_ID)
            if id_item:
                print(f"Row {row}: ID {id_item.text()}")

    def shazam_all(self):
        """Process all visible songs with Shazam"""
        if not self.shazam or not self.loop:
            QMessageBox.warning(self, "Error", "Shazam functionality is not available.")
            return
            
        # Count visible songs
        total = sum(1 for row in range(self.table.rowCount()) 
                   if not self.table.isRowHidden(row))
        
        reply = QMessageBox.question(
            self,
            "Confirm Shazam All",
            "This will attempt to Shazam all visible songs in the list. This may take a while. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if not self.shazam_mode:
                self.toggle_shazam_mode()
            
            progress = QDialog(self)
            progress.setWindowTitle("Processing")
            progress.setModal(True)
            
            layout = QVBoxLayout(progress)
            progress_label = QLabel("Processing songs with Shazam...")
            layout.addWidget(progress_label)
            
            cancel_button = QPushButton("Cancel")
            layout.addWidget(cancel_button)
            
            self.cancelled = False
            cancel_button.clicked.connect(lambda: setattr(self, 'cancelled', True))
            
            progress.show()
            
            try:
                processed = self.loop.run_until_complete(
                    self.process_songs_with_shazam(progress_label, total)
                )
                
                if self.cancelled:
                    QMessageBox.information(
                        self, 
                        "Cancelled", 
                        f"Process cancelled.\nProcessed {processed} out of {total} songs."
                    )
                else:
                    QMessageBox.information(
                        self, 
                        "Complete", 
                        f"Shazam All process completed!\nProcessed {processed} songs."
                    )
                
            except Exception as e:
                QMessageBox.warning(
                    self, 
                    "Error", 
                    f"An error occurred during processing: {str(e)}"
                )
                traceback.print_exc()
            finally:
                progress.close()

    async def process_songs_with_shazam(self, progress_label, total):
        processed = 0
        
        for row in range(self.table.rowCount()):
            if self.cancelled:
                break
                
            if not self.table.isRowHidden(row):
                processed += 1
                remaining = total - processed
                est_seconds = remaining * 1.75
                
                # Format time estimate
                if est_seconds < 60:
                    time_str = f"{int(est_seconds)} seconds"
                else:
                    minutes = int(est_seconds // 60)
                    seconds = int(est_seconds % 60)
                    time_str = f"{minutes} minute{'s' if minutes != 1 else ''} {seconds} second{'s' if seconds != 1 else ''}"
                
                progress_label.setText(
                    f"Processing songs with Shazam... ({processed}/{total})\n"
                    f"Estimated time remaining: {time_str}"
                )
                QApplication.processEvents()
                
                try:
                    # Get the music file path
                    id_item = self.table.item(row, self.COL_ID)
                    if id_item:
                        entry_id = id_item.text()
                        entry = next((e for e in self.file_entries if e['id'] == entry_id), None)
                        
                        if entry:
                            directory = os.path.dirname(entry['filepaths'][0])
                            for file in os.listdir(directory):
                                if file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                                    music_path = os.path.join(directory, file)
                                    await self.run_shazam_analysis(music_path, row)
                                    await asyncio.sleep(1.25)  # Delay between requests
                                    break
                                    
                except Exception as e:
                    print(f"Error processing row {row}: {str(e)}")
                    continue  # Continue to next song if one fails
                    
        return processed

class PackSelectorDialog(QDialog):
    def __init__(self, parent, directories):
        super().__init__(parent)
        self.setWindowTitle("Select Packs")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        # Convert directories to list and store as instance variable
        self.directories = sorted(list(directories), key=str.lower)
        self.selected_packs = set()
        self.buttons = {}
        self.is_accepting = False
        
        # Create the UI after initializing variables
        self.setup_ui()
        
    def setup_ui(self):
        try:
            layout = QVBoxLayout(self)
            
            # Warning label
            warning_text = ("Warning: Selecting all packs may cause performance issues.\n"
                          "Consider working with a handful of packs at a time for better responsiveness.")
            warning_label = QLabel(warning_text)
            warning_label.setStyleSheet("color: blue; font-weight: bold;")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)
            
            # Create scroll area
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_widget = QWidget()
            scroll_layout = QGridLayout(scroll_widget)
            scroll_layout.setSpacing(4)
            

            button_width = 240 
            
            # Create pack buttons with proper reference handling
            row = col = 0
            for pack in self.directories:
                btn = QPushButton(str(pack))  # Ensure string conversion
                btn.setCheckable(True)
                btn.setFixedWidth(button_width)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                
                # Set the stylesheet for the button
                btn.setStyleSheet("""
                    QPushButton:checked {
                        background-color: lightgreen;
                    }
                """)
                
                # Store button reference and connect with lambda
                self.buttons[pack] = btn
                btn.clicked.connect(lambda checked, p=pack: self.toggle_pack(p))
                
                btn.setToolTip(str(pack))
                scroll_layout.addWidget(btn, row, col)
                
                col += 1
                if col >= 3:
                    col = 0
                    row += 1
            
            # Add stretch to push buttons to top
            scroll_layout.setRowStretch(row + 1, 1)
            scroll_layout.setColumnStretch(3, 1)
            
            scroll_area.setWidget(scroll_widget)
            layout.addWidget(scroll_area)
            
            # Button frame
            button_frame = QFrame()
            button_layout = QHBoxLayout(button_frame)
            
            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(self.select_all_packs)
            button_layout.addWidget(select_all_btn)
            
            deselect_all_btn = QPushButton("Deselect All")
            deselect_all_btn.clicked.connect(self.deselect_all_packs)
            button_layout.addWidget(deselect_all_btn)
            
            button_layout.addStretch()
            
            ok_button = QPushButton("Let's Go!")
            ok_button.clicked.connect(self.accept)
            button_layout.addWidget(ok_button)
            
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(self.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addWidget(button_frame)
            
        except Exception as e:
            print(f"Error in setup_ui: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def toggle_pack(self, pack):
        """Toggle pack selection state with error handling"""
        try:
            if pack in self.selected_packs:
                self.selected_packs.remove(pack)
                if pack in self.buttons:
                    self.buttons[pack].setChecked(False)
            else:
                self.selected_packs.add(pack)
                if pack in self.buttons:
                    self.buttons[pack].setChecked(True)
        except Exception as e:
            print(f"Error toggling pack {pack}: {str(e)}")
            traceback.print_exc()

    def select_all_packs(self):
        """Select all packs with error handling"""
        try:
            self.selected_packs = set(self.directories)
            for btn in self.buttons.values():
                btn.setChecked(True)
        except Exception as e:
            print(f"Error selecting all packs: {str(e)}")
            traceback.print_exc()

    def deselect_all_packs(self):
        """Deselect all packs with error handling"""
        try:
            self.selected_packs.clear()
            for btn in self.buttons.values():
                btn.setChecked(False)
        except Exception as e:
            print(f"Error deselecting all packs: {str(e)}")
            traceback.print_exc()

    def accept(self):
        """Override accept with proper cleanup"""
        if self.is_accepting:
            return
            
        try:
            self.is_accepting = True
            
            if not self.selected_packs:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select at least one pack to continue."
                )
                self.is_accepting = False
                return
            
            # Safely disconnect signals
            for btn in self.buttons.values():
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                    
            self.buttons.clear()
            super().accept()
            
        except Exception as e:
            print(f"Error in accept: {str(e)}")
            traceback.print_exc()
        finally:
            self.is_accepting = False

    def reject(self):
        """Override reject with proper cleanup"""
        try:
            # Safely disconnect signals
            for btn in self.buttons.values():
                try:
                    btn.clicked.disconnect()
                except Exception:
                    pass
                    
            self.buttons.clear()
            super().reject()
            
        except Exception as e:
            print(f"Error in reject: {str(e)}")
            traceback.print_exc()

class CreditSelectorDialog(QDialog):
    def __init__(self, parent, credits):
        super().__init__(parent)
        self.setWindowTitle("Select Credits")
        self.setMinimumSize(800, 600)
        
        self.credits = credits
        self.selected_credits = set()
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info label
        info_text = ("Select credits to filter songs by their creators.\n"
                    "You can select multiple credits to see all songs by those creators.")
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #666; font-weight: bold;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Button frame for Select All/Deselect All
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self.select_all_credits)
        button_layout.addWidget(select_all)
        
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(self.deselect_all_credits)
        button_layout.addWidget(deselect_all)
        
        button_layout.addStretch()
        layout.addWidget(button_frame)
        
        # Create scroll area for credit buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setSpacing(4)
        
        # Create credit buttons in a grid
        row = 0
        col = 0
        for credit in sorted(self.credits, key=str.lower):
            btn = QPushButton(credit)
            btn.setCheckable(True)
            btn.setFixedWidth(240)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            
            # Set the stylesheet for the button
            btn.setStyleSheet("""
                QPushButton:checked {
                    background-color: lightgreen;
                }
            """)
            
            btn.clicked.connect(lambda checked, c=credit: self.toggle_credit(c))
            btn.setToolTip(credit)
            scroll_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Add stretch to push buttons to top
        scroll_layout.setRowStretch(row + 1, 1)
        scroll_layout.setColumnStretch(3, 1)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Dialog buttons
        dialog_buttons = QFrame()
        dialog_layout = QHBoxLayout(dialog_buttons)
        dialog_layout.addStretch()
        
        ok_button = QPushButton("Filter by Credits")
        ok_button.clicked.connect(self.accept)
        dialog_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        dialog_layout.addWidget(cancel_button)
        
        layout.addWidget(dialog_buttons)
        
    def select_all_credits(self):
        self.selected_credits = set(self.credits)
        for button in self.findChildren(QPushButton):
            if button.text() in self.credits:
                button.setChecked(True)
                
    def deselect_all_credits(self):
        self.selected_credits.clear()
        for button in self.findChildren(QPushButton):
            if button.text() in self.credits:
                button.setChecked(False)

    def toggle_credit(self, credit):
        if credit in self.selected_credits:
            self.selected_credits.remove(credit)
        else:
            self.selected_credits.add(credit)
            
class ArtworkPreviewDialog(QDialog):
    def __init__(self, parent, current_img_path, new_artwork_url, filepaths):
        super().__init__(parent)
        self.setWindowTitle("Album Artwork Preview")
        self.setFixedSize(800, 600)
        
        self.current_img_path = current_img_path
        self.new_artwork_url = new_artwork_url
        self.filepaths = filepaths
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create image preview area
        preview_frame = QFrame()
        preview_layout = QHBoxLayout(preview_frame)
        
        # Current artwork
        current_frame = QFrame()
        current_layout = QVBoxLayout(current_frame)
        current_label = QLabel("Current Artwork")
        current_layout.addWidget(current_label)
        
        self.current_image_label = QLabel()
        if os.path.exists(self.current_img_path):
            pixmap = QPixmap(self.current_img_path)
            pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio)
            self.current_image_label.setPixmap(pixmap)
            current_layout.addWidget(QLabel(f"Dimensions: {pixmap.width()}x{pixmap.height()}"))
        else:
            self.current_image_label.setText("No current artwork")
        current_layout.addWidget(self.current_image_label)
        
        preview_layout.addWidget(current_frame)
        
        # New artwork
        new_frame = QFrame()
        new_layout = QVBoxLayout(new_frame)
        new_label = QLabel("New Artwork")
        new_layout.addWidget(new_label)
        
        self.new_image_label = QLabel()
        try:
            response = requests.get(self.new_artwork_url)
            image = Image.open(BytesIO(response.content))
            qimage = ImageQt.ImageQt(image)
            pixmap = QPixmap.fromImage(qimage)
            pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio)
            self.new_image_label.setPixmap(pixmap)
            new_layout.addWidget(QLabel(f"Dimensions: {pixmap.width()}x{pixmap.height()}"))
            self.new_image = image
        except Exception as e:
            self.new_image_label.setText(f"Failed to load new artwork: {str(e)}")
            self.new_image = None
        new_layout.addWidget(self.new_image_label)
        
        preview_layout.addWidget(new_frame)
        layout.addWidget(preview_frame)
        
        # Buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        keep_button = QPushButton("Keep Current")
        keep_button.clicked.connect(self.reject)
        button_layout.addWidget(keep_button)
        
        update_button = QPushButton("Update Artwork")
        update_button.clicked.connect(self.update_artwork)
        button_layout.addWidget(update_button)
        
        layout.addWidget(button_frame)
        
    def update_artwork(self):
        if not self.new_image:
            return
        
        try:
            # Save new artwork
            self.new_image.save(self.current_img_path)
            
            # Update metadata in files
            for filepath in self.filepaths:
                content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                if not content:
                    continue
                
                jacket_name = os.path.basename(self.current_img_path)
                jacket_line_exists = False
                
                for i, line in enumerate(content):
                    if line.startswith('#JACKET:'):
                        content[i] = f'#JACKET:{jacket_name};\n'
                        jacket_line_exists = True
                        break
                
                if not jacket_line_exists:
                    # Find #TITLE: line and add JACKET after it
                    for i, line in enumerate(content):
                        if line.startswith('#TITLE:'):
                            content.insert(i + 1, f'#JACKET:{jacket_name};\n')
                            break
                
                with open(filepath, 'w', encoding=encoding) as file:
                    file.writelines(content)
            
            QMessageBox.information(self, "Success", "Artwork updated successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update artwork: {str(e)}")
            
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("StepMania Metadata Editor Help")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Help content sections
        sections = {
            "Basic Features": [
                "• Add Directory: Select folders containing StepMania song files (.sm, .ssc)",
                "• Clear All: Remove all loaded songs from the editor",
                "• Bulk Edit: Select multiple songs to edit their metadata simultaneously",
                "• Sort columns by clicking on column headers"
            ],
            "Actions Column": [
                "• ... (three dots): Open song folder in file explorer",
                "   ▶ (play): Preview song audio (if available)",
                "✎ (pencil): Open full metadata editor for advanced fields"
            ],
            "Metadata Editing": [
                "• Edit Title, Subtitle, Artist, and Genre directly in the main view",
                "• Successfully saved changes appear in light green commited button",
                "• Click 'Commit?' to save changes (appears when modifications are made)",
                "• Use 'Commit All' to save all pending changes at once"
            ],
            "Shazam Integration": [
                "• Toggle Shazam Mode to identify songs automatically",
                "• Play a song while Shazam is active to get metadata suggestions",
                "• Click on suggested values to apply them",
                "• Preview and update album artwork when available"
            ],
            "Bulk Editing": [
                "• Enable Bulk Edit mode to show checkboxes",
                "• Select multiple songs using checkboxes",
                "• Enter new values in the bulk edit fields",
                "• Click 'Apply to Selected' to update all chosen songs"
            ],
            "Tips": [
                "• The editor supports multiple file encodings (UTF-8, Shift-JIS, etc.)",
                "• Combined view for songs with both .sm and .ssc files",
                "• Mouse wheel scrolling supported in all views",
                "• Internet connection required for Shazam features"
            ],
            "File Handling": [
                "• SSC files take precedence over SM files with the same name",
                "• When both SM and SSC exist, SSC metadata is used but both files are updated",
                "• Files are matched by name (case-insensitive)",
                "• The Type column shows 'sm+ssc' when both file types exist"
            ]
        }
        
        for section, items in sections.items():
            # Section header
            header = QLabel(section)
            header.setStyleSheet("font-weight: bold; font-size: 12pt;")
            scroll_layout.addWidget(header)
            
            # Section content
            content = QLabel("\n".join(items))
            content.setWordWrap(True)
            content.setContentsMargins(20, 0, 0, 0)
            scroll_layout.addWidget(content)
            
            # Add spacing between sections
            scroll_layout.addSpacing(10)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

class MetadataEditorDialog(QDialog):
    def __init__(self, parent, filepaths):
        super().__init__(parent)
        self.setWindowTitle("Full Metadata Editor")
        self.setMinimumSize(600, 800)
        
        self.filepaths = filepaths
        self.entries = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        
        # Read metadata from first file
        metadata = MetadataUtil.read_metadata(self.filepaths[0])
        
        # Create entry fields for each metadata item
        row = 0
        for key, value in metadata.items():
            if key != 'CREDITS':  # Skip credits set
                label = QLabel(key)
                scroll_layout.addWidget(label, row, 0)
                
                line_edit = QLineEdit(value)
                scroll_layout.addWidget(line_edit, row, 1)
                self.entries[key] = {'widget': line_edit, 'original': value}
                
                row += 1
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Button frame
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        commit_button = QPushButton("Commit Changes")
        commit_button.clicked.connect(self.commit_changes)
        button_layout.addWidget(commit_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addWidget(button_frame)
        
    def commit_changes(self):
        changes = {}
        for key, entry in self.entries.items():
            new_value = entry['widget'].text()
            if new_value != entry['original']:
                changes[key] = new_value
        
        if changes:
            success = True
            for filepath in self.filepaths:
                if not MetadataUtil.write_metadata(filepath, changes):
                    success = False
                    break
            
            if success:
                QMessageBox.information(self, "Success", "Changes saved successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to save changes to one or more files.")
        else:
            self.reject()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Appearance Settings
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout()
        
        # Create radio button group for themes
        self.theme_group = QButtonGroup(self)
        
        self.light_mode_radio = QRadioButton("Light Mode")
        self.rainbow_mode_radio = QRadioButton("🌈 Rainbow Mode")
        
        # Set initial state based on current mode
        if hasattr(self.parent, 'rainbow_mode') and self.parent.rainbow_mode:
            self.rainbow_mode_radio.setChecked(True)
        else:
            self.light_mode_radio.setChecked(True)
        
        # Add radio buttons to group and layout
        self.theme_group.addButton(self.light_mode_radio)
        self.theme_group.addButton(self.rainbow_mode_radio)
        
        appearance_layout.addWidget(self.light_mode_radio)
        appearance_layout.addWidget(self.rainbow_mode_radio)
        
        # Connect theme changes
        self.light_mode_radio.toggled.connect(self.update_theme)
        self.rainbow_mode_radio.toggled.connect(self.update_theme)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # Audio Settings
        audio_group = QGroupBox("Audio Settings")
        audio_layout = QVBoxLayout()
        
        self.toggle_audio_btn = QPushButton(
            "Audio Enabled" if self.parent.audio_enabled else "Audio Disabled"
        )
        self.toggle_audio_btn.clicked.connect(self.toggle_audio)
        audio_layout.addWidget(self.toggle_audio_btn)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # Shazam Settings
        shazam_group = QGroupBox("Shazam Settings")
        shazam_layout = QVBoxLayout()
        
        shazam_all_btn = QPushButton("Shazam All Songs")
        shazam_all_btn.clicked.connect(self.parent.shazam_all)
        shazam_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)
        shazam_layout.addWidget(shazam_all_btn)
        
        shazam_group.setLayout(shazam_layout)
        layout.addWidget(shazam_group)

        # Export Settings
        export_group = QGroupBox("Export Settings")
        export_layout = QVBoxLayout()
        
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self.parent.export_to_csv)
        export_layout.addWidget(export_btn)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Debug Settings
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QVBoxLayout()
        
        self.toggle_console_btn = QPushButton(
            "Show Console" if not self.parent.console_window.isVisible() else "Hide Console"
        )
        self.toggle_console_btn.clicked.connect(self.toggle_console)
        debug_layout.addWidget(self.toggle_console_btn)
        
        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        # Close button at bottom
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def update_theme(self):
        if self.light_mode_radio.isChecked():
            self.parent.rainbow_mode = False
            self.parent.setStyleSheet(MODERN_LIGHT_STYLE)
        elif self.rainbow_mode_radio.isChecked():
            self.parent.rainbow_mode = True
            self.parent.setStyleSheet(MODERN_RAINBOW_STYLE)

    def toggle_audio(self):
        try:
            if self.parent.audio_enabled:
                pygame.mixer.quit()
                self.parent.audio_enabled = False
                self.toggle_audio_btn.setText("Audio Disabled")
            else:
                pygame.mixer.init()
                self.parent.audio_enabled = True
                self.toggle_audio_btn.setText("Audio Enabled")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to toggle audio: {str(e)}"
            )

    def toggle_console(self):
        if self.parent.console_window.isVisible():
            self.parent.console_window.hide()
            self.toggle_console_btn.setText("Show Console")
        else:
            self.parent.console_window.show()
            self.toggle_console_btn.setText("Hide Console")
            
            # Print debug information when console is opened
            print("\n=== Debug Information ===")
            print(f"Python Version: {sys.version}")
            print(f"Operating System: {os.name} - {sys.platform}")
            print(f"Working Directory: {os.getcwd()}")
            print(f"Executable Path: {sys.executable}")
            
            # System info
            print("\n=== System Information ===")
            print(f"CPU Architecture: {platform.machine()}")
            print(f"Windows Version: {platform.platform()}")
            
            # Application info
            print("\n=== Application State ===")
            print(f"Rainbow Mode: {self.parent.rainbow_mode}")
            print(f"Audio Enabled: {self.parent.audio_enabled}")
            print(f"Window Size: {self.parent.size()}")
            
            # File system info
            print("\n=== File System ===")
            try:
                print(f"Write Permission in Current Dir: {os.access(os.getcwd(), os.W_OK)}")
                print(f"Read Permission in Current Dir: {os.access(os.getcwd(), os.R_OK)}")
                print(f"Current User: {os.getlogin()}")
            except Exception as e:
                print(f"Error checking permissions: {e}")
                
            # Qt info
            print("\n=== Qt Information ===")
            print(f"Qt Version: {QtCore.QT_VERSION_STR}")
            print(f"PyQt Version: {QtCore.PYQT_VERSION_STR}")
            
            # Check loaded modules
            print("\n=== Loaded Modules ===")
            for name, module in sorted(sys.modules.items()):
                if hasattr(module, '__version__'):
                    print(f"{name}: {module.__version__}")
    def update_theme(self):
        if self.light_mode_radio.isChecked():
            self.parent.rainbow_mode = False
            self.parent.setStyleSheet(MODERN_LIGHT_STYLE)
        elif self.rainbow_mode_radio.isChecked():
            self.parent.rainbow_mode = True
            self.parent.setStyleSheet(MODERN_RAINBOW_STYLE)

    def toggle_audio(self):
        try:
            if self.parent.audio_enabled:
                pygame.mixer.quit()
                self.parent.audio_enabled = False
                self.toggle_audio_btn.setText("Audio Disabled")
            else:
                pygame.mixer.init()
                self.parent.audio_enabled = True
                self.toggle_audio_btn.setText("Audio Enabled")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to toggle audio: {str(e)}"
            )
def toggle_console(self):
    if self.parent.console_window.isVisible():
        self.parent.console_window.hide()
        self.toggle_console_btn.setText("Show Console")
    else:
        self.parent.console_window.show()
        self.toggle_console_btn.setText("Hide Console")
        
        # Write directly to the console output
        self.parent.console_window.console_output.append("\n=== Debug Information ===")
        self.parent.console_window.console_output.append(f"Python Version: {sys.version}")
        self.parent.console_window.console_output.append(f"Operating System: {os.name} - {sys.platform}")
        self.parent.console_window.console_output.append(f"Working Directory: {os.getcwd()}")
        self.parent.console_window.console_output.append(f"Executable Path: {sys.executable}")
        
        self.parent.console_window.console_output.append("\n=== System Information ===")
        self.parent.console_window.console_output.append(f"CPU Architecture: {platform.machine()}")
        self.parent.console_window.console_output.append(f"Windows Version: {platform.platform()}")
        
        self.parent.console_window.console_output.append("\n=== Application State ===")
        self.parent.console_window.console_output.append(f"Rainbow Mode: {self.parent.rainbow_mode}")
        self.parent.console_window.console_output.append(f"Audio Enabled: {self.parent.audio_enabled}")
        self.parent.console_window.console_output.append(f"Window Size: {self.parent.size()}")
        
        self.parent.console_window.console_output.append("\n=== File System ===")
        try:
            self.parent.console_window.console_output.append(
                f"Write Permission in Current Dir: {os.access(os.getcwd(), os.W_OK)}")
            self.parent.console_window.console_output.append(
                f"Read Permission in Current Dir: {os.access(os.getcwd(), os.R_OK)}")
            self.parent.console_window.console_output.append(
                f"Current User: {os.getlogin()}")
        except Exception as e:
            self.parent.console_window.console_output.append(f"Error checking permissions: {e}")
        
        self.parent.console_window.console_output.append("\n=== Qt Information ===")
        self.parent.console_window.console_output.append(f"Qt Version: {QtCore.QT_VERSION_STR}")
        self.parent.console_window.console_output.append(f"PyQt Version: {QtCore.PYQT_VERSION_STR}")
        
        self.parent.console_window.console_output.append("\n=== Loaded Modules ===")
        for name, module in sorted(sys.modules.items()):
            if hasattr(module, '__version__'):
                self.parent.console_window.console_output.append(f"{name}: {module.__version__}")
        
        # Force update
        self.parent.console_window.console_output.repaint()
class ConsoleWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Console Output")
        self.setMinimumSize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create text display
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: Consolas, monospace;
                padding: 8px;
            }
        """)
        layout.addWidget(self.console_output)
        
        # Add clear and close buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console_output.clear)
        button_layout.addWidget(clear_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.hide)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def write(self, text):
        try:
            print(f"DEBUG: Writing to console: {text!r}", file=sys.__stdout__)  # Debug to real stdout
            self.console_output.append(text.rstrip())
            self.console_output.repaint()
        except Exception as e:
            print(f"ERROR in console write: {e}", file=sys.__stdout__)
        
    def flush(self):
        pass

def main():
    try:
        # Enable high DPI scaling
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Force the color palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor('#f0f0f0'))
        palette.setColor(QPalette.ColorRole.WindowText, QColor('#000000'))
        palette.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#f7f7f7'))
        palette.setColor(QPalette.ColorRole.Text, QColor('#000000'))
        palette.setColor(QPalette.ColorRole.Button, QColor('#f0f0f0'))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor('#000000'))
        palette.setColor(QPalette.ColorRole.Link, QColor('#0078d7'))
        palette.setColor(QPalette.ColorRole.Highlight, QColor('#0078d7'))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
        app.setPalette(palette)
        
        # Apply stylesheet and font
        app.setStyleSheet(MODERN_LIGHT_STYLE)
        font = app.font()
        font.setPointSize(9)
        app.setFont(font)
        
        # Create and show window
        window = MetadataEditor()
        window.show()
        window.setWindowState(Qt.WindowState.WindowActive)
        window.raise_()
        window.activateWindow()
        QApplication.processEvents()
        
        return app.exec()

    except Exception as e:
        with open('error_log.txt', 'w') as f:
            f.write(f"Error during startup: {str(e)}\n")
            f.write(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())