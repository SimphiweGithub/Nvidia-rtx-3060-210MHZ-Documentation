# NVML shared-page and RM fallback comparison — 7 November 2026

## Result

On driver 610.62, a hash-guarded fresh process called the public `nvmlDeviceGetPowerUsage`, then directly called the installed NVML binary's own internal RM-query fallback using the ABI observed at its normal call site. The first run returned 752,673 mW from both; an independent second run returned 752,672 mW from the public API and 752,673 mW from the fallback, both with status 0. The 1 mW difference is within the small variation already seen in average telemetry. NVML was shut down after each run.

This is an intervention on the **query path in the test process only**: the internal function was called as a getter, with a local output buffer. No pointer, memory page, driver setting, power limit, clock or firmware was modified. Both paths are driver-reported telemetry, not independent physical power measurements. The result is strong evidence that this fallback also produces the implausible reading and that the issue is not confined to the one user-mode shared-page value. It does not prove that the GPU power controller consumes either query's output or identify the upstream fault.

## Static basis and limitations

For DriverStore `nvml.dll` SHA-256 `7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06`, the successful `nvmlDeviceGetPowerUsage` dispatch points to `0x101880`. Its fallback call at RVA `0x101d36` targets `0x10db90` with the original context, GPU device pointer, selector 0, output pointer, and flags 0. This target contains source-file/debug references to `common_power.c` and `cDeviceGetPowerUsageRmApi`. It contains paths invoking functions at `0x10c250` and `0x10c670`, whose embedded names are `cDeviceGetAveragePowerUsage` and `cDeviceGetInstantaneousPowerUsage`; static code includes RM control values `0x2080a637` and `0x2080a613`, respectively. The snapshot did not breakpoint the internal branch taken, so it cannot assert which specific lower getter ran in this experiment. Private ABI semantics are inferred from the actual call site, and NVIDIA does not publish this as an application API.

The reproduction tool [nvml_rm_query_compare.py](../../tools/nvml_rm_query_compare.py) verifies the exact DLL hash and dispatch pointer before invoking the internal getter, and refuses unknown versions. It performs two read-only NVML power queries and does not spoof or alter the controller. It was run twice successfully. The corresponding public-to-shared-page path is analyzed in [nvml-power-query-indirect-dispatch-2026-11-07.md](nvml-power-query-indirect-dispatch-2026-11-07.md).

## Alternate-selector attempt and correction

A later isolated process attempted the same internal fallback with selector `0` followed by selector `1`. Selector 0 returned status 0 and 752,673 mW; selector 1 raised a Windows access violation in that test process, and the process terminated. Selector 2 was not attempted. A subsequent public `nvidia-smi` query still succeeded and showed 210 MHz, 752.67 W and the software power cap active. The test supplied no alternate-channel value and does not establish that a physical fault or any driver state was changed.

The direct fallback does not reproduce the preceding wrapper's device-capability checks for nonzero selectors. The earlier successful selector-0 comparison must not be generalized to other selectors or used as a template for calling private functions with guessed values. The checked-in reproduction tool remains restricted to selector 0; do not call selector 1 or 2 directly. Public `nvidia-smi -q -d POWER` reports GPU memory and module power as unavailable on this configuration.

## Kernel dispatch records

The installed `nvlddmkm.sys` contains a `.rdata` record matching command `0x2080a637` at RVA `0xe738a0`, with data size `0x17718` and target pointer to RVA `0x4f06d0`. A separate matching record for `0x2080a613` is at RVA `0xe73620`, size `0x13840`, with target RVA `0x4e4d50`. These correspond to the current NVML lower-getter command values and request sizes visible in the user-mode code. The targets traverse internal objects and invoke indirect function pointers; their actual runtime use, final implementation and relationship to boost control remain unproven. This maps a plausible user/kernel boundary without supplying a safe write or an independently measured rail value.

## Supported NVML field query after the exception

A fresh process used NVIDIA's public `nvmlDeviceGetFieldValues` API with documented average-power field 185 and instantaneous-power field 186. For GPU scope 0, both returned status 0, unsigned-int type and 752,673 mW. For module scope 1, both returned per-field status 3 (`NVML_ERROR_NOT_SUPPORTED`); no output value is valid for those fields. The overall batch returned 0. This confirms the supported API handles that scope cleanly and supplies no module reading on this machine. It says nothing about individual physical rails or the controller's source. Definitions and the requirement to check per-field results are in NVIDIA's [field enums](https://docs.nvidia.com/deploy/archive/R550/nvml-api/group__nvmlFieldValueEnums.html) and [field-value structure](https://docs.nvidia.com/deploy/nvml-api/api/structnvmlFieldValue__t.html).

