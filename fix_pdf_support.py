#!/usr/bin/env python3
"""
Fix PDF Support Script
======================
Run this script to diagnose and fix pdfplumber installation issues.
"""

import sys
import subprocess
import os

print("=" * 60)
print("PDF Support Diagnostic & Fix Tool")
print("=" * 60)
print(f"\nPython executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}...")

print("\n" + "-" * 60)
print("Step 1: Checking if pdfplumber is installed...")
print("-" * 60)

try:
    import pdfplumber
    print(f"[OK] pdfplumber version: {pdfplumber.__version__}")
    print(f"[OK] pdfplumber location: {pdfplumber.__file__}")
    
    # Test if it actually works
    print("\nTesting pdfplumber functionality...")
    
    # Create a simple test PDF
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        test_pdf = "test_pdf_support.pdf"
        c = canvas.Canvas(test_pdf, pagesize=letter)
        c.drawString(100, 700, "RELIANCE TCS INFY HDFCBANK")
        c.save()
        
        # Try to read it
        with pdfplumber.open(test_pdf) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    print(f"[OK] PDF text extraction works: '{text[:50]}...'")
                else:
                    print("[WARNING] PDF text extraction returned empty")
        
        # Clean up
        if os.path.exists(test_pdf):
            os.remove(test_pdf)
        
        print("\n[SUCCESS] pdfplumber is installed and working correctly!")
        print("\nIf the app still shows an error, try restarting it.")
        
    except ImportError:
        print("[WARNING] reportlab not available for testing, but pdfplumber is installed")
        print("[OK] pdfplumber should work for basic PDF parsing")
    
    except Exception as e:
        print(f"[WARNING] Test failed: {e}")
        print("[OK] pdfplumber is installed, but there may be a runtime issue")

except ImportError as e:
    print(f"[NOT FOUND] pdfplumber is not installed: {e}")
    print("\n" + "-" * 60)
    print("Step 2: Installing pdfplumber...")
    print("-" * 60)
    
    try:
        print(f"\nRunning: {sys.executable} -m pip install pdfplumber")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pdfplumber"],
            capture_output=True,
            text=True
        )
        
        print(f"\nReturn code: {result.returncode}")
        
        if result.stdout:
            print(f"Output:\n{result.stdout}")
        
        if result.stderr:
            print(f"Errors:\n{result.stderr}")
        
        if result.returncode == 0:
            print("\n[SUCCESS] pdfplumber installed successfully!")
            print("\nPlease restart the stock scanner application.")
            
            # Verify installation
            try:
                import importlib
                importlib.invalidate_caches()
                import pdfplumber
                print(f"[OK] Verified: pdfplumber version {pdfplumber.__version__}")
            except ImportError:
                print("[INFO] You may need to restart your Python environment")
        else:
            print("\n[FAILED] Installation failed!")
            print("\nManual installation steps:")
            print("1. Open Command Prompt (Windows) or Terminal (Mac/Linux)")
            print("2. Run: pip install pdfplumber")
            print("3. If that fails, try: pip install --user pdfplumber")
            print("4. Or try: python -m pip install pdfplumber")
            
    except Exception as e:
        print(f"\n[ERROR] Could not run pip: {e}")
        print("\nManual installation:")
        print("1. Open Command Prompt/Terminal")
        print("2. Navigate to Python Scripts folder")
        print("3. Run: pip install pdfplumber")

print("\n" + "=" * 60)
print("Additional Troubleshooting")
print("=" * 60)
print("""
If pdfplumber is installed but the app still shows an error:

1. CHECK PYTHON ENVIRONMENT:
   - You might have multiple Python installations
   - The app might use a different Python than where you installed pdfplumber
   - Run: where python (Windows) or which python (Mac/Linux)
   - Make sure you install pdfplumber for the SAME Python

2. REINSTALL pdfplumber:
   pip uninstall pdfplumber
   pip install pdfplumber

3. CHECK PIP VERSION:
   python -m pip --version
   python -m pip install --upgrade pip
   python -m pip install pdfplumber

4. VIRTUAL ENVIRONMENT:
   If using a virtual environment, make sure it's activated:
   - Windows: .\\venv\\Scripts\\activate
   - Mac/Linux: source venv/bin/activate
   Then install: pip install pdfplumber

5. PERMISSION ISSUES:
   - Windows: Run Command Prompt as Administrator
   - Mac/Linux: Use sudo or --user flag
   pip install --user pdfplumber

6. RESTART THE APP:
   After installing, always restart the stock scanner app
""")

input("\nPress Enter to exit...")
