"""
Hardware ID module for unique device identification.
Used for author authentication on the game distribution server.
"""

import hashlib
import platform
import subprocess
import uuid
import os
from pathlib import Path


def _get_mac_address() -> str:
    """Get MAC address using uuid.getnode()."""
    mac = uuid.getnode()
    return ':'.join(f'{(mac >> i) & 0xff:02x}' for i in range(0, 48, 8))


def _get_windows_uuid() -> str:
    """Get Windows motherboard UUID via WMIC."""
    try:
        result = subprocess.check_output(
            'wmic csproduct get uuid',
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore')
        lines = result.strip().split('\n')
        if len(lines) >= 2:
            return lines[1].strip()
    except Exception:
        pass
    return ""


def _get_macos_uuid() -> str:
    """Get macOS IOPlatformUUID via ioreg."""
    try:
        result = subprocess.check_output(
            ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore')
        for line in result.split('\n'):
            if 'IOPlatformUUID' in line:
                # Extract UUID from line like: "IOPlatformUUID" = "XXXXXXXX-XXXX-..."
                parts = line.split('=')
                if len(parts) >= 2:
                    return parts[1].strip().strip('"')
    except Exception:
        pass
    return ""


def _get_linux_machine_id() -> str:
    """Get Linux machine-id from /etc/machine-id or /var/lib/dbus/machine-id."""
    for path in ['/etc/machine-id', '/var/lib/dbus/machine-id']:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


def _get_platform_uuid() -> str:
    """Get platform-specific UUID."""
    system = platform.system()
    if system == 'Windows':
        return _get_windows_uuid()
    elif system == 'Darwin':
        return _get_macos_uuid()
    elif system == 'Linux':
        return _get_linux_machine_id()
    return ""


def _get_hwid_cache_path() -> Path:
    """Get path to cached HWID file."""
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home()
    return base / '.mpy_hwid'


def _generate_hwid() -> str:
    """Generate hardware ID from multiple sources."""
    data = []
    
    # MAC address (always available)
    data.append(_get_mac_address())
    
    # Platform-specific UUID
    platform_uuid = _get_platform_uuid()
    if platform_uuid:
        data.append(platform_uuid)
    
    # Fallback info
    data.append(platform.node())      # Hostname
    data.append(platform.machine())   # Architecture
    data.append(platform.processor()) # Processor info
    
    # Create stable hash
    combined = '|'.join(data)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def get_hardware_id() -> str:
    """
    Get unique hardware ID for this device.
    
    The ID is generated from multiple hardware sources and cached
    to ensure stability even if some hardware changes.
    
    Returns:
        32-character hexadecimal string unique to this device.
    """
    cache_path = _get_hwid_cache_path()
    
    # Try to read cached HWID
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached = f.read().strip()
                if len(cached) == 32 and all(c in '0123456789abcdef' for c in cached):
                    return cached
        except Exception:
            pass
    
    # Generate new HWID
    hwid = _generate_hwid()
    
    # Cache it for stability
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            f.write(hwid)
    except Exception:
        pass  # Caching failed, but HWID is still valid
    
    return hwid


def get_short_hwid() -> str:
    """Get shortened (8-char) hardware ID for display purposes."""
    return get_hardware_id()[:8]


if __name__ == '__main__':
    print(f"Hardware ID: {get_hardware_id()}")
    print(f"Short HWID: {get_short_hwid()}")
