using System;
using System.Buffers.Binary;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace PazGui.Models;

public static class PamtExtractor
{
    private const int DdsHeaderSize = 128;
    private static readonly byte[] DdsMagic = "DDS "u8.ToArray();

    /// <summary>
    /// Decompress LZ4-compressed pixel data embedded inside a DDS file.
    /// Handles per-mip-level compression: reserved[0..10] store per-mip stored sizes.
    /// Returns true if decompression was performed.
    /// </summary>
    private static bool TryDecompressDdsInternal(ref byte[] data)
    {
        if (data.Length <= DdsHeaderSize)
            return false;
        if (data[0] != DdsMagic[0] || data[1] != DdsMagic[1] ||
            data[2] != DdsMagic[2] || data[3] != DdsMagic[3])
            return false;

        uint reserved0 = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x20));
        if (reserved0 == 0)
            return false;

        uint height = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x0C));
        uint width = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x10));
        if (width == 0 || height == 0)
            return false;

        uint mipCount = Math.Max(1, BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x1C)));
        uint bpp = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x58));
        uint reserved1 = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x24));
        uint actualDataSize = (uint)(data.Length - DdsHeaderSize);

        // Build per-mip stored/natural sizes
        var storedSizes = new List<uint>();
        var naturalSizes = new List<uint>();

        for (int i = 0; i < (int)mipCount; i++)
        {
            uint natural;
            if (bpp > 0)
            {
                uint mw = Math.Max(1, width >> i);
                uint mh = Math.Max(1, height >> i);
                natural = mw * mh * (bpp / 8);
            }
            else if (i == 0)
            {
                if (reserved1 == 0) return false;
                natural = reserved1;
            }
            else
            {
                if (i >= 11) break;
                uint r = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x20 + i * 4));
                if (r == 0) break;
                natural = r;
            }

            uint stored;
            if (i < 11)
            {
                stored = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(0x20 + i * 4));
                if (stored == 0) stored = natural;
            }
            else
            {
                stored = natural;
            }

            storedSizes.Add(stored);
            naturalSizes.Add(natural);
        }

        // Validate sum
        uint totalStored = 0;
        foreach (var s in storedSizes) totalStored += s;
        if (totalStored != actualDataSize)
            return false;

        // Check any compressed
        bool anyCompressed = false;
        for (int i = 0; i < storedSizes.Count; i++)
            if (storedSizes[i] < naturalSizes[i]) { anyCompressed = true; break; }
        if (!anyCompressed)
            return false;

        // Decompress each mip
        using var output = new MemoryStream();
        output.Write(data, 0, DdsHeaderSize);

        int offset = DdsHeaderSize;
        for (int i = 0; i < storedSizes.Count; i++)
        {
            uint stored = storedSizes[i];
            uint natural = naturalSizes[i];

            if (stored < natural)
            {
                var compressed = data.AsSpan(offset, (int)stored).ToArray();
                var decompressed = PazNative.Lz4Decompress(compressed, natural);
                if (decompressed == null) return false;
                output.Write(decompressed);
            }
            else
            {
                output.Write(data, offset, (int)stored);
            }
            offset += (int)stored;
        }

        var result = output.ToArray();
        // Clear all reserved fields
        for (int i = 0; i < 11; i++)
            BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(0x20 + i * 4), 0);
        data = result;
        return true;
    }

    public static async Task<(int Extracted, int Decrypted, int Decompressed)> ExtractAllAsync(
        IReadOnlyList<FileEntry> entries,
        string outputDir,
        IProgress<(int Current, int Total, int Decrypted, int Decompressed)>? progress = null,
        CancellationToken ct = default)
    {
        return await Task.Run(() =>
        {
            int total = entries.Count;
            int decrypted = 0;
            int decompressed = 0;

            for (int i = 0; i < total; i++)
            {
                ct.ThrowIfCancellationRequested();

                var entry = entries[i];
                uint readSize = entry.CompressedSize > 0
                    ? entry.CompressedSize
                    : entry.OriginalSize;

                string relPath = entry.FullPath.Replace('\\', '/');
                string outPath = Path.Combine(outputDir, relPath.Replace('/', Path.DirectorySeparatorChar));

                string? dir = Path.GetDirectoryName(outPath);
                if (dir != null)
                    Directory.CreateDirectory(dir);

                using var paz = new FileStream(entry.PazFilePath, FileMode.Open, FileAccess.Read, FileShare.Read);
                paz.Seek(entry.Offset, SeekOrigin.Begin);

                var buffer = new byte[readSize];
                paz.ReadExactly(buffer);

                // Decrypt XML files using filename-derived key
                if (IsXmlFile(entry.FullPath))
                {
                    string basename = Path.GetFileName(entry.FullPath);
                    buffer = PazNative.Decrypt(buffer, basename);
                    decrypted++;

                    // Decompress after decryption if LZ4
                    if (entry.IsCompressed && entry.CompressionType == 2)
                    {
                        var decompData = PazNative.Lz4Decompress(buffer, entry.OriginalSize);
                        if (decompData != null)
                        {
                            buffer = decompData;
                            decompressed++;
                        }
                    }
                }
                else if (entry.IsCompressed && entry.CompressionType == 2)
                {
                    var decompData = PazNative.Lz4Decompress(buffer, entry.OriginalSize);
                    if (decompData != null)
                    {
                        buffer = decompData;
                        decompressed++;
                    }
                }

                TryDecompressDdsInternal(ref buffer);

                File.WriteAllBytes(outPath, buffer);

                if (i % 50 == 0 || i == total - 1)
                    progress?.Report((i + 1, total, decrypted, decompressed));
            }

            return (total, decrypted, decompressed);
        }, ct);
    }

    private static bool IsXmlFile(string path)
    {
        return path.EndsWith(".xml", StringComparison.OrdinalIgnoreCase);
    }
}
