"""Read and compare the live VBIOS image; never stage or change an override.

Requires the previously inspected Vix loader source on PYTHONPATH. NVAPI's
readback identifies the driver image, not whether power protection works.
"""
import hashlib
import json
from pathlib import Path

from nvidia_vbios.windows_loader.nvapi import read_vbios_image

candidate = (Path(__file__).resolve().parent.parent / 'evidence' / 'runs' /
             'OFFLINE-ONLY-current-slope-relocated-20261110.bin').read_bytes()
expected = '8bcebb313011f95cf879751bf11685e58495ce02c2a7d3f946cd60b5c4754153'
if hashlib.sha256(candidate).hexdigest() != expected:
    raise RuntimeError('Candidate file hash mismatch')
image = read_vbios_image('01:00.0')
print(json.dumps({'pci': '01:00.0', 'bytes': len(image),
                  'sha256': hashlib.sha256(image).hexdigest(),
                  'matches_candidate_byte_for_byte': image == candidate,
                  'power_protection_verified': False}))
