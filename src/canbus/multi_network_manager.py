"""
Multi-Network CAN Manager
Manages multiple CAN networks and hardware interfaces simultaneously
"""

import json
import time
from typing import Dict, List, Optional, Set
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .network import CANNetwork, NetworkConfiguration, HardwareInterface, ConnectionState
from .hardware_discovery import HardwareDiscovery


class MultiNetworkManager(QObject):
    """Manages multiple CAN networks and their connections"""
    
    # Signals
    network_added = pyqtSignal(str)  # network_id
    network_removed = pyqtSignal(str)  # network_id
    network_state_changed = pyqtSignal(str, object)  # network_id, ConnectionState
    message_received = pyqtSignal(str, object)  # network_id, CANMessage
    message_transmitted = pyqtSignal(str, object)  # network_id, CANMessage
    error_occurred = pyqtSignal(str, str)  # network_id, error_message
    hardware_discovered = pyqtSignal(list)  # List[HardwareInterface]
    
    def __init__(self):
        super().__init__()
        
        # Network management
        self.networks: Dict[str, CANNetwork] = {}
        self.hardware_interfaces: Dict[str, HardwareInterface] = {}
        self.hardware_discovery = HardwareDiscovery()
        
        # Global statistics
        self.global_stats = {
            'total_networks': 0,
            'active_connections': 0,
            'total_messages': 0,
            'total_errors': 0,
            'start_time': time.time()
        }
        
        # Configuration management
        self.config_file = Path("network_profiles.json")
        self.auto_save = True
        
        # Discovery and monitoring
        self.discovery_timer = QTimer()
        self.discovery_timer.timeout.connect(self.discover_hardware)
        self.discovery_timer.start(10000)  # Discover every 10 seconds
        
        # Initial hardware discovery
        self.discover_hardware()
        
        # Auto-reconnect networks after hardware discovery
        QTimer.singleShot(2000, self.auto_reconnect_networks)  # Wait 2s for hardware discovery
        
    def discover_hardware(self):
        """Discover available hardware interfaces"""
        try:
            interfaces = self.hardware_discovery.discover_interfaces()
            
            # Update hardware interfaces dict
            self.hardware_interfaces.clear()
            for interface in interfaces:
                key = f"{interface.interface_type}:{interface.channel}"
                self.hardware_interfaces[key] = interface
                
            self.hardware_discovered.emit(interfaces)
            
        except Exception as e:
            self.error_occurred.emit("system", f"Hardware discovery failed: {str(e)}")
            
    def get_available_hardware(self) -> List[HardwareInterface]:
        """Get list of available hardware interfaces"""
        return list(self.hardware_interfaces.values())
        
    def get_available_hardware_for_type(self, interface_type: str) -> List[HardwareInterface]:
        """Get hardware interfaces of a specific type"""
        return [hw for hw in self.hardware_interfaces.values() 
                if hw.interface_type == interface_type and hw.available]
                
    def create_network(self, config: NetworkConfiguration) -> str:
        """Create a new CAN network"""
        # Auto-assign bus number if not set or conflicts exist
        if config.bus_number <= 0 or self._is_bus_number_used(config.bus_number):
            config.bus_number = self._get_next_available_bus_number()
            
        network = CANNetwork(config)
        
        # Connect network signals
        network.connection_state_changed.connect(self._on_network_state_changed)
        network.message_received.connect(self._on_message_received)
        network.message_transmitted.connect(self._on_message_transmitted)
        network.error_occurred.connect(self._on_error_occurred)
        
        # Add to networks
        self.networks[config.network_id] = network
        self.global_stats['total_networks'] += 1
        
        # Auto-save configuration
        if self.auto_save:
            self.save_configuration()
            
        self.network_added.emit(config.network_id)
        return config.network_id
        
    def remove_network(self, network_id: str) -> bool:
        """Remove a CAN network"""
        if network_id not in self.networks:
            return False
            
        network = self.networks[network_id]
        
        # Disconnect if connected
        if network.is_connected():
            network.disconnect()
            
        # Remove from networks
        del self.networks[network_id]
        self.global_stats['total_networks'] -= 1
        
        # Auto-save configuration
        if self.auto_save:
            self.save_configuration()
            
        self.network_removed.emit(network_id)
        return True
        
    def get_network(self, network_id: str) -> Optional[CANNetwork]:
        """Get a network by ID"""
        return self.networks.get(network_id)
        
    def get_all_networks(self) -> Dict[str, CANNetwork]:
        """Get all networks"""
        return self.networks.copy()
        
    def connect_network(self, network_id: str, hardware_key: str) -> bool:
        """Connect a network to a hardware interface"""
        if network_id not in self.networks:
            self.error_occurred.emit(network_id, "Network not found")
            return False
            
        if hardware_key not in self.hardware_interfaces:
            self.error_occurred.emit(network_id, "Hardware interface not found")
            return False
            
        network = self.networks[network_id]
        hardware = self.hardware_interfaces[hardware_key]
        
        # Check if hardware is already in use
        if self._is_hardware_in_use(hardware_key, network_id):
            self.error_occurred.emit(network_id, "Hardware interface already in use")
            return False
            
        try:
            network.set_hardware(hardware)
            success = network.connect()
            
            if success:
                hardware.available = False  # Mark as in use
                self.global_stats['active_connections'] += 1
                
                # Save hardware interface for auto-reconnect
                network.config.last_hardware_interface = hardware_key
                self.save_configuration()
                
            return success
            
        except Exception as e:
            self.error_occurred.emit(network_id, f"Connection failed: {str(e)}")
            return False
            
    def disconnect_network(self, network_id: str) -> bool:
        """Disconnect a network"""
        if network_id not in self.networks:
            return False
            
        network = self.networks[network_id]
        
        if network.is_connected():
            # Free up hardware interface
            if network.hardware:
                hardware_key = f"{network.hardware.interface_type}:{network.hardware.channel}"
                if hardware_key in self.hardware_interfaces:
                    self.hardware_interfaces[hardware_key].available = True
                    
            network.disconnect()
            self.global_stats['active_connections'] -= 1
            
        return True
        
    def auto_reconnect_networks(self):
        """Automatically reconnect networks to their last used hardware interfaces"""
        print("🔄 Attempting auto-reconnect to saved hardware interfaces...")
        
        reconnected_count = 0
        
        for network_id, network in self.networks.items():
            # Skip if already connected
            if network.is_connected():
                continue
                
            # Check if network has a saved hardware interface
            if network.config.last_hardware_interface:
                hardware_key = network.config.last_hardware_interface
                
                # Check if the hardware interface is available
                if hardware_key in self.hardware_interfaces:
                    hardware = self.hardware_interfaces[hardware_key]
                    
                    # Only try to reconnect if hardware is available
                    if hardware.available and not self._is_hardware_in_use(hardware_key, network_id):
                        print(f"🔌 Auto-reconnecting {network.config.name} to {hardware_key}")
                        
                        success = self.connect_network(network_id, hardware_key)
                        if success:
                            reconnected_count += 1
                            print(f"✅ Auto-reconnected {network.config.name} to {hardware_key}")
                        else:
                            print(f"❌ Failed to auto-reconnect {network.config.name} to {hardware_key}")
                    else:
                        print(f"⚠️ Hardware {hardware_key} not available for {network.config.name}")
                else:
                    print(f"⚠️ Saved hardware {hardware_key} not found for {network.config.name}")
                    
        if reconnected_count > 0:
            print(f"🎉 Auto-reconnected {reconnected_count} network(s) to saved hardware interfaces")
        else:
            print("ℹ️ No networks auto-reconnected (none had saved interfaces or hardware unavailable)")
        
    def disconnect_all_networks(self):
        """Disconnect all networks"""
        for network_id in list(self.networks.keys()):
            self.disconnect_network(network_id)
            
    def send_message(self, network_id: str, msg_id: int, data: bytes, is_extended: bool = False) -> bool:
        """Send a message on a specific network"""
        if network_id not in self.networks:
            return False
            
        return self.networks[network_id].send_message(msg_id, data, is_extended)
        
    def broadcast_message(self, msg_id: int, data: bytes, is_extended: bool = False, 
                         exclude_networks: Set[str] = None) -> int:
        """Broadcast a message to all connected networks"""
        if exclude_networks is None:
            exclude_networks = set()
            
        sent_count = 0
        for network_id, network in self.networks.items():
            if network_id not in exclude_networks and network.is_connected():
                if network.send_message(msg_id, data, is_extended):
                    sent_count += 1
                    
        return sent_count
        
    def add_periodic_message(self, network_id: str, msg_id: int, data: bytes, 
                           period_ms: int, is_extended: bool = False) -> bool:
        """Add a periodic message to a network"""
        if network_id not in self.networks:
            return False
            
        self.networks[network_id].add_periodic_message(msg_id, data, period_ms, is_extended)
        return True
        
    def remove_periodic_message(self, network_id: str, msg_id: int) -> bool:
        """Remove a periodic message from a network"""
        if network_id not in self.networks:
            return False
            
        self.networks[network_id].remove_periodic_message(msg_id)
        return True
        
    def get_network_statistics(self, network_id: str) -> Dict:
        """Get statistics for a specific network"""
        if network_id not in self.networks:
            return {}
            
        return self.networks[network_id].get_statistics()
        
    def get_global_statistics(self) -> Dict:
        """Get global statistics across all networks"""
        stats = self.global_stats.copy()
        
        # Calculate aggregated statistics
        total_messages = 0
        total_errors = 0
        
        for network in self.networks.values():
            network_stats = network.get_statistics()
            total_messages += network_stats.get('message_count', 0)
            total_errors += network_stats.get('error_count', 0)
            
        stats['total_messages'] = total_messages
        stats['total_errors'] = total_errors
        stats['uptime'] = time.time() - stats['start_time']
        
        return stats
        
    def save_configuration(self, filename: Optional[str] = None) -> bool:
        """Save network configurations to file"""
        try:
            if filename:
                config_file = Path(filename)
            else:
                config_file = self.config_file
                
            configurations = {}
            for network_id, network in self.networks.items():
                configurations[network_id] = network.config.to_dict()
                
            with open(config_file, 'w') as f:
                json.dump(configurations, f, indent=2)
                
            return True
            
        except Exception as e:
            self.error_occurred.emit("system", f"Failed to save configuration: {str(e)}")
            return False
            
    def load_configuration(self, filename: Optional[str] = None) -> bool:
        """Load network configurations from file"""
        try:
            if filename:
                config_file = Path(filename)
            else:
                config_file = self.config_file
                
            if not config_file.exists():
                return True  # No configuration file is not an error
                
            with open(config_file, 'r') as f:
                configurations = json.load(f)
                
            # Clear existing networks (disconnect first)
            self.disconnect_all_networks()
            self.networks.clear()
            
            # Load configurations
            for network_id, config_data in configurations.items():
                config = NetworkConfiguration.from_dict(config_data)
                self.create_network(config)
                
            return True
            
        except Exception as e:
            self.error_occurred.emit("system", f"Failed to load configuration: {str(e)}")
            return False
            
    def create_default_networks(self):
        """Create some default network configurations"""
        # Virtual CAN network for testing
        virtual_config = NetworkConfiguration()
        virtual_config.name = "Bus 1 - Virtual CAN"
        virtual_config.description = "Virtual CAN network for testing and simulation"
        virtual_config.bus_number = 1
        virtual_config.bitrate = 500000
        self.create_network(virtual_config)
        
        # High-speed CAN network
        hs_can_config = NetworkConfiguration()
        hs_can_config.name = "Bus 2 - High-Speed CAN"
        hs_can_config.description = "High-speed CAN network (500 kbps)"
        hs_can_config.bus_number = 2
        hs_can_config.bitrate = 500000
        self.create_network(hs_can_config)
        
        # Low-speed CAN network
        ls_can_config = NetworkConfiguration()
        ls_can_config.name = "Bus 3 - Low-Speed CAN"
        ls_can_config.description = "Low-speed CAN network (125 kbps)"
        ls_can_config.bus_number = 3
        ls_can_config.bitrate = 125000
        self.create_network(ls_can_config)
        
    def _is_hardware_in_use(self, hardware_key: str, exclude_network: str = None) -> bool:
        """Check if a hardware interface is already in use"""
        for network_id, network in self.networks.items():
            if network_id == exclude_network:
                continue
                
            if (network.hardware and network.is_connected() and
                f"{network.hardware.interface_type}:{network.hardware.channel}" == hardware_key):
                return True
                
        return False
        
    def _is_bus_number_used(self, bus_number: int) -> bool:
        """Check if a bus number is already in use"""
        for network in self.networks.values():
            if network.config.bus_number == bus_number:
                return True
        return False
        
    def _get_next_available_bus_number(self) -> int:
        """Get the next available bus number"""
        used_numbers = {network.config.bus_number for network in self.networks.values()}
        bus_number = 1
        while bus_number in used_numbers:
            bus_number += 1
        return bus_number
        
    def get_network_by_bus_number(self, bus_number: int) -> Optional['CANNetwork']:
        """Get network by bus number"""
        for network in self.networks.values():
            if network.config.bus_number == bus_number:
                return network
        return None
        
    def get_all_bus_numbers(self) -> List[int]:
        """Get all active bus numbers"""
        return sorted([network.config.bus_number for network in self.networks.values()])
        
    def _on_network_state_changed(self, network_id: str, state: ConnectionState):
        """Handle network state changes"""
        self.network_state_changed.emit(network_id, state)
        
    def _on_message_received(self, network_id: str, message):
        """Handle received messages from networks"""
        self.message_received.emit(network_id, message)
        
    def _on_message_transmitted(self, network_id: str, message):
        """Handle transmitted messages from networks"""
        self.message_transmitted.emit(network_id, message)
        
    def _on_error_occurred(self, network_id: str, error: str):
        """Handle errors from networks"""
        self.error_occurred.emit(network_id, error)
        
    def shutdown(self):
        """Shutdown the multi-network manager"""
        # Stop discovery
        self.discovery_timer.stop()
        
        # Disconnect all networks
        self.disconnect_all_networks()
        
        # Save configuration
        if self.auto_save:
            self.save_configuration()
