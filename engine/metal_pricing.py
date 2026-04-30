"""Historical metal commodity pricing analytics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


METAL_COLUMNS = ["Aluminum", "Copper", "Iron Ore", "Nickel", "Zinc"]
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "metal_price_data.json"


@dataclass(frozen=True)
class MetalPricingInputs:
    metal: str
    start_date: str
    end_date: str
    monthly_volume: float = 0.0
    forecast_months: int = 6
    shock_pct: float = 0.10


@dataclass(frozen=True)
class MetalPricingSummary:
    metal: str
    start_date: str
    end_date: str
    observations: int
    start_price: float
    latest_price: float
    absolute_change: float
    percent_change: float
    annualized_return: float
    annualized_volatility: float
    max_drawdown: float
    monthly_spend: float
    shock_cost_impact: float
    forecast_price: float
    notes: list[str]


def load_metal_prices(path: Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    df = pd.read_json(path)
    df["Date"] = pd.to_datetime(df["Date"])
    for col in METAL_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("Date").reset_index(drop=True)


def analyze_metal_pricing(inputs: MetalPricingInputs, data: pd.DataFrame | None = None) -> tuple[MetalPricingSummary, pd.DataFrame, pd.DataFrame]:
    if inputs.metal not in METAL_COLUMNS:
        raise ValueError(f"metal must be one of: {', '.join(METAL_COLUMNS)}")
    if inputs.monthly_volume < 0:
        raise ValueError("monthly_volume must be >= 0")
    if inputs.forecast_months < 1:
        raise ValueError("forecast_months must be >= 1")
    if inputs.shock_pct < 0:
        raise ValueError("shock_pct must be >= 0")

    df = load_metal_prices() if data is None else data.copy()
    start = pd.to_datetime(inputs.start_date)
    end = pd.to_datetime(inputs.end_date)
    window = df[(df["Date"] >= start) & (df["Date"] <= end)][["Date", inputs.metal]].dropna().copy()
    if len(window) < 3:
        raise ValueError("selected date range needs at least 3 observations")

    window = window.rename(columns={inputs.metal: "Price"})
    window["Monthly Return"] = window["Price"].pct_change()
    window["Indexed Price"] = window["Price"] / window["Price"].iloc[0] * 100
    window["Rolling 12M Avg"] = window["Price"].rolling(12, min_periods=1).mean()

    returns = window["Monthly Return"].dropna()
    start_price = float(window["Price"].iloc[0])
    latest_price = float(window["Price"].iloc[-1])
    years = max((window["Date"].iloc[-1] - window["Date"].iloc[0]).days / 365.25, 1 / 12)
    annualized_return = (latest_price / start_price) ** (1 / years) - 1 if start_price > 0 else 0.0
    annualized_volatility = float(returns.std(ddof=0) * (12 ** 0.5)) if not returns.empty else 0.0
    max_drawdown = _max_drawdown(window["Price"])
    monthly_spend = latest_price * inputs.monthly_volume
    shock_cost_impact = monthly_spend * inputs.shock_pct

    forecast_df = _simple_forecast(window, inputs.forecast_months)
    forecast_price = float(forecast_df["Forecast Price"].iloc[-1])

    summary = MetalPricingSummary(
        metal=inputs.metal,
        start_date=window["Date"].iloc[0].strftime("%Y-%m-%d"),
        end_date=window["Date"].iloc[-1].strftime("%Y-%m-%d"),
        observations=len(window),
        start_price=round(start_price, 4),
        latest_price=round(latest_price, 4),
        absolute_change=round(latest_price - start_price, 4),
        percent_change=round((latest_price / start_price) - 1, 4) if start_price else 0.0,
        annualized_return=round(annualized_return, 4),
        annualized_volatility=round(annualized_volatility, 4),
        max_drawdown=round(max_drawdown, 4),
        monthly_spend=round(monthly_spend, 2),
        shock_cost_impact=round(shock_cost_impact, 2),
        forecast_price=round(forecast_price, 4),
        notes=[
            "Source dataset is historical monthly metal pricing from the referenced project, covering 1990 through the dataset end date.",
            "Forecast uses a lightweight drift estimate from recent monthly returns, not a live market feed or TensorFlow model.",
            "Procurement impact is latest historical price x monthly volume x selected shock.",
        ],
    )
    return summary, window, forecast_df


def _simple_forecast(window: pd.DataFrame, months: int) -> pd.DataFrame:
    recent_returns = window["Monthly Return"].dropna().tail(12)
    drift = float(recent_returns.mean()) if not recent_returns.empty else 0.0
    last_date = window["Date"].iloc[-1]
    price = float(window["Price"].iloc[-1])
    rows = []
    for step in range(1, months + 1):
        price *= 1 + drift
        rows.append({
            "Date": last_date + pd.DateOffset(months=step),
            "Forecast Price": round(price, 4),
            "Assumed Monthly Drift": round(drift, 6),
        })
    return pd.DataFrame(rows)


def _max_drawdown(prices: pd.Series) -> float:
    running_max = prices.cummax()
    drawdowns = prices / running_max - 1
    return float(drawdowns.min())
