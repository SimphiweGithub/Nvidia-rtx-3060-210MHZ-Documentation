"""Observe the known power-query dispatch in a disposable child process.

Frida instruments only the child; no driver, returned values, or GPU settings
are modified. The script refuses an NVML build other than the previously traced
hash. Requires the local Frida Python package.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import frida

ROOT = Path(__file__).resolve().parent
DRIVER = Path(os.environ["SystemRoot"]) / "System32/DriverStore/FileRepository/nvdmi.inf_amd64_38c6812b57a66ef3/nvml.dll"
EXPECTED = "7e00bb555f2c6ab96f2a56781a9dce0518fa30835f079b3d3731eae3f44d3b06"
if hashlib.sha256(DRIVER.read_bytes()).hexdigest() != EXPECTED:
    raise RuntimeError("NVML hash changed; refusing build-specific instrumentation")

child_code = (
    "import ctypes,runpy,sys; sys.path.insert(0,sys.argv[2]); n=ctypes.CDLL('nvml.dll'); "
    "assert n.nvmlInit_v2()==0; "
    "print('READY',flush=True); sys.stdin.readline(); "
    "runpy.run_path(sys.argv[1],run_name='__main__')"
)
child = subprocess.Popen([sys.executable, "-u", "-c", child_code, str(ROOT / "nvml_rm_query_compare.py"), str(ROOT)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
session = None
try:
    if child.stdout.readline().strip() != "READY":
        raise RuntimeError("Probe did not initialize")
    session = frida.attach(child.pid)
    script = session.create_script(r"""
const m = Process.enumerateModules().find(x => x.name.toLowerCase() === 'nvml.dll' && x.path.toLowerCase().includes('filerepository'));
if (!m) throw new Error('DriverStore NVML module not loaded');
const active = new Set();
Interceptor.attach(m.base.add(0x8bcf0), {
  onEnter(args) {
    const a2 = args[2].toUInt32(), a3 = args[3].toUInt32();
    const a4 = args[4].toUInt32(), a5 = args[5].toUInt32();
    if (a2 !== 0x2080a637 && a3 !== 0x2080a637 && a4 !== 0x2080a637 && a5 !== 0x2080a637) return;
    this.traced = true;
    active.add(Process.getCurrentThreadId());
    const target = args[0].add(0x20).readPointer();
    const module = Process.findModuleByAddress(target);
    send({command: '0x2080a637',
          module: module ? module.name : null,
          path: module ? module.path : null,
          rva: module ? target.sub(module.base).toString() : null});
  },
  onLeave() { if (this.traced) active.delete(Process.getCurrentThreadId()); }
});
Interceptor.attach(m.base.add(0x15ff20), {
  onEnter() {
    if (!active.has(Process.getCurrentThreadId())) return;
    const table = m.base.add(0x15bd518).readPointer();
    const target = table.add(0x190).readPointer();
    const module = Process.findModuleByAddress(target);
    send({stage: 'transport', module: module ? module.name : null,
          path: module ? module.path : null,
          rva: module ? target.sub(module.base).toString() : null});
  }
});
const escape = Process.getModuleByName('win32u.dll').getExportByName('NtGdiDdDDIEscape');
Interceptor.attach(escape, {
  onEnter(args) {
    if (!active.has(Process.getCurrentThreadId())) return;
    const desc = args[0], data = desc.add(0x10).readPointer();
    const size = desc.add(0x18).readU32();
    this.traced = true;
    send({stage: 'wddm_escape', type: desc.add(8).readU32(), size,
          signature: size >= 4 ? data.readU32().toString(16) : null,
          command: size >= 0x3c ? data.add(0x38).readU32().toString(16) : null,
          payloadSize: size >= 0x40 ? data.add(0x3c).readU32() : null});
  },
  onLeave(result) { if (this.traced) send({stage: 'wddm_escape_return', status: result.toInt32()}); }
});
""")
    script.on("message", lambda message, data: print(json.dumps(message), flush=True))
    script.load()
    child.stdin.write("go\n")
    child.stdin.flush()
    stdout, stderr = child.communicate(timeout=30)
    print(stdout, end="")
    if stderr:
        print(stderr, file=sys.stderr, end="")
    if child.returncode:
        raise RuntimeError(f"Probe failed with status {child.returncode}")
finally:
    if session:
        session.detach()
    if child.poll() is None:
        child.kill()
        child.wait()