## Runtime confirmation of the RM control and returned field

A fresh, hash-checked Python probe initialized NVML and called the existing selector-0 fallback. A Frida 17.26.1 interceptor attached **only to that disposable probe process**, at DriverStore `nvml.dll` RVA `0x8bcf0`. It filtered calls for control value `0x2080a637` with data length `0x17718` and observed the actual return. The interceptor necessarily inserted an instrumentation hook into that process; it did not modify the request or returned data, alter the driver or firmware, or invoke another control. The target and tracer exited normally.

The matching request returned status 0. Its output buffer contained `1` at offset `0x0c` and `752673` at offset `0x3c`. The fallback returned status 0 and `752673` mW to the probe. This confirms the specific `0x2080a637` path ran in this experiment and supplies the same field that the static selector-0 code at RVA `0x10c3e0` copies to its output. Other inspected offsets were zero, but their meaning and validity are unknown and they should not be treated as rail readings. This traces the reported value across the user-mode RM-call boundary; it does not expose a physical measurement, prove the corresponding kernel table handler executed, or prove the boost controller consumes this output.

### Follow-up: observed WDDM escape transport

On 8 November, a new hash-guarded Frida trace instrumented only a disposable child process running the same selector-0 getter. For the `0x2080a637` call, the indirect target at the traced user-mode wrapper resolved to DriverStore `nvml.dll` RVA `0x8ae00`; static disassembly shows a jump to `0x160fa0`. During the same call on the same thread, the next transport target resolved to `win32u.dll` export `NtGdiDdDDIEscape`. The intercepted escape descriptor reported type `0` (`D3DKMT_ESCAPE_DRIVERPRIVATE`), total private-buffer size `96092` (`0x1775c`), and an NVIDIA private header containing command `0x2080a637` and payload length `96024` (`0x17718`). The system call returned status 0 and the getter returned the erroneous value. Microsoft describes the type-0 escape as targeted at the display miniport in its [D3DKMT_ESCAPE documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/d3dkmthk/ns-d3dkmthk-_d3dkmt_escape).

This confirms the tested query passes through the Windows graphics escape transport rather than establishing that a previously observed `DeviceIoControl` is its transport. It narrows the kernel entry investigation to the WDDM escape route, but does not identify the final NVIDIA handler, establish whether its output feeds boost, or expose a 90 W setter. The trace attached only to its disposable child, installed user-mode instrumentation, and did not alter arguments, responses, kernel, GPU settings or firmware. Reproduce with `PYTHONPATH` pointing at the installed Frida Python package and `python tools/trace_nvml_control_target.py`; output is preserved in [the run log](../runs/nvml-control-transport-20261108.txt).

The instrumented process was launched solely for this observation; no existing application was attached. Afterward, `nvidia-smi` still reported driver 610.62, 210 MHz, 752.67 W and an active software power cap. The user reported having neither a wall meter nor a multimeter available, so independent electrical validation remains unavailable at present.

## Candidate voltage/current components in both RM responses

A subsequent isolated, hash-checked trace repeated the known selector-0 average getter three times. In each returned `0x2080a637` buffer, offsets `0x20`, `0x24`, and `0x28` held `752673`, `33867`, and `22224000`. The public result at offset `0x3c` alternated between `752672` and `752673` mW. A second isolated trace used the same selector 0 with the fallback's statically identified instantaneous mode (`2`); it returned success through the separate `0x2080a613` query. Its output repeated the triplet at offsets `0x2c`–`0x34` and `0x40`–`0x48`, and the fallback returned `752673` mW. Both processes exited normally. These traces attached only to the disposable test process, inserted an instrumentation hook, and did not alter the call arguments or output.

**Inference, not identified field semantics:** interpreting `33867` as mA and `22224000` as µV gives `752660.208` mW, about 12.792 mW below `752673` (0.0017%). The numerical relationship and the repeated ordering in two different responses make current/voltage components a plausible lead. However, no source definition or physical measurement confirms the field units, whether these are raw sensor values or computed values, what rail they refer to, or whether the controller uses them. An approximate product is not enough to attribute a failed component or determine a correction. In particular, it is not evidence that an INA sensor is present or that any specific current or voltage is real.

## Plugged-in comparison snapshot

