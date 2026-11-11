import ctypes as c,time,sys
C=c.WinDLL('nvcuda.dll');p=c.c_void_p;u=c.c_uint;i=c.c_int
C.cuInit.argtypes=[u];C.cuDeviceGet.argtypes=[c.POINTER(i),i];C.cuCtxCreate_v2.argtypes=[c.POINTER(p),u,i];C.cuModuleLoadData.argtypes=[c.POINTER(p),p];C.cuModuleGetFunction.argtypes=[c.POINTER(p),p,c.c_char_p];C.cuMemAlloc_v2.argtypes=[c.POINTER(c.c_ulonglong),c.c_size_t];C.cuMemFree_v2.argtypes=[c.c_ulonglong];C.cuLaunchKernel.argtypes=[p,u,u,u,u,u,u,u,p,c.POINTER(p),c.POINTER(p)];C.cuCtxSynchronize.argtypes=[];C.cuModuleUnload.argtypes=[p];C.cuCtxDestroy_v2.argtypes=[p]
def check(name,*args):
 code=getattr(C,name)(*args)
 if code:raise RuntimeError(f'{name} failed: {code}')
ptx=b'''.version 7.8
.target sm_86
.address_size 64
.visible .entry burn(.param .u64 output) {
.reg .pred %p;
.reg .b32 %r<5>;
.reg .b64 %rd<4>;
ld.param.u64 %rd1, [output];
mov.u32 %r0, %tid.x;
mov.u32 %r1, %ctaid.x;
mad.lo.u32 %r0, %r1, 128, %r0;
mov.u32 %r1, 0;
mov.u32 %r2, %r0;
LOOP:
mad.lo.u32 %r2, %r2, 1664525, 1013904223;
add.u32 %r1, %r1, 1;
setp.lt.u32 %p, %r1, 10000;
@%p bra LOOP;
mul.wide.u32 %rd2, %r0, 4;
add.u64 %rd3, %rd1, %rd2;
st.global.u32 [%rd3], %r2;
ret;
}'''
ctx=p();mod=p();fn=p();mem=c.c_ulonglong();dev=i();check('cuInit',0);check('cuDeviceGet',c.byref(dev),0);check('cuCtxCreate_v2',c.byref(ctx),0,dev.value)
try:
 code=c.create_string_buffer(ptx);check('cuModuleLoadData',c.byref(mod),c.cast(code,p));check('cuModuleGetFunction',c.byref(fn),mod,b'burn');check('cuMemAlloc_v2',c.byref(mem),64*128*4)
 params=(p*1)(c.cast(c.byref(mem),p));print('READY',flush=True); deadline=time.monotonic()+10;count=0
 while time.monotonic()<deadline:
  check('cuLaunchKernel',fn,64,1,1,128,1,1,0,None,params,None);check('cuCtxSynchronize');count+=1
 print('DONE',count,flush=True)
finally:
 if mem.value:C.cuMemFree_v2(mem)
 if mod.value:C.cuModuleUnload(mod)
 if ctx.value:C.cuCtxDestroy_v2(ctx)

