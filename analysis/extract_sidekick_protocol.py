#!/usr/bin/env python3
"""Extract Sidekick protocol from host-side files."""
import os
import struct
from pathlib import Path

sidekick_dir = Path("osd-sidekick/B21.0707.1")
print(f"Inspecting {sidekick_dir}")
for f in sidekick_dir.iterdir():
    print(f"  {f.name}: {f.stat().st_size} bytes")

# Read support.xml
with open(sidekick_dir / "support.xml", 'r') as f:
    print("\n" + f.read())

# Try to extract strings from Install.exe and UpdPack.cab
import subprocess
try:
    # Use strings equivalent
    result = subprocess.run(['strings', str(sidekick_dir / 'Install.exe')], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                          timeout=30)
    out = result.stdout.decode('latin-1', errors='ignore')
    # Look for relevant strings
    for line in out.splitlines():
        if any(x in line.lower() for x in ['apcs', 'aocs', 'oled', 'e0', '80', '82', 'ddc', 'hid', 'vid', '0bda']):
            if len(line) < 80:
                print(f"STR: {line}")
except Exception as e:
    print(f"Error: {e}")
