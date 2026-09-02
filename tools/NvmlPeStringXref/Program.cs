using System.Buffers.Binary;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text;

if (args.Length is < 2 or > 3 || args[0] is "--help" or "-h")
{
    Console.WriteLine("Usage: NvmlPeStringXref <path-to-pe> <ascii-string> [output-path]");
    return;
}

var inputPath = Path.GetFullPath(args[0]);
var needle = Encoding.ASCII.GetBytes(args[1]);
if (needle.Length == 0 || needle.Any(value => value > 0x7F))
{
    throw new ArgumentException("ascii-string must be non-empty ASCII text.");
}

var outputPath = args.Length == 3 ? Path.GetFullPath(args[2]) : null;
var report = StringXref.Create(inputPath, needle, args[1]);
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

internal sealed record FunctionRange(int Start, int End)
{
    public bool Contains(int rva) => rva >= Start && rva < End;
}

internal sealed record Reference(int InstructionRva, string Kind, string Register, FunctionRange? Function);

internal static class StringXref
{
    private const uint ImageScnMemExecute = 0x20000000;

    public static string Create(string inputPath, byte[] needle, string displayNeedle)
    {
        var bytes = File.ReadAllBytes(inputPath);
        using var image = new PEReader(new MemoryStream(bytes, writable: false));
        var headers = image.PEHeaders;
        var peHeader = headers.PEHeader ?? throw new InvalidDataException("The file does not have a PE header.");
        var functions = ReadFunctionRanges(image, peHeader.ExceptionTableDirectory);
        var rawOffsets = FindAll(bytes, needle).ToList();

        var report = new StringBuilder();
        report.AppendLine("# PE ASCII-string xref scan");
        report.AppendLine($"path={inputPath}");
        report.AppendLine($"sha256={Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant()}");
        report.AppendLine($"ascii_string={displayNeedle}");
        report.AppendLine("method=raw ASCII match; x86-64 RIP-relative LEA and mov-imm64 references in executable PE sections; exception-table function ranges");
        report.AppendLine("limit=this is a bounded static scan, not a full disassembly; it does not prove execution, catch computed/pointer-table references, or link an xref to a dynamic call without a trace");
        report.AppendLine();

        if (rawOffsets.Count == 0)
        {
            report.AppendLine("No raw ASCII matches found.");
            return report.ToString();
        }

        foreach (var rawOffset in rawOffsets)
        {
            report.AppendLine($"[string raw_offset=0x{rawOffset:X8}");
            if (!TryGetRva(headers, rawOffset, out var stringRva))
            {
                report.AppendLine(" rva=unmapped]");
                continue;
            }

            report.AppendLine($" rva=0x{stringRva:X8}]");
            var references = FindReferences(bytes, headers, peHeader.ImageBase, stringRva, functions).ToList();
            if (references.Count == 0)
            {
                report.AppendLine("No recognized executable xrefs.");
            }
            else
            {
                foreach (var reference in references)
                {
                    var range = reference.Function is null
                        ? "function_range=none"
                        : $"function_range=0x{reference.Function.Start:X8}-0x{reference.Function.End:X8}";
                    report.AppendLine($"xref instruction_rva=0x{reference.InstructionRva:X8} kind={reference.Kind} register={reference.Register} {range}");
                }
            }

            report.AppendLine();
        }

        return report.ToString();
    }

    private static IEnumerable<int> FindAll(byte[] bytes, byte[] needle)
    {
        for (var offset = 0; offset <= bytes.Length - needle.Length; offset++)
        {
            if (bytes.AsSpan(offset, needle.Length).SequenceEqual(needle))
            {
                yield return offset;
            }
        }
    }

    private static IEnumerable<Reference> FindReferences(byte[] bytes, PEHeaders headers, ulong imageBase, int targetRva, IReadOnlyList<FunctionRange> functions)
    {
        foreach (var section in headers.SectionHeaders.Where(section => ((uint)section.SectionCharacteristics & ImageScnMemExecute) != 0))
        {
            var rawStart = checked((int)section.PointerToRawData);
            var rawEnd = checked(rawStart + (int)section.SizeOfRawData);
            for (var fileOffset = rawStart; fileOffset < rawEnd; fileOffset++)
            {
                var instructionRva = checked((int)((long)section.VirtualAddress + fileOffset - rawStart));
                if (fileOffset + 7 <= rawEnd && bytes[fileOffset] is >= 0x48 and <= 0x4F && bytes[fileOffset + 1] == 0x8D)
                {
                    var modRm = bytes[fileOffset + 2];
                    if ((modRm & 0xC7) == 0x05)
                    {
                        var displacement = BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(fileOffset + 3, sizeof(int)));
                        var resolvedRva = checked((int)((long)instructionRva + 7 + displacement));
                        if (resolvedRva == targetRva)
                        {
                            yield return new Reference(instructionRva, "lea-rip-relative", RegisterName(bytes[fileOffset], (modRm >> 3) & 7), FunctionAt(functions, instructionRva));
                        }
                    }
                }

                if (fileOffset + 10 <= rawEnd && bytes[fileOffset] == 0x48 && bytes[fileOffset + 1] is >= 0xB8 and <= 0xBF)
                {
                    var immediate = BinaryPrimitives.ReadUInt64LittleEndian(bytes.AsSpan(fileOffset + 2, sizeof(ulong)));
                    if (immediate == imageBase + (uint)targetRva)
                    {
                        yield return new Reference(instructionRva, "mov-imm64", RegisterName(0x48, bytes[fileOffset + 1] & 7), FunctionAt(functions, instructionRva));
                    }
                }
            }
        }
    }

    private static string RegisterName(byte rex, int encodedRegister)
    {
        var index = encodedRegister + (((rex & 0x04) != 0) ? 8 : 0);
        return index switch
        {
            0 => "rax", 1 => "rcx", 2 => "rdx", 3 => "rbx", 4 => "rsp", 5 => "rbp", 6 => "rsi", 7 => "rdi",
            8 => "r8", 9 => "r9", 10 => "r10", 11 => "r11", 12 => "r12", 13 => "r13", 14 => "r14", 15 => "r15",
            _ => throw new ArgumentOutOfRangeException(nameof(encodedRegister)),
        };
    }

    private static FunctionRange? FunctionAt(IReadOnlyList<FunctionRange> functions, int rva) => functions.FirstOrDefault(range => range.Contains(rva));

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
            _ = reader.ReadUInt32();
            if (end > start)
            {
                functions.Add(new FunctionRange(start, end));
            }
        }

        return functions.OrderBy(range => range.Start).ToList();
    }

    private static bool TryGetRva(PEHeaders headers, int rawOffset, out int rva)
    {
        foreach (var section in headers.SectionHeaders)
        {
            var rawStart = (long)section.PointerToRawData;
            var rawEnd = rawStart + section.SizeOfRawData;
            if (rawOffset >= rawStart && rawOffset < rawEnd)
            {
                rva = checked((int)((long)section.VirtualAddress + rawOffset - rawStart));
                return true;
            }
        }

        rva = 0;
        return false;
    }
}
