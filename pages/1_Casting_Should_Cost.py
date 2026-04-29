import io

import pandas as pd
import streamlit as st

from engine.casting_estimator import (
    CastingInputs,
    COMPLEXITY_LABELS,
    MATERIALS,
    NDT_METHODS,
    PROCESS_MULTIPLIERS,
    estimate_casting_cost,
    suggest_complexity,
)

st.set_page_config(
    page_title="Casting Should-Cost",
    page_icon="⚙",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Alegreya+Sans:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Alegreya Sans', sans-serif; }
  .casting-hero {
    background: linear-gradient(135deg, #1f2a24 0%, #364336 52%, #8a5a2b 100%);
    color: #f8f0df;
    border: 1px solid rgba(248,240,223,.18);
    padding: 26px 30px;
    margin-bottom: 18px;
  }
  .casting-kicker {
    letter-spacing: .16em;
    text-transform: uppercase;
    font-size: .72rem;
    color: #e7c27a;
  }
  .casting-price {
    font-size: 3rem;
    line-height: 1;
    font-weight: 800;
    margin: 10px 0 4px;
  }
  .casting-band { color: #f3dfb3; font-size: .95rem; }
  .rule { border: none; border-top: 1px solid #d8d0bf; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.0f}" if abs(value) >= 100 else f"${value:,.2f}"


st.markdown("#### — Sourcing Operations Suite")
st.title("Casting Should-Cost Estimator")
st.caption("Deterministic casting cost estimation for early sourcing and supplier quote checks.")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

left, right = st.columns(2)

with left:
    st.subheader("01 — Order")
    part_id = st.text_input("Part ID", value="CAST-0001")
    material_key = st.selectbox("Material / Grade", list(MATERIALS.keys()), index=0)
    process = st.selectbox("Casting Process", list(PROCESS_MULTIPLIERS.keys()), index=0)
    quantity = st.number_input("Quantity Ordered", min_value=1, max_value=250000, value=250, step=25)
    ndt_method = st.selectbox("NDT Method", list(NDT_METHODS.keys()), index=1)
    margin_rate = st.slider("Supplier Margin", min_value=0.0, max_value=0.40, value=0.16, step=0.01)

with right:
    st.subheader("02 — Geometry")
    st.caption("Use MATLAB-style metric inputs. The estimator converts mm/mm²/mm³ to inches internally, matching the reference model.")
    casting_volume = st.number_input("Casting Volume (mm³)", min_value=1.0, value=250000.0, step=10000.0, format="%.1f")
    core_volume = st.number_input("Core Volume (mm³)", min_value=0.0, value=0.0, step=5000.0, format="%.1f")
    surface_area = st.number_input("Casting Surface Area (mm²)", min_value=1.0, value=42000.0, step=1000.0, format="%.1f")
    c1, c2, c3 = st.columns(3)
    box_x = c1.number_input("Box X (mm)", min_value=1.0, value=160.0, step=5.0)
    box_y = c2.number_input("Box Y (mm)", min_value=1.0, value=90.0, step=5.0)
    box_z = c3.number_input("Box Z (mm)", min_value=1.0, value=55.0, step=5.0)
    feeder_count = st.number_input("Feeder Count", min_value=0, max_value=40, value=1, step=1)

box_dimensions = (box_x, box_y, box_z)
suggested_complexity = suggest_complexity(core_volume, casting_volume, feeder_count, surface_area, box_dimensions)

st.markdown('<hr class="rule">', unsafe_allow_html=True)
st.subheader("03 — Complexity")
use_suggested = st.toggle("Use suggested complexity", value=True)
if use_suggested:
    complexity = suggested_complexity
    st.info(f"Suggested complexity: {COMPLEXITY_LABELS[complexity]}")
else:
    complexity = st.select_slider(
        "Manual Shape Complexity",
        options=list(COMPLEXITY_LABELS.keys()),
        value=suggested_complexity,
        format_func=lambda value: COMPLEXITY_LABELS[value],
    )

run = st.button("Run Casting Should-Cost", type="primary")

if run:
    try:
        inputs = CastingInputs(
            part_id=part_id,
            material_key=material_key,
            process=process,
            quantity_ordered=int(quantity),
            casting_volume_mm3=float(casting_volume),
            core_volume_mm3=float(core_volume),
            casting_surface_area_mm2=float(surface_area),
            box_dimensions_mm=tuple(float(v) for v in box_dimensions),
            shape_complexity=int(complexity),
            feeder_count=int(feeder_count),
            ndt_method=ndt_method,
            margin_rate=float(margin_rate),
        )
        estimate = estimate_casting_cost(inputs)
        st.session_state["casting_estimate"] = estimate
    except Exception as exc:
        st.error(f"Casting estimate failed: {exc}")

estimate = st.session_state.get("casting_estimate")
if estimate:
    b = estimate.breakdown
    m = estimate.metrics

    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("04 — Results")
    st.markdown(
        f"""
<div class="casting-hero">
  <div class="casting-kicker">Casting Should-Cost — {estimate.inputs.part_id}</div>
  <div class="casting-price">{money(b.grand_total_per_part)}</div>
  <div class="casting-band">Low: {money(estimate.low_per_part)} | Mid: {money(b.grand_total_per_part)} | High: {money(estimate.high_per_part)} per part</div>
  <div class="casting-band">Order total: {money(b.grand_total_order)} | Range: {money(estimate.low_order)} - {money(estimate.high_order)}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Casting Weight", f"{m.casting_weight_lb:,.2f} lb")
    metric_cols[1].metric("Yield Weight", f"{m.yield_weight_lb:,.2f} lb")
    metric_cols[2].metric("Envelope Volume", f"{m.envelope_volume_in3:,.2f} in³")
    metric_cols[3].metric("Complexity", str(estimate.inputs.shape_complexity))

    breakdown_df = pd.DataFrame(
        [
            ("Material", b.material_per_part),
            ("Processing", b.processing_per_part),
            ("Tooling", b.tooling_per_part),
            ("NDT", b.ndt_per_part),
            ("Straightening Fixture", b.straightening_per_part),
            ("Check Fixture", b.check_fixture_per_part),
            ("Subtotal", b.subtotal_per_part),
            ("Supplier Margin", b.margin_per_part),
            ("Grand Total", b.grand_total_per_part),
        ],
        columns=["Cost Bucket", "Per Part"],
    )
    breakdown_df["% of Price"] = breakdown_df["Per Part"].apply(lambda value: f"{value / b.grand_total_per_part * 100:.1f}%")
    breakdown_df["Per Part"] = breakdown_df["Per Part"].apply(money)

    geometry_df = pd.DataFrame(
        [
            ("Material", f"{estimate.material.name} {estimate.material.grade}"),
            ("Casting class", estimate.material.casting_class),
            ("Box dimensions", " x ".join(f"{v:.2f}" for v in m.box_dimensions_in) + " in"),
            ("Box volume", f"{m.box_volume_in3:,.2f} in³"),
            ("Casting volume", f"{m.casting_volume_in3:,.2f} in³"),
            ("Core volume", f"{m.core_volume_in3:,.2f} in³"),
            ("Surface area", f"{m.surface_area_in2:,.2f} in²"),
            ("Envelope / box ratio", f"{m.volume_ratio:.2%}"),
            ("Surface density", f"{m.surface_area_density:.2f}"),
        ],
        columns=["Metric", "Value"],
    )

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("**Cost Breakdown — Per Part**")
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
    with c_right:
        st.markdown("**Converted Geometry / Assumptions**")
        st.dataframe(geometry_df, use_container_width=True, hide_index=True)

    st.markdown("**Model Notes**")
    for note in estimate.notes:
        st.caption(f"• {note}")

    csv_buffer = io.StringIO()
    export_df = pd.concat(
        [
            pd.DataFrame({"Section": ["Cost"] * len(breakdown_df), **breakdown_df.to_dict(orient="list")}),
            pd.DataFrame({"Section": ["Geometry"] * len(geometry_df), "Cost Bucket": geometry_df["Metric"], "Per Part": geometry_df["Value"], "% of Price": ""}),
        ],
        ignore_index=True,
    )
    export_df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download Casting Estimate (.csv)",
        data=csv_buffer.getvalue(),
        file_name=f"{estimate.inputs.part_id}_casting_should_cost.csv",
        mime="text/csv",
    )

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#918675; margin-top:28px; border-top:1px solid #d8d0bf; padding-top:10px;">
  Casting Should-Cost page | Deterministic Python estimator | Workbook-free and supplier-quote ready.
</div>
""",
    unsafe_allow_html=True,
)
