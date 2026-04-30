import io

import pandas as pd
import streamlit as st

from engine.metal_pricing import METAL_COLUMNS, MetalPricingInputs, analyze_metal_pricing, load_metal_prices

st.set_page_config(page_title="Metal Commodity Pricing", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
  .metal-hero { background: radial-gradient(circle at 16% 20%, rgba(190,204,214,.9) 0, transparent 22%), linear-gradient(135deg, #121417 0%, #34383c 54%, #50605a 100%); color: #f7fbff; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .metal-kicker { letter-spacing: .18em; text-transform: uppercase; color: #d9edf3; font-size: .72rem; }
  .metal-price { font-size: 3rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .metal-band { color: #edf7fa; }
  .rule { border: none; border-top: 1px solid #d5d9db; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


data = load_metal_prices()
min_date = data["Date"].min().date()
max_date = data["Date"].max().date()

st.markdown("#### — Sourcing Operations Suite")
st.title("Metal Commodity Pricing")
st.caption("Historical monthly metal pricing, trend diagnostics, simple forecast, and procurement shock impact.")
st.markdown("Reference project: [RichGude/Metal-Commodity-Pricing](https://github.com/RichGude/Metal-Commodity-Pricing)")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

with st.form("metal_pricing"):
    c1, c2, c3, c4 = st.columns(4)
    metal = c1.selectbox("Metal", METAL_COLUMNS, index=0)
    start_date = c2.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    end_date = c3.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    forecast_months = c4.slider("Forecast Months", min_value=1, max_value=24, value=6, step=1)

    p1, p2 = st.columns(2)
    monthly_volume = p1.number_input("Monthly Buy Volume", min_value=0.0, value=100.0, step=10.0, help="Uses the unit implied by the selected historical price series.")
    shock_pct = p2.slider("Price Shock", min_value=0.0, max_value=0.5, value=0.10, step=0.01, format="%0.2f", help="Use 0.10 for a 10% price shock.")
    submitted = st.form_submit_button("Analyze Metal Pricing", type="primary")

if submitted or "metal_pricing_summary" not in st.session_state:
    try:
        summary, window, forecast_df = analyze_metal_pricing(
            MetalPricingInputs(
                metal=metal,
                start_date=str(start_date),
                end_date=str(end_date),
                monthly_volume=float(monthly_volume),
                forecast_months=int(forecast_months),
                shock_pct=float(shock_pct),
            ),
            data=data,
        )
        st.session_state["metal_pricing_summary"] = summary
        st.session_state["metal_pricing_window"] = window
        st.session_state["metal_pricing_forecast"] = forecast_df
    except Exception as exc:
        st.error(f"Metal pricing analysis failed: {exc}")

summary = st.session_state.get("metal_pricing_summary")
window = st.session_state.get("metal_pricing_window")
forecast_df = st.session_state.get("metal_pricing_forecast")

if summary and window is not None and forecast_df is not None:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("Pricing Summary")
    st.markdown(
        f"""
<div class="metal-hero">
  <div class="metal-kicker">{summary.metal} Latest Historical Price</div>
  <div class="metal-price">{money(summary.latest_price)}</div>
  <div class="metal-band">Window: {summary.start_date} to {summary.end_date} | Observations: {summary.observations:,}</div>
  <div class="metal-band">Change: {money(summary.absolute_change)} ({pct(summary.percent_change)}) | Volatility: {pct(summary.annualized_volatility)} | Max drawdown: {pct(summary.max_drawdown)}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("Latest Price", money(summary.latest_price))
    cols[1].metric("Annualized Return", pct(summary.annualized_return))
    cols[2].metric("Monthly Spend", money(summary.monthly_spend))
    cols[3].metric("Shock Impact", money(summary.shock_cost_impact))

    chart_df = window.set_index("Date")[["Price", "Rolling 12M Avg"]]
    indexed_df = window.set_index("Date")[["Indexed Price"]]
    forecast_chart = forecast_df.set_index("Date")[["Forecast Price"]]

    tabs = st.tabs(["Price Trend", "Indexed Trend", "Forecast", "Data / Notes"])
    with tabs[0]:
        st.line_chart(chart_df, width="stretch")
    with tabs[1]:
        st.line_chart(indexed_df, width="stretch")
    with tabs[2]:
        st.line_chart(forecast_chart, width="stretch")
        st.dataframe(forecast_df, width="stretch", hide_index=True)
    with tabs[3]:
        display_df = window.copy()
        display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
        st.dataframe(display_df, width="stretch", hide_index=True)
        for note in summary.notes:
            st.caption(f"- {note}")

    csv_buffer = io.StringIO()
    window.to_csv(csv_buffer, index=False)
    st.download_button("Download Metal Pricing Window (.csv)", csv_buffer.getvalue(), file_name="metal_pricing_window.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#7d8588; margin-top:28px; border-top:1px solid #d5d9db; padding-top:10px;">
  Metal Commodity Pricing | Historical metal prices + trend diagnostics + lightweight forecast | Inspired by RichGude/Metal-Commodity-Pricing.
</div>
""",
    unsafe_allow_html=True,
)
