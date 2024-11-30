# Stepmania Metadata Editor

A user-friendly tool for managing and editing metadata in Stepmania song files (.sm and .ssc formats).

## Features
- 🎵 Browse and edit multiple Stepmania song files from a single screen
- 🎧 Preview song audio directly in the application
- 📝 Batch edit metadata across multiple files
- 🔍 Sort songs by title, subtitle, artist, or pack
- 📁 Quick access to file locations
- 🎵 ShazamIO integration for automatic song identification (and jacket artwork matching!) Goodbye, random genre values!
- 🔍 Filter by #CREDIT to find songs with your favorite creator easily
- 💫 Simple, intuitive interface. Select your song directory and pick which packs you want to view!

## Quick Start
1. Run the application
2. Click "Select Directory" to choose your Stepmania songs folder
3. Browse and edit your song files:
   - Use "..." to open the directory of that specific song
   - Use "▶" to preview the song
   - Use "✎" to open the full metadata editor
   - Edit title, subtitle, artist, or genre directly in the main view

## Interface Guide

### Main View Columns
- Actions: File location, play audio, and metadata editor buttons
- Type: File format (SM/SSC)
- Parent Directory: The song pack name
- Title: Song title (editable)
- Subtitle: Song subtitle (editable)
- Artist: Song artist (editable)
- Genre: Song genre (editable)
- Status: Shows commit status for changes

### Editing Metadata
There are three ways to edit metadata:

1. **Quick Edit**: Directly edit fields in the main view
   - Modified fields will be highlighted in blue
   - Click "Commit?" to save changes
   - Successfully saved changes will be highlighted in green

2. **Bulk Edit**: Edit multiple songs at once
   - Click "Bulk Edit" to enter bulk edit mode
   - Select songs using checkboxes
   - Edit subtitle, artist, or genre for all selected songs
   - Changes are applied to all selected entries

3. **Shazam Integration**: Automatic song identification
   - Click "Shazam Mode" to enable
   - Play a song to automatically identify and fill metadata
   - Confirm changes before committing
   - The app will notify you if Shazam mode is attempted without internet
   - Shazam mode will be disabled until connection is restored

## Requirements
If running from source code:
- Python 3.x
- Required packages:
  - tkinter
  - pygame
  - shazamio
  - nest_asyncio

Or simply run the precompiled exe file.

## Credits
This project uses several open-source libraries:
- [ShazamIO](https://github.com/dotX12/ShazamIO) - For song identification
- [Pygame](https://www.pygame.org/) - For audio playback
- [Tkinter](https://docs.python.org/3/library/tkinter.html) - For the graphical interface

## Notes
- The program is provided as-is and may have limitations
- Contributions and improvements are welcome
- Some features (like ShazamIO) require an internet connection

## License
This project is open source and available under the MIT License.
