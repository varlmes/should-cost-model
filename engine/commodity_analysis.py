"""Deterministic commodity price and procurement-risk analytics."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, pi, sin, sqrt
from random import Random
from statistics import mean, pstdev


TRADING_DAYS = 252


@dataclass(frozen=True)
class CommodityProfile:
    name: str
    unit: str
    current_price: float
    annual_volatility: float
    annual_drift: float
    seasonality: float


@dataclass(frozen=True)
class CommodityPosition:
    name: str
    unit: str
    current_price: float
    monthly_volume: float
    hedge_coverage: float = 0.0


@dataclass(frozen=True)
class CommodityInputs:
    positions: list[CommodityPosition]
    horizon_days: int = 63
    confidence_level: float = 0.95
    shock_pct: float = 0.10


@dataclass(frozen=True)
class CommodityMetric:
    name: str
    unit: str
    current_price: float
    monthly_volume: float
    monthly_spend: float
    unhedged_spend: float
    annualized_volatility: float
    trailing_return: float
    var_price_move: float
    cvar_price_move: float
    stress_cost_impact: float
    low_price: float
    base_price: float
    high_price: float


@dataclass(frozen=True)
class CommodityAnalysis:
    inputs: CommodityInputs
    metrics: list[CommodityMetric]
    total_monthly_spend: float
    unhedged_monthly_spend: float
    portfolio_var: float
    portfolio_cvar: float
    stress_cost_impact: float
    price_history: dict[str, list[float]]
    notes: list[str]


COMMODITY_PROFILES: dict[str, CommodityProfile] = {
    "Steel HRC": CommodityProfile("Steel HRC", "$/short ton", 850.0, 0.28, 0.03, 0.05),
    "Aluminum": CommodityProfile("Aluminum", "$/metric ton", 2450.0, 0.24, 0.025, 0.03),
    "Copper": CommodityProfile("Copper", "$/metric ton", 9400.0, 0.27, 0.035, 0.04),
    "Nickel": CommodityProfile("Nickel", "$/metric ton", 18200.0, 0.38, 0.02, 0.06),
    "Lithium Carbonate": CommodityProfile("Lithium Carbonate", "$/metric ton", 14500.0, 0.55, -0.02, 0.08),
    "Crude Oil": CommodityProfile("Crude Oil", "$/barrel", 82.0, 0.34, 0.015, 0.07),
    "Natural Gas": CommodityProfile("Natural Gas", "$/MMBtu", 2.75, 0.62, 0.00, 0.18),
    "Gold": CommodityProfile("Gold", "$/troy oz", 2300.0, 0.18, 0.025, 0.02),
}


def default_positions() -> list[CommodityPosition]:
    volumes = {
        "Steel HRC": 120.0,
        "Aluminum": 40.0,
        "Copper": 18.0,
        "Crude Oil": 900.0,
    }
    return [
        CommodityPosition(profile.name, profile.unit, profile.current_price, volumes.get(profile.name, 0.0), 0.0)
        for profile in COMMODITY_PROFILES.values()
    ]


def analyze_commodities(inputs: CommodityInputs) -> CommodityAnalysis:
    if not inputs.positions:
        raise ValueError("at least one commodity position is required")
    if inputs.horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")
    if not 0.50 <= inputs.confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0.50 and 0.99")
    if inputs.shock_pct < 0:
        raise ValueError("shock_pct must be >= 0")

    metrics: list[CommodityMetric] = []
    history: dict[str, list[float]] = {}
    portfolio_losses: list[float] = []

    for position in inputs.positions:
        if position.current_price < 0:
            raise ValueError(f"{position.name} current_price must be >= 0")
        if position.monthly_volume < 0:
            raise ValueError(f"{position.name} monthly_volume must be >= 0")
        if not 0 <= position.hedge_coverage <= 1:
            raise ValueError(f"{position.name} hedge_coverage must be between 0 and 1")

        profile = COMMODITY_PROFILES.get(position.name)
        if profile is None:
            profile = CommodityProfile(position.name, position.unit, position.current_price, 0.30, 0.02, 0.04)

        prices = _price_path(profile, position.current_price, days=252)
        returns = _returns(prices)
        sorted_returns = sorted(returns)
        tail_count = max(1, int(len(sorted_returns) * (1 - inputs.confidence_level)))
        tail = sorted_returns[:tail_count]
        horizon_scale = sqrt(inputs.horizon_days)
        var_move = abs(sorted_returns[tail_count - 1]) * horizon_scale
        cvar_move = abs(mean(tail)) * horizon_scale
        monthly_spend = position.current_price * position.monthly_volume
        unhedged_spend = monthly_spend * (1 - position.hedge_coverage)
        stress_impact = unhedged_spend * inputs.shock_pct

        metrics.append(
            CommodityMetric(
                name=position.name,
                unit=position.unit,
                current_price=round(position.current_price, 4),
                monthly_volume=round(position.monthly_volume, 4),
                monthly_spend=round(monthly_spend, 2),
                unhedged_spend=round(unhedged_spend, 2),
                annualized_volatility=round(pstdev(returns) * sqrt(TRADING_DAYS), 4) if len(returns) > 1 else 0.0,
                trailing_return=round((prices[-1] / prices[0]) - 1, 4) if prices[0] else 0.0,
                var_price_move=round(var_move, 4),
                cvar_price_move=round(cvar_move, 4),
                stress_cost_impact=round(stress_impact, 2),
                low_price=round(position.current_price * exp(-cvar_move), 4),
                base_price=round(position.current_price * exp(profile.annual_drift * inputs.horizon_days / TRADING_DAYS), 4),
                high_price=round(position.current_price * exp(cvar_move), 4),
            )
        )
        history[position.name] = [round(price, 4) for price in prices]
        portfolio_losses.extend([unhedged_spend * max(0.0, -ret) * horizon_scale for ret in returns])

    total_monthly_spend = sum(item.monthly_spend for item in metrics)
    unhedged_monthly_spend = sum(item.unhedged_spend for item in metrics)
    portfolio_losses.sort(reverse=True)
    tail_count = max(1, int(len(portfolio_losses) * (1 - inputs.confidence_level)))
    tail_losses = portfolio_losses[:tail_count]

    return CommodityAnalysis(
        inputs=inputs,
        metrics=metrics,
        total_monthly_spend=round(total_monthly_spend, 2),
        unhedged_monthly_spend=round(unhedged_monthly_spend, 2),
        portfolio_var=round(tail_losses[-1], 2) if tail_losses else 0.0,
        portfolio_cvar=round(mean(tail_losses), 2) if tail_losses else 0.0,
        stress_cost_impact=round(sum(item.stress_cost_impact for item in metrics), 2),
        price_history=history,
        notes=[
            "Price paths are deterministic seeded scenarios for sourcing analysis, not live market data.",
            "VaR and CVaR estimate downside procurement exposure over the selected horizon.",
            "Hedge coverage reduces spend-at-risk and stress impact but does not change displayed commodity prices.",
        ],
    )


def _price_path(profile: CommodityProfile, current_price: float, days: int) -> list[float]:
    rng = Random(profile.name)
    sigma_daily = profile.annual_volatility / sqrt(TRADING_DAYS)
    drift_daily = (profile.annual_drift - 0.5 * profile.annual_volatility**2) / TRADING_DAYS
    start_price = current_price / exp(profile.annual_drift)
    prices = [max(0.0001, start_price)]

    for day in range(1, days + 1):
        seasonal = profile.seasonality * sin(2 * pi * day / TRADING_DAYS) / TRADING_DAYS
        shock = sigma_daily * rng.gauss(0.0, 1.0)
        prices.append(max(0.0001, prices[-1] * exp(drift_daily + seasonal + shock)))

    if prices[-1] > 0:
        scale = current_price / prices[-1]
        prices = [price * scale for price in prices]
    return prices


def _returns(prices: list[float]) -> list[float]:
    return [log(prices[idx] / prices[idx - 1]) for idx in range(1, len(prices)) if prices[idx - 1] > 0]
