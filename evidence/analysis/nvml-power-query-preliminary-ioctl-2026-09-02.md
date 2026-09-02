# Preliminary IOCTL in the isolated NVML power-query sequence — 2 September 2026

## Confirmed observations

The read-only `NvmlPowerOnlyEvidenceProbe.exe` trace (PID 13960) stopped at `kernel32!DeviceIoControl` with its main-thread stack returning through internal `nvmlVgpuTypeGetResolution` frames to `nvml!nvmlDeviceGetPowerUsage+0x1C0`.

At that API boundary:

- `dwIoControlCode` (`RDX`) was `0x08DE0004`.
- The input pointer was passed in `R8`; the input size (`R9`) was `0x88` bytes.
- A distinct output pointer was visible in the fifth x64 argument slot (`[RSP+0x28]`).

Running only to the API return instruction produced `RAX = 1` (success). Executing that return resumed in `nvml.dll`, whose next observed work includes `CloseHandle`.

## Interpretation limits

This proves that `0x08DE0004` is a successful preliminary transport request in this direct, one-query power-usage sequence. It does not establish NVIDIA-specific IOCTL semantics, decode the `0x88`-byte input buffer, or demonstrate that the visible output buffer contains the final mW value.

This call is distinct from the previously captured `0x08DE0008` request. The evidence images and hashes are in [`../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-preliminary/`](../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-preliminary/).
