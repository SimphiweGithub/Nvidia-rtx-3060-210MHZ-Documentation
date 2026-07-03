# RTX 30-Series Mobile GPU: Permanent P8/210MHz Lock on Newer NVIDIA Drivers

## TL;DR

A cross-vendor, cross-OS bug affecting RTX 3000-series (and reportedly newer) mobile GPUs: after updating past a certain NVIDIA driver version, the GPU permanently locks into the lowest performance state (P8, ~210MHz core / ~405MHz memory) and never boosts under load. The embedded controller (EC) simultaneously reports wildly incorrect power/current telemetry, which the newer driver reads and reacts to by capping clocks as a protective measure. Reverting to an older driver (e.g. 461.92) restores normal boost behavior, at the cost of losing access to newer CUDA versions.

**Update: a working, confirmed software workaround was found for this case** — see "Confirmed Workaround" below. It does not fix the root cause, but it recovers most of the lost performance while staying on a modern driver with full CUDA support.

## Affected Hardware (confirmed across sources)

- Dell G15 5510 (Intel i7-10870H + RTX 3060 Laptop, 6GB) — this case
- MSI laptops (model unspecified in source thread, RTX 3060)
- Acer Nitro 5 (RTX 3060)
- ASUS ROG (model unspecified)
- Medion Erazer Deputy P25 (AMD Ryzen 7 5800H + RTX 3060)

Spans both Intel and AMD CPU platforms, and at least four OEMs, all sharing NVIDIA RTX 30-series mobile GPUs. This points to the common factor being the **NVIDIA driver's power-state transition logic**, not any single OEM's board design — though each OEM's EC implementation determines exactly how badly it manifests.

## Symptom Signature

- Graphics clock frozen at exactly 210MHz (sometimes reported alongside 405MHz or 840MHz memory/video clock, depending on GPU)
- GPU utilization can read 99-100% while clock stays locked — the workload is real, the GPU just won't boost
- Power/current telemetry is internally inconsistent with reality:
  - On working drivers: power reading can freeze at an implausibly low flat value (e.g. 6.1W) while clock and utilization visibly vary — a dead telemetry channel, not a real cap
  - On broken drivers: power reading spikes to 700-800W (physically impossible for these parts), current readings on individual rails freeze at high values (e.g. 22-33A per rail)
  - "Power Limit" flag in monitoring tools (HWInfo/HWMonitor) shows active (1) continuously on broken drivers
  - The Power Limit (%) control in MSI Afterburner is greyed out/unavailable on the affected unit, regardless of driver
- GPU temperature stays low (40-50°C) — this is *not* thermal throttling
- Can appear immediately on driver install, or only after the GPU attempts to transition out of P8 under stress (varies by how far past the breaking driver version you are)
- PCIe link can also degrade (seen dropping to Gen1 2.5GT/s with recoverable link errors in this case)

## Root Cause — CONFIRMED: Frozen Power-Telemetry Reading + Permanent SW Power Cap

The GPU's power-measurement channel reports a **frozen, physically impossible ~752.67 W** to the driver (see "Definitive Diagnostic" below for the raw readout). Drivers newer than ~461.92 read this channel and enforce the platform power limit (80 W on this unit) against it: since 752.67 W can never be brought under 80 W, the driver's **SW Power Cap engages permanently** and pins the GPU at the bottom of its V/F curve (~210 MHz). Driver 461.92 and older never read this channel — they display a separate dead 6.1 W value — and therefore boost normally. The defect itself is hardware-level, most likely the current-sense/telemetry circuit on the GPU's power delivery feeding a stuck value, which is why it survives OS reinstalls, driver wipes, EC resets, AWCC removal, and full vBIOS swaps.

Confirmed ruled out on this unit: AWCC (service stopped/disabled, no change), Windows-install corruption (reproduced identically on Linux), stuck volatile EC state (full power-drain reset performed, no change), thermal throttling (temps stay low while locked). This points to a genuine hardware-level defect, most likely in the GPU's power telemetry circuit (e.g. a current-sense IC on the VRM), that only newer drivers act upon.

## Definitive Diagnostic: `nvidia-smi -q -d PERFORMANCE,POWER`

**This should be step one for anyone with this symptom** — one read-only command distinguishes every competing theory. `nvidia-smi.exe` ships with the driver (`C:\Windows\System32`), no admin needed:

