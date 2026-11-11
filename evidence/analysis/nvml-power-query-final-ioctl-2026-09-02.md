# Final IOCTL in the isolated NVML power-query sequence — 2 September 2026

## Confirmed observations

In the read-only `NvmlPowerOnlyEvidenceProbe.exe` trace (PID 13960), a conditional `kernel32!DeviceIoControl` breakpoint for `RDX == 0x08DE0008` stopped on the main thread. Its stack reached `nvml!nvmlDeviceGetPowerUsage+0x268` through internal `nvmlVgpuTypeGetResolution` frames.

At the API boundary, the x64 arguments were:

- `RCX`: handle value `0x360`.
- `RDX`: IOCTL `0x08DE0008`.
- `R8`: input-buffer pointer `0x000000E30579DDF0`.
- `R9`: input-buffer length `0x6C` (108 bytes).
- `[RSP+0x28]`: distinct output-buffer pointer `0x000000E30579DE60`.

The screenshot labelled input-buffer instead shows `0x000000E30579DBB0`, not the address in `R8`; it is not a complete capture of the actual input. The output buffer was viewed before and after the call without modifying process state. Running until the `DeviceIoControl` return produced `RAX = 1`, the Windows success result.

On re-review of the entry screenshot, `[RSP+0x30]` has low 32 bits `0x6C`, indicating a 108-byte output length, and `[RSP+0x38]` points to `0x000000E30579DED0`. The post-return dump at that address begins `01 00 00 00`, consistent with a reported byte count of 1. This interpretation is limited to the screenshot and should be repeated in a fresh capture.

## What this establishes

This is reproducible dynamic evidence that the direct NVML power-usage path issues the `0x08DE0008` request and that Windows reported that request successful. The standard Windows encoding mechanically decomposes the value as device type `0x08DE`, function `0x002`, `METHOD_BUFFERED`, and `FILE_ANY_ACCESS`.

## Interpretation limits

The output buffer had pre-existing scratch data before the call and its displayed bytes **changed** after return. The reported byte count appears to be 1, so the meaning and validity of the rest of the changed buffer must not be assumed. Neither those changes nor the IOCTL number identify NVIDIA-specific semantics, the milliwatt field, or the physical sensor/firmware source. The input-buffer image is misaddressed; the actual 108-byte input was not fully preserved in that image.

The final capture is preserved in [`../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-final/`](../screenshots/2026-09-02-x64dbg-power-only-deviceiocontrol-final/). The separate successful `0x08DE0004` setup request is documented in [`nvml-power-query-preliminary-ioctl-2026-09-02.md`](nvml-power-query-preliminary-ioctl-2026-09-02.md).
