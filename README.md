# StepMania Metadata Editor
## Version 1.1 - Now with PyQt6!

A powerful, simple tool for managing StepMania song metadata with an intuitive interface and advanced features.

![Untitled design](https://github.com/user-attachments/assets/a21b1ef3-b811-4798-8d0d-f2afde1ad379)



## 🌟 New in 1.1
- Complete rewrite using PyQt6 for a modern, responsive interface
- Enhanced performance for large song collections
- Real-time search filtering
- Improved bulk editing capabilities
- Better audio playback controls
- Enhanced Shazam integration with artwork comparison
- Rainbow mode! 🌈

## ✨ Features

### Core Features
- 📝 Edit multiple StepMania files (.sm/.ssc) simultaneously
- 🎵 Preview audio directly in the application
- 📊 Sort by any column (pack, title, artist, etc.)
- 🔍 Real-time search filtering
- 📁 Quick access to file locations
- 💾 Commit changes individually or all at once


### Advanced Features
- 🎵 Shazam Integration
  - Automatic song identification
  - Album artwork detection and comparison
  - One-click metadata updates
  - (Verify before commiting as Shazam isn't always right! Tim McGraw definitely isn't rave music!)
- 📝 Bulk Editing
  - Edit multiple songs simultaneously
  - Update credits across multiple files
  - Smart selection tools
- 🖼️ Artwork Management
  - Compare current and Shazam artwork
  - Auto-update jacket images
  - Maintain 1:1 aspect ratio
- 📝 Export your data to CSV.

## 🚀 Quick Start

1. Launch the application
2. Click "Pick Directory" to select your StepMania songs folder
3. Choose which packs to load
4. Start editing:
   - 📁 Open file location
   - ▶️ Preview audio
   - ✏️ Edit metadata
   - 💾 Commit changes

## 🎨 Interface Guide

### Main Table Columns
- ☑️ Selection checkbox
- 🔧 Actions (folder, play, edit)
- 📄 File type (SM/SSC)
- 📁 Pack name
- 🎵 Title
- 📝 Subtitle
- 👤 Artist
- 🎼 Genre
- ⚠️ Status
- 💾 Commit

### Editing Modes

#### Direct Edit
- Click any editable field
- Make changes
- Commit individually or all at once

#### Bulk Edit
1. Click "Bulk Edit"
2. Select multiple songs
3. Edit shared fields
4. Apply changes to all selected songs

#### Shazam Mode
1. Enable "Shazam Mode"
2. Play any song
3. Review suggested metadata
4. Accept or reject changes (left click to accept, right click to say no!)
5. Optionally update artwork
   ***Sorting will cause your suggestions to not be clickable if you didn't click before sorting. You will need to re-analyze the song or make your decision before. 

## 🛠️ Technical Requirements

### Running from Source
- Python 3.8+
- Required packages:
  - PyQt6
  - pygame
  - shazamio
  - nest_asyncio
  - Pillow
  - requests

### Precompiled Version
- Windows (can be compiled in Mac as well)
- No additional dependencies required


## 🙏 Credits

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [ShazamIO](https://github.com/dotX12/ShazamIO)
- [Pygame](https://www.pygame.org/)
- [Pillow](https://python-pillow.org/)


---

Made with ❤️ for the StepMania community
