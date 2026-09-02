using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

const string CsvHeader = "timestamp_utc,sequence,nvml_status,power_mw,pstate,graphics_clock_mhz,memory_clock_mhz,current_limit_mw,enforced_limit_mw";

var isPowerOnlyLauncher = string.Equals(
    Path.GetFileNameWithoutExtension(Environment.ProcessPath),
    "NvmlPowerOnlyEvidenceProbe",
    StringComparison.OrdinalIgnoreCase);
var options = Options.Parse(args, isPowerOnlyLauncher);
Directory.CreateDirectory(Path.GetDirectoryName(options.OutputPath)!);

try
{
    using var nvml = new NvmlSession();
    using var writer = new StreamWriter(options.OutputPath, append: false, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

    writer.WriteLine($"# NvmlEvidenceProbe {typeof(Program).Assembly.GetName().Version}");
    writer.WriteLine($"# started_utc={DateTimeOffset.UtcNow:O}");
    writer.WriteLine($"# driver_version={nvml.DriverVersion}");
    writer.WriteLine($"# nvml_version={nvml.NvmlVersion}");
    writer.WriteLine($"# gpu_index={options.GpuIndex}");
    writer.WriteLine($"# sample_interval_ms={options.IntervalMs}");
    writer.WriteLine($"# power_only={options.PowerOnly.ToString().ToLowerInvariant()}");
    writer.WriteLine($"# explicitly_loaded_nvml_module={nvml.LoadedModulePath}");
    writer.WriteLine("# loaded_nvml_modules:");
    foreach (var module in ModuleInventory.FindNvmlModules())
    {
        writer.WriteLine($"# {module.Path} | sha256={module.Sha256}");
    }

    writer.WriteLine(CsvHeader);

    for (var sequence = 1; sequence <= options.SampleCount; sequence++)
    {
        var sample = nvml.ReadSample(options.GpuIndex, options.PowerOnly);
        writer.WriteLine(sample.ToCsv(sequence));
        writer.Flush();
        Console.WriteLine(sample.ToConsole(sequence));

        if (sequence < options.SampleCount)
        {
            Thread.Sleep(options.IntervalMs);
        }
    }

    Console.WriteLine($"Wrote {options.SampleCount} sample(s) to {Path.GetFullPath(options.OutputPath)}");
    Environment.ExitCode = 0;
}
catch (Exception exception)
{
    Console.Error.WriteLine($"Probe failed: {exception.Message}");
    Environment.ExitCode = 1;
}

internal sealed record Options(int GpuIndex, int SampleCount, int IntervalMs, bool PowerOnly, string OutputPath)
{
    public static Options Parse(string[] arguments, bool powerOnlyLauncher)
    {
        var gpuIndex = 0;
        var sampleCount = powerOnlyLauncher ? 1 : 10;
        var intervalMs = 1000;
        var powerOnly = powerOnlyLauncher;
        var outputPath = Path.Combine("evidence", "runs", $"nvml-probe-{DateTimeOffset.UtcNow:yyyyMMdd-HHmmss}.csv");

        for (var index = 0; index < arguments.Length; index++)
        {
            string Value()
            {
                if (++index >= arguments.Length)
                {
                    throw new ArgumentException($"Missing value for {arguments[index - 1]}.");
                }

                return arguments[index];
            }

            switch (arguments[index])
            {
                case "--gpu":
                    gpuIndex = ParseNonNegativeInt(Value(), "--gpu");
                    break;
                case "--samples":
                    sampleCount = ParsePositiveInt(Value(), "--samples");
                    break;
                case "--interval-ms":
                    intervalMs = ParsePositiveInt(Value(), "--interval-ms");
                    break;
                case "--output":
                    outputPath = Value();
                    break;
                case "--power-only":
                    powerOnly = true;
                    break;
                case "--help":
                case "-h":
                    PrintUsageAndExit();
                    break;
                default:
                    throw new ArgumentException($"Unknown option: {arguments[index]}.");
            }
        }

        return new Options(gpuIndex, sampleCount, intervalMs, powerOnly, outputPath);
    }

    private static int ParsePositiveInt(string value, string option)
    {
        var parsed = ParseNonNegativeInt(value, option);
        return parsed > 0 ? parsed : throw new ArgumentException($"{option} must be greater than zero.");
    }

    private static int ParseNonNegativeInt(string value, string option) =>
        int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var parsed) && parsed >= 0
            ? parsed
            : throw new ArgumentException($"{option} must be a non-negative integer.");

    private static void PrintUsageAndExit()
    {
        Console.WriteLine("Usage: NvmlEvidenceProbe [--gpu 0] [--samples 10] [--interval-ms 1000] [--power-only] [--output path.csv]");
        Environment.Exit(0);
    }
}

