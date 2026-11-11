"""Bounded, read-only repeated NVML RM fallback for kernel-stack observation."""
import ctypes as c
import hashlib
import os
import time

import nvml_runtime_trace as trace

n = c.CDLL('nvml.dll')
if n.nvmlInit_v2() != 0:
    raise RuntimeError('NVML initialization failed')
try:
    h = c.c_void_p()
    if n.nvmlDeviceGetHandleByIndex_v2(0, c.byref(h)) != 0:
        raise RuntimeError('GPU lookup failed')
    path, base = trace.module_for(h.value)
    if hashlib.sha256(path.read_bytes()).hexdigest() != trace.EXPECTED:
        raise RuntimeError('Unexpected NVML build')
    context = trace.read(h.value + 0x28348, 8)
    if trace.read(trace.read(context + 0x160, 8) + 8, 8) - base != 0x101880:
        raise RuntimeError('Unexpected dispatch')
    getter = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p, c.c_uint8,
                         c.POINTER(c.c_uint), c.c_uint)(base + 0x10db90)
    print(f'pid={os.getpid()} tid={c.windll.kernel32.GetCurrentThreadId()}', flush=True)
    deadline = time.monotonic() + 45
    count = 0
    value = c.c_uint()
    while time.monotonic() < deadline:
        status = getter(context, h.value, 0, c.byref(value), 2)
        if status:
            raise RuntimeError(f'Getter returned {status}')
        count += 1
        time.sleep(0.005)
    print(f'count={count} last_mw={value.value}', flush=True)
finally:
    n.nvmlShutdown()
