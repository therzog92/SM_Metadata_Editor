import os
import PyInstaller.__main__
import shutil

# Get the source directory
source_dir = os.path.dirname(os.path.abspath(__file__))

# Define icon path relative to source directory
icon_path = os.path.join(source_dir, "Assets", "icon.ico")

# Verify icon exists
if not os.path.exists(icon_path):
    raise FileNotFoundError(f"Icon file not found at: {icon_path}")

print(f"Using icon from: {icon_path}")

# Define source files and output names
builds = [
    {
        "source": "SM_Metadata_Editor_v1_1.py",
        "output": "SM_Metadata_Editor_v1_1"
    },
    {
        "source": "SM_Metadata_Editor_v1_1.py",
        "output": "SM_Metadata_Editor_v1_1_WithConsole",
        "console": True
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
    
    options = [
        '--onefile',
        '--clean',
        '--noupx',
        '--noconfirm',
        f'--icon={icon_path}',
        f'--name={build["output"]}',
        source_file
    ]
    
    # Add noconsole option only if console is not explicitly True
    if not build.get('console', False):
        options.insert(3, '--noconsole')
    
    PyInstaller.__main__.run(options)

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