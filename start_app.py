#!/usr/bin/env python3
"""
Smart Launcher for DR. NILESH SHAH'S MARKET ANALYSIS
Auto-installs missing packages and starts the app.
"""

import subprocess
import sys
import os

def install_package(package_name):
    """Install a package using pip."""
    print(f"  Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "-q"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "-q", "--user"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            return False

def check_and_install():
    """Check all dependencies and install if missing."""
    
    packages = {
        'yfinance': 'yfinance',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'ta': 'ta',
        'sklearn': 'scikit-learn',
        'openpyxl': 'openpyxl',
        'reportlab': 'reportlab',
        'pdfplumber': 'pdfplumber',
        'schedule': 'schedule',
        'PIL': 'Pillow',
        'pytz': 'pytz',
        'matplotlib': 'matplotlib',
        'requests': 'requests',
        'keyring': 'keyring',
    }
    
    missing = []
    
    print("=" * 60)
    print("DR. NILESH SHAH'S MARKET ANALYSIS")
    print("Checking Dependencies...")
    print("=" * 60)
    print()
    
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [MISSING] {package}")
            missing.append(package)
    
    if missing:
        print()
        print(f"Installing {len(missing)} missing packages...")
        print()
        
        for package in missing:
            if install_package(package):
                print(f"  [INSTALLED] {package}")
            else:
                print(f"  [FAILED] {package} - Please install manually: pip install {package}")
    
    print()
    print("=" * 60)
    print("Starting Application...")
    print("=" * 60)
    print()

# Run checks
check_and_install()

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import and run the main app
try:
    # Now import the main app
    import dr_shah_analysis
    dr_shah_analysis.main()
except ImportError as e:
    print(f"ERROR: Could not import main app: {e}")
    print()
    print("Make sure these files are in the same folder:")
    print("  - dr_shah_analysis.py")
    print("  - daily_report.py")
    print("  - ai_engine.py")
    print("  - pattern_recognition.py")
    print("  - live_trading.py")
    print("  - logo_new.png")
    input("\nPress Enter to exit...")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to exit...")
