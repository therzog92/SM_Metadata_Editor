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

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QFrame, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStyle, QFileDialog, QMessageBox,
    QDialog, QToolButton, QMenu, QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor

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
        self.temp_widgets = []  # Add this if missing
        self.search_credits_button = None  # Add this if missing
        self.search_frame = None  # Add this if missing
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
        
        # Add search box with clear button in the middle
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.apply_search_filter)
        search_layout.addWidget(self.search_box)
        
        # Add clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search)
        self.clear_button.setVisible(False)  # Hidden by default
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
        
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_bulk_edit)
        bulk_layout.addWidget(apply_button)
        
        # Add to main layout and hide initially
        self.main_layout.addWidget(self.bulk_edit_controls)
        self.bulk_edit_controls.hide()
        
    def setup_table(self):
        """Set up the table widget"""
        # Set up columns
        columns = ['', 'Actions', 'Type', 'Pack', 'Title', 'Subtitle', 'Artist', 'Genre', '', '']
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Enable single-click editing
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.AllEditTriggers  # Change this line to enable all edit triggers
        )
        
        # Set column widths
        for col, width in enumerate(COLUMN_WIDTHS.values()):
            self.table.setColumnWidth(col, width)
        
        # Connect cell change signal
        self.table.cellChanged.connect(self.on_cell_changed)
        
        # Set table properties
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        
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

            # Set file type and parent directory
            self.table.setItem(row, 2, QTableWidgetItem(file_type))
            self.table.setItem(row, 3, QTableWidgetItem(parent_dir))

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

            # Add empty status and commit columns
            self.table.setItem(row, 8, QTableWidgetItem(""))
            self.table.setItem(row, 9, QTableWidgetItem(""))

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

    def play_audio(self, music_path, play_btn):
        """Play audio file and optionally trigger Shazam analysis"""
        if not self.audio_enabled:
            QMessageBox.warning(self, "Audio Disabled", 
                "Audio playback is currently disabled due to initialization error.")
            return
        
        try:
            # Get row from play button's parent widget
            row = -1
            parent = play_btn.parent()
            if parent:
                index = self.table.indexAt(parent.pos())
                if index.isValid():
                    row = index.row()

            # Handle stop button press
            if self.current_playing == play_btn:
                pygame.mixer.music.stop()
                play_btn.setText("▶")
                self.current_playing = None
                return

            # Stop any currently playing audio
            if self.current_playing:
                pygame.mixer.music.stop()
                self.current_playing.setText("▶")
                self.current_playing = None

            # Clean and normalize the path
            music_path = os.path.normpath(music_path.strip())
            directory = os.path.dirname(music_path)
            music_name = os.path.basename(music_path)
            base_name = os.path.splitext(music_name)[0]

            found_playable = False
            actual_path = None

            # First try exact path
            if os.path.exists(music_path):
                try:
                    pygame.mixer.music.load(music_path)
                    actual_path = music_path
                    found_playable = True
                except Exception as e:
                    print(f"Exact path failed: {str(e)}")

            # If exact path fails, try to find a matching audio file
            if not found_playable:
                print(f"Searching directory for matching file...")
                try:
                    for file in os.listdir(directory):
                        file_base = os.path.splitext(file)[0]
                        if (file_base.lower() == base_name.lower() and 
                            file.lower().endswith(tuple(SUPPORTED_AUDIO))):
                            full_path = os.path.join(directory, file)
                            try:
                                pygame.mixer.music.load(full_path)
                                actual_path = full_path
                                found_playable = True
                                break
                            except Exception as e:
                                print(f"Failed to load alternative file: {str(e)}")
                except Exception as e:
                    print(f"Error searching directory: {str(e)}")

            # If still not found, try any audio file in the directory
            if not found_playable:
                try:
                    for file in os.listdir(directory):
                        if file.lower().endswith(tuple(SUPPORTED_AUDIO)):
                            full_path = os.path.join(directory, file)
                            try:
                                pygame.mixer.music.load(full_path)
                                actual_path = full_path
                                found_playable = True
                                break
                            except Exception as e:
                                print(f"Failed to load fallback file: {str(e)}")
                except Exception as e:
                    print(f"Error in fallback search: {str(e)}")

            if found_playable:
                pygame.mixer.music.play()
                play_btn.setText("⏹")
                self.current_playing = play_btn
                
                # Only run Shazam if mode is on and we have a valid row
                if self.shazam_mode and row != -1:
                    print("Starting Shazam analysis...")
                    self.run_shazam_analysis(actual_path, row)
                return

            # If we get here, no playable file was found
            print(f"No playable audio file found for: {music_path}")

        except Exception as e:
            print(f"Error in play_audio: {str(e)}")
            traceback.print_exc()
            if play_btn:
                play_btn.setText("▶")
                self.current_playing = None

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
            # Clear existing directories
            self.selected_directories.clear()
            
            # Add the selected pack paths directly
            self.selected_directories.update(selected_pack_paths)
            
            # Create progress dialog with better styling
            progress = QMessageBox(self)
            progress.setWindowTitle("Loading")
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
            
            # Load files directly
            self.table.setRowCount(0)  # Clear existing rows
            self.file_entries.clear()
            self.load_files_from_all_directories()
            
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

    def load_files_from_all_directories(self):
        """Load all StepMania files from selected directories"""
        try:
            self.table.setSortingEnabled(False)
            
            # Clear existing table
            self.table.setRowCount(0)
            self.file_entries.clear()
            
            # Show UI elements (with safe checks)
            if hasattr(self, 'clear_button') and self.clear_button:
                self.clear_button.show()
            if hasattr(self, 'bulk_edit_btn') and self.bulk_edit_btn:
                self.bulk_edit_btn.show()
            if hasattr(self, 'search_credits_button') and self.search_credits_button:
                self.search_credits_button.show()
            if hasattr(self, 'search_frame') and self.search_frame:
                self.search_frame.show()
            
            # Track files by directory for grouping
            files_by_dir = defaultdict(list)
            
            # Find all SM/SSC files in selected directories
            for directory in self.selected_directories:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                            filepath = os.path.join(root, file)
                            files_by_dir[os.path.dirname(filepath)].append(filepath)
            
            # Process each directory's files
            for directory, filepaths in files_by_dir.items():
                try:
                    # Group files by their base name (without extension)
                    grouped_files = {}
                    for filepath in filepaths:
                        base_name = os.path.splitext(os.path.basename(filepath))[0]
                        if base_name not in grouped_files:
                            grouped_files[base_name] = {'sm': None, 'ssc': None}
                        ext = os.path.splitext(filepath)[1].lower()
                        if ext == '.sm':
                            grouped_files[base_name]['sm'] = filepath
                        elif ext == '.ssc':
                            grouped_files[base_name]['ssc'] = filepath
                    
                    # Process each group of files
                    for base_name, files in grouped_files.items():
                        sm_file = files['sm']
                        ssc_file = files['ssc']
                        
                        # Determine file type display
                        if sm_file and ssc_file:
                            # Both files exist, check if metadata matches
                            sm_metadata = MetadataUtil.read_metadata(sm_file)
                            ssc_metadata = MetadataUtil.read_metadata(ssc_file)
                            
                            # Compare relevant metadata fields
                            fields_match = all(
                                sm_metadata.get(field, '').strip() == ssc_metadata.get(field, '').strip()
                                for field in ['TITLE', 'SUBTITLE', 'ARTIST', 'GENRE']
                            )
                            
                            if fields_match:
                                # Metadata matches, create single entry with both files
                                self.create_file_entry_with_type(
                                    [sm_file, ssc_file],
                                    "sm+ssc",
                                    parent_dir=os.path.basename(os.path.dirname(directory)),
                                    title=ssc_metadata.get('TITLE', '').strip(),
                                    subtitle=ssc_metadata.get('SUBTITLE', '').strip(),
                                    artist=ssc_metadata.get('ARTIST', '').strip(),
                                    genre=ssc_metadata.get('GENRE', '').strip(),
                                    music_file=ssc_metadata.get('MUSIC', '')
                                )
                            else:
                                # Metadata differs, create separate entries
                                if sm_file:
                                    self.create_file_entry_with_type(
                                        [sm_file],
                                        "sm",  # Explicitly mark as SM file
                                        parent_dir=os.path.basename(os.path.dirname(directory)),
                                        title=sm_metadata.get('TITLE', '').strip(),
                                        subtitle=sm_metadata.get('SUBTITLE', '').strip(),
                                        artist=sm_metadata.get('ARTIST', '').strip(),
                                        genre=sm_metadata.get('GENRE', '').strip(),
                                        music_file=sm_metadata.get('MUSIC', '')
                                    )
                                if ssc_file:
                                    self.create_file_entry_with_type(
                                        [ssc_file],
                                        "ssc",  # Explicitly mark as SSC file
                                        parent_dir=os.path.basename(os.path.dirname(directory)),
                                        title=ssc_metadata.get('TITLE', '').strip(),
                                        subtitle=ssc_metadata.get('SUBTITLE', '').strip(),
                                        artist=ssc_metadata.get('ARTIST', '').strip(),
                                        genre=ssc_metadata.get('GENRE', '').strip(),
                                        music_file=ssc_metadata.get('MUSIC', '')
                                    )
                        else:
                            # Single file
                            file_to_use = sm_file or ssc_file
                            metadata = MetadataUtil.read_metadata(file_to_use)
                            self.create_file_entry_with_type(
                                [file_to_use],
                                "sm" if sm_file else "ssc",
                                parent_dir=os.path.basename(os.path.dirname(directory)),
                                title=metadata.get('TITLE', '').strip(),
                                subtitle=metadata.get('SUBTITLE', '').strip(),
                                artist=metadata.get('ARTIST', '').strip(),
                                genre=metadata.get('GENRE', '').strip(),
                                music_file=metadata.get('MUSIC', '')
                            )
                    
                except Exception as e:
                    print(f"Error processing directory {directory}: {str(e)}")
                    continue
                
        finally:
            self.table.setSortingEnabled(True)
            # Update status message...

    def apply_search_filter(self):
        search_text = self.search_box.text().lower()  # Changed from search_input to search_box
        shown_count = 0
        total_count = len(self.file_entries)
        
        # Show/hide clear button based on search text
        self.clear_button.setVisible(bool(search_text))
        
        for entry in self.file_entries:
            show_entry = False if search_text else True
            
            if search_text:
                # Check all relevant fields for the search text
                for field in ['title', 'subtitle', 'artist', 'genre']:
                    item = self.table.item(entry['row'], self.get_column_index(field))
                    if item and search_text in item.text().lower():
                        show_entry = True
                        break
            
            self.table.setRowHidden(entry['row'], not show_entry)
            if show_entry:
                shown_count += 1
        
        # Update display count
        self.update_display_count(shown_count, total_count)
        
        # Update status bar
        if search_text:
            self.statusBar().showMessage(f"Search filter applied")
        else:
            self.statusBar().showMessage("Ready")
        
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
        self.table.setColumnHidden(0, not self.bulk_edit_enabled)
        
        if self.bulk_edit_enabled:
            self.bulk_edit_btn.setText("Exit Bulk Edit")  # Changed from bulk_edit_button to bulk_edit_btn
            self.bulk_edit_controls.show()
            # Show checkboxes
            for entry in self.file_entries:
                if 'checkbox' in entry:  # Add safety check
                    entry['checkbox'].setVisible(True)
        else:
            self.bulk_edit_btn.setText("Bulk Edit: OFF")  # Changed from bulk_edit_button to bulk_edit_btn
            self.bulk_edit_controls.hide()
            # Hide checkboxes and clear selection
            for entry in self.file_entries:
                if 'checkbox' in entry:  # Add safety check
                    entry['checkbox'].setVisible(False)
                    entry['checkbox'].setChecked(False)
            self.selected_entries.clear()

    def apply_bulk_edit(self):
        selected_entries = [
            entry for entry in self.file_entries
            if entry['checkbox'].isChecked()
        ]
        
        if not selected_entries:
            return
        
        # Get values from bulk edit fields
        new_values = {
            'subtitle': self.bulk_fields['subtitle'].text(),
            'artist': self.bulk_fields['artist'].text(),
            'genre': self.bulk_fields['genre'].text()
        }
        
        # Apply to each selected entry
        for entry in selected_entries:
            for field, value in new_values.items():
                if value:  # Only update if value is not empty
                    entry['metadata'][field].setText(value)
                    self.on_entry_change(entry['row'], entry['filepaths'], field)

    def toggle_shazam_mode(self):
        """Toggle Shazam mode on/off"""
        self.shazam_mode = not self.shazam_mode
        
        if self.shazam_mode:
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
        if not self.shazam_mode:  # Add this check
            return
        
        try:
            entry_data = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry_data:
                print("No entry data found for row")
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
                        
                        print(f"Field: {field}, Current: {current_value}, New: {new_value}")
                        
                        # Create container widget
                        container = QWidget()
                        layout = QVBoxLayout(container)
                        layout.setContentsMargins(4, 4, 4, 4)
                        layout.setSpacing(4)
                        
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
                artwork_btn = QPushButton("Compare Artwork")
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
                
                # Add to actions cell
                actions_widget = self.table.cellWidget(row, 1)
                if actions_widget:
                    actions_layout = actions_widget.layout()
                    actions_layout.insertWidget(3, artwork_btn)  # Insert before the stretch
                
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
        all_credits = set()
        has_no_credits = False
        
        for entry in self.file_entries:
            entry_has_credits = False
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if 'CREDITS' in metadata:
                    valid_credits = {credit for credit in metadata['CREDITS'] 
                                   if credit and not credit.isspace()}
                    if valid_credits:
                        entry_has_credits = True
                        all_credits.update(valid_credits)
            
            if not entry_has_credits:
                has_no_credits = True
        
        if has_no_credits:
            all_credits.add("No Credits! :(")
        
        return all_credits

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
            entry_credits = set()
            
            # Collect credits from all files in the entry
            for filepath in entry['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if 'CREDITS' in metadata:
                    entry_credits.update(metadata['CREDITS'])
            
            # Show entry if it has any of the selected credits
            if entry_credits & selected_credits:
                show_entry = True
                shown_count += 1
            
            self.table.setRowHidden(entry['row'], not show_entry)
        
        # Update display count
        self.update_display_count(shown_count, total_count)
        
        # Update status bar
        self.statusBar().showMessage("Credit filter applied")

    def clear_directories(self):
        """Clear all loaded directories and reset the table"""
        self.selected_directories.clear()
        self.table.setRowCount(0)
        self.file_entries.clear()
        
        # Hide buttons that should only show when files are loaded
        self.clear_button.hide()
        self.bulk_edit_button.hide()
        self.search_credits_button.hide()
        self.search_frame.hide()
        self.commit_all_button.hide()
        
        # Reset status bar
        self.statusBar().showMessage("Ready")

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
                    play_btn
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
        """Clear the search box"""
        self.search_box.clear()
        self.clear_button.setVisible(False)

    def on_cell_changed(self, row, col):
        """Handle cell value changes"""
        try:
            # Only process editable metadata columns
            if col not in [4, 5, 6, 7]:  # title, subtitle, artist, genre
                return
                
            # Get the entry data
            entry = next((e for e in self.file_entries if e['row'] == row), None)
            if not entry:
                return
                
            # Get the field name based on column
            field_map = {4: 'title', 5: 'subtitle', 6: 'artist', 7: 'genre'}
            field = field_map.get(col)
            
            # Get current value
            item = self.table.item(row, col)
            if not item:
                return
                
            current_value = item.text()
            original_value = entry['original_values'][field]
            
            if current_value != original_value:
                # Create warning status
                status_container = QWidget()
                status_layout = QHBoxLayout(status_container)
                status_layout.setContentsMargins(0, 0, 0, 0)
                status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                status_label = QLabel("⚠")
                status_label.setStyleSheet("color: #FF8C00;")  # Dark orange
                status_label.setToolTip("Unsaved changes")
                status_layout.addWidget(status_label)
                
                self.table.setCellWidget(row, 8, status_container)
                
                # Create commit button
                commit_container = QWidget()
                commit_layout = QHBoxLayout(commit_container)
                commit_layout.setContentsMargins(2, 2, 2, 2)
                
                commit_btn = QPushButton("Commit?")
                commit_btn.clicked.connect(lambda: self.commit_changes(row, entry['filepaths']))
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
                
                # Update commit all button
                self.update_commit_all_button()
                
        except Exception as e:
            print(f"Error in on_cell_changed: {str(e)}")
            traceback.print_exc()

    def update_display_count(self, shown_count, total_count):
        """Update the display count indicator"""
        if shown_count == total_count:
            self.display_count_frame.hide()
        else:
            self.display_count_label.setText(f"Displaying {shown_count} of {total_count} songs")
            self.display_count_frame.show()

class PackSelectorDialog(QDialog):
    def __init__(self, parent, directories):
        super().__init__(parent)
        self.setWindowTitle("Select Packs")
        self.setMinimumSize(800, 600)
        self.setModal(True)  # Ensure dialog is modal
        
        # Convert directories to list to ensure stable ordering
        self.directories = sorted(directories, key=str.lower)
        self.selected_packs = set()
        self.buttons = {}
        self.is_accepting = False
        
        # Process events before setting up UI
        QApplication.processEvents()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Warning label
        warning_text = ("Warning: Selecting many packs may cause performance issues.\n"
                       "Consider working with fewer packs at a time for better responsiveness.")
        warning_label = QLabel(warning_text)
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        # Create scroll area for pack buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        
        # Create pack buttons
        row = 0
        col = 0
        for pack in self.directories:
            btn = QPushButton(pack)
            btn.setCheckable(True)
            # Store reference to button
            self.buttons[pack] = btn
            # Use a regular function instead of lambda
            btn.clicked.connect(self.create_toggle_handler(pack))
            btn.setToolTip(pack)
            scroll_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 4:
                col = 0
                row += 1
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Button frame
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        
        # Add Select All / Deselect All buttons
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_packs)
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all_packs)
        button_layout.addWidget(deselect_all_btn)
        
        # Add spacer
        button_layout.addStretch()
        
        ok_button = QPushButton("Let's Go!")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addWidget(button_frame)
    
    def create_toggle_handler(self, pack):
        """Create a proper toggle handler for each pack button"""
        def handler(checked):
            self.toggle_pack(pack)
        return handler
    
    def toggle_pack(self, pack):
        """Toggle pack selection state"""
        try:
            if pack in self.selected_packs:
                self.selected_packs.remove(pack)
                self.buttons[pack].setChecked(False)
            else:
                self.selected_packs.add(pack)
                self.buttons[pack].setChecked(True)
        except Exception as e:
            print(f"Error toggling pack {pack}: {str(e)}")
    
    def select_all_packs(self):
        """Select all packs"""
        try:
            self.selected_packs = set(self.directories)
            for btn in self.buttons.values():
                btn.setChecked(True)
        except Exception as e:
            print(f"Error selecting all packs: {str(e)}")
    
    def deselect_all_packs(self):
        """Deselect all packs"""
        try:
            self.selected_packs.clear()
            for btn in self.buttons.values():
                btn.setChecked(False)
        except Exception as e:
            print(f"Error deselecting all packs: {str(e)}")
    
    def accept(self):
        """Override accept to ensure clean exit"""
        if self.is_accepting:
            return
            
        try:
            self.is_accepting = True
            # Ensure we have selections
            if not self.selected_packs:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select at least one pack to continue."
                )
                self.is_accepting = False
                return
                
            # Clean up before accepting
            for btn in self.buttons.values():
                btn.clicked.disconnect()
            self.buttons.clear()
            
            super().accept()
            
        except Exception as e:
            print(f"Error in dialog accept: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_accepting = False
    
    def reject(self):
        """Override reject to ensure clean exit"""
        try:
            # Clean up before rejecting
            for btn in self.buttons.values():
                btn.clicked.disconnect()
            self.buttons.clear()
            
            super().reject()
            
        except Exception as e:
            print(f"Error in dialog reject: {str(e)}")
            import traceback
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
        layout.setSpacing(8)  # Consistent spacing between sections
        
        # Info label
        info_text = ("Select credits to filter songs by their creators.\n"
                    "You can select multiple credits to see all songs by those creators.")
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Select All/Deselect All buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(4)  # Tighter spacing between buttons
        button_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self.select_all_credits)
        button_layout.addWidget(select_all)
        
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(self.deselect_all_credits)
        button_layout.addWidget(deselect_all)
        
        button_layout.addStretch()  # Add stretch like PackSelector
        layout.addWidget(button_frame)
        
        # Create scroll area for credit buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setSpacing(4)  # Add consistent spacing
        
        # Store buttons like in PackSelectorDialog
        self.buttons = {}
        
        # Create credit buttons
        row = 0
        col = 0
        for credit in sorted(self.credits, key=str.lower):
            btn = QPushButton(credit)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # Make buttons expand horizontally
            btn.setMinimumWidth(180)  # Set minimum width for consistency
            btn.clicked.connect(self.create_toggle_handler(credit))  # Use same handler approach as PackSelector
            btn.setToolTip(credit)
            self.buttons[credit] = btn  # Store reference to button
            scroll_layout.addWidget(btn, row, col)
            
            col += 1
            if col >= 4:  # Four columns like PackSelector
                col = 0
                row += 1
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Dialog buttons
        dialog_buttons = QFrame()
        dialog_layout = QHBoxLayout(dialog_buttons)
        
        ok_button = QPushButton("Filter by Credit")
        ok_button.clicked.connect(self.accept)
        dialog_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        dialog_layout.addWidget(cancel_button)
        
        layout.addWidget(dialog_buttons)
        
    def create_toggle_handler(self, credit):
        """Create a proper toggle handler for each credit button"""
        def handler(checked):
            self.toggle_credit(credit)
        return handler
    
    def toggle_credit(self, credit):
        if credit in self.selected_credits:
            self.selected_credits.remove(credit)
        else:
            self.selected_credits.add(credit)
            
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
                "• ✎ (pencil): Open full metadata editor for advanced fields"
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
