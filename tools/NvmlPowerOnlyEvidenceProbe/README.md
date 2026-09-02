# NVML Power-Only Evidence Probe

This is the debugger-friendly companion to `NvmlEvidenceProbe`. With no arguments, it performs exactly one device lookup and one `nvmlDeviceGetPowerUsage()` call. It never requests P-state, clock, or power-limit values, and has no state-changing operation.

Use this executable for the x64dbg transport capture:

`tools\NvmlPowerOnlyEvidenceProbe\bin\Release\net8.0-windows\NvmlPowerOnlyEvidenceProbe.exe`

Its source is shared with `NvmlEvidenceProbe`; the executable name selects the one-sample `--power-only` defaults. Command-line options can still override those defaults when needed.
