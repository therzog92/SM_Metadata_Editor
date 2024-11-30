import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import os
import subprocess
import pygame
from collections import defaultdict
import fnmatch
import asyncio
from shazamio import Shazam
import nest_asyncio
from PIL import Image, ImageTk
import requests
from io import BytesIO
import webbrowser

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
    'status': 50
}
SHAZAM_BUTTON_NORMAL = {
    "text": "Shazam Mode: OFF",
    "style": "Modern.TButton"
}
SHAZAM_BUTTON_ACTIVE = {
    "text": "SHAZAM ON!",
    "style": "Shazam.TButton"
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
        credits = set()  # Create a set for credits
        
        for line in content:
            if line.startswith('#') and ':' in line:
                key, value = line.strip().split(':', 1)
                key = key[1:]  # Remove the # character
                value = value.rstrip(';')
                
                if key == 'CREDIT':  # Special handling for CREDIT field
                    credits.add(value)
                else:
                    metadata[key] = value
        
        metadata['CREDITS'] = credits  # Store all credits in metadata
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

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.scheduled_hide = None
        self.scheduled_show = None
        self.widget.bind("<Enter>", self.schedule_show)
        self.widget.bind("<Leave>", self.schedule_hide)

    def schedule_show(self, event=None):
        # Cancel any pending hide
        if self.scheduled_hide:
            self.widget.after_cancel(self.scheduled_hide)
            self.scheduled_hide = None
        
        # Cancel any pending show to prevent multiple schedules
        if self.scheduled_show:
            self.widget.after_cancel(self.scheduled_show)
        
        # Schedule new show with small delay
        self.scheduled_show = self.widget.after(200, self.show_tooltip)

    def schedule_hide(self, event=None):
        # Cancel any pending show
        if self.scheduled_show:
            self.widget.after_cancel(self.scheduled_show)
            self.scheduled_show = None
            
        # Schedule hide with small delay
        self.scheduled_hide = self.widget.after(200, self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip:
            return
        
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height()

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = ttk.Label(self.tooltip, text=self.text, 
                         justify=tk.LEFT,
                         background="#ffffe0", 
                         relief="solid", 
                         borderwidth=1)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class PackSelector:
    def __init__(self, root, directories, on_complete):
        self.window = tk.Toplevel(root)
        self.window.title("Select Packs")
        self.directories = directories
        self.selected_packs = set()
        self.on_complete = on_complete
        
        # Create custom styles
        style = ttk.Style()
        style.configure("Pack.TButton", 
                       padding=5,
                       width=30,
                       foreground="black",
                       font=("Helvetica", 10))
        style.configure("PackSelected.TButton",
                       padding=5,
                       width=30,
                       foreground="green",
                       font=("Helvetica", 10, "bold"))
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Warning label
        warning_text = ("Warning: Selecting many packs may cause performance issues.\n"
                       "Consider working with fewer packs at a time for better responsiveness.")
        warning_label = ttk.Label(
            main_frame,
            text=warning_text,
            style="Warning.TLabel",
            wraplength=780,
            justify=tk.CENTER
        )
        warning_label.pack(pady=(0, 10))
        
        # Create scrollable frame for pack buttons
        canvas = tk.Canvas(main_frame, background="#f0f0f0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel only when mouse is over the canvas
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Configure grid for buttons (4 columns instead of 5)
        for i in range(4):  # Changed from 5 to 4
            self.scrollable_frame.grid_columnconfigure(i, weight=1, minsize=200)
            
        # Calculate window size based on number of packs
        num_packs = len(self.directories)
        window_width = min(1200, max(800, (250 * 4) + 50))  # Adjusted for 4 columns
        window_height = min(800, max(600, (50 * ((num_packs // 4) + 1)) + 150))  # Adjusted division
        self.window.geometry(f"{window_width}x{window_height}")
        
        # Create pack buttons
        row = 0
        col = 0
        for pack in sorted(self.directories, key=str.lower):  # Changed to case-insensitive sort
            btn = ttk.Button(
                self.scrollable_frame,
                text=pack,
                command=lambda p=pack: self.toggle_pack(p),
                style="Pack.TButton"
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Add tooltip
            ToolTip(btn, pack)
            
            col += 1
            if col >= 4:  # Changed from 5 to 4
                col = 0
                row += 1
        
        # Configure scrollable frame width
        self.scrollable_frame.configure(width=window_width - 50)  # Account for scrollbar
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create bottom button frame
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Add buttons
        ttk.Button(
            button_frame,
            text="Let's Go!",
            command=self.complete_selection,
            style="Modern.TButton"
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.window.destroy,
            style="Modern.TButton"
        ).pack(side=tk.RIGHT, padx=5)
        
    def toggle_pack(self, pack):
        if pack in self.selected_packs:
            self.selected_packs.remove(pack)
            style = "Pack.TButton"
        else:
            self.selected_packs.add(pack)
            style = "PackSelected.TButton"
            
        # Update button style
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == pack:
                widget.configure(style=style)
                break
                
    def complete_selection(self):
        if self.selected_packs:
            self.on_complete(self.selected_packs)
            self.window.destroy()

class MetadataEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Stepmania Metadata Editor")
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_and_exit)
        
        # Initialize tracking variables
        self.current_playing = None
        self.selected_entries = []
        self.file_entries = []
        self.selected_directories = set()
        self.bulk_edit_enabled = False
        self.shazam_mode = False
        
        # Initialize sort tracking
        self.sort_reverse = {
            'pack': False,  # Changed from 'parent_directory'
            'title': False,
            'subtitle': False,
            'artist': False,
            'genre': False
        }
        
        # Initialize pygame mixer with error handling
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        try:
            pygame.mixer.init()
            self.audio_enabled = True
        except Exception as e:
            print(f"Warning: Audio playback disabled - {str(e)}")
            self.audio_enabled = False
            messagebox.showwarning(
                "Audio Initialization Failed",
                "Audio playback will be disabled. Other features will work normally."
            )
        
        # Configure styles
        self.configure_styles()
        
        # Initialize UI components
        self.setup_ui()
        
        # Add Shazam functionality
        nest_asyncio.apply()
        self.shazam = Shazam()
        self.loop = asyncio.get_event_loop()
        
        # Add Shazam button to button_frame
        self.shazam_button = ttk.Button(
            self.button_frame,
            text=SHAZAM_BUTTON_NORMAL["text"],
            style=SHAZAM_BUTTON_NORMAL["style"],
            command=self.toggle_shazam_mode
        )
        self.shazam_button.pack(side=tk.RIGHT, padx=5)
    def configure_styles(self):
        style = ttk.Style()
        styles = {
            "Modern.TFrame": {"background": "#f0f0f0"},
            "Modern.TButton": {"padding": 5, "relief": "flat", "background": "#4a90e2", "foreground": "black"},
            "Modern.TLabel": {"background": "#f0f0f0", "foreground": "#333333", "font": ("Helvetica", 10)},
            "Modern.TEntry": {"padding": 5, "relief": "flat"},
            "Header.TButton": {"font": ("Helvetica", 10, "bold")},
            "Modified.TEntry": {"fieldbackground": "lightblue"},
            "Committed.TEntry": {"fieldbackground": "lightgreen"},
            "Warning.TButton": {"background": "orange"},
            "Success.TButton": {"background": "lightgreen"},
            "Shazam.TEntry": {
                "padding": 5,
                "foreground": "green",
            },
        }
        
        for style_name, properties in styles.items():
            style.configure(style_name, **properties)
        
        style = ttk.Style()
        style.configure("Shazam.TButton", 
                       background="lightgreen",
                       padding=5,
                       relief="flat")
        
        # Add new styles for pack selector
        style.configure("Pack.TButton", 
                       padding=5,
                       background="#f0f0f0")
        style.configure("PackSelected.TButton",
                       padding=5,
                       background="lightgreen")
        style.configure("Warning.TLabel",
                       foreground="red",
                       font=("Helvetica", 10, "bold"))
    
    def setup_ui(self):
        # Create GitHub and help button frame at the bottom right
        github_frame = ttk.Frame(self.root, style="Modern.TFrame")
        github_frame.pack(side=tk.BOTTOM, anchor=tk.E, padx=10, pady=5)

        # Create Help button first (so it appears to the left of GitHub)
        help_button = ttk.Button(
            github_frame, 
            text="❓ Help",
            style="Modern.TButton",
            command=self.show_help_dialog
        )
        help_button.pack(side=tk.LEFT, padx=5)

        # Create GitHub button
        github_button = ttk.Button(
            github_frame, 
            text="\u25D3 GitHub",  # Unicode octocat-like symbol
            style="Modern.TButton",
            command=lambda: webbrowser.open("https://github.com/therzog92/SM_Metadata_Editor")
        )
        github_button.pack(side=tk.LEFT)

        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10", style="Modern.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create top button frame
        self.button_frame = ttk.Frame(self.main_frame, style="Modern.TFrame")
        self.button_frame.pack(fill=tk.X, pady=(0,10))
        
        # Create directory picker button frame
        self.dir_button_frame = ttk.Frame(self.button_frame, style="Modern.TFrame")
        self.dir_button_frame.pack(side=tk.LEFT)
        
        # Create directory picker buttons (initially visible)
        self.dir_button = ttk.Button(self.dir_button_frame, text="Add Directory", 
                                   command=self.pick_directory, style="Modern.TButton")
        self.dir_button.pack(side=tk.LEFT, padx=5)
        
        # Clear directories button (initially hidden)
        self.clear_button = ttk.Button(self.dir_button_frame, text="Clear All", 
                                    command=self.clear_directories, style="Modern.TButton")
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.clear_button.pack_forget()  # Initially hidden
        
        # Create bulk edit button (initially hidden)
        self.bulk_edit_button = ttk.Button(self.button_frame, text="Bulk Edit",
                                         command=self.toggle_bulk_edit, style="Modern.TButton")
        self.bulk_edit_button.pack(side=tk.LEFT, padx=5)
        self.bulk_edit_button.pack_forget()  # Initially hidden
        
        # Create credit search button (initially hidden)
        self.search_credits_button = ttk.Button(
            self.button_frame,
            text="Search Credits",
            command=self.show_credit_search,  # Connect to the new method
            style="Modern.TButton"
        )
        self.search_credits_button.pack(side=tk.LEFT, padx=5)
        self.search_credits_button.pack_forget()  # Initially hidden
        
        # Create commit all button (initially hidden)
        self.commit_all_button = ttk.Button(self.button_frame, text="Commit All (0)",
                                          command=self.commit_all_changes, style="Modern.TButton")
        self.commit_all_button.pack(side=tk.RIGHT, padx=5)
        self.commit_all_button.pack_forget()
        
        # Create bulk edit controls frame (initially hidden)
        self.bulk_edit_controls = ttk.Frame(self.main_frame, style="Modern.TFrame")
        self.selected_entries = []
        
        # Create bulk edit fields
        self.bulk_fields = {}
        fields = ['Subtitle', 'Artist', 'Genre']
        for i, field in enumerate(fields):
            label = ttk.Label(self.bulk_edit_controls, text=field+":", style="Modern.TLabel")
            label.grid(row=0, column=i*2, padx=5, pady=5)
            
            var = tk.StringVar()
            entry = ttk.Entry(self.bulk_edit_controls, textvariable=var, style="Modern.TEntry")
            entry.grid(row=0, column=i*2+1, padx=5, pady=5)
            self.bulk_fields[field.lower()] = var
            
        # Add apply button
        self.apply_bulk = ttk.Button(self.bulk_edit_controls, text="Apply to Selected",
                                   command=self.apply_bulk_edit, style="Modern.TButton")
        self.apply_bulk.grid(row=0, column=len(fields)*2, padx=5, pady=5)
        
        # Create frame for file entries
        self.files_frame = ttk.Frame(self.main_frame, style="Modern.TFrame")
        self.files_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create headers frame with grid
        self.headers_frame = ttk.Frame(self.files_frame, style="Modern.TFrame")
        self.headers_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure grid columns
        for i, width in enumerate([
            COLUMN_WIDTHS['checkbox'],
            COLUMN_WIDTHS['actions'],
            COLUMN_WIDTHS['type'],
            COLUMN_WIDTHS['parent_dir'],
            COLUMN_WIDTHS['title'],
            COLUMN_WIDTHS['subtitle'],
            COLUMN_WIDTHS['artist'],
            COLUMN_WIDTHS['genre'],
            COLUMN_WIDTHS['status']
        ]):
            self.headers_frame.grid_columnconfigure(i, minsize=width)
        
        # Create headers
        headers = ["", "Actions", "Type", "Pack", "Title", "Subtitle", "Artist", "Genre", " "]
        for i, header in enumerate(headers):
            if header in ["Pack", "Title", "Subtitle", "Artist", "Genre"]:
                column_key = header.lower().replace(" ", "_")
                if column_key == "pack":  # Changed from parent_directory check
                    column_key = "parent_dir"  # Keep this as is for column width reference
                    
                btn = ttk.Button(
                    self.headers_frame, 
                    text=header,
                    command=lambda h=header.lower(): self.sort_entries(h),  # Simplified since 'pack' doesn't need replacement
                    style="Header.TButton",
                    width=COLUMN_WIDTHS[column_key] // 8
                )
                btn.grid(row=0, column=i, padx=5, sticky='')
            else:
                column_key = {
                    "": "checkbox" if i == 0 else "status",
                    "Actions": "actions",
                    "Type": "type",
                    " ": "status"
                }.get(header, "status")
                
                width = COLUMN_WIDTHS[column_key] // 8 - 1
                
                lbl = ttk.Label(
                    self.headers_frame, 
                    text=header, 
                    style="Modern.TLabel",
                    anchor="center",
                    width=width
                )
                lbl.grid(row=0, column=i, padx=5, sticky='nsew')
        
        # Create scrollable frame
        self.canvas = tk.Canvas(self.files_frame, background="#f0f0f0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.files_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="Modern.TFrame")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=1550)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel only when mouse is over the canvas
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def toggle_bulk_edit(self):
        self.bulk_edit_enabled = not self.bulk_edit_enabled
        if self.bulk_edit_enabled:
            self.bulk_edit_button.configure(text="Exit Bulk Edit")
            self.bulk_edit_controls.pack(after=self.button_frame, fill=tk.X, pady=(0,10))
            # Show checkboxes
            for entry in self.file_entries:
                entry['checkbox'].grid()
        else:
            self.bulk_edit_button.configure(text="Bulk Edit")
            self.bulk_edit_controls.pack_forget()
            # Hide checkboxes and clear selection
            for entry in self.file_entries:
                entry['checkbox'].grid_remove()
                entry['checkbox_var'].set(False)
            self.selected_entries.clear()
            
    def apply_bulk_edit(self):
        if not self.selected_entries:
            return
        
        # Get values from bulk edit fields - removed 'title' from here
        new_values = {
            'subtitle': self.bulk_fields['subtitle'].get(),
            'artist': self.bulk_fields['artist'].get(),
            'genre': self.bulk_fields['genre'].get()
        }
        
        # Apply to each selected entry
        for entry_data in self.selected_entries:
            for field, value in new_values.items():
                if value:  # Only update if value is not empty
                    entry_data['entries'][field]['var'].set(value)
                    self.on_entry_change(entry_data['frame'], entry_data['filepaths'], 
                                       field, entry_data['entries'][field])
                    
    def on_checkbox_toggle(self, entry_data):
        if entry_data['checkbox_var'].get():
            if entry_data not in self.selected_entries:
                self.selected_entries.append(entry_data)
        else:
            if entry_data in self.selected_entries:
                self.selected_entries.remove(entry_data)
        
        # Update commit all button text
        self.update_commit_all_button()
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def play_audio(self, music_path, play_btn):
        if not self.audio_enabled:
            messagebox.showwarning(
                "Audio Disabled",
                "Audio playback is currently disabled due to initialization error."
            )
            return
        
        # Stop current playing audio if any
        if self.current_playing:
            pygame.mixer.music.stop()
            try:
                self.current_playing.configure(text="▶")
            except (tk.TclError, RuntimeError):
                # Button no longer exists, just clear the reference
                pass
            if self.current_playing == play_btn:
                self.current_playing = None
                return
            
        # Show appropriate log message based on mode
        if self.shazam_mode:
            print(f"\nAttempting to play and analyze: {music_path}")
        else:
            print(f"\nAttempting to play: {music_path}")
        
        # Clean and normalize the path
        music_path = os.path.normpath(music_path.strip())
        directory = os.path.dirname(music_path)
        music_name = os.path.basename(music_path)
        
        def process_shazam_result(file_path, play_button):
            if self.shazam_mode:
                print("Starting Shazam analysis...")
                result = self.loop.run_until_complete(self.analyze_single_file(file_path))
                if result and 'track' in result:
                    track = result['track']
                    # Clean up special characters
                    special_chars = ['#', ':', ';']
                    title = track.get('title', '')
                    artist = track.get('subtitle', '')
                    genre = track.get('genres', {}).get('primary', '')
                    
                    # Safely get the coverart URL from the correct path
                    coverart_url = None
                    if 'share' in track and 'image' in track['share']:
                        coverart_url = track['share']['image']
                    
                    for char in special_chars:
                        title = title.replace(char, '\\' + char)
                        artist = artist.replace(char, '\\' + char)
                        genre = genre.replace(char, '\\' + char)
                        
                    shazam_data = {
                        'title': title,
                        'artist': artist,
                        'genre': genre,
                        'images': {'coverart': coverart_url} if coverart_url else {}
                    }
                    entry_frame = play_button.master.master
                    self.show_shazam_results(entry_frame, shazam_data)
        
        # First try exact path
        if os.path.exists(music_path):
            try:
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.play()
                play_btn.configure(text="⏹")
                self.current_playing = play_btn
                process_shazam_result(music_path, play_btn)
                return
            except Exception as e:
                print(f"Exact path failed: {str(e)}")
        
        # If exact path fails, try to find the file
        print(f"Searching directory for matching file...")
        try:
            for file in os.listdir(directory):
                if file.lower().endswith(('.ogg', '.mp3', '.wav')):
                    full_path = os.path.join(directory, file)
                    print(f"Trying: {full_path}")
                    try:
                        pygame.mixer.music.load(full_path)
                        pygame.mixer.music.play()
                        play_btn.configure(text="⏹")
                        self.current_playing = play_btn
                        process_shazam_result(full_path, play_btn)
                        return
                    except Exception as e:
                        print(f"Failed to load alternative file: {str(e)}")
        except Exception as e:
            print(f"Error searching directory: {str(e)}")

    def toggle_shazam_mode(self):
        # Check internet connection first
        try:
            import urllib.request
            urllib.request.urlopen('http://google.com', timeout=1)
        except:
            messagebox.showwarning(
                "No Internet Connection",
                "Shazam mode requires an internet connection. Please check your connection and try again."
            )
            self.shazam_mode = False
            self.shazam_button.configure(**SHAZAM_BUTTON_NORMAL)
            return

        # Toggle mode
        self.shazam_mode = not self.shazam_mode
        
        if self.shazam_mode:
            self.shazam_button.configure(**SHAZAM_BUTTON_ACTIVE)
        else:
            self.shazam_button.configure(**SHAZAM_BUTTON_NORMAL)
            self.restore_normal_mode()

    def restore_normal_mode(self):
        # Restore any modified entries to their normal state
        for entry_data in self.file_entries:
            for field_data in entry_data['entries'].values():
                if 'shazam_btn' in field_data:
                    field_data['shazam_btn'].destroy()
                    field_data['entry'].grid()
                    field_data.pop('shazam_btn')

    def show_shazam_results(self, entry_frame, shazam_data):
        # Check if artwork button already exists in the actions frame
        actions_frame = next(
            (child for child in entry_frame.winfo_children() 
             if isinstance(child, ttk.Frame)),
            None
        )
        if not actions_frame:
            return

        # Handle metadata fields
        column_positions = {
            'title': 4,
            'artist': 6,
            'genre': 7
        }
        
        for field, value in shazam_data.items():
            if not value or field == 'images':  # Skip empty values and images field
                continue
            
            entry_data = next(
                (e for e in self.file_entries if e['frame'] == entry_frame),
                None
            )
            if not entry_data:
                continue

            current = entry_data['entries'][field]['var'].get()
            if current == value:
                entry_data['entries'][field]['entry'].configure(style="Shazam.TEntry")
                continue

            # Calculate max characters per line (roughly 8 pixels per character)
            max_chars = COLUMN_WIDTHS[field.lower()] // 8
            
            # Create button text with conditional truncation
            current_text = f"{current}..." if len(current) > max_chars else current
            new_text = f"{value}..." if len(value) > max_chars else value
            button_text = f"Current: {current_text}\nNew: {new_text}"
            full_text = f"Current: {current}\nNew: {value}"
            
            btn = ttk.Button(
                entry_frame,
                text=button_text,
                command=lambda f=field, v=value, e=entry_data: self.apply_shazam_value(f, v, e),
                style="Modern.TButton",
                width=COLUMN_WIDTHS[field.lower()] // 8
            )
            
            # Only add tooltip if text was truncated
            if len(current) > max_chars or len(value) > max_chars:
                ToolTip(btn, full_text)
            
            entry_data['entries'][field]['entry'].grid_remove()
            col = column_positions[field]
            btn.grid(row=0, column=col, padx=5, sticky='ew')
            entry_data['entries'][field]['shazam_btn'] = btn

        # Handle artwork button - only create if we have coverart and no existing button
        if 'images' in shazam_data and 'coverart' in shazam_data['images']:
            coverart_url = shazam_data['images']['coverart']
            if coverart_url:
                # Check for existing artwork button
                existing_artwork_btn = next(
                    (child for child in actions_frame.winfo_children() 
                     if isinstance(child, ttk.Button) and child['text'] == "🖼"),
                    None
                )
                
                if not existing_artwork_btn:
                    artwork_btn = ttk.Button(
                        actions_frame,
                        text="🖼",
                        width=2,
                        command=lambda: self.show_artwork_preview(entry_frame, coverart_url),
                        style="Modern.TButton"
                    )
                    artwork_btn.pack(side=tk.LEFT, padx=2)
                    ToolTip(artwork_btn, "Preview/Update Album Artwork")

    def apply_shazam_value(self, field, value, entry_data):
        """Apply Shazam result to an entry field"""
        # Update the entry value
        entry_data['entries'][field]['var'].set(value)
        
        # Remove the Shazam button and show the entry
        if 'shazam_btn' in entry_data['entries'][field]:
            entry_data['entries'][field]['shazam_btn'].destroy()
            entry_data['entries'][field]['entry'].grid()
            entry_data['entries'][field].pop('shazam_btn')
        
        # Trigger the entry change handler
        self.on_entry_change(entry_data['frame'], entry_data['filepaths'])

    def show_metadata_editor(self, filepaths):
        # Create new window
        editor = tk.Toplevel(self.root)
        editor.title("Full Metadata Editor")
        editor.geometry("600x800")
        
        # Create main frame with scrollbar
        main_frame = ttk.Frame(editor, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=550)
        canvas.configure(yscrollcommand=scrollbar.set)
        # Bind mousewheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Read metadata from first file
        metadata = {}
        try:
            with open(filepaths[0], 'r', encoding='utf-8') as file:
                for line in file:
                    if line.startswith('#') and ':' in line:
                        key, value = line.strip().split(':', 1)
                        key = key[1:]  # Remove the # character
                        value = value.rstrip(';')
                        metadata[key] = value
        except Exception as e:
            print(f"Error reading metadata: {str(e)}")
            
        # Create entry fields for each metadata item
        entries = {}
        row = 0
        for key, value in metadata.items():
            # Label
            label = ttk.Label(scrollable_frame, text=key, style="Modern.TLabel")
            label.grid(row=row, column=0, padx=5, pady=5, sticky='e')
            
            # Entry
            var = tk.StringVar(value=value)
            entry = ttk.Entry(scrollable_frame, textvariable=var, width=50)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky='ew')
            entries[key] = {'var': var, 'original': value}
            row += 1
            
        # Button frame
        button_frame = ttk.Frame(editor)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Commit button
        commit_btn = ttk.Button(button_frame, text="Commit Changes",
                              command=lambda: self.commit_full_metadata(filepaths, entries, editor))
        commit_btn.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_btn = ttk.Button(button_frame, text="Close",
                              command=editor.destroy)
        close_btn.pack(side=tk.RIGHT, padx=5)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_file_entry(self, filepaths, parent_dir, title, subtitle, artist, genre, music_file):
        frame = ttk.Frame(self.scrollable_frame, style="Modern.TFrame")
        frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Configure grid columns with same widths as headers
        for i, width in enumerate([
            COLUMN_WIDTHS['checkbox'],
            COLUMN_WIDTHS['actions'],
            COLUMN_WIDTHS['type'],
            COLUMN_WIDTHS['parent_dir'],
            COLUMN_WIDTHS['title'],
            COLUMN_WIDTHS['subtitle'],
            COLUMN_WIDTHS['artist'],
            COLUMN_WIDTHS['genre'],
            COLUMN_WIDTHS['status']
        ]):
            frame.grid_columnconfigure(i, minsize=width)
        
        # Create entries with center alignment
        entries = {}
        original_values = {'title': title, 'subtitle': subtitle, 'artist': artist, 'genre': genre}
        col = 4
        
        for field in ['title', 'subtitle', 'artist', 'genre']:
            var = tk.StringVar(value=original_values[field])
            entry = ttk.Entry(
                frame, 
                textvariable=var, 
                style="Modern.TEntry",
                width=COLUMN_WIDTHS[field] // 8
            )
            entry.grid(row=0, column=col, padx=5, sticky='ew')
            entries[field] = {
                'var': var,
                'entry': entry,
                'original': original_values[field]
            }
            # Update the lambda to only pass frame and entries
            var.trace_add('write', lambda *args, f=field: self.on_entry_change(frame, entries))
            col += 1
        
        # Checkbox for bulk edit (initially hidden)
        checkbox_var = tk.BooleanVar()
        checkbox = ttk.Checkbutton(frame, variable=checkbox_var)
        checkbox.grid(row=0, column=0, padx=5)
        checkbox.grid_remove()  # Hidden by default
        
        # Actions frame
        actions_frame = ttk.Frame(frame, style="Modern.TFrame")
        actions_frame.grid(row=0, column=1, padx=5)
        
        # Open button
        open_btn = ttk.Button(actions_frame, text="...", width=2,
                             command=lambda: self.open_file_location(os.path.dirname(filepaths[0])),
                             style="Modern.TButton")
        open_btn.pack(side=tk.LEFT, padx=2)
        
        # Play button - only add if valid music file exists
        if music_file:  # First check if music_file is not empty
            directory = os.path.dirname(filepaths[0])
            music_path = os.path.join(directory, music_file)
            base_name = os.path.splitext(music_file)[0].split()[-1].lower()  # Get last word before extension
            extension = os.path.splitext(music_file)[1].lower()
            has_music = False
            
            # First check for exact file
            if os.path.exists(music_path):
                has_music = True
            else:
                # If exact match fails, look for any file ending with the base name
                for file in os.listdir(directory):
                    file_lower = file.lower()
                    if (file_lower.endswith(f"{base_name}{extension}") and 
                        file_lower.endswith(('.ogg', '.mp3', '.wav'))):
                        has_music = True
                        break
            
            if has_music:
                play_btn = ttk.Button(actions_frame, text="▶", width=2,
                                    command=lambda: self.play_audio(music_path, play_btn),
                                    style="Modern.TButton")
                play_btn.pack(side=tk.LEFT, padx=2)

        # Edit metadata button
        edit_btn = ttk.Button(actions_frame, text="✎", width=2,
                            command=lambda: self.show_metadata_editor(filepaths),
                            style="Modern.TButton")
        edit_btn.pack(side=tk.LEFT, padx=2)
        
        # File type indicator
        file_types = []
        for path in filepaths:
            ext = os.path.splitext(path)[1].upper()[1:]
            if ext not in file_types:
                file_types.append(ext)
        type_label = ttk.Label(
            frame, 
            text="+".join(file_types) if len(filepaths) > 1 else file_types[0], 
            style="Modern.TLabel"
        )
        type_label.grid(row=0, column=2, padx=5)
        
        # Parent directory (uneditable) with fixed width
        parent_width = COLUMN_WIDTHS['parent_dir'] // 8  # Convert pixels to approximate character width
        if len(parent_dir) > parent_width:
            display_text = parent_dir[:parent_width-3] + "..."
        else:
            display_text = parent_dir

        parent_label = ttk.Label(
            frame, 
            text=display_text, 
            style="Modern.TLabel",
            width=parent_width
        )
        parent_label.grid(row=0, column=3, padx=5)

        # Add tooltip for full text if truncated
        if len(parent_dir) > parent_width:
            ToolTip(parent_label, parent_dir)
        
        # Create commit button (initially hidden)
        commit_btn = ttk.Button(
            frame,
            text="Commit?",
            command=lambda: self.commit_changes(frame, filepaths, entries),
            style="Warning.TButton"
        )
        commit_btn.grid(row=0, column=8, padx=5, sticky='e')
        commit_btn.grid_remove()

        entry_data = {
            'frame': frame,
            'filepaths': filepaths,
            'entries': entries,
            'commit_btn': commit_btn,
            'parent_dir': parent_dir,
            'checkbox': checkbox,
            'checkbox_var': checkbox_var
        }
        
        # Bind checkbox to selection tracking
        checkbox_var.trace_add('write', lambda *args: self.on_checkbox_toggle(entry_data))
        
        self.file_entries.append(entry_data)

    def commit_full_metadata(self, filepaths, entries, editor):
        for filepath in filepaths:
            try:
                # Read file content
                with open(filepath, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                # Update the lines
                for i, line in enumerate(lines):
                    for field, entry_data in entries.items():
                        if line.startswith(f'#{field}:'):
                            new_value = entry_data['var'].get()
                            lines[i] = f'#{field}:{new_value};\n'
                
                # Write back to file
                with open(filepath, 'w', encoding='utf-8') as file:
                    file.writelines(lines)
            except Exception as e:
                print(f"Error updating file {filepath}: {str(e)}")
                return
                
        # Close editor window
        editor.destroy()
        
    def on_entry_change(self, frame, filepaths, field=None, field_data=None):
        """Handle changes to entry fields"""
        # Find the entry data for this frame
        entry_data = next((e for e in self.file_entries if e['frame'] == frame), None)
        if not entry_data:
            return
        
        has_changes = False
        # Check all fields for changes
        for f, data in entry_data['entries'].items():
            if data['var'].get() != data['original']:
                has_changes = True
                data['entry'].configure(style='Modified.TEntry')
            else:
                data['entry'].configure(style='Modern.TEntry')
        
        # Show/hide commit button
        if has_changes:
            entry_data['commit_btn'].configure(text="Commit?", style='Warning.TButton', state='normal')
            entry_data['commit_btn'].grid()
        else:
            entry_data['commit_btn'].grid_remove()
        
        # Update commit all button
        self.update_commit_all_button()
        
    def update_commit_all_button(self):
        # Count uncommitted changes
        uncommitted = 0
        for entry in self.file_entries:
            for field_data in entry['entries'].values():
                if field_data['var'].get() != field_data['original']:
                    uncommitted += 1
                    break
                    
        if uncommitted > 0:
            self.commit_all_button.configure(text=f"Commit All ({uncommitted})")
            self.commit_all_button.pack(side=tk.RIGHT, padx=5)
        else:
            self.commit_all_button.pack_forget()
            
    def commit_all_changes(self):
        for entry in self.file_entries:
            if any(e['var'].get() != e['original'] for e in entry['entries'].values()):
                self.commit_changes(entry['frame'], entry['filepaths'], entry['entries'])
            
    def commit_changes(self, frame, filepaths, entries):
        encodings = ['utf-8-sig', 'utf-8', 'shift-jis', 'latin1', 'cp1252']
        
        for filepath in filepaths:
            success = False
            file_content = None
            
            # First, try to read the file with different encodings
            for encoding in encodings:
                try:
                    with open(filepath, 'r', encoding=encoding) as file:
                        file_content = file.readlines()
                        used_encoding = encoding
                        success = True
                        break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Error reading file {filepath}: {str(e)}")
                    return
            
            if not success or file_content is None:
                print(f"Could not read file {filepath} with any supported encoding")
                return
            
            try:
                # Track if we need to add new fields and their position
                title_line_index = None
                fields_to_add = set()  # Changed to set to ensure uniqueness
                existing_fields = set()  # Track which fields already exist
                
                # First pass: identify existing fields and update them
                for i, line in enumerate(file_content):
                    if line.startswith('#TITLE:'):
                        title_line_index = i
                    
                    for field, entry_data in entries.items():
                        field_upper = field.upper()
                        if line.startswith(f'#{field_upper}:'):
                            existing_fields.add(field_upper)
                            new_value = entry_data['var'].get()
                            if new_value != entry_data['original']:
                                file_content[i] = f'#{field_upper}:{new_value};\n'
                                entry_data['original'] = new_value
                                entry_data['entry'].configure(style='Committed.TEntry')
                
                # Identify which fields need to be added
                for field, entry_data in entries.items():
                    field_upper = field.upper()
                    if (field_upper not in existing_fields and 
                        entry_data['var'].get() != entry_data['original'] and 
                        entry_data['var'].get()):  # Only add if there's a value
                        fields_to_add.add((field_upper, entry_data['var'].get()))
                
                # Second pass: add new fields after #TITLE
                if title_line_index is not None and fields_to_add:
                    # Convert set to list and sort for consistent ordering
                    sorted_fields = sorted(list(fields_to_add))
                    for field_upper, value in sorted_fields:
                        new_line = f'#{field_upper}:{value};\n'
                        title_line_index += 1  # Insert after previous insertion
                        file_content.insert(title_line_index, new_line)
                
                # Write back to file using the same encoding we successfully read with
                with open(filepath, 'w', encoding=used_encoding) as file:
                    file.writelines(file_content)
            except Exception as e:
                print(f"Error updating file {filepath}: {str(e)}")
                return
        
        # Update commit button
        commit_btn = [w for w in frame.winfo_children() if isinstance(w, ttk.Button) and w['text'] in ["Commit?", "Committed"]][0]
        commit_btn.configure(text="Committed", style='Success.TButton', state='disabled')
        
        # Update commit all button
        self.update_commit_all_button()
        
    def sort_entries(self, field):
        self.sort_reverse[field] = not self.sort_reverse[field]
        
        if field == 'pack':  # Changed from 'parent_directory'
            self.file_entries.sort(
                key=lambda x: x['parent_dir'],
                reverse=self.sort_reverse[field]
            )
        else:
            self.file_entries.sort(
                key=lambda x: x['entries'][field]['var'].get(),
                reverse=self.sort_reverse[field]
            )
        
        # Repack all entries in new order
        for entry in self.file_entries:
            entry['frame'].pack_forget()
            entry['frame'].pack(fill=tk.X, padx=5, pady=2)
            
    def open_file_location(self, directory):
        try:
            if os.name == 'nt':  # Windows
                os.startfile(directory)
            elif os.name == 'posix':  # macOS and Linux
                subprocess.run(['open', directory])
        except Exception as e:
            print(f"Error opening directory {directory}: {str(e)}")
            
    def pick_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            # Find all SM/SSC files and their parent packs
            packs = set()
            sm_files_found = False
            
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(('.sm', '.ssc')):
                        sm_files_found = True
                        # Get the song directory and its parent (pack directory)
                        song_dir = os.path.dirname(os.path.join(root, file))
                        pack_dir = os.path.dirname(song_dir)
                        pack_name = os.path.basename(pack_dir)
                        
                        # If we're selecting a song directory or pack directory directly
                        if pack_dir == directory:  # Selected a pack directory
                            self.load_selected_packs(directory, {directory})
                            return
                        elif song_dir == directory:  # Selected a song directory
                            self.load_selected_packs(os.path.dirname(directory), {os.path.dirname(directory)})
                            return
                        elif pack_name and pack_name != os.path.basename(directory):
                            packs.add((pack_name, pack_dir))
            
            if packs:
                # Show pack selector with pack names only
                PackSelector(
                    self.root,
                    {name for name, _ in packs},
                    lambda selected: self.load_selected_packs(
                        directory, 
                        {path for name, path in packs if name in selected}
                    )
                )
            elif sm_files_found:  # If we found SM files but no packs, load the directory directly
                self.load_selected_packs(os.path.dirname(directory), {directory})
            else:
                messagebox.showinfo(
                    "No Songs Found",
                    "No StepMania files (.sm/.ssc) were found in the selected directory."
                )
    
    def load_selected_packs(self, base_directory, selected_pack_paths):
        # Clear existing directories
        self.selected_directories.clear()
        
        # Add the selected pack paths directly
        self.selected_directories.update(selected_pack_paths)
        
        # Load files from selected directories
        self.load_files_from_all_directories()
    
    def load_files_from_all_directories(self):
        # Clear existing entries
        for entry in self.file_entries:
            entry['frame'].destroy()
        self.file_entries.clear()
        
        # Create styles
        style = ttk.Style()
        style.configure('Modified.TEntry', fieldbackground='lightblue')
        style.configure('Committed.TEntry', fieldbackground='lightgreen')
        style.configure('Warning.TButton', background='orange')
        style.configure('Success.TButton', background='lightgreen')
        
        # Track files by base name to combine SM and SSC
        file_groups = defaultdict(list)
        
        # Process all selected directories
        for directory in self.selected_directories:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(('.sm', '.ssc')):
                        filepath = os.path.join(root, file)
                        base_name = os.path.splitext(file)[0]
                        file_groups[f"{os.path.dirname(filepath)}_{base_name}"].append(filepath)
        
        # Create entries for each unique song
        for _, filepaths in file_groups.items():
            metadata_list = [self.read_metadata(fp) for fp in filepaths]
            parent_parent_dir = os.path.basename(os.path.dirname(os.path.dirname(filepaths[0])))
            
            # Check if we need separate entries
            need_separate = False
            combined_metadata = {}
            
            for field in ['TITLE', 'SUBTITLE', 'ARTIST', 'GENRE']:
                values = set()
                for metadata in metadata_list:
                    value = metadata.get(field, '').strip()
                    if value and not value.endswith(':;'):  # If field exists and has content
                        values.add(value)
                
                if len(values) > 1:  # If we have different non-empty values
                    need_separate = True
                    break
                elif values:  # If we have at least one non-empty value
                    combined_metadata[field] = values.pop()  # Use the non-empty value
                else:
                    combined_metadata[field] = ''  # No valid value found
            
            if need_separate:
                # Create separate entries for each file
                for filepath, metadata in zip(filepaths, metadata_list):
                    self.create_file_entry(
                        [filepath],  # Single file path
                        parent_parent_dir,
                        metadata.get('TITLE', ''),
                        metadata.get('SUBTITLE', ''),
                        metadata.get('ARTIST', ''),
                        metadata.get('GENRE', ''),
                        metadata.get('MUSIC', '')
                    )
            else:
                # Create combined entry
                self.create_file_entry(
                    filepaths,
                    parent_parent_dir,
                    combined_metadata.get('TITLE', ''),
                    combined_metadata.get('SUBTITLE', ''),
                    combined_metadata.get('ARTIST', ''),
                    combined_metadata.get('GENRE', ''),
                    metadata_list[0].get('MUSIC', '')  # Use music from first file
                )
        
        # Show buttons when files are loaded
        if self.file_entries:
            self.clear_button.pack(side=tk.LEFT, padx=5)
            self.bulk_edit_button.pack(side=tk.LEFT, padx=5)
            self.search_credits_button.pack(side=tk.LEFT, padx=5)
    
    def read_metadata(self, filepath):
        metadata = {}
        target_fields = {'#' + field + ':' for field in METADATA_FIELDS}
        
        for encoding in SUPPORTED_ENCODINGS:
            try:
                with open(filepath, 'r', encoding=encoding) as file:
                    for line in file:
                        if any(line.startswith(field) for field in target_fields):
                            key, value = line.strip().split(':', 1)
                            key = key[1:]  # Remove the # character
                            value = value.rstrip(';')
                            metadata[key] = value
                            
                            # Early exit if we found all fields
                            if len(metadata) == len(METADATA_FIELDS):
                                break
                    break  # Successfully read file, exit encoding loop
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading metadata from {filepath}: {str(e)}")
                break
            
        return metadata

    async def analyze_single_file(self, file_path):
        try:
            return await self.shazam.recognize(file_path)
        except Exception as e:
            print(f"Shazam analysis error: {str(e)}")
            return None

    def cleanup_and_exit(self):
        try:
            # Stop any playing audio
            if pygame.mixer.get_init():
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                pygame.mixer.quit()
            
            # Clear file entries
            for entry in self.file_entries:
                entry['frame'].destroy()
            self.file_entries.clear()
            
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
        finally:
            self.root.destroy()  # Always ensure window is destroyed

    def show_artwork_preview(self, entry_frame, artwork_url):
        # Create preview window with fixed size
        preview_window = tk.Toplevel(self.root)
        preview_window.title("Album Artwork Preview")
        preview_window.geometry("800x600")  # Set initial size
        preview_window.resizable(False, False)  # Prevent resizing

        # Create main content frame for images and labels
        content_frame = ttk.Frame(preview_window)
        content_frame.pack(fill=tk.X, padx=10, pady=10)  # Changed to fill=tk.X

        # Create left and right frames for the artwork
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, expand=True, padx=10)

        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, expand=True, padx=10)

        # Find the current jacket file and reference
        entry_data = next((e for e in self.file_entries if e['frame'] == entry_frame), None)
        if not entry_data:
            return

        directory = os.path.dirname(entry_data['filepaths'][0])
        
        # Get current jacket reference from file
        current_jacket_ref = None
        jacket_line_exists = False
        current_img = None
        jacket_path = None
        
        # First check for explicit reference in the SM/SSC files
        for filepath in entry_data['filepaths']:
            content, encoding = MetadataUtil.read_file_with_encoding(filepath)
            if content:
                for line in content:
                    if line.startswith('#JACKET:'):
                        jacket_line_exists = True
                        ref = line.split(':', 1)[1].strip().rstrip(';')
                        if ref:  # If we found a non-empty reference
                            current_jacket_ref = ref
                            break
                if current_jacket_ref:  # If we found a reference, stop checking files
                    break

        # Try to find the jacket image in this order:
        # 1. Explicit reference from SM/SSC file
        # 2. Any PNG file with "jacket" in the name
        # 3. Default to creating a new jacket.png
        
        if current_jacket_ref:
            # Try exact match first
            exact_path = os.path.join(directory, current_jacket_ref)
            try:
                current_img = Image.open(exact_path)
                jacket_path = exact_path
            except Exception:
                # If exact match fails, try wildcard search
                base_name = os.path.splitext(current_jacket_ref)[0]
                for file in os.listdir(directory):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')) and base_name.lower() in file.lower():
                        try:
                            jacket_path = os.path.join(directory, file)
                            current_img = Image.open(jacket_path)
                            break
                        except Exception:
                            continue

        # If no image found from explicit reference, look for PNG files ending with "jacket.png"
        if not current_img:
            for file in os.listdir(directory):
                # Check specifically for filenames ending with "jacket.png" (case insensitive)
                if file.lower().endswith('jacket.png'):
                    try:
                        jacket_path = os.path.join(directory, file)
                        current_img = Image.open(jacket_path)
                        current_jacket_ref = file  # Update reference to found file
                        break
                    except Exception:
                        continue

        # If still no image found, set default path
        if not current_img:
            jacket_path = os.path.join(directory, "jacket.png")
            if not current_jacket_ref:
                current_jacket_ref = "jacket.png"

        # If no current jacket found or reference is invalid
        if not current_img:
            jacket_path = os.path.join(directory, "SM_MDE_Jacket.png")
            ttk.Label(left_frame, text="No current artwork found", style="Modern.TLabel").pack(padx=10, pady=10)
        else:
            # Display current artwork
            current_img.thumbnail((350, 350))
            current_photo = ImageTk.PhotoImage(current_img)
            current_label = ttk.Label(left_frame, image=current_photo)
            current_label.image = current_photo
            current_label.pack(padx=10, pady=10)
            ttk.Label(left_frame, 
                     text=f"Dimensions: {current_img.size[0]}x{current_img.size[1]}" if current_img else "",
                     style="Modern.TLabel").pack(pady=(0, 10))

        # Load new artwork
        try:
            response = requests.get(artwork_url)
            new_img = Image.open(BytesIO(response.content))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load new artwork: {str(e)}")
            preview_window.destroy()
            return
        
        # Display new artwork
        new_img.thumbnail((350, 350))
        new_photo = ImageTk.PhotoImage(new_img)
        new_label = ttk.Label(right_frame, image=new_photo)
        new_label.image = new_photo
        new_label.pack(padx=10, pady=10)
        
        # Add dimensions labels
        ttk.Label(right_frame, 
                 text=f"Dimensions: {new_img.size[0]}x{new_img.size[1]}",
                 style="Modern.TLabel").pack(pady=(0, 10))
        
        # Add buttons frame at the bottom
        button_frame = ttk.Frame(preview_window)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # Configure two equal columns for buttons
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Keep current button
        keep_button = ttk.Button(
            button_frame, 
            text="Keep Current", 
            command=preview_window.destroy,
            style="Modern.TButton",
            width=20
        )
        keep_button.grid(row=0, column=0, padx=20, sticky='nsew')

        # Update button
        update_button = ttk.Button(
            button_frame, 
            text="Update Artwork",
            command=lambda: self.update_artwork(
                jacket_path, 
                new_img,
                (
                    max(512, current_img.size[0]) if current_img and current_img.size[0] >= 512 
                    else min(512, new_img.size[0]),
                    max(512, current_img.size[1]) if current_img and current_img.size[1] >= 512 
                    else min(512, new_img.size[1])
                ),
                preview_window,
                entry_data['filepaths'],
                current_jacket_ref
            ),
            style="Modern.TButton",
            width=20
        )
        update_button.grid(row=0, column=1, padx=20, sticky='nsew')

    def update_artwork(self, jacket_path, new_img, target_size, preview_window, filepaths, current_jacket_ref):
        try:
            # Resize new image to match current dimensions
            resized_img = new_img.resize(target_size, Image.Resampling.LANCZOS)
            resized_img.save(jacket_path)
            
            # Get the new jacket filename (relative path)
            new_jacket_name = os.path.basename(jacket_path)
            
            # Get all related files (both SM and SSC)
            directory = os.path.dirname(filepaths[0])
            base_name = os.path.splitext(os.path.basename(filepaths[0]))[0]
            all_files = []
            
            # Find all related SM and SSC files
            for file in os.listdir(directory):
                if file.startswith(base_name) and file.endswith(('.sm', '.ssc')):
                    all_files.append(os.path.join(directory, file))
            
            # Update JACKET line in all files
            for filepath in all_files:
                content, encoding = MetadataUtil.read_file_with_encoding(filepath)
                if not content:
                    continue
                    
                jacket_line_exists = False
                title_line_index = None
                
                # First pass: look for existing JACKET line and TITLE line
                for i, line in enumerate(content):
                    if line.startswith('#JACKET:'):
                        content[i] = f'#JACKET:{new_jacket_name};\n'
                        jacket_line_exists = True
                    elif line.startswith('#TITLE:'):
                        title_line_index = i
                
                # If no JACKET line exists, add it after TITLE
                if not jacket_line_exists and title_line_index is not None:
                    content.insert(title_line_index + 1, f'#JACKET:{new_jacket_name};\n')
                
                # Write back to file
                with open(filepath, 'w', encoding=encoding) as file:
                    file.writelines(content)
            
            messagebox.showinfo("Success", "Artwork updated successfully!")
            preview_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update artwork: {str(e)}")

    def show_help_dialog(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("StepMania Metadata Editor Help")
        help_window.geometry("800x600")
        
        # Create main frame with scrollbar
        main_frame = ttk.Frame(help_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=750)
        canvas.configure(yscrollcommand=scrollbar.set)
        
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
        
        row = 0
        for section, items in sections.items():
            # Section header
            header = ttk.Label(
                scrollable_frame,
                text=section,
                style="Modern.TLabel",
                font=("Helvetica", 12, "bold")
            )
            header.grid(row=row, column=0, sticky="w", pady=(15,5))
            row += 1
            
            # Section content
            content = ttk.Label(
                scrollable_frame,
                text="\n".join(items),
                style="Modern.TLabel",
                justify=tk.LEFT,
                wraplength=700
            )
            content.grid(row=row, column=0, sticky="w", padx=20)
            row += 1
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Enable mouse wheel scrolling
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Close button
        close_btn = ttk.Button(
            help_window,
            text="Close",
            command=help_window.destroy,
            style="Modern.TButton"
        )
        close_btn.pack(pady=10)

    def cleanup_audio(self):
        if self.current_playing:
            pygame.mixer.music.stop()
            try:
                self.current_playing.configure(text="▶")
            except (tk.TclError, RuntimeError):
                pass
            self.current_playing = None

    def clear_entries(self):
        self.cleanup_audio()
        # Rest of clear_entries method...

    def reload_entries(self):
        self.cleanup_audio()
        # Rest of reload_entries method...

    def clear_directories(self):
        """Clear all loaded directories and reset the UI"""
        # Stop any playing audio
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            if self.current_playing:
                try:
                    self.current_playing.configure(text="▶")
                except (tk.TclError, RuntimeError):
                    pass
                self.current_playing = None
        
        # Clear directories
        self.selected_directories.clear()
        
        # Clear existing entries
        for entry in self.file_entries:
            entry['frame'].destroy()
        self.file_entries.clear()
        
        # Hide buttons
        self.clear_button.pack_forget()
        self.bulk_edit_button.pack_forget()
        self.search_credits_button.pack_forget()
        
        # Remove credit filter
        self.apply_credit_filter(set())

    def collect_credits(self):
        """Collect all unique credits from loaded files"""
        all_credits = set()
        has_no_credits = False
        
        for entry_data in self.file_entries:
            entry_has_credits = False
            for filepath in entry_data['filepaths']:
                metadata = MetadataUtil.read_metadata(filepath)
                if 'CREDITS' in metadata:
                    # Filter out empty or whitespace-only credits
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
        """Show the credit search dialog"""
        credits = self.collect_credits()
        CreditSelector(self.root, sorted(credits), self.apply_credit_filter)

    def apply_credit_filter(self, selected_credits):
        """Filter entries based on selected credits"""
        if not selected_credits:
            # If no credits selected, show all entries
            for entry in self.file_entries:
                entry['frame'].pack()
            # Remove filter indicator if it exists
            if hasattr(self, 'filter_label'):
                self.filter_label.destroy()
                delattr(self, 'filter_label')
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
            
            if show_entry:
                entry['frame'].pack()
            else:
                entry['frame'].pack_forget()
        
        # Update or create filter indicator
        filter_text = f"Showing {shown_count} of {total_count} songs"
        if hasattr(self, 'filter_label'):
            self.filter_label.configure(text=filter_text)
        else:
            self.filter_label = ttk.Label(
                self.button_frame,
                text=filter_text,
                style="Modern.TLabel",
                font=("Helvetica", 10)
            )
            self.filter_label.pack(side=tk.LEFT, padx=10)

class FileEntry:
    def __init__(self, parent_frame, filepaths, metadata, callbacks):
        self.frame = ttk.Frame(parent_frame, style="Modern.TFrame")
        self.filepaths = filepaths
        self.metadata = metadata
        self.callbacks = callbacks
        self.entries = {}
        self.checkbox_var = tk.BooleanVar()
        
        self.setup_ui()
        
    def setup_ui(self):
        self.frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Configure grid columns
        for i, width in enumerate(COLUMN_WIDTHS.values()):
            self.frame.grid_columnconfigure(i, minsize=width)
            
        self.create_checkbox()
        self.create_actions()
        self.create_type_label()
        self.create_metadata_entries()
        
    def create_metadata_entries(self):
        for col, field in enumerate(METADATA_FIELDS, start=4):
            var = tk.StringVar(value=self.metadata.get(field, ''))
            entry = ttk.Entry(self.frame, textvariable=var, style="Modern.TEntry")
            entry.grid(row=0, column=col, padx=5, sticky='ew')
            self.entries[field.lower()] = {
                'var': var,
                'entry': entry,
                'original': self.metadata.get(field, '')
            }
            var.trace_add('write', lambda *args, f=field.lower(): 
                         self.callbacks['on_change'](self, f))
                         
    def has_changes(self):
        return any(e['var'].get() != e['original'] for e in self.entries.values())
        
    def commit_changes(self):
        for entry_data in self.entries.values():
            entry_data['original'] = entry_data['var'].get()
            entry_data['entry'].configure(style='Committed.TEntry')

class CreditSelector:
    def __init__(self, root, credits=None, on_filter=None):
        self.window = tk.Toplevel(root)
        self.window.title("Select Credits")
        self.credits = credits or []
        self.selected_credits = set()
        self.on_filter = on_filter  # Add callback for filtering
        
        # Create custom styles (similar to PackSelector)
        style = ttk.Style()
        style.configure("Credit.TButton", 
                       padding=5,
                       width=30,
                       foreground="black",
                       font=("Helvetica", 10))
        style.configure("CreditSelected.TButton",
                       padding=5,
                       width=30,
                       foreground="green",
                       font=("Helvetica", 10, "bold"))
        
        if not self.credits:
            self.show_no_credits_message()
        else:
            self.setup_ui()
            
    def show_no_credits_message(self):
        # Main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Message
        message = ttk.Label(
            main_frame,
            text="Whoops, no one has claimed credit for these files!",
            style="Modern.TLabel",
            font=("Helvetica", 12),
            wraplength=300,
            justify=tk.CENTER
        )
        message.pack(pady=(20, 30))
        
        # Back button
        ttk.Button(
            main_frame,
            text="Back to Main Menu",
            command=self.window.destroy,
            style="Modern.TButton"
        ).pack()
        
        # Center the window
        self.window.geometry("400x200")
        self.window.transient(self.window.master)
        self.window.grab_set()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info label
        info_text = ("Select credits to filter songs by their creators.\n"
                    "You can select multiple credits to see all songs by those creators.")
        info_label = ttk.Label(
            main_frame,
            text=info_text,
            style="Modern.TLabel",
            wraplength=780,
            justify=tk.CENTER
        )
        info_label.pack(pady=(0, 10))
        
        # Add Select All/Deselect All buttons at the top
        top_button_frame = ttk.Frame(main_frame)
        top_button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            top_button_frame,
            text="Select All",
            command=self.select_all_credits,
            style="Modern.TButton"
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            top_button_frame,
            text="Deselect All",
            command=self.deselect_all_credits,
            style="Modern.TButton"
        ).pack(side=tk.LEFT, padx=5)
        
        # Create scrollable frame for credit buttons
        canvas = tk.Canvas(main_frame, background="#f0f0f0")
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        # Configure grid for buttons (4 columns)
        for i in range(4):
            self.scrollable_frame.grid_columnconfigure(i, weight=1, minsize=200)
        
        # Calculate window size
        num_credits = len(self.credits)
        window_width = min(1200, max(800, (250 * 4) + 50))
        window_height = min(800, max(600, (50 * ((num_credits // 4) + 1)) + 150))
        self.window.geometry(f"{window_width}x{window_height}")
        
        # Create credit buttons
        row = 0
        col = 0
        for credit in sorted(self.credits, key=str.lower):
            btn = ttk.Button(
                self.scrollable_frame,
                text=credit,
                command=lambda c=credit: self.toggle_credit(c),
                style="Credit.TButton"
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Add tooltip
            ToolTip(btn, credit)
            
            col += 1
            if col >= 4:
                col = 0
                row += 1
        
        # Configure scrollable frame width
        self.scrollable_frame.configure(width=window_width - 50)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create bottom button frame
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Add buttons
        ttk.Button(
            button_frame,
            text="Filter by Credit",
            command=self.apply_filter,
            style="Modern.TButton"
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.window.destroy,
            style="Modern.TButton"
        ).pack(side=tk.RIGHT, padx=5)
        
    def toggle_credit(self, credit):
        if credit in self.selected_credits:
            self.selected_credits.remove(credit)
            style = "Credit.TButton"
        else:
            self.selected_credits.add(credit)
            style = "CreditSelected.TButton"
        
        # Update button style
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, ttk.Button) and widget['text'] == credit:
                widget.configure(style=style)
                break
    
    def apply_filter(self):
        if self.on_filter:
            self.on_filter(self.selected_credits)
        self.window.destroy()

    def select_all_credits(self):
        self.selected_credits.update(self.credits)
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.configure(style="CreditSelected.TButton")

    def deselect_all_credits(self):
        self.selected_credits.clear()
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.configure(style="Credit.TButton")

def main():
    root = tk.Tk()
    root.geometry("1600x800")  # Increased width for checkbox column
    root.resizable(False, False)  # Prevent window resizing
    app = MetadataEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()