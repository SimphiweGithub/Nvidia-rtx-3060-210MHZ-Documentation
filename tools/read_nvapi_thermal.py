"""Read documented NVAPI thermal sensors; no device settings are changed."""
import ctypes as c
import json

api = c.WinDLL('nvapi64.dll')
query = api.nvapi_QueryInterface
query.argtypes = [c.c_uint32]
query.restype = c.c_void_p

def fn(identifier, *argtypes):
    address = query(identifier)
    if not address:
        raise RuntimeError('NVAPI interface missing: %08x' % identifier)
    return c.WINFUNCTYPE(c.c_int32, *argtypes)(address)

class Sensor(c.Structure):
    _fields_ = [('controller', c.c_int32), ('minimum', c.c_int32),
                ('maximum', c.c_int32), ('current', c.c_int32), ('target', c.c_int32)]

class Thermal(c.Structure):
    _fields_ = [('version', c.c_uint32), ('count', c.c_uint32), ('sensors', Sensor * 3)]

assert fn(0x0150e828)() == 0
handles = (c.c_void_p * 64)()
count = c.c_uint32()
status = fn(0xe5ac921f, c.POINTER(c.c_void_p), c.POINTER(c.c_uint32))(handles, c.byref(count))
if status != 0 or count.value > 64:
    raise RuntimeError('GPU enumeration failed: %d, count %d' % (status, count.value))
get_thermal = fn(0xe3640a56, c.c_void_p, c.c_uint32, c.POINTER(Thermal))
get_decrease = fn(0x7f7f4600, c.c_void_p, c.POINTER(c.c_uint32))
for index in range(count.value):
    data = Thermal()
    data.version = c.sizeof(Thermal) | (2 << 16)
    result = get_thermal(handles[index], 15, c.byref(data))
    sensors = []
    if result == 0:
        for sensor in data.sensors[:min(data.count, 3)]:
            sensors.append({name: getattr(sensor, name) for name in ('controller', 'minimum', 'maximum', 'current', 'target')})
    decrease = c.c_uint32()
    decrease_status = get_decrease(handles[index], c.byref(decrease))
    print(json.dumps({'gpu_index': index, 'status': result, 'reported_count': data.count, 'sensors': sensors,
                      'perf_decrease_status': decrease_status, 'perf_decrease_mask': hex(decrease.value)}))
