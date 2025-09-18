# QCAN Explorer

A modern, cross-platform CAN network analysis tool built with Python and PyQt6. QCAN Explorer provides professional-grade CAN bus monitoring, message transmission, symbolic decoding, and data logging capabilities in an intuitive graphical interface.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

## ✨ Key Features

### 🔍 **Real-time CAN Bus Monitoring**

- **Expandable Message Tree**: Message names shown by default, expand to see individual signals
- **Built-in SYM File Loading**: Load symbol files directly from Monitor tab
- Live message display with sortable, filterable tables
- Color-coded TX/RX messages and extended ID support
- Automatic period calculation and message statistics
- Detailed hex/binary/decimal data views with signal decoding

### 📤 **Message Transmission**

- Manual and periodic message transmission
- Transmit list management with save/load functionality
- Extended ID and remote frame support
- Configurable timing and repeat options

### 🏷️ **Symbolic Representation**

- SYM file support for message decoding (PCAN Symbol Editor format)
- Real-time signal value display with units and enumerations
- Database browser with message/signal details
- Automatic message interpretation

### 💾 **Data Logging & Playback**

- **Professional Text Display**: Messages shown in industry-standard format with message names
- **Hover Tooltips**: Decoded signal values appear on hover (with SYM files)
- **Wide Message Names**: Full symbolic message names visible in dedicated column
- Record CAN traffic in CSV, JSON, ASC, and TRC formats
- **Streamlined Controls**: Start/Stop/Clear/Save/Open/Format on single row
- **No Message Limits**: Log unlimited messages
- Open existing log files for analysis
- Background file operations with progress indication

### 📈 **Real-time Signal Plotting**

- **Full-Width Interactive Plots**: Maximum plotting area with popup signal selection
- **Dual-Mode Operation**: Real-time CAN monitoring + historical trace file analysis
- **Multiple Signal Overlay**: Plot unlimited signals with automatic color assignment
- **Professional Analysis**: Interactive zoom, pan, and measurement tools
- **Smart Signal Selection**: Popup dialog with full signal names and multi-selection
- **Data Export**: Save plots as images (PNG, JPEG) and data as CSV
- **Flexible Display**: Auto-scaling, grid, legend, and configurable time windows

### 🔌 **Multi-Interface Support**

- SocketCAN, PCAN, Vector, Kvaser, and more
- **Virtual CAN**: Built-in virtual CAN network for testing without hardware
- Automatic interface detection
- Simultaneous multi-interface connections
- Robust error handling and recovery

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

**Linux/macOS:**

```bash
./run.sh
```

**Windows:**

```cmd
run.bat
```

### Option 2: Manual Installation

1. **Install Python 3.8+** from [python.org](https://python.org)

2. **Clone/Download** this repository

3. **Install dependencies:**

   ```bash
   # Install core dependencies
   pip install -r requirements-minimal.txt
   
   # Optional: Install additional packages for enhanced features
   pip install numpy pandas pyqtgraph
   ```

4. **Run the application:**

   ```bash
   python main.py
   ```

### Troubleshooting

**Import Issues**: If you encounter import errors, ensure you're running the script from the project root directory.

**Dependency Issues**: If pandas fails to build (especially on Python 3.13), use the minimal requirements:

```bash
pip install -r requirements-minimal.txt
```

The application will work fine without pandas - it's only used for enhanced data processing features.

## Supported CAN Interfaces

- SocketCAN (Linux)
- PCAN (Windows/Linux/macOS)
- Vector (Windows)
- IXXAT (Windows)
- NI-CAN (Windows)
- Kvaser (Windows/Linux)

## Usage

1. **Connect to CAN Interface**: Select your CAN interface (including Virtual for testing) from the dropdown and configure settings
2. **Monitor Messages**: View real-time CAN traffic in the monitoring tab
3. **Send Messages**: Use the transmission tab to send custom messages
4. **Load Symbol Files**: Import SYM files for symbolic message interpretation
5. **Record Data**: Use the logging feature to capture and analyze CAN traffic

## File Formats Supported

- **SYM Files**: PCAN Symbol Editor format for symbolic message definitions
- **Log Files**: CSV, JSON, ASC, TRC formats for data logging
- **Configuration Files**: JSON format for saving/loading setups

## Virtual CAN Network

QCAN Explorer includes a built-in virtual CAN network for testing without hardware:

- **Realistic Message Generation**: 7 different message types with varying data
- **Symbolic Decoding**: Includes matching SYM file (`examples/sym/virtual_can_network.sym`)
- **Control Interface**: Virtual CAN tab for managing message generation
- **Demo Script**: Run `python examples/demo_virtual_can.py` to see it in action

### Virtual Message Types:
- `0x100`: Engine RPM, Load, Temperature, Throttle (500ms - 2Hz)
- `0x101`: Vehicle Speed, Odometer (1000ms - 1Hz)
- `0x200`: Door/Window Status, Lights (2000ms - 0.5Hz)
- `0x300`: Battery, Fuel, Electrical (5000ms - 0.2Hz)
- `0x400`: Climate Control (10000ms - 0.1Hz)
- `0x7E0/0x7E8`: Diagnostic Messages (20000ms - 0.05Hz)

### Rate Control Features:
- **Speed Up (÷2)**: Double message rates by halving periods
- **Slow Down (×2)**: Halve message rates by doubling periods
- **Real-time Adjustment**: Change rates while virtual network is running
- **Individual Control**: Enable/disable specific message types

## License

MIT License - See LICENSE file for details
