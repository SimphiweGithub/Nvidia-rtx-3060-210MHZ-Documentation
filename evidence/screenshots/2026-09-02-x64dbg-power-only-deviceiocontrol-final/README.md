# Final `DeviceIoControl` capture — isolated NVML power query

These screenshots document a read-only x64dbg capture from `NvmlPowerOnlyEvidenceProbe.exe` (PID 13960) on 2 September 2026.

| File | SHA-256 | Purpose |
| --- | --- | --- |
| `deviceiocontrol-08de0008-call-stack.png` | `6e4582d621dee629519cfa43338408ac99afae83a197f25df488d3dc58e7d1ea` | Connects `kernel32!DeviceIoControl` to `nvmlDeviceGetPowerUsage+0x268`. |
| `deviceiocontrol-08de0008-cpu.png` | `be2934ec8204ff97294decf15e93106569dadd8096612f0719df794be148f9f0` | Records `RDX=0x08DE0008`, `R8`, `R9=0x6C`, and the output pointer. |
| `deviceiocontrol-08de0008-input-buffer.png` | `5990d462dfd4a36493187f209b304abfc98f0550a9f4b63a9c3e9efc03098364` | Read-only input-buffer view at `R8`. |
| `deviceiocontrol-08de0008-output-buffer-before.png` | `c02f7622de6b77aa18dc9e4f727542cea609ceb6e4a59c8ab45e49bbc5558093` | Read-only output-buffer view before the call returns. |
| `deviceiocontrol-08de0008-returned-success-output-buffer.png` | `c01c01852480abffb3e1a05e71f3c484217240ed256e9bd4c9cb976605526046` | Shows `RAX=1` after return and the same output-buffer view. |

The input and output pointers are process-local addresses, not durable identifiers. The screenshots establish call path, standard IOCTL fields, and success status; they do not decode NVIDIA's proprietary request/result schema.
