"""Capture GPU-Z voltage and NVML clock reasons without changing GPU state.

Requires GPU-Z to be running with its shared-memory sensor block available.
Never starts or stops a workload, alters settings, or guarantees protection.
"""
import argparse
import csv
import ctypes as c
import math
import struct
import subprocess
import time
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=10, choices=range(1, 61))
args = parser.parse_args()
kernel = c.WinDLL('kernel32', use_last_error=True)
kernel.OpenFileMappingW.argtypes = [c.c_uint32, c.c_int, c.c_wchar_p]
kernel.OpenFileMappingW.restype = c.c_void_p
kernel.MapViewOfFile.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32, c.c_size_t]
kernel.MapViewOfFile.restype = c.c_void_p
kernel.UnmapViewOfFile.argtypes = [c.c_void_p]
kernel.CloseHandle.argtypes = [c.c_void_p]
size = 12 + 128*1024 + 128*540
handle = kernel.OpenFileMappingW(4, 0, 'GPUZShMem')
if not handle:
    raise OSError(c.get_last_error(), 'GPU-Z shared memory is unavailable')
view = kernel.MapViewOfFile(handle, 4, 0, 0, size)
if not view:
    error = c.get_last_error()
    kernel.CloseHandle(handle)
    raise OSError(error, 'Cannot map GPU-Z sensors read-only')

names = ('GPU Clock', 'GPU Voltage', 'GPU Temperature', 'GPU Load', 'PerfCap Reason')
target = Path(__file__).resolve().parent.parent / 'evidence' / 'runs' / (
    'gpuz-voltage-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.csv')
try:
    with target.open('x', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=['timestamp', 'gpuz_last_update', *names, 'nvml'])
        writer.writeheader()
        for _ in range(args.seconds):
            block = c.string_at(view, size)
            version, busy, last_update = struct.unpack_from('<III', block)
            if version != 1 or busy:
                raise RuntimeError(f'Unexpected or busy GPU-Z snapshot: version={version}, busy={busy}')
            row = {'timestamp': datetime.now().astimezone().isoformat(), 'gpuz_last_update': last_update}
            for i in range(128):
                offset = 12 + 128*1024 + i*540
                name = block[offset:offset+512].decode('utf-16le', errors='replace').split('\0')[0]
                if name in names:
                    value = struct.unpack_from('<d', block, offset+532)[0]
                    if not math.isfinite(value):
                        raise RuntimeError(f'Non-finite GPU-Z sensor: {name}')
                    row[name] = value
            if any(name not in row for name in names):
                raise RuntimeError('Required GPU-Z sensors are missing')
            result = subprocess.run(['nvidia-smi', '--query-gpu=clocks.current.graphics,temperature.gpu,utilization.gpu,clocks_event_reasons.active',
                                     '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if result.returncode:
                raise RuntimeError('NVML query failed: ' + result.stderr.strip())
            row['nvml'] = result.stdout.strip()
            writer.writerow(row)
            output.flush()
            print(row, flush=True)
            time.sleep(1)
finally:
    kernel.UnmapViewOfFile(view)
    kernel.CloseHandle(handle)
print('Capture:', target)
