# DeviceIoControl target candidates — 2 September 2026

## Confirmed call site

The power-only x64dbg trace stopped at `kernel32!DeviceIoControl` and returned to DriverStore `nvml.dll` RVA `0x0016892D`. That is the instruction immediately after the statically mapped import call at RVA `0x00168927`.

For the recorded DriverStore `nvml.dll` (`SHA-256 7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06`):

- The call belongs to the exception-table function range `0x001687F0–0x00168972`.
- That function directly imports `DeviceIoControl` at `0x00168927` and closes handles at `0x00168934` and `0x00168951`.
- Its direct callee at `0x00169000–0x001690B3` imports `CreateFileA` at `0x00169084`.
- The same DLL contains the literal device path `\\.\NvAdminDevice` at raw file offset `0x00296448`, mapping to RVA `0x00297848`.
- That exact helper loads the literal into `RCX` with a RIP-relative `LEA` at `0x00169062`, then reaches the `CreateFileA` call at `0x00169084`. On x64 Windows, `RCX` is the first argument register.

The static maps are preserved in [`nvml-deviceiocontrol-callsite-2026-09-02.txt`](nvml-deviceiocontrol-callsite-2026-09-02.txt) and [`nvml-nvadmindevice-open-helper-2026-09-02.txt`](nvml-nvadmindevice-open-helper-2026-09-02.txt). The bounded string-xref scan is [`nvml-nvadmindevice-xrefs-2026-09-02.txt`](nvml-nvadmindevice-xrefs-2026-09-02.txt).

A separate xref at `0x0016999F` is in another function that also calls `CreateFileA` and `DeviceIoControl`; its map is [`nvml-nvadmindevice-secondary-transport-2026-09-02.txt`](nvml-nvadmindevice-secondary-transport-2026-09-02.txt). It confirms that the DLL contains more than one `NvAdminDevice` transport helper, but it is not the return site observed in the power-only trace.

## Current interpretation

The evidence now statically identifies `\\.\NvAdminDevice` as the filename passed by the helper called from the observed `DeviceIoControl` function. The parent function's direct call to that helper is at `0x001688E8`; its `DeviceIoControl` call is at `0x00168927`.

This still does not prove that the helper ran in the specific power-only trace or that its returned handle was the particular handle passed to the captured `DeviceIoControl` invocation. The capture did not stop at `CreateFileA` to read its live argument or return value, so the runtime linkage remains unconfirmed.

## Observed IOCTL encoding (not vendor semantics)

The observed IOCTL value `0x08DE0008` has the standard Windows `CTL_CODE` bit layout:

- Device type: `0x08DE`
- Function: `0x002`
- Method: `0` (`METHOD_BUFFERED`)
- Access: `0` (`FILE_ANY_ACCESS`)

This mechanical decomposition does **not** identify NVIDIA's operation, establish the input-buffer schema, or show that the candidate device path is the handle used by this call.

## Focused validation

On a repeat run of the one-query probe, set `kernel32!CreateFileA` after the DriverStore `nvmlDeviceGetPowerUsage` breakpoint. The target is confirmed only if the CPU view shows the `CreateFileA` filename pointer resolving to `\\.\NvAdminDevice` and the stack still includes `nvmlDeviceGetPowerUsage`. The full, read-only target/handle/payload capture procedure is [`next-read-only-x64dbg-capture-2026-09-02.md`](next-read-only-x64dbg-capture-2026-09-02.md).
