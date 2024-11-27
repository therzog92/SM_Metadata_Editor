import tkinter as tk
from tkinter import filedialog, ttk
import os
import subprocess
import pygame
from collections import defaultdict
import fnmatch



class MetadataEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Stepmania Metadata Editor")
        self.root.resizable(False, False)
        
        # Initialize pygame mixer for audio
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"  # Add this line
        pygame.mixer.init()
        self.current_playing = None
        
        # Configure modern style
        style = ttk.Style()
        style.configure("Modern.TFrame", background="#f0f0f0")
        style.configure("Modern.TButton", padding=5, relief="flat", background="#4a90e2", foreground="black")
        style.configure("Modern.TLabel", background="#f0f0f0", foreground="#333333", font=("Helvetica", 10))
        style.configure("Modern.TEntry", padding=5, relief="flat")
        style.configure("Header.TButton", font=("Helvetica", 10, "bold"))
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10", style="Modern.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create directory picker button
        self.dir_button = ttk.Button(self.main_frame, text="Select Directory", 
                                   command=self.pick_directory, style="Modern.TButton")
        self.dir_button.pack(pady=10)
        
        # Create frame for file entries
        self.files_frame = ttk.Frame(self.main_frame, style="Modern.TFrame")
        self.files_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create headers frame with grid
        self.headers_frame = ttk.Frame(self.files_frame, style="Modern.TFrame")
        self.headers_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure grid columns
        for i in range(8):  # Increased to 8 for new Genre column
            self.headers_frame.grid_columnconfigure(i, weight=1)
            
        # Fixed column widths
        self.headers_frame.grid_columnconfigure(0, minsize=130)  # Actions column
        self.headers_frame.grid_columnconfigure(1, minsize=75)   # File type column
        self.headers_frame.grid_columnconfigure(2, minsize=160)  # Parent dir column
        self.headers_frame.grid_columnconfigure(3, minsize=250)  # Title column
        self.headers_frame.grid_columnconfigure(4, minsize=250)  # Subtitle column 
        self.headers_frame.grid_columnconfigure(5, minsize=250)  # Artist column
        self.headers_frame.grid_columnconfigure(6, minsize=250)  # Genre column
        self.headers_frame.grid_columnconfigure(7, minsize=50)   # Status column
        
        # Create headers
        headers = ["Actions", "Type", "Parent Directory", "Title", "Subtitle", "Artist", "Genre", "Status"]
        for i, header in enumerate(headers):
            if header in ["Parent Directory", "Title", "Subtitle", "Artist", "Genre"]:
                btn = ttk.Button(self.headers_frame, text=header, width=15,
                               command=lambda h=header.lower().replace(" ", "_"): self.sort_entries(h),
                               style="Header.TButton")
                btn.grid(row=0, column=i, padx=5, sticky='n')
            else:
                lbl = ttk.Label(self.headers_frame, text=header, style="Modern.TLabel")
                lbl.grid(row=0, column=i, padx=(25,15), sticky='ew')  # Increased left padding for Actions and Type
        
        # Create scrollable frame
        self.canvas = tk.Canvas(self.files_frame, background="#f0f0f0", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.files_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="Modern.TFrame")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=1500)  # Increased width
        self.canvas.configure(yscrollcommand=scrollbar.set)
        # Enable mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Store file entries and sorting state
        self.file_entries = []
        self.sort_reverse = {'parent_directory': False, 'title': False, 'subtitle': False, 'artist': False, 'genre': False}
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def play_audio(self, music_path, play_btn):
        directory = os.path.dirname(music_path)
        music_name = os.path.basename(music_path)
        base_name = os.path.splitext(music_name)[0]
        
        # Stop current playing audio if any
        if self.current_playing:
            pygame.mixer.music.stop()
            self.current_playing.configure(text="▶")
            if self.current_playing == play_btn:
                self.current_playing = None
                return
                
        # Search for matching audio file
        for file in os.listdir(directory):
            if file.lower().endswith(('.ogg', '.mp3', '.wav')) and base_name.lower() in file.lower():
                try:
                    full_path = os.path.join(directory, file)
                    pygame.mixer.music.load(full_path)
                    pygame.mixer.music.play()
                    play_btn.configure(text="⏹")
                    self.current_playing = play_btn
                    return
                except Exception as e:
                    print(f"Error playing audio {full_path}: {str(e)}")
                    return

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
        
        # Configure grid
        for i in range(8):  # Increased to 8 for Genre column
            frame.grid_columnconfigure(i, weight=1)
        # Fixed column widths
        frame.grid_columnconfigure(0, minsize=130)  # Actions column
        frame.grid_columnconfigure(1, minsize=75)   # File type column
        frame.grid_columnconfigure(2, minsize=160)  # Parent dir column
        frame.grid_columnconfigure(3, minsize=250)  # Title column
        frame.grid_columnconfigure(4, minsize=250)  # Subtitle column 
        frame.grid_columnconfigure(5, minsize=250)  # Artist column
        frame.grid_columnconfigure(6, minsize=250)  # Genre column
        frame.grid_columnconfigure(7, minsize=50)   # Status column
        
        # Actions frame
        actions_frame = ttk.Frame(frame, style="Modern.TFrame")
        actions_frame.grid(row=0, column=0, padx=5)
        
        # Open button
        open_btn = ttk.Button(actions_frame, text="...", width=2,
                             command=lambda: self.open_file_location(os.path.dirname(filepaths[0])),
                             style="Modern.TButton")
        open_btn.pack(side=tk.LEFT, padx=2)
        
        # Play button
        music_path = os.path.join(os.path.dirname(filepaths[0]), music_file)
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
        type_label = ttk.Label(frame, text="+".join(file_types), style="Modern.TLabel")
        type_label.grid(row=0, column=1, padx=5)
        
        # Parent directory (uneditable)
        parent_label = ttk.Label(frame, text=parent_dir, style="Modern.TLabel")
        parent_label.grid(row=0, column=2, padx=5)
        
        # Create entry fields
        entries = {}
        original_values = {'title': title, 'subtitle': subtitle, 'artist': artist, 'genre': genre}
        
        col = 3
        for field, value in original_values.items():
            var = tk.StringVar(value=value)
            entry = ttk.Entry(frame, textvariable=var, style="Modern.TEntry")
            entry.grid(row=0, column=col, padx=5, sticky='ew')
            entries[field] = {'var': var, 'entry': entry, 'original': value}
            
            # Bind to changes
            var.trace_add('write', lambda *args, f=field, 
                         e=entries[field]: self.on_entry_change(frame, filepaths, f, e))
            col += 1
        
        # Commit button (initially hidden)
        commit_btn = ttk.Button(frame, text="Commit?", width=10,
                              command=lambda: self.commit_changes(frame, filepaths, entries),
                              style="Modern.TButton")
        commit_btn.grid(row=0, column=7, padx=5, sticky='e')
        commit_btn.grid_remove()
        
        entry_data = {
            'frame': frame,
            'filepaths': filepaths,
            'entries': entries,
            'commit_btn': commit_btn,
            'parent_dir': parent_dir
        }
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
        
    def on_entry_change(self, frame, filepaths, field, entry_data):
        new_value = entry_data['var'].get()
        commit_btn = [w for w in frame.winfo_children() if isinstance(w, ttk.Button) and w['text'] in ["Commit?", "Committed"]][0]
        
        if new_value != entry_data['original']:
            entry_data['entry'].configure(style='Modified.TEntry')
            commit_btn.configure(text="Commit?", style='Warning.TButton', state='normal')
            commit_btn.grid()
        else:
            entry_data['entry'].configure(style='Modern.TEntry')
            if all(e['var'].get() == e['original'] for e in [entry for entry in frame.entries.values()]):
                commit_btn.grid_remove()
            
    def commit_changes(self, frame, filepaths, entries):
        for filepath in filepaths:
            try:
                # Read file content
                with open(filepath, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                
                # Update the lines
                for i, line in enumerate(lines):
                    for field, entry_data in entries.items():
                        field_upper = field.upper()
                        if line.startswith(f'#{field_upper}:'):
                            new_value = entry_data['var'].get()
                            lines[i] = f'#{field_upper}:{new_value};\n'
                            entry_data['original'] = new_value
                            entry_data['entry'].configure(style='Committed.TEntry')
                
                # Write back to file
                with open(filepath, 'w', encoding='utf-8') as file:
                    file.writelines(lines)
            except Exception as e:
                print(f"Error updating file {filepath}: {str(e)}")
                return
        
        # Update commit button
        commit_btn = [w for w in frame.winfo_children() if isinstance(w, ttk.Button) and w['text'] in ["Commit?", "Committed"]][0]
        commit_btn.configure(text="Committed", style='Success.TButton', state='disabled')
        
    def sort_entries(self, field):
        self.sort_reverse[field] = not self.sort_reverse[field]
        
        if field == 'parent_directory':
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
            self.load_files(directory)
    
    def load_files(self, directory):
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
            
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.sm', '.ssc')):
                    filepath = os.path.join(root, file)
                    base_name = os.path.splitext(file)[0]
                    file_groups[base_name].append(filepath)
        
        # Create entries for each unique song
        for base_name, filepaths in file_groups.items():
            # Use metadata from first file
            metadata = self.read_metadata(filepaths[0])
            parent_parent_dir = os.path.basename(os.path.dirname(os.path.dirname(filepaths[0])))
            
            self.create_file_entry(
                filepaths,
                parent_parent_dir,
                metadata.get('TITLE', ''),
                metadata.get('SUBTITLE', ''),
                metadata.get('ARTIST', ''),
                metadata.get('GENRE', ''),
                metadata.get('MUSIC', '')
            )
    
    def read_metadata(self, filepath):
        metadata = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                for line in file:
                    if line.startswith(('#TITLE:', '#SUBTITLE:', '#ARTIST:', '#GENRE:', '#MUSIC:')):
                        key, value = line.strip().split(':', 1)
                        key = key[1:]  # Remove the # character
                        value = value.rstrip(';')
                        metadata[key] = value
        except Exception as e:
            print(f"Error reading metadata from {filepath}: {str(e)}")
        return metadata

def main():
    root = tk.Tk()
    root.geometry("1550x800")  # Increased width for Genre column
    app = MetadataEditor(root)
    root.mainloop()
 

if __name__ == "__main__":
    main()