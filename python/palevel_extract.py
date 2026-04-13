"""PARC palevel resource node extractor for Crimson Desert.

Scans .palevel files (PARC format) to extract resource object placements
with world coordinates. Uses heuristic matching: finds resource path references
in the file's resource table, then associates them with nearby float32 XYZ
coordinate triplets.

Usage:
    # Scan a single palevel file
    python palevel_extract.py /path/to/sector_-16_14.palevel

    # Scan all sector palevel files in a directory
    python palevel_extract.py /path/to/leveldata/ --all

    # Filter for specific resource types
    python palevel_extract.py /path/to/leveldata/ --all --filter "mine"

    # Export to CSV
    python palevel_extract.py /path/to/leveldata/ --all --filter "mine" --csv mines.csv
"""

import struct
import re
import os
import csv
import argparse
from dataclasses import dataclass, field


@dataclass
class PalevelPlacement:
    """A placed object extracted from a .palevel file."""
    sector: str        # source sector filename
    resource: str      # resource path (basename)
    resource_full: str # full resource path
    x: float
    y: float           # altitude
    z: float
    resource_type: str = ""  # classified type (mine, collect, etc.)


def _parse_resource_table(data: bytes) -> dict[int, str]:
    """Extract the resource path table from PARC data.

    Returns {index: path_string} mapping.
    """
    table = {}
    for m in re.finditer(rb'(object|leveldata)/[\x20-\x7e]+?\.pami', data):
        off = m.start()
        path_str = m.group().decode('ascii')
        # uint32 index is 8 bytes before the path string
        # format: uint32 prev_idx, uint32 str_len, char[str_len]
        idx_off = off - 8
        if idx_off >= 0:
            res_idx = struct.unpack_from('<I', data, idx_off)[0]
            if res_idx < 100000:  # sanity check
                table[res_idx] = path_str
    return table


def _classify_resource(path: str) -> str:
    """Classify a resource path into a type category."""
    p = path.lower()
    basename = p.split('/')[-1]

    if 'mine_gold' in p or 'goldstone' in p:
        return 'gold'
    elif 'mine_iron' in p or 'ironstone' in p:
        return 'iron'
    elif 'mine_copper' in p or 'copperstone' in p:
        return 'copper'
    elif 'mine_silver' in p or 'silverstone' in p:
        return 'silver'
    elif 'mine_diamond' in p:
        return 'diamond'
    elif 'mine_ruby' in p:
        return 'ruby'
    elif 'mine_bismuth' in p:
        return 'bismuth'
    elif 'mine_bluestone' in p or 'azurite' in p:
        return 'bluestone'
    elif 'mine_redstone' in p or 'firestone' in p:
        return 'redstone'
    elif 'mine_whitestone' in p:
        return 'whitestone'
    elif 'mine_greenstone' in p or 'emerald' in p:
        return 'greenstone'
    elif 'mine_coal' in p:
        return 'coal'
    elif 'mine_tin' in p:
        return 'tin'
    elif 'mine_salt' in p:
        return 'salt'
    elif 'mine_sapphire' in p:
        return 'sapphire'
    elif 'mine_meteor' in p:
        return 'meteor'
    elif 'mercury' in p:
        return 'mercury'
    elif 'sulfur' in p:
        return 'sulfur'
    elif 'cinnabar' in p:
        return 'cinnabar'
    elif 'epidote' in p:
        return 'epidote'
    elif 'mine_rock' in p or 'mine_stone' in p:
        return 'stone'
    elif 'mine' in p:
        return 'mine_other'
    elif 'collect' in p or 'bush' in p:
        return 'collect'
    elif 'farm' in p:
        return 'farm'
    elif 'chaya' in p:
        return 'chaya'
    elif 'ensete' in p:
        return 'ensete'
    elif 'kudzu' in p:
        return 'kudzu'
    elif 'dulse' in p:
        return 'dulse'
    elif 'amaranth' in p:
        return 'amaranth'
    elif 'taro' in p:
        return 'taro'
    elif 'chlorella' in p:
        return 'chlorella'
    elif 'jijeongta' in p:
        return 'jijeongta'
    elif 'opuntia' in p:
        return 'opuntia'
    elif 'herb' in p:
        return 'herb'
    elif 'rubber' in p:
        return 'rubber'
    elif 'fish' in p:
        return 'fish'
    elif 'lumber' in p or 'timber' in p or 'wood' in p:
        return 'wood'
    else:
        return 'other'


def _find_coords(data: bytes, start: int = 0) -> list[tuple[int, float, float, float]]:
    """Find all float32 XYZ coordinate triplets in data.

    Returns [(offset, x, y, z), ...] for values that look like world coordinates.
    """
    coords = []
    for j in range(start, len(data) - 11, 4):
        f1 = struct.unpack_from('<f', data, j)[0]
        f2 = struct.unpack_from('<f', data, j + 4)[0]
        f3 = struct.unpack_from('<f', data, j + 8)[0]
        if (abs(f1) > 500 and abs(f1) < 100000 and
                abs(f2) > 5 and abs(f2) < 10000 and
                abs(f3) > 500 and abs(f3) < 100000 and
                f1 != f2 and f2 != f3):
            coords.append((j, f1, f2, f3))
    return coords


