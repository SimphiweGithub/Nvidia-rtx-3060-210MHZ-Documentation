# Direct power-query transport capture — 2 September 2026

## Scope

The target was `NvmlPowerOnlyEvidenceProbe.exe`, a read-only launcher which performs exactly one device lookup and one `nvmlDeviceGetPowerUsage()` call. It makes no P-state, clock, power-limit, configuration, or write query.

The recorded DriverStore module was:

- `C:\\Windows\\System32\\DriverStore\\FileRepository\\nvdmi.inf_amd64_38c6812b57a66ef3\\nvml.dll`
- SHA-256: `7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06`

## Confirmed observations

1. x64dbg stopped at the DriverStore `nvmlDeviceGetPowerUsage` handler.
2. A `kernel32.dll!DeviceIoControl` breakpoint was set while that handler was paused.
3. Continuing execution stopped at `kernel32!DeviceIoControl`.
4. The main-thread call stack contains, in order, `kernel32!DeviceIoControl`, five frames labelled `nvmlVgpuTypeGetResolution`, and `nvmlDeviceGetPowerUsage+0x268`.
5. At the API boundary, the CPU view shows `RDX = 0x08DE0008` (the `dwIoControlCode` argument), `R8 = 0x000000AFABF7DB20` (the input-buffer pointer), and `R9 = 0x6C` (the input-buffer length argument under the Windows x64 calling convention).
6. The 108-byte buffer was followed read-only in x64dbg's Dump view. It visibly begins with zero fields, `0x60`, and the ASCII sequence `ADVN`; no proprietary field interpretation is asserted.
7. Resuming from the captured call allowed the dedicated probe to exit with code `0`. No second `DeviceIoControl` breakpoint fired before that exit.

This confirms that this isolated direct power-usage query reaches the normal Windows `DeviceIoControl` transport through the DriverStore NVML implementation.

## Limits

The screenshots do not decode the IOCTL buffer, identify the device object/driver below the handle, or establish the physical origin of the reported 752,673 mW value. No instruction, memory, buffer, or driver state was changed during capture.

## Files and SHA-256

- `deviceiocontrol-cpu.png` — `7d1b6f70ed51d5b79d8d109da683e0ffc4781519420d9a5bab92903845e3ed9f`
- `deviceiocontrol-call-stack.png` — `25a1762f177d3265b1b8c5cac40eb137b8a98960de3706e2e3010d18cc8a1d70`
- `deviceiocontrol-input-buffer.png` — `ec2bcfeb6dfe2a7b523bbce1255aa2206efb71bb23e06a719e3bf9fb722feba2`
- `deviceiocontrol-run-completed.png` — `8e97ecec9001828e37a066ed218879a719d9370b350bdbc99ff4bbf2af61615f`
