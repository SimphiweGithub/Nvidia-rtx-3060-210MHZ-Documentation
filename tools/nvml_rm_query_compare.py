"""Compare NVML's public power reading with its build-specific RM-query fallback.

Read-only diagnostic for one exact NVML binary. This calls an undocumented,
internal getter through the same ABI observed in that build; it may be unsupported
by NVIDIA. It never invokes a setter or changes the monitoring page. A result
is still driver telemetry, not an independent physical power measurement.
"""
import ctypes as c
import hashlib
import nvml_runtime_trace as trace


def main():
    nvml = c.CDLL("nvml.dll")
    if nvml.nvmlInit_v2() != 0:
        raise RuntimeError("NVML initialization failed")
    try:
        nvml.nvmlDeviceGetHandleByIndex_v2.argtypes = [c.c_uint, c.POINTER(c.c_void_p)]
        nvml.nvmlDeviceGetPowerUsage.argtypes = [c.c_void_p, c.POINTER(c.c_uint)]
        dev = c.c_void_p()
        if nvml.nvmlDeviceGetHandleByIndex_v2(0, c.byref(dev)) != 0:
            raise RuntimeError("GPU lookup failed")
        public = c.c_uint()
        if nvml.nvmlDeviceGetPowerUsage(dev, c.byref(public)) != 0:
            raise RuntimeError("NVML power query failed")
        path, base = trace.module_for(dev.value)
        if hashlib.sha256(path.read_bytes()).hexdigest() != trace.EXPECTED:
            raise RuntimeError("Unexpected NVML build; refusing internal call")
        context = trace.read(dev.value + 0x28348, 8)
        dispatch = trace.read(trace.read(context + 0x160, 8) + 8, 8)
        if dispatch - base != 0x101880:
            raise RuntimeError("Unexpected dispatch; refusing internal call")
        getter = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p, c.c_uint8,
                             c.POINTER(c.c_uint), c.c_uint)(base + 0x10db90)
        value = c.c_uint()
        status = getter(context, dev.value, 0, c.byref(value), 0)
        print(f"public_mw={public.value} fallback_status={status} fallback_mw={value.value}")
        if status != 0:
            raise RuntimeError("Internal query returned an error")
    finally:
        nvml.nvmlShutdown()


if __name__ == "__main__":
    main()
