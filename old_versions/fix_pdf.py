#!/usr/bin/env python3
"""
Fix PDF Export - Install required packages
Run this script to fix PDF export issues.
"""

import subprocess
import sys

print("=" * 50)
print("DR. NILESH SHAH'S MARKET ANALYSIS")
print("PDF Export Fix Tool")
print("=" * 50)

packages = ['reportlab', 'Pillow']

for pkg in packages:
    print(f"\nInstalling {pkg}...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])
        print(f"[OK] {pkg} installed successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to install {pkg}: {e}")

print("\n" + "=" * 50)
print("Testing installation...")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    print("[OK] ReportLab working!")
    
    from PIL import Image
    print("[OK] PIL working!")
    
    print("\n[SUCCESS] All packages installed correctly!")
    print("\nNow run: python dr_shah_analysis.py")
    
except Exception as e:
    print(f"[ERROR] {e}")
    print("\nTry restarting your terminal and running again.")

input("\nPress Enter to exit...")
