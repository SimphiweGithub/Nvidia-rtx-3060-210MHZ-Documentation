"""Build an offline multi-channel hypothesis without candidate-v2's possible self-reference."""
import hashlib
import json
import struct
from pathlib import Path
from nvidia_vbios.rom.tables import checksum_tail

root=Path(__file__).resolve().parent.parent
source=root/'evidence/runs/nvapi-running-vbios-20261109.bin'
target=root/'evidence/runs/OFFLINE-ONLY-multi-channel-v3-20261110.bin'
manifest=target.with_suffix('.json')
if target.exists() or manifest.exists():
    raise FileExistsError('Refusing to overwrite offline artifacts')
data=source.read_bytes()
assert hashlib.sha256(data).hexdigest()=='34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae'
table,image_start,image_end=563230,180224,609792
assert tuple(data[table:table+6])==(32,6,26,32,46,32)
assert sum(data[image_start:image_end])%256==0 and checksum_tail(data,image_end,'ampere') is not None
entry=lambda n:table+6+n*26
rel=table+6+32*26
assert data[rel+15*46:rel+16*46]==bytes(46)
users={14:[],15:[]}
for i in range(32):
    r=data[entry(i):entry(i)+26]
    if r[0]==2 and r[14]<=r[15]<32:
        for j in users:
            if r[14]<=j<=r[15]:users[j].append(i)
assert users=={14:[12],15:[]}
changes=[
 (entry(0)+14,bytes([1,2]),bytes([2,2]),'channel 0 uses relationship 2'),
 (entry(3),bytes([5]),bytes([2]),'channel 3 class'),
 (entry(3)+14,bytes([0,1]),bytes([15,15]),'channel 3 uses relationship 15'),
 (entry(5),bytes([5]),bytes([2]),'channel 5 class'),
 (entry(5)+14,bytes([0,0]),bytes([14,14]),'channel 5 uses relationship 14'),
 (entry(12)+14,bytes([13,14]),bytes([13,13]),'channel 12 uses relationship 13'),
 (rel+14*46+1,bytes([11]),bytes([10]),'relationship 14 source'),
 (rel+14*46+2,struct.pack('<i',-4096),struct.pack('<i',4096),'relationship 14 weight'),
 (rel+15*46,bytes(6),bytes([1,10])+struct.pack('<i',1410),'relationship 15 first record')]
out=bytearray(data)
for off,before,after,label in changes:
    if data[off:off+len(before)]!=before:raise ValueError('Unexpected bytes: '+label)
    out[off:off+len(after)]=after
for i in range(32):
    assert out[rel+i*46+31:rel+(i+1)*46]==data[rel+i*46+31:rel+(i+1)*46]
for i in (3,5):
    start,end=out[entry(i)+14:entry(i)+16]
    for j in range(start,end+1):
        sub=out[rel+j*46+31:rel+j*46+46]
        assert not (sub[0]==1 and sub[1]==i)
old=out[image_end-1]
out[image_end-1]=(old-sum(out[image_start:image_end]))&255
assert sum(out[image_start:image_end])%256==0
summary={'status':'OFFLINE ONLY; no runtime, boot, PMU, signature or protection validation',
 'source_sha256':hashlib.sha256(data).hexdigest(),'output_sha256':hashlib.sha256(out).hexdigest(),
 'changes':[{'offset':o,'before_hex':b.hex(),'after_hex':a.hex(),'field':label} for o,b,a,label in changes],
 'checksum_offset':image_end-1,'checksum_before':old,'checksum_after':out[image_end-1],
 'predicted_first_words_mw_before_rounding':{'C0':6100,'C1':6100-6100*1410/4096,'C3':6100*1410/4096,
                                           'C5':6100,'C10':6100,'C11':6100-6100*1410/4096,'C12':6100},
 'limitations':['Second-record semantics remain unknown, even when unchanged',
                'Relationship 15 allocation and class-5 to class-2 conversions remain untested',
                'Use of relations 14 and 15 by non-class-2 consumers remains unknown',
                'Current/voltage feedback and independent board-power protection are not verified',
                'The failed v2 boot was not proven to result from the possible self-reference']}
target.write_bytes(out)
manifest.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
