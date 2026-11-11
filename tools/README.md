# Tools

Run commands from the repository root unless a tool says otherwise. Most scripts are machine-specific investigation artifacts; read them before use. The switch is the intended entry point for the tested laptop.

## On/off switch

Double-click [GPU-Slope-Switch.cmd](GPU-Slope-Switch.cmd) in File Explorer. Its menu calls [gpu_slope_toggle.ps1](gpu_slope_toggle.ps1):

| Menu choice | Action |
| --- | --- |
| 1 | Show configured override and device status. |
| 2 | Enable the expected override and restart the GPU device. |
| 3 | Remove the expected override and restart the GPU device. |
| Q | Exit. |

Enable and Disable prompt for confirmation and administrator access. Save work first. The switch is tied to the original laptop's device identity and [image](../evidence/runs/OFFLINE-ONLY-current-slope-relocated-20261110.bin); keep the folder layout intact. If a restart fails, its registry change may already have occurred. See the [main guide](../README.md#run-the-switch-on-the-tested-laptop) for the limitations and recovery context.

Status checks the registry configuration, not necessarily the image currently loaded by the driver. [verify_loaded_slope_image.py](verify_loaded_slope_image.py) compares a readback with the candidate without changing settings, but requires the separately obtained Vix loader Python source on `PYTHONPATH` and assumes PCI address `01:00.0`; it is not a standalone general-purpose verification tool. A matching image does not verify power protection.

## Read-only monitoring

[capture_gpuz_voltage.py](capture_gpuz_voltage.py) captures GPU-Z sensor values and NVIDIA clock reasons for 1–60 seconds. It requires Python, GPU-Z running with shared memory available, and `nvidia-smi` accessible. From the repository root:

```powershell
python tools/capture_gpuz_voltage.py --seconds 10
```

The CSV is written to `evidence/runs`. The script does not start or stop workloads, change settings, or enforce a temperature or power limit. With the override loaded, reported power/current cannot be used as actual measurements.

## Research and previous experiments

- `build_offline_*`, `model_*`, and `inspect_*` files relate to candidate construction or investigation. “Offline” describes preparation, not approval to load an image.
- `*_probe.ps1`, `run_*_stage.ps1`, and restart or debugger scripts were created for specific experiments. Some change system state, require elevation, restart a GPU, or stage overrides; they are not routine usage instructions.
- `prepare_afterburner_profile4_*` and `install_afterburner_profile4_*` document specific historical curve changes. They are not a generic profile installer, and old results do not establish a stable overclock.
- `Nvml*` directories contain earlier .NET investigation utilities. Their associated analysis and captures are indexed in [evidence](../evidence/README.md).

The candidate images in `evidence/runs` include failed and untested variants. Only the exact image linked above is the one used by the switch.
