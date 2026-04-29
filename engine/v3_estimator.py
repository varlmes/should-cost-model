"""Workbook-free V3 bottom-up should-cost calculator.

This module ports the V3 platform's core calculation flow into local dataclasses
so the Streamlit app can run it without the original FastAPI/React stack.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialOption:
    grade: str
    material_type: str
    rate_per_kg: float
    scrap_recovery_pct: float


@dataclass(frozen=True)
class MachineOption:
    name: str
    machine_type: str
    hourly_rate: float


@dataclass(frozen=True)
class ProcessTemplate:
    name: str
    commodity_type: str
    machine_name: str | None
    cycle_time_min: float
    setup_time_min: float
    batch_size: int
    operators: int
    labor_rate_per_hr: float
    tooling_cost_per_unit: float


@dataclass(frozen=True)
class OverheadProfile:
    name: str
    factory_overhead_pct: float
    admin_overhead_pct: float
    depreciation_pct: float
    quality_cost_pct: float
    profit_margin_pct: float
    taxes_duties_pct: float
    sga_pct: float
    packaging_per_unit: float
    freight_per_unit: float
    other_logistics_per_unit: float


@dataclass(frozen=True)
class MaterialInput:
    name: str
    grade: str
    finished_mass_kg: float
    utilization_rate: float
    price_per_kg: float
    scrap_recovery_pct: float = 0.35
    price_source: str = "seeded rate"
    confidence: str = "medium"


@dataclass(frozen=True)
class ProcessStepInput:
    step_name: str
    machine_type: str
    machine_rate_per_hr: float
    cycle_time_min: float
    setup_time_min: float = 0.0
    operators: int = 1
    labor_rate_per_hr: float = 0.0
    tooling_cost_per_unit: float = 0.0
    rate_source: str = "seeded rate"
    confidence: str = "medium"


@dataclass(frozen=True)
class ToolingNreInput:
    item: str
    cost: float
    life_units: int
    source: str = "estimated"
    confidence: str = "medium"


@dataclass(frozen=True)
class LogisticsInput:
    packaging_per_unit: float = 0.0
    freight_per_unit: float = 0.0
    other_per_unit: float = 0.0
    source: str = "estimated"


@dataclass(frozen=True)
class CostSheetInput:
    product_name: str
    currency: str
    current_quoted_price: float
    annual_volume: int
    batch_size: int
    materials: list[MaterialInput]
    process_steps: list[ProcessStepInput]
    tooling_nre: list[ToolingNreInput]
    learning_curve_factor: float
    overhead: OverheadProfile
    logistics: LogisticsInput


@dataclass(frozen=True)
class LineItem:
    category: str
    item: str
    value: float
    detail: str = ""
    source: str = ""
    confidence: str = "medium"


@dataclass(frozen=True)
class ResultSummary:
    total_material_gross: float
    total_scrap_credit: float
    total_material_net: float
    total_conversion: float
    total_labor: float
    total_tooling_nre: float
    total_overhead: float
    total_sga: float
    total_profit: float
    total_taxes: float
    total_logistics: float
    should_cost: float
    current_price: float
    gap: float
    gap_pct: float
    annual_volume: int
    annual_opportunity: float


@dataclass(frozen=True)
class SensitivityItem:
    driver: str
    new_should_cost: float
    impact: float
    impact_pct: float


@dataclass(frozen=True)
class VolumeAnalysisItem:
    annual_volume: int
    batch_size: int
    should_cost_per_unit: float
    delta_vs_base: float
    delta_pct: float


@dataclass(frozen=True)
class Recommendation:
    severity: str
    title: str
    description: str
    category: str
    potential_savings_pct: float = 0.0


@dataclass(frozen=True)
class CostSheetResult:
    product: str
    currency: str
    line_items: list[LineItem]
    summary: ResultSummary
    confidence_summary: dict[str, int]
    confidence_warning: str | None
    low_confidence_items: list[str]
    sensitivity: list[SensitivityItem]
    volume_analysis: list[VolumeAnalysisItem]
    recommendations: list[Recommendation]


MATERIALS: dict[str, MaterialOption] = {
    "EN8 (Medium Carbon Steel)": MaterialOption("EN8 (Medium Carbon Steel)", "Steel", 68, 0.35),
    "EN19 (Alloy Steel)": MaterialOption("EN19 (Alloy Steel)", "Steel", 95, 0.35),
    "EN24 (High Tensile Steel)": MaterialOption("EN24 (High Tensile Steel)", "Steel", 112, 0.35),
    "SS304 (Stainless Steel)": MaterialOption("SS304 (Stainless Steel)", "Steel", 210, 0.40),
    "IS2062 E250 (Mild Steel)": MaterialOption("IS2062 E250 (Mild Steel)", "Steel", 58, 0.30),
    "42CrMo4 (Chromoly Steel)": MaterialOption("42CrMo4 (Chromoly Steel)", "Steel", 130, 0.35),
    "ADC12 (Aluminium Die Cast)": MaterialOption("ADC12 (Aluminium Die Cast)", "Aluminum", 185, 0.40),
    "A356 (Aluminium Sand Cast)": MaterialOption("A356 (Aluminium Sand Cast)", "Aluminum", 175, 0.38),
    "GG25 (Grey Cast Iron)": MaterialOption("GG25 (Grey Cast Iron)", "Cast Iron", 52, 0.25),
    "SG500 (Ductile Iron)": MaterialOption("SG500 (Ductile Iron)", "Cast Iron", 62, 0.28),
    "IS 2062 E350 (Structural Steel)": MaterialOption("IS 2062 E350 (Structural Steel)", "Steel", 65, 0.30),
}

MACHINES: dict[str, MachineOption] = {
    "CNC Machining Center": MachineOption("CNC Machining Center", "CNC", 1800),
    "VMC 850 (Vertical Machining Center)": MachineOption("VMC 850 (Vertical Machining Center)", "CNC", 2000),
    "Hydraulic Press 500T": MachineOption("Hydraulic Press 500T", "Press", 2200),
    "Hydraulic Press 1000T": MachineOption("Hydraulic Press 1000T", "Press", 3200),
    "Induction Heater": MachineOption("Induction Heater", "Heater", 1600),
    "Heat Treatment Furnace": MachineOption("Heat Treatment Furnace", "Furnace", 1400),
    "Shot Blasting Machine": MachineOption("Shot Blasting Machine", "Blasting", 800),
    "Lathe Machine": MachineOption("Lathe Machine", "Lathe", 1200),
    "MIG Welding Station": MachineOption("MIG Welding Station", "Welding", 950),
    "TIG Welding Station": MachineOption("TIG Welding Station", "Welding", 1200),
    "Plasma Cutting Machine": MachineOption("Plasma Cutting Machine", "Cutting", 1100),
    "Press Brake 200T": MachineOption("Press Brake 200T", "Press", 1100),
    "Sand Casting Setup": MachineOption("Sand Casting Setup", "Casting", 900),
    "Die Casting Machine 400T": MachineOption("Die Casting Machine 400T", "Casting", 2500),
    "Fettling & Grinding": MachineOption("Fettling & Grinding", "Grinding", 750),
    "Manual / Bench Operation": MachineOption("Manual / Bench Operation", "Manual", 0),
}

PROCESS_TEMPLATES: dict[str, list[ProcessTemplate]] = {
    "Forging": [
        ProcessTemplate("Billet Cutting", "Forging", "Lathe Machine", 3, 15, 200, 1, 350, 2),
        ProcessTemplate("Induction Heating", "Forging", "Induction Heater", 5, 20, 200, 1, 300, 0),
        ProcessTemplate("Forging Press", "Forging", "Hydraulic Press 500T", 2, 30, 200, 2, 400, 15),
        ProcessTemplate("Trimming", "Forging", "Hydraulic Press 500T", 1.5, 15, 200, 1, 350, 5),
        ProcessTemplate("Heat Treatment", "Forging", "Heat Treatment Furnace", 15, 30, 100, 1, 300, 0),
        ProcessTemplate("Shot Blasting", "Forging", "Shot Blasting Machine", 5, 10, 100, 1, 250, 0),
        ProcessTemplate("CNC Machining", "Forging", "CNC Machining Center", 8, 25, 50, 1, 450, 25),
    ],
    "Casting": [
        ProcessTemplate("Pattern Making", "Casting", None, 60, 120, 1, 2, 500, 50),
        ProcessTemplate("Mould Preparation", "Casting", "Sand Casting Setup", 20, 30, 10, 2, 350, 10),
        ProcessTemplate("Melting & Pouring", "Casting", "Sand Casting Setup", 10, 30, 20, 2, 400, 5),
        ProcessTemplate("Shakeout & Cleaning", "Casting", "Fettling & Grinding", 15, 10, 20, 1, 280, 0),
        ProcessTemplate("Fettling & Grinding", "Casting", "Fettling & Grinding", 10, 10, 20, 1, 280, 8),
        ProcessTemplate("Heat Treatment (Casting)", "Casting", "Heat Treatment Furnace", 20, 30, 50, 1, 300, 0),
        ProcessTemplate("CNC Machining (Casting)", "Casting", "VMC 850 (Vertical Machining Center)", 10, 30, 25, 1, 450, 30),
    ],
    "Fabrication": [
        ProcessTemplate("Laser / Plasma Cutting", "Fabrication", "Plasma Cutting Machine", 5, 15, 50, 1, 380, 3),
        ProcessTemplate("Sheet Bending", "Fabrication", "Press Brake 200T", 4, 20, 50, 1, 350, 5),
        ProcessTemplate("MIG Welding", "Fabrication", "MIG Welding Station", 12, 20, 20, 2, 400, 8),
        ProcessTemplate("TIG Welding", "Fabrication", "TIG Welding Station", 20, 25, 10, 1, 500, 12),
        ProcessTemplate("Surface Treatment / Painting", "Fabrication", None, 15, 20, 20, 1, 300, 20),
        ProcessTemplate("Assembly & Fastening", "Fabrication", None, 10, 15, 20, 2, 350, 5),
        ProcessTemplate("Inspection & Dispatch", "Fabrication", None, 5, 10, 50, 1, 280, 0),
    ],
}

OVERHEAD_PROFILES: dict[str, OverheadProfile] = {
    "India - Standard Forging": OverheadProfile("India - Standard Forging", 0.12, 0.08, 0.05, 0.03, 0.10, 0.05, 0.08, 50, 80, 20),
    "India - Automotive Tier 1": OverheadProfile("India - Automotive Tier 1", 0.15, 0.10, 0.07, 0.05, 0.08, 0.05, 0.07, 80, 120, 30),
    "India - Export / IATF": OverheadProfile("India - Export / IATF", 0.18, 0.12, 0.08, 0.06, 0.12, 0.00, 0.09, 120, 350, 50),
    "India - Small Foundry": OverheadProfile("India - Small Foundry", 0.10, 0.06, 0.04, 0.02, 0.12, 0.05, 0.06, 30, 60, 10),
}


def calculate_should_cost(inp: CostSheetInput) -> CostSheetResult:
    currency = inp.currency
    line_items: list[LineItem] = []
    total_material_cost = 0.0
    total_scrap_credit = 0.0

    for mat in inp.materials:
        buy_weight = mat.finished_mass_kg / mat.utilization_rate if mat.utilization_rate > 0 else 0.0
        gross_mat_cost = buy_weight * mat.price_per_kg
        scrap_weight = buy_weight - mat.finished_mass_kg
        scrap_credit = scrap_weight * mat.price_per_kg * mat.scrap_recovery_pct
        net_mat_cost = gross_mat_cost - scrap_credit
        total_material_cost += net_mat_cost
        total_scrap_credit += scrap_credit
        line_items.append(LineItem(
            category="Material",
            item=f"{mat.name} ({mat.grade})",
            value=round(net_mat_cost, 2),
            detail=(
                f"{mat.finished_mass_kg:.2f}kg finished / {mat.utilization_rate:.0%} util = {buy_weight:.2f}kg buy "
                f"x {currency} {mat.price_per_kg:.2f}/kg - {currency} {scrap_credit:.2f} scrap credit"
            ),
            source=mat.price_source,
            confidence=mat.confidence,
        ))

    total_conversion_cost = 0.0
    total_labor_cost = 0.0
    total_inline_tooling = 0.0
    batch_size = max(1, inp.batch_size)

    for step in inp.process_steps:
        machine_cost = (step.cycle_time_min / 60) * step.machine_rate_per_hr
        setup_cost_per_part = (step.setup_time_min / 60) * step.machine_rate_per_hr / batch_size
        labor_time_min = step.cycle_time_min + (step.setup_time_min / batch_size)
        labor_cost = (labor_time_min / 60) * step.labor_rate_per_hr * step.operators
        step_total = machine_cost + setup_cost_per_part + labor_cost + step.tooling_cost_per_unit
        total_conversion_cost += machine_cost + setup_cost_per_part
        total_labor_cost += labor_cost
        total_inline_tooling += step.tooling_cost_per_unit
        line_items.append(LineItem(
            category="Conversion",
            item=f"{step.step_name} ({step.machine_type})",
            value=round(step_total, 2),
            detail=(
                f"Machine {step.cycle_time_min:.1f}min @ {currency} {step.machine_rate_per_hr:.0f}/hr = {currency} {machine_cost:.2f}; "
                f"setup {currency} {setup_cost_per_part:.2f}/unit; labor {currency} {labor_cost:.2f}; tooling {currency} {step.tooling_cost_per_unit:.2f}"
            ),
            source=step.rate_source,
            confidence=step.confidence,
        ))

    if inp.learning_curve_factor < 1.0:
        lr_reduction_conv = total_conversion_cost * (1 - inp.learning_curve_factor)
        lr_reduction_labor = total_labor_cost * (1 - inp.learning_curve_factor)
        total_conversion_cost -= lr_reduction_conv
        total_labor_cost -= lr_reduction_labor
        line_items.append(LineItem(
            category="Learning Curve",
            item=f"Learning curve adjustment ({(1 - inp.learning_curve_factor):.0%} reduction)",
            value=round(-(lr_reduction_conv + lr_reduction_labor), 2),
            detail=f"Conversion -{currency} {lr_reduction_conv:.2f}; labor -{currency} {lr_reduction_labor:.2f}",
            source="user input",
            confidence="medium",
        ))

    total_tooling_per_unit = total_inline_tooling
    for tool in inp.tooling_nre:
        per_unit = tool.cost / tool.life_units if tool.life_units > 0 else 0.0
        total_tooling_per_unit += per_unit
        line_items.append(LineItem(
            category="Tooling/NRE",
            item=tool.item,
            value=round(per_unit, 2),
            detail=f"{currency} {tool.cost:,.0f} total / {tool.life_units:,} units = {currency} {per_unit:.2f}/unit",
            source=tool.source,
            confidence=tool.confidence,
        ))

    oh = inp.overhead
    overhead_base = total_conversion_cost + total_labor_cost
    factory_oh = overhead_base * oh.factory_overhead_pct
    admin_oh = overhead_base * oh.admin_overhead_pct
    depreciation = overhead_base * oh.depreciation_pct
    quality = overhead_base * oh.quality_cost_pct
    total_overhead = factory_oh + admin_oh + depreciation + quality
    for item, pct, value in [
        ("Factory overhead", oh.factory_overhead_pct, factory_oh),
        ("Admin overhead", oh.admin_overhead_pct, admin_oh),
        ("Depreciation", oh.depreciation_pct, depreciation),
        ("Quality cost", oh.quality_cost_pct, quality),
    ]:
        if value > 0:
            line_items.append(LineItem("Overhead", f"{item} ({pct:.0%})", round(value, 2), f"{currency} {overhead_base:.2f} x {pct:.0%}", oh.name, "medium"))

    total_factory_cost = total_material_cost + total_conversion_cost + total_labor_cost + total_overhead + total_tooling_per_unit
    sga_cost = total_factory_cost * oh.sga_pct
    profit_base = total_factory_cost + sga_cost
    profit_cost = profit_base * oh.profit_margin_pct
    taxes = profit_base * oh.taxes_duties_pct
    total_logistics = inp.logistics.packaging_per_unit + inp.logistics.freight_per_unit + inp.logistics.other_per_unit

    line_items.extend([
        LineItem("SGA", f"Selling, general & admin ({oh.sga_pct:.0%})", round(sga_cost, 2), f"{currency} {total_factory_cost:.2f} x {oh.sga_pct:.0%}", oh.name, "medium"),
        LineItem("Profit", f"Supplier profit ({oh.profit_margin_pct:.0%})", round(profit_cost, 2), f"{currency} {profit_base:.2f} x {oh.profit_margin_pct:.0%}", oh.name, "medium"),
    ])
    if taxes > 0:
        line_items.append(LineItem("Taxes", f"Taxes & duties ({oh.taxes_duties_pct:.0%})", round(taxes, 2), f"{currency} {profit_base:.2f} x {oh.taxes_duties_pct:.0%}", oh.name, "medium"))
    if total_logistics > 0:
        line_items.append(LineItem("Logistics", "Packaging + freight + other", round(total_logistics, 2), f"Pkg {currency} {inp.logistics.packaging_per_unit:.2f}; freight {currency} {inp.logistics.freight_per_unit:.2f}; other {currency} {inp.logistics.other_per_unit:.2f}", inp.logistics.source, "medium"))

    should_cost = total_factory_cost + sga_cost + profit_cost + taxes + total_logistics
    gap = inp.current_quoted_price - should_cost
    gap_pct = gap / inp.current_quoted_price * 100 if inp.current_quoted_price > 0 else 0.0
    annual_opportunity = gap * inp.annual_volume

    summary = ResultSummary(
        total_material_gross=round(total_material_cost + total_scrap_credit, 2),
        total_scrap_credit=round(-total_scrap_credit, 2),
        total_material_net=round(total_material_cost, 2),
        total_conversion=round(total_conversion_cost, 2),
        total_labor=round(total_labor_cost, 2),
        total_tooling_nre=round(total_tooling_per_unit, 2),
        total_overhead=round(total_overhead, 2),
        total_sga=round(sga_cost, 2),
        total_profit=round(profit_cost, 2),
        total_taxes=round(taxes, 2),
        total_logistics=round(total_logistics, 2),
        should_cost=round(should_cost, 2),
        current_price=round(inp.current_quoted_price, 2),
        gap=round(gap, 2),
        gap_pct=round(gap_pct, 1),
        annual_volume=inp.annual_volume,
        annual_opportunity=round(annual_opportunity, 2),
    )

    confidence_summary = {"high": 0, "medium": 0, "low": 0}
    for item in line_items:
        confidence_summary[item.confidence.lower()] = confidence_summary.get(item.confidence.lower(), 0) + 1
    total_items = sum(confidence_summary.values())
    confidence_warning = None
    if total_items and confidence_summary.get("medium", 0) > 0.7 * total_items:
        confidence_warning = "More than 70% of assumptions are medium confidence; verify the highest-cost drivers."
    low_confidence_items = [item.item for item in line_items if item.confidence.lower() == "low"]

    result = CostSheetResult(
        product=inp.product_name,
        currency=currency,
        line_items=line_items,
        summary=summary,
        confidence_summary=confidence_summary,
        confidence_warning=confidence_warning,
        low_confidence_items=low_confidence_items,
        sensitivity=_compute_sensitivity(inp, should_cost, total_conversion_cost, total_labor_cost, overhead_base, oh),
        volume_analysis=_compute_volume_analysis(inp, should_cost, total_material_cost, total_logistics, oh),
        recommendations=[],
    )
    return CostSheetResult(**{**result.__dict__, "recommendations": get_recommendations(result)})


def _compute_sensitivity(inp: CostSheetInput, base_cost: float, total_conversion_cost: float, total_labor_cost: float, overhead_base: float, oh: OverheadProfile) -> list[SensitivityItem]:
    sensitivity: list[SensitivityItem] = []
    margin_mult = (1 + oh.sga_pct) * (1 + oh.profit_margin_pct)
    for mat in inp.materials:
        buy_weight = mat.finished_mass_kg / mat.utilization_rate if mat.utilization_rate > 0 else 0.0
        base_mat = buy_weight * mat.price_per_kg
        for label, factor in [("-20%", 0.8), ("+20%", 1.2)]:
            delta = base_mat * (factor - 1)
            new_total = base_cost + delta * (1 + oh.factory_overhead_pct) * margin_mult
            sensitivity.append(_sens(f"{mat.name} price {label}", new_total, base_cost))

    total_cycle_conv = sum((s.cycle_time_min / 60) * s.machine_rate_per_hr for s in inp.process_steps)
    for label, factor in [("-20%", 0.8), ("+20%", 1.2)]:
        delta = total_cycle_conv * (factor - 1)
        new_total = base_cost + delta * (1 + oh.factory_overhead_pct) * margin_mult
        sensitivity.append(_sens(f"Cycle time {label}", new_total, base_cost))

    for label, factor in [("-20%", 0.8), ("+20%", 1.2)]:
        delta = total_labor_cost * (factor - 1)
        new_total = base_cost + delta * (1 + oh.factory_overhead_pct) * margin_mult
        sensitivity.append(_sens(f"Labor rate {label}", new_total, base_cost))

    for label, factor in [("-20%", 0.8), ("+20%", 1.2)]:
        delta = overhead_base * oh.factory_overhead_pct * (factor - 1)
        new_total = base_cost + delta * margin_mult
        sensitivity.append(_sens(f"Factory overhead {label}", new_total, base_cost))
    return sensitivity


def _sens(driver: str, new_total: float, base_cost: float) -> SensitivityItem:
    impact = new_total - base_cost
    return SensitivityItem(driver, round(new_total, 2), round(impact, 2), round(impact / base_cost * 100, 1) if base_cost else 0.0)


def _compute_volume_analysis(inp: CostSheetInput, base_should_cost: float, total_material_cost: float, total_logistics: float, oh: OverheadProfile) -> list[VolumeAnalysisItem]:
    results: list[VolumeAnalysisItem] = []
    for mult in [0.5, 1.0, 2.0, 5.0]:
        vol = max(1, int(inp.annual_volume * mult))
        adj_batch = max(50, min(1000, int(inp.batch_size * mult)))
        adj_conversion = 0.0
        adj_labor = 0.0
        adj_tooling_inline = 0.0
        for step in inp.process_steps:
            adj_conversion += (step.cycle_time_min / 60) * step.machine_rate_per_hr
            adj_conversion += (step.setup_time_min / 60) * step.machine_rate_per_hr / adj_batch
            labor_time = step.cycle_time_min + step.setup_time_min / adj_batch
            adj_labor += (labor_time / 60) * step.labor_rate_per_hr * step.operators
            adj_tooling_inline += step.tooling_cost_per_unit
        adj_conversion *= inp.learning_curve_factor
        adj_labor *= inp.learning_curve_factor
        adj_tooling = adj_tooling_inline
        for tool in inp.tooling_nre:
            life = max(1, vol * max(1, tool.life_units // max(1, inp.annual_volume)))
            adj_tooling += tool.cost / life
        adj_oh_base = adj_conversion + adj_labor
        adj_oh = adj_oh_base * (oh.factory_overhead_pct + oh.admin_overhead_pct + oh.depreciation_pct + oh.quality_cost_pct)
        adj_factory = total_material_cost + adj_conversion + adj_labor + adj_oh + adj_tooling
        adj_sga = adj_factory * oh.sga_pct
        adj_profit = (adj_factory + adj_sga) * oh.profit_margin_pct
        adj_taxes = (adj_factory + adj_sga) * oh.taxes_duties_pct
        adj_total = adj_factory + adj_sga + adj_profit + adj_taxes + total_logistics
        results.append(VolumeAnalysisItem(vol, adj_batch, round(adj_total, 2), round(adj_total - base_should_cost, 2), round((adj_total - base_should_cost) / base_should_cost * 100, 1) if base_should_cost else 0.0))
    return results


def get_recommendations(result: CostSheetResult) -> list[Recommendation]:
    s = result.summary
    recs: list[Recommendation] = []
    if s.should_cost > 0 and s.total_material_net / s.should_cost > 0.60:
        recs.append(Recommendation("high", "Material cost dominates total cost", "Focus negotiation on material pricing, utilization, scrap credit, and index-linked contracts.", "material", 5.0))
    if s.total_material_gross > 0:
        effective_util = 1 - (abs(s.total_scrap_credit) / s.total_material_gross)
        if effective_util < 0.70:
            recs.append(Recommendation("medium", "Low effective material utilization", "Review gross-to-net mass, nesting, forging/casting yield, and scrap recovery terms.", "material", 3.0))
    if s.current_price > 0 and s.gap_pct > 15:
        recs.append(Recommendation("high", f"Significant price gap of {s.gap_pct:.1f}%", f"Annual opportunity is {result.currency} {s.annual_opportunity:,.0f}; use the cost sheet as negotiation support.", "pricing", s.gap_pct * 0.5))
    if s.current_price > 0 and s.gap_pct < -5:
        recs.append(Recommendation("medium", "Supplier quote is below should-cost", "Validate assumptions and assess whether the supplier has a structural advantage or underpricing risk.", "pricing", 0.0))
    if s.should_cost > 0 and s.total_overhead / s.should_cost > 0.25:
        recs.append(Recommendation("medium", "Overhead is a large cost share", "Ask for overhead allocation logic and evaluate volume commitments or multi-shift absorption.", "overhead", 2.0))
    for va in result.volume_analysis:
        if va.annual_volume == result.summary.annual_volume * 2 and va.delta_pct < -10:
            recs.append(Recommendation("medium", f"Strong volume leverage: {abs(va.delta_pct):.1f}% at 2x volume", "Consider annual volume bundling, demand aggregation, or multi-year commitments.", "volume", abs(va.delta_pct) * 0.3))
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(recs, key=lambda rec: severity_order.get(rec.severity, 3))


def templates_to_steps(commodity_type: str, selected_names: list[str]) -> list[ProcessStepInput]:
    steps: list[ProcessStepInput] = []
    by_name = {tpl.name: tpl for tpl in PROCESS_TEMPLATES.get(commodity_type, [])}
    for name in selected_names:
        tpl = by_name[name]
        machine = MACHINES[tpl.machine_name or "Manual / Bench Operation"]
        steps.append(ProcessStepInput(
            step_name=tpl.name,
            machine_type=machine.machine_type,
            machine_rate_per_hr=machine.hourly_rate,
            cycle_time_min=tpl.cycle_time_min,
            setup_time_min=tpl.setup_time_min,
            operators=tpl.operators,
            labor_rate_per_hr=tpl.labor_rate_per_hr,
            tooling_cost_per_unit=tpl.tooling_cost_per_unit,
        ))
    return steps
