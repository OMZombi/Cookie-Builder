from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import trimesh
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


@dataclass
class BuildResult:
    mesh: trimesh.Trimesh
    outer_polygon: Polygon
    emboss_geometries: list
    warnings: list[str]


def mask_to_polygon(mask: np.ndarray, simplify_pixels: float) -> Polygon:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("Could not find an outer contour")

    largest = max(contours, key=cv2.contourArea)
    if len(largest) < 3:
        raise ValueError("Outer contour has fewer than three points")

    points = largest[:, 0, :].astype(float)
    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    if simplify_pixels > 0:
        polygon = polygon.simplify(simplify_pixels, preserve_topology=True)

    if polygon.is_empty:
        raise ValueError("Outer contour simplified to an empty polygon")

    return polygon


def scale_polygon(polygon: Polygon, scale_x: float, scale_y: float) -> Polygon:
    coords = np.asarray(polygon.exterior.coords)
    transformed = [(x * scale_x, y * scale_y) for x, y in coords]
    result = Polygon(transformed)

    if not polygon.is_valid:
        raise ValueError("Invalid scaled outer contour")

    return result


def extract_emboss_lines(mask: np.ndarray) -> list[LineString]:
    gray = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    lines: list[LineString] = []
    for contour in contours:
        if len(contour) < 2:
            continue

        points = contour[:, 0, :].astype(float)
        if len(points) >= 3:
            approx = cv2.approxPolyDP(contour, 1.2, False)[:, 0, :].astype(float)
            if len(approx) >= 2:
                points = approx

        line = LineString(points)
        if line.length >= 3:
            lines.append(line)

    if not lines:
        return []

    merged = unary_union(lines)
    if isinstance(merged, LineString):
        return [merged]

    if hasattr(merged, "geoms"):
        return [geom for geom in merged.geoms if isinstance(geom, (LineString,))]

    return lines


def extrude_polygon(polygon: Polygon, z0: float, z1: float) -> trimesh.Trimesh:
    result = trimesh.creation.extrude_polygon(polygon, z1 - z0)
    result.apply_translation((0, 0, z0))
    return result


def generate_model(
    mask: np.ndarray,
    size_mm: float,
    wall_mm: float,
    cutter_height_mm: float,
    emboss_mm: float,
    base_mm: float,
    simplify_mm: float,
) -> BuildResult:
    height, width = mask.shape

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("Could not find a silhouette")

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    crop = mask[y:y+h, x:x+w]

    contour_scale = size_mm / max(w, h)
    polygon = mask_to_polygon(crop, simplify_mm / contour_scale)

    coords = np.asarray(polygon.exterior.coords)
    min_x, min_y = coords[:, 0].min(), coords[:, 1].min()
    coords -= np.array([min_x, min_y])

    polygon = Polygon([(x * contour_scale, y * contour_scale) for x, y in coords])

    # Mirror Y so the preview and coordinate system match the source image.
    py = polygon.bounds[3]
    polygon = scale_polygon(polygon, 1.0, -1.0).translate((0, py))

    parts: list[trimesh.Trimesh] = []

    parts.append(extrude_polygon(polygon, 0.0, base_mm))

    outer_offset = polygon.buffer(-wall_mm)
    if outer_offset.is_empty:
        raise ValueError("Wall thickness is too large for this silhouette")

    outer_wall = polygon.difference(outer_offset)
    parts.append(extrude_polygon(outer_wall, base_mm, cutter_height_mm + base_mm))

    lines = extract_emboss_lines(crop)
    emboss_parts: list[Polygon] = []

    source_width = crop.shape[1]
    source_height = crop.shape[0]

    for line in lines:
        scaled_coords = []
        for px, py_source in line.coords:
            scaled_coords.append((px * contour_scale, (source_height - py_source) * contour_scale))

        scaled_line = LineString(scaled_coords)
        # Keep emboss geometry away from the cutting wall.
        if not polygon.contains(scaled_line) and not polygon.intersects(scaled_line):
            continue

        clipped = scaled_line.intersection(polygon)
        clipped = clipped.buffer(0.45, cap_style="round", join_style="round")
        clipped = clipped.difference(polygon.buffer(-wall_mm * 1.5))

        if clipped.is_empty:
            continue

        if hasattr(clipped, "geoms"):
            geoms = list(clipped.geoms)
        else:
            geoms = [clipped]

        for geom in geoms:
            if geom.is_empty:
                continue
            emb_polygon = Polygon(geom.exterior.coords) if isinstance(geom, Polygon) else None
            if emb_polygon is None:
                continue
            emboss_parts.append(emb_polygon)
            parts.append(extrude_polygon(emb_polygon, base_mm, base_mm + emboss_mm))

    mesh = trimesh.util.concatenate(parts)
    mesh.remove_duplicate_faces()
    mesh.remove_degenerate_faces()
    mesh.merge_vertices()

    warnings: list[str] = []
    if len(emboss_parts) == 0:
        warnings.append("No emboss lines were detected. Try a higher-contrast line-art image.")

    try:
        mesh.process(validate=True)
    except Exception:
        warnings.append("The mesh may contain invalid geometry; validate it in a slicer.")

    return BuildResult(
        mesh=mesh,
        outer_polygon=polygon,
        emboss_geometries=emboss_parts,
        warnings=warnings,
    )


def save_preview(
    mask: np.ndarray,
    outer_polygon: Polygon,
    emboss_geometries: Iterable[Polygon],
    path: Path,
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 8))

    x, y = outer_polygon.exterior.xy
    ax.plot(x, y, color="red", linewidth=2, label="Outer cutter")

    for geometry in emboss_geometries:
        if geometry.is_empty:
            continue
        if hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                gx, gy = part.exterior.xy
                ax.plot(gx, gy, color="blue", alpha=0.7)
        else:
            gx, gy = geometry.exterior.xy
            ax.plot(gx, gy, color="blue", alpha=0.7)

    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
