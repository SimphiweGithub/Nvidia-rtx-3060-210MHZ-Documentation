"""Prepare profile 4's 800 mV curve without installing or applying it."""
import configparser
import hashlib
import json
import re
import struct
from pathlib import Path

source = Path(r'C:\Program Files (x86)\MSI Afterburner\Profiles\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1&BUS_1&DEV_0&FN_0.cfg')
out = Path(__file__).resolve().parent.parent / 'evidence' / 'runs'
raw = source.read_bytes()
text = raw.decode('ascii')
parser = configparser.ConfigParser(interpolation=None)
parser.read_string(text)
if parser['Profile4'].get('memclkboost') != '300000':
    raise RuntimeError('Profile 4 memory offset is not +300 MHz')
matches = list(re.finditer(r'(?ms)^\[Profile4\][^\r\n]*\r?\n(.*?)(?=^\[|\Z)', text))
if len(matches) != 1:
    raise RuntimeError('Profile 4 section is not unique')
section = matches[0]
body = section.group(1)
curves = list(re.finditer(r'(?m)^VFCurve=([0-9A-Fa-f]+)\r?$', body))
if len(curves) != 1:
    raise RuntimeError('Profile 4 curve missing or ambiguous')
curve = curves[0]
data = bytearray.fromhex(curve.group(1))
if len(data) != 3224 or struct.unpack_from('<III', data) != (0x20000, 128, 0):
    raise RuntimeError('Unexpected curve layout')
before = bytes(data)
points = [struct.unpack_from('<fff', data, 12 + i * 12) for i in range(128)]
anchor = [f + d for v, f, d in points if v == 775.0]
if anchor != [1530.0] or not any(v == 800.0 for v, _, _ in points):
    raise RuntimeError('Expected curve points differ')
for i, (v, base, _) in enumerate(points):
    if v > 775.0:
        target = 1875.0 if v >= 800.0 else 1530.0 + 345.0 * (v - 775.0) / 25.0
        struct.pack_into('<f', data, 12 + i * 12 + 8, target - base)
for i, (v, _, _) in enumerate(points):
    off = 12 + i * 12
    voltage, base, offset = struct.unpack_from('<fff', data, off)
    if data[off:off+8] != before[off:off+8] or (v <= 775 and data[off:off+12] != before[off:off+12]):
        raise RuntimeError('Unexpected change to voltage, base, or low point')
    if voltage >= 800 and abs(base + offset - 1875) > 0.001:
        raise RuntimeError('Plateau verification failed')
if data[12 + 128 * 12:] != before[12 + 128 * 12:]:
    raise RuntimeError('Unexpected curve tail change')
new_body = body[:curve.start(1)] + data.hex().upper() + body[curve.end(1):]
new_text = text[:section.start(1)] + new_body + text[section.end(1):]
candidate = out / 'afterburner-profile4-1875-prepared.cfg'
candidate.write_bytes(new_text.encode('ascii'))
manifest = {'source_sha256': hashlib.sha256(raw).hexdigest(),
            'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
            'memory_offset_mhz': 300, 'anchor_mv': 775, 'anchor_mhz': 1530,
            'plateau_mv': 800, 'plateau_mhz': 1875, 'applied': False}
(out / 'afterburner-profile4-1875-prepared.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest))
