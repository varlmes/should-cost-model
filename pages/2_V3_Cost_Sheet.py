import io

import pandas as pd
import streamlit as st

from engine.v3_estimator import (
    CostSheetInput,
    LogisticsInput,
    MATERIALS,
    OVERHEAD_PROFILES,
    PROCESS_TEMPLATES,
    MaterialInput,
    ToolingNreInput,
    calculate_should_cost,
    templates_to_steps,
)

st.set_page_config(page_title="V3 Cost Sheet", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  .v3-hero { background: linear-gradient(130deg, #10251f 0%, #173c35 48%, #c6782f 100%); color: #fff8ec; padding: 26px 30px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .v3-kicker { letter-spacing: .16em; text-transform: uppercase; color: #ffd48a; font-size: .72rem; }
  .v3-price { font-size: 3rem; line-height: 1; font-weight: 700; margin: 10px 0 6px; }
  .v3-band { color: #f5ddae; }
  .rule { border: none; border-top: 1px solid #d9d2c3; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float, currency: str = "INR") -> str:
    symbol = "₹" if currency == "INR" else f"{currency} "
    return f"{symbol}{value:,.2f}"


st.markdown("#### — Sourcing Operations Suite")
st.title("V3 Bottom-Up Cost Sheet")
st.caption("Build a cleansheet cost model from BOM, routing, overhead, logistics, sensitivity, and volume leverage.")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("v3_cost_sheet"):
    c1, c2, c3, c4 = st.columns(4)
    product_name = c1.text_input("Part Name", value="Connecting Rod")
    commodity_type = c2.selectbox("Commodity", list(PROCESS_TEMPLATES.keys()), index=0)
    annual_volume = c3.number_input("Annual Volume", min_value=1, max_value=1000000, value=5000, step=500)
    quoted_price = c4.number_input("Quoted Price (₹/unit)", min_value=0.0, value=950.0, step=25.0)

    st.subheader("01 — Raw Material")
    material_key = st.selectbox("Material Grade", list(MATERIALS.keys()), index=0)
    material = MATERIALS[material_key]
    m1, m2, m3, m4 = st.columns(4)
    finished_mass = m1.number_input("Finished Mass (kg)", min_value=0.01, value=1.9, step=0.1)
    utilization = m2.slider("Utilization", min_value=0.30, max_value=0.98, value=0.68, step=0.01)
    material_rate = m3.number_input("Material Rate (₹/kg)", min_value=0.0, value=float(material.rate_per_kg), step=5.0)
    scrap_recovery = m4.slider("Scrap Recovery", min_value=0.0, max_value=0.90, value=float(material.scrap_recovery_pct), step=0.01)

    st.subheader("02 — Process Routing")
    available_templates = [tpl.name for tpl in PROCESS_TEMPLATES[commodity_type]]
    default_templates = available_templates[: min(7, len(available_templates))]
    selected_templates = st.multiselect("Apply Process Templates", available_templates, default=default_templates)
    batch_size = st.number_input("Batch Size", min_value=1, max_value=100000, value=100, step=25)
    learning_curve = st.slider("Learning Curve Factor", min_value=0.70, max_value=1.00, value=1.00, step=0.01, help="0.90 means 10% reduction in conversion and labor.")

    st.subheader("03 — Tooling, Overhead, Logistics")
    o1, o2, o3 = st.columns(3)
    tooling_cost = o1.number_input("Tooling / NRE Cost (₹)", min_value=0.0, value=75000.0, step=5000.0)
    tooling_life = o2.number_input("Tooling Life (units)", min_value=1, max_value=10000000, value=5000, step=500)
    overhead_name = o3.selectbox("Overhead Profile", list(OVERHEAD_PROFILES.keys()), index=0)
    overhead = OVERHEAD_PROFILES[overhead_name]

    l1, l2, l3 = st.columns(3)
    packaging = l1.number_input("Packaging / unit", min_value=0.0, value=float(overhead.packaging_per_unit), step=10.0)
    freight = l2.number_input("Freight / unit", min_value=0.0, value=float(overhead.freight_per_unit), step=10.0)
    other_logistics = l3.number_input("Other / outsourced / unit", min_value=0.0, value=float(overhead.other_logistics_per_unit), step=10.0)

    submitted = st.form_submit_button("Calculate V3 Cost Sheet", type="primary")

if submitted:
    try:
        steps = templates_to_steps(commodity_type, selected_templates)
        inputs = CostSheetInput(
            product_name=product_name,
            currency="INR",
            current_quoted_price=float(quoted_price),
            annual_volume=int(annual_volume),
            batch_size=int(batch_size),
            materials=[MaterialInput(
                name=material.material_type,
                grade=material.grade,
                finished_mass_kg=float(finished_mass),
                utilization_rate=float(utilization),
                price_per_kg=float(material_rate),
                scrap_recovery_pct=float(scrap_recovery),
            )],
            process_steps=steps,
            tooling_nre=[ToolingNreInput("Program tooling / NRE", float(tooling_cost), int(tooling_life))] if tooling_cost > 0 else [],
            learning_curve_factor=float(learning_curve),
            overhead=overhead,
            logistics=LogisticsInput(float(packaging), float(freight), float(other_logistics), overhead.name),
        )
        st.session_state["v3_result"] = calculate_should_cost(inputs)
    except Exception as exc:
        st.error(f"V3 calculation failed: {exc}")

result = st.session_state.get("v3_result")
if result:
    s = result.summary
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("04 — Results")
    gap_label = "above" if s.gap >= 0 else "below"
    st.markdown(
        f"""
<div class="v3-hero">
  <div class="v3-kicker">Bottom-Up Should-Cost — {result.product}</div>
  <div class="v3-price">{money(s.should_cost, result.currency)}</div>
  <div class="v3-band">Quoted price: {money(s.current_price, result.currency)} | Gap: {money(abs(s.gap), result.currency)} {gap_label} should-cost ({s.gap_pct:.1f}%)</div>
  <div class="v3-band">Annual opportunity: {money(s.annual_opportunity, result.currency)}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Material Net", money(s.total_material_net, result.currency))
    k2.metric("Conversion + Labor", money(s.total_conversion + s.total_labor, result.currency))
    k3.metric("Overhead + SGA", money(s.total_overhead + s.total_sga, result.currency))
    k4.metric("Profit + Logistics", money(s.total_profit + s.total_logistics, result.currency))

    summary_df = pd.DataFrame([
        ("Material gross", s.total_material_gross),
        ("Scrap credit", s.total_scrap_credit),
        ("Material net", s.total_material_net),
        ("Conversion", s.total_conversion),
        ("Labor", s.total_labor),
        ("Tooling / NRE", s.total_tooling_nre),
        ("Overhead", s.total_overhead),
        ("SGA", s.total_sga),
        ("Profit", s.total_profit),
        ("Taxes / duties", s.total_taxes),
        ("Logistics", s.total_logistics),
        ("Should-cost", s.should_cost),
    ], columns=["Bucket", "Value"])
    summary_df["% of Should-Cost"] = summary_df["Value"].apply(lambda value: f"{value / s.should_cost * 100:.1f}%" if s.should_cost else "0.0%")
    summary_display = summary_df.copy()
    summary_display["Value"] = summary_display["Value"].apply(lambda value: money(value, result.currency))

    line_df = pd.DataFrame([item.__dict__ for item in result.line_items])
    if not line_df.empty:
        line_df["value"] = line_df["value"].apply(lambda value: money(value, result.currency))

    sens_df = pd.DataFrame([item.__dict__ for item in result.sensitivity]).sort_values("impact", key=lambda col: col.abs(), ascending=False)
    sens_display = sens_df.copy()
    for col in ["new_should_cost", "impact"]:
        sens_display[col] = sens_display[col].apply(lambda value: money(value, result.currency))
    sens_display["impact_pct"] = sens_display["impact_pct"].apply(lambda value: f"{value:+.1f}%")

    volume_df = pd.DataFrame([item.__dict__ for item in result.volume_analysis])
    volume_display = volume_df.copy()
    for col in ["should_cost_per_unit", "delta_vs_base"]:
        volume_display[col] = volume_display[col].apply(lambda value: money(value, result.currency))
    volume_display["delta_pct"] = volume_display["delta_pct"].apply(lambda value: f"{value:+.1f}%")

    tabs = st.tabs(["Summary", "Line Items", "Sensitivity", "Volume", "Recommendations"])
    with tabs[0]:
        st.dataframe(summary_display, width="stretch", hide_index=True)
        if result.confidence_warning:
            st.warning(result.confidence_warning)
    with tabs[1]:
        st.dataframe(line_df, width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(sens_display, width="stretch", hide_index=True)
    with tabs[3]:
        st.dataframe(volume_display, width="stretch", hide_index=True)
    with tabs[4]:
        if result.recommendations:
            for rec in result.recommendations:
                st.markdown(f"**{rec.severity.title()} — {rec.title}**")
                st.caption(f"{rec.description} Potential savings: {rec.potential_savings_pct:.1f}%")
        else:
            st.success("No major cost-risk rules triggered for this scenario.")

    csv_buffer = io.StringIO()
    export = pd.concat(
        [
            pd.DataFrame({"section": "summary", **summary_df.to_dict(orient="list")}),
            pd.DataFrame({"section": "line_item", "Bucket": line_df.get("category", pd.Series(dtype=str)), "Value": [item.value for item in result.line_items], "% of Should-Cost": line_df.get("item", pd.Series(dtype=str))}),
        ],
        ignore_index=True,
    )
    export.to_csv(csv_buffer, index=False)
    st.download_button("Download V3 Cost Sheet (.csv)", csv_buffer.getvalue(), file_name=f"{result.product.replace(' ', '_')}_v3_cost_sheet.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#918675; margin-top:28px; border-top:1px solid #d8d0bf; padding-top:10px;">
  V3 Cost Sheet | BOM + routing + overhead + sensitivity + volume analysis | Deterministic Python estimator.
</div>
""",
    unsafe_allow_html=True,
)
