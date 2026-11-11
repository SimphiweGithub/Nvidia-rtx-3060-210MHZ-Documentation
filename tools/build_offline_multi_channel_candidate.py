"""Build the reviewed multi-channel hypothesis offline; never load or flash it."""
import hashlib
import json
import struct
from pathlib import Path

from nvidia_vbios.rom.tables import checksum_tail

root = Path(__file__).resolve().parent.parent
source = root / 'evidence/runs/nvapi-running-vbios-20261109.bin'
destination = root / 'evidence/runs/OFFLINE-ONLY-multi-channel-candidate-20261110.bin'
manifest_path = destination.with_suffix('.json')
if destination.exists() or manifest_path.exists():
    raise FileExistsError('Refusing to overwrite offline artifacts')
original = source.read_bytes()
assert hashlib.sha256(original).hexdigest() == '34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae'
table, image_start, image_end = 563230, 180224, 609792
assert tuple(original[table:table+6]) == (32, 6, 26, 32, 46, 32)
assert sum(original[image_start:image_end]) % 256 == 0
assert checksum_tail(original, image_end, 'ampere') is not None
entry = lambda index: table + 6 + 26*index
relations = table + 6 + 26*32
row1 = original[relations+46:relations+92]
assert row1[:6] == bytes.fromhex('010a00100000')
assert original[relations+15*46:relations+16*46] == bytes(46)
for index in range(32):
    rec = original[entry(index):entry(index)+26]
    if rec[0] == 2 and rec[14] <= rec[15] < 32 and rec[14] <= 15 <= rec[15]:
        raise ValueError('Relationship 15 is already referenced by a class-2 channel')
row15 = bytearray(row1)
struct.pack_into('<i', row15, 2, 1410)
changes = [
    (entry(0)+14, bytes([1,2]), bytes([2,2]), 'channel 0 range'),
    (entry(3), bytes([5]), bytes([2]), 'channel 3 class'),
    (entry(3)+14, bytes([0,1]), bytes([15,15]), 'channel 3 range'),
    (entry(5), bytes([5]), bytes([2]), 'channel 5 class'),
    (entry(5)+14, bytes([0,0]), bytes([1,1]), 'channel 5 range'),
    (relations+15*46, bytes(46), bytes(row15), 'relationship 15'),
]
output = bytearray(original)
for offset, before, after, label in changes:
    if original[offset:offset+len(before)] != before:
        raise ValueError('Unexpected source bytes for '+label)
    output[offset:offset+len(after)] = after
checksum_before = output[image_end-1]
output[image_end-1] = (checksum_before-sum(output[image_start:image_end])) & 255
assert sum(output[image_start:image_end]) % 256 == 0
manifest = {
    'status': 'OFFLINE ONLY; class conversion, policy behavior and safety unverified',
    'source_sha256': hashlib.sha256(original).hexdigest(),
    'output_sha256': hashlib.sha256(output).hexdigest(),
    'changes': [{'offset': off, 'before_hex': old.hex(), 'after_hex': new.hex(), 'field': label}
                for off, old, new, label in changes],
    'checksum_offset': image_end-1, 'checksum_before': checksum_before, 'checksum_after': output[image_end-1],
    'limitations': ['No signature validation', 'No demonstrated PMU acceptance or sustained boost',
                    'No independent board-power protection', 'Current and voltage output unknown',
                    'Relationship 15 is unused only among observed class-2 ranges',
                    'Copied relationship 15 bytes 31..45 form a second record of unknown meaning and contain a channel-5-like reference'],
}
destination.write_bytes(output)
manifest_path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
print(json.dumps(manifest, indent=2))
