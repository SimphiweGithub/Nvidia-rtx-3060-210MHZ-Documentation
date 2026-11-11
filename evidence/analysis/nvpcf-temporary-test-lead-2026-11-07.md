# NVIDIA platform-controller test lead — 7 November 2026

A [Linux user report](https://github.com/CachyOS/CachyOS-Settings/issues/203) describes the same 752.67 W GPU reading on a different Lenovo/RTX 3070 laptop and reports that disabling `nvidia-powerd` after reboot or driver reload resolved that person's symptoms. It is a single external report, and its cause and applicability to this Dell/Windows system are not established. The `gpu-unlock` tensor-throughput project found in a separate search addresses a different problem and provides no evidence of a fix for this throttle.

The active Windows machine has an enabled PnP device `NVIDIA Platform Controllers and Framework`, instance `ACPI\NVDA0820\NPCF`, with driver service `nvpcf` running, version `32.0.16.1029`. The project's historical notes say the BIOS did not expose a way to disable NVPCF, but do not establish that a temporary Windows PnP disable was tested. This is a reasonable diagnostic lead because the platform controller participates in dynamic laptop power management; it is not proven to be equivalent to Linux's daemon or responsible for the GPU reading.

A temporary device-disable attempt from the current, non-administrator session failed with `Generic failure`; the device remained `OK`, `CM_PROB_NONE`. No before/after GPU comparison occurred. To make the test concrete, `tools/test_nvpcf_temporarily.ps1` checks for elevation and an initially enabled device, records the normal GPU state, requests a short device disable, records the GPU state, and re-enables the device in `finally`. It verifies final device status and prints a manual restoration command if it cannot. It does not change clock offsets, voltage, firmware, power-limit settings, or the driver's start type. If Windows requires a reboot or the device does not actually stop, a missing immediate effect is inconclusive; do not reboot with the device intentionally disabled. The script's unelevated preflight was tested and exits before changing state.

This test needs an administrator session. The current agent process is not an administrator. It has not yet shown that disabling the platform device will change telemetry or boost, and even a successful change would require checking power limits, behavior under load, and rollback.

NVIDIA's published [Dynamic Boost control-panel note](https://nvidia.custhelp.com/app/answers/detail/a_id/5087/kw/support/related/1) states that its older Max-Q Dynamic Boost global toggle is unavailable on RTX 30-series notebook GPUs and newer. That source is dated 2021 and does not document this particular installed driver version, but it weakens the idea that the published 20-series Control Panel toggle is a direct route for this 3060.

## Completed temporary Windows test

On 7 November at 13:28, the diagnostic was launched in an elevated, visible PowerShell after the user's earlier command failed before producing a log. It completed successfully and automatically restored the device. The saved raw output is [nvpcf-temporary-test-20261107-132831.txt](../runs/nvpcf-temporary-test-20261107-132831.txt):

| Stage | PnP device state | GPU telemetry |
| --- | --- | --- |
| Before | `OK`, `CM_PROB_NONE` | 210 MHz, 752.67 W, software power cap active |
| Five seconds after disable | `Error`, `CM_PROB_DISABLED` | 210 MHz, 752.67 W, software power cap active |
| After restore | `OK`, `CM_PROB_NONE` | 210 MHz, 752.67 W, software power cap active |

The immediate temporary Windows PnP disable did not clear the reported power or cap. The OS-reported device disable and subsequent restoration were verified, but the test did not verify whether the service fully unloaded, restart the GPU driver, reboot, or run a load benchmark. Thus it does not exclude a latched platform/driver effect requiring reload, and idle clock alone does not establish boost behavior. It is narrower than the Linux report, which described a reboot or driver reload. The final platform device status was independently queried as `OK`, `CM_PROB_NONE`.

## Driver-reload consideration

A driver reload could distinguish an immediate platform-device toggle from an effect latched at GPU initialization, but the machine currently reports 14 NVIDIA compute/graphics-client entries, including interactive desktop applications. A driver reset can disrupt or terminate those clients. The test therefore did not reload the GPU driver or reboot, and no conclusion is drawn about effects that require reinitialization. The integrated Intel GPU reports the active 1920×1080 desktop, but that alone does not make resetting the NVIDIA device nondisruptive to applications using it.

## GPU device restart while platform device was disabled

After the user saved their work and approved elevation, the prepared diagnostic ran at 21:08 on 7 November. Before the test, the GPU reported 752.67 W, 210 MHz, and an active software power cap. Windows confirmed the NVIDIA platform device was disabled, then `pnputil /restart-device` reported that the NVIDIA GPU device restarted successfully and returned exit code 0. A reading taken with the platform device confirmed disabled both before and after the sample still showed 752.67 W, 210 MHz, and the software cap active. The GPU subsequently reported PnP status `OK`, `CM_PROB_NONE`.

The script restored the platform device, verified `OK`, `CM_PROB_NONE`, and an independent watchdog confirmed the same state after 90 seconds. A later independent query also confirmed the platform device was healthy and the GPU still reported 752.67 W, 210 MHz, and active software power cap. Logs: [main test](../runs/nvpcf-gpu-restart-20261107-210849.txt) and [watchdog](../runs/nvpcf-gpu-restart-20261107-210849.txt.watchdog).

This rules out an immediate improvement from this particular PnP device-restart sequence. PnP reported success, but the test did not prove that the kernel driver or GPU firmware fully unloaded and reinitialized, and it did not reboot; therefore it does not rule out effects requiring a complete driver unload or reboot. It did not modify offsets, firmware, or power limits, and it did not validate normal boost or protections under sustained load.

At 21:15, after the platform device had been restored and the watchdog had confirmed it healthy, a bounded eight-second CUDA workload produced one initial idle sample followed by eight one-second-spaced high-load samples. The idle sample showed `0% / P8 / 210 MHz / 752.67 W / 57°C / SW cap active`; the high-load samples showed `99–100% / P0 / 210 MHz / 752.67 W / 58–59°C / SW cap active`. The workload completed normally. This shows that the device can report P8 at idle and P0 under load, but it did not boost in this short test. It does not establish sustained performance or independently validate thermal or power protections.

### Post-test energy-counter timing

At `2026-11-07T21:12:38.708678+02:00`, a successful read-only `nvmlDeviceGetTotalEnergyConsumption` query returned `168051838` mJ. If the reported power had stayed constant at 752673 mW since the counter started, dividing the counter by that rate estimates a counter start at `21:08:55.435`, within the `21:08:51.819`–`21:08:56.145` platform-disabled GPU-restart interval. A separately captured 08:43 counter was already above 8.2 billion mJ. These data are consistent with the device restart resetting the energy counter and hence with some GPU/device reinitialization during the test. The start time is an estimate based on an implausible software power value and a constant-rate assumption; no counter sample was captured immediately before the restart. Other resets between 08:43 and 21:08 remain possible. This does not prove a complete kernel-driver unload, GPU firmware reload, or that Windows NVPCF behaves like Linux `nvidia-powerd`.
