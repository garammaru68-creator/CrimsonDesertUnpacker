#include "PamtExtractor.h"
#include "Lz4.h"
#include <fstream>
#include <cstring>
#include <filesystem>

namespace fs = std::filesystem;

namespace paz {

static constexpr uint32_t DDS_HEADER_SIZE = 128;
static constexpr uint32_t DDS_MAGIC = 0x20534444; // "DDS "

/// Decompress LZ4-compressed pixel data embedded inside a DDS file in-place.
/// Handles per-mip-level compression: reserved[0..10] store per-mip stored sizes.
static void ddsDecompressInternal(std::vector<uint8_t> &data) {
    if (data.size() <= DDS_HEADER_SIZE)
        return;

    uint32_t magic;
    std::memcpy(&magic, data.data(), 4);
    if (magic != DDS_MAGIC)
        return;

    uint32_t reserved0;
    std::memcpy(&reserved0, data.data() + 0x20, 4);
    if (reserved0 == 0)
        return;

    uint32_t height, width, bpp, mipCount, reserved1;
    std::memcpy(&height,   data.data() + 0x0C, 4);
    std::memcpy(&width,    data.data() + 0x10, 4);
    std::memcpy(&mipCount, data.data() + 0x1C, 4);
    std::memcpy(&bpp,      data.data() + 0x58, 4);
    std::memcpy(&reserved1,data.data() + 0x24, 4);
    if (width == 0 || height == 0)
        return;
    if (mipCount == 0) mipCount = 1;

    uint32_t actualDataSize = static_cast<uint32_t>(data.size()) - DDS_HEADER_SIZE;

    // Build per-mip stored/natural sizes
    std::vector<uint32_t> storedSizes, naturalSizes;
    for (uint32_t i = 0; i < mipCount; i++) {
        uint32_t natural;
        if (bpp > 0) {
            uint32_t mw = std::max(1u, width >> i);
            uint32_t mh = std::max(1u, height >> i);
            natural = mw * mh * (bpp / 8);
        } else if (i == 0) {
            if (reserved1 == 0) return;
            natural = reserved1;
        } else {
            if (i >= 11) break;
            uint32_t r;
            std::memcpy(&r, data.data() + 0x20 + i * 4, 4);
            if (r == 0) break;
            natural = r;
        }

        uint32_t stored;
        if (i < 11) {
            std::memcpy(&stored, data.data() + 0x20 + i * 4, 4);
            if (stored == 0) stored = natural;
        } else {
            stored = natural;
        }

        storedSizes.push_back(stored);
        naturalSizes.push_back(natural);
    }

    // Validate sum
    uint32_t totalStored = 0;
    for (auto s : storedSizes) totalStored += s;
    if (totalStored != actualDataSize)
        return;

    // Check any compressed
    bool anyCompressed = false;
    for (size_t i = 0; i < storedSizes.size(); i++)
        if (storedSizes[i] < naturalSizes[i]) { anyCompressed = true; break; }
    if (!anyCompressed)
        return;

    // Decompress each mip
    std::vector<uint8_t> result;
    result.reserve(DDS_HEADER_SIZE + actualDataSize * 2);
    result.insert(result.end(), data.data(), data.data() + DDS_HEADER_SIZE);

    uint32_t offset = DDS_HEADER_SIZE;
    for (size_t i = 0; i < storedSizes.size(); i++) {
        if (storedSizes[i] < naturalSizes[i]) {
            auto decompressed = lz4Decompress(data.data() + offset, storedSizes[i], naturalSizes[i]);
            if (decompressed.empty()) return;
            result.insert(result.end(), decompressed.begin(), decompressed.end());
        } else {
            result.insert(result.end(), data.data() + offset, data.data() + offset + storedSizes[i]);
        }
        offset += storedSizes[i];
    }

    // Clear all reserved fields
    uint32_t zero = 0;
    for (int i = 0; i < 11; i++)
        std::memcpy(result.data() + 0x20 + i * 4, &zero, 4);

    data = std::move(result);
}

std::vector<uint8_t> pamtExtractToMemory(const FileEntry &entry) {
    std::ifstream pazFile(entry.pazFilePath, std::ios::binary);
    if (!pazFile.is_open())
        return {};

    // PAMT format stores files as-is in the PAZ (no encryption).
    // compressedSize is the actual stored size; originalSize may be larger
    // (e.g. full-mip DDS) but the stored data is already a valid file.
    uint32_t readSize = entry.compressedSize > 0
                        ? entry.compressedSize : entry.originalSize;

    std::vector<uint8_t> raw(readSize);
    pazFile.seekg(entry.offset);
    pazFile.read(reinterpret_cast<char *>(raw.data()), readSize);

    return raw;
}

bool pamtExtractToFile(const FileEntry &entry, const std::string &outputPath) {
    try {
        auto data = pamtExtractToMemory(entry);
        if (data.empty() && entry.originalSize > 0)
            return false;

        ddsDecompressInternal(data);

        fs::path p(outputPath);
        if (p.has_parent_path())
            fs::create_directories(p.parent_path());

        std::ofstream out(outputPath, std::ios::binary);
        if (!out.is_open()) return false;
        out.write(reinterpret_cast<const char *>(data.data()), data.size());
        return true;
    } catch (...) {
        return false;
    }
}

static std::string normalizePath(const std::string &path) {
    std::string result = path;
    for (auto &c : result) {
        if (c == '\\') c = '/';
    }
    return result;
}

void pamtExtractAll(const std::vector<FileEntry> &entries,
                    const std::string &outputDir,
                    ProgressCallback progress) {
    uint32_t total = static_cast<uint32_t>(entries.size());
    uint32_t idx = 0;

    for (auto &entry : entries) {
        std::string relPath = normalizePath(entry.fullPath);
        fs::path outPath = fs::path(outputDir) / relPath;
        pamtExtractToFile(entry, outPath.string());

        idx++;
        if (progress) progress(idx, total);
    }
}

} // namespace paz
