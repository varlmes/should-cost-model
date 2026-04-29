import io

import pandas as pd
import streamlit as st

from engine.supply_chain_optimizer import (
    BASE_DEMAND,
    CAPACITY_K_UNITS,
    FIXED_COST_K_PER_MONTH,
    FREIGHT_COST_PER_CONTAINER,
    LOCATIONS,
    VARIABLE_COST,
    NetworkInputs,
    lane_unit_cost,
    optimize_network,
)

st.set_page_config(page_title="Supply Chain Optimization", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
  .sc-hero { background: radial-gradient(circle at 15% 12%, rgba(88,166,255,.8) 0, transparent 24%), linear-gradient(135deg, #07111f 0%, #123353 52%, #2e4f3a 100%); color: #eef7ff; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .sc-kicker { letter-spacing: .18em; text-transform: uppercase; color: #a8d5ff; font-size: .72rem; }
  .sc-price { font-size: 3rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .sc-band { color: #d9ecff; }
  .rule { border: none; border-top: 1px solid #d1d9df; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value / 1_000_000:,.2f}M"


def units(value: float) -> str:
    return f"{value / 1_000_000:,.2f}M"


st.markdown("#### — Sourcing Operations Suite")
st.title("Supply Chain Network Optimizer")
st.caption("Choose plant locations and allocate production to minimize fixed, manufacturing, and freight cost.")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("supply_chain_optimizer"):
    c1, c2, c3, c4 = st.columns(4)
    demand_multiplier = c1.slider("Demand Multiplier", min_value=0.50, max_value=1.50, value=1.00, step=0.05)
    freight_multiplier = c2.slider("Freight Cost Multiplier", min_value=0.25, max_value=3.00, value=1.00, step=0.05)
    fixed_multiplier = c3.slider("Fixed Cost Multiplier", min_value=0.50, max_value=1.50, value=1.00, step=0.05)
    variable_multiplier = c4.slider("Variable Cost Multiplier", min_value=0.50, max_value=1.50, value=1.00, step=0.05)
    allow_stacked = st.toggle("Allow low + high capacity at same location", value=True)
    submitted = st.form_submit_button("Optimize Network", type="primary")

if submitted:
    try:
        inputs = NetworkInputs(
            demand_multiplier=float(demand_multiplier),
            freight_multiplier=float(freight_multiplier),
            fixed_cost_multiplier=float(fixed_multiplier),
            variable_cost_multiplier=float(variable_multiplier),
            allow_stacked_capacity=bool(allow_stacked),
        )
        st.session_state["supply_chain_result"] = optimize_network(inputs)
    except Exception as exc:
        st.error(f"Supply-chain optimization failed: {exc}")

result = st.session_state.get("supply_chain_result")
if result:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("Optimization Results")
    if result.status != "Optimal":
        st.error("No feasible network found for this scenario.")
    else:
        st.markdown(
            f"""
<div class="sc-hero">
  <div class="sc-kicker">Optimal Monthly Network Cost</div>
  <div class="sc-price">{money(result.total_cost)}</div>
  <div class="sc-band">Fixed: {money(result.fixed_cost)} | Variable + freight: {money(result.variable_cost)}</div>
  <div class="sc-band">Demand served: {units(sum(result.demand.values()))} units/month | Open plants: {len(result.plant_decisions)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Cost", money(result.total_cost))
        k2.metric("Fixed Cost", money(result.fixed_cost))
        k3.metric("Flow Cost", money(result.variable_cost))
        k4.metric("Open Plants", str(len(result.plant_decisions)))

        plant_df = pd.DataFrame([row.__dict__ for row in result.plant_decisions])
        plant_display = plant_df.copy()
        if not plant_display.empty:
            plant_display["capacity_units"] = plant_display["capacity_units"].apply(units)
            plant_display["fixed_cost"] = plant_display["fixed_cost"].apply(money)
            plant_display["utilization"] = plant_display["utilization"].apply(lambda value: f"{value:.1%}")

        flow_df = pd.DataFrame([row.__dict__ for row in result.flows])
        flow_display = flow_df.copy()
        if not flow_display.empty:
            flow_display["units"] = flow_display["units"].apply(units)
            flow_display["unit_cost"] = flow_display["unit_cost"].apply(lambda value: f"${value:,.2f}/unit")
            flow_display["total_cost"] = flow_display["total_cost"].apply(money)

        demand_df = pd.DataFrame([{"market": loc, "demand": demand} for loc, demand in result.demand.items()])
        demand_display = demand_df.copy()
        demand_display["demand"] = demand_display["demand"].apply(units)

        lane_cost_df = pd.DataFrame(
            [[lane_unit_cost(src, dst, result.inputs) for dst in LOCATIONS] for src in LOCATIONS],
            index=LOCATIONS,
            columns=LOCATIONS,
        )

        baseline_df = pd.DataFrame({
            "Location": LOCATIONS,
            "Demand Units": [BASE_DEMAND[loc] for loc in LOCATIONS],
            "Variable Cost / Unit": [VARIABLE_COST[loc] for loc in LOCATIONS],
            "Low Capacity": [CAPACITY_K_UNITS[loc]["Low"] * 1000 for loc in LOCATIONS],
            "High Capacity": [CAPACITY_K_UNITS[loc]["High"] * 1000 for loc in LOCATIONS],
            "Low Fixed Cost": [FIXED_COST_K_PER_MONTH[loc]["Low"] * 1000 for loc in LOCATIONS],
            "High Fixed Cost": [FIXED_COST_K_PER_MONTH[loc]["High"] * 1000 for loc in LOCATIONS],
        })

        tabs = st.tabs(["Plants", "Production Flows", "Demand", "Lane Costs", "Inputs / Notes"])
        with tabs[0]:
            st.dataframe(plant_display, use_container_width=True, hide_index=True)
        with tabs[1]:
            st.dataframe(flow_display, use_container_width=True, hide_index=True)
        with tabs[2]:
            st.dataframe(demand_display, use_container_width=True, hide_index=True)
        with tabs[3]:
            st.caption("Unit cost equals production variable cost plus freight cost per container / 1000.")
            st.dataframe(lane_cost_df.style.format("${:,.2f}"), use_container_width=True)
        with tabs[4]:
            st.dataframe(baseline_df, use_container_width=True, hide_index=True)
            for note in result.notes:
                st.caption(f"• {note}")

        csv_buffer = io.StringIO()
        pd.concat(
            [
                pd.DataFrame({"section": "plants", **plant_df.to_dict(orient="list")}),
                pd.DataFrame({"section": "flows", "location": flow_df.get("source", pd.Series(dtype=str)), "low_open": flow_df.get("destination", pd.Series(dtype=str)), "high_open": "", "capacity_units": flow_df.get("units", pd.Series(dtype=float)), "fixed_cost": flow_df.get("total_cost", pd.Series(dtype=float)), "utilization": ""}),
            ],
            ignore_index=True,
        ).to_csv(csv_buffer, index=False)
        st.download_button("Download Network Plan (.csv)", csv_buffer.getvalue(), file_name="supply_chain_network_plan.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#7f8b94; margin-top:28px; border-top:1px solid #d1d9df; padding-top:10px;">
  Supply Chain Network Optimizer | Plant location + capacity + production allocation | Deterministic Python solver.
</div>
""",
    unsafe_allow_html=True,
)
