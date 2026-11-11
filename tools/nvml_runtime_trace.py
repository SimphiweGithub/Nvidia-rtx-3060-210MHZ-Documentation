"""Read-only inspection of one known NVML build's power-dispatch pointers.

This inspects only the current Python process and never calls a driver setter.
Offsets are specific to the hash below; it refuses to dereference them on a
different build. It is a diagnostic snapshot, not an intervention.
"""
import ctypes as c
import hashlib
from ctypes import wintypes as w
from pathlib import Path

EXPECTED = "7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06"
k = c.WinDLL("kernel32", use_last_error=True)
k.GetCurrentProcess.restype = c.c_void_p
k.ReadProcessMemory.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
k.ReadProcessMemory.restype = w.BOOL
k.GetModuleHandleExW.argtypes = [w.DWORD, c.c_void_p, c.POINTER(c.c_void_p)]
k.GetModuleHandleExW.restype = w.BOOL
k.GetModuleFileNameW.argtypes = [c.c_void_p, w.LPWSTR, w.DWORD]
k.GetModuleFileNameW.restype = w.DWORD


def read(addr, size):
    value = c.create_string_buffer(size)
    count = c.c_size_t()
    if not k.ReadProcessMemory(k.GetCurrentProcess(), c.c_void_p(addr), value, size, c.byref(count)) or count.value != size:
        raise OSError(f"Unable to read {size} bytes at {addr:#x}")
    return int.from_bytes(value.raw, "little")


def module_for(addr):
    handle = c.c_void_p()
    # FROM_ADDRESS | UNCHANGED_REFCOUNT
    if not k.GetModuleHandleExW(6, c.c_void_p(addr), c.byref(handle)):
        raise OSError("Unable to resolve loaded NVML module")
    name = c.create_unicode_buffer(32768)
    if not k.GetModuleFileNameW(handle, name, len(name)):
        raise OSError("Unable to resolve loaded module path")
    return Path(name.value), handle.value


def main():
    n = c.CDLL("nvml.dll")
    if n.nvmlInit_v2() != 0:
        raise RuntimeError("NVML initialization failed")
    try:
        device = c.c_void_p()
        if n.nvmlDeviceGetHandleByIndex_v2(0, c.byref(device)) != 0:
            raise RuntimeError("NVML device lookup failed")
        n.nvmlDeviceGetPowerUsage.argtypes = [c.c_void_p, c.POINTER(c.c_uint)]
        power = c.c_uint()
        status = n.nvmlDeviceGetPowerUsage(device, c.byref(power))
        if status != 0:
            raise RuntimeError(f"NVML power query failed: {status}")

        # The returned device handle is inside the DriverStore module in this build.
        path, base = module_for(device.value)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"module={path}\nsha256={digest}\nnvml_power_mw={power.value}")
        if digest != EXPECTED:
            raise RuntimeError("Unrecognized NVML build; refusing build-specific offsets")
        dev = device.value
        api = read(dev + 0x28348, 8)
        first = read(read(api + 0x160, 8) + 8, 8)
        second = read(read(api + 0x120, 8) + 0x60, 8)
        for label, address in (("dispatch_1", first), ("dispatch_2", second)):
            target_path, target_base = module_for(address)
            if target_path != path:
                raise RuntimeError(f"{label} points outside the expected module")
            print(f"{label}_rva={address - target_base:#x}")
        if read(dev + 0x284C0, 4) != 1 or read(dev + 0x284C8, 4) != 0:
            raise RuntimeError("Shared-data cache is not initialized successfully")
        page = read(dev + 0x284B8, 8)
        print(f"poll_mask={read(dev + 0x8B568, 8):#x}")
        print(f"candidate_average_mw={read(page + 0x990, 4)}")
        print(f"candidate_instant_mw={read(page + 0x9A8, 4)}")
        print(f"candidate_enforced_limit_mw={read(page + 0x904, 4)}")
    finally:
        n.nvmlShutdown()


if __name__ == "__main__":
    main()
