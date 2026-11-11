"""Model, but never build or apply, a multi-channel VBIOS hypothesis."""
import hashlib
import json
import struct
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root / 'evidence/runs/nvapi-running-vbios-20261109.bin'
data = source.read_bytes()
assert hashlib.sha256(data).hexdigest() == '34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae'
table = 563230
assert tuple(data[table:table+6]) == (32, 6, 26, 32, 46, 32)
record = lambda index: data[table+6+26*index:table+6+26*(index+1)]
rel = table+6+26*32
assert record(0)[14:16] == bytes([1, 2])
assert record(3)[0] == record(5)[0] == 5
assert data[rel+46:rel+46+6] == bytes.fromhex('010a00100000')
assert data[rel+46*15:rel+46*16] == bytes(46)
users = {}
for index in range(32):
    entry = record(index)
    if entry[0] == 2 and entry[14] <= entry[15] < 32:
        for row in range(entry[14], entry[15]+1):
            users.setdefault(row, []).append(index)
assert 15 not in users
constant = 6100
memory = constant * 1410 / 4096
connector = constant
chip = connector-memory
out = {
    'status': 'ARITHMETIC HYPOTHESIS ONLY; no firmware image was built or staged',
    'source_sha256': hashlib.sha256(data).hexdigest(),
    'hypothetical_edits': [
        {'channel': 0, 'relationship_range': [2, 2], 'reason': 'read channel 5 only'},
        {'channel': 5, 'class': 2, 'relationship_range': [1, 1], 'reason': 'derive from channel 10'},
        {'channel': 3, 'class': 2, 'relationship_range': [15, 15], 'reason': 'derive from scaled channel 10'},
        {'relationship': 15, 'kind': 1, 'source_channel': 10, 'signed_weight': 1410},
    ],
    'predicted_first_words_before_rounding_mw': {'C0': connector, 'C1': chip, 'C3': memory, 'C5': connector,
                                                   'C10': constant, 'C11': chip, 'C12': memory},
    'limitations': [
        'Arithmetic assumes existing relation and unit interpretations; firmware may reject, clamp or interpret edits differently.',
        'Changing a channel class and changing an unused-looking relation are untested; other reference types may use relation 15.',
        'No prediction for current or voltage fields; power/current/voltage consistency and hardware threshold behavior are unknown.',
        'Channel 10 itself is presumed constant from prior observations; 6.1 W is not actual measured power.',
        'Affected board, input and current policies would lose genuine feedback; independent full-board protection is unverified.',
        'NVVDD channels 18 and 19 remain untouched but their calibration, enforcement and coverage are not established.',
    ],
    'policy_rows_consuming_affected_channels': {'C0': [2,5,7,8,10,11,19], 'C5': [6,9], 'C11': [0,3,4,14,15], 'C12': [1]},
}
destination = root / 'evidence/runs/OFFLINE-ONLY-multi-channel-model-20261110.json'
if destination.exists():
    raise FileExistsError(destination)
destination.write_text(json.dumps(out, indent=2)+'\n', encoding='utf-8')
print(json.dumps(out, indent=2))
