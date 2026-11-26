#!/usr/bin/env python3
"""Build a cookie-cutter STL from an image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from shapely.geometry import Polygon

import cookie_builder_core as core


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an image to a cookie-cutter STL")
    parser.add_argument("input", type=Path, help="Input image")
    parser.add_argument("output", type=Path, help="Output .stl or .3mf file")
    parser.add_argument("--size-mm", type=float, default=80.0)
    parser.add_argument("--wall-mm", type=float, default=1.2)
    parser.add_argument("--cutter-height-mm", type=float, default=12.0)
    parser.add_argument("--emboss-mm", type=float, default=1.0)
    parser.add_argument("--base-mm", type=float, default=2.0)
    parser.add_argument("--simplify-mm", type=float, default=0.25)
    parser.add_argument("--threshold", type=int, default=128)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def load_mask(path: Path, threshold: int, invert: bool) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Input image not found: {path}")

    image = Image.open(path).convert("RGBA")
    rgba = np.asarray(image)

    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    binary = np.where(gray < threshold, 255, 0).astype(np.uint8)

    # Preserve transparency as an explicit part of a silhouette mask.
    binary = np.where(alpha < 16, 0, binary).astype(np.uint8)

    if invert:
        binary = cv2.bitwise_not(binary)

    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    if cv2.countNonZero(binary) == 0:
        raise ValueError("No foreground pixels found. Try --invert or another threshold.")

    return binary


def main() -> int:
    args = parse_args()

    if args.output.suffix.lower() not in {".stl", ".3mf"}:
        raise ValueError("Output must end in .stl or .3mf")

    if args.wall_mm <= 0 or args.base_mm <= 0:
        raise ValueError("Wall and base thickness must be positive")
    if args.emboss_mm < 0 or args.cutter_height_mm <= args.emboss_mm:
        raise ValueError("Cutter height must be greater than emboss height")

    try:
        mask = load_mask(args.input, args.threshold, args.invert)
        result = core.generate_model(
            mask=mask,
            size_mm=args.size_mm,
            wall_mm=args.wall_mm,
            cutter_height_mm=args.cutter_height_mm,
            emboss_mm=args.emboss_mm,
            base_mm=args.base_mm,
            simplify_mm=args.simplify_mm,
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.mesh.export(args.output)

        if args.preview:
            preview_path = args.output.with_suffix(".preview.png")
            core.save_preview(mask, result.outer_polygon, result.emboss_geometries, preview_path)

        if not args.quiet:
            print(f"Wrote: {args.output}")
            print(f"Triangles: {len(result.mesh.faces):,}")
            print(f"Emboss elements: {len(result.emboss_geometries)}")
            if result.warnings:
                print("Warnings:")
                for warning in result.warnings:
                    print(f"  - {warning}")

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
