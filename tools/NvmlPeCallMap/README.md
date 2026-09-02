# NVML PE Call Map

This read-only static-analysis utility maps a root RVA to its PE exception-table function range and follows selected direct call patterns for a bounded depth. It does not load the target DLL or call any NVIDIA API.

```powershell
dotnet run --project .\tools\NvmlPeCallMap\NvmlPeCallMap.csproj -c Release -- `
  "C:\Windows\System32\DriverStore\FileRepository\...\nvml.dll" 0x47250 3 `
  .\evidence\analysis\nvml-power-usage-call-map.txt
```

It recognizes only `E8` relative direct calls and `FF 15` RIP-relative calls to normal PE imports, then uses the x64 exception table for function ranges. The output is a lead map, not a disassembly or evidence that any listed edge executed. Verify relevant edges with the single-query x64dbg trace.
