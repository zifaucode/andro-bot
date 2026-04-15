"""
screen_checker.py — Screen validation utilities. (BOT-ANDRO)
Import 'device' sebagai pengganti 'emulator'.
"""

import logging
import struct
import zlib
import math
from pathlib import Path

import device

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string ke RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def color_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance antara dua warna RGB."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _read_png_pixel(png_bytes: bytes, x: int, y: int) -> tuple[int, int, int]:
    """
    Parse PNG secara manual tanpa library pihak ketiga.
    Hanya mendukung PNG truecolor (8-bit, color type 2 dan 6).
    """
    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Bukan file PNG yang valid")

    pos = 8
    width = height = 0
    bit_depth = 0
    color_type = 0
    idat_chunks = []

    while pos < len(png_bytes):
        length = struct.unpack('>I', png_bytes[pos:pos+4])[0]
        chunk_type = png_bytes[pos+4:pos+8]
        chunk_data = png_bytes[pos+8:pos+8+length]
        pos += 12 + length

        if chunk_type == b'IHDR':
            width = struct.unpack('>I', chunk_data[0:4])[0]
            height = struct.unpack('>I', chunk_data[4:8])[0]
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break

    if width == 0 or height == 0:
        raise ValueError("PNG IHDR tidak ditemukan")

    if x >= width or y >= height or x < 0 or y < 0:
        raise ValueError(f"Koordinat ({x},{y}) diluar batas gambar ({width}x{height})")

    if color_type == 2:      # RGB
        bpp = 3
    elif color_type == 6:    # RGBA
        bpp = 4
    elif color_type == 0:    # Grayscale
        bpp = 1
    elif color_type == 4:    # Grayscale + Alpha
        bpp = 2
    else:
        raise ValueError(f"Color type {color_type} tidak didukung")

    raw = zlib.decompress(b''.join(idat_chunks))
    row_bytes = width * bpp
    stride = 1 + row_bytes

    prev_row = bytearray(row_bytes)
    current_row = None

    for row_idx in range(y + 1):
        row_start = row_idx * stride
        filter_byte = raw[row_start]
        current_row = bytearray(raw[row_start + 1: row_start + 1 + row_bytes])

        if filter_byte == 0:
            pass
        elif filter_byte == 1:
            for i in range(bpp, row_bytes):
                current_row[i] = (current_row[i] + current_row[i - bpp]) & 0xFF
        elif filter_byte == 2:
            for i in range(row_bytes):
                current_row[i] = (current_row[i] + prev_row[i]) & 0xFF
        elif filter_byte == 3:
            for i in range(row_bytes):
                left = current_row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                current_row[i] = (current_row[i] + (left + up) // 2) & 0xFF
        elif filter_byte == 4:
            for i in range(row_bytes):
                left = current_row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                up_left = prev_row[i - bpp] if i >= bpp else 0
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                if pa <= pb and pa <= pc:
                    pr = left
                elif pb <= pc:
                    pr = up
                else:
                    pr = up_left
                current_row[i] = (current_row[i] + pr) & 0xFF

        prev_row = current_row

    pixel_offset = x * bpp

    if color_type in (2, 6):
        r = current_row[pixel_offset]
        g = current_row[pixel_offset + 1]
        b = current_row[pixel_offset + 2]
        return (r, g, b)
    elif color_type in (0, 4):
        v = current_row[pixel_offset]
        return (v, v, v)

    raise ValueError(f"Gagal membaca pixel di ({x},{y})")


def check_pixel_color(
    x: int,
    y: int,
    expected_hex: str,
    tolerance: int = 50,
    transaction_id: str = "",
) -> tuple[bool, str]:
    """
    Ambil screenshot, cek warna pixel di (x, y).

    Returns:
        (match: bool, detail: str)
    """
    try:
        img_bytes = device.get_screenshot(save_path=None)
        if img_bytes is None:
            return False, "Gagal mengambil screenshot untuk pengecekan"

        actual_rgb = _read_png_pixel(img_bytes, x, y)
        expected_rgb = hex_to_rgb(expected_hex)
        dist = color_distance(actual_rgb, expected_rgb)

        actual_hex = "#{:02X}{:02X}{:02X}".format(*actual_rgb)
        detail = f"Pixel ({x},{y}): actual={actual_hex}, expected={expected_hex}, distance={dist:.1f}, tolerance={tolerance}"
        logger.info(f"[{transaction_id}] {detail}")

        return (dist <= tolerance), detail

    except Exception as exc:
        return False, f"Error saat check_screen: {exc}"


def check_pixel_not_color(
    x: int,
    y: int,
    unexpected_hex: str,
    tolerance: int = 50,
    transaction_id: str = "",
) -> tuple[bool, str]:
    """
    Kebalikan dari check_pixel_color.
    Return True jika pixel TIDAK SAMA dengan warna yang diberikan.
    """
    match, detail = check_pixel_color(x, y, unexpected_hex, tolerance, transaction_id)
    return (not match), detail
