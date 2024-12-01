import os
import PyInstaller.__main__
import shutil

# Get the source directory
source_dir = "C:/Users/Thoma/OneDrive/Documents/GitHub/SM_Metadata_Editor"

# Define source files and output names
builds = [
    {
        "source": "SM_Metadata_Editor.py",
        "output": "SM_Metadata_Editor"
    },
    {
        "source": "SM_Metadata_Editor_PYQT6_Migration.py",
        "output": "SM_Metadata_Editor_v1_1"
    }
]

# Clean up old builds
dist_dir = os.path.join(source_dir, "dist")
build_dir = os.path.join(source_dir, "build")
if os.path.exists(dist_dir):
    shutil.rmtree(dist_dir)
if os.path.exists(build_dir):
    shutil.rmtree(build_dir)

# Build each executable
for build in builds:
    print(f"\nBuilding {build['output']}...")
    source_file = os.path.join(source_dir, build['source'])
    
    PyInstaller.__main__.run([
        '--onefile',
        '--noconsole',
        f'--name={build["output"]}',
        '--clean',
        '--noupx',
        '--noconfirm',
        source_file
    ])

    # Move the executable
    exe_name = f"{build['output']}.exe"
    source_exe = os.path.join(dist_dir, exe_name)
    dest_exe = os.path.join(source_dir, exe_name)

    if os.path.exists(dest_exe):
        os.remove(dest_exe)
    shutil.move(source_exe, source_dir)

    # Clean up build directories
    shutil.rmtree(dist_dir)
    shutil.rmtree(build_dir)
    spec_file = f"{build['output']}.spec"
    if os.path.exists(spec_file):
        os.remove(spec_file)

print("\nBuild complete!")
print("Executables created:")
for build in builds:
    print(f"- {os.path.join(source_dir, build['output'] + '.exe')}")