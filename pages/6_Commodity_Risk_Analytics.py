import io

import pandas as pd
import streamlit as st

from engine.commodity_analysis import (
    COMMODITY_PROFILES,
    CommodityInputs,
    CommodityPosition,
    analyze_commodities,
    default_positions,
)

st.set_page_config(page_title="Commodity Risk Analytics", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
  .cmdty-hero { background: radial-gradient(circle at 16% 18%, rgba(79,176,139,.85) 0, transparent 24%), linear-gradient(135deg, #101416 0%, #243336 52%, #5a4b27 100%); color: #f3fff8; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .cmdty-kicker { letter-spacing: .18em; text-transform: uppercase; color: #b8f3d6; font-size: .72rem; }
  .cmdty-price { font-size: 3rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .cmdty-band { color: #dbf7e9; }
  .rule { border: none; border-top: 1px solid #d7d9d2; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


st.markdown("#### — Sourcing Operations Suite")
st.title("Commodity Risk Analytics")
st.caption("Procurement exposure, commodity price scenarios, and downside spend-at-risk.")
st.markdown(
    "Reference project: [FinancialStrategy/CommoditiesAnalysis](https://github.com/FinancialStrategy/CommoditiesAnalysis)"
)
st.markdown('<hr class="rule">', unsafe_allow_html=True)

default_df = pd.DataFrame([position.__dict__ for position in default_positions()])
default_df["include"] = default_df["monthly_volume"] > 0
default_df = default_df[["include", "name", "unit", "current_price", "monthly_volume", "hedge_coverage"]]

with st.form("commodity_risk"):
    c1, c2, c3 = st.columns(3)
    horizon_days = c1.slider("Risk Horizon", min_value=21, max_value=252, value=63, step=21, help="Trading days used for VaR/CVaR and price scenarios.")
    confidence_level = c2.select_slider("Confidence Level", options=[0.90, 0.95, 0.975, 0.99], value=0.95, format_func=lambda value: f"{value:.1%}")
    shock_pct = c3.slider("Stress Shock", min_value=0.00, max_value=0.50, value=0.10, step=0.01, format="%0.2f", help="Applied to unhedged monthly spend. Use 0.10 for a 10% shock.")

    st.markdown("**Commodity Basket**")
    edited_df = st.data_editor(
        default_df,
        width="stretch",
        hide_index=True,
        column_config={
            "include": st.column_config.CheckboxColumn("Use", default=False),
            "name": st.column_config.SelectboxColumn("Commodity", options=list(COMMODITY_PROFILES), required=True),
            "unit": st.column_config.TextColumn("Unit"),
            "current_price": st.column_config.NumberColumn("Current Price", min_value=0.0, step=10.0, format="$%.4f"),
            "monthly_volume": st.column_config.NumberColumn("Monthly Volume", min_value=0.0, step=1.0),
            "hedge_coverage": st.column_config.NumberColumn("Hedge Coverage (0-1)", min_value=0.0, max_value=1.0, step=0.05, format="%.2f"),
        },
    )
    submitted = st.form_submit_button("Analyze Commodity Risk", type="primary")

if submitted:
    try:
        positions = []
        for row in edited_df.to_dict(orient="records"):
            if not row.get("include"):
                continue
            profile = COMMODITY_PROFILES.get(row["name"])
            positions.append(
                CommodityPosition(
                    name=str(row["name"]),
                    unit=str(row.get("unit") or (profile.unit if profile else "")),
                    current_price=float(row["current_price"]),
                    monthly_volume=float(row["monthly_volume"]),
                    hedge_coverage=float(row["hedge_coverage"]),
                )
            )
        st.session_state["commodity_analysis"] = analyze_commodities(
            CommodityInputs(
                positions=positions,
                horizon_days=int(horizon_days),
                confidence_level=float(confidence_level),
                shock_pct=float(shock_pct),
            )
        )
    except Exception as exc:
        st.error(f"Commodity analysis failed: {exc}")

analysis = st.session_state.get("commodity_analysis")
if analysis:
    st.markdown('<hr class="rule">', unsafe_allow_html=True)
    st.subheader("Risk Summary")
    st.markdown(
        f"""
<div class="cmdty-hero">
  <div class="cmdty-kicker">Portfolio CVaR Spend Exposure</div>
  <div class="cmdty-price">{money(analysis.portfolio_cvar)}</div>
  <div class="cmdty-band">Monthly spend: {money(analysis.total_monthly_spend)} | Unhedged spend: {money(analysis.unhedged_monthly_spend)}</div>
  <div class="cmdty-band">VaR: {money(analysis.portfolio_var)} | Stress impact: {money(analysis.stress_cost_impact)} | Horizon: {analysis.inputs.horizon_days} trading days</div>
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("Monthly Spend", money(analysis.total_monthly_spend))
    cols[1].metric("Unhedged Spend", money(analysis.unhedged_monthly_spend))
    cols[2].metric("VaR", money(analysis.portfolio_var))
    cols[3].metric("CVaR", money(analysis.portfolio_cvar))

    metrics_df = pd.DataFrame([row.__dict__ for row in analysis.metrics])
    display_df = metrics_df.copy()
    currency_cols = ["current_price", "monthly_spend", "unhedged_spend", "stress_cost_impact", "low_price", "base_price", "high_price"]
    for col in currency_cols:
        display_df[col] = display_df[col].apply(lambda value: f"${value:,.2f}")
    for col in ["annualized_volatility", "trailing_return", "var_price_move", "cvar_price_move"]:
        display_df[col] = display_df[col].apply(pct)

    tabs = st.tabs(["Exposure", "Price Scenarios", "History", "Inputs / Notes"])
    with tabs[0]:
        st.dataframe(
            display_df[
                [
                    "name",
                    "unit",
                    "monthly_volume",
                    "monthly_spend",
                    "unhedged_spend",
                    "annualized_volatility",
                    "var_price_move",
                    "cvar_price_move",
                    "stress_cost_impact",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
    with tabs[1]:
        st.dataframe(
            display_df[["name", "current_price", "low_price", "base_price", "high_price", "trailing_return"]],
            width="stretch",
            hide_index=True,
        )
    with tabs[2]:
        history_df = pd.DataFrame(analysis.price_history)
        history_df.index.name = "Scenario Day"
        st.line_chart(history_df, width="stretch")
        st.caption("Scenario paths are normalized to the current price entered above.")
    with tabs[3]:
        input_df = pd.DataFrame([row.__dict__ for row in analysis.inputs.positions])
        st.dataframe(input_df, width="stretch", hide_index=True)
        for note in analysis.notes:
            st.caption(f"- {note}")

    csv_buffer = io.StringIO()
    metrics_df.to_csv(csv_buffer, index=False)
    st.download_button("Download Commodity Risk (.csv)", csv_buffer.getvalue(), file_name="commodity_risk_analytics.csv", mime="text/csv")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#7f897b; margin-top:28px; border-top:1px solid #d7d9d2; padding-top:10px;">
  Commodity Risk Analytics | Procurement exposure + VaR/CVaR + price scenarios | Inspired by FinancialStrategy/CommoditiesAnalysis.
</div>
""",
    unsafe_allow_html=True,
)
