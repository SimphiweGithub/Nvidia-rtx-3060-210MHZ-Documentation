# NVML Evidence Probe

This read-only Windows probe calls `nvmlDeviceGetPowerUsage()` directly. It writes a CSV with one sample per line plus an evidence header recording NVML/driver versions and the paths and SHA-256 hashes of every loaded `nvml.dll` module.

It does not set clocks, change driver state, edit the registry, or send a custom NVIDIA control request.

## Build

```powershell
dotnet build .\tools\NvmlEvidenceProbe\NvmlEvidenceProbe.csproj -c Release
```

## Capture

From the repository root, record 60 seconds at the API's one-second averaging interval:

```powershell
dotnet run --project .\tools\NvmlEvidenceProbe\NvmlEvidenceProbe.csproj -c Release -- --samples 60 --interval-ms 1000
```

The default output path is `evidence\runs\nvml-probe-<UTC timestamp>.csv`. Use `--output` to select a specific file and `--gpu` for a GPU index other than `0`.

For a trace that performs only `nvmlDeviceGetHandleByIndex*` and `nvmlDeviceGetPowerUsage`, add `--power-only`. The remaining CSV fields will intentionally be blank:

```powershell
.\tools\NvmlEvidenceProbe\bin\Release\net8.0-windows\NvmlEvidenceProbe.exe --samples 1 --power-only --output .\evidence\runs\nvml-power-only.csv
```

## Next debugger run

Trace this probe, not `nvidia-smi`. Start it under x64dbg, allow `nvml.dll` to load, and then set breakpoints on exports in the exact loaded module(s) reported in the CSV header. Record the module path, breakpoint address, call stack, and exit code. Do not modify code, data buffers, or requests.

For the next transport test, use the `--power-only` command above and set a breakpoint on `kernel32!DeviceIoControl` after the DriverStore `nvmlDeviceGetPowerUsage` breakpoint is reached. If it breaks, record the call stack; it is relevant only if the DriverStore NVML handler remains in that stack.

For x64dbg, [`tools/NvmlPowerOnlyEvidenceProbe`](../NvmlPowerOnlyEvidenceProbe/README.md) avoids the command-line step entirely: open its release executable and it makes exactly one power-only query by default.