```
nvidia-smi -q -d PERFORMANCE,POWER
```

Result on this unit (driver 610.62, GPU idle at the desktop):

```
Performance State                : P0
Clocks Event Reasons
    SW Power Cap                 : Active
    HW Slowdown                  : Not Active
        HW Thermal Slowdown      : Not Active
        HW Power Brake Slowdown  : Not Active
Clocks Event Reasons Counters
    SW Power Capping             : 4,007,672,629 µs (cumulative)
    HW Power Braking             : 0 µs
GPU Power Readings
    Average Power Draw           : 752.67 W
    Instantaneous Power Draw     : 752.67 W
    Current Power Limit          : 80.00 W
    Max Power Limit              : 95.00 W
```

What this one readout proves:

- **The power sensor is frozen at 752.67 W.** Average and instantaneous identical to the hundredth of a watt, at desktop idle, on a GPU whose real ceiling is 95 W. This is the phantom ~750 W reading seen in monitoring tools all along — now confirmed as what the driver itself sees and acts on.
- **SW Power Cap: Active — permanently.** The driver must keep the GPU under 80 W, reads 752.67 W no matter what it does, and so drives clocks to the floor and holds them there. The cap can never release because the reading never changes.
- **HW Power Brake: lifetime counter of zero.** The physical emergency-brake pin has never been asserted — the board's protection circuit is fine. It is purely the *measurement* that is broken.
- **Performance State: P0.** The GPU was never "stuck in P8" — it sits in P0, power-capped to the clock floor. Every P-state-forcing tool (Profile Inspector overrides, Prefer Maximum Performance) was aimed at a problem that never existed, which is why they all did nothing.
- **Why the +1000 offset delivers exactly ~1207 MHz:** the cap crushes the GPU to the bottom of its V/F curve (~210 MHz); a clock offset shifts the entire curve upward, so the same floor lands at ~1207 MHz. The offset never "unlocked boost" — it raised the floor the cap pins you to. This is also why it's rock-stable: the GPU isn't oscillating around a boost target, it's parked.
- **`nvidia-smi -pl` is mathematically useless here**: the max settable limit can never exceed a frozen 752.67 W reading, regardless of what that limit is set to.

