"""Build an experimental, offline-only VBIOS topology candidate.

This does not load, flash, or establish safety of the output. It deliberately
requires the exact previously captured source image and a reviewed checksum tail.
The topology interpretation is a hypothesis; fixed power feedback removes the
affected policy's ability to measure real board power.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "evidence/runs/nvapi-running-vbios-20261109.bin"
OUTPUT = ROOT / "evidence/runs/OFFLINE-ONLY-90w-candidate-20261109.bin"
EXPECTED = "34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae"


def main():
    from nvidia_vbios.rom.tables import checksum_tail

    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError("Source image does not match the examined readback")
    result = bytearray(source)
    table, image_start, image_end = 563230, 180224, 609792
    if tuple(source[table:table + 6]) != (32, 6, 26, 32, 46, 32):
        raise ValueError("Unexpected topology layout")
    if sum(source[image_start:image_end]) & 255:
        raise ValueError("Source data image checksum is invalid")
    if checksum_tail(source, image_end, "ampere") is None:
        raise ValueError("Unrecognized checksum tail")
    changes = [
        (table + 6 + 15, bytes([2]), bytes([1]), "channel 0 last relation"),
    ]
    relation = table + 6 + 26 * 32
    changes.extend([
        (relation + 46 + 2, struct.pack('<i', 4096), struct.pack('<i', 60433), "relation 1 weight"),
        (relation + 46 * 13 + 1, bytes([0]), bytes([3]), "relation 13 source"),
        (relation + 46 * 14 + 1, bytes([11]), bytes([10]), "relation 14 source"),
        (relation + 46 * 14 + 2, struct.pack('<i', -4096), struct.pack('<i', 4096), "relation 14 weight"),
    ])
    for offset, before, after, label in changes:
        if source[offset:offset + len(before)] != before:
            raise ValueError(f"Unexpected original bytes for {label}")
        result[offset:offset + len(before)] = after
    old = result[image_end - 1]
    result[image_end - 1] = (old - sum(result[image_start:image_end])) & 255
    if sum(result[image_start:image_end]) & 255:
        raise ValueError("Checksum repair failed")
    manifest = {
        "status": "OFFLINE ONLY: not validated for loading, not a power limit",
        "source_sha256": EXPECTED,
        "output_sha256": hashlib.sha256(result).hexdigest(),
        "changes": [{"offset": offset, "before_hex": before.hex(), "after_hex": after.hex(), "field": label}
                    for offset, before, after, label in changes],
        "checksum_offset": image_end - 1,
        "checksum_before": old,
        "checksum_after": result[image_end - 1],
        "signature_verified": False,
        "independent_board_power_protection_verified": False,
    }
    if OUTPUT.exists() or OUTPUT.with_suffix('.json').exists():
        raise FileExistsError("Refusing to overwrite an existing candidate or manifest")
    OUTPUT.write_bytes(result)
    OUTPUT.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
