# Installed NVML power-query dispatch — 7 November 2026

## Static observation

Disassembly with Capstone 5.0.9 of the installed DriverStore `nvml.dll`, SHA-256 `7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06`, was scoped to the previously identified `nvmlDeviceGetPowerUsage` function range RVA `0x47250–0x474BF`. RVAs below are relative to this particular binary and must not be assumed for another build.

On the successful branch, the function preserves the caller's output pointer in `RSI` and device argument in `RBX`. It then follows several runtime pointers and dispatches:

```text
RVA       instruction
00047474  mov rcx, qword ptr [rbx + 0x28348]
00047484  mov rax, qword ptr [rcx + 0x160]
00047494  mov rax, qword ptr [rax + 8]
000474A1  mov r9, rsi
000474A4  mov dword ptr [rsp + 0x20], 0
000474AC  xor r8d, r8d
000474AF  mov rdx, rbx
000474B2  call qword ptr [rip + 0x233198]
```

Each pointer is checked for zero before the next dereference. The `call` uses the qword at RVA `0x27A650`, whose on-disk value points to RVA `0x278770`; that code is `jmp rax`. This is an indirect dispatch trampoline, not a statically identified Windows import or proof of the runtime destination. It explains why the prior direct-call mapper did not resolve the power-producing callee.

## Live pointer inspection and further static analysis

In a fresh Python process, after a successful NVML power query returned `752672 mW`, a read-only `ReadProcessMemory` traversal using the same device handle found the first dispatch pointer at DriverStore NVML RVA `0x101880`. The same device's dispatch table at `[context + 0x120]`, entry `+0x60`, pointed to DriverStore NVML RVA `0xEC230`. These are observations of pointer values after the query, not a breakpoint capture proving that either call executed during it.

Disassembly of `0x101880` shows a conditional indirect call through that second dispatch entry, with a fallback direct call at `0x10DB90`. In the inspected process the relevant global at RVA `0x306000` was `1`; the device's cache initialization field at `+0x714` was `1` with status `0` at `+0x71C`, and other branch-related fields were consistent with this route being a candidate. The helper still has additional checks, so this snapshot alone does not prove branch selection.

The second target at `0xEC230` invokes a helper with poll mask `0x8`. Its subsequent code requests a 24-byte record at offset `0x988`, copies the first power value from eight bytes into that record to the output, and has a fallback request at offset `0x9A0`. Its helper at `0xECEF0` obtains a page pointer from `[device + 0x284B8]` and adds the requested offset. The snapshot showed the poll mask at `[device + 0x8B568]` was `0x8`, the page cache initialized flag at `+0x284C0` was `1`, and cache status at `+0x284C8` was `0`.

The live pointer at `[device + 0x284B8]` resolved to the same layout seen in the prior scan: at `+0x990` was `752672`, at `+0x9A8` was `752673`, and at `+0x904` was the 115000 mW enforced limit. This connects the previously anonymous page candidate to the data structure used by the installed binary's shared-data reader, and substantially narrows where the NVML result can originate. It remains a monitoring route, not proof of the source used by the power-control loop. Snapshot reads are process-local and do not alter data.

## Next evidence needed

In a fresh isolated debugger run, observe whether `0xEC230` and the `0x988` shared-data read execute in the power query, or use equivalent non-mutating tracing. Then investigate the page's kernel/firmware producer and whether its source is also consumed by the power-control loop. Do not patch the trampoline or substitute power values: the control-policy relationship remains unknown. The offsets are build-specific leads, not safe places to apply a fix.
