"""
IT8951 e-ink display driver over USB (SCSI generic interface).

Communicates with the IT8951 controller using vendor SCSI commands (0xfe prefix)
sent via Linux SG_IO ioctl. Image data is sent in chunks (max 60800 bytes per
transfer). The protocol uses big-endian for coordinates but little-endian for
the image buffer address.

Requires: Linux with SCSI generic support, root/sudo for device access.

Usage:
    from dreamcam.display.usb import USBDisplay

    with USBDisplay('/dev/sg0') as display:
        display.show_image('photo.jpg')
"""

import ctypes
import fcntl
import io
import os
import struct

from PIL import Image

from dreamcam.display import MODE_GC16, MODE_INIT

# SCSI constants
SG_IO = 0x2285
SG_DXFER_FROM_DEV = -3
SG_DXFER_TO_DEV = -2


def _scsi_command(fd, cmd_bytes, data_in=None, data_out_len=0, timeout=10000):
    """Send a SCSI command via SG_IO ioctl."""

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

    fcntl.ioctl(fd, SG_IO, hdr)

    if data_out_len > 0:
        return bytes(data)
    return None


class USBDisplay:
    """IT8951 e-ink display over USB/SCSI."""

    MAX_TRANSFER = 60800  # Max bytes per SCSI transfer

    def __init__(self, device='/dev/sg0'):
        self.fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        self._device = device
        self._get_device_info()
        self.clear(MODE_INIT)

    def _get_device_info(self):
        """Query display dimensions and buffer address from IT8951."""
        cmd = bytes([
            0xfe, 0x00,
            0x38, 0x39, 0x35, 0x31,  # "8951" signature
            0x80, 0x00,              # Get System Info
            0x01, 0x00, 0x02, 0x00   # Version
        ])
        response = _scsi_command(self.fd, cmd, data_out_len=112)
        self.width = struct.unpack('>I', response[16:20])[0]
        self.height = struct.unpack('>I', response[20:24])[0]
        self._img_addr = struct.unpack('<I', response[28:32])[0]
        print(f"IT8951: {self.width}x{self.height}, buffer=0x{self._img_addr:08x}")

    def _load_image_area(self, x, y, w, h, data):
        """Load image data to display buffer."""
        cmd = bytes([0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0xa2, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x00, 0x00, 0x00, 0x00])
        area = struct.pack('<I', self._img_addr)
        area += struct.pack('>i', x)
        area += struct.pack('>i', y)
        area += struct.pack('>i', w)
        area += struct.pack('>i', h)
        _scsi_command(self.fd, cmd, data_in=area + bytes(data))

    def _display_area(self, x, y, w, h, mode):
        """Trigger display refresh."""
        cmd = bytes([0xfe, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x94, 0x00, 0x00, 0x00, 0x00, 0x00,
                     0x00, 0x00, 0x00, 0x00])
        area = struct.pack('<I', self._img_addr)
        area += struct.pack('>i', mode)
        area += struct.pack('>i', x)
        area += struct.pack('>i', y)
        area += struct.pack('>i', w)
        area += struct.pack('>i', h)
        area += struct.pack('>i', 1)  # wait_ready
        _scsi_command(self.fd, cmd, data_in=area)

    def display(self, image_data, x=0, y=0, w=None, h=None, mode=MODE_GC16):
        """Display raw 8-bit grayscale bytes, sent in chunks."""
        if w is None:
            w = self.width
        if h is None:
            h = self.height

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
        """Display a PIL Image, file path, or bytes."""
        if isinstance(image, str):
            img = Image.open(image)
        elif isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
        else:
            img = image

        img = img.convert('L').resize((self.width, self.height),
                                      Image.Resampling.LANCZOS)
        self.display(img.tobytes(), mode=mode)

    def clear(self, mode=MODE_INIT):
        """Clear display to white."""
        self.display(bytes([0xFF] * (self.width * self.height)), mode=mode)

    def reset(self):
        """Reset connection (fixes freezes)."""
        try:
            device = os.readlink(f"/proc/self/fd/{self.fd}")
        except OSError:
            device = self._device
        os.close(self.fd)
        self.fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        self._get_device_info()
        self.clear(MODE_INIT)
        print("Display reset!")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
