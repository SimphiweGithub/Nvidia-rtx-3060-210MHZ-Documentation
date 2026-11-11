"""Read legacy DCB EXTDEV records from NVIDIA ROM files, without hardware access.

Only handles version 0x30/0x40/0x41 DCB and 0x30/0x40 EXTDEV, using the
layout in envytools nvbios/{bios,dcb,extdev}.c. A ROM may omit devices from
this table or describe hardware different from the active board.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect_power_sense(data, base):
    """Inspect BIT P v2 + 0x28 with NVIDIA's documented EFI-gap mapping."""
    bit = data.find(b"\xff\xb8BIT\x00\x00", base, min(len(data), base + 0xfe00))
    if bit < 0 or bit + 12 > len(data):
        return {"status": "BIT signature not found"}
    version = u16(data, bit + 6)
    hlen, rlen, count = data[bit + 8:bit + 11]
    if version != 0x100 or hlen < 12 or rlen < 6 or bit + hlen + rlen * count > len(data) or sum(data[bit:bit + hlen]) & 0xff:
        return {"status": "unsupported BIT directory"}
    power = []
    for idx in range(count):
        typ, ver, size, ptr = struct.unpack_from("<BBHH", data, bit + hlen + idx * rlen)
        if typ == ord("P") and ver == 2 and size >= 0x2c:
            power.append((size, ptr))
    if len(power) != 1:
        return {"status": "missing or ambiguous BIT P version 2"}
    size, ptr = power[0]
    if base + ptr + size > len(data):
        return {"status": "BIT P data outside file"}
    relative = struct.unpack_from("<I", data, base + ptr + 0x28)[0]
    if not relative:
        return {"status": "no power-sense pointer"}
    pcir = base + u16(data, base + 0x18)
    first_size = u16(data, pcir + 0x10) * 512
    gap = 0
    next_image = base + first_size
    # NVIDIA's BIT specification adjusts pointers beyond the PC-compatible
    # image by the length of an immediately following EFI image.
    if data[next_image:next_image + 2] == b"\x55\xaa":
        next_pcir = next_image + u16(data, next_image + 0x18)
        if next_pcir + 0x16 > len(data) or data[next_pcir:next_pcir + 4] != b"PCIR" or data[next_pcir + 0x14] != 3:
            return {"status": "unsupported intervening image"}
        gap = u16(data, next_pcir + 0x10) * 512
        if not gap or next_image + gap > len(data):
            return {"status": "invalid EFI image length"}
    start = base + relative + (gap if relative > first_size else 0)
    if start + 4 > len(data):
        return {"status": "power-sense pointer outside file"}
    sv, sh, sr, sc = data[start:start + 4]
    end = start + sh + sr * sc
    if sv != 0x20 or sh < 4 or sr < 5 or end > len(data):
        return {"status": "unsupported power-sense table", "candidate_offset": start}
    result = {"status": "parsed with EFI-gap mapping", "bit_offset": bit,
            "logical_offset": relative, "efi_gap": gap, "file_offset": start,
            "version": sv, "header_size": sh, "record_size": sr, "entry_count": sc,
            "raw_sha256": hashlib.sha256(data[start:end]).hexdigest()}
    for name, offset, versions in (("budget", 0x2c, (0x30,)), ("topology", 0x3c, (0x10, 0x20))):
        if size < offset + 4:
            continue
        pointer = struct.unpack_from("<I", data, base + ptr + offset)[0]
        if not pointer:
            continue
        pos = base + pointer + (gap if pointer > first_size else 0)
        if pos + 4 > len(data):
            continue
        ver, header, record, count = data[pos:pos + 4]
        table_end = pos + header + record * count
        if ver not in versions or header < 4 or record < 4 or table_end > len(data):
            continue
        table = {"file_offset": pos, "version": ver, "entry_count": count,
                 "raw_sha256": hashlib.sha256(data[pos:table_end]).hexdigest()}
        if name == "budget" and record >= 14 and count > 2:
            values = struct.unpack_from("<III", data, pos + header + 2 * record + 2)
            table["entry_2_candidate_mw"] = {"minimum": values[0], "average": values[1], "peak": values[2]}
            table["entry_2_type_and_channel_bytes"] = list(data[pos + header + 2 * record:pos + header + 2 * record + 2])
            if header >= 14:
                table["candidate_header_policy_indices"] = {
                    "tgp": data[pos + 10], "rtp": data[pos + 11],
                    "mxm": data[pos + 12], "dnotifier": data[pos + 13]}
        if name == "topology" and record >= 23 and count > 10:
            entry = data[pos + header + 10 * record:pos + header + 11 * record]
            # Raw bytes only: semantics and relationship to runtime indices are unknown.
            table["entry_10_raw_hex"] = entry.hex()
            table["entry_10_offset_19_u32"] = struct.unpack_from("<I", entry, 19)[0]
        # Ampere relationship layout independently inferred by the VBIOS VIX
        # project. Report raw fields, not presumed physical meaning.
        if name == "topology" and ver == 0x20 and header >= 6 and record >= 16:
            relation_size, relation_count = data[pos + 4:pos + 6]
            relation_end = table_end + relation_size * relation_count
            if relation_size >= 6 and relation_end <= len(data):
                sums = []
                for idx in range(count):
                    entry = data[pos + header + idx * record:pos + header + (idx + 1) * record]
                    first, last = entry[14:16]
                    if entry[0] != 2 or first > last or last >= relation_count:
                        continue
                    relations = []
                    for ridx in range(first, last + 1):
                        start_rel = table_end + ridx * relation_size
                        rel = data[start_rel:start_rel + relation_size]
                        relations.append({"index": ridx, "kind": rel[0], "channel": rel[1],
                                          "weight_raw_signed": struct.unpack_from("<i", rel, 2)[0]})
                    sums.append({"channel": idx, "rail_byte": entry[1], "relationships": relations})
                table["candidate_sum_relationships"] = sums
        result[name] = table
    return result


