"""Read NVAPI's documented P-state table; no settings or clocks are changed."""
import ctypes as c
import json

u32 = c.c_uint32
i32 = c.c_int32

class Delta(c.Structure):
    _fields_ = [('value', i32), ('minimum', i32), ('maximum', i32)]

class Clock(c.Structure):
    # The 5-dword union is large enough for either single or range form.
    _fields_ = [('domain', u32), ('type', u32), ('flags', u32),
                ('delta', Delta), ('data', u32 * 5)]

class Voltage(c.Structure):
    _fields_ = [('domain', u32), ('flags', u32), ('voltage_uv', u32), ('delta', Delta)]

class Pstate(c.Structure):
    _fields_ = [('id', u32), ('flags', u32), ('clocks', Clock * 8), ('voltages', Voltage * 4)]

class Info(c.Structure):
    _fields_ = [('version', u32), ('flags', u32), ('num_pstates', u32),
                ('num_clocks', u32), ('num_voltages', u32), ('pstates', Pstate * 16),
                ('overvoltage_count', u32), ('overvoltage', Voltage * 4)]

api = c.WinDLL('nvapi64.dll')
query = api.nvapi_QueryInterface
query.argtypes = [u32]
query.restype = c.c_void_p

def fn(identifier, *args):
    address = query(identifier)
    if not address:
        raise RuntimeError('NVAPI interface unavailable: %08x' % identifier)
    return c.WINFUNCTYPE(i32, *args)(address)

assert fn(0x0150e828)() == 0
handles = (c.c_void_p * 64)()
count = u32()
assert fn(0xe5ac921f, c.POINTER(c.c_void_p), c.POINTER(u32))(handles, c.byref(count)) == 0
assert count.value <= 64
get_info = fn(0x6ff81213, c.c_void_p, c.POINTER(Info))
get_current = fn(0x927da4f6, c.c_void_p, c.POINTER(u32))
for index in range(count.value):
    info = Info()
    info.version = c.sizeof(Info) | (3 << 16)
    result = get_info(handles[index], c.byref(info))
    current = u32()
    current_status = get_current(handles[index], c.byref(current))
    out = {'gpu_index': index, 'status': result, 'current_status': current_status,
           'current_pstate': current.value if current_status == 0 else None,
           'num_pstates': info.num_pstates, 'num_clocks': info.num_clocks, 'pstates': []}
    if result == 0 and info.num_pstates <= 16 and info.num_clocks <= 8:
        for state in info.pstates[:info.num_pstates]:
            clocks = []
            for clock in state.clocks[:info.num_clocks]:
                clocks.append({'domain': clock.domain, 'type': clock.type,
                               'delta_khz': clock.delta.value, 'data': list(clock.data)})
            out['pstates'].append({'id': state.id, 'clocks': clocks})
    print(json.dumps(out))
