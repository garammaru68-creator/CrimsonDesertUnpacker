"""PABGB/PABGH binary data parser for Crimson Desert.

Parses .pabgh (index) + .pabgb (data) file pairs and extracts records
with names and XYZ world coordinates.

Usage:
    # Parse a single file pair
    python pabg_parse.py /path/to/factionnode.pabgb

    # Export to CSV
    python pabg_parse.py /path/to/factionnode.pabgb --csv output.csv

    # Parse all .pabgb files in a directory
    python pabg_parse.py /path/to/gamedata/ --all --csv all_data.csv

    # Filter by name pattern
    python pabg_parse.py /path/to/factionnode.pabgb --filter "Village"
"""

import struct
import os
import csv
import argparse
import fnmatch
from dataclasses import dataclass


@dataclass
class PabgRecord:
    """A single record from a PABGB file."""
    source: str       # source filename (without extension)
    type_id: int      # uint16 type identifier
    name: str         # record name string
    x: float          # world X coordinate
    y: float          # world Y (altitude) coordinate
    z: float          # world Z coordinate
    has_coords: bool  # whether valid coordinates were found


def parse_pabgh(path: str) -> list[tuple[int, int, int]]:
    """Parse a .pabgh index file.

    Returns list of (type_id, flags, offset) tuples.
    """
    with open(path, 'rb') as f:
        data = f.read()

    count = struct.unpack_from('<H', data, 0)[0]
    entries = []
    for i in range(count):
        off = 2 + i * 8
        if off + 8 > len(data):
            break
        type_id = struct.unpack_from('<H', data, off)[0]
        flags = struct.unpack_from('<H', data, off + 2)[0]
        offset = struct.unpack_from('<I', data, off + 4)[0]
        entries.append((type_id, flags, offset))

    return entries


def _find_coords(rec: bytes, name_end: int) -> tuple[float, float, float] | None:
    """Search for a float32 XYZ triplet in the record after the name.

    Uses two strategies:
      1. Fixed offset right after null-terminated name (actionpointinfo style)
      2. Scanning for plausible world coordinate triplets (factionnode style)
    """
    # Strategy 1: coords at name_end + 1 (null terminator)
    off = name_end + 1
    if off + 12 <= len(rec):
        x = struct.unpack_from('<f', rec, off)[0]
        y = struct.unpack_from('<f', rec, off + 4)[0]
        z = struct.unpack_from('<f', rec, off + 8)[0]
        if (abs(x) > 50 and abs(x) < 100000 and
                abs(y) > 1 and abs(y) < 10000 and
                abs(z) > 50 and abs(z) < 100000):
            return (x, y, z)

    # Strategy 2: scan forward for plausible triplet
    for j in range(name_end, min(len(rec) - 11, name_end + 300)):
        f1 = struct.unpack_from('<f', rec, j)[0]
        f2 = struct.unpack_from('<f', rec, j + 4)[0]
        f3 = struct.unpack_from('<f', rec, j + 8)[0]
        if (abs(f1) > 100 and abs(f1) < 100000 and
                abs(f2) > 5 and abs(f2) < 10000 and
                abs(f3) > 100 and abs(f3) < 100000):
            return (f1, f2, f3)

    return None


def parse_pabgb(bpath: str, hpath: str | None = None) -> list[PabgRecord]:
    """Parse a .pabgb data file using its .pabgh index.

    Args:
        bpath: path to .pabgb file
        hpath: path to .pabgh file (auto-detected if None)

    Returns:
        list of PabgRecord
    """
    if hpath is None:
        hpath = bpath.replace('.pabgb', '.pabgh')
    if not os.path.exists(hpath):
        raise FileNotFoundError(f"Index file not found: {hpath}")

    source = os.path.splitext(os.path.basename(bpath))[0]

    index = parse_pabgh(hpath)

    with open(bpath, 'rb') as f:
        bdata = f.read()

    records = []
    for i, (type_id, flags, offset) in enumerate(index):
        # Determine record end
        if i + 1 < len(index):
            next_offset = index[i + 1][2]
        else:
            next_offset = len(bdata)

        rec = bdata[offset:next_offset]
        if len(rec) < 12:
            continue

        # Parse name: uint16 type, uint16 pad, uint32 name_len, char[name_len]
        name_len = struct.unpack_from('<I', rec, 4)[0]
        if name_len > 500 or 8 + name_len > len(rec):
            continue

        name = rec[8:8 + name_len].decode('ascii', errors='replace').rstrip('\x00')
        name_end = 8 + name_len

        # Find coordinates
        coords = _find_coords(rec, name_end)
        if coords:
            x, y, z = coords
            records.append(PabgRecord(source, type_id, name, x, y, z, True))
        else:
            records.append(PabgRecord(source, type_id, name, 0.0, 0.0, 0.0, False))

    return records


def export_csv(records: list[PabgRecord], path: str, coords_only: bool = True):
    """Export records to CSV."""
    if coords_only:
        records = [r for r in records if r.has_coords]

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source', 'type_id', 'name', 'x', 'y', 'z'])
        for r in records:
            writer.writerow([r.source, f'0x{r.type_id:04X}', r.name,
                             f'{r.x:.2f}', f'{r.y:.2f}', f'{r.z:.2f}'])

    print(f"Exported {len(records)} records to {path}")


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Parse Crimson Desert PABGB data files")
    parser.add_argument("path", help="Path to .pabgb file or directory")
    parser.add_argument("--all", action="store_true", help="Parse all .pabgb files in directory")
    parser.add_argument("--csv", help="Export to CSV file")
    parser.add_argument("--filter", help="Filter records by name pattern")
    parser.add_argument("--include-no-coords", action="store_true",
                        help="Include records without coordinates")
    args = parser.parse_args()

    all_records: list[PabgRecord] = []

    if args.all and os.path.isdir(args.path):
        for fname in sorted(os.listdir(args.path)):
            if fname.endswith('.pabgb'):
                bpath = os.path.join(args.path, fname)
                try:
                    records = parse_pabgb(bpath)
                    all_records.extend(records)
                    with_coords = sum(1 for r in records if r.has_coords)
                    print(f"  {fname}: {len(records)} records ({with_coords} with coords)")
                except Exception as e:
                    print(f"  {fname}: ERROR - {e}")
    elif os.path.isfile(args.path):
        all_records = parse_pabgb(args.path)
    else:
        print(f"Error: {args.path} not found")
        return

    # Filter
    if args.filter:
        pattern = args.filter.lower()
        all_records = [r for r in all_records
                       if fnmatch.fnmatch(r.name.lower(), f'*{pattern}*')]

    # Display
    coords_only = not args.include_no_coords
    display = [r for r in all_records if r.has_coords or not coords_only]

    if not args.csv:
        for r in display:
            if r.has_coords:
                print(f"  [{r.source}] {r.name:<60s}  ({r.x:>9.1f}, {r.y:>6.1f}, {r.z:>9.1f})")
            else:
                print(f"  [{r.source}] {r.name:<60s}  (no coords)")

    total = len(all_records)
    with_coords = sum(1 for r in all_records if r.has_coords)
    print(f"\nTotal: {total} records, {with_coords} with coordinates")

    # Export
    if args.csv:
        export_csv(all_records, args.csv, coords_only=coords_only)


if __name__ == "__main__":
    main()
