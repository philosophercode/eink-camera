#!/usr/bin/env python3
"""
Pure Python driver for IT8951 e-ink displays over USB.
No C compilation needed - uses direct SCSI commands.

Usage:
    from eink import EInkDisplay

    display = EInkDisplay('/dev/sg0')
    display.show_image('photo.jpg')
    display.clear()
    display.close()
"""

import struct
import fcntl
import os
from PIL import Image
import io

# Display modes
MODE_INIT = 0   # Full clear (slow, removes ghosting)
MODE_DU = 1     # Direct update (fast, 1-bit)
MODE_GC16 = 2   # 16-level grayscale (best quality)
MODE_A2 = 4     # Fast 2-level B&W (for video/animation)

# SCSI constants
SG_IO = 0x2285
SG_DXFER_FROM_DEV = -3
SG_DXFER_TO_DEV = -2

# sg_io_hdr structure for Linux SCSI generic interface
# See /usr/include/scsi/sg.h
class SGIOHeader:
    FORMAT = 'iiBBHIPIPIPIIiPBBBBI'  # Total 64 bytes on 64-bit
    SIZE = 88  # Actual size with padding on 64-bit Linux

    def __init__(self):
        self.interface_id = ord('S')
        self.dxfer_direction = 0
        self.cmd_len = 0
        self.mx_sb_len = 32
        self.iovec_count = 0
        self.dxfer_len = 0
        self.dxferp = 0
        self.cmdp = 0
        self.sbp = 0
        self.timeout = 10000
        self.flags = 0
        self.pack_id = 0
        self.usr_ptr = 0
        self.status = 0
        self.masked_status = 0
        self.msg_status = 0
        self.sb_len_wr = 0
        self.host_status = 0
        self.driver_status = 0
        self.resid = 0
        self.duration = 0
        self.info = 0

def _scsi_command(fd, cmd_bytes, data=None, direction=SG_DXFER_FROM_DEV, timeout=10000):
    """Send a SCSI command and optionally transfer data."""

    # Prepare command buffer
    cmd = (ctypes.c_ubyte * len(cmd_bytes))(*cmd_bytes)
    sense = (ctypes.c_ubyte * 32)()

    # Prepare data buffer if needed
    if data is not None:
        if direction == SG_DXFER_TO_DEV:
            data_buf = (ctypes.c_ubyte * len(data))(*data)
        else:
            data_buf = (ctypes.c_ubyte * len(data))()
        data_ptr = ctypes.addressof(data_buf)
        data_len = len(data)
    else:
        data_ptr = 0
        data_len = 0

    # Build sg_io_hdr structure manually (64-bit Linux)
    # This is tricky because of pointer sizes and padding
    hdr = bytearray(88)

    # int interface_id (4 bytes)
    struct.pack_into('i', hdr, 0, ord('S'))
    # int dxfer_direction (4 bytes)
    struct.pack_into('i', hdr, 4, direction)
    # unsigned char cmd_len (1 byte)
    hdr[8] = len(cmd_bytes)
    # unsigned char mx_sb_len (1 byte)
    hdr[9] = 32
    # unsigned short iovec_count (2 bytes)
    struct.pack_into('H', hdr, 10, 0)
    # unsigned int dxfer_len (4 bytes)
    struct.pack_into('I', hdr, 12, data_len)
    # void* dxferp (8 bytes on 64-bit)
    struct.pack_into('Q', hdr, 16, data_ptr)
    # unsigned char* cmdp (8 bytes)
    struct.pack_into('Q', hdr, 24, ctypes.addressof(cmd))
    # unsigned char* sbp (8 bytes)
    struct.pack_into('Q', hdr, 32, ctypes.addressof(sense))
    # unsigned int timeout (4 bytes)
    struct.pack_into('I', hdr, 40, timeout)
    # Rest is output fields, leave as zeros

    # Send command
    fcntl.ioctl(fd, SG_IO, bytes(hdr))

    if direction == SG_DXFER_FROM_DEV and data is not None:
        return bytes(data_buf)
    return None

