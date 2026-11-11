"""Build a 6.1 W topology hypothesis offline; never load or flash the result.

The feedback and controller semantics are not established. The fixed reading
would not enforce a measured board-power limit.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'evidence/runs/nvapi-running-vbios-20261109.bin'
OUTPUT = ROOT / 'evidence/runs/OFFLINE-ONLY-6100mW-candidate-20261109.bin'
EXPECTED = '34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae'


def main():
    from nvidia_vbios.rom.tables import checksum_tail
    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError('Unexpected source VBIOS')
    table, image_start, image_end = 563230, 180224, 609792
    if tuple(source[table:table + 6]) != (32, 6, 26, 32, 46, 32):
        raise ValueError('Unexpected power topology layout')
    if sum(source[image_start:image_end]) & 255 or checksum_tail(source, image_end, 'ampere') is None:
        raise ValueError('Unexpected source checksum or tail')
    record = lambda i: source[table + 6 + 26*i:table + 6 + 26*(i+1)]
    base = table + 6 + 26*32
    relation = lambda i: source[base + 46*i:base + 46*(i+1)]
    if record(0)[14:16] != bytes([1, 2]) or record(12)[14:16] != bytes([13, 14]):
        raise ValueError('Unexpected channel ranges')
    if relation(1)[:6] != bytes.fromhex('010a00100000'):
        raise ValueError('Channel 10 relation differs from the expected unit weight')
    for i in range(32):
        r = record(i)
        if r[0] == 2 and r[14] <= r[15] < 32:
            for j in range(r[14], r[15] + 1):
                if j in (1, 13, 14) and (i, j) not in ((0, 1), (12, 13), (12, 14)):
                    raise ValueError('Relationship row has another consumer')
    changes = [
        (table + 6 + 15, b'\x02', b'\x01', 'channel 0 last relationship'),
        (base + 46*13 + 1, b'\x00', b'\x03', 'relationship 13 source'),
        (base + 46*14 + 1, b'\x0b', b'\x0a', 'relationship 14 source'),
        (base + 46*14 + 2, struct.pack('<i', -4096), struct.pack('<i', 4096), 'relationship 14 weight'),
    ]
    out = bytearray(source)
    for offset, before, after, label in changes:
        if source[offset:offset+len(before)] != before:
            raise ValueError(f'Unexpected bytes for {label}')
        out[offset:offset+len(before)] = after
    original_checksum = out[image_end-1]
    out[image_end-1] = (original_checksum - sum(out[image_start:image_end])) & 255
    if sum(out[image_start:image_end]) & 255:
        raise ValueError('Checksum repair failed')
    manifest = {'status': 'OFFLINE ONLY; no runtime or safety validation', 'source_sha256': EXPECTED,
                'output_sha256': hashlib.sha256(out).hexdigest(),
                'changes': [{'offset': i, 'before_hex': a.hex(), 'after_hex': b.hex(), 'field': label}
                            for i, a, b, label in changes],
                'checksum_offset': image_end-1, 'checksum_before': original_checksum,
                'checksum_after': out[image_end-1], 'signature_verified': False,
                'board_power_feedback_preserved': False}
    if OUTPUT.exists() or OUTPUT.with_suffix('.json').exists():
        raise FileExistsError('Refusing to overwrite candidate or manifest')
    OUTPUT.write_bytes(out)
    OUTPUT.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
