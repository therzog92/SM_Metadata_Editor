import os
import PyInstaller.__main__
import shutil

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
source_file = os.path.join(current_dir, "SM_Metadata_Editor.py")

# Clean up old builds
dist_dir = os.path.join(current_dir, "dist")
build_dir = os.path.join(current_dir, "build")
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)
if os.path.exists(build_dir):
    shutil.rmtree(build_dir)

# Build one-file executable
print("Building one-file executable...")
PyInstaller.__main__.run([
    '--onefile',
    '--noconsole',
    '--name=SM_Metadata_Editor',
    '--clean',
    '--noupx',
    '--noconfirm',
    source_file
])

# Move the one-file executable
exe_name = "SM_Metadata_Editor.exe"
source_exe = os.path.join(dist_dir, exe_name)
dest_exe = os.path.join(current_dir, exe_name)

if os.path.exists(dest_exe):
    os.remove(dest_exe)
shutil.move(source_exe, current_dir)

# Clean up build directories
shutil.rmtree(dist_dir)
shutil.rmtree(build_dir)
if os.path.exists("SM_Metadata_Editor.spec"):
    os.remove("SM_Metadata_Editor.spec")

print(f"\nBuild complete!")
print(f"Executable created at: {dest_exe}")