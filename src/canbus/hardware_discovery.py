"""
Hardware Discovery System
Automatically discovers and enumerates available CAN hardware interfaces
"""

import platform
import subprocess
import re
from typing import List, Dict, Set
from pathlib import Path

from .network import HardwareInterface


class HardwareDiscovery:
    """Discovers available CAN hardware interfaces"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.discovered_interfaces: List[HardwareInterface] = []
        
    def discover_interfaces(self) -> List[HardwareInterface]:
        """Discover all available CAN hardware interfaces"""
        # Use the safer discovery method by default
        return self.discover_interfaces_safe()
        
    def _discover_virtual_interfaces(self) -> List[HardwareInterface]:
        """Discover virtual CAN interfaces"""
        interfaces = []
        
        # Create multiple virtual interfaces for testing
        for i in range(4):  # virtual0 through virtual3
            interface = HardwareInterface(
                interface_type='virtual',
                channel=f'virtual{i}',
                name=f'Virtual CAN {i}',
                description=f'Virtual CAN interface for testing and simulation (Channel {i})',
                available=True
            )
            interfaces.append(interface)
            
        return interfaces
        
    def _discover_socketcan_interfaces(self) -> List[HardwareInterface]:
        """Discover SocketCAN interfaces (Linux)"""
        interfaces = []
        
        try:
            # Check for CAN network interfaces using ip command
            result = subprocess.run(['ip', 'link', 'show', 'type', 'can'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse output for CAN interfaces
                # Format: "2: can0: <NOARP,UP,LOWER_UP> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10"
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if ':' in line and 'can' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            interface_name = parts[1].strip().split()[0]
                            
                            # Get interface state
                            if 'UP' in line:
                                state = 'UP'
                                available = True
                                description = f'SocketCAN interface {interface_name} (Active)'
                            elif 'DOWN' in line:
                                state = 'DOWN'
                                available = True
                                description = f'SocketCAN interface {interface_name} (Down)'
                            else:
                                state = 'UNKNOWN'
                                available = True
                                description = f'SocketCAN interface {interface_name} (Unknown state)'
                            
                            interface = HardwareInterface(
                                interface_type='socketcan',
                                channel=interface_name,
                                name=f'SocketCAN {interface_name}',
                                description=description,
                                available=available
                            )
                            interfaces.append(interface)
                            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # SocketCAN tools not available or command failed
            pass
            
        # Also check /sys/class/net for CAN interfaces
        try:
            net_path = Path('/sys/class/net')
            if net_path.exists():
                for interface_dir in net_path.iterdir():
                    if interface_dir.is_dir():
                        type_file = interface_dir / 'type'
                        if type_file.exists():
                            try:
                                # CAN interfaces have type 280 (ARPHRD_CAN)
                                with open(type_file, 'r') as f:
                                    if f.read().strip() == '280':
                                        interface_name = interface_dir.name
                                        
                                        # Check if we already found this interface
                                        if not any(iface.channel == interface_name for iface in interfaces):
                                            # Check if interface is up
                                            operstate_file = interface_dir / 'operstate'
                                            if operstate_file.exists():
                                                with open(operstate_file, 'r') as f:
                                                    operstate = f.read().strip()
                                                    available = operstate in ['up', 'down', 'unknown']
                                                    description = f'SocketCAN interface {interface_name} (State: {operstate})'
                                            else:
                                                available = True
                                                description = f'SocketCAN interface {interface_name} (Hardware detected)'
                                            
                                            interface = HardwareInterface(
                                                interface_type='socketcan',
                                                channel=interface_name,
                                                name=f'SocketCAN {interface_name}',
                                                description=description,
                                                available=available
                                            )
                                            interfaces.append(interface)
                                            
                            except (IOError, ValueError):
                                continue
                                
        except Exception:
            # Filesystem access failed
            pass
            
        return interfaces
        
    def _discover_windows_interfaces(self) -> List[HardwareInterface]:
        """Discover CAN interfaces on Windows"""
        interfaces = []
        
        # Note: This would require Windows-specific detection
        # For now, we'll add common interface names
        
        return interfaces
        
    def _discover_macos_interfaces(self) -> List[HardwareInterface]:
        """Discover CAN interfaces on macOS"""
        interfaces = []
        
        # Note: macOS typically uses USB-based CAN adapters
        # Detection would require specific vendor tools
        
        return interfaces
        
    def _discover_pcan_interfaces(self) -> List[HardwareInterface]:
        """Discover PEAK PCAN interfaces"""
        interfaces = []
        
        try:
            # Try to import PCAN library
            import can.interfaces.pcan
            
            # Try to import the PCAN API directly for hardware detection
            try:
                from can.interfaces.pcan.pcan import PcanBus
                import can.interfaces.pcan.pcan as pcan_module
                
                # PCAN channel definitions
                pcan_channels = [
                    ('PCAN_USBBUS1', 0x51, 'PEAK USB CAN 1'),
                    ('PCAN_USBBUS2', 0x52, 'PEAK USB CAN 2'),
                    ('PCAN_USBBUS3', 0x53, 'PEAK USB CAN 3'),
                    ('PCAN_USBBUS4', 0x54, 'PEAK USB CAN 4'),
                    ('PCAN_USBBUS5', 0x55, 'PEAK USB CAN 5'),
                    ('PCAN_USBBUS6', 0x56, 'PEAK USB CAN 6'),
                    ('PCAN_USBBUS7', 0x57, 'PEAK USB CAN 7'),
                    ('PCAN_USBBUS8', 0x58, 'PEAK USB CAN 8'),
                    ('PCAN_PCIBUS1', 0x41, 'PEAK PCI CAN 1'),
                    ('PCAN_PCIBUS2', 0x42, 'PEAK PCI CAN 2'),
                    ('PCAN_ISABUS1', 0x21, 'PEAK ISA CAN 1'),
                    ('PCAN_ISABUS2', 0x22, 'PEAK ISA CAN 2'),
                ]
                
                # Try to detect actual PCAN hardware
                for channel_name, channel_id, display_name in pcan_channels:
                    try:
                        # Try to get channel status - this will fail if hardware not present
                        # We'll create a temporary bus instance to test availability
                        test_bus = can.Bus(channel=channel_name, bustype='pcan', bitrate=500000)
                        test_bus.shutdown()
                        
                        # If we get here, the interface exists
                        interface = HardwareInterface(
                            interface_type='pcan',
                            channel=channel_name,
                            name=display_name,
                            description=f'PEAK CAN interface {channel_name} (Hardware detected)',
                            available=True
                        )
                        interfaces.append(interface)
                        
                    except Exception:
                        # Hardware not available for this channel
                        continue
                        
            except ImportError:
                # PCAN API not fully available, fall back to basic detection
                pass
                
        except ImportError:
            # PCAN library not available at all
            pass
            
        return interfaces
        
    def _discover_vector_interfaces(self) -> List[HardwareInterface]:
        """Discover Vector CAN interfaces"""
        interfaces = []
        
        try:
            # Try to import Vector library
            import can.interfaces.vector
            
            # Try to detect actual Vector hardware
            try:
                from can.interfaces.vector.vector import VectorBus
                
                # Vector hardware detection is more complex
                # We'll try to enumerate available channels
                for channel in range(8):  # Check up to 8 channels
                    try:
                        # Try to create a bus instance to test if hardware exists
                        test_bus = can.Bus(channel=channel, bustype='vector', bitrate=500000)
                        test_bus.shutdown()
                        
                        # If successful, hardware exists
                        interface = HardwareInterface(
                            interface_type='vector',
                            channel=str(channel),
                            name=f'Vector CAN {channel + 1}',
                            description=f'Vector CAN interface (Channel {channel}, Hardware detected)',
                            available=True
                        )
                        interfaces.append(interface)
                        
                    except Exception:
                        # Hardware not available for this channel
                        continue
                        
            except ImportError:
                # Vector API not fully available
                pass
                
        except ImportError:
            # Vector library not available at all
            pass
            
        return interfaces
        
    def _discover_kvaser_interfaces(self) -> List[HardwareInterface]:
        """Discover Kvaser CAN interfaces"""
        interfaces = []
        
        try:
            # Try to import Kvaser library
            import can.interfaces.kvaser
            
            # Try to detect actual Kvaser hardware
            try:
                from can.interfaces.kvaser.kvaser import KvaserBus
                
                # Kvaser hardware detection
                for channel in range(8):  # Check up to 8 channels
                    try:
                        # Try to create a bus instance to test if hardware exists
                        test_bus = can.Bus(channel=channel, bustype='kvaser', bitrate=500000)
                        test_bus.shutdown()
                        
                        # If successful, hardware exists
                        interface = HardwareInterface(
                            interface_type='kvaser',
                            channel=str(channel),
                            name=f'Kvaser CAN {channel + 1}',
                            description=f'Kvaser CAN interface (Channel {channel}, Hardware detected)',
                            available=True
                        )
                        interfaces.append(interface)
                        
                    except Exception:
                        # Hardware not available for this channel
                        continue
                        
            except ImportError:
                # Kvaser API not fully available
                pass
                
        except ImportError:
            # Kvaser library not available at all
            pass
            
        return interfaces
        
    def get_interfaces_by_type(self, interface_type: str) -> List[HardwareInterface]:
        """Get interfaces of a specific type"""
        return [iface for iface in self.discovered_interfaces 
                if iface.interface_type == interface_type]
                
    def get_available_interfaces(self) -> List[HardwareInterface]:
        """Get only available interfaces"""
        return [iface for iface in self.discovered_interfaces if iface.available]
        
    def refresh_discovery(self) -> List[HardwareInterface]:
        """Refresh hardware discovery"""
        return self.discover_interfaces()
        
    def test_interface_availability(self, interface: HardwareInterface) -> bool:
        """Test if a specific interface is actually available"""
        try:
            # For virtual interfaces, always return True
            if interface.interface_type == 'virtual':
                return True
                
            # For physical interfaces, attempt a quick connection test
            import can
            
            # Try to create a bus instance with a short timeout
            bus_config = {
                'channel': interface.channel,
                'bustype': interface.interface_type,
                'bitrate': 500000  # Standard test bitrate
            }
            
            # Create bus instance to test hardware availability
            test_bus = can.Bus(**bus_config)
            test_bus.shutdown()
            return True
            
        except Exception as e:
            # Hardware not available or driver not installed
            return False
            
    def discover_interfaces_safe(self) -> List[HardwareInterface]:
        """Safely discover interfaces with timeout protection"""
        interfaces = []
        
        # Always add virtual interfaces first (these are always available)
        interfaces.extend(self._discover_virtual_interfaces())
        
        # Discover physical interfaces with timeout protection
        discovery_methods = [
            ('SocketCAN', self._discover_socketcan_interfaces),
            ('PCAN', self._discover_pcan_interfaces),
            ('Vector', self._discover_vector_interfaces),
            ('Kvaser', self._discover_kvaser_interfaces),
        ]
        
        for method_name, method in discovery_methods:
            try:
                # Run discovery method with timeout protection
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"{method_name} discovery timed out")
                
                # Set timeout (only on Unix systems)
                if hasattr(signal, 'SIGALRM'):
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(5)  # 5 second timeout
                
                discovered = method()
                interfaces.extend(discovered)
                
                # Clear timeout
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                    
            except (TimeoutError, Exception) as e:
                # Discovery method failed or timed out
                print(f"Warning: {method_name} discovery failed: {e}")
                continue
                
        self.discovered_interfaces = interfaces
        return interfaces
            
    def get_interface_capabilities(self, interface: HardwareInterface) -> Set[str]:
        """Get detailed capabilities for an interface"""
        capabilities = set(interface.capabilities)
        
        # Add dynamic capabilities based on testing or detection
        if self.test_interface_availability(interface):
            capabilities.add('tested_available')
        else:
            capabilities.add('test_failed')
            
        return capabilities
        
    def get_recommended_interfaces(self) -> List[HardwareInterface]:
        """Get recommended interfaces for typical use"""
        recommended = []
        
        # Always recommend virtual for testing
        virtual_interfaces = self.get_interfaces_by_type('virtual')
        if virtual_interfaces:
            recommended.append(virtual_interfaces[0])  # First virtual interface
            
        # Recommend first available physical interface of each type
        for interface_type in ['pcan', 'vector', 'kvaser', 'socketcan']:
            interfaces = self.get_interfaces_by_type(interface_type)
            available = [iface for iface in interfaces if iface.available]
            if available:
                recommended.append(available[0])
                
        return recommended
        
    def export_discovery_report(self) -> Dict:
        """Export a detailed discovery report"""
        report = {
            'system': platform.system(),
            'platform': platform.platform(),
            'discovery_time': None,  # Would be set to current time
            'total_interfaces': len(self.discovered_interfaces),
            'available_interfaces': len(self.get_available_interfaces()),
            'interfaces_by_type': {},
            'interfaces': []
        }
        
        # Group by type
        for interface in self.discovered_interfaces:
            if interface.interface_type not in report['interfaces_by_type']:
                report['interfaces_by_type'][interface.interface_type] = 0
            report['interfaces_by_type'][interface.interface_type] += 1
            
        # Add interface details
        for interface in self.discovered_interfaces:
            interface_data = {
                'type': interface.interface_type,
                'channel': interface.channel,
                'name': interface.name,
                'description': interface.description,
                'available': interface.available,
                'capabilities': list(interface.capabilities)
            }
            report['interfaces'].append(interface_data)
            
        return report