def u16(data, pos):
    if pos < 0 or pos + 2 > len(data):
        raise ValueError(f"out-of-bounds 16-bit read at {pos:#x}")
    return struct.unpack_from("<H", data, pos)[0]


def inspect(path):
    data = path.read_bytes()
    candidates = []
    for base in range(0, len(data) - 0x38, 0x200):
        if data[base:base + 2] != b"\x55\xaa":
            continue
        pcir = base + u16(data, base + 0x18)
        if data[pcir:pcir + 4] != b"PCIR":
            continue
        dcb = base + u16(data, base + 0x36)
        if dcb + 23 > len(data):
            continue
        if data[dcb] not in (0x30, 0x40, 0x41) or data[dcb + 6:dcb + 10] != b"\xcb\xbd\xdc\x4e":
            continue
        candidates.append((base, dcb))
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one supported DCB image, found {len(candidates)}")
    base, dcb = candidates[0]
    if data[dcb + 1] < 20:
        raise ValueError("DCB header does not include external-device pointer")
    relative_ext = u16(data, dcb + 18)
    result = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(),
              "legacy_image_offset": base, "dcb_offset": dcb,
              "dcb_version": data[dcb], "extdev_relative_offset": relative_ext}
    if not relative_ext:
        result["extdev"] = None
        return result
    ext = base + relative_ext
    if ext + 4 > len(data):
        raise ValueError("external-device table header outside file")
    version, hlen, count, rlen = data[ext:ext + 4]
    if version not in (0x30, 0x40) or hlen < 4 or rlen < 4 or ext + hlen + count * rlen > len(data):
        raise ValueError("unsupported or truncated external-device table")
    entries = []
    for i in range(count):
        rec = data[ext + hlen + i * rlen: ext + hlen + (i + 1) * rlen]
        if rec[0] != 0xff:
            entries.append({"index": i, "type": rec[0], "address_byte": rec[1],
                            "bus_bit": (rec[2] >> 4) & 1, "raw_hex": rec.hex()})
    result["power_sense"] = inspect_power_sense(data, base)
    result["extdev"] = {"file_offset": ext, "version": version, "entry_count": count,
                        "record_size": rlen, "non_unused_entries": entries}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.rom:
        try:
            print(json.dumps(inspect(path), indent=2))
        except (OSError, ValueError) as exc:
            parser.exit(1, f"{path}: {exc}\n")


if __name__ == "__main__":
    main()
