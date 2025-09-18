#!/bin/bash
# Quick start script for QCAN Explorer

echo "QCAN Explorer - CAN Network Analysis Tool"
echo "=========================================="
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

echo "Python version: $python_version ✓"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
echo "Installing minimal requirements first..."
pip install -r requirements-minimal.txt

echo "Attempting to install additional packages..."
pip install numpy>=1.21.0 || echo "Warning: numpy installation failed, continuing without it"
pip install pandas>=2.2.0 || echo "Warning: pandas installation failed, continuing without it"  
pip install pyqtgraph>=0.13.0 || echo "Warning: pyqtgraph installation failed, continuing without it"

# Run the application
echo "Starting QCAN Explorer..."
echo
python main.py
