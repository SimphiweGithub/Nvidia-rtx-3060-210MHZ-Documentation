using System.Buffers.Binary;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text;

if (args.Length is < 2 or > 4 || args[0] is "--help" or "-h")
{
    Console.WriteLine("Usage: NvmlPeCallMap <path-to-dll> <root-rva-hex> [max-depth] [output-path]");
    return;
}

var inputPath = Path.GetFullPath(args[0]);
var rootRva = ParseRva(args[1]);
var maxDepth = args.Length >= 3 && int.TryParse(args[2], out var parsedDepth) ? parsedDepth : 3;
if (maxDepth < 0 || maxDepth > 8)
{
    throw new ArgumentOutOfRangeException(nameof(maxDepth), "max-depth must be between 0 and 8.");
}

var outputPath = args.Length == 4 ? Path.GetFullPath(args[3]) : null;
var report = CallMap.Create(inputPath, rootRva, maxDepth);
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

static int ParseRva(string value)
{
    var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? value[2..] : value;
    return int.TryParse(normalized, System.Globalization.NumberStyles.AllowHexSpecifier, null, out var parsed) && parsed >= 0
        ? parsed
        : throw new ArgumentException($"Invalid RVA: {value}");
}

internal sealed record FunctionRange(int Start, int End)
{
    public bool Contains(int rva) => rva >= Start && rva < End;
}

internal sealed record CallEdge(int CallSiteRva, string Kind, int? TargetRva, string Detail);

internal static class CallMap
{
    public static string Create(string inputPath, int rootRva, int maxDepth)
    {
        var bytes = File.ReadAllBytes(inputPath);
        using var image = new PEReader(new MemoryStream(bytes, writable: false));
        var headers = image.PEHeaders;
        var peHeader = headers.PEHeader ?? throw new InvalidDataException("The file does not have a PE header.");
        var functions = ReadFunctionRanges(image, peHeader.ExceptionTableDirectory);
        var root = functions.FirstOrDefault(range => range.Contains(rootRva))
            ?? throw new InvalidDataException($"No exception-table function contains RVA 0x{rootRva:X8}.");
        var imports = ReadImportIat(image, headers, peHeader.ImportTableDirectory);

        var report = new StringBuilder();
        report.AppendLine("# Heuristic PE call map");
        report.AppendLine($"path={inputPath}");
        report.AppendLine($"sha256={Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant()}");
        report.AppendLine($"root_rva=0x{rootRva:X8}");
        report.AppendLine($"root_function_range=0x{root.Start:X8}-0x{root.End:X8}");
        report.AppendLine($"max_depth={maxDepth}");
        report.AppendLine("method=exception-table function ranges; E8 direct-call targets must resolve to an exception-table function; FF 15 RIP-relative normal-import calls");
        report.AppendLine("limit=this is not a full x86-64 disassembly or proof of execution; it omits unresolved direct targets and dynamic confirmation remains required");
        report.AppendLine();

        var queue = new Queue<(FunctionRange Function, int Depth)>();
        var visited = new HashSet<int>();
        queue.Enqueue((root, 0));

        while (queue.Count > 0)
        {
            var (function, depth) = queue.Dequeue();
            if (!visited.Add(function.Start))
            {
                continue;
            }

            report.AppendLine($"[function depth={depth} range=0x{function.Start:X8}-0x{function.End:X8}]");
            foreach (var edge in FindCallEdges(bytes, headers, function, imports, functions))
            {
                var target = edge.TargetRva is int targetRva ? $" target_rva=0x{targetRva:X8}" : string.Empty;
                report.AppendLine($"{edge.Kind} call_site_rva=0x{edge.CallSiteRva:X8}{target} detail={edge.Detail}");

                if (depth < maxDepth && edge.Kind == "direct" && edge.TargetRva is int directTarget)
                {
                    var targetFunction = functions.FirstOrDefault(range => range.Contains(directTarget));
                    if (targetFunction is not null && !visited.Contains(targetFunction.Start))
                    {
                        queue.Enqueue((targetFunction, depth + 1));
                    }
                }
            }

            report.AppendLine();
        }

        return report.ToString();
    }

