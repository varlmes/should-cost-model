"""Casting should-cost estimator translated from the MATLAB Cost Advisor flow.

The upstream MATLAB project drives an Excel workbook through COM and reads these
cost buckets: material, processing, NDT, tooling, straightening fixture, and
check fixture. The workbook/trained model artifacts are not present in the
public repo, so this module keeps the same inputs and outputs while using an
explicit deterministic parametric model that can run inside Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod

MM_PER_IN = 25.4
MM2_PER_IN2 = MM_PER_IN ** 2
MM3_PER_IN3 = MM_PER_IN ** 3


@dataclass(frozen=True)
class CastingMaterial:
    name: str
    grade: str
    casting_class: str
    density_lb_in3: float
    metal_price_lb: float
    melt_yield: float
    process_rate_lb: float
    process_rate_in2: float
    tooling_factor: float
    fixture_factor: float
    ndt_factor: float


MATERIALS: dict[str, CastingMaterial] = {
    "Aluminum A356-T6": CastingMaterial("Aluminum", "A356-T6", "2", 0.097, 3.75, 0.72, 6.5, 0.14, 0.85, 0.70, 0.75),
    "Aluminum 356-F": CastingMaterial("Aluminum", "356-F", "1", 0.097, 3.20, 0.74, 5.8, 0.12, 0.78, 0.65, 0.65),
    "Gray Iron Class 30": CastingMaterial("Iron", "Class 30", "1", 0.260, 0.72, 0.82, 2.7, 0.05, 0.62, 0.70, 0.45),
    "Ductile Iron 65-45-12": CastingMaterial("Iron", "65-45-12", "2", 0.257, 0.92, 0.78, 3.4, 0.06, 0.70, 0.82, 0.55),
    "Carbon Steel WCB": CastingMaterial("Steel", "WCB", "3", 0.283, 1.15, 0.68, 6.9, 0.10, 1.00, 1.00, 0.85),
    "Stainless Steel CF8M": CastingMaterial("Stainless", "CF8M", "4", 0.289, 3.90, 0.62, 10.5, 0.16, 1.35, 1.25, 1.25),
    "Bronze C83600": CastingMaterial("Bronze", "C83600", "3", 0.318, 5.10, 0.70, 7.4, 0.12, 0.95, 0.95, 0.70),
}

PROCESS_MULTIPLIERS = {
    "Sand casting": 1.00,
    "Investment casting": 1.55,
    "Permanent mold": 1.25,
    "Die casting": 1.70,
}

NDT_METHODS = {
    "Visual only": 0.0,
    "Dye penetrant": 18.0,
    "Mag particle": 24.0,
    "X-ray sample": 65.0,
    "X-ray 100%": 140.0,
}

COMPLEXITY_LABELS = {
    1: "1 - simple open casting",
    2: "2 - basic cored/featured casting",
    3: "3 - moderate parting and features",
    4: "4 - high complexity geometry",
    5: "5 - severe cores/parting/NDT risk",
}


@dataclass(frozen=True)
class CastingInputs:
    part_id: str
    material_key: str
    process: str
    quantity_ordered: int
    casting_volume_mm3: float
    core_volume_mm3: float
    casting_surface_area_mm2: float
    box_dimensions_mm: tuple[float, float, float]
    shape_complexity: int
    feeder_count: int = 0
    ndt_method: str = "Dye penetrant"
    margin_rate: float = 0.16


@dataclass(frozen=True)
class CastingBreakdown:
    material_per_part: float
    processing_per_part: float
    tooling_per_part: float
    ndt_per_part: float
    straightening_per_part: float
    check_fixture_per_part: float
    subtotal_per_part: float
    margin_per_part: float
    grand_total_per_part: float
    grand_total_order: float


@dataclass(frozen=True)
class CastingMetrics:
    casting_volume_in3: float
    core_volume_in3: float
    envelope_volume_in3: float
    surface_area_in2: float
    box_dimensions_in: tuple[float, float, float]
    box_volume_in3: float
    casting_weight_lb: float
    yield_weight_lb: float
    volume_ratio: float
    surface_area_density: float


@dataclass(frozen=True)
class CastingEstimate:
    inputs: CastingInputs
    material: CastingMaterial
    metrics: CastingMetrics
    breakdown: CastingBreakdown
    low_per_part: float
    high_per_part: float
    low_order: float
    high_order: float
    complexity_label: str
    notes: list[str]


def mm3_to_in3(value: float) -> float:
    return value / MM3_PER_IN3


def mm2_to_in2(value: float) -> float:
    return value / MM2_PER_IN2


def mm_to_in(value: float) -> float:
    return value / MM_PER_IN


def suggest_complexity(
    core_volume_mm3: float,
    casting_volume_mm3: float,
    feeder_count: int,
    surface_area_mm2: float,
    box_dimensions_mm: tuple[float, float, float],
) -> int:
    """Small deterministic stand-in for the MATLAB trained complexity model."""
    dims = sorted(box_dimensions_mm)
    box_volume = max(prod(dims), 1.0)
    solidity = casting_volume_mm3 / box_volume
    core_ratio = core_volume_mm3 / max(casting_volume_mm3, 1.0)
    area_density = surface_area_mm2 / max(casting_volume_mm3 ** (2 / 3), 1.0)
    slenderness = dims[-1] / max(dims[0], 1.0)

    score = 1
    score += core_ratio > 0.03
    score += core_ratio > 0.15
    score += feeder_count >= 2
    score += area_density > 8.0
    score += slenderness > 4.0 or solidity < 0.18
    return max(1, min(5, int(score)))


def estimate_casting_cost(inputs: CastingInputs) -> CastingEstimate:
    if not inputs.part_id:
        raise ValueError("part_id is required")
    if inputs.material_key not in MATERIALS:
        raise ValueError(f"Unknown material: {inputs.material_key}")
    if inputs.process not in PROCESS_MULTIPLIERS:
        raise ValueError(f"Unknown casting process: {inputs.process}")
    if inputs.quantity_ordered < 1:
        raise ValueError("quantity_ordered must be >= 1")
    if inputs.casting_volume_mm3 <= 0:
        raise ValueError("casting_volume_mm3 must be > 0")
    if inputs.casting_surface_area_mm2 <= 0:
        raise ValueError("casting_surface_area_mm2 must be > 0")
    if any(d <= 0 for d in inputs.box_dimensions_mm):
        raise ValueError("all box dimensions must be > 0")
    if not 1 <= inputs.shape_complexity <= 5:
        raise ValueError("shape_complexity must be between 1 and 5")

    mat = MATERIALS[inputs.material_key]
    quantity = inputs.quantity_ordered
    process_multiplier = PROCESS_MULTIPLIERS[inputs.process]
    complexity_multiplier = 1.0 + 0.22 * (inputs.shape_complexity - 1)
    quantity_discount = max(0.58, quantity ** -0.075)

    casting_volume_in3 = mm3_to_in3(inputs.casting_volume_mm3)
    core_volume_in3 = mm3_to_in3(max(inputs.core_volume_mm3, 0.0))
    envelope_volume_in3 = casting_volume_in3 + core_volume_in3
    surface_area_in2 = mm2_to_in2(inputs.casting_surface_area_mm2)
    box_dimensions_in = tuple(sorted(mm_to_in(d) for d in inputs.box_dimensions_mm))
    box_volume_in3 = prod(box_dimensions_in)
    casting_weight_lb = casting_volume_in3 * mat.density_lb_in3
    yield_weight_lb = casting_weight_lb / mat.melt_yield
    volume_ratio = envelope_volume_in3 / max(box_volume_in3, 0.001)
    surface_area_density = surface_area_in2 / max(casting_volume_in3 ** (2 / 3), 0.001)

    material_per_part = yield_weight_lb * mat.metal_price_lb
    processing_base = 45.0 * process_multiplier * complexity_multiplier * quantity_discount
    processing_per_part = (
        processing_base
        + casting_weight_lb * mat.process_rate_lb * process_multiplier * complexity_multiplier
        + surface_area_in2 * mat.process_rate_in2 * complexity_multiplier
        + core_volume_in3 * 1.85 * complexity_multiplier
        + inputs.feeder_count * 8.0
    )

    tooling_total = (
        1800.0
        * mat.tooling_factor
        * process_multiplier
        * complexity_multiplier
        * (max(box_volume_in3, 1.0) ** 0.34)
    )
    tooling_per_part = tooling_total / quantity

    ndt_base = NDT_METHODS.get(inputs.ndt_method, NDT_METHODS["Dye penetrant"])
    ndt_per_part = (ndt_base + 0.08 * surface_area_in2 + 1.20 * casting_weight_lb) * mat.ndt_factor

    straightening_total = 320.0 * mat.fixture_factor * max(inputs.shape_complexity - 1, 0) * (casting_weight_lb ** 0.35)
    check_fixture_total = 550.0 * mat.fixture_factor * complexity_multiplier * (max(box_volume_in3, 1.0) ** 0.20)
    straightening_per_part = straightening_total / quantity
    check_fixture_per_part = check_fixture_total / quantity

    subtotal = sum(
        [
            material_per_part,
            processing_per_part,
            tooling_per_part,
            ndt_per_part,
            straightening_per_part,
            check_fixture_per_part,
        ]
    )
    margin = subtotal * inputs.margin_rate
    grand_total_per_part = subtotal + margin
    grand_total_order = grand_total_per_part * quantity

    # Match the MATLAB controller behavior: recompute across complexity tags to
    # create an uncertainty band around the selected complexity result.
    scenario_totals = []
    for c in range(1, 6):
        scenario_inputs = CastingInputs(**{**inputs.__dict__, "shape_complexity": c})
        if c == inputs.shape_complexity:
            scenario_totals.append(grand_total_per_part)
            continue
        scenario_totals.append(_estimate_without_band(scenario_inputs))

    low_per_part = min(scenario_totals)
    high_per_part = max(scenario_totals)

    notes = [
        "Translated from the MATLAB Cost Advisor structure: material, processing, NDT, tooling, straightening fixture, and check fixture.",
        "This page uses transparent parametric assumptions instead of hidden workbook formulas, making the estimate runnable and reviewable inside the app.",
    ]
    if volume_ratio < 0.12:
        notes.append("Low casting-to-box volume ratio: pattern/layout assumptions may carry extra risk.")
    if inputs.core_volume_mm3 > 0:
        notes.append("Core volume is included in envelope volume and processing complexity.")

    metrics = CastingMetrics(
        casting_volume_in3=round(casting_volume_in3, 4),
        core_volume_in3=round(core_volume_in3, 4),
        envelope_volume_in3=round(envelope_volume_in3, 4),
        surface_area_in2=round(surface_area_in2, 4),
        box_dimensions_in=tuple(round(v, 4) for v in box_dimensions_in),
        box_volume_in3=round(box_volume_in3, 4),
        casting_weight_lb=round(casting_weight_lb, 4),
        yield_weight_lb=round(yield_weight_lb, 4),
        volume_ratio=round(volume_ratio, 4),
        surface_area_density=round(surface_area_density, 4),
    )
    breakdown = CastingBreakdown(
        material_per_part=round(material_per_part, 2),
        processing_per_part=round(processing_per_part, 2),
        tooling_per_part=round(tooling_per_part, 2),
        ndt_per_part=round(ndt_per_part, 2),
        straightening_per_part=round(straightening_per_part, 2),
        check_fixture_per_part=round(check_fixture_per_part, 2),
        subtotal_per_part=round(subtotal, 2),
        margin_per_part=round(margin, 2),
        grand_total_per_part=round(grand_total_per_part, 2),
        grand_total_order=round(grand_total_order, 2),
    )

    return CastingEstimate(
        inputs=inputs,
        material=mat,
        metrics=metrics,
        breakdown=breakdown,
        low_per_part=round(low_per_part, 2),
        high_per_part=round(high_per_part, 2),
        low_order=round(low_per_part * quantity, 2),
        high_order=round(high_per_part * quantity, 2),
        complexity_label=COMPLEXITY_LABELS[inputs.shape_complexity],
        notes=notes,
    )


def _estimate_without_band(inputs: CastingInputs) -> float:
    """Internal scenario helper to avoid recursive band generation."""
    mat = MATERIALS[inputs.material_key]
    quantity = inputs.quantity_ordered
    process_multiplier = PROCESS_MULTIPLIERS[inputs.process]
    complexity_multiplier = 1.0 + 0.22 * (inputs.shape_complexity - 1)
    quantity_discount = max(0.58, quantity ** -0.075)

    casting_volume_in3 = mm3_to_in3(inputs.casting_volume_mm3)
    core_volume_in3 = mm3_to_in3(max(inputs.core_volume_mm3, 0.0))
    surface_area_in2 = mm2_to_in2(inputs.casting_surface_area_mm2)
    box_volume_in3 = prod(mm_to_in(d) for d in inputs.box_dimensions_mm)
    casting_weight_lb = casting_volume_in3 * mat.density_lb_in3
    yield_weight_lb = casting_weight_lb / mat.melt_yield

    material = yield_weight_lb * mat.metal_price_lb
    processing = (
        45.0 * process_multiplier * complexity_multiplier * quantity_discount
        + casting_weight_lb * mat.process_rate_lb * process_multiplier * complexity_multiplier
        + surface_area_in2 * mat.process_rate_in2 * complexity_multiplier
        + core_volume_in3 * 1.85 * complexity_multiplier
        + inputs.feeder_count * 8.0
    )
    tooling = (
        1800.0
        * mat.tooling_factor
        * process_multiplier
        * complexity_multiplier
        * (max(box_volume_in3, 1.0) ** 0.34)
    ) / quantity
    ndt = (NDT_METHODS.get(inputs.ndt_method, 18.0) + 0.08 * surface_area_in2 + 1.20 * casting_weight_lb) * mat.ndt_factor
    straightening = (320.0 * mat.fixture_factor * max(inputs.shape_complexity - 1, 0) * (casting_weight_lb ** 0.35)) / quantity
    check = (550.0 * mat.fixture_factor * complexity_multiplier * (max(box_volume_in3, 1.0) ** 0.20)) / quantity
    subtotal = material + processing + tooling + ndt + straightening + check
    return subtotal * (1 + inputs.margin_rate)
