"""PCBA should-cost estimator.

Ports the workbook-driven Streamlit PCBA costing flow into deterministic local
Python. The model combines process mapping, MMR conversion, labor, NRE,
consumables, raw material inputs, and volume-band overhead/profit percentages.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class ProcessStep:
    side: str
    stage: str
    batch_setup_sec: float
    process_cycle_sec: float
    mmr_per_sec: float
    setup_fte: float
    dl_fte: float
    idl_fte: float


@dataclass(frozen=True)
class ProcessCost:
    side: str
    stage: str
    batch_setup_cost: float
    va_machine_cost: float
    labor_cost: float
    total_cost: float


@dataclass(frozen=True)
class NreItem:
    item: str
    unit_price: float
    life_cycle_boards: float


@dataclass(frozen=True)
class PcbaInputs:
    part_id: str
    annual_volume: float
    product_life_years: float
    batch_qty: float
    pcb_cost: float
    electronics_component_cost: float
    mechanical_component_cost: float
    board_length_mm: float
    board_width_mm: float
    top_solder_paste_thickness_mm: float
    bottom_solder_paste_thickness_mm: float
    top_weight_estimate_pct: float
    bottom_weight_estimate_pct: float
    solder_paste_wastage_pct: float
    rtv_weight_estimate: float
    rtv_wastage_pct: float
    rtv_cost_per_ml: float
    rtv_specific_gravity: float
    flux_wastage_pct: float
    selected_processes: list[str]
    selected_nre_items: list[str]
    volume_band: str
    labor_cost_hr: float = 2.81
    idl_cost_hr: float = 4.754
    labor_uplift: float = 1.15
    solder_paste_sg: float = 7.31
    solder_paste_cost_per_g: float = 0.065
    flux_cost_per_ml: float = 0.0055
    tool_maintenance_pct: float = 10.0


@dataclass(frozen=True)
class ConsumableCost:
    rtv_cost: float
    top_solder_paste_cost: float
    bottom_solder_paste_cost: float
    flux_cost: float
    total: float
    solder_paste_weight_g: float


@dataclass(frozen=True)
class PcbaBreakdown:
    pcb_components_mech: float
    nre_per_unit: float
    consumables: float
    material_cost: float
    manufacturing_cost: float
    moh: float
    foh: float
    profit_on_rm: float
    profit_on_va: float
    ohp: float
    r_and_d: float
    warranty: float
    sg_and_a: float
    total_cost: float
    rm_cost: float
    conversion_cost: float


@dataclass(frozen=True)
class PcbaEstimate:
    inputs: PcbaInputs
    process_costs: list[ProcessCost]
    selected_nre: list[dict]
    consumables: ConsumableCost
    breakdown: PcbaBreakdown
    percentages: dict[str, float]
    notes: list[str]


PROCESS_ROWS = [
    ("SMT-Top", "Label Printing & Pasting", 300.0, 11.0, 0.0066, 1.0, 1.0, 0.25),
    ("SMT-Top", "Bare Board Loading", 120.0, 2.0, 0.0175, 1.0, 1.0, 0.25),
    ("SMT-Top", "Screen Printing", 900.0, 15.0, 0.1346, 1.0, 1.0, 0.50),
    ("SMT-Top", "Solder Paste Inspection", 600.0, 15.0, 0.1911, 1.0, 1.0, 0.50),
    ("SMT-Top", "SMT Placement", 2400.0, 25.0, 1.1421, 1.0, 3.0, 2.00),
    ("SMT-Top", "Reflow Soldering", 600.0, 60.0, 0.0996, 1.0, 1.0, 0.50),
    ("SMT-Top", "AOI", 900.0, 30.0, 0.1833, 1.0, 1.0, 0.50),
    ("SMT-Top", "X-Ray", 300.0, 18.0, 0.5206, 1.0, 1.0, 0.50),
    ("SMT-Bottom", "Label Printing & Pasting", 300.0, 11.0, 0.0066, 1.0, 1.0, 0.25),
    ("SMT-Bottom", "Bare Board Loading", 120.0, 2.0, 0.0175, 1.0, 1.0, 0.25),
    ("SMT-Bottom", "Screen Printing", 900.0, 15.0, 0.1346, 1.0, 1.0, 0.50),
    ("SMT-Bottom", "Solder Paste Inspection", 600.0, 15.0, 0.1911, 1.0, 1.0, 0.50),
    ("SMT-Bottom", "SMT Placement", 2400.0, 25.0, 1.1421, 1.0, 3.0, 2.00),
    ("SMT-Bottom", "Reflow Soldering", 600.0, 60.0, 0.0996, 1.0, 1.0, 0.50),
    ("SMT-Bottom", "AOI", 900.0, 30.0, 0.1833, 1.0, 1.0, 0.50),
    ("SMT-Bottom", "X-Ray", 300.0, 18.0, 0.5206, 1.0, 1.0, 0.50),
    ("Manual/TH Line", "Offline Activities", 300.0, 60.0, 0.0144, 1.0, 10.0, 1.00),
    ("Manual/TH Line", "Singulating Machine", 120.0, 40.0, 0.0128, 1.0, 1.0, 0.25),
    ("Manual/TH Line", "Manual Component Insertion", 300.0, 12.0, 0.0144, 1.0, 10.0, 1.00),
    ("Manual/TH Line", "Pre-Wave Inspection", 0.0, 10.0, 0.0144, 1.0, 2.0, 0.25),
    ("Manual/TH Line", "Wave Soldering", 600.0, 60.0, 0.3028, 1.0, 1.0, 0.25),
    ("Manual/TH Line", "Post Wave Inspection", 0.0, 20.0, 0.0144, 1.0, 2.0, 0.25),
    ("Manual/TH Line", "Manual Soldering/Touchup/Rework", 0.0, 50.0, 0.0144, 1.0, 2.0, 0.25),
    ("Manual/TH Line", "Final Inspection", 0.0, 20.0, 0.0144, 1.0, 2.0, 0.25),
    ("Testing/Box Build", "ICT", 600.0, 60.0, 0.5270, 1.0, 2.0, 0.00),
    ("Testing/Box Build", "Integration", 300.0, 60.0, 0.0144, 1.0, 2.0, 0.50),
    ("Testing/Box Build", "Box Build", 600.0, 90.0, 0.0144, 1.0, 3.0, 0.50),
    ("Testing/Box Build", "Functional Test", 300.0, 60.0, 0.5270, 1.0, 2.0, 0.00),
    ("Testing/Box Build", "OBA", 0.0, 30.0, 0.0144, 1.0, 2.0, 0.25),
]

PROCESS_STEPS = [ProcessStep(*row) for row in PROCESS_ROWS]

NRE_ITEMS = {
    "Stencil: DEK 265GSX (Top)": NreItem("Stencil: DEK 265GSX (Top)", 140, 100000),
    "Stencil: DEK 265GSX (Bottom)": NreItem("Stencil: DEK 265GSX (Bottom)", 140, 100000),
    "Printer Base Block": NreItem("Printer Base Block", 375, 500000),
    "SMT Programming Placement": NreItem("SMT Programming Placement", 20, 500000),
    "SMT Programming Vision": NreItem("SMT Programming Vision", 20, 500000),
    "SMT Pallet": NreItem("SMT Pallet", 200, 500000),
    "Dipping Pallet": NreItem("Dipping Pallet", 180, 500000),
    "Assembly Fixture": NreItem("Assembly Fixture", 300, 500000),
    "Gold Finger Clip": NreItem("Gold Finger Clip", 30, 100000),
    "Pneumatic Press": NreItem("Pneumatic Press", 1500, 500000),
    "Rubber Stamp": NreItem("Rubber Stamp", 5, 100000),
    "Press Riveter": NreItem("Press Riveter", 150, 500000),
    "Heatsink Assembly Jig": NreItem("Heatsink Assembly Jig", 150, 100000),
    "Programming Socket": NreItem("Programming Socket", 250, 500000),
    "Gluing Fixture": NreItem("Gluing Fixture", 100, 500000),
    "Wave Soldering Pallet - Selective": NreItem("Wave Soldering Pallet - Selective", 455, 500000),
    "Wave Soldering Pallet - Normal": NreItem("Wave Soldering Pallet - Normal", 450, 500000),
    "Depaneling Fixture": NreItem("Depaneling Fixture", 200, 500000),
    "Conformal Coating Fixture": NreItem("Conformal Coating Fixture", 1000, 500000),
}

OHP_PERCENTAGES = {
    "<100K": {"MOH %": 1.0, "FOH %": 12.5, "Profit on RM %": 1.5, "Profit on VA %": 8.0, "R&D %": 1.0, "Warranty %": 1.0, "SG&A %": 3.0},
    ">100K": {"MOH %": 1.0, "FOH %": 12.5, "Profit on RM %": 1.0, "Profit on VA %": 8.0, "R&D %": 2.0, "Warranty %": 1.0, "SG&A %": 2.0},
    "5K/10K": {"MOH %": 1.0, "FOH %": 20.0, "Profit on RM %": 1.0, "Profit on VA %": 8.0, "R&D %": 3.0, "Warranty %": 1.0, "SG&A %": 4.0},
}


def default_process_names(include_bottom: bool = True, include_manual: bool = True, include_test: bool = True) -> list[str]:
    names = []
    for step in PROCESS_STEPS:
        if step.side == "SMT-Bottom" and not include_bottom:
            continue
        if step.side == "Manual/TH Line" and not include_manual:
            continue
        if step.side == "Testing/Box Build" and not include_test:
            continue
        names.append(_process_key(step))
    return names


def _process_key(step: ProcessStep) -> str:
    return f"{step.side} - {step.stage}"


def estimate_pcba_cost(inputs: PcbaInputs) -> PcbaEstimate:
    if inputs.annual_volume <= 0:
        raise ValueError("annual_volume must be > 0")
    if inputs.product_life_years <= 0:
        raise ValueError("product_life_years must be > 0")
    if inputs.batch_qty <= 0:
        raise ValueError("batch_qty must be > 0")
    if inputs.volume_band not in OHP_PERCENTAGES:
        raise ValueError("unknown volume_band")

    selected_keys = set(inputs.selected_processes)
    process_costs = [_cost_process(step, inputs) for step in PROCESS_STEPS if _process_key(step) in selected_keys]
    nre_selected = _cost_nre(inputs)
    consumables = _cost_consumables(inputs)

    batch_setup = sum(row.batch_setup_cost for row in process_costs)
    va_machine = sum(row.va_machine_cost for row in process_costs)
    labor = sum(row.labor_cost for row in process_costs)
    manufacturing = batch_setup + va_machine + labor

    pcb_comp_mech = inputs.pcb_cost + inputs.electronics_component_cost + inputs.mechanical_component_cost
    nre_per_unit = sum(row["extended_price"] for row in nre_selected) * (1 + inputs.tool_maintenance_pct / 100) / (inputs.annual_volume * inputs.product_life_years)
    material_cost = pcb_comp_mech + nre_per_unit + consumables.total

    pct = OHP_PERCENTAGES[inputs.volume_band]
    moh = pcb_comp_mech * pct["MOH %"] / 100
    foh = manufacturing * pct["FOH %"] / 100
    profit_rm = pcb_comp_mech * pct["Profit on RM %"] / 100
    profit_va = manufacturing * pct["Profit on VA %"] / 100
    ohp = moh + foh + profit_rm + profit_va
    base = material_cost + manufacturing
    r_and_d = base * pct["R&D %"] / 100
    warranty = base * pct["Warranty %"] / 100
    sg_and_a = base * pct["SG&A %"] / 100
    total = base + ohp + r_and_d + warranty + sg_and_a

    breakdown = PcbaBreakdown(
        pcb_components_mech=round(pcb_comp_mech, 4),
        nre_per_unit=round(nre_per_unit, 4),
        consumables=round(consumables.total, 4),
        material_cost=round(material_cost, 4),
        manufacturing_cost=round(manufacturing, 4),
        moh=round(moh, 4),
        foh=round(foh, 4),
        profit_on_rm=round(profit_rm, 4),
        profit_on_va=round(profit_va, 4),
        ohp=round(ohp, 4),
        r_and_d=round(r_and_d, 4),
        warranty=round(warranty, 4),
        sg_and_a=round(sg_and_a, 4),
        total_cost=round(total, 4),
        rm_cost=round(material_cost, 4),
        conversion_cost=round(total - material_cost, 4),
    )
    notes = [
        "Process costs use mapped machine rate per second, batch setup amortization, and DL/IDL labor factors.",
        "NRE quantity for lifecycle volume uses max(product volume, tool life) divided by tool life, then applies tool maintenance and amortizes per board.",
        "Consumables include RTV, top/bottom solder paste, and flux using board-area based formulas.",
    ]
    return PcbaEstimate(inputs, process_costs, nre_selected, consumables, breakdown, pct, notes)


def _cost_process(step: ProcessStep, inputs: PcbaInputs) -> ProcessCost:
    batch_setup_cost = (((step.batch_setup_sec * inputs.labor_cost_hr) / 3600) * inputs.labor_uplift * step.setup_fte) / inputs.batch_qty
    va_machine_cost = step.process_cycle_sec * step.mmr_per_sec
    labor_cost = (
        (((step.process_cycle_sec * inputs.labor_cost_hr) / 3600) * inputs.labor_uplift) * step.dl_fte
        + (((step.process_cycle_sec * inputs.idl_cost_hr) / 3600) * inputs.labor_uplift) * step.idl_fte
    )
    total = batch_setup_cost + va_machine_cost + labor_cost
    return ProcessCost(step.side, step.stage, round(batch_setup_cost, 4), round(va_machine_cost, 4), round(labor_cost, 4), round(total, 4))


def _cost_nre(inputs: PcbaInputs) -> list[dict]:
    product_volume = inputs.annual_volume * inputs.product_life_years
    rows = []
    for name in inputs.selected_nre_items:
        item = NRE_ITEMS[name]
        qty_for_lcv = max(product_volume, item.life_cycle_boards) / item.life_cycle_boards
        extended = item.unit_price * qty_for_lcv
        rows.append({
            "item": item.item,
            "unit_price": round(item.unit_price, 4),
            "life_cycle_boards": item.life_cycle_boards,
            "qty_for_lcv": round(qty_for_lcv, 4),
            "extended_price": round(extended, 4),
        })
    return rows


def _cost_consumables(inputs: PcbaInputs) -> ConsumableCost:
    board_area = inputs.board_length_mm * inputs.board_width_mm
    rtv_weight = inputs.rtv_weight_estimate * inputs.rtv_specific_gravity * (1 + inputs.rtv_wastage_pct / 100)
    rtv_cost = rtv_weight * inputs.rtv_cost_per_ml

    top_weight_100 = board_area * inputs.top_solder_paste_thickness_mm * inputs.solder_paste_sg / 1000
    top_weight = top_weight_100 * (inputs.top_weight_estimate_pct / 100) * (1 + inputs.solder_paste_wastage_pct / 100)
    top_cost = top_weight * inputs.solder_paste_cost_per_g

    bottom_weight_100 = board_area * inputs.bottom_solder_paste_thickness_mm * inputs.solder_paste_sg / 1000
    bottom_weight = bottom_weight_100 * (inputs.bottom_weight_estimate_pct / 100) * (1 + inputs.solder_paste_wastage_pct / 100)
    bottom_cost = bottom_weight * inputs.solder_paste_cost_per_g

    flux_spray_area = ((board_area / 100) * 0.1) * (1 + inputs.flux_wastage_pct / 100)
    flux_cost = flux_spray_area * inputs.flux_cost_per_ml
    total = rtv_cost + top_cost + bottom_cost + flux_cost
    return ConsumableCost(round(rtv_cost, 4), round(top_cost, 4), round(bottom_cost, 4), round(flux_cost, 4), round(total, 4), round(top_weight + bottom_weight, 4))
