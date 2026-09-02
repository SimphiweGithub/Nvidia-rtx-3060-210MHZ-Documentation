# NvmlPeStringXref

A deliberately bounded, read-only PE scanner for reproducing static references to an ASCII literal in an x64 PE image.

It reports raw string offsets, mapped RVAs, and recognized executable references using RIP-relative `LEA` or `mov reg, imm64`, plus exception-table function ranges. It is not a disassembler and cannot prove that a reference executed or that an unreported reference does not exist.

Example:

```powershell
dotnet run --project tools/NvmlPeStringXref -- "C:\Windows\System32\DriverStore\FileRepository\...\nvml.dll" "\\.\NvAdminDevice" evidence/analysis/nvml-nvadmindevice-xrefs-2026-09-02.txt
```
