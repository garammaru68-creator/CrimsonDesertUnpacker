"""Convert extracted DDS worldmap tiles to PNG for Leaflet tile serving.

Usage:
    # Convert all worldmap blur_height tiles
    python dds_to_png.py /path/to/worldmap_extract/ui/ --output /path/to/tiles/ --pattern "cd_worldmap_blur_height_*"

    # Convert uitexture worldmap backgrounds
    python dds_to_png.py /path/to/worldmap_extract/ui/ --output /path/to/backgrounds/ --pattern "cd_uitexture_worldmap_0*"

    # Convert all DDS in a directory
    python dds_to_png.py /path/to/dds_dir/ --output /path/to/png_dir/
"""

import os
import sys
import struct
import argparse
import fnmatch
from PIL import Image


def needs_internal_lz4(filepath: str) -> bool:
    """Check if DDS file has internal LZ4 compression."""
    with open(filepath, 'rb') as f:
        data = f.read(128)
    if data[:4] != b'DDS ':
        return False
    reserved0 = struct.unpack_from('<I', data, 0x20)[0]
    return reserved0 != 0


def convert_dds_to_png(dds_path: str, png_path: str) -> bool:
    """Convert a single DDS file to PNG using Pillow."""
    try:
        img = Image.open(dds_path)
        # Convert grayscale to RGB for better visibility
        if img.mode == 'L':
            img = img.convert('RGB')
        elif img.mode == 'LA':
            img = img.convert('RGBA')

        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        img.save(png_path, 'PNG')
        img.close()
        return True
    except Exception as e:
        print(f"  ERROR: {dds_path}: {e}", file=sys.stderr)
        return False


def organize_tiles(input_dir: str, output_dir: str, pattern: str = "cd_worldmap_blur_height_*_*.dds"):
    """Convert and organize worldmap tiles into Z/X/Y structure for Leaflet."""
    dds_files = sorted(f for f in os.listdir(input_dir)
                       if fnmatch.fnmatch(f, pattern) and f.endswith('.dds'))

    # Parse tile coordinates from filename: cd_worldmap_blur_height_X_Y.dds
    tiles = []
    for f in dds_files:
        name = f.replace('.dds', '')
        parts = name.rsplit('_', 2)
        if len(parts) >= 3:
            try:
                x = int(parts[-2])
                y = int(parts[-1])
                tiles.append((x, y, f))
            except ValueError:
                continue

    if not tiles:
        print("No tiles found matching pattern: %s" % pattern)
        return

    max_x = max(t[0] for t in tiles)
    max_y = max(t[1] for t in tiles)
    grid_size = max(max_x, max_y) + 1

    print(f"Found {len(tiles)} tiles ({grid_size}x{grid_size} grid)")

    # Determine zoom level from grid size (16x16 = zoom 4, etc.)
    import math
    zoom = int(math.log2(grid_size)) if grid_size > 0 else 0

    converted = 0
    for x, y, f in tiles:
        dds_path = os.path.join(input_dir, f)
        # Leaflet TMS: tiles/{z}/{x}/{y}.png
        png_path = os.path.join(output_dir, str(zoom), str(x), f"{y}.png")

        if convert_dds_to_png(dds_path, png_path):
            converted += 1

    print(f"Converted {converted}/{len(tiles)} tiles to {output_dir} (zoom={zoom})")


def batch_convert(input_dir: str, output_dir: str, pattern: str = "*.dds"):
    """Convert all matching DDS files to PNG (flat output)."""
    dds_files = sorted(f for f in os.listdir(input_dir)
                       if fnmatch.fnmatch(f, pattern) and f.endswith('.dds'))

    print(f"Converting {len(dds_files)} DDS files...")
    converted = 0
    for f in dds_files:
        dds_path = os.path.join(input_dir, f)
        png_name = f.replace('.dds', '.png')
        png_path = os.path.join(output_dir, png_name)

        if convert_dds_to_png(dds_path, png_path):
            converted += 1
            if converted % 50 == 0:
                print(f"  {converted}/{len(dds_files)}...")

    print(f"Done: {converted}/{len(dds_files)} converted")


def main():
    parser = argparse.ArgumentParser(description="Convert DDS worldmap tiles to PNG")
    parser.add_argument("input", help="Directory containing DDS files")
    parser.add_argument("--output", "-o", required=True, help="Output directory")
    parser.add_argument("--pattern", "-p", default="*.dds", help="Filename pattern (default: *.dds)")
    parser.add_argument("--tiles", action="store_true", help="Organize as Z/X/Y tile pyramid")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.tiles:
        organize_tiles(args.input, args.output, args.pattern)
    else:
        batch_convert(args.input, args.output, args.pattern)


if __name__ == "__main__":
    main()
