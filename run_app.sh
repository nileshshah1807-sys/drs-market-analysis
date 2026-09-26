#!/bin/bash

echo "========================================"
echo " Indian Stock Technical Scanner"
echo "========================================"
echo ""

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

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt --quiet

echo ""
echo "Starting application..."
python3 stock_scanner.py 2>/dev/null || python stock_scanner.py
