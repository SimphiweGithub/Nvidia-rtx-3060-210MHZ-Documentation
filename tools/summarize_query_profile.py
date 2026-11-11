"""Summarize a filtered xperf text dump using explicitly supplied module bases."""
import argparse
from collections import defaultdict
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('dump', type=Path)
parser.add_argument('--driver-base', type=lambda x: int(x, 0), required=True)
parser.add_argument('--nvml-base', type=lambda x: int(x, 0), required=True)
args = parser.parse_args()
groups = defaultdict(set)
pattern = re.compile(r'^\s*(?:SampledProfile|Stack),\s*(\d+),.*?(nvlddmkm\.sys|nvml\.dll)!0x([0-9a-f]+)', re.I)
for line in args.dump.read_text(errors='replace').splitlines():
    match = pattern.search(line)
    if not match:
        continue
    module = match[2].lower()
    base = args.driver_base if module == 'nvlddmkm.sys' else args.nvml_base
    rva = int(match[3], 16) - base
    if 0 <= rva < 0x10000000:
        groups[match[1]].add((module, rva))
markers = [('nvml.dll', 0x10c82f), ('nvlddmkm.sys', 0x4e3a9e),
           ('nvlddmkm.sys', 0x4e36d7), ('nvlddmkm.sys', 0x5a42cf),
           ('nvlddmkm.sys', 0x5a2f0d), ('nvlddmkm.sys', 0x3585f9)]
print(f'sample_timestamps={len(groups)}')
for end in range(1, len(markers) + 1):
    required = set(markers[:end])
    print(' & '.join(f'{module}+{rva:#x}' for module, rva in markers[:end]),
          sum(required <= frames for frames in groups.values()))
