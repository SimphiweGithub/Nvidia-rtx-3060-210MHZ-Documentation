"""Prepare, but do not install or apply, a flat Afterburner profile 4."""
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
if parser.has_section('Profile4'):
    raise RuntimeError('Profile 4 already exists; refusing to overwrite it')
if parser['Profile2'].get('memclkboost') != '300000':
    raise RuntimeError('Profile 2 memory offset is not +300 MHz')
matches = list(re.finditer(r'(?ms)^\[Profile2\][^\r\n]*(?:\r?\n)(.*?)(?=^\[|\Z)', text))
if len(matches) != 1:
    raise RuntimeError('Profile 2 section is not unique')
body = matches[0].group(1)
vf = list(re.finditer(r'(?m)^VFCurve=([0-9A-Fa-f]+)\r?$', body))
if len(vf) != 1:
    raise RuntimeError('Profile 2 curve missing or ambiguous')
data = bytearray.fromhex(vf[0].group(1))
if len(data) != 3224:
    raise RuntimeError('Unexpected curve length')
version, count, reserved = struct.unpack_from('<III', data)
if version != 0x20000 or count != 128 or reserved != 0:
    raise RuntimeError('Unexpected curve header')
before = bytes(data)
previous = -1.0
changed = 0
for i in range(count):
    offset = 12 + i * 12
    voltage, base, delta = struct.unpack_from('<fff', data, offset)
    if not (previous < voltage < 1500):
        raise RuntimeError('Unexpected voltage grid')
    previous = voltage
    if voltage >= 825.0:
        struct.pack_into('<f', data, offset + 8, 1925.0 - base)
        changed += 1
if not any(struct.unpack_from('<f', data, 12+i*12)[0] == 825.0 for i in range(count)):
    raise RuntimeError('825 mV point absent')
for i in range(count):
    off = 12 + i * 12
    v, f, delta = struct.unpack_from('<fff', data, off)
    if v >= 825 and abs(f + delta - 1925.0) > 0.001:
        raise RuntimeError('Curve does not flatten at requested frequency')
    if v < 825 and data[off:off+12] != before[off:off+12]:
        raise RuntimeError('Unexpected change below 825 mV')
    if data[off:off+8] != before[off:off+8]:
        raise RuntimeError('Voltage or base frequency changed')
if data[12+count*12:] != before[12+count*12:]:
    raise RuntimeError('Unexpected tail change')
new_body = body[:vf[0].start(1)] + data.hex().upper() + body[vf[0].end(1):]
newline = '\r\n' if '\r\n' in text else '\n'
candidate = raw + (b'' if raw.endswith((b'\n', b'\r')) else newline.encode()) + ('[Profile4]' + newline + new_body).encode('ascii')
target = out / 'afterburner-profile4-prepared.cfg'
manifest = out / 'afterburner-profile4-prepared.json'
target.write_bytes(candidate)
manifest.write_text(json.dumps({'source_sha256': hashlib.sha256(raw).hexdigest(),
    'candidate_sha256': hashlib.sha256(candidate).hexdigest(), 'base': 'Profile2',
    'memory_offset_mhz': 300, 'target_mv': 825, 'target_mhz': 1925,
    'modified_points': changed, 'applied': False, 'profile3_untouched': True}, indent=2)+'\n')
print(manifest.read_text())
