# Direct NVML dispatch capture — 2 September 2026

These screenshots document a read-only dynamic trace of `NvmlEvidenceProbe.exe` in x64dbg. The probe calls the documented `nvmlDeviceGetPowerUsage` API; it contains no configuration, tuning, or write functions.

## Observations

1. The probe explicitly loaded `C:\\Windows\\System32\\nvml.dll`.
2. The debugger stopped at `nvmlInit_v2`, then at the `nvmlDeviceGetPowerUsage` export in that System32 module.
3. That System32 export begins with an indirect `jmp qword ptr ...` dispatch thunk (`system32-export-thunk.png`).
4. Stepping once into that jump entered the actual `nvmlDeviceGetPowerUsage` implementation in the loaded DriverStore `nvml.dll` (`driverstore-nvml-power-handler.png`).

This establishes a runtime delegation path from the System32 export facade to the DriverStore implementation for this process. Addresses are subject to ASLR and are not treated as stable identifiers.

## Still unknown

The capture does **not** establish the interface used by that handler to reach the kernel driver, nor the physical origin of the reported 752,673 mW value. The probe CSV records the driver file paths and SHA-256 values needed to identify the exact binaries without copying proprietary NVIDIA driver files into the repository.

## Files

- `call-stack-nvml-init.png` — stack at the direct `nvmlInit_v2` breakpoint.
- `system32-export-thunk.png` — System32 `nvmlDeviceGetPowerUsage` indirect-jump facade.
- `driverstore-nvml-module-exports.png` — DriverStore module and its exported NVML functions.
- `driverstore-nvml-power-handler.png` — code reached after stepping through the facade's jump.
