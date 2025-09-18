"""
CAN Message Data Structures
"""

from dataclasses import dataclass


@dataclass
class CANMessage:
    """CAN Message data structure"""
    timestamp: float
    arbitration_id: int
    data: bytes
    is_extended_id: bool
    is_remote_frame: bool
    is_error_frame: bool
    channel: str
    direction: str  # 'rx' or 'tx'
