"""Build a multi-channel relationship hypothesis offline. Never load or flash it."""
import hashlib
import json
import struct
from pathlib import Path

from nvidia_vbios.rom.tables import checksum_tail

root = Path(__file__).resolve().parent.parent
source = root / 'evidence/runs/nvapi-running-vbios-20261109.bin'
target = root / 'evidence/runs/OFFLINE-ONLY-multi-channel-v2-20261110.bin'
manifest = target.with_suffix('.json')
if target.exists() or manifest.exists():
    raise FileExistsError('Refusing to overwrite offline artifacts')
data = source.read_bytes()
assert hashlib.sha256(data).hexdigest() == '34c6676becef4ced24308274e4537f59b5cf0e23b64659bce6f07325debea3ae'
table, image_start, image_end = 563230, 180224, 609792
assert tuple(data[table:table+6]) == (32, 6, 26, 32, 46, 32)
assert sum(data[image_start:image_end]) % 256 == 0 and checksum_tail(data, image_end, 'ampere') is not None
entry = lambda n: table+6+n*26
rel = table+6+32*26
assert data[rel+46:rel+46+6] == bytes.fromhex('010a00100000')
assert data[rel+2*46:rel+2*46+6] == bytes.fromhex('010500100000')
users=[]
for index in range(32):
    rec=data[entry(index):entry(index)+26]
    if rec[0]==2 and rec[14]<=rec[15]<32 and rec[14]<=14<=rec[15]:
        users.append(index)
if users != [12]:
    raise ValueError('Relationship 14 has unexpected class-2 users: '+repr(users))
changes = [
    (entry(0)+14, bytes([1,2]), bytes([2,2]), 'channel 0 reads channel 5'),
    (entry(3), bytes([5]), bytes([2]), 'channel 3 class'),
    (entry(3)+14, bytes([0,1]), bytes([14,14]), 'channel 3 uses relationship 14'),
    (entry(5), bytes([5]), bytes([2]), 'channel 5 class'),
    (entry(5)+14, bytes([0,0]), bytes([1,1]), 'channel 5 uses relationship 1'),
    (entry(12)+14, bytes([13,14]), bytes([13,13]), 'channel 12 reads channel 0 only'),
    (rel+14*46+1, bytes([11]), bytes([10]), 'relationship 14 source'),
    (rel+14*46+2, struct.pack('<i',-4096), struct.pack('<i',1410), 'relationship 14 weight'),
]
output=bytearray(data)
for offset,before,after,label in changes:
    if data[offset:offset+len(before)] != before:
        raise ValueError('Unexpected original bytes: '+label)
    output[offset:offset+len(after)] = after
for index in range(32):
    assert output[rel+index*46+31:rel+(index+1)*46] == data[rel+index*46+31:rel+(index+1)*46]
old=output[image_end-1]
output[image_end-1]=(old-sum(output[image_start:image_end]))&255
assert sum(output[image_start:image_end])%256 == 0
summary={
    'status':'OFFLINE ONLY; not validated for firmware or live use',
    'source_sha256':hashlib.sha256(data).hexdigest(),
    'output_sha256':hashlib.sha256(output).hexdigest(),
    'changes':[{'offset':o,'before_hex':b.hex(),'after_hex':a.hex(),'field':label} for o,b,a,label in changes],
    'checksum_offset':image_end-1,'checksum_before':old,'checksum_after':output[image_end-1],
    'predicted_first_words_mw_before_rounding':{'C0':6100,'C1':6100-6100*1410/4096,'C3':6100*1410/4096,
                                               'C5':6100,'C10':6100,'C11':6100-6100*1410/4096,'C12':6100},
    'limitations':['Class-5 to class-2 conversion has not been tested',
                   'Unknown second records are preserved, but their effects are unverified',
                   'Relationship 14 usage by non-class-2 objects is unverified',
                   'Power/current/voltage feedback is spoofed and independent board protection is unverified',
                   'Current and voltage values, policy behavior, boot behavior and signature are unverified']}
target.write_bytes(output)
manifest.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2))
