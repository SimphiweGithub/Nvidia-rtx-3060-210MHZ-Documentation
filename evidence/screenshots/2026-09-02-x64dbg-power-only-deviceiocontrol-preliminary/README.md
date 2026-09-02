# Preliminary power-query DeviceIoControl capture — 2 September 2026

These are read-only x64dbg captures from `NvmlPowerOnlyEvidenceProbe.exe` (PID 13960).

## Observed facts

- x64dbg stopped at `kernel32!DeviceIoControl`.
- The CPU capture shows `RDX = 0x08DE0004`, `R8` as the input-buffer pointer, and `R9 = 0x88` at the API boundary.
- The main-thread call stack reaches `nvml!nvmlDeviceGetPowerUsage+0x1C0` through internal `nvmlVgpuTypeGetResolution` frames.
- The input-buffer Dump is captured before the call returns. The visible stack argument at `[RSP+0x28]` is a distinct output-buffer pointer.
- `DeviceIoControl` reached its return instruction with `RAX = 1`; after that return, execution is back in `nvml.dll` and is about to call `CloseHandle`.

This is therefore a second observed IOCTL in the isolated direct-power-query sequence, distinct from the previous `0x08DE0008` capture. The screenshots alone do not establish the input/output buffer schema or assign NVIDIA-specific meaning to either code.

## Files and SHA-256

| File | SHA-256 |
|---|---|
| `deviceiocontrol-08de0004-cpu.png` | `df9be5a20609acefa6e5437ca1b378eea5ff30523343420fdf0d3d342e9e2c6d` |
| `deviceiocontrol-08de0004-call-stack.png` | `75bd37866d2ee697bc8d8e26d9efea26ed47dc24ba7a346dfcb0798dee5eb925` |
| `deviceiocontrol-08de0004-input-buffer.png` | `9181af39232ffae9cea66ba963c419e65c7560c31265cd04e7da37d7b0dd5039` |
| `deviceiocontrol-08de0004-output-buffer-before.png` | `18bbbd5153d4d639d9045debaac52055755013c71beb9852b478e1cc6c290e95` |
| `deviceiocontrol-08de0004-return-boundary.png` | `6df0a79e1fee06c2dae8291c7ffeccc0a4f285103eca882845769ba384209565` |
| `deviceiocontrol-08de0004-returned-to-nvml.png` | `196220770802b78ff16d1b519820a28830b508667fc7cc230679f64df860bdb5` |