    private static List<FunctionRange> ReadFunctionRanges(PEReader image, DirectoryEntry directory)
    {
        var functions = new List<FunctionRange>();
        if (directory.RelativeVirtualAddress == 0 || directory.Size == 0)
        {
            return functions;
        }

        var reader = image.GetSectionData(directory.RelativeVirtualAddress).GetReader();
        for (var consumed = 0; consumed + 12 <= directory.Size; consumed += 12)
        {
            var start = checked((int)reader.ReadUInt32());
            var end = checked((int)reader.ReadUInt32());
            _ = reader.ReadUInt32(); // UnwindInfoAddress
            if (end > start)
            {
                functions.Add(new FunctionRange(start, end));
            }
        }

        return functions.OrderBy(range => range.Start).ToList();
    }

    private static Dictionary<int, string> ReadImportIat(PEReader image, PEHeaders headers, DirectoryEntry directory)
    {
        var imports = new Dictionary<int, string>();
        if (directory.RelativeVirtualAddress == 0 || directory.Size == 0)
        {
            return imports;
        }

        var descriptorReader = image.GetSectionData(directory.RelativeVirtualAddress).GetReader();
        var pointerSize = headers.PEHeader!.Magic == PEMagic.PE32Plus ? sizeof(ulong) : sizeof(uint);
        for (var consumed = 0; consumed + 20 <= directory.Size; consumed += 20)
        {
            var originalFirstThunk = descriptorReader.ReadUInt32();
            _ = descriptorReader.ReadUInt32();
            _ = descriptorReader.ReadUInt32();
            var nameRva = descriptorReader.ReadUInt32();
            var firstThunk = descriptorReader.ReadUInt32();
            if (originalFirstThunk == 0 && nameRva == 0 && firstThunk == 0)
            {
                break;
            }

            var library = ReadAscii(image, checked((int)nameRva));
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
                var symbol = isOrdinal
                    ? $"ordinal:{entry & 0xFFFF}"
                    : ReadImportName(image, checked((int)entry));
                imports[checked((int)(firstThunk + (uint)(index * pointerSize)))] = $"{library}!{symbol}";
            }
        }

        return imports;
    }

    private static IEnumerable<CallEdge> FindCallEdges(byte[] bytes, PEHeaders headers, FunctionRange function, Dictionary<int, string> imports, IReadOnlyList<FunctionRange> functions)
    {
        for (var rva = function.Start; rva < function.End; rva++)
        {
            if (!TryGetFileOffset(headers, rva, out var fileOffset))
            {
                continue;
            }

            if (rva + 5 <= function.End && bytes[fileOffset] == 0xE8)
            {
                var displacement = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(fileOffset + 1, sizeof(int)));
                var target = checked((int)((long)rva + 5 + displacement));
                var targetFunction = functions.FirstOrDefault(range => range.Contains(target));
                if (targetFunction is not null)
                {
                    yield return new CallEdge(rva, "direct", target, $"E8-relative function_range=0x{targetFunction.Start:X8}-0x{targetFunction.End:X8}");
                }
            }

            if (rva + 6 <= function.End && bytes[fileOffset] == 0xFF && bytes[fileOffset + 1] == 0x15)
            {
                var displacement = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(fileOffset + 2, sizeof(int)));
                var iatRva = checked((int)((long)rva + 6 + displacement));
                if (imports.TryGetValue(iatRva, out var symbol))
                {
                    yield return new CallEdge(rva, "import", null, symbol);
                }
            }
        }
    }

    private static bool TryGetFileOffset(PEHeaders headers, int rva, out int fileOffset)
    {
        foreach (var section in headers.SectionHeaders)
        {
            var start = (long)section.VirtualAddress;
            var length = Math.Max(section.VirtualSize, section.SizeOfRawData);
            if (rva >= start && rva < start + length)
            {
                fileOffset = checked((int)(section.PointerToRawData + ((long)rva - start)));
                return true;
            }
        }

        fileOffset = 0;
        return false;
    }

    private static string ReadImportName(PEReader image, int rva)
    {
        var reader = image.GetSectionData(rva).GetReader();
        _ = reader.ReadUInt16(); // Hint
        return ReadAscii(reader);
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
