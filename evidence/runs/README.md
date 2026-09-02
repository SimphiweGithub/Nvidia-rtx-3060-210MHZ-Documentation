# Controlled probe runs

Each CSV is produced by [`tools/NvmlEvidenceProbe`](../../tools/NvmlEvidenceProbe/). The probe is read-only: it dynamically loads `nvml.dll`, calls NVML query functions, and writes the returned values without setting clocks, limits, registry values, or driver controls.

## `nvml-probe-2026-09-02-initial.csv`

- Captured: 2026-09-02 10:47:34–10:47:43 UTC
- Driver: 610.62
- NVML: 13.610.62
- GPU index: 0
- Samples: 10 at 1-second intervals
- SHA-256: `37c5e8e1e0cd0628b06344b6fa997359552f4c7eb3391623b21cb6f9c6ee2533`

Observed result: all ten calls succeeded and returned `752672` or `752673 mW`; P-state remained `P0`; graphics and memory clocks remained `1207 MHz` and `7301 MHz`; the enforced power limit was `115000 mW`.

The CSV header records the full path and SHA-256 digest for both loaded NVML modules. This is important because the earlier debugger session showed distinct System32 and DriverStore module copies.

## `nvml-power-only-2026-09-02.csv`

- Captured: 2026-09-02 11:42:59 UTC
- Driver: 610.62
- NVML: 13.610.62
- GPU index: 0
- Samples: 1
- Query scope: device lookup plus `nvmlDeviceGetPowerUsage()` only
- SHA-256: `d250890da926c0546bb8c2bfd6ad51d5854c82324ec7836f5249959cde140c78`

Observed result: the isolated direct query succeeded and returned `752673 mW`. P-state, clocks, and limits are intentionally blank because `--power-only` made no follow-up query calls. This is the exact executable mode for the focused transport trace.

## `nvml-power-only-launcher-2026-09-02.csv`

- Captured: 2026-09-02 11:57:38 UTC
- Driver: 610.62
- NVML: 13.610.62
- GPU index: 0
- Samples: 1
- Query scope: dedicated `NvmlPowerOnlyEvidenceProbe` launcher default (device lookup plus `nvmlDeviceGetPowerUsage()` only)
- SHA-256: `7c81622abb640ca82acbaeaab70aa2d394f05a52857db821a34fd9f67c3954d3`

Observed result: the dedicated debugger launcher successfully returned `752673 mW`. This verifies that opening its executable directly, without command-line configuration, produces the intended single-query trace target.
