"""Validate the procedural GLES triangle directly from its GPU attachment.

The current carrier's fixed clear is BGRA 0f0504ff; this deliberately does not
claim that glClearColor is implemented. Every triangle pixel is compared with
an independent barycentric oracle, and the complete coverage mask is checked.
"""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('attachment', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
raw = args.attachment.read_bytes()
width = height = 512
assert len(raw) == width * height * 4
linear = bytearray(len(raw))
coverage_errors = color_errors = background_errors = covered = max_error = 0
for y in range(height):
    for x in range(width):
        morton = sum((((x >> bit) & 1) << (2 * bit)) |
                     (((y >> bit) & 1) << (2 * bit + 1)) for bit in range(6))
        source = (((y // 64) * 8 + x // 64) * 4096 + morton) * 4
        bgra = raw[source:source + 4]
        rgba = bytes((bgra[2], bgra[1], bgra[0], bgra[3]))
        linear[(y * width + x) * 4:(y * width + x + 1) * 4] = rgba
        screen_x = (x + .5) / 256 - 1
        screen_y = 1 - (y + .5) / 256
        r = (screen_y + .72) / 1.54
        g = (1 - r + screen_x / .82) / 2
        b = 1 - r - g
        inside = min(r, g, b) > 0
        actual_inside = bgra != bytes.fromhex('0f0504ff')
        coverage_errors += inside != actual_inside
        if inside:
            covered += 1
            expected = [round(max(0, min(1, v)) * 255) for v in (r, g, b)] + [255]
            error = max(abs(a - b) for a, b in zip(rgba, expected))
            max_error = max(max_error, error)
            color_errors += error > 1
        else:
            background_errors += actual_inside

report = dict(width=width, height=height, covered=covered,
              coverage_errors=coverage_errors, color_errors=color_errors,
              background_errors=background_errors, max_channel_error=max_error,
              attachment_sha256=hashlib.sha256(raw).hexdigest())
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')

def chunk(kind, data):
    return (struct.pack('>I', len(data)) + kind + data +
            struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))

png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(b''.join(
    b'\0' + linear[y * width * 4:(y + 1) * width * 4] for y in range(height))))
png += chunk(b'IEND', b'')
args.output.with_suffix('.png').write_bytes(png)
print(json.dumps(report))
assert coverage_errors == color_errors == background_errors == 0
