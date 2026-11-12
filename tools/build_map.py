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


def coordinate_system_for_dimensions(width: int, height: int) -> dict[str, int | str]:
    if width != 6016 or height != 6016:
        raise ValueError(
            f"Voxygen world map must be exactly 6016x6016 pixels; received {width}x{height}."
        )
    origin = width // 2
    return {
        "type": "minecraft-block-pixel-centers",
        "originX": origin,
        "originY": origin,
        "minX": -origin,
        "maxX": width - origin - 1,
        "minZ": -origin,
        "maxZ": height - origin - 1,
        "width": width,
        "height": height,
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
        image = ImageOps.exif_transpose(opened).convert("RGBA")
    width, height = image.size
    try:
        coordinate_system = coordinate_system_for_dimensions(width, height)
    except ValueError as error:
        raise SystemExit(str(error)) from error

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
    print(f"Built {width}x{height} map: {tile_count} tiles, levels 0-{max_level}, version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
