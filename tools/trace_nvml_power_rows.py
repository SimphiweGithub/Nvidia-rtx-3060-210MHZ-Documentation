"""Read-only WDDM escape trace of a disposable NVML energy query process."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import frida

nvml = Path(os.environ['SystemRoot']) / 'System32/DriverStore/FileRepository/nvdmi.inf_amd64_38c6812b57a66ef3/nvml.dll'
if hashlib.sha256(nvml.read_bytes()).hexdigest() != '7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06':
    raise RuntimeError('Unexpected NVML binary')
code = r'''import ctypes as c,sys
n=c.CDLL(sys.argv[1]); h=c.c_void_p(); e=c.c_ulonglong()
assert n.nvmlInit_v2()==0 and n.nvmlDeviceGetHandleByIndex_v2(0,c.byref(h))==0
print('READY',flush=True); sys.stdin.readline()
status=n.nvmlDeviceGetTotalEnergyConsumption(h,c.byref(e))
print('energy_status=%d energy_mj=%d'%(status,e.value),flush=True)
sys.stdin.readline()
n.nvmlShutdown()
'''
child = subprocess.Popen([sys.executable, '-u', '-c', code, str(nvml)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
session = None
observed_status = threading.Event()
try:
    if child.stdout.readline().strip() != 'READY':
        raise RuntimeError('NVML probe failed to initialize')
    session = frida.attach(child.pid)
    script = session.create_script(r'''
const nvml=Process.enumerateModules().find(x => x.name.toLowerCase()==='nvml.dll' && x.path.toLowerCase().includes('filerepository'));
if (!nvml) throw new Error('Expected NVML module not loaded');
Interceptor.attach(nvml.base.add(0x8bcf0), {
  onEnter(args) {
    this.command=args[3].toUInt32();
    if (this.command !== 0x2080a612 && this.command !== 0x2080a613) return;
    this.param=args[4];
    this.size=args[5].toUInt32();
  },
  onLeave(status) {
    if (!this.param) return;
    if (this.command === 0x2080a613 && this.size >= 0x40 + 20*0x258) {
      const rows=[];
      for (const i of [0,1,3,5,10,11,12,18,19]) {
        const p=this.param.add(0x40+i*0x258);
        rows.push({index:i, words:[p.readU32(),p.add(4).readU32(),p.add(8).readU32()]});
      }
      send({stage:'channel_rows', command:'0x2080a613', status:status.toInt32(), rows});
    }
    const words=[];
    for (let i=0; i<0x50 && i+4<=this.size; i+=4) words.push(this.param.add(i).readU32());
    send({stage:'dispatch_return', command:'0x'+this.command.toString(16), status:status.toInt32(),
          size:this.size, words});
  }
});
const escape = Process.getModuleByName('win32u.dll').getExportByName('NtGdiDdDDIEscape');
Interceptor.attach(escape, {onEnter(args) {
  const desc=args[0], data=desc.add(0x10).readPointer(), size=desc.add(0x18).readU32();
  if (data.isNull() || size < 0x40 || data.readU32() !== 0x4e564441) return;
  this.data=data;
  this.size=size;
  this.command=data.add(0x38).readU32();
  send({type:desc.add(8).readU32(), size, command:'0x'+data.add(0x38).readU32().toString(16),
        payload_size:data.add(0x3c).readU32()});
}, onLeave(status) {
  if (!this.data || (this.command !== 0x2080a612 && this.command !== 0x2080a613)) return;
  const p=this.data.add(0x44), words=[];
  for (let i=0; i<0x80 && i+0x48<=this.size; i+=4) words.push(p.add(i).readU32());
  send({stage:'return', command:'0x'+this.command.toString(16), ntstatus:status.toInt32(),
        note:'candidate payload starts at private buffer +0x44', words});
}});
''')
    def on_message(message, data):
        print(json.dumps(message), flush=True)
        payload = message.get('payload', {})
        if payload.get('stage') == 'dispatch_return' and payload.get('command') == '0x2080a613':
            observed_status.set()
    script.on('message', on_message)
    script.load()
    child.stdin.write('go\n')
    child.stdin.flush()
    print(child.stdout.readline(), end='', flush=True)
    observed_status.wait(3)
    script.unload()
    child.stdin.write('shutdown\n')
    child.stdin.flush()
    stdout, stderr = child.communicate(timeout=30)
    print(stdout, end='')
    if stderr:
        print(stderr, file=sys.stderr, end='')
    if child.returncode:
        raise RuntimeError(f'Probe exited {child.returncode}')
finally:
    if session:
        session.detach()
    if child.poll() is None:
        child.kill()
        child.wait()