internal sealed class NvmlSession : IDisposable
{
    private readonly nint _library;
    private readonly NvmlInit _init;
    private readonly NvmlShutdown _shutdown;
    private readonly NvmlDeviceGetHandleByIndex _getHandle;
    private readonly NvmlDeviceGetPowerUsage _getPowerUsage;
    private readonly NvmlDeviceGetPowerState? _getPowerState;
    private readonly NvmlDeviceGetClockInfo? _getClockInfo;
    private readonly NvmlDeviceGetPowerManagementLimit? _getPowerManagementLimit;
    private readonly NvmlDeviceGetEnforcedPowerLimit? _getEnforcedPowerLimit;
    private bool _initialized;

    public NvmlSession()
    {
        _library = NativeLibrary.Load("nvml.dll");
        _init = LoadRequired<NvmlInit>("nvmlInit_v2", "nvmlInit");
        _shutdown = LoadRequired<NvmlShutdown>("nvmlShutdown");
        _getHandle = LoadRequired<NvmlDeviceGetHandleByIndex>("nvmlDeviceGetHandleByIndex_v2", "nvmlDeviceGetHandleByIndex");
        _getPowerUsage = LoadRequired<NvmlDeviceGetPowerUsage>("nvmlDeviceGetPowerUsage");
        _getPowerState = LoadOptional<NvmlDeviceGetPowerState>("nvmlDeviceGetPowerState");
        _getClockInfo = LoadOptional<NvmlDeviceGetClockInfo>("nvmlDeviceGetClockInfo");
        _getPowerManagementLimit = LoadOptional<NvmlDeviceGetPowerManagementLimit>("nvmlDeviceGetPowerManagementLimit");
        _getEnforcedPowerLimit = LoadOptional<NvmlDeviceGetEnforcedPowerLimit>("nvmlDeviceGetEnforcedPowerLimit");

        LoadedModulePath = GetModulePath(_library);
        Check(_init(), "nvmlInit");
        _initialized = true;
        DriverVersion = ReadVersion("nvmlSystemGetDriverVersion");
        NvmlVersion = ReadVersion("nvmlSystemGetNVMLVersion");
    }

    public string DriverVersion { get; }
    public string NvmlVersion { get; }
    public string LoadedModulePath { get; }

    public Sample ReadSample(int gpuIndex, bool powerOnly)
    {
        Check(_getHandle((uint)gpuIndex, out var device), "nvmlDeviceGetHandleByIndex");
        var timestamp = DateTimeOffset.UtcNow;

        var powerStatus = _getPowerUsage(device, out var powerMw);
        var pState = powerOnly ? null : TryRead(_getPowerState, device);
        var graphicsClock = powerOnly ? null : TryRead(_getClockInfo, device, NvmlClockType.Graphics);
        var memoryClock = powerOnly ? null : TryRead(_getClockInfo, device, NvmlClockType.Memory);
        var currentLimit = powerOnly ? null : TryRead(_getPowerManagementLimit, device);
        var enforcedLimit = powerOnly ? null : TryRead(_getEnforcedPowerLimit, device);

        return new Sample(timestamp, powerStatus, powerMw, pState, graphicsClock, memoryClock, currentLimit, enforcedLimit);
    }

    public void Dispose()
    {
        if (_initialized)
        {
            _shutdown();
        }

        NativeLibrary.Free(_library);
    }

