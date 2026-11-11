# Offline comparison of archived 461.92 and installed 610.62 power queries

Date: 2026-11-07. This is static analysis, not a driver installation or live experiment.

## Archived package and applicability

The archive is `Downloads/Drive Upload/_Software (skip)/461.92-desktop-win10-64bit-international-whql (1).exe`. Despite its desktop filename, its `Display.Driver/nvdmi.inf` includes `PCI\\VEN_10DE&DEV_2520&SUBSYS_0A641028` under `[NVIDIA_Devices.NTamd64.10.0...17134]`, and names that entry `NVIDIA GeForce RTX 3060 Laptop GPU`. The live GPU reports device ID `0x252010DE`, subsystem ID `0x0A641028`. An INF match makes the package relevant to this machine; it does not establish that this was the exact package used in the earlier successful 461.92 test or that it should be installed.

Extracted reference components (SHA-256):

- `nvml.dll`: `20fc3bd1ad23027bfa17b4039ebf1e07926ca460d2b632a3957831b205b6b988`
- `nvlddmkm.sys`, expanded from `nvlddmkm.sy_`: `d9d1da82ee2948bf9f44169d1e70495e3b3decd4735780d217d848d347ea451b`

## Reporting path differences

The old `nvmlDeviceGetPowerUsage` export is at RVA `0x271c0`. Its disassembly includes a call to RVA `0x7d710` at `0x2736d`. That routine contains paths calling RVA `0x78cb0` and/or `0x7a040`. The former contains a call to an internal dispatcher with command value `0x20802637` and may fall back to the latter, which calls the same dispatcher with `0x20802618`. These values are observed call arguments; their precise command semantics and whether the device used these paths at runtime are not established. The old functions reference an NVIDIA debug source pathname ending `dmal/rm/rm_power.c`, supporting their role in NVML power reporting.

The installed 610.62 `nvml.dll` (SHA-256 `7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06`) instead has an indirect dispatch in its power query; a resolved target includes reads of shared telemetry fields as described in `nvml-power-query-indirect-dispatch-2026-11-07.md`. This is a difference in the user-mode reporting implementation. It does not demonstrate that either reporting path controls boost, explain why the older driver reportedly boosted, or identify a safe spoofing point.

## Next question

Trace the producer and consumers of the underlying controller telemetry, and compare old and current control logic where feasible. Independently verify actual power and preserve a recovery path before any experiment that changes the input to a power controller. Display-only changes cannot prove a boost fix.

## Old kernel dispatch-table lead

In the extracted 461.92 `nvlddmkm.sys`, `.rdata` contains adjacent records for the two observed NVML command values. The `0x20802637` record at RVA `0x880860` contains the same `0x5dd0` length passed by the user-mode query and a pointer to RVA `0x64e038`. The `0x20802618` record at RVA `0x8805a0` similarly contains length `0x1410` and a pointer to RVA `0x4a0320`. The first target performs conditional checks and calls another function indirectly. This is a promising route for tracing the old reporting implementation across the user/kernel boundary, but its table layout and targets have not been verified by execution and neither is established as part of boost control.

A simple byte search did not find these two literal command values in the current 610.62 kernel file. This observation alone does not mean equivalent operations are absent: implementation, encoding, compilation and data layout may differ.

## Old query selects a record supplied by the driver

Further offline disassembly of the archived 461.92 NVML getter at RVA `0x78cb0` shows that after a successful `0x20802637` request it reads a 32-bit index from response offset `0x08`, multiplies it by a 24-byte record stride, checks fields at record offsets `0x10`, `0x18`, and `0x20`, and copies the word at `0x20` to the caller if those checks pass. If the checks fail, it instead calls the getter at `0x7a040`. Offsets here are relative to the response buffer, with the indexed first record starting at `0x10`.

This establishes a concrete old **reporting-path** selection mechanism: the selected index comes from the driver response, not a hardcoded index in this success branch of NVML. Neither the selected index on the historical machine nor the actual path taken on 461.92 was recorded. It does not show that the 6.1 W value was the fixed topology record, that this reporting path controls boost, or how the modern controller can be corrected. No old driver was installed or executed.

By comparison, on installed 610.62 the statically identified average-power getter uses the caller's selector to choose one of several direct fields from the `0x2080a637` response; for selector 0 it reads response offset `0x3c`. In the separately captured live selector-0 query this field contained 752673 mW. Thus the two observed reporting implementations select values differently, but they use different response layouts and commands: their index and selector values cannot be equated without additional evidence. Neither comparison exposes the controller's input or identifies a safe replacement.
