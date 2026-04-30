"""Lightweight STL mesh analysis for the 3D object viewer page."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from struct import pack, unpack


@dataclass(frozen=True)
class MeshInputs:
    density_g_cc: float = 1.05
    material_cost_per_kg: float = 200.0
    filament_diameter_mm: float = 1.75
    print_speed_mm_s: float = 150.0


@dataclass(frozen=True)
class MeshStats:
    triangle_count: int
    width_mm: float
    depth_mm: float
    height_mm: float
    volume_cm3: float
    surface_area_cm2: float
    weight_g: float
    material_cost: float
    filament_length_mm: float
    build_hours: int
    build_minutes: int
    notes: list[str]


Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]


def demo_stl_bytes() -> bytes:
    """Return a small binary STL block so the viewer has a useful first render."""
    vertices = [
        (-25.0, -18.0, 0.0),
        (25.0, -18.0, 0.0),
        (25.0, 18.0, 0.0),
        (-25.0, 18.0, 0.0),
        (-18.0, -12.0, 32.0),
        (18.0, -12.0, 32.0),
        (18.0, 12.0, 32.0),
        (-18.0, 12.0, 32.0),
    ]
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    out = bytearray(b"Should-cost demo STL".ljust(80, b" "))
    out.extend(len(faces).to_bytes(4, "little"))
    for face in faces:
        tri = tuple(vertices[idx] for idx in face)
        normal = _normal(*tri)
        for value in (*normal, *tri[0], *tri[1], *tri[2]):
            out.extend(pack("<f", value))
        out.extend((0).to_bytes(2, "little"))
    return bytes(out)


def analyze_stl(data: bytes, inputs: MeshInputs) -> MeshStats:
    if inputs.density_g_cc < 0:
        raise ValueError("density_g_cc must be >= 0")
    if inputs.material_cost_per_kg < 0:
        raise ValueError("material_cost_per_kg must be >= 0")
    if inputs.filament_diameter_mm <= 0:
        raise ValueError("filament_diameter_mm must be > 0")
    if inputs.print_speed_mm_s <= 0:
        raise ValueError("print_speed_mm_s must be > 0")

    triangles = parse_stl(data)
    if not triangles:
        raise ValueError("No STL triangles found.")

    points = [point for tri in triangles for point in tri]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    width = max(xs) - min(xs)
    depth = max(ys) - min(ys)
    height = max(zs) - min(zs)

    signed_volume_mm3 = sum(_signed_volume(*tri) for tri in triangles)
    volume_mm3 = abs(signed_volume_mm3)
    surface_area_mm2 = sum(_triangle_area(*tri) for tri in triangles)
    volume_cm3 = volume_mm3 / 1000.0
    surface_area_cm2 = surface_area_mm2 / 100.0
    weight_g = volume_cm3 * inputs.density_g_cc
    material_cost = weight_g * inputs.material_cost_per_kg / 1000.0
    filament_area_mm2 = pi * (inputs.filament_diameter_mm / 2) ** 2
    filament_length_mm = volume_mm3 / filament_area_mm2 if filament_area_mm2 else 0.0
    build_seconds = filament_length_mm / inputs.print_speed_mm_s if inputs.print_speed_mm_s else 0.0
    build_minutes_total = max(1, round(build_seconds / 60)) if filament_length_mm > 0 else 0

    notes = [
        "STL dimensions are interpreted as millimeters and converted to cm/cm3 for reporting.",
        "Material cost follows the 3DObjectViewer convention: weight x cost per kg.",
        "Build time is a simple filament-length / print-speed estimate and excludes travel, infill strategy, supports, and slicer acceleration.",
    ]
    if signed_volume_mm3 < 0:
        notes.append("Triangle winding produced negative signed volume; absolute enclosed volume was used.")

    return MeshStats(
        triangle_count=len(triangles),
        width_mm=round(width, 4),
        depth_mm=round(depth, 4),
        height_mm=round(height, 4),
        volume_cm3=round(volume_cm3, 4),
        surface_area_cm2=round(surface_area_cm2, 4),
        weight_g=round(weight_g, 4),
        material_cost=round(material_cost, 4),
        filament_length_mm=round(filament_length_mm, 4),
        build_hours=build_minutes_total // 60,
        build_minutes=build_minutes_total % 60,
        notes=notes,
    )


def parse_stl(data: bytes) -> list[Triangle]:
    if _looks_binary_stl(data):
        return _parse_binary_stl(data)
    return _parse_ascii_stl(data)


def _looks_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    tri_count = int.from_bytes(data[80:84], "little")
    return 84 + tri_count * 50 == len(data)


def _parse_binary_stl(data: bytes) -> list[Triangle]:
    tri_count = int.from_bytes(data[80:84], "little")
    triangles = []
    offset = 84
    for _ in range(tri_count):
        if offset + 50 > len(data):
            break
        values = unpack("<12fH", data[offset:offset + 50])
        triangles.append((
            (values[3], values[4], values[5]),
            (values[6], values[7], values[8]),
            (values[9], values[10], values[11]),
        ))
        offset += 50
    return triangles


def _parse_ascii_stl(data: bytes) -> list[Triangle]:
    text = data.decode("utf-8", errors="ignore")
    vertices: list[Point] = []
    for raw_line in text.splitlines():
        parts = raw_line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return [(vertices[idx], vertices[idx + 1], vertices[idx + 2]) for idx in range(0, len(vertices) - 2, 3)]


def _signed_volume(a: Point, b: Point, c: Point) -> float:
    return (
        a[0] * b[1] * c[2]
        + b[0] * c[1] * a[2]
        + c[0] * a[1] * b[2]
        - a[0] * c[1] * b[2]
        - b[0] * a[1] * c[2]
        - c[0] * b[1] * a[2]
    ) / 6.0


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    ab = _sub(b, a)
    ac = _sub(c, a)
    cross = _cross(ab, ac)
    return 0.5 * sqrt(_dot(cross, cross))


def _normal(a: Point, b: Point, c: Point) -> Point:
    cross = _cross(_sub(b, a), _sub(c, a))
    length = sqrt(_dot(cross, cross))
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (cross[0] / length, cross[1] / length, cross[2] / length)


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Point, b: Point) -> Point:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

