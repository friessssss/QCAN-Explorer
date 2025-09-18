#!/usr/bin/env python3
"""
Create macOS App Bundle for QCAN Explorer
This script creates a proper .app bundle for macOS with the correct icon and metadata.
"""

import os
import shutil
import sys
from pathlib import Path

def create_app_bundle():
    """Create a macOS .app bundle"""
    app_name = "QCAN Explorer"
    bundle_name = f"{app_name}.app"
    
    # Create app bundle structure
    bundle_path = Path(bundle_name)
    contents_path = bundle_path / "Contents"
    macos_path = contents_path / "MacOS"
    resources_path = contents_path / "Resources"
    
    # Clean up existing bundle
    if bundle_path.exists():
        shutil.rmtree(bundle_path)
    
    # Create directories
    macos_path.mkdir(parents=True)
    resources_path.mkdir(parents=True)
    
    # Copy Info.plist
    if Path("Info.plist").exists():
        shutil.copy2("Info.plist", contents_path / "Info.plist")
    
    # Copy logo as icon
    if Path("logo.png").exists():
        shutil.copy2("logo.png", resources_path / "logo.png")
    
    # Create launcher script
    launcher_script = f"""#!/bin/bash
cd "$(dirname "$0")/../../../"
python3 main.py
"""
    
    launcher_path = macos_path / app_name
    with open(launcher_path, 'w') as f:
        f.write(launcher_script)
    
    # Make launcher executable
    os.chmod(launcher_path, 0o755)
    
    print(f"✅ Created {bundle_name}")
    print(f"📁 Bundle location: {bundle_path.absolute()}")
    print(f"🚀 You can now double-click {bundle_name} to launch QCAN Explorer!")
    
    return bundle_path

if __name__ == "__main__":
    create_app_bundle()
