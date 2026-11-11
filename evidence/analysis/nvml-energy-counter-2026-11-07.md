# NVML energy counter and power reading — 7 November 2026

At approximately 08:43 South Africa time, with driver 610.62 and the core offset removed, a read-only Python `ctypes` call to the installed `nvml.dll` sampled `nvmlDeviceGetTotalEnergyConsumption` and `nvmlDeviceGetPowerUsage` three times, with two-second sleeps between samples. Initialization, device lookup, and every query returned `NVML_SUCCESS` (0).

| Sample | Total energy (mJ) | Reported power (mW) |
| --- | ---: | ---: |
| 1 | 8,269,777,964 | 752,673 |
| 2 | 8,271,282,804 | 752,673 |
| 3 | 8,272,787,613 | 752,673 |

The energy increments were 1,504,840 and 1,504,809 mJ across intervals of at least two seconds. Their rough rates are close to the same implausible 752.67 W. The exact elapsed times were not measured, so these are not precision power measurements. This counter is therefore not an independent physical-power validation: it is consistent with integrating or otherwise sharing the erroneous telemetry. It does not localize the fault, establish true power draw, or prove which controller makes the power-capping decision.

The query used the standard read-only NVML functions; it did not change clocks, power limits, firmware or control settings. NVIDIA documents the energy reading in millijoules since the driver was reloaded and power in milliwatts: [NVML device queries](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html).
