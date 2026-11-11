# Offline comparison of saved GPU power-sense tables — 7 November 2026

## Finding

Four saved NVIDIA VBIOS files contain candidate BIT `P` version 2 power-sense tables that are byte-for-byte identical (435 bytes; SHA-256 `7932eb7771aa2226c1c069d053d3abd7fa0fc7c94abaa36a6f5ce1546c1f5290`). Each candidate has version `0x20`, header length 8, record length 61 and seven records. The BIT `P + 0x28` power-sensor pointer and `P + 0x3c` power-topology pointer match NVIDIA’s [BIT specification](https://http.download.nvidia.com/open-gpu-doc/BIOS-Information-Table/1/BIOS-Information-Table.html); record layout follows the version-2 interpretation in [envytools power.c](https://github.com/envytools/envytools/blob/master/nvbios/power.c). Full record semantics are not established, and this is not a recommendation to modify a ROM.

| File | Parsed BIT `i` VBIOS version | File SHA-256 | Candidate table file offset |
| --- | --- | --- | --- |
| `backup.rom` | `94.06.1b.00.1a` | `853bd342b318c56d796b006fad9d05fbce8a5d06e80bb85d03a108992f219142` | `0x7890e` |
| `248585.rom` | `94.06.1f.00.1d` | `8347a7a6e51ab5764dfcc78f996f68565edfb6fa290e71745e1df08a796b11b0` | `0x8f5de` |
| `257580.rom` | `94.06.3b.00.0b` | `9f0ce22d1164afd66b4cee04a971bf7c360fb36d4573c9e9c55dd225f5831772` | `0x92a6b` |
| `Asus.RTX3060Mobile.6144.210526.rom` | `94.06.17.00.65` | `36ce10bbac9b66e90490212710a5311ce747291930331320b729e0333720c07a` | `0x7868f` |

The current GPU reports VBIOS version `94.06.3b.00.0b`, matching `257580.rom` by version only; this does not establish byte-for-byte identity with the currently running ROM. Nor does the filename `backup.rom` prove its origin or suitability for restoration.

## Dell package version and local utility comparison

[Dell's published firmware package 389GX](https://www.dell.com/support/home/en-uk/drivers/driversdetails?driverid=389gx) lists the G15 5510 and specifies RTX 3060 VBIOS version `94.06.1B.00.1A`, matching the parsed version of `backup.rom`. Dell lists SHA-256 `03e54f7155bd399ff8c986b308f03530a9dffba5d6392b51ca096263a9b1fa4a` for its 17.67 MB self-extracting package. The official download returned access denied in this session, so its contents and package hash were not verified.

The pre-existing local `Downloads/New folder (2)/VBIOS_Flash.exe` is a separate 378,501,632-byte unsigned executable, SHA-256 `b860b035f093f1d18e3a3192301a8b6e5fb52fb5a01199daeaac7473c7b9acd4`; its file version is 0.0.3.1. Read-only byte inspection found an embedded `NVGI`-starting sequence adjacent to the string `94.06.1B.00.1A`. Comparing the 999,424-byte region beginning there with `backup.rom` found 259 byte differences, all at offsets `0x4000`–`0x41b3`; all remaining bytes in that compared range matched. The reason for the differences is unknown. This is evidence of a close relationship, not proof that the unsigned local utility is Dell's package, that the two images are interchangeable, or that the saved backup came from this laptop. The executable was not run, and no firmware was changed. Earlier historical reports of failed tests should not be taken as proof of the exact original firmware provenance.

Following the [Linux kernel's documented version-3 IFR header procedure](https://dri.freedesktop.org/docs/drm/gpu/nova/core/vbios.html#ifr-header), the saved backup reports total data size `0x19c0`. The 32-bit value at that offset is `0x4000`, the flash-status offset in that procedure; the directory is at `0x5000`, has the required `RFRD` signature, and points to the same `0x9200` PCI ROM start found independently by the parser. All 259 observed differences lie immediately at the reported flash-status offset and before the directory and PCI ROM. The PCI ROM and rest of the compared suffix are byte-identical. This locates the discrepancy more precisely but does not decode those status bytes, verify image signatures, or prove that it is safe to restore either image.

## Address translation

All four files are NVGI containers with a legacy PCIR image. In `248585.rom` and `257580.rom`, a second PCIR image of EFI type and declared length `0x16c00` immediately follows the `0xfe00` legacy image. For 32-bit BIT pointers beyond the PC-compatible image, the inspection adds the EFI image length to the file offset. NVIDIA’s [published BIT specification](https://http.download.nvidia.com/open-gpu-doc/BIOS-Information-Table/1/BIOS-Information-Table.html) explicitly describes this adjustment and scanning 512-byte boundaries for a PCIR-validated legacy image. Without it these two pointers lead to bytes incompatible with the expected table header; with it they lead to the same well-formed table as the other two files. The specification confirms the pointer rule, but not the detailed record interpretation or live ROM identity.

## External-device table

Using the legacy DCB `0x41` and EXTDEV `0x40` layout from [envytools dcb.c](https://github.com/envytools/envytools/blob/master/nvbios/dcb.c) and [extdev.c](https://github.com/envytools/envytools/blob/master/nvbios/extdev.c), the table has 32 slots in each file. `backup.rom`, `257580.rom`, and the ASUS image have all slots marked unused (`0xff`); `248585.rom` has one non-unused entry with type `0xe0`, whose meaning is not established here. In particular none has an entry with envytools' known INA219/INA209/INA3221 type values. This does **not** prove those devices or other power sensors are physically absent, because hardware can be described elsewhere and this legacy parser may not capture modern layouts.

## Interpretation and reproduction

The matching table is consistent with the historical observation that switching VBIOS files did not fix this problem, and makes a difference in *this particular table's raw bytes* a weaker explanation for the reported behavior. It does not identify the false measurement's source, prove which entries are used at runtime, or establish whether another table, driver, sensor or controller is responsible. It provides no safe spoof value.

Run `python tools/inspect_vbios_extdev.py <rom> [<rom> ...]` to reproduce the file hashes, table offsets, candidate table hash, and non-unused EXTDEV entries. The script reads files only; it does not inspect or modify a live GPU, flash firmware, or write configuration. The comparison above used the four files in `Downloads/nvflash_5.867`.

## Cross-check against power limits and topology

Using the same documented EFI-gap mapping, the version-`0x30` table at BIT `P + 0x2c` has the following values in entry 2 when decoded with the min/average/peak offsets in envytools' power-budget parser (mW):

| Image | Entry 2 minimum | Entry 2 average | Entry 2 peak |
| --- | ---: | ---: | ---: |
| `backup.rom` | 1,000 | 80,000 | 95,000 |
| `248585.rom` | 1,000 | 115,000 | 130,000 |
| `257580.rom` | 1,000 | 115,000 | 140,000 |
| ASUS image | 1,000 | 115,000 | 130,000 |

The reported GPU limits for the running `94.06.3b.00.0b` configuration on 7 November were 1 W minimum, 115 W default/current, and 140 W maximum. Those match entry 2 of `257580.rom`, whose parsed version matches the live reported version. This corroborates the candidate pointer translation and parser interpretation, but the correlation does not prove which exact table entry the live driver selected, establish full live-ROM identity, or measure actual draw. The observed budget differences also show the files have distinct data despite the matching sense table.

The candidate BIT `P + 0x3c` power-topology table, version `0x20`, is also identical across all four files: 838 bytes with SHA-256 `0865abe274964f93186c92e07dc59a9a641cd4269a323915c9a170943363ce55`. Envytools identifies the table location and record boundaries but does not decode the entries' meaning; the matching bytes therefore do not establish the physical sensor or the runtime controller path. The read-only script now emits both topology hashes and the candidate budget values.

The candidate topology table's record 10 contains little-endian `6100` at byte offset 19 in all four saved images. An instantaneous RM response also returned 6100 in runtime record 10, unchanged between the captured idle and short-load snapshots. This is an unverified numerical correlation; the VBIOS schema and relationship between the index spaces are not known. See [the RM analysis](nvml-rm-fallback-comparison-2026-11-07.md) before drawing conclusions.

## Candidate control policy and measured channel graph

An independent reverse-engineered Ampere VBIOS parser ([VBIOS VIX `tables.py`, commit `3ca26ae74b76ed62a9de8a9a5a33409e514599f8`](https://github.com/Panchovix/nvidia-vbios-vix-editor/blob/3ca26ae74b76ed62a9de8a9a5a33409e514599f8/src/nvidia_vbios/rom/tables.py)) describes the BIT P + 0x3c version-0x20 table as power channels, with class-2 channel bytes 14–15 selecting a range in a trailing relationship table. It interprets signed weights of 4096 and -4096 as +1 and -1. This is third-party analysis, not NVIDIA's published schema, and its matching examples do not independently verify this laptop. The saved `257580.rom` and `backup.rom` both contain that candidate layout; the current live VBIOS version matches `257580.rom`, but its actual bytes remain unverified.

The following relations are decoded from both saved files and match the *independently captured runtime* first-word arithmetic exactly:

- Channel 0 = channel 10 + channel 5: `752673 = 6100 + 746573`.
- Channel 1 = channel 5 - channel 3: `522264 = 746573 - 224309`.
- Channel 11 has the same candidate inputs as channel 1; channel 12 = channel 0 - channel 11, consistent with the captured `230409` when channel 11 equals `522264`.

The budget table's candidate notebook policy row 2 starts with bytes `01 00`, which this parser interprets as a class-1 TGP policy using channel 0; its min/default/max fields are 1000/115000/140000 mW in `257580.rom`, corresponding to the reported live limits. These cross-checks materially strengthen the hypothesis that the false aggregate is associated with the configured board-power policy, and that channels 3 and 5 feed its aggregate. They do not prove the GPU loaded these exact bytes, that the relevant live policy is active or that policy execution uses these runtime records, or locate a host or firmware injection point. The relationship rows do not identify physical sensor ICs. No configuration, firmware, or GPU state was changed.

Reproduce with `python tools/inspect_vbios_extdev.py <rom>`; raw output for both files is [archived](../runs/vbios-channel-relationships-20261108.txt). The helper reports relationship fields only when bounds checks pass, and exposes raw signed weights rather than asserting their units. The relationship table extends beyond the earlier topology hash, which covered only the header and channel entries; equality of that earlier hash alone did not establish equality of relation records.

## NVIDIA nvgpu power-manager interface comparison

NVIDIA-authored nvgpu code mirrored at commit `21d928824dc7ca3dc17603a53b11edc6641ace2d` provides an independent older implementation of power table formats and PMU messaging. Its [`bios.h`](https://github.com/OE4T/linux-nvgpu/blob/21d928824dc7ca3dc17603a53b11edc6641ace2d/drivers/gpu/nvgpu/include/nvgpu/bios.h) declares the version-3x policy header fields in order, including TGP, RTP, MXM and D-notifier indices, and a policy-entry channel index followed by min/rated/max limits. In both saved laptop images these header indices are `ff ff ff 02`: row 2 is explicitly named by the D-notifier field, while the TGP field is `ff`. Row 2's channel byte is 0. The independent VBIOS VIX parser treats this particular notebook header as selecting row 2 for TGP; the NVIDIA header alone names it D-notifier and does not establish that notebook-specific equivalence.

The older code's [`pmgrpmu.c`](https://github.com/OE4T/linux-nvgpu/blob/21d928824dc7ca3dc17603a53b11edc6641ace2d/drivers/gpu/nvgpu/common/pmu/pmgr/pmgrpmu.c) constructs channel/relationship and policy packs and sends them as separate PMU objects. That establishes a concrete architecture in this older Linux source: host power-manager configuration can be sent to GPU firmware. It is not evidence that this Windows driver or GA106 uses identical object layouts, command IDs, firmware, transport or policy semantics. In fact, its topology parser requires 22-byte entries and handles class-1 sensor entries, whereas this laptop image has 26-byte entries and relevant channels 3 and 5 are class 5. The older Linux policy parser only processes its class-5 hardware-threshold records, so it does not establish how this laptop's class-1 row is implemented. No PMU command was sent and this comparison does not authorize or establish a 90 W write.
