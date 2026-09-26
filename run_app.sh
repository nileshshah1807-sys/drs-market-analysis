#!/bin/bash

echo "========================================"
echo " DR. NILESH SHAH'S MARKET ANALYSIS"
echo "========================================"
echo ""

# Run from this script's folder
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Install Python 3:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-tk"
    echo "  Mac: brew install python python-tk"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Install dependencies into the same Python that runs the app
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt --quiet

echo ""
echo "Starting application..."
python3 dr_shah_analysis.py