def _dedup_coords(coords: list[tuple[int, float, float, float]]) -> list[tuple[int, float, float, float]]:
    """Remove duplicate coords from _worldTransform/_tiledTransform pairs (40-byte stride)."""
    if not coords:
        return coords
    skip = set()
    result = []
    for i, (j, x, y, z) in enumerate(coords):
        if j in skip:
            continue
        result.append((j, x, y, z))
        # Mark the 40-byte-later duplicate
        for j2, _, _, _ in coords[i + 1:i + 4]:
            if j2 - j == 40:
                skip.add(j2)
                break
    return result


def parse_palevel(filepath: str, resource_filter: str = "") -> list[PalevelPlacement]:
    """Parse a .palevel file and extract resource placements.

    This uses a heuristic approach: for each resource in the path table
    that matches the filter, find the nearest coordinate triplet.
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if data[:4] != b'PARC':
        return []

    sector = os.path.splitext(os.path.basename(filepath))[0]

    # Build resource table
    res_table = _parse_resource_table(data)
    if not res_table:
        return []

    # Filter resources of interest
    filter_lower = resource_filter.lower()
    target_indices = {}
    for idx, path in res_table.items():
        basename = path.split('/')[-1].replace('.pami', '')
        if filter_lower and filter_lower not in path.lower():
            continue
        rtype = _classify_resource(path)
        if rtype != 'other' or not filter_lower:
            target_indices[idx] = (path, basename, rtype)

    if not target_indices:
        return []

    # Find all coordinates
    coords = _find_coords(data)
    coords = _dedup_coords(coords)

    if not coords:
        return []

    # Strategy: for each coord, check multiple offsets for resource index references
    # and pick the most relevant one
    placements = []
    used_coords = set()

    for coord_off, x, y, z in coords:
        # Scan backward from coord for resource index
        best_match = None
        for dist in range(52, 500, 4):
            ref_off = coord_off - dist
            if ref_off < 0:
                break
            val = struct.unpack_from('<I', data, ref_off)[0]
            if val in target_indices:
                path_full, basename, rtype = target_indices[val]
                best_match = (basename, path_full, rtype)
                break

        if best_match and coord_off not in used_coords:
            basename, path_full, rtype = best_match
            placements.append(PalevelPlacement(
                sector=sector,
                resource=basename,
                resource_full=path_full,
                x=x, y=y, z=z,
                resource_type=rtype
            ))
            used_coords.add(coord_off)

    return placements


def scan_directory(dirpath: str, resource_filter: str = "",
                   verbose: bool = False) -> list[PalevelPlacement]:
    """Scan all .palevel files in a directory."""
    all_placements = []
    palevel_files = sorted(f for f in os.listdir(dirpath) if f.endswith('.palevel'))

    total = len(palevel_files)
    for i, fname in enumerate(palevel_files):
        filepath = os.path.join(dirpath, fname)
        try:
            placements = parse_palevel(filepath, resource_filter)
            if placements:
                all_placements.extend(placements)
                if verbose:
                    print(f"  [{i+1}/{total}] {fname}: {len(placements)} placements")
        except Exception as e:
            if verbose:
                print(f"  [{i+1}/{total}] {fname}: ERROR - {e}")

        if not verbose and (i + 1) % 500 == 0:
            print(f"  {i+1}/{total}...", end='\r')

    if not verbose:
        print()

    return all_placements


def export_csv(placements: list[PalevelPlacement], path: str):
    """Export placements to CSV."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['sector', 'resource_type', 'resource', 'x', 'y', 'z', 'resource_full'])
        for p in placements:
            writer.writerow([p.sector, p.resource_type, p.resource,
                             f'{p.x:.2f}', f'{p.y:.2f}', f'{p.z:.2f}',
                             p.resource_full])
    print(f"Exported {len(placements)} placements to {path}")


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract resource placements from Crimson Desert .palevel files")
    parser.add_argument("path", help="Path to .palevel file or directory")
    parser.add_argument("--all", action="store_true", help="Scan all .palevel files in directory")
    parser.add_argument("--filter", default="mine", help="Resource path filter (default: 'mine')")
    parser.add_argument("--csv", help="Export to CSV file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show each file as processed")
    args = parser.parse_args()

    if args.all and os.path.isdir(args.path):
        print(f"Scanning {args.path} for .palevel files (filter: '{args.filter}')...")
        placements = scan_directory(args.path, args.filter, args.verbose)
    elif os.path.isfile(args.path):
        placements = parse_palevel(args.path, args.filter)
    else:
        print(f"Error: {args.path} not found")
        return

    # Display summary
    from collections import Counter
    type_counts = Counter(p.resource_type for p in placements)
    print(f"\nTotal placements: {len(placements)}")
    print("\nBy resource type:")
    for rtype, count in type_counts.most_common():
        print(f"  {rtype:<20s} {count:>6d}")

    if not args.csv:
        print(f"\nSample placements:")
        for p in placements[:20]:
            print(f"  [{p.resource_type:<12s}] {p.resource:<50s} ({p.x:>9.1f}, {p.y:>7.1f}, {p.z:>9.1f})")

    if args.csv:
        export_csv(placements, args.csv)


if __name__ == "__main__":
    main()
