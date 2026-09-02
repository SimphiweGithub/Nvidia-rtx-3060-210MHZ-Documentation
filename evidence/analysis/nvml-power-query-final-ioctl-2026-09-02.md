# Final IOCTL in the isolated NVML power-query sequence — 2 September 2026

## Confirmed observations

In the read-only `NvmlPowerOnlyEvidenceProbe.exe` trace (PID 13960), a conditional `kernel32!DeviceIoControl` breakpoint for `RDX == 0x08DE0008` stopped on the main thread. Its stack reached `nvml!nvmlDeviceGetPowerUsage+0x268` through internal `nvmlVgpuTypeGetResolution` frames.

At the API boundary, the x64 arguments were:

- `RCX`: handle value `0x360`.
- `RDX`: IOCTL `0x08DE0008`.
- `R8`: input-buffer pointer `0x000000E30579DBB0`.
- `R9`: input-buffer length `0x6C` (108 bytes).
- `[RSP+0x28]`: distinct output-buffer pointer `0x000000E30579DE60`.

The input and pre-call output-buffer views were captured without modifying process state. Running only until the `DeviceIoControl` return and executing that return produced `RAX = 1`, the Windows success result. The same output-buffer view was captured immediately afterwards.

## What this establishes

This is reproducible dynamic evidence that the direct NVML power-usage path issues the `0x08DE0008` request and that Windows reported that request successful. The standard Windows encoding mechanically decomposes the value as device type `0x08DE`, function `0x002`, `METHOD_BUFFERED`, and `FILE_ANY_ACCESS`.

## Interpretation limits

The output buffer had pre-existing scratch data before the call, and the displayed bytes in the post-return view are visually unchanged over the captured range. That does **not** prove that the request returned no data, nor does it identify the final milliwatt field: the output-buffer length, bytes-returned pointer, and proprietary structure schema were not decoded in this capture. The IOCTL number and standard `CTL_CODE` fields likewise do not identify NVIDIA-specific semantics or the physical sensor/firmware source.

The final capture is preserved in [`../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-final/`](../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-final/). The separate successful `0x08DE0004` setup request is documented in [`nvml-power-query-preliminary-ioctl-2026-09-02.md`](nvml-power-query-preliminary-ioctl-2026-09-02.md).
