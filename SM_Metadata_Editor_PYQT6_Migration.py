import sys
import os
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

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QFrame, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyle, QFileDialog, QMessageBox,
    QDialog, QToolButton, QMenu, QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QAction  # Add QAction here

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
    'commit': 80
}
SHAZAM_BUTTON_NORMAL = {
    "text": "Shazam Mode: OFF",
    "style": "QPushButton { background-color: #4a90e2; }"
}
SHAZAM_BUTTON_ACTIVE = {
    "text": "SHAZAM ON!",
    "style": "QPushButton { background-color: lightgreen; }"
}

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
            
        for i, line in enumerate(content):
            for key, value in metadata.items():
                if line.startswith(f'#{key}:'):
                    content[i] = f'#{key}:{value};\n'
                    
        try:
            with open(filepath, 'w', encoding=encoding) as file:
                file.writelines(content)
            return True
        except Exception:
            return False
            
class MetadataEditor(QMainWindow):
    def __init__(self):
        super().__init__()
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
        self.table.setColumnCount(10)
        
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
        
        # Set headers
        headers = ['', 'Actions', 'Type', 'Pack', 'Title', 'Subtitle', 'Artist', 'Genre', 'Status', 'Commit']
        self.table.setHorizontalHeaderLabels(headers)
        
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
        
    def create_file_entry_with_type(self, filepaths, file_type, parent_dir, title, subtitle, artist, genre, music_file):
        """Create a file entry with specified type in the table"""
        try:
            # Initialize table if not already done
            if not hasattr(self, 'table'):
                self.table = QTableWidget()
                self.setup_table()
                
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Store entry data
            entry_data = {
                'row': row,
                'filepaths': filepaths,
                'original_values': {
                    'title': title,
                    'subtitle': subtitle,
                    'artist': artist,
                    'genre': genre
                }
            }

            # Create checkbox column
            checkbox = QCheckBox()
            checkbox.setVisible(False)
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, checkbox_container)
            entry_data['checkbox'] = checkbox

            # Create action buttons
            action_widget = self.create_action_buttons(row, filepaths, music_file)
            self.table.setCellWidget(row, 1, action_widget)

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

            # Store the entry data
            if not hasattr(self, 'file_entries'):
                self.file_entries = []
            self.file_entries.append(entry_data)
            
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
        """Commit changes for a specific row"""
        try:
            entry = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry:
                return
            
            # Get current values from table
            metadata = {
                'TITLE': self.table.item(row, 4).text() if self.table.item(row, 4) else '',
                'SUBTITLE': self.table.item(row, 5).text() if self.table.item(row, 5) else '',
                'ARTIST': self.table.item(row, 6).text() if self.table.item(row, 6) else '',
                'GENRE': self.table.item(row, 7).text() if self.table.item(row, 7) else ''
            }
            
            success = True
            for filepath in filepaths:
                if not MetadataUtil.write_metadata(filepath, metadata):
                    success = False
                    break
            
            if success:
                # Update original values
                entry['original_values'].update({
                    'title': metadata['TITLE'],
                    'subtitle': metadata['SUBTITLE'],
                    'artist': metadata['ARTIST'],
                    'genre': metadata['GENRE']
                })
                
                # Clear existing status cell first
                self.table.removeCellWidget(row, 8)
                self.table.setItem(row, 8, QTableWidgetItem(""))
                
                # Update status to checkmark
                status_container = QWidget()
                status_layout = QHBoxLayout(status_container)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                status_label = QLabel("✓")
                status_label.setStyleSheet("color: #32CD32;")  # Lime green
                status_label.setToolTip("Changes saved")
                status_layout.addWidget(status_label)
                
                self.table.setCellWidget(row, 8, status_container)
                self.table.removeCellWidget(row, 9)  # Remove commit button
                
                # Update commit all button
                self.update_commit_all_button()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to save changes to one or more files."
                )
            
        except Exception as e:
            print(f"Error in commit_changes: {str(e)}")
            traceback.print_exc()

    def commit_all_changes(self):
        """Commit all pending changes"""
        try:
            # Find all rows with uncommitted changes
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
                    entry = next((e for e in self.file_entries if e['row'] == row), None)
                    if entry:
                        self.commit_changes(row, entry['filepaths'])
        except Exception as e:
            print(f"Error in commit_all_changes: {str(e)}")
            traceback.print_exc()

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

    def play_audio(self, music_path, play_btn, row):
        """Play audio file and handle Shazam if enabled"""
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
                # Button was deleted, reset current_playing
                self.current_playing = None
            except Exception as e:
                print(f"Error handling current playing button: {str(e)}")
                self.current_playing = None

            directory = os.path.dirname(music_path)
            base_name = os.path.splitext(os.path.basename(music_path))[0]
            found_playable = False
            actual_path = music_path

            print(f"Attempting to play: {music_path}")
            print(f"Shazam mode is: {self.shazam_mode}")
            print(f"Row is: {row}")

            # Try exact path first
            if os.path.exists(music_path):
                try:
                    pygame.mixer.music.load(music_path)
                    found_playable = True
                    actual_path = music_path
                    print("Found exact file match")
                except Exception as e:
                    print(f"Failed to load exact file: {str(e)}")

            # If exact path fails, try to find a matching audio file
            if not found_playable:
                print(f"Searching directory for matching file...")
                try:
                    matching_files = []
                    for file in os.listdir(directory):
                        if file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                            full_path = os.path.join(directory, file)
                            matching_files.append(full_path)
                        
                        # Sort by size and try each one
                        if matching_files:
                            matching_files.sort(key=lambda x: os.path.getsize(x))
                            for full_path in matching_files:
                                try:
                                    pygame.mixer.music.load(full_path)
                                    actual_path = full_path
                                    found_playable = True
                                    print(f"Found playable audio file: {full_path}")
                                    break
                                except Exception as e:
                                    print(f"Failed to load file: {str(e)}")

                except Exception as e:
                    print(f"Error searching directory: {str(e)}")

            try:
                if found_playable:
                    pygame.mixer.music.play()
                    play_btn.setText("⏹")
                    self.current_playing = play_btn
                    print("Playing audio file")
                else:
                    print(f"No playable audio file found for: {music_path}")
                    play_btn.setText("🔇")
                    play_btn.setToolTip("No audio file found")
                    # Don't disable the button
            except Exception as e:
                print(f"Error updating button state: {str(e)}")

            # Always run Shazam if enabled
            if self.shazam_mode:
                print("Starting Shazam analysis...")
                try:
                    self.run_shazam_analysis(actual_path, row)
                except Exception as e:
                    print(f"Error running Shazam: {str(e)}")
                    if not found_playable:
                        print("No Shazam results found - no playable audio")
                        
        except Exception as e:
            print(f"Error playing audio: {str(e)}")
            traceback.print_exc()

    def run_shazam_analysis(self, file_path, row):
        """Run Shazam analysis in the background"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def run_analysis():
                try:
                    shazam = Shazam()
                    result = await shazam.recognize(file_path)
                    
                    if result and 'track' in result:
                        track = result['track']
                        shazam_data = {
                            'title': track.get('title', ''),
                            'artist': track.get('subtitle', ''),
                            'genre': track.get('genres', {}).get('primary', ''),
                            'images': {'coverart': track['share']['image']} if 'share' in track and 'image' in track['share'] else {}
                        }
                        # Use QTimer to safely update UI from main thread
                        QTimer.singleShot(0, lambda: self.show_shazam_results(row, shazam_data))
                    else:
                        print("No Shazam results found")
                except Exception as e:
                    print(f"Error in Shazam analysis: {str(e)}")
                    traceback.print_exc()
                finally:
                    loop.stop()

            # Run the analysis in the event loop
            loop.run_until_complete(run_analysis())
            loop.close()

        except Exception as e:
            print(f"Error starting Shazam analysis: {str(e)}")
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
                
            # Count total songs first
            total_songs = 0
            for pack_dir in new_pack_paths:
                for song_dir in next(os.walk(pack_dir))[1]:
                    full_song_dir = os.path.join(pack_dir, song_dir)
                    has_sm_or_ssc = False
                    for file in os.listdir(full_song_dir):
                        if file.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                            if not has_sm_or_ssc:  # Only count once per song directory
                                total_songs += 1
                                has_sm_or_ssc = True

            # Add the new pack paths to existing ones
            self.selected_directories.update(new_pack_paths)
            
            # Create progress dialog with better styling
            progress = QMessageBox(self)
            progress.setWindowTitle("Loading")
            progress.setText(f"Loading selected packs... (0/{total_songs} songs)")
            progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress.setStyleSheet("""
                QMessageBox {
                    min-width: 300px;
                    min-height: 100px;
                }
            """)
            progress.show()
            QApplication.processEvents()
            
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
                progress.setText(f"Loading selected packs... ({loaded_songs}/{total_songs} songs)")
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
            for entry in self.file_entries:
                self.table.setRowHidden(entry['row'], False)
            self.update_display_count(total_count, total_count)
            return
        
        for entry in self.file_entries:
            row = entry['row']
            
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
            hide_row = search_text and search_text not in searchable_text
            
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
            entry = next((e for e in self.file_entries if e['row'] == row), None)
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
                   • Click "Compare Artwork" to compare and 
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
            entry_data = next((e for e in self.file_entries if e['row'] == row), None)
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
            # Get the entry data first
            entry_data = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry_data:
                print(f"Warning: Could not find entry data for row {row}")
                return

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
        if not selected_credits:
            # Show all entries
            for entry in self.file_entries:
                self.table.setRowHidden(entry['row'], False)
            self.statusBar().showMessage("Ready")
            return

        shown_count = 0
        total_count = len(self.file_entries)
        
        for entry in self.file_entries:
            show_entry = False
            entry_has_credits = False
            entry_credits = set()
            
            # Collect credits from all files in the entry
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if metadata.get('CREDITS'):
                    valid_credits = {credit.lower() for credit in metadata['CREDITS'] 
                                   if credit and not credit.isspace()}
                    if valid_credits:
                        entry_has_credits = True
                        entry_credits.update(valid_credits)
        
            # Check if we should show this entry
            if not entry_has_credits and 'no credits! :(' in selected_credits:
                # Show entries with no credits when "no credits! :(" is selected
                show_entry = True
                shown_count += 1
            elif entry_credits and (entry_credits & selected_credits):
                # Show entries that have any of the selected credits
                show_entry = True
                shown_count += 1
            
            self.table.setRowHidden(entry['row'], not show_entry)
        
        # Update display count
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
            field_map = {
                3: 'pack',
                4: 'title',
                5: 'subtitle',
                6: 'artist',
                7: 'genre'
            }
            
            if column not in field_map:
                return
            
            field = field_map[column]
            self.sort_reverse[field] = not self.sort_reverse[field]

            # 1. Get sort keys from the entry metadata directly
            entries_with_keys = []
            for entry in self.file_entries:
                if field == 'pack':
                    item = self.table.item(entry['row'], 3)
                    sort_key = item.text().lower() if item else ''
                else:
                    # Use the original metadata widget from entry
                    widget = entry['metadata'][field]
                    sort_key = widget.text().lower() if widget else ''
                entries_with_keys.append((sort_key, entry))

            # 2. Sort entries
            entries_with_keys.sort(key=lambda x: x[0], reverse=self.sort_reverse[field])

            # 3. Disable table updates
            self.table.setUpdatesEnabled(False)
            
            try:
                # 4. Store current widgets and items
                old_state = {}
                for i in range(self.table.rowCount()):
                    old_state[i] = {
                        'widgets': {
                            col: self.table.cellWidget(i, col)
                            for col in range(self.table.columnCount())
                            if self.table.cellWidget(i, col)
                        },
                        'items': {
                            col: self.table.item(i, col).text() if self.table.item(i, col) else ''
                            for col in range(self.table.columnCount())
                        },
                        'height': self.table.rowHeight(i),
                        'hidden': self.table.isRowHidden(i)
                    }

                # 5. Clear table content without destroying widgets
                for row in range(self.table.rowCount()):
                    for col in range(self.table.columnCount()):
                        self.table.takeItem(row, col)
                        if self.table.cellWidget(row, col):
                            self.table.removeCellWidget(row, col)

                # 6. Restore content in new order
                for new_index, (_, entry) in enumerate(entries_with_keys):
                    old_row = entry['row']
                    entry['row'] = new_index  # Update entry reference

                    # Restore widgets and items
                    for col in range(self.table.columnCount()):
                        if col in old_state[old_row]['widgets']:
                            self.table.setCellWidget(new_index, col, old_state[old_row]['widgets'][col])
                        else:
                            self.table.setItem(new_index, col, QTableWidgetItem(old_state[old_row]['items'][col]))

                    # Restore row properties
                    self.table.setRowHeight(new_index, old_state[old_row]['height'])
                    self.table.setRowHidden(new_index, old_state[old_row]['hidden'])

            finally:
                self.table.setUpdatesEnabled(True)
                self.table.viewport().update()

        except Exception as e:
            print(f"Sort error: {str(e)}")
            self.table.setUpdatesEnabled(True)
            QMessageBox.warning(self, "Sort Error", f"Failed to sort table: {str(e)}")

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
        """Save artwork to song directory"""
        try:
            entry = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry:
                return
            
            directory = os.path.dirname(entry['filepaths'][0])
            image.save(os.path.join(directory, 'bg.png'))
            QMessageBox.information(self, "Success", "Artwork saved as bg.png")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save artwork: {str(e)}")
            
    def create_action_buttons(self, row, filepaths, music_file=''):
        """Create action buttons (play, edit, folder) for a table row"""
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(5)
        
        # Play button
        play_btn = QToolButton()
        play_btn.setText("▶")
        play_btn.setMinimumWidth(30)
        if music_file:
            play_btn.clicked.connect(
                lambda: self.play_audio(
                    os.path.join(os.path.dirname(filepaths[0]), music_file), 
                    play_btn,
                    row  # Add the row parameter here
                )
            )
        else:
            play_btn.setEnabled(False)
            play_btn.setToolTip("No music file found")
        action_layout.addWidget(play_btn)
        
        # Edit button
        edit_btn = QPushButton("✎")
        edit_btn.setToolTip("Edit Metadata")
        edit_btn.setMinimumWidth(30)
        edit_btn.clicked.connect(lambda: self.edit_metadata(filepaths))
        action_layout.addWidget(edit_btn)
        
        # Open folder button
        folder_btn = QPushButton("📂")
        folder_btn.setToolTip("Open Folder")
        folder_btn.setMinimumWidth(30)
        folder_btn.clicked.connect(lambda: self.open_file_location(os.path.dirname(filepaths[0])))
        action_layout.addWidget(folder_btn)
        
        # Add stretch to ensure buttons are left-aligned
        action_layout.addStretch()
        
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
        """Handle cleanup when the application closes"""
        try:
            self.cleanup_audio()
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            if pygame.get_init():
                pygame.quit()
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
            # Find local jacket image
            local_image = None
            current_jacket_ref = None
            
            # First check for explicit reference in the SM/SSC files
            entry_data = next((e for e in self.file_entries if e['row'] == row), None)
            if entry_data:
                for filepath in entry_data['filepaths']:
                    content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                    if content:
                        for line in content:
                            if line.startswith('#JACKET:'):
                                ref = line.split(':', 1)[1].strip().rstrip(';')
                                if ref:
                                    current_jacket_ref = ref
                                    exact_path = os.path.join(song_directory, ref)
                                    try:
                                        local_image = Image.open(exact_path)
                                        break
                                    except Exception:
                                        # If exact match fails, try wildcard search
                                        base_name = os.path.splitext(ref)[0]
                                        for file in os.listdir(song_directory):
                                            if file.lower().endswith(('.jpg', '.jpeg', '.png')) and base_name.lower() in file.lower():
                                                try:
                                                    local_image = Image.open(os.path.join(song_directory, file))
                                                    break
                                                except Exception:
                                                    continue
                    if local_image:
                        break

            # If no image found from explicit reference, look for jacket.png
            if not local_image:
                for file in os.listdir(song_directory):
                    if file.lower() in ['jacket.png', 'jacket.jpg', 'jacket.jpeg']:
                        try:
                            local_image = Image.open(os.path.join(song_directory, file))
                            current_jacket_ref = file
                            break
                        except Exception:
                            continue

            # Download Shazam image
            response = requests.get(shazam_url)
            shazam_image = Image.open(BytesIO(response.content))
            
            # Create comparison dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Compare Artwork")
            dialog.setMinimumWidth(500)
            layout = QVBoxLayout(dialog)
            
            # Create image comparison area
            images_layout = QHBoxLayout()
            layout.addLayout(images_layout)
            
            # Left side (Current)
            left_frame = QFrame()
            left_layout = QVBoxLayout(left_frame)
            left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if local_image:
                local_label = QLabel()
                local_pixmap = ImageQt.toqpixmap(local_image.resize((200, 200)))
                local_label.setPixmap(local_pixmap)
                left_layout.addWidget(local_label)
                left_layout.addWidget(QLabel(f"Current: {current_jacket_ref}"))
                left_layout.addWidget(QLabel(f"Size: {local_image.size[0]}x{local_image.size[1]}"))
            else:
                left_layout.addWidget(QLabel("No current artwork found"))
            
            images_layout.addWidget(left_frame)
            
            # Right side (Shazam)
            right_frame = QFrame()
            right_layout = QVBoxLayout(right_frame)
            right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
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
            update_btn.clicked.connect(lambda: self.save_artwork(row, shazam_image))
            button_layout.addWidget(update_btn)
            
            dialog.exec()
            
        except Exception as e:
            print(f"Error comparing artwork: {str(e)}")
            traceback.print_exc()

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
            # Get the entry data
            entry = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry:
                return

            # Check if any values have changed
            has_changes = False
            for col, field in [(4, 'title'), (5, 'subtitle'), (6, 'artist'), (7, 'genre')]:
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
                self.table.removeCellWidget(row, 8)
                self.table.removeCellWidget(row, 9)
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
        for entry in self.file_entries:
            self.table.setRowHidden(entry['row'], False)
            
        # Update display count to show all entries
        self.update_display_count(total_count, total_count)

    def on_cell_changed(self, row, col):
        """Handle cell value changes"""
        try:
            # Only process editable columns
            if col not in [4, 5, 6, 7]:  # title, subtitle, artist, genre
                return
                
            entry = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry:
                return
                
            # Get current and original values
            current_value = self.table.item(row, col).text()
            field_map = {4: 'title', 5: 'subtitle', 6: 'artist', 7: 'genre'}
            field = field_map[col]
            original_value = entry['original_values'].get(field, '')
            
            if current_value != original_value:
                # Update row status using existing method
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
        """Show the settings dialog"""
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
                            # Get the entry data
                            entry = next((e for e in self.file_entries if e['row'] == row), None)
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
            warning_text = ("Warning: Selecting many packs may cause performance issues.\n"
                          "Consider working with fewer packs at a time for better responsiveness.")
            warning_label = QLabel(warning_text)
            warning_label.setStyleSheet("color: red; font-weight: bold;")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)
            
            # Create scroll area
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_widget = QWidget()
            scroll_layout = QGridLayout(scroll_widget)
            scroll_layout.setSpacing(4)
            
            # Calculate button width
            # Total width of dialog is typically around 800px
            # Subtract margins (12px * 2), spacing between buttons (4px * 2)
            # Divide by 3 for three columns
            button_width = 250  # (800 - (12 * 2) - (4 * 2)) / 3
            
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
                "• ▶ (play): Preview song audio (if available)",
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
        self.setMinimumWidth(300)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Export section
        export_frame = QFrame()
        export_layout = QHBoxLayout(export_frame)
        
        export_btn = QPushButton("Export to CSV")
        export_btn.setToolTip("Export visible table data to CSV file")
        export_btn.clicked.connect(self.parent.export_to_csv)
        export_layout.addWidget(export_btn)
        
        layout.addWidget(export_frame)
        
        # Add a stretch to push everything up
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

def main():
    # Enable high DPI scaling
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set default font
    font = app.font()
    font.setPointSize(9)
    app.setFont(font)
    
    # Create and show main window
    window = MetadataEditor()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
