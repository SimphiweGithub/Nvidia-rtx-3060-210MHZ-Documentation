# Live NVML device-handle trace — 7 November 2026

## Scope and provenance

The existing one-query `NvmlPowerOnlyEvidenceProbe.exe` was run under x64dbg on the Dell G15 with driver 610.62. The core offset had been manually removed. This was an observation-only debugger run: breakpoints and memory views in the probe process, with no register edits, injected requests, clock changes or firmware changes. Values below were transcribed from the live debugger and its accessibility view; screenshots from this run were not saved as standalone evidence, so an independently reproducible capture is still desirable. Process-local addresses and handles apply only to this run.

## Results

After the `nvmlDeviceGetPowerUsage` breakpoint, `CreateFileA` stopped with `RCX` resolving to `\\.\NvAdminDevice`. The call stack included `nvmlDeviceGetPowerUsage+0x268`. At the return instruction, `RAX` was `0x374`. After returning to NVIDIA code, the next relevant `DeviceIoControl` stop had the same handle (`RCX = 0x374`), `RDX = 0x08DE0008`, `R8 = 0x000000636717DCE0`, `R9 = 0x6C`, and the same power-query stack. This dynamically links this particular IOCTL to the opened device handle; it does not establish the physical telemetry source or driver policy mechanism.

The output pointer at `[RSP+0x28]` was `0x000000636717DD50`; `[RSP+0x38]` pointed to `0x000000636717DDC0`. At the API return `RAX = 1` and the first four bytes at the bytes-returned pointer were `6C 00 00 00`, consistent with **108 bytes returned**. This fresh result supersedes any assumption that the earlier screenshot's apparent value of one byte applies to all runs.

Actual input bytes at `R8`, before the call, were displayed as:

```text
00 00 00 00 00 00 00 00 60 00 00 00 41 44 56 4E
02 00 01 00 60 00 00 00 2A 2A 56 4E 1B 00 00 05
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 BD 01 D0 C1
10 00 5A A5 40 00 5A A5 00 00 00 00 00 00 00 00
00 00 00 00 50 0C 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 01 00 00 00
```

The output buffer visibly changed from its pre-call scratch contents. Its first 96 bytes after return largely matched the input; bytes at offsets `0x38` through `0x3B` changed from zero to `01 00 00 00`. Other bytes included a process address. These are observations, not decoded vendor fields, and the final NVML milliwatt value has not been located. Do not replay or modify this request on that basis.

The probe was allowed to exit. Debugger DLL-stop preferences changed during setup were restored afterwards. The next question is whether the captured envelope is an administration/transport setup request or directly contains the telemetry response; trace subsequent code and compare read-only calls before considering any modification to power-management behavior.