# Use ctypes for cleaner pointer handling
import ctypes

def scsi_command(fd, cmd_bytes, data_in=None, data_out_len=0, timeout=10000):
    """
    Send SCSI command via SG_IO ioctl.

    Args:
        fd: File descriptor for /dev/sgX
        cmd_bytes: Command descriptor block (CDB)
        data_in: Data to send to device (for write commands)
        data_out_len: Expected response length (for read commands)
        timeout: Timeout in milliseconds

    Returns:
        Response data for read commands, None for write commands
    """

    class sg_io_hdr(ctypes.Structure):
        _fields_ = [
            ('interface_id', ctypes.c_int),
            ('dxfer_direction', ctypes.c_int),
            ('cmd_len', ctypes.c_ubyte),
            ('mx_sb_len', ctypes.c_ubyte),
            ('iovec_count', ctypes.c_ushort),
            ('dxfer_len', ctypes.c_uint),
            ('dxferp', ctypes.c_void_p),
            ('cmdp', ctypes.c_void_p),
            ('sbp', ctypes.c_void_p),
            ('timeout', ctypes.c_uint),
            ('flags', ctypes.c_uint),
            ('pack_id', ctypes.c_int),
            ('usr_ptr', ctypes.c_void_p),
            ('status', ctypes.c_ubyte),
            ('masked_status', ctypes.c_ubyte),
            ('msg_status', ctypes.c_ubyte),
            ('sb_len_wr', ctypes.c_ubyte),
            ('host_status', ctypes.c_ushort),
            ('driver_status', ctypes.c_ushort),
            ('resid', ctypes.c_int),
            ('duration', ctypes.c_uint),
            ('info', ctypes.c_uint),
        ]

    # Prepare buffers
    cmd = (ctypes.c_ubyte * len(cmd_bytes))(*cmd_bytes)
    sense = (ctypes.c_ubyte * 32)()

    if data_in is not None:
        direction = SG_DXFER_TO_DEV
        data = (ctypes.c_ubyte * len(data_in))(*data_in)
        data_len = len(data_in)
    elif data_out_len > 0:
        direction = SG_DXFER_FROM_DEV
        data = (ctypes.c_ubyte * data_out_len)()
        data_len = data_out_len
    else:
        direction = SG_DXFER_FROM_DEV
        data = None
        data_len = 0

    # Build header
    hdr = sg_io_hdr()
    hdr.interface_id = ord('S')
    hdr.dxfer_direction = direction
    hdr.cmd_len = len(cmd_bytes)
    hdr.mx_sb_len = 32
    hdr.dxfer_len = data_len
    hdr.dxferp = ctypes.addressof(data) if data else 0
    hdr.cmdp = ctypes.addressof(cmd)
    hdr.sbp = ctypes.addressof(sense)
    hdr.timeout = timeout

    # Execute
    fcntl.ioctl(fd, SG_IO, hdr)

    if data_out_len > 0:
        return bytes(data)
    return None


