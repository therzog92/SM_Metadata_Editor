# Stepmania Metadata Editor

A simple, user-friendly tool for managing and editing metadata in Stepmania song files (.sm and .ssc formats).

## Features

- 🎵 Browse and edit multiple Stepmania song files from a single screen
- 🎧 Preview song audio directly in the application
- 📝 Batch edit metadata across multiple files
- 🔍 Sort songs by title, subtitle, artist, or parent directory
- 📁 Quick access to file locations
- 💫 Simple albeit remedial interface

## Quick Start

1. Run the application
2. Click "Select Directory" to choose your Stepmania songs folder
3. Browse and edit your song files:
   - Use "..." to open the open the directory of that specific song if you want to access it quickly
   - Use "▶" to preview the song
   - Use "✎" to open the full metadata editor to adjust values other than Title, Subtitle, Artist
   - Edit title, subtitle, or artist directly in the main view

## Interface Guide

### Main View Columns
- **Actions**: File location, play audio, and metadata editor buttons
- **Type**: File format (SM/SSC)
- **Parent Directory**: The song pack name
- **Title**: Song title (editable)
- **Subtitle**: Song subtitle (editable)
- **Artist**: Song artist (editable)
- **Status**: Shows commit status for changes

### Editing Metadata

There are two ways to edit metadata:

1. **Quick Edit**: Directly edit title, subtitle, or artist in the main view
   - Modified fields will be highlighted in blue
   - Click "Commit?" to save changes
   - Successfully saved changes will be highlighted in green and show as Commited

2. **Full Metadata Editor**: Click the "✎" button to open
   - Edit all available metadata fields
   - Click "Commit Changes" to save
   - Click "Close" to exit without saving

## Requirements
If running from the source code you'll need:

- Python 3.x
- Required packages:
  - tkinter
  - pygame
  - os
  - subprocess
 
  Or just click the precompiled exe file to run the program. 


## Notes:
- The program might not be perfect (you can copy a pack or two to do some testing if you'd like).
- I'm not much of a coder so I won't be supporting this I just wanted something to quickly edit items and thought I'd share
  -- feel free to steal this and make it better, add features, etc. 
