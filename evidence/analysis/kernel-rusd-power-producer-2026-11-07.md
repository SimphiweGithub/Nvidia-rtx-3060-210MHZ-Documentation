# Static link between RM power queries and the shared NVML page — 7 November 2026

## Finding

Offline disassembly of the installed Windows 610.62 `nvlddmkm.sys` (SHA-256 `a5dde035859cfa298f890c832ae3094002b13a24462ace190da8c2c85ae46142`) provides a concrete candidate producer for the shared data page observed in the live NVML process. All RVAs apply only to this binary.

The function beginning at RVA `0x531420` passes `rdi + 0x9a0` and `rdi + 0x988` to a helper at RVA `0x5332b0` (call at `0x53178f`). Those offsets match the instantaneous and average power records in the previously observed page and NVIDIA's published RUSD structure layout. The helper issues control `0x2080a637` with a `0x17718`-byte buffer in one path and `0x2080a613` with a `0x13840`-byte buffer in another. These match the requests traced in the isolated NVML fallback process.

On the successful average-request path, code at `0x533435` reads buffer offset `0x20`, while code at `0x533440` reads offset `0x3c`; these are the positions at which the live trace observed `752673` and `752672/752673`, respectively. Later code writes a timestamp sentinel, copies a 16-byte block to the record passed at `rdi + 0x9a0`, and updates its timestamp. It similarly copies another 16-byte block to the record passed at `rdi + 0x988`. The initialization, update pattern, record offsets, and matching field values are strongly consistent with a producer of the instantaneous and average shared power records, not merely two independent displays accidentally showing the same number.

This is a static relationship corroborated by separately observed user-mode data; no kernel breakpoint has proved that this exact function executed during the captured trace or that the `rdi` argument was the observed page in that execution. Paths depend on flags and device state. The routine also includes an instantaneous-query path that indexes records with a `0x258`-byte stride. The object names, type identifiers, and the precise meaning of the other returned fields remain unverified.

## Implication

The evidence now links a plausible chain: driver RM power-query result → kernel code that populates records at the RUSD power offsets → NVML shared-data reader. This explains why the direct fallback and shared page can agree. It still does **not** demonstrate that this shared page supplies the closed-loop boost controller; changing it could affect reporting only. Nor does the producer reveal the source of `33867` and `22224000` or establish their units. The next controller-path investigation should follow the indirect power-query handlers and firmware/PMU consumers, rather than modifying the shared page.

No kernel code was executed, patched, or hooked for this static analysis. The separate user-mode traces, battery comparison, and their limits are documented in [the RM query notes](nvml-rm-fallback-comparison-2026-11-07.md) and [battery comparison](battery-vs-gpu-power-2026-11-07.md).
