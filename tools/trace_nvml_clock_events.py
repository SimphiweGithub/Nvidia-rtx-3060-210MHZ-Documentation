"""Trace read-only NVML clock-event getters in a disposable child process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import frida

nvml = Path(os.environ['SystemRoot']) / 'System32/DriverStore/FileRepository/nvdmi.inf_amd64_38c6812b57a66ef3/nvml.dll'
if hashlib.sha256(nvml.read_bytes()).hexdigest() != '7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06':
    raise RuntimeError('Unexpected NVML build')
code = r'''import ctypes as c,sys
n=c.CDLL(sys.argv[1]); h=c.c_void_p(); result=c.c_ulonglong()
assert n.nvmlInit_v2()==0 and n.nvmlDeviceGetHandleByIndex_v2(0,c.byref(h))==0
for name in ('nvmlDeviceGetCurrentClocksThrottleReasons','nvmlDeviceGetSupportedClocksThrottleReasons'):
    assert getattr(n,name)(h,c.byref(result))==0
print('READY',flush=True); sys.stdin.readline()
for name in ('nvmlDeviceGetCurrentClocksThrottleReasons','nvmlDeviceGetSupportedClocksThrottleReasons'):
    print('WAIT '+name,flush=True); sys.stdin.readline()
    result.value=0
    print(name, getattr(n,name)(h,c.byref(result)),hex(result.value),flush=True)
n.nvmlShutdown()
'''
child = subprocess.Popen([sys.executable, '-u', '-c', code, str(nvml)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
session = None
try:
    if child.stdout.readline().strip() != 'READY':
        raise RuntimeError('NVML initialization failed')
    session = frida.attach(child.pid)
    script = session.create_script(r'''
const m=Process.enumerateModules().find(x=>x.name.toLowerCase()==='nvml.dll' && x.path.toLowerCase().includes('filerepository'));
if (!m) throw new Error('expected NVML missing');
let phase='initialization';
rpc.exports={setphase(x){phase=x;}};
const active=new Set();
for (const name of ['nvmlDeviceGetCurrentClocksThrottleReasons','nvmlDeviceGetSupportedClocksThrottleReasons']) {
 Interceptor.attach(m.getExportByName(name), {onEnter(){active.add(Process.getCurrentThreadId());send({getter:name,event:'enter'});},onLeave(result){send({getter:name,event:'leave',status:result.toInt32()});active.delete(Process.getCurrentThreadId());}});
}
Interceptor.attach(m.base.add(0x67420), {onEnter(args) {
 if (!active.has(Process.getCurrentThreadId())) return;
 try { const obj=args[0].add(0x28348).readPointer(), table=obj.add(0x148).readPointer(), target=table.add(8).readPointer(), mod=Process.findModuleByAddress(target);
 send({event:'clock_status_target',module:mod?mod.name:null,rva:mod?target.sub(mod.base).toString():null});
 } catch(e) { send({event:'clock_status_target_error',error:String(e)}); }
}});
Interceptor.attach(m.base.add(0xdb0f0), {onEnter(args) {
 if (!active.has(Process.getCurrentThreadId())) return;
 try { const obj=args[1].add(0x28348).readPointer(), table=obj.add(0x148).readPointer(), target=table.readPointer(), mod=Process.findModuleByAddress(target);
 send({event:'clock_state_source',module:mod?mod.name:null,rva:mod?target.sub(mod.base).toString():null});
 const convert=obj.add(0x120).readPointer().add(8).readPointer(), cm=Process.findModuleByAddress(convert);
 send({event:'possible_clock_conversion',module:cm?cm.name:null,rva:cm?convert.sub(cm.base).toString():null});
 } catch(e) { send({event:'clock_state_source_error',error:String(e)}); }
}});
for (const rva of [0xde440,0xe08b0,0xdf040,0xeb210]) {
 Interceptor.attach(m.base.add(rva), {onEnter(){this.hit=active.has(Process.getCurrentThreadId());if(this.hit)send({event:'status_branch',rva:'0x'+rva.toString(16)});},onLeave(result){if(this.hit)send({event:'status_branch_return',rva:'0x'+rva.toString(16),status:result.toInt32()});}});
}
Interceptor.attach(m.base.add(0xecef0), {onEnter(args){
 if (!active.has(Process.getCurrentThreadId())) return;
 this.hit=true; this.offset=args[2].toUInt32(); this.size=args[3].toUInt32(); this.output=this.context.rsp.add(0x28).readPointer();
},onLeave(result){ if(!this.hit) return; let words=[]; if(result.toInt32()===0 && !this.output.isNull()) for(let i=0;i<Math.min(this.size,32);i+=4) words.push(this.output.add(i).readU32());
 let violation=[]; if(result.toInt32()===0 && this.size===1880){ for(let j=0;j<9;j++){ const p=this.output.add(32+j*56); const times=[]; for(let k=0;k<6;k++) times.push(p.add(8+k*8).readU64().toString()); violation.push({index:j,perfPointMask:p.readU32(),timesNs:times}); } }
 send({event:'shared_status_read',offset:this.offset,size:this.size,status:result.toInt32(),words,violation}); }});
Interceptor.attach(m.base.add(0x8bcf0), {
 onEnter(args) { if(!active.has(Process.getCurrentThreadId())) return; this.traced=true; this.cmd=args[3].toUInt32(); this.p=args[4]; this.n=args[5].toUInt32(); },
 onLeave(status) { if (!this.traced) return; let words=[]; if (!this.p.isNull() && this.n<=0x10000) for(let i=0;i+4<=Math.min(this.n,64);i+=4) words.push(this.p.add(i).readU32());
  send({phase,command:'0x'+this.cmd.toString(16),size:this.n,status:status.toInt32(),words}); }
});
''')
    script.on('message', lambda message, data: print(json.dumps(message), flush=True))
    script.load()
    child.stdin.write('go\n'); child.stdin.flush()
    for name in ('nvmlDeviceGetCurrentClocksThrottleReasons','nvmlDeviceGetSupportedClocksThrottleReasons'):
        if child.stdout.readline().strip() != 'WAIT '+name:
            raise RuntimeError('Unexpected child phase')
        script.exports_sync.setphase(name)
        child.stdin.write('go\n'); child.stdin.flush()
        print(child.stdout.readline().strip(),flush=True)
    out, err = child.communicate(timeout=20)
    print(out, end='')
    if err:
        print(err, file=sys.stderr)
    if child.returncode:
        raise RuntimeError('Child failed: %s' % child.returncode)
finally:
    if session:
        session.detach()
    if child.poll() is None:
        child.kill()
