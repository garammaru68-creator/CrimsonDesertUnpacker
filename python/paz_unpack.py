"""PAZ archive unpacker for Crimson Desert.

Extracts files from PAZ archives, with automatic decryption (ChaCha20)
and decompression (LZ4) based on PAMT metadata.

Usage:
    # Extract everything
    python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/

    # Extract only XML files
    python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/ --filter "*.xml"

    # Extract a single file by path
    python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/ \
        --filter "technique/rendererconfiguration.xml"

    # Dry run (list what would be extracted)
    python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 --dry-run
"""

import os
import sys
import struct
import fnmatch
import argparse

from paz_parse import parse_pamt, PazEntry
from paz_crypto import decrypt, lz4_decompress


DDS_HEADER_SIZE = 128
DDS_MAGIC = b'DDS '


def _dds_mip_natural_size(width: int, height: int, bpp: int, mip: int) -> int:
    """Calculate the natural (uncompressed) byte size for a single mip level."""
    mw = max(1, width >> mip)
    mh = max(1, height >> mip)
    return mw * mh * (bpp // 8)


def _try_decompress_dds_internal(data: bytes) -> tuple[bytes, bool]:
    """Decompress LZ4-compressed pixel data embedded inside a DDS file.

    Crimson Desert DDS files store per-mip-level sizes in the reserved[0..10]
    header fields. If a mip's stored size is smaller than its natural size,
    that chunk is LZ4-compressed.

    Returns (data, was_decompressed).
    """
    if len(data) <= DDS_HEADER_SIZE or data[:4] != DDS_MAGIC:
        return data, False

    reserved0 = struct.unpack_from('<I', data, 0x20)[0]
    if reserved0 == 0:
        return data, False

    height = struct.unpack_from('<I', data, 0x0C)[0]
    width = struct.unpack_from('<I', data, 0x10)[0]
    mipcount = max(1, struct.unpack_from('<I', data, 0x1C)[0])
    if width == 0 or height == 0:
        return data, False

    bpp = struct.unpack_from('<I', data, 0x58)[0]
    if bpp == 0:
        # Block-compressed (DXT/BC): use reserved[1] to get mip0 expected size
        reserved1 = struct.unpack_from('<I', data, 0x24)[0]
        if reserved1 == 0:
            return data, False
        bpp_effective = 0
    else:
        bpp_effective = bpp

    actual_data_size = len(data) - DDS_HEADER_SIZE

    # Build per-mip stored sizes and natural sizes
    stored_sizes = []
    natural_sizes = []
    for i in range(mipcount):
        if bpp_effective > 0:
            natural = _dds_mip_natural_size(width, height, bpp_effective, i)
        elif i == 0:
            natural = reserved1
        else:
            # For block-compressed, smaller mips beyond reserved are untracked
            if i < 11:
                r = struct.unpack_from('<I', data, 0x20 + i * 4)[0]
                natural = r if r > 0 else 0
            else:
                natural = 0
            if natural == 0:
                break

        if i < 11:
            stored = struct.unpack_from('<I', data, 0x20 + i * 4)[0]
            if stored == 0:
                stored = natural
        else:
            stored = natural

        stored_sizes.append(stored)
        natural_sizes.append(natural)

    # Validate: sum of stored sizes must equal actual data
    total_stored = sum(stored_sizes)
    if total_stored != actual_data_size:
        return data, False

    # Check if any mip is actually compressed
    any_compressed = any(s < n for s, n in zip(stored_sizes, natural_sizes))
    if not any_compressed:
        return data, False

    # Decompress each mip level
    offset = DDS_HEADER_SIZE
    chunks = []
    for stored, natural in zip(stored_sizes, natural_sizes):
        chunk = data[offset:offset + stored]
        if stored < natural:
            chunk = lz4_decompress(chunk, natural)
        chunks.append(chunk)
        offset += stored

    header = bytearray(data[:DDS_HEADER_SIZE])
    # Clear all reserved fields
    for i in range(11):
        struct.pack_into('<I', header, 0x20 + i * 4, 0)
    return bytes(header) + b''.join(chunks), True


def extract_entry(entry: PazEntry, output_dir: str, decrypt_xml: bool = True) -> dict:
    """Extract a single entry from a PAZ archive.

    Args:
        entry: parsed PAMT entry
        output_dir: base directory for extracted files
        decrypt_xml: whether to decrypt XML files (default: True)

    Returns:
        dict with extraction info (decrypted, decompressed, size)
    """
    result = {"decrypted": False, "decompressed": False}

    read_size = entry.comp_size if entry.compressed else entry.orig_size

    with open(entry.paz_file, 'rb') as f:
        f.seek(entry.offset)
        data = f.read(read_size)

    # Decrypt encrypted files (XML and .paloc localization files)
    basename = os.path.basename(entry.path)
    is_paloc = entry.path.lower().endswith('.paloc')
    if decrypt_xml and (entry.encrypted or is_paloc):
        data = decrypt(data, basename)
        result["decrypted"] = True

    # Decompress LZ4
    if entry.compressed and entry.compression_type == 2:
        data = lz4_decompress(data, entry.orig_size)
        result["decompressed"] = True

    # Decompress DDS-internal LZ4 (pixel data compressed inside the DDS)
    data, dds_decomp = _try_decompress_dds_internal(data)
    result["dds_decompressed"] = dds_decomp

    # Write to disk
    rel_path = entry.path.replace('\\', '/').replace('/', os.sep)
    out_path = os.path.join(output_dir, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, 'wb') as f:
        f.write(data)

    result["size"] = len(data)
    result["path"] = out_path
    return result


def extract_all(entries: list[PazEntry], output_dir: str,
                decrypt_xml: bool = True, verbose: bool = False) -> dict:
    """Extract all entries from PAZ archives.

    Returns:
        dict with summary stats
    """
    total = len(entries)
    decrypted = 0
    decompressed = 0
    dds_decompressed = 0
    errors = 0

    for i, entry in enumerate(entries):
        try:
            result = extract_entry(entry, output_dir, decrypt_xml)
            if result["decrypted"]:
                decrypted += 1
            if result["decompressed"]:
                decompressed += 1
            if result.get("dds_decompressed"):
                dds_decompressed += 1
            if verbose:
                flags = []
                if result["decrypted"]: flags.append("decrypted")
                if result["decompressed"]: flags.append("decompressed")
                if result.get("dds_decompressed"): flags.append("dds-lz4")
                extra = f" [{', '.join(flags)}]" if flags else ""
                print(f"  [{i+1}/{total}] {entry.path}{extra}")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {entry.path}: {e}", file=sys.stderr)

        if not verbose and (i + 1) % 100 == 0:
            print(f"  {i+1}/{total}...", end='\r')

    if not verbose:
        print()

    return {
        "total": total,
        "decrypted": decrypted,
        "decompressed": decompressed,
        "dds_decompressed": dds_decompressed,
        "errors": errors,
    }


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract files from PAZ archives")
    parser.add_argument("pamt", help="Path to .pamt index file")
    parser.add_argument("--paz-dir", help="Directory containing .paz files")
    parser.add_argument("-o", "--output", default="output", help="Output directory (default: output/)")
    parser.add_argument("--filter", help="Filter by glob pattern (e.g. '*.xml')")
    parser.add_argument("--no-decrypt", action="store_true", help="Skip XML decryption")
    parser.add_argument("--dry-run", action="store_true", help="List files without extracting")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show each file as it's extracted")
    args = parser.parse_args()

    print(f"Parsing {args.pamt}...")
    entries = parse_pamt(args.pamt, paz_dir=args.paz_dir)
    print(f"Found {len(entries):,} entries")

    if args.filter:
        pattern = args.filter.lower()
        entries = [e for e in entries
                   if fnmatch.fnmatch(e.path.lower(), pattern)
                   or fnmatch.fnmatch(os.path.basename(e.path).lower(), pattern)
                   or pattern in e.path.lower()]
        print(f"Filtered to {len(entries):,} entries matching '{args.filter}'")

    if not entries:
        print("Nothing to extract.")
        return

    if args.dry_run:
        for e in entries:
            comp = "LZ4" if e.compression_type == 2 else "   "
            enc = "ENC" if e.encrypted else "   "
            print(f"  [{comp}] [{enc}] {e.comp_size:>10,} -> {e.orig_size:>10,}  {e.path}")
        print(f"\n{len(entries):,} entries (dry run)")
        return

    print(f"Extracting to {args.output}/...")
    stats = extract_all(entries, args.output,
                        decrypt_xml=not args.no_decrypt,
                        verbose=args.verbose)

    parts = [f"{stats['total']} extracted"]
    if stats["decrypted"]: parts.append(f"{stats['decrypted']} decrypted")
    if stats["decompressed"]: parts.append(f"{stats['decompressed']} decompressed")
    if stats["dds_decompressed"]: parts.append(f"{stats['dds_decompressed']} dds-lz4")
    if stats["errors"]: parts.append(f"{stats['errors']} errors")
    print(f"Done: {', '.join(parts)}")


if __name__ == "__main__":
    main()
