"""Create a class-preserving current-slope hypothesis offline only."""
import hashlib
import json
import struct
from pathlib import Path
from nvidia_vbios.rom.tables import checksum_tail

root=Path(__file__).resolve().parent.parent
source=root/'evidence/runs/OFFLINE-ONLY-6100mW-candidate-20261109.bin'
target=root/'evidence/runs/OFFLINE-ONLY-current-slope-20261110.bin'
manifest=target.with_suffix('.json')
if target.exists() or manifest.exists(): raise FileExistsError('Refusing to overwrite offline files')
raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
assert digest=='1e08ed1984f1a3c726d6c1d17b3dad30c409095f4853e6c0de1c80421758e57c'
base,begin,end=563230,180224,609792
assert tuple(raw[base:base+6])==(32,6,26,32,46,32)
assert sum(raw[begin:end])%256==0 and checksum_tail(raw,end,'ampere') is not None
out=bytearray(raw); changes=[]
for channel in (3,5):
    rec=base+6+26*channel
    assert raw[rec]==5
    off=rec+6
    old=struct.unpack_from('<I',raw,off)[0]
    assert old==4096
    struct.pack_into('<I',out,off,32)
    changes.append({'channel':channel,'offset':off,'before':old,'after':32})
old_sum=out[end-1];out[end-1]=(old_sum-sum(out[begin:end]))&255
assert sum(out[begin:end])%256==0
result={'status':'OFFLINE ONLY; not tested or staged',
 'source_sha256':digest,'output_sha256':hashlib.sha256(out).hexdigest(),'changes':changes,
 'checksum_offset':end-1,'checksum_before':old_sum,'checksum_after':out[end-1],
 'hypothesis':'For each channel, 32/4096 is one 128th of its original candidate current-correction slope.',
 'limitations':['Field meaning inferred from older Linux format and live correlation; Windows and PMU semantics not proved',
                'Behavior of power, current and voltage outputs under this edit is unknown',
                'Spoofed values cannot establish real board-power or current protection',
                'No PMU acceptance, signature, boot, thermal or boost validation'],
 }
target.write_bytes(out);manifest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
