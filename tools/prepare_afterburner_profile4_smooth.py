"""Prepare a corrected profile 4; never install or apply it."""
import configparser
import hashlib
import json
import re
import struct
from pathlib import Path

path = Path(r'C:\Program Files (x86)\MSI Afterburner\Profiles\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1&BUS_1&DEV_0&FN_0.cfg')
out = Path(__file__).resolve().parent.parent / 'evidence' / 'runs'
raw = path.read_bytes()
text = raw.decode('ascii')
c = configparser.ConfigParser(interpolation=None)
c.read_string(text)
if c['Profile4'].get('memclkboost') != '300000':
    raise RuntimeError('Profile 4 memory offset is not +300 MHz')
sections = list(re.finditer(r'(?ms)^\[Profile4\][^\r\n]*\r?\n(.*?)(?=^\[|\Z)', text))
if len(sections) != 1:
    raise RuntimeError('Profile 4 section is not unique')
section = sections[0]
body = section.group(1)
vf = list(re.finditer(r'(?m)^VFCurve=([0-9A-Fa-f]+)\r?$', body))
if len(vf) != 1:
    raise RuntimeError('Curve missing or ambiguous')
data = bytearray.fromhex(vf[0].group(1))
version, count, reserved = struct.unpack_from('<III', data)
if len(data) != 3224 or (version, count, reserved) != (0x20000, 128, 0):
    raise RuntimeError('Unexpected curve layout')
original = bytes(data)
points = [struct.unpack_from('<fff', data, 12+i*12) for i in range(count)]
anchors = [(f + d) for v, f, d in points if v == 800.0]
if len(anchors) != 1 or anchors[0] != 1710.0:
    raise RuntimeError('800 mV anchor differs from expected profile 2')
for i, (v, base, _) in enumerate(points):
    if v > 800:
        target = 1925.0 if v >= 825 else 1710.0 + (1925.0 - 1710.0) * (v - 800.0) / 25.0
        struct.pack_into('<f', data, 12+i*12+8, target - base)
for i, (v, _, _) in enumerate(points):
    off = 12+i*12
    if data[off:off+8] != original[off:off+8] or (v <= 800 and data[off:off+12] != original[off:off+12]):
        raise RuntimeError('Unexpected voltage, base, or low-point change')
if data[12+count*12:] != original[12+count*12:]:
    raise RuntimeError('Unexpected curve tail change')
new_body = body[:vf[0].start(1)] + data.hex().upper() + body[vf[0].end(1):]
new_text = text[:section.start(1)] + new_body + text[section.end(1):]
target = out / 'afterburner-profile4-smooth-prepared.cfg'
target.write_bytes(new_text.encode('ascii'))
manifest = {'source_sha256': hashlib.sha256(raw).hexdigest(),
            'candidate_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'memory_offset_mhz': 300, 'anchor_mv': 800, 'anchor_mhz': 1710,
            'plateau_mv': 825, 'plateau_mhz': 1925, 'applied': False}
(out / 'afterburner-profile4-smooth-prepared.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps(manifest))
