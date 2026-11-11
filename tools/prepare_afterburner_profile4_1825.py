"""Prepare a 1825 MHz / 800 mV profile 4 without applying or installing it."""
import configparser
import hashlib
import json
import re
import struct
from pathlib import Path

src = Path(r'C:\Program Files (x86)\MSI Afterburner\Profiles\VEN_10DE&DEV_2520&SUBSYS_0A641028&REV_A1&BUS_1&DEV_0&FN_0.cfg')
out = Path(__file__).resolve().parent.parent / 'evidence' / 'runs'
raw = src.read_bytes()
text = raw.decode('ascii')
c = configparser.ConfigParser(interpolation=None)
c.read_string(text)
if c['Profile4'].get('memclkboost') != '300000':
    raise RuntimeError('Profile 4 does not have the expected +300 MHz memory offset')
sections = list(re.finditer(r'(?ms)^\[Profile4\][^\r\n]*\r?\n(.*?)(?=^\[|\Z)', text))
if len(sections) != 1:
    raise RuntimeError('Profile 4 section missing or ambiguous')
section = sections[0]
body = section.group(1)
curves = list(re.finditer(r'(?m)^VFCurve=([0-9A-Fa-f]+)\r?$', body))
if len(curves) != 1:
    raise RuntimeError('Curve missing or ambiguous')
curve = curves[0]
data = bytearray.fromhex(curve.group(1))
if len(data) != 3224 or struct.unpack_from('<III', data) != (0x20000, 128, 0):
    raise RuntimeError('Unexpected curve layout')
before = bytes(data)
points = [struct.unpack_from('<fff', data, 12+i*12) for i in range(128)]
if [f+d for v,f,d in points if v == 700] != [990.0] or [f+d for v,f,d in points if v == 800] != [1875.0]:
    raise RuntimeError('Expected curve points differ')
for i, (v, base, _) in enumerate(points):
    if v > 700:
        target = 1825.0 if v >= 800 else 990.0 + 835.0 * (v - 700.0) / 100.0
        struct.pack_into('<f', data, 12+i*12+8, target-base)
for i, (v, _, _) in enumerate(points):
    off = 12+i*12
    _, base, delta = struct.unpack_from('<fff', data, off)
    if data[off:off+8] != before[off:off+8] or (v <= 700 and data[off:off+12] != before[off:off+12]):
        raise RuntimeError('Unexpected voltage, base, or low-point change')
    if v >= 800 and abs(base+delta-1825) > .001:
        raise RuntimeError('Plateau verification failed')
if data[12+128*12:] != before[12+128*12:]:
    raise RuntimeError('Unexpected curve tail change')
body = body[:curve.start(1)] + data.hex().upper() + body[curve.end(1):]
candidate = out / 'afterburner-profile4-1825-prepared.cfg'
candidate.write_bytes((text[:section.start(1)] + body + text[section.end(1):]).encode('ascii'))
manifest = {'source_sha256':hashlib.sha256(raw).hexdigest(),
            'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
            'memory_offset_mhz':300,'start_mv':700,'start_mhz':990,
            'plateau_mv':800,'plateau_mhz':1825,'applied':False}
(out/'afterburner-profile4-1825-prepared.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))
