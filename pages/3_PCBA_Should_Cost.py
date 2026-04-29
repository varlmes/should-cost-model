import io

import pandas as pd
import streamlit as st

from engine.pcba_estimator import (
    NRE_ITEMS,
    OHP_PERCENTAGES,
    PROCESS_STEPS,
    PcbaInputs,
    default_process_names,
    estimate_pcba_cost,
)

st.set_page_config(page_title="PCBA Should-Cost", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
  .pcba-hero { background: radial-gradient(circle at 20% 10%, #3ed598 0, transparent 28%), linear-gradient(135deg, #081c24 0%, #12313c 55%, #314d2f 100%); color: #eefdf6; padding: 26px 30px; border: 1px solid rgba(255,255,255,.16); margin-bottom: 18px; }
  .pcba-kicker { letter-spacing: .18em; text-transform: uppercase; color: #a7f3c8; font-size: .72rem; }
  .pcba-price { font-size: 3rem; line-height: 1; font-weight: 700; margin: 10px 0 6px; }
  .pcba-band { color: #d4ffe6; }
  .rule { border: none; border-top: 1px solid #d6ddcf; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.4f}" if abs(value) < 10 else f"${value:,.2f}"


st.markdown("#### — Sourcing Operations Suite")
st.title("PCBA Should-Cost Estimator")
st.caption("Process mapping, cycle-time simulation, NRE amortization, consumables, RM, conversion, and OH&P costing.")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("pcba_costing"):
    c1, c2, c3, c4 = st.columns(4)
    part_id = c1.text_input("Assembly / PCB ID", value="PCBA-0001")
    annual_volume = c2.number_input("Annual Volume", min_value=1.0, value=100000.0, step=5000.0)
    product_life = c3.number_input("Product Life (years)", min_value=0.1, value=5.0, step=0.5)
    batch_qty = c4.number_input("Batch Qty", min_value=1.0, value=1666.67, step=100.0)

    st.subheader("01 — Input Cost")
    r1, r2, r3, r4 = st.columns(4)
    pcb_cost = r1.number_input("PCB ($/board)", min_value=0.0, value=4.50, step=0.25)
    electronics_cost = r2.number_input("Electronics Components ($)", min_value=0.0, value=26.00, step=0.50)
    mechanical_cost = r3.number_input("Mechanical Components ($)", min_value=0.0, value=2.25, step=0.25)
    volume_band = r4.selectbox("OHP Volume Band", list(OHP_PERCENTAGES.keys()), index=1)

    st.subheader("02 — Process Mapping")
    all_processes = [f"{step.side} - {step.stage}" for step in PROCESS_STEPS]
    default_processes = default_process_names(include_bottom=True, include_manual=True, include_test=True)
    selected_processes = st.multiselect("Selected PCBA process steps", all_processes, default=default_processes)
    p1, p2, p3 = st.columns(3)
    labor_cost_hr = p1.number_input("DL Labour Cost / Hr", min_value=0.0, value=2.81, step=0.10)
    idl_cost_hr = p2.number_input("IDL Cost / Hr", min_value=0.0, value=4.754, step=0.10)
    labor_uplift = p3.number_input("Labor Uplift Factor", min_value=1.0, value=1.15, step=0.01)

    st.subheader("03 — NRE")
    default_nre = [
        "Stencil: DEK 265GSX (Top)",
        "Stencil: DEK 265GSX (Bottom)",
        "Printer Base Block",
        "SMT Programming Placement",
        "SMT Programming Vision",
        "SMT Pallet",
        "Assembly Fixture",
        "Wave Soldering Pallet - Normal",
        "Depaneling Fixture",
    ]
    selected_nre = st.multiselect("Selected NRE / tooling items", list(NRE_ITEMS.keys()), default=[item for item in default_nre if item in NRE_ITEMS])
    tool_maintenance = st.slider("Tool Maintenance Rate", min_value=0.0, max_value=30.0, value=10.0, step=1.0)

    st.subheader("04 — Consumables")
    b1, b2, b3, b4 = st.columns(4)
    board_length = b1.number_input("Board Length (mm)", min_value=1.0, value=180.0, step=5.0)
    board_width = b2.number_input("Board Width (mm)", min_value=1.0, value=120.0, step=5.0)
    top_sp_thick = b3.number_input("Top Solder Paste Thick (mm)", min_value=0.0, value=0.12, step=0.01)
    bot_sp_thick = b4.number_input("Bottom Solder Paste Thick (mm)", min_value=0.0, value=0.10, step=0.01)

    s1, s2, s3, s4 = st.columns(4)
    top_weight_pct = s1.number_input("Top Weight Estimate %", min_value=0.0, value=12.0, step=1.0)
    bottom_weight_pct = s2.number_input("Bottom Weight Estimate %", min_value=0.0, value=10.0, step=1.0)
    sp_wastage = s3.number_input("Solder Paste Wastage %", min_value=0.0, value=10.0, step=1.0)
    flux_wastage = s4.number_input("Flux Wastage %", min_value=0.0, value=10.0, step=1.0)

    g1, g2, g3, g4 = st.columns(4)
    rtv_weight = g1.number_input("RTV Weight Estimate", min_value=0.0, value=1.5, step=0.1)
    rtv_wastage = g2.number_input("RTV Wastage %", min_value=0.0, value=5.0, step=1.0)
    rtv_cost = g3.number_input("RTV Cost / ml", min_value=0.0, value=0.08, step=0.01)
    rtv_sg = g4.number_input("RTV Specific Gravity", min_value=0.0, value=1.1, step=0.1)

    submitted = st.form_submit_button("Calculate PCBA Should-Cost", type="primary")

if submitted:
    try:
        inputs = PcbaInputs(
            part_id=part_id,
            annual_volume=float(annual_volume),
            product_life_years=float(product_life),
            batch_qty=float(batch_qty),
            pcb_cost=float(pcb_cost),
            electronics_component_cost=float(electronics_cost),
            mechanical_component_cost=float(mechanical_cost),
            board_length_mm=float(board_length),
            board_width_mm=float(board_width),
            top_solder_paste_thickness_mm=float(top_sp_thick),
            bottom_solder_paste_thickness_mm=float(bot_sp_thick),
            top_weight_estimate_pct=float(top_weight_pct),
            bottom_weight_estimate_pct=float(bottom_weight_pct),
            solder_paste_wastage_pct=float(sp_wastage),
            rtv_weight_estimate=float(rtv_weight),
            rtv_wastage_pct=float(rtv_wastage),
            rtv_cost_per_ml=float(rtv_cost),
            rtv_specific_gravity=float(rtv_sg),
            flux_wastage_pct=float(flux_wastage),
            selected_processes=selected_processes,
            selected_nre_items=selected_nre,
            volume_band=volume_band,
            labor_cost_hr=float(labor_cost_hr),
            idl_cost_hr=float(idl_cost_hr),
            labor_uplift=float(labor_uplift),
            tool_maintenance_pct=float(tool_maintenance),
        )
        st.session_state["pcba_estimate"] = estimate_pcba_cost(inputs)
    except Exception as exc:
        st.error(f"PCBA estimate failed: {exc}")

estimate = st.session_state.get("pcba_estimate")
if estimate:
    b = estimate.breakdown
    c = estimate.consumables
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("05 — Results")
    st.markdown(
        f"""
<div class="pcba-hero">
  <div class="pcba-kicker">PCBA Should-Cost — {estimate.inputs.part_id}</div>
  <div class="pcba-price">{money(b.total_cost)}</div>
  <div class="pcba-band">RM: {money(b.rm_cost)} | Conversion: {money(b.conversion_cost)} | Manufacturing: {money(b.manufacturing_cost)}</div>
  <div class="pcba-band">NRE/unit: {money(b.nre_per_unit)} | Consumables: {money(b.consumables)} | Volume band: {estimate.inputs.volume_band}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("RM Cost", money(b.rm_cost))
    k2.metric("Conversion Cost", money(b.conversion_cost))
    k3.metric("Total Cost", money(b.total_cost))
    k4.metric("Solder Paste", f"{c.solder_paste_weight_g:.3f} g")

    summary_df = pd.DataFrame([
        ("PCB + components + mechanical", b.pcb_components_mech),
        ("NRE per unit", b.nre_per_unit),
        ("Consumables", b.consumables),
        ("Material Cost", b.material_cost),
        ("Manufacturing Cost", b.manufacturing_cost),
        ("MOH", b.moh),
        ("FOH", b.foh),
        ("Profit on RM", b.profit_on_rm),
        ("Profit on VA", b.profit_on_va),
        ("OH&P", b.ohp),
        ("R&D", b.r_and_d),
        ("Warranty", b.warranty),
        ("SG&A", b.sg_and_a),
        ("Total Cost", b.total_cost),
    ], columns=["Bucket", "Value"])
    summary_df["% of Total"] = summary_df["Value"].apply(lambda value: f"{value / b.total_cost * 100:.1f}%" if b.total_cost else "0.0%")
    summary_display = summary_df.copy()
    summary_display["Value"] = summary_display["Value"].apply(money)

    process_df = pd.DataFrame([row.__dict__ for row in estimate.process_costs])
    process_display = process_df.copy()
    for col in ["batch_setup_cost", "va_machine_cost", "labor_cost", "total_cost"]:
        if col in process_display:
            process_display[col] = process_display[col].apply(money)

    nre_df = pd.DataFrame(estimate.selected_nre)
    if not nre_df.empty:
        nre_display = nre_df.copy()
        for col in ["unit_price", "extended_price"]:
            nre_display[col] = nre_display[col].apply(money)
    else:
        nre_display = nre_df

    consumables_df = pd.DataFrame([
        ("RTV", c.rtv_cost),
        ("Top solder paste", c.top_solder_paste_cost),
        ("Bottom solder paste", c.bottom_solder_paste_cost),
        ("Flux", c.flux_cost),
        ("Total consumables", c.total),
    ], columns=["Consumable", "Cost / board"])
    consumables_df["Cost / board"] = consumables_df["Cost / board"].apply(money)

    tabs = st.tabs(["Summary", "Process", "NRE", "Consumables", "Notes"])
    with tabs[0]:
        st.dataframe(summary_display, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(process_display, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(nre_display, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(consumables_df, use_container_width=True, hide_index=True)
    with tabs[4]:
        for note in estimate.notes:
            st.caption(f"• {note}")
        st.json(estimate.percentages)

    export_df = pd.concat([
        pd.DataFrame({"section": "summary", **summary_df.to_dict(orient="list")}),
        pd.DataFrame({"section": "process", "Bucket": process_df.get("stage", pd.Series(dtype=str)), "Value": process_df.get("total_cost", pd.Series(dtype=float)), "% of Total": process_df.get("side", pd.Series(dtype=str))}),
    ], ignore_index=True)
    csv_buffer = io.StringIO()
    export_df.to_csv(csv_buffer, index=False)
    st.download_button("Download PCBA Costing (.csv)", csv_buffer.getvalue(), file_name=f"{estimate.inputs.part_id}_pcba_should_cost.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#829084; margin-top:28px; border-top:1px solid #d6ddcf; padding-top:10px;">
  PCBA Should-Cost | Process mapping + cycle time + NRE + consumables + RM/conversion summary.
</div>
""",
    unsafe_allow_html=True,
)