A later isolated selector-0 instantaneous-query trace while AC was connected again returned candidate triplets `752673 / 33867 / 22224000` at both previously observed response positions. At approximately the same time, battery WMI reported power online, charging, and battery voltage 12,108 mV. The candidate triplet's field units remain unverified. No simultaneous RM triplet was captured during the earlier battery-discharge test, so this snapshot alone cannot establish whether those fields follow battery voltage. A user-assisted repeat while unplugged was requested and remains pending.

## Cross-machine numerical pattern

The local average RM response included `752673` at offset `0x20`, `752672/752673` at `0x3c`, and `522264` at `0x40`. A [Razer Blade 17 owner](https://insider.razer.com/general-discussion-6/gpu-limited-to-210mhz-85141) independently reported a 210 MHz cap, approximately 752.7 W board power and 522.3 W chip power. An [ASUS XG Mobile owner](https://www.reddit.com/r/AskTechnology/comments/z9sxo2/laptop_gpu_stuck_in_a_low_power_state/) likewise reported 210 MHz and the same rounded board/chip pair on an RTX 3080 configuration. These are self-reported observations on different hardware; they do not verify the field layout of this machine or establish a common hardware defect.

If offset `0x40` is also expressed in mW, `522264` would round to 522.3 W, matching those reports. That label and unit are an inference, not established by a structure definition, and both reports may rely on related NVIDIA telemetry. The repeated rounded pair nevertheless makes a recurring shared failure representation or saturation worth investigating; it does not prove a sentinel, a specific ADC or a software-only cause, and it does not identify a safe spoofing point.

The ASUS report additionally lists a `PWR_SRC` value of about 230.4 W. Numerically, the local `752673 - 522264 = 230409` (230.409 W if both values are mW), which rounds to that reported value. This three-way arithmetic pattern is noteworthy across the two different machines. The local 230409 figure is **derived**, not a directly identified local field or an independently measured rail; the ASUS labels come from that user's GPU-Z output. Shared driver behavior, a common fallback, and other explanations remain possible.

## More records in the instantaneous response and a short load test

Another isolated trace inspected the first word at `0x40 + index × 0x258` in the successful `0x2080a613` response. Static Windows-driver code at `0x533529` uses this stride when selecting records. The following nonzero words were observed, followed in each record by the next two 32-bit words:

| Index | First word | Next word | Third word |
| ---: | ---: | ---: | ---: |
| 0 | 752673 | 33867 | 22224000 |
| 1 | 522264 | 22992 | 22715000 |
| 3 | 224309 | 9875 | 22715000 |
| 5 | 746573 | 32867 | 22715000 |
| 10 | 6100 | 1000 | 12000000 |
| 11 | 522264 | 22992 | 22715000 |
| 12 | 230409 | 10875 | 21187000 |
| 18 | 1528 | 2125 | 718750 |
| 19 | 6135 | 8532 | 718750 |

For most rows, interpreting the first value as mW and the next two as mA and µV gives a close product. Index 10 is an important counterexample: `1000 × 12000000 / 1000000 = 12000`, not 6100. Values may be calculated differently, stale, synthetic, or have different meanings across records. The meaning, units, validity mask, physical sensors and safety role are not confirmed. Entries with zero or `0xffffffff` as the first word were omitted; omission does not establish they are invalid.

The independent ASUS user's rounded readings of 752.7, 522.3, 224.3, 746.6 and 230.4 W match the numbers in local indices 0, 1, 3, 5 and 12, respectively. This makes a shared multi-record failure representation plausible but does not establish that GPU-Z's labels apply to our indices or identify an upstream failure. The local index 10 value of 6100 also numerically matches the historical 6.10 W reading reported on driver 461.92. That is a lead for investigating channel selection, **not** evidence that the older driver used index 10 or that this is the actual draw.

A separate short CUDA load attempt observed 99% GPU utilization, 58 °C, 210 MHz and 752.67 W after starting a bounded workload. The GPU reading was 752.67 W and 210 MHz before the workload as well. An attempt to attach the separate telemetry tracer during that run timed out, so no per-record values were captured during the load and there is no basis to claim that the 6.1 W record did or did not respond. The load and tracer processes subsequently exited; a follow-up query showed 58 °C, 3% utilization, 210 MHz and 752.67 W. This was a diagnostic observation, not a normal-boost or sustained-protection validation.

## Follow-up: pre-attached trace during a bounded workload

To address the earlier tracer timeout, a fresh selector-0 instantaneous probe was initialized and instrumented before starting the same bounded CUDA workload. After the workload started, `nvidia-smi` reported 99% GPU utilization, 58 °C, 210 MHz and 752.67 W. The workload process was still running both when the RM query was issued and when its response returned. The query returned successfully and the workload completed normally; afterwards `nvidia-smi` showed 3% utilization, 58 °C, 210 MHz, 752.67 W, and software power cap active. No clock, power, voltage, firmware, or driver setting was modified.

In that under-load response, index 10 remained `6100 / 1000 / 12000000`, exactly as in the preceding idle snapshot. Indices 0, 1, 3, 5, 11, and 12 also had the same triplets as the preceding idle snapshot. Index 18 changed from `1528 / 2125 / 718750` to `1567 / 2179 / 718750`; index 19 changed from `6135 / 8532 / 718750` to `7564 / 10520 / 718750`. The two samples were separate snapshots rather than a controlled statistical series, and the observed field units and channel identities remain unverified.

The 6.1 W record did not track the short load in this limited comparison. Because the faulty power path can be stuck, that observation does not rule out its involvement in a control or aggregation path. Its numerical match to the historical 461.92 reading still does not prove the old driver selected this record. The changes at indices 18 and 19 show that at least parts of the returned structure can vary, but do not establish independent physical power, a safe replacement input, or the controller's source. The low clock during this short test, and the active power cap after it, do not constitute normal-boost verification.


## Arithmetic relationships and a 6100 value in VBIOS

The first words of the captured instantaneous records have exact numerical relationships:

- index 5: `746573 = 522264 + 224309` (indices 1 and 3);
- index 12: `230409 = 224309 + 6100` (indices 3 and 10);
- index 0: `752673 = 522264 + 224309 + 6100` (indices 1, 3, and 10).

The second words also satisfy `32867 = 22992 + 9875`, `10875 = 9875 + 1000`, and `33867 = 22992 + 9875 + 1000`. These identities, repeated in the idle and under-load snapshots, are consistent with a hierarchical aggregation of several records. They do not prove the computation direction, units, labels, causal relationships, or what the power controller uses. In particular, selecting only the 6.1 W record as a replacement would ignore the other components and is not a justified or validated power-control fix.

In a separate offline VBIOS inspection, the candidate power-topology table's record 10 contains bytes `d4 17 00 00` at byte offset 19 within that record, representing little-endian integer `6100`; the immediately preceding portion also contains `d4 17 00`. The same 26-byte record occurs in all four saved ROM files. It is fixed in those files, while the local runtime record with index 10 also returned 6100 during both snapshots. The candidate VBIOS version of `257580.rom` matches the currently reported version, but live ROM identity is not established.

The matching number and index make a configuration-derived constant a plausible explanation for the 6.1 W record and the historical older-driver reading. **This is a hypothesis, not a decoded table or proven VBIOS-to-runtime mapping**: the table-entry schema, the units, and whether these two index spaces correspond are unknown. Do not modify firmware or the runtime power records based on this correlation. `tools/inspect_vbios_extdev.py` now emits the record's raw bytes and offset-19 integer to reproduce the observation.

## AC versus unplugged instantaneous records

At the user's request, a later matched-style snapshot was captured after the user disconnected the charger again. Immediately before and after the isolated RM trace, Windows battery WMI reported `PowerOnline=False`, `Discharging=True`, voltage `11599` mV, and discharge rate `57160` (approximately 57.16 W, consistent with the earlier explicitly milliwatt-labelled Windows Runtime battery measurement). The RM query succeeded and returned the same triplets at indices 0, 1, 3, 5, 10, 11, and 12 as in the plugged-in snapshot, including index 0 `752673 / 33867 / 22224000` and index 10 `6100 / 1000 / 12000000`.

Two other triplets differed from the earlier plugged-in snapshot: index 18 was `1236 / 1884 / 656250` and index 19 was `4951 / 7548 / 656250` on battery, compared with `1528 / 2125 / 718750` and `6135 / 8532 / 718750` in the earlier AC snapshot. These were separate, uncontrolled snapshots; time, power policy, activity and other conditions may differ. The changes do not prove the field units or that disconnecting AC alone caused them. The unchanged implausible aggregate across power sources further supports that those particular reported values do not track the battery's changing voltage or whole-system reported power. It does not identify the controller input or prove a physical sensor diagnosis.

The user was told the snapshot was complete and could reconnect AC. The tracer instrumented only a disposable process and did not change driver, GPU or firmware settings.

