# Next read-only x64dbg capture — 2 September 2026

## Purpose

Validate whether the one-query direct `nvmlDeviceGetPowerUsage` run opens `\\.\NvAdminDevice`, and preserve the request/result boundary for the already-confirmed `DeviceIoControl` call.

The steps below only pause, inspect, and resume the purpose-built one-query probe. Do not edit registers, patch code, modify breakpoints in driver memory, or send a request outside the probe.

## Setup

1. Start `NvmlPowerOnlyEvidenceProbe.exe` in x64dbg.
2. When the DriverStore `nvml.dll!nvmlDeviceGetPowerUsage` breakpoint stops, enter these two x64dbg commands:

   ```text
   bp kernel32.dll:CreateFileA
   bp kernel32.dll:DeviceIoControl
   ```

3. Press `F9`.

## Capture A — filename and handle

If `CreateFileA` stops first:

1. In the CPU view, inspect `RCX`. On x64 Windows this is `CreateFileA`'s filename pointer. It should resolve to `\\.\NvAdminDevice` if the static route is active.
2. Capture the **CPU** and **Call Stack** views. The call stack must still contain `nvmlDeviceGetPowerUsage` for this to count as power-query evidence.
3. Press `F8` once to return from `CreateFileA`; record or capture the `RAX` value. This is the returned handle for the subsequent comparison.
4. Press `F9` to the `DeviceIoControl` breakpoint.

If `DeviceIoControl` stops before `CreateFileA`, record that ordering and capture its CPU and Call Stack views. It can mean that the handle was cached or that a different path was selected; it does not prove the static route executed in that run.

## Capture B — IOCTL boundary

At `DeviceIoControl`, record the standard x64 arguments:

| Location | API field |
|---|---|
| `RCX` | device handle |
| `RDX` | `dwIoControlCode` |
| `R8` | input-buffer pointer |
| `R9` | input-buffer length |
| `[RSP+0x28]` | output-buffer pointer |
| `[RSP+0x30]` | output-buffer length |
| `[RSP+0x38]` | bytes-returned pointer |
| `[RSP+0x40]` | overlapped pointer |

Capture the CPU and Call Stack views. If Capture A produced a handle, compare its post-`CreateFileA` `RAX` with the `DeviceIoControl` `RCX` value. Equal values establish the live handle linkage for this run.

For the captured IOCTL, the prior run observed `RDX = 0x08DE0008`, `R8` pointing to a `0x6C`-byte input buffer, and a stack path back to `nvmlDeviceGetPowerUsage`.

## Optional read-only result capture

If an output pointer and a nonzero output length are present, note the pointer and press `F8` once to step over `DeviceIoControl`. Then inspect that same output pointer in Dump and capture it, together with the `RAX` API return value and the value at the bytes-returned pointer. This captures a result buffer; it does not decode vendor fields or change program state.

After screenshots are taken, press `F9` and let the dedicated probe exit normally. Preserve the CPU, Call Stack, input Dump, and (if present) output Dump screenshots as separate evidence.