class EInkDisplay:
    """IT8951 e-ink display driver over USB."""

    MAX_TRANSFER = 60800  # Max bytes per transfer

    def __init__(self, device='/dev/sg0'):
        """
        Open connection to IT8951 display.

        Args:
            device: SCSI generic device path (usually /dev/sg0)
        """
        self.fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        self._get_device_info()

        # Full init clear on startup: black then white to reset all particles
        black = bytes([0x00] * (self.width * self.height))
        self.display(black, mode=MODE_INIT)
        white = bytes([0xFF] * (self.width * self.height))
        self.display(white, mode=MODE_INIT)

    def _get_device_info(self):
        """Query display info from IT8951."""
        cmd = bytes([
            0xfe, 0x00,
            0x38, 0x39, 0x35, 0x31,  # "8951" signature
            0x80, 0x00,              # Get System Info
            0x01, 0x00, 0x02, 0x00   # Version
        ])

        response = scsi_command(self.fd, cmd, data_out_len=112)

        # Parse device info (big-endian integers)
        self.width = struct.unpack('>I', response[16:20])[0]
        self.height = struct.unpack('>I', response[20:24])[0]
        self.img_addr = struct.unpack('<I', response[28:32])[0]  # Little-endian address

        print(f"IT8951: {self.width}x{self.height}, buffer=0x{self.img_addr:08x}")

    def _load_image_area(self, x, y, w, h, data):
        """Load image data to display buffer."""
        cmd = bytes([0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0xa2, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x00, 0x00, 0x00, 0x00])

        # Build area header (big-endian except address)
        area = struct.pack('<I', self.img_addr)  # address (little-endian)
        area += struct.pack('>i', x)   # x
        area += struct.pack('>i', y)   # y
        area += struct.pack('>i', w)   # width
        area += struct.pack('>i', h)   # height

        # Combine area header + image data
        payload = area + bytes(data)
        scsi_command(self.fd, cmd, data_in=payload)

    def _display_area(self, x, y, w, h, mode):
        """Trigger display refresh."""
        cmd = bytes([0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x94, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x00, 0x00, 0x00, 0x00])

        # Build display area struct (big-endian except address)
        area = struct.pack('<I', self.img_addr)  # address
        area += struct.pack('>i', mode)  # wavemode
        area += struct.pack('>i', x)     # x
        area += struct.pack('>i', y)     # y
        area += struct.pack('>i', w)     # width
        area += struct.pack('>i', h)     # height
        area += struct.pack('>i', 1)     # wait_ready

        scsi_command(self.fd, cmd, data_in=area)

    def display(self, image_data, x=0, y=0, w=None, h=None, mode=MODE_GC16):
        """
        Display 8-bit grayscale image data.

        Args:
            image_data: Raw 8-bit grayscale bytes (1 byte per pixel)
            x, y: Position on display
            w, h: Dimensions (defaults to full display)
            mode: Refresh mode (MODE_GC16, MODE_A2, etc.)
        """
        if w is None:
            w = self.width
        if h is None:
            h = self.height

        # Send in chunks
        lines_per_chunk = self.MAX_TRANSFER // w
        offset = 0
        total = w * h

        while offset < total:
            chunk_lines = min(lines_per_chunk, h - (offset // w))
            chunk_size = chunk_lines * w
            self._load_image_area(x, y + (offset // w), w, chunk_lines,
                                  image_data[offset:offset + chunk_size])
            offset += chunk_size

        self._display_area(x, y, w, h, mode)

    def show_image(self, image, mode=MODE_GC16):
        """
        Display a PIL Image or image file.

        Args:
            image: PIL Image, file path, or bytes
            mode: Refresh mode
        """
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        else:
            img = image

        # Convert and resize
        img = img.convert('L')  # Grayscale
        img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)

        self.display(img.tobytes(), mode=mode)

    def show_image_fast(self, image):
        """Display image using fast A2 mode (for video/animation)."""
        self.show_image(image, mode=MODE_A2)

    def clear(self, mode=MODE_INIT):
        """Clear display to white."""
        white = bytes([0xFF] * (self.width * self.height))
        self.display(white, mode=mode)

    def reset(self):
        """Reset connection to display (fixes freezes)."""
        device = f"/proc/self/fd/{self.fd}"
        # Get the actual device path
        try:
            device = os.readlink(device)
        except:
            device = '/dev/sg0'

        # Close and reopen
        os.close(self.fd)
        self.fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        self._get_device_info()
        # Do a full clear to reset the controller
        self.clear(MODE_INIT)
        print("Display reset!")

    def close(self):
        """Close connection."""
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Simple test
if __name__ == '__main__':
    import sys

    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/sg0'

    with EInkDisplay(device) as display:
        print(f"Display: {display.width}x{display.height}")

        if len(sys.argv) > 2:
            print(f"Showing: {sys.argv[2]}")
            display.show_image(sys.argv[2])
        else:
            print("Clearing display...")
            display.clear()
