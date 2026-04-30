import io

import pandas as pd
import streamlit as st

from engine.fuel_estimator import FuelInputs, estimate_fuel_cost

st.set_page_config(page_title="Fuel Cost Calculator", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
  .fuel-hero { background: radial-gradient(circle at 18% 20%, rgba(255,193,7,.95) 0, transparent 22%), linear-gradient(135deg, #101113 0%, #242a2f 55%, #5a3b12 100%); color: #fff9e8; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .fuel-kicker { letter-spacing: .18em; text-transform: uppercase; color: #ffd66b; font-size: .72rem; }
  .fuel-price { font-size: 3.2rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .fuel-band { color: #ffe8a8; }
  .rule { border: none; border-top: 1px solid #d9d0bd; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float, currency: str) -> str:
    return f"{currency}{value:,.2f}"


st.markdown("#### — Sourcing Operations Suite")
st.title("Fuel Cost Calculator")
st.caption("Trip fuel cost from distance, fuel efficiency, and fuel price.")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("fuel_cost"):
    c1, c2, c3, c4 = st.columns(4)
    distance = c1.number_input("Distance", min_value=0.0, value=250.0, step=10.0)
    distance_unit = c2.selectbox("Distance Unit", ["km", "mi"], index=0)
    efficiency_unit = c3.selectbox("Efficiency Unit", ["L/100 km", "mpg", "km/L"], index=0)
    currency = c4.text_input("Currency Symbol", value="$", max_chars=4)

    e1, e2, e3, e4 = st.columns(4)
    default_efficiency = 7.5 if efficiency_unit == "L/100 km" else 32.0 if efficiency_unit == "mpg" else 13.0
    fuel_efficiency = e1.number_input("Fuel Efficiency", min_value=0.0, value=default_efficiency, step=0.1)
    fuel_price = e2.number_input("Fuel Price", min_value=0.0, value=1.45, step=0.05, help="Per liter for L/100 km and km/L. Per gallon is converted through mpg by first calculating liters.")
    passengers = e3.number_input("Passengers / Split", min_value=1, max_value=99, value=1, step=1)
    extra_costs = e4.number_input("Extra Costs", min_value=0.0, value=0.0, step=1.0, help="Optional tolls, parking, or fees added to total trip cost.")

    round_trip = st.toggle("Round trip", value=False)
    submitted = st.form_submit_button("Calculate Fuel Cost", type="primary")

if submitted:
    try:
        inputs = FuelInputs(
            distance=float(distance),
            fuel_efficiency=float(fuel_efficiency),
            fuel_price=float(fuel_price),
            distance_unit=distance_unit,
            efficiency_unit=efficiency_unit,
            round_trip=bool(round_trip),
            passengers=int(passengers),
            extra_costs=float(extra_costs),
        )
        st.session_state["fuel_estimate"] = estimate_fuel_cost(inputs)
        st.session_state["fuel_currency"] = currency or "$"
    except Exception as exc:
        st.error(f"Fuel cost calculation failed: {exc}")

estimate = st.session_state.get("fuel_estimate")
currency = st.session_state.get("fuel_currency", "$")
if estimate:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("Results")
    st.markdown(
        f"""
<div class="fuel-hero">
  <div class="fuel-kicker">Fuel Cost Estimate</div>
  <div class="fuel-price">{money(estimate.total_cost, currency)}</div>
  <div class="fuel-band">Fuel only: {money(estimate.fuel_cost, currency)} | Fuel used: {estimate.fuel_liters:,.2f} L | Trip distance: {estimate.trip_distance_km:,.1f} km</div>
  <div class="fuel-band">Per passenger: {money(estimate.cost_per_passenger, currency)} | Per km: {money(estimate.cost_per_km, currency)} | Per mile: {money(estimate.cost_per_mile, currency)}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("Fuel Used", f"{estimate.fuel_liters:,.2f} L")
    cols[1].metric("Fuel Cost", money(estimate.fuel_cost, currency))
    cols[2].metric("Total Cost", money(estimate.total_cost, currency))
    cols[3].metric("Split Cost", money(estimate.cost_per_passenger, currency))

    detail_df = pd.DataFrame([
        ("One-way distance", f"{estimate.one_way_distance_km:,.2f} km"),
        ("Trip distance", f"{estimate.trip_distance_km:,.2f} km"),
        ("Efficiency", f"{estimate.inputs.fuel_efficiency:g} {estimate.inputs.efficiency_unit}"),
        ("Fuel price", money(estimate.inputs.fuel_price, currency)),
        ("Extra costs", money(estimate.inputs.extra_costs, currency)),
        ("Passengers", estimate.inputs.passengers),
    ], columns=["Metric", "Value"])
    st.dataframe(detail_df, width="stretch", hide_index=True)

    csv_buffer = io.StringIO()
    detail_df.to_csv(csv_buffer, index=False)
    st.download_button("Download Fuel Cost (.csv)", csv_buffer.getvalue(), file_name="fuel_cost_estimate.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#8c826f; margin-top:28px; border-top:1px solid #d9d0bd; padding-top:10px;">
  Fuel Cost Calculator | Distance x efficiency x fuel price | Optional round trip and split cost.
</div>
""",
    unsafe_allow_html=True,
)
