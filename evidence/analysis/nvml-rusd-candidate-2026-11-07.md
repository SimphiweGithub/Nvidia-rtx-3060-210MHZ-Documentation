# Live read-only shared-data candidate — 7 November 2026

## Finding

A fresh Python process initialized the installed NVML, obtained GPU 0, called `nvmlDeviceGetPowerUsage` successfully, and searched only its own committed, readable memory with `VirtualQuery` and `ReadProcessMemory`. One 4 KiB `MEM_PRIVATE`, `PAGE_READONLY` region contained a strong candidate for NVIDIA's RM User Shared Data (RUSD) layout. It was never written to. The process then shut NVML down normally. This is a live observation transcribed from the run, not a saved binary dump.

At offsets relative to the candidate page base:

| Offset | Observed data | Interpretation, if this is the published layout |
| --- | --- | --- |
| `0x8F8` | Changing 64-bit value | Power-limit timestamp |
| `0x900` | `0xFFFFFFFF`, then `115000` | Requested and enforced power limit in mW |
| `0x908` | Changing 64-bit value | GPU temperature timestamp |
| `0x910` | `0x00003510` | 53.0625 °C in NVIDIA's signed 24.8 fixed-point representation |
| `0x988` | Changing 64-bit value | Average-power timestamp |
| `0x990` | `752672` or `752673` | Average GPU power in mW |
| `0x9A0` | Changing 64-bit value | Instantaneous-power timestamp |
| `0x9A8` | `752673` | Instantaneous GPU power in mW |

The average and instantaneous values are 24 bytes apart, consistent with the sizes and ordering of the adjacent `RUSD_AVG_POWER_USAGE` and `RUSD_INST_POWER_USAGE` structures in NVIDIA's [610.57.04 header](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/e4a5faa2567f28c8eabe0ebb6422b6d0abcf37eb/src/common/sdk/nvidia/inc/class/cl00de.h). The nearby limit and temperature positions also match the header's order and their values match independent NVML query outputs at approximately the same time: 115 W and 53 °C. The sampled timestamps and average value changed over three one-second reads without another power query, consistent with a live asynchronously updated monitoring page. The scan found one candidate matching this pair in the examined read-only private 4 KiB regions; this is not a claim about every process or mapping on the machine.

This makes the candidate stronger than a simple numeric coincidence, but the page has not been identified through an allocation stack, mapped-object handle, or matching full structure offsets in the exact Windows 610.62 binary. The copy observed by NVML is a monitoring surface; changing it would not establish a change to the producer or the power-control loop. No memory, driver, policy, or hardware state was modified. The value's upstream source, controller decision and physical cause remain unknown.

Static analysis subsequently located an indirect call in the installed NVML power handler. In a fresh process, read-only inspection resolved the relevant dispatch pointers to a routine that requests records at offsets `0x988` and `0x9A0`, and linked that routine's cached page pointer to a page with the expected data. See [indirect-dispatch analysis](nvml-power-query-indirect-dispatch-2026-11-07.md). The observed pointers and instructions make the relationship strong, but no execution breakpoint has yet proved which branch that specific query took.

## Reproduction boundary

The scan searched committed `MEM_PRIVATE` and `MEM_MAPPED` pages with readable protection, skipping guarded and larger-than-32 MiB regions. It found no exact `752673` value in the 26 examined `MEM_MAPPED` regions (about 5.8 MiB), but did find matching values in private regions. A later focused pass inspected only read-only private 4 KiB regions for matching values separated by 24 bytes. Absence in this bounded scan does not rule out other mappings, encodings, processes or transient data. Do not infer that the `0x08DE0008` output buffer itself contained the power value.

## Working-set query

In another fresh NVML process, `K32QueryWorkingSetEx` on the candidate average-power page returned valid `1`, share count `0`, and shared bit `0` (`flags = 0x400021`). These values were unchanged while a second independent NVML process held its own candidate page. Both processes exited normally. Microsoft's [working-set documentation](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-psapi_working_set_ex_block) defines the shared bit as whether a page can be shared; this observation does not identify kernel mappings, prove how the page is populated, or establish that modifying its backing storage would be isolated or safe. No protection or memory was changed.
