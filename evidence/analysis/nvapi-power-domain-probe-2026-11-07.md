# NVAPI power-domain status probe — 7 November 2026

## Purpose and scope

Check whether NVAPI exposes a separate power-domain or power-policy reading that can be compared with the implausible 752.67 W NVML value. The test used read-only functions in the installed `nvapi64.dll`; it did not change power limits, clocks, voltages, firmware or configuration. The private function identifiers and v1 structure layouts are inferred from third-party software, not NVIDIA's published NVAPI contract, so interpret the results as specific to this driver, machine and attempted layouts.

## Observations

- `NvAPI_Initialize` returned 0. `NvAPI_EnumPhysicalGPUs` returned 0 and one device, named `NVIDIA GeForce RTX 3060 Laptop GPU`.
- `ClientPowerTopologyGetStatus` (interface `0xEDCF624E`, a 72-byte v1 buffer, version `0x00010048`) returned status 0 but a count of **zero entries**.
- `ClientPowerPoliciesGetStatus` (interface `0x70916171`, same-sized v1 buffer) returned status 0 but a count of **zero entries**.
- NVAPI was unloaded normally afterwards.

No power-domain values or policy targets were returned by these calls. Status 0 with an empty list does not prove these sensors or control paths do not exist, that the private ABI is correct for this driver, or that an alternate version would behave the same. It supplies no independent physical power measurement and no unlock. The machine's NVML baseline at 08:48 was driver 610.62, vBIOS `94.06.3B.00.0B`, P0, graphics 210 MHz and 752.67 W, with the manual core offset removed.

Interface provenance: NVIDIA's public [NVAPI interface table](https://github.com/NVIDIA/nvapi/blob/main/nvapi_interface.h) identifies initialization, enumeration, naming and unload; the unadvertised status interface and buffer are described by the [NvAPIWrapper topology structure](https://github.com/falahati/NvAPIWrapper/blob/master/NvAPIWrapper/Native/GPU/Structures/PrivatePowerTopologiesStatusV1.cs), [policy structure](https://github.com/falahati/NvAPIWrapper/blob/master/NvAPIWrapper/Native/GPU/Structures/PrivatePowerPoliciesStatusV1.cs), and [power-topology interface definition](https://github.com/vuplea/simple-nvidia-undervolt/blob/main/src/NvApi.cs). These sources document those projects' interpretations, not an NVIDIA guarantee.
