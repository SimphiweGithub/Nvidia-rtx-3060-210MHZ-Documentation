# NVML PE Import Inventory

This read-only utility records the PE import table of a selected `nvml.dll`. It does not load the target library or call any NVIDIA API.

```powershell
dotnet run --project .\tools\NvmlPeInventory\NvmlPeInventory.csproj -c Release -- `
  "C:\Windows\System32\DriverStore\FileRepository\...\nvml.dll" `
  .\evidence\analysis\nvml-imports.txt
```

Imported functions establish that a DLL is statically linked against an interface; they do not by themselves prove that a particular NVML function invokes that interface.