**Correction from later in this session**: an earlier version of this document claimed the platform unconditionally overrides vBIOS-declared power limits (based on the ASUS vBIOS test still showing Dell's 80W/95W enforced). A third vBIOS test (Mechrevo, 115W/140W tables) **disproved this** — after flashing it, `nvidia-smi` showed the power limit genuinely change to 115W/140W, exactly matching Mechrevo's declared values. So the power *limit* value is genuinely vBIOS-influenced after all; the ASUS result was likely an incomplete flash of that specific table section, not evidence of a platform override. What doesn't change, across all three vBIOS (Dell 80/95, ASUS 115/130, Mechrevo 115/140): **the final delivered clock with the +1000 offset is 1207MHz, every time**, regardless of which power limit is active. See "The Math" below for why that specific invariance makes sense despite the power limit itself being real and changeable.

### The Math: Why It's Always Exactly 1207MHz

**1207 MHz = 210 MHz (the P8 floor) + 1000 MHz (the Afterburner offset), landing on the nearest clock step the GPU's generator can produce.**

- The SW Power Cap permanently parks the GPU at P8, whose base clock is ~210MHz — this is the original "stuck at 210MHz" symptom.
- An Afterburner clock offset does not set an absolute target — it **adds to whatever floor the GPU currently sits at**. Since the cap keeps the GPU pinned at P8 regardless of vBIOS, power limit, or curve configuration, the offset always applies to the same 210MHz starting point.
- 210 + 1000 = 1210. Delivered: 1207. The 3MHz gap is clock-generator step granularity (GPU clocks move in discrete increments, not continuously).
- This is why **nothing else mattered** across every experiment in this document: the curve target, the vBIOS, the power limit — none of them touch the P8 floor value (210) or the offset value (1000), so the sum was always going to land in the same place. It's simple addition against a floor that never moved, because the one thing that determines the floor — the frozen power sensor forcing P8 — never changed either.

## Confirmed Workaround: MSI Afterburner Core Clock Offset

**Result: recovers the GPU from a dead 210MHz lock to a stable 1207MHz on driver 610.62 — a ~5.7x improvement, confirmed stable under sustained real load.**

### Setup
1. Open MSI Afterburner (already handles GPUs where NVIDIA Control Panel may not be available)
2. Under **Clock → Core (MHz)**, click the numeric field and type **1000**, press Enter
3. Click **Apply**
4. Save as a profile, then in **Settings (gear icon) → General**, enable **"Apply overclocking at system startup"** so it survives reboots — without this, the GPU reverts to the 210MHz lock on every restart

### Notes and limitations
- The **Power Limit (%)** slider is greyed out entirely on this unit — vBIOS-level restriction, unrelated to the P8 bug, could not be adjusted
- The simple Core (MHz) offset field **hard-caps at +1000** — typing a higher value (tried 1400) has no effect, it clamps back to 1000
- Actual delivered clock (1207MHz) is noticeably below this chip's normal stock boost range (~1400-1700MHz depending on TGP configuration) — this is a partial recovery, not a full fix

### Validation performed
- **3DMark Steel Nomad benchmark**: GPU clock held perfectly flat at ~1200MHz for the entire benchmark run (no reverting to 210MHz under real sustained load) — confirms the fix is stable, not just an idle-screen reading
  - Score: 1539 vs. same-hardware average of 1823 (~84%) and best of 2186 (~70%) — roughly a 15-16% performance deficit vs. typical same-model laptops, consistent with running at ~80-85% of this chip's normal boost clock
  - Note the pink "GPU Clock Frequency (MHz)" trace in the monitoring graph below staying perfectly flat for the full run — this is the stability confirmation, not just the final score

  ![Steel Nomad benchmark result showing stable ~1200MHz GPU clock throughout the run](images/steel-nomad-benchmark-result.png)
- **eFootball real-world test**: performance was identical or better compared to the original 461.92 baseline. This confirms the original diagnosis (see timeline below) that eFootball's FPS inconsistency was CPU-bound, not GPU-clock-bound — the GPU lock/fix has little to no effect on that specific game either way

## Curve Editor Experiments (attempted, not recommended — documented as negative results)

After the simple offset worked, further attempts were made in Afterburner's Voltage/Frequency Curve Editor to push past 1207MHz toward this chip's normal ~1600-1700MHz boost range. These were **unsuccessful and inconsistent**, and are documented here so nobody repeats the same dead ends:

- The curve editor renders two lines: a **bold/dashed interactive curve** (the actual editable V/F table, confirmed by direct testing — only this one responds to clicks/drags) and a **thin non-interactive reference line** underneath it (does not respond to clicks or drag attempts at all)
- **Attempt 1**: flattened the low-voltage section (700-950mV) of the bold curve to a fixed 2300MHz. Result: **worse** — actual delivered clock dropped to ~1000MHz, lower than the simple offset's 1207MHz
- **Attempt 2**: shifted the entire bold curve uniformly upward by +50MHz. Result: **no change at all** — actual delivered clock remained exactly 1207MHz
- **Conclusion**: actual delivered clock does not scale predictably, linearly, or even monotonically with the configured V/F curve on this unit. The broken telemetry/P-state logic appears to override or ignore the curve in ways that don't respond to straightforward tuning, and can react worse to an artificially flattened curve shape than to the offset-shifted default shape. **Recommendation: use the simple Core (MHz) offset slider (+1000) instead of manual curve editing** — it's the only method that has produced a reproducible, stable result.

**Follow-up round (later session): locked points can exceed the +1000 slider cap, but it doesn't matter.** Discovered that individually locking a curve point (select a point, press `L`) can hold an offset value above the simple slider's +1000 ceiling — found one persisted at +1050, then manually pushed to +1400 (target ~2607MHz at 731mV). This is genuine new information: the simple offset field's +1000 cap and the curve editor's actual ceiling are two different things. However, every variation tested still produced the identical 1207MHz delivered clock:
- Single-point spike to +1400/2607MHz at 731mV — no change, still 1207MHz
- Full range selected (Shift+click first/last point) and flattened — no change, still 1207MHz
- Entire curve pushed to a 3000+ MHz target — no change, still 1207MHz
- Direct NVML clock lock, bypassing Afterburner and the curve editor entirely (`nvidia-smi -lgc 1350,1702`) — no change, still 1207MHz

This is now the most exhaustively tested finding in the whole investigation: the delivered clock is invariant not just to vBIOS and power limit, but to *every* method of requesting a higher clock, including ones that bypass Afterburner's UI entirely. Consistent with "The Math" above — none of these methods change the P8 floor value (210) or the offset applied to it (1000), so none of them can move the result.

### Why the P8 Floor Itself Can't Be Edited

Since delivered clock = P8 floor + offset, the obvious next question is whether the **P8 floor value (210MHz) itself** can be changed — if it could, the same +1000 offset would land somewhere much higher (e.g., a 700MHz floor would put the same offset at ~1700MHz, right in this chip's normal boost range).

**This is technically true in principle and practically blocked by design.** NVIDIA's own "Virtual P-state Table" specification confirms P-state clock values (including P8's) are stored in a vBIOS data table, not hardwired into silicon. But two things close this off:

1. **Empirical evidence this value isn't vendor-customized**: three different vendor vBIOS (Dell, ASUS, Mechrevo) all produced the identical 210MHz P8 base, despite genuinely different power limit tables across the same three files. Power limits vary by vendor; this value apparently doesn't — consistent with it being a standardized reference default rather than something OEMs configure per-model.
2. **Ampere-generation vBIOS is cryptographically signed (NVIDIA Falcon Security)**: any hand-edit to a vBIOS — even changing a single table entry — breaks its cryptographic signature. Flashing a modified/unsigned vBIOS causes the Falcon (NVIDIA's onboard security microcontroller) to shut the GPU core down before it even POSTs. This is why flashing *complete, differently-signed* vendor vBIOS files worked fine all session (each one's signature is independently valid), but hand-editing a specific value inside any of them would not — it's a fundamentally different, much riskier class of action than anything performed in this document, requiring firmware security bypass techniques (SPI programmer recovery, signature forgery) that are out of scope for a consumer fix.

Conclusion: the math for "raise the floor to raise the ceiling" is completely valid, but the floor sits behind a deliberate cryptographic lock on this GPU generation, not just a missing tool.

## This Case: Full Diagnostic Timeline (Dell G15 5510)

System: Dell G15 5510, i7-10870H, RTX 3060 Laptop 6GB, BIOS 1.38.0 (2025/11), Windows 11 Pro.

1. Baseline complaint: inconsistent FPS in eFootball on driver 461.92, locked to this driver because it's the only one that doesn't force the GPU into permanent P8
2. HWMonitor on 461.92: GPU clock ranges 522-1425MHz normally, utilization moves 14-40%, but GPU Power reads a frozen flat 6.10W throughout — identified as a dead telemetry channel, not a real power cap
3. Installed driver 610 (latest at time of testing): GPU clock frozen at 210MHz, "Power Limit" = 1 constantly, current readings frozen at implausible values, PCIe degraded to Gen1 with 61 recoverable errors
4. Stopped + disabled AWCCService entirely, retested — no change
5. NVCleanstall with only Display Driver + PhysX components — no change
6. Full EC power-drain reset — no change
7. Cross-OS test on Linux with a modern driver — **same lock behavior reproduced**, ruling out Windows/registry/AWCC-stack corruption
8. Root cause conclusion: EC-to-driver power telemetry communication broken at a level that survives OS reinstall, AWCC removal, and EC reset — most likely a hardware defect in the GPU power telemetry circuit. No warranty remaining; no local repair shop capable of board-level diagnosis
9. **MSI Afterburner +1000 Core Clock offset applied on driver 610.62 — GPU recovered to a stable 1207MHz.** Confirmed stable via 3DMark Steel Nomad (clock held flat under full load) and real-world eFootball testing (no regression vs. 461.92 baseline)
10. Further curve editor tuning attempted to push past 1207MHz — inconsistent/regressive results, abandoned in favor of the simple offset (see "Curve Editor Experiments" above)

## Ruled Out

| Cause | Status | How it was ruled out |
|---|---|---|
| AWCC / Alienware Command Center | Ruled out | Service stopped + disabled, issue persisted |
| Windows install corruption | Ruled out | Reproduced identically on Linux |
| Stuck volatile EC state | Ruled out | Full power-drain reset performed, no change |
| Thermal throttling | Ruled out | GPU temps stay low (40-50°C range) while locked |
| Specific AWCC version (5.x vs older) | Untested | No older AWCC installer available to test |
| BIOS version | Partially ruled out | Already on latest (1.38.0); Dell blocks downgrades on many G-series models |
| Manual V/F curve tuning beyond +1000 offset | Ruled out as unproductive | Flattening gave worse results; uniform shift gave no change (see Curve Editor Experiments) |
| NVIDIA Profile Inspector (P-State override at driver profile level) | Ruled out | Tried previously (prior to this write-up); did not resolve the lock |
| MSI Afterburner OC Scanner | Ruled out | Fails immediately with "Failed to start scanning!" — most likely because OC Scanner requires trustworthy real-time power/voltage telemetry to iteratively test points, which this unit cannot provide (consistent with the root cause) |
| NVIDIA Profile Inspector — "Power Management - Mode" → "Prefer maximum performance" (retested this session) | Ruled out | Set on Global Driver Profile, driver 610.62, Apply Changes clicked. No change to actual GPU clock. Same driver-level-policy-can't-fix-hardware-telemetry pattern as everything else |
| Core (mV) voltage slider in Afterburner | Ruled out | Voltage control is locked/greyed out on this unit, same as the Power Limit (%) slider. Not accessible to test at all |
| **Different vBIOS with a higher-rated power/clock table** (tested 3x: MSI/prior-session, ASUS, Mechrevo) | **Ruled out for delivered clock; power limit itself IS vBIOS-real** | Flashed hash-verified ASUS (94.06.17.00.65, 115W/130W, 1702MHz rated) and Mechrevo (94.06.3B.00.0B, 115W/140W, 1702MHz rated) vBIOS via NVFlash `-6`. Confirmed via `nvidia-smi` that Mechrevo's power limit genuinely took effect (115W/140W exactly, correcting an earlier session note that assumed platform override). Despite the power limit being real and different across all three vBIOS, delivered clock with +1000 offset was **identical: 1207MHz in all three cases** — see "The Math" section for why |
| Locked curve point exceeding the +1000 slider cap (+1050, then +1400) | Ruled out for delivered clock, but genuine new mechanism found | Slider caps at +1000; a locked individual point can hold higher values. Tested as a spike (+1400/2607MHz @ 731mV), a flattened full-range selection, an extreme 3000+ MHz target, and a direct NVML clock lock bypassing Afterburner entirely (`nvidia-smi -lgc`). All four produced identical 1207MHz |
| Editing the P8 floor value (210MHz) directly in vBIOS | Ruled out — blocked by design, not by missing tooling | NVIDIA's Virtual P-state Table spec confirms this value is vBIOS-stored in principle, but Ampere-generation vBIOS is cryptographically signed (Falcon Security) — any hand-edit breaks the signature and the GPU refuses to POST. Three vendor vBIOS all shared the identical 210MHz value regardless of differing power tables, suggesting it's a standardized default OEMs don't customize anyway |
| DisableDynamicPstate / KBOOST registry tricks | Ruled out | KBOOST itself hasn't worked on any driver since 378.49 (2017); its "modern equivalent" is the same DisableDynamicPstate key, already tested with no effect |
| GPU power telemetry spoofing (fake the sensor reading before the driver sees it) | Not attempted — no accessible tooling | Would require custom kernel-mode driver hooking or ACPI table override against undocumented internals; no existing consumer tool does this for NVIDIA GPUs. Out of scope without dedicated security-research-level tooling |

## Untested — Worth Trying Next

**Update: as of this session, every item below has now been tried or confirmed inaccessible. This section is kept for historical reference — see the Ruled Out table above and the Final Conclusion below for the current state.**

1. ~~NVIDIA Profile Inspector~~ — already tried prior to this write-up, did not resolve the lock. Ruled out (see table above).
2. ~~MSI Afterburner's OC Scanner~~ — fails immediately with "Failed to start scanning!". Ruled out (see table above).
3. ~~The dedicated Core (mV) voltage slider~~ — locked/greyed out on this unit, same as Power Limit (%). Ruled out (see table above).
4. ~~Test the same +1000 offset trick on a vBIOS with genuinely different/higher-rated power and clock tables~~ — completed this session with a hash-verified ASUS vBIOS (94.06.17.00.65, 115W/130W power, 1702MHz rated boost vs Dell's 80W/95W, 1425MHz). Confirmed via GPU-Z that the flash took. **Delivered clock was identical: 1207MHz.** This is the definitive test — see Ruled Out table above.
5. ~~NVIDIA Control Panel → Prefer Maximum Performance~~ — equivalent setting tested via Profile Inspector's "Power Management - Mode", no effect. Ruled out (see table above).
6. ~~Extended power drain~~ — superseded by the vBIOS swap test, which is a stronger test of the same "is this a resettable/configurable state" hypothesis and came back negative.
7. ~~Toggle Hybrid vs. Discrete-only GPU mode in BIOS~~ — **impossible on this unit**: the Dell G15 5510 has no MUX switch, so it's permanently in Hybrid/Optimus mode with no discrete-only option to toggle to. Ruled out, not just untested.
8. ~~Disable the wired Ethernet adapter~~ — **not applicable on this unit**: Device Manager shows no physical wired Ethernet adapter at all (only Wi-Fi, Bluetooth, and virtual/WAN Miniport entries). This specific G15 5510 configuration has no Ethernet port/controller to disable.
9. ~~GPU VBIOS reflash~~ — completed this session with full verification (hash-matched files, confirmed genuine Dell backup staged first). See item 4 above and the Ruled Out table — this is now a definitive negative result, not an open option.

## Final Conclusion

After this session's testing, **1207MHz (via the MSI Afterburner +1000 Core Clock offset) is the confirmed practical ceiling for this unit**, and it is very unlikely to be improved further by any driver, firmware, or software configuration. The evidence: a full vBIOS swap to a different vendor's genuinely higher-rated firmware (higher power target, higher rated boost clock) produced an identical delivered clock, which rules out vBIOS configuration as the limiting factor. Combined with everything else ruled out this session (AWCC, driver version, Profile Inspector, OC Scanner, curve editing, voltage control being locked entirely), the ceiling is now **confirmed** (via the `nvidia-smi` readout — see Definitive Diagnostic above) to be the driver's SW Power Cap acting on a frozen ~752 W telemetry reading against an 80 W platform limit — a condition no end-user setting can clear, because the reading never changes.

**Final lever tested and closed out**: the `DisableDynamicPstate` registry DWORD (`HKLM\SYSTEM\CurrentControlSet\Services\nvlddmkm`, value `1`) — a driver-level flag telling the driver to stop dynamically managing power/P-states, effectively replicating what 461.92 does by never querying the channel at all. Result: **no effect**. Post-reboot `nvidia-smi` showed the identical frozen ~752W reading against the same 80W cap, bit-for-bit unchanged. This was the last driver/registry-level intervention available and it did not touch the underlying telemetry.

**This closes the software investigation definitively.** Every accessible lever — driver version switching, AWCC, NVPCF disable (blocked by locked Dell BIOS), Profile Inspector P-state overrides, OC Scanner, manual curve editing, voltage control (locked), a full cross-vendor vBIOS swap with genuinely different power tables, and now direct driver-level power-management disable — has been tested and failed to change the frozen sensor reading. Combined with the HW Power Brake counter reading zero for the GPU's uptime (the physical protection circuit has never engaged), the fault is isolated to the **power-sensing/current-measurement circuit itself** — most likely a failed or miscalibrated current-sense IC or ADC on the GPU's power delivery path. This requires physical board-level diagnosis and repair; no further software, driver, firmware, or vBIOS change can address it.

**Recommended end state**: revert to the genuine Dell stock vBIOS (verified backup available), keep the +1000 Afterburner offset active with "Apply overclocking at system startup" enabled, and keep the 7301MHz memory overclock (independently validated, unrelated to this core-clock ceiling). This combination gives working CUDA 12.x access, a stable 1207MHz core clock (up from a fully dead 210MHz lock), and no regression on CPU-bound workloads — the practical, evidence-based best outcome achievable on this hardware.

### This Chapter Is Closed

A later session pushed further, specifically trying to find any way past 1207MHz, and the additional testing only reinforced the conclusion above rather than changing it:

- A third vendor vBIOS (Mechrevo, 115W/140W) corrected an earlier assumption (power limit *is* genuinely vBIOS-influenced) but still produced the identical 1207MHz delivered clock — see "The Math" section above for the actual arithmetic (P8 floor 210MHz + 1000MHz offset ≈ 1207MHz reported, invariant because neither number ever changes).
- A newly-discovered ability to exceed the Afterburner slider's +1000 cap via locked curve points was tested exhaustively (spike, full-range flatten, extreme target, direct NVML clock lock) — all four still landed on exactly 1207MHz.
- The logically sound follow-up question — "if delivered clock = floor + offset, can the floor itself be raised?" — is technically true in principle (P-state clocks are vBIOS-stored data, confirmed via NVIDIA's own Virtual P-state Table spec) but blocked by Ampere's cryptographic vBIOS signing (Falcon Security): any hand-edit to a vBIOS breaks its signature and prevents the GPU from posting at all. This is a deliberate security boundary, not a tooling gap.
- GPU telemetry "spoofing" (faking the sensor reading before the driver sees it) was considered and correctly identified as requiring custom kernel-mode or ACPI-level development with no existing tool for the job — out of reach without dedicated security-research tooling.

**One closing, general note unrelated to this specific defect**: newer NVIDIA drivers do not reliably provide raw performance improvements for existing hardware in already-released games — benchmarking evidence shows mixed results (some games identical, some actually faster on older drivers), since driver optimization effort is generally aimed at the currently-active GPU generation, not older cards. For this unit specifically, the practical value of staying on a modern driver was always CUDA/API access and Game Ready profiles for new titles, not raw FPS gains — worth remembering so the 1207MHz ceiling isn't mistaken for "falling behind" on driver-side performance in general.

No further avenues remain that don't require specialized hardware reverse-engineering or firmware security research. The investigation is complete.

## Practical Fallback

With the +1000 offset workaround in place, this is now less critical, but still worth knowing: on 461.92 (no offset needed, GPU boosts normally), the **Vulkan compute backend** (supported by llama.cpp, Ollama, LM Studio) gets full GPU utilization for local LLM inference without touching CUDA at all — a fallback if the workaround ever stops being reliable on a future driver.

## Sources

- [MSI Global English Forum — "GPU stuck at 210 MHz"](https://forum-en.msi.com/index.php?threads/gpu-stuck-at-210-mhz.388801/)
- [Tom's Hardware — "GPU on 100% but GPU stuck on 210 mhz"](https://forums.tomshardware.com/threads/gpu-on-100-but-gpu-stuck-on-210-mhz.3803947/)
- [Tom's Hardware — "GPU clock stuck at 210 MHz"](https://forums.tomshardware.com/threads/gpu-clock-stuck-at-210-mhz.3777250/)
- [Tom's Hardware — "My laptop's RTX 3060 is stuck on 210MHz core speed?"](https://forums.tomshardware.com/threads/my-laptops-rtx-3060-is-stuck-on-210mhz-core-speed.3800963/)
- [NVIDIA GeForce Forums — "(LAPTOP) gpu stuck at 210 mhz core clock and 405 mhz"](https://www.nvidia.com/en-us/geforce/forums/geforce-laptops/6/497370/laptop-gpu-stuck-at-210-mhz-core-clock-and-405-mhz/)
- [NVIDIA GeForce Forums — "Laptop GPU stuck at 210 mhz core clock and 405 mhz" (game-ready-drivers board)](https://www.nvidia.com/en-us/geforce/forums/game-ready-drivers/13/511232/laptop-gpu-stuck-at-210-mhz-core-clock-and-405-mhz/)
- [Medion Community — "RTX 3060 stuck at 210 MHz GPU clock on Medion Erazer Deputy P25"](https://community.medion.com/t5/Notebook-Netbook/RTX-3060-stuck-at-210-MHz-GPU-clock-on-Medion-Erazer-Deputy-P25/td-p/185705)
- [ASUS ROG Forum — "GPU clock speed stuck at 210mhz After Re-Install Windows"](https://rog-forum.asus.com/t5/gaming-notebooks/gpu-clock-speed-stuck-at-210mhz-after-re-install-windows-rog/td-p/1124779)
- [Linus Tech Tips — "Gpu clock and watt is getting stuck at 210mhz and 22W"](https://linustechtips.com/topic/1501430-gpu-clock-and-watt-is-getting-stuck-at-210mhz-and-22w-and-not-using-full-power-but-running-at-99-utilization/)
