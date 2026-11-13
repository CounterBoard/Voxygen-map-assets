#!/usr/bin/env python3
"""Build a versioned Deep Zoom pyramid from one uploaded map image."""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageOps

TILE_SIZE = 512
PREVIEW_MAX = 1200
MAX_RASTER_DIMENSION = 8944
MAX_RASTER_PIXELS = 80_000_000


def world_coordinate_system() -> dict[str, int | str]:
    """Return Voxygen's fixed world-coordinate bounds, independent of raster size."""
    return {
        "type": "minecraft-world-block-centers",
        "minX": -3008,
        "maxX": 3007,
        "minZ": -3008,
        "maxZ": 3007,
    }


def save_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "WEBP", lossless=True, method=6)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: build_map.py SOURCE_IMAGE OUTPUT_PUBLIC_DIR")

    source_path = Path(sys.argv[1])
    public_dir = Path(sys.argv[2])
    version = os.environ.get("MAP_VERSION", "").strip()
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in version):
        raise SystemExit("MAP_VERSION must contain only letters, numbers, dot, underscore or dash")

    version_dir = public_dir / "world-map" / "versions" / version
    if version_dir.exists():
        shutil.rmtree(version_dir)
    tiles_dir = version_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as opened:
        if opened.format not in {"PNG", "JPEG", "WEBP"}:
            raise SystemExit(f"Unsupported source image format: {opened.format or 'unknown'}. Use PNG, JPEG or WebP.")
        width, height = opened.size
        if width < 1 or height < 1 or width > MAX_RASTER_DIMENSION or height > MAX_RASTER_DIMENSION:
            raise SystemExit(
                f"Unsupported raster dimensions: {width}x{height}. "
                f"Each side must be between 1 and {MAX_RASTER_DIMENSION} pixels."
            )
        pixel_count = width * height
        if pixel_count > MAX_RASTER_PIXELS:
            raise SystemExit(
                f"Raster exceeds maximum pixel count: {pixel_count} > {MAX_RASTER_PIXELS}."
            )
        if width != height:
            raise SystemExit(
                f"World map raster must be square to preserve equal X/Z scale; received {width}x{height}."
            )
        image = ImageOps.exif_transpose(opened).convert("RGBA")

    coordinate_system = world_coordinate_system()
    max_level = math.ceil(math.log2(max(width, height)))
    preview = image.copy()
    preview.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.Resampling.LANCZOS)
    save_webp(preview, version_dir / "preview.webp")

    tile_count = 0
    for level in range(max_level + 1):
        scale = 2 ** (max_level - level)
        level_width = max(1, math.ceil(width / scale))
        level_height = max(1, math.ceil(height / scale))
        if (level_width, level_height) == image.size:
            level_image = image
        else:
            level_image = image.resize((level_width, level_height), Image.Resampling.LANCZOS)

        cols = math.ceil(level_width / TILE_SIZE)
        rows = math.ceil(level_height / TILE_SIZE)
        for y in range(rows):
            for x in range(cols):
                tile = level_image.crop((
                    x * TILE_SIZE,
                    y * TILE_SIZE,
                    min((x + 1) * TILE_SIZE, level_width),
                    min((y + 1) * TILE_SIZE, level_height),
                ))
                save_webp(tile, tiles_dir / str(level) / f"{x}_{y}.webp")
                tile_count += 1

    manifest = {
        "schemaVersion": 1,
        "mapVersion": version,
        "source": {
            "type": "deepzoom",
            "width": width,
            "height": height,
            "tileSize": TILE_SIZE,
            "minLevel": 0,
            "maxLevel": max_level,
            "format": "webp",
            "coordinateSystem": coordinate_system,
            "tileUrlTemplate": f"/world-map/versions/{version}/tiles/{{level}}/{{x}}_{{y}}.webp",
            "previewUrl": f"/world-map/versions/{version}/preview.webp",
        },
        "futureSources": {
            "urlGrid": {
                "type": "url-grid",
                "rows": 12,
                "columns": 12,
                "urls": [],
            }
        },
        "generated": {"tileCount": tile_count, "tileSize": TILE_SIZE},
    }

    map_root = public_dir / "world-map"
    map_root.mkdir(parents=True, exist_ok=True)
    temp_manifest = map_root / "manifest.json.tmp"
    temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp_manifest.replace(map_root / "manifest.json")
    print(f"Built {width}x{height} raster with fixed world coordinates: {tile_count} tiles, levels 0-{max_level}, version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
