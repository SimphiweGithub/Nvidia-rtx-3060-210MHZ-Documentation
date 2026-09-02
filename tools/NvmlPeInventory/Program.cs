using System.Buffers.Binary;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text;

if (args.Length is < 1 or > 2 || args[0] is "--help" or "-h")
{
    Console.WriteLine("Usage: NvmlPeInventory <path-to-dll> [output-path]");
    return;
}

var inputPath = Path.GetFullPath(args[0]);
var outputPath = args.Length == 2 ? Path.GetFullPath(args[1]) : null;
var report = PeImportInventory.Create(inputPath);

if (outputPath is null)
{
    Console.Write(report);
}
else
{
    Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
    File.WriteAllText(outputPath, report, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
    Console.WriteLine($"Wrote {outputPath}");
}

internal static class PeImportInventory
{
    public static string Create(string inputPath)
    {
        using var stream = File.OpenRead(inputPath);
        using var image = new PEReader(stream);
        var headers = image.PEHeaders;
        var peHeader = headers.PEHeader ?? throw new InvalidDataException("The file does not have a PE header.");
        var importDirectory = peHeader.ImportTableDirectory;
        var imports = ReadImports(image, headers, importDirectory);
        var deviceIoControlIat = FindNamedImportIat(image, headers, importDirectory, "KERNEL32.dll", "DeviceIoControl");
        var deviceIoControlCallSites = deviceIoControlIat is null
            ? []
            : FindDirectIatCallSites(inputPath, headers, deviceIoControlIat.Value);

        var report = new StringBuilder();
        report.AppendLine("# PE import inventory");
        report.AppendLine($"path={inputPath}");
        report.AppendLine($"sha256={Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(inputPath))).ToLowerInvariant()}");
        report.AppendLine($"machine={headers.CoffHeader.Machine}");
        report.AppendLine($"import_directory_rva=0x{importDirectory.RelativeVirtualAddress:X8}");
        report.AppendLine();

        foreach (var library in imports.OrderBy(entry => entry.Key, StringComparer.OrdinalIgnoreCase))
        {
            report.AppendLine($"[{library.Key}]");
            foreach (var symbol in library.Value.OrderBy(symbol => symbol, StringComparer.OrdinalIgnoreCase))
            {
                report.AppendLine(symbol);
            }

            report.AppendLine();
        }

        report.AppendLine("# Direct DeviceIoControl IAT call-site scan");
        if (deviceIoControlIat is null)
        {
            report.AppendLine("DeviceIoControl is not a normal static import.");
        }
        else
        {
            report.AppendLine($"iat_rva=0x{deviceIoControlIat.Value:X8}");
            report.AppendLine("method=FF 15 RIP-relative indirect calls in executable PE sections");
            report.AppendLine("limit=does not detect calls routed through a register, dynamically resolved pointers, or other instruction forms");
            foreach (var callSite in deviceIoControlCallSites)
            {
                report.AppendLine($"call_site_rva=0x{callSite:X8}");
            }
        }

        return report.ToString();
    }

    private static Dictionary<string, List<string>> ReadImports(PEReader image, PEHeaders headers, DirectoryEntry directory)
    {
        var result = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        if (directory.RelativeVirtualAddress == 0 || directory.Size == 0)
        {
            return result;
        }

        var descriptorReader = image.GetSectionData(directory.RelativeVirtualAddress).GetReader();
        var consumed = 0;
        var pointerSize = headers.PEHeader!.Magic == PEMagic.PE32Plus ? sizeof(ulong) : sizeof(uint);

        while (consumed + 20 <= directory.Size)
        {
            var originalFirstThunk = descriptorReader.ReadUInt32();
            _ = descriptorReader.ReadUInt32(); // TimeDateStamp
            _ = descriptorReader.ReadUInt32(); // ForwarderChain
            var nameRva = descriptorReader.ReadUInt32();
            var firstThunk = descriptorReader.ReadUInt32();
            consumed += 20;

            if (originalFirstThunk == 0 && nameRva == 0 && firstThunk == 0)
            {
                break;
            }

            var libraryName = ReadAscii(image, checked((int)nameRva));
            var thunkRva = originalFirstThunk != 0 ? originalFirstThunk : firstThunk;
            result[libraryName] = ReadThunkSymbols(image, checked((int)thunkRva), pointerSize);
        }

        return result;
    }

    private static List<string> ReadThunkSymbols(PEReader image, int thunkRva, int pointerSize)
    {
        var symbols = new List<string>();
        var reader = image.GetSectionData(thunkRva).GetReader();

        while (reader.RemainingBytes >= pointerSize)
        {
            var entry = pointerSize == sizeof(ulong) ? reader.ReadUInt64() : reader.ReadUInt32();
            if (entry == 0)
            {
                break;
            }

            var isOrdinal = pointerSize == sizeof(ulong)
                ? (entry & 0x8000000000000000UL) != 0
                : (entry & 0x80000000U) != 0;

            if (isOrdinal)
            {
                symbols.Add($"ordinal:{entry & 0xFFFF}");
                continue;
            }

            var nameReader = image.GetSectionData(checked((int)entry)).GetReader();
            _ = nameReader.ReadUInt16(); // Hint
            symbols.Add(ReadAscii(nameReader));
        }

        return symbols;
    }

    private static int? FindNamedImportIat(PEReader image, PEHeaders headers, DirectoryEntry directory, string targetLibrary, string targetSymbol)
    {
        if (directory.RelativeVirtualAddress == 0 || directory.Size == 0)
        {
            return null;
        }

        var descriptorReader = image.GetSectionData(directory.RelativeVirtualAddress).GetReader();
        var consumed = 0;
        var pointerSize = headers.PEHeader!.Magic == PEMagic.PE32Plus ? sizeof(ulong) : sizeof(uint);

        while (consumed + 20 <= directory.Size)
        {
            var originalFirstThunk = descriptorReader.ReadUInt32();
            _ = descriptorReader.ReadUInt32();
            _ = descriptorReader.ReadUInt32();
            var nameRva = descriptorReader.ReadUInt32();
            var firstThunk = descriptorReader.ReadUInt32();
            consumed += 20;

            if (originalFirstThunk == 0 && nameRva == 0 && firstThunk == 0)
            {
                break;
            }

            if (!string.Equals(ReadAscii(image, checked((int)nameRva)), targetLibrary, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var lookupThunk = originalFirstThunk != 0 ? originalFirstThunk : firstThunk;
            var symbolReader = image.GetSectionData(checked((int)lookupThunk)).GetReader();
            for (var index = 0; symbolReader.RemainingBytes >= pointerSize; index++)
            {
                var entry = pointerSize == sizeof(ulong) ? symbolReader.ReadUInt64() : symbolReader.ReadUInt32();
                if (entry == 0)
                {
                    break;
                }

                var isOrdinal = pointerSize == sizeof(ulong)
                    ? (entry & 0x8000000000000000UL) != 0
                    : (entry & 0x80000000U) != 0;
                if (!isOrdinal)
                {
                    var nameReader = image.GetSectionData(checked((int)entry)).GetReader();
                    _ = nameReader.ReadUInt16();
                    if (string.Equals(ReadAscii(nameReader), targetSymbol, StringComparison.Ordinal))
                    {
                        return checked((int)(firstThunk + (uint)(index * pointerSize)));
                    }
                }
            }
        }

        return null;
    }

    private static List<int> FindDirectIatCallSites(string inputPath, PEHeaders headers, int iatRva)
    {
        var bytes = File.ReadAllBytes(inputPath);
        var callSites = new List<int>();

        foreach (var section in headers.SectionHeaders)
        {
            if ((section.SectionCharacteristics & SectionCharacteristics.MemExecute) == 0)
            {
                continue;
            }

            var start = section.PointerToRawData;
            var size = section.SizeOfRawData;
            for (var offset = 0; offset <= size - 6; offset++)
            {
                var fileOffset = start + offset;
                if (bytes[fileOffset] != 0xFF || bytes[fileOffset + 1] != 0x15)
                {
                    continue;
                }

                var displacement = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(fileOffset + 2, sizeof(int)));
                var callRva = section.VirtualAddress + offset;
                var targetRva = (long)callRva + 6 + displacement;
                if (targetRva == iatRva)
                {
                    callSites.Add(callRva);
                }
            }
        }

        return callSites;
    }

    private static string ReadAscii(PEReader image, int rva) => ReadAscii(image.GetSectionData(rva).GetReader());

    private static string ReadAscii(BlobReader reader)
    {
        var bytes = new List<byte>();
        while (reader.RemainingBytes > 0)
        {
            var value = reader.ReadByte();
            if (value == 0)
            {
                break;
            }

            bytes.Add(value);
        }

        return Encoding.ASCII.GetString(bytes.ToArray());
    }
}