    private string ReadVersion(string exportName)
    {
        var getVersion = LoadOptional<NvmlSystemGetVersion>(exportName);
        if (getVersion is null)
        {
            return "unavailable";
        }

        var buffer = Marshal.AllocHGlobal(80);
        try
        {
            var status = getVersion(buffer, 80);
            return status == NvmlReturn.Success ? Marshal.PtrToStringAnsi(buffer) ?? "empty" : $"error-{(int)status}";
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private T LoadRequired<T>(params string[] names) where T : Delegate =>
        LoadOptional<T>(names) ?? throw new MissingMethodException($"NVML does not export any of: {string.Join(", ", names)}.");

    private T? LoadOptional<T>(params string[] names) where T : Delegate
    {
        foreach (var name in names)
        {
            if (NativeLibrary.TryGetExport(_library, name, out var export))
            {
                return Marshal.GetDelegateForFunctionPointer<T>(export);
            }
        }

        return null;
    }

    private static uint? TryRead(NvmlDeviceGetPowerState? function, nint device)
    {
        if (function is null)
        {
            return null;
        }

        var status = function(device, out var value);
        return status == NvmlReturn.Success ? value : null;
    }

    private static uint? TryRead(NvmlDeviceGetClockInfo? function, nint device, NvmlClockType clockType)
    {
        if (function is null)
        {
            return null;
        }

        var status = function(device, clockType, out var value);
        return status == NvmlReturn.Success ? value : null;
    }

    private static uint? TryRead(NvmlDeviceGetPowerManagementLimit? function, nint device)
    {
        if (function is null)
        {
            return null;
        }

        var status = function(device, out var value);
        return status == NvmlReturn.Success ? value : null;
    }

    private static uint? TryRead(NvmlDeviceGetEnforcedPowerLimit? function, nint device)
    {
        if (function is null)
        {
            return null;
        }

        var status = function(device, out var value);
        return status == NvmlReturn.Success ? value : null;
    }

    private static void Check(NvmlReturn status, string operation)
    {
        if (status != NvmlReturn.Success)
        {
            throw new InvalidOperationException($"{operation} failed with NVML status {(int)status} ({status}).");
        }
    }

    private static string GetModulePath(nint moduleHandle)
    {
        var capacity = 260;
        while (capacity <= 32768)
        {
            var buffer = new StringBuilder(capacity);
            var length = GetModuleFileName(moduleHandle, buffer, buffer.Capacity);
            if (length == 0)
            {
                return "unavailable";
            }

            if (length < buffer.Capacity - 1)
            {
                return buffer.ToString();
            }

            capacity *= 2;
        }

        return "unavailable";
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetModuleFileName(nint module, StringBuilder fileName, int size);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlInit();

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlShutdown();

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlSystemGetVersion(nint buffer, uint length);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetHandleByIndex(uint index, out nint device);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetPowerUsage(nint device, out uint powerMw);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetPowerState(nint device, out uint pState);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetClockInfo(nint device, NvmlClockType clockType, out uint clockMhz);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetPowerManagementLimit(nint device, out uint powerLimitMw);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate NvmlReturn NvmlDeviceGetEnforcedPowerLimit(nint device, out uint powerLimitMw);
}

internal sealed record Sample(
    DateTimeOffset Timestamp,
    NvmlReturn PowerStatus,
    uint PowerMw,
    uint? PState,
    uint? GraphicsClockMhz,
    uint? MemoryClockMhz,
    uint? CurrentLimitMw,
    uint? EnforcedLimitMw)
{
    public string ToCsv(int sequence) => string.Join(",",
        Timestamp.ToString("O", CultureInfo.InvariantCulture),
        sequence.ToString(CultureInfo.InvariantCulture),
        ((int)PowerStatus).ToString(CultureInfo.InvariantCulture),
        PowerMw.ToString(CultureInfo.InvariantCulture),
        Format(PState),
        Format(GraphicsClockMhz),
        Format(MemoryClockMhz),
        Format(CurrentLimitMw),
        Format(EnforcedLimitMw));

    public string ToConsole(int sequence) =>
        $"{sequence,3} | {Timestamp:HH:mm:ss}Z | power={PowerMw} mW | P{Format(PState)} | graphics={Format(GraphicsClockMhz)} MHz | memory={Format(MemoryClockMhz)} MHz";

    private static string Format(uint? value) => value?.ToString(CultureInfo.InvariantCulture) ?? "";
}

internal static class ModuleInventory
{
    public static IReadOnlyList<ModuleRecord> FindNvmlModules()
    {
        using var process = Process.GetCurrentProcess();
        return process.Modules
            .Cast<ProcessModule>()
            .Where(module => string.Equals(module.ModuleName, "nvml.dll", StringComparison.OrdinalIgnoreCase))
            .Select(module => new ModuleRecord(module.FileName, HashFile(module.FileName)))
            .OrderBy(module => module.Path, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static string HashFile(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }
}

internal sealed record ModuleRecord(string Path, string Sha256);

internal enum NvmlReturn
{
    Success = 0,
}

internal enum NvmlClockType
{
    Graphics = 0,
    Sm = 1,
    Memory = 2,
    Video = 3,
}
