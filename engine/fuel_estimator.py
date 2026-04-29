"""Fuel trip cost calculator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FuelInputs:
    distance: float
    fuel_efficiency: float
    fuel_price: float
    distance_unit: str = "km"
    efficiency_unit: str = "L/100 km"
    round_trip: bool = False
    passengers: int = 1
    extra_costs: float = 0.0


@dataclass(frozen=True)
class FuelEstimate:
    inputs: FuelInputs
    one_way_distance_km: float
    trip_distance_km: float
    fuel_liters: float
    fuel_cost: float
    total_cost: float
    cost_per_passenger: float
    cost_per_km: float
    cost_per_mile: float


KM_PER_MILE = 1.609344
LITERS_PER_GALLON = 3.785411784


def estimate_fuel_cost(inputs: FuelInputs) -> FuelEstimate:
    if inputs.distance < 0:
        raise ValueError("distance must be >= 0")
    if inputs.fuel_efficiency < 0:
        raise ValueError("fuel_efficiency must be >= 0")
    if inputs.fuel_price < 0:
        raise ValueError("fuel_price must be >= 0")
    if inputs.passengers < 1:
        raise ValueError("passengers must be >= 1")
    if inputs.extra_costs < 0:
        raise ValueError("extra_costs must be >= 0")

    one_way_km = inputs.distance * KM_PER_MILE if inputs.distance_unit == "mi" else inputs.distance
    trip_km = one_way_km * (2 if inputs.round_trip else 1)

    if inputs.efficiency_unit == "mpg":
        trip_miles = trip_km / KM_PER_MILE
        fuel_liters = (trip_miles / inputs.fuel_efficiency) * LITERS_PER_GALLON if inputs.fuel_efficiency else 0.0
    elif inputs.efficiency_unit == "km/L":
        fuel_liters = trip_km / inputs.fuel_efficiency if inputs.fuel_efficiency else 0.0
    else:
        fuel_liters = (trip_km / 100) * inputs.fuel_efficiency

    fuel_cost = fuel_liters * inputs.fuel_price
    total_cost = fuel_cost + inputs.extra_costs
    cost_per_km = total_cost / trip_km if trip_km else 0.0
    cost_per_mile = total_cost / (trip_km / KM_PER_MILE) if trip_km else 0.0

    return FuelEstimate(
        inputs=inputs,
        one_way_distance_km=round(one_way_km, 4),
        trip_distance_km=round(trip_km, 4),
        fuel_liters=round(fuel_liters, 4),
        fuel_cost=round(fuel_cost, 4),
        total_cost=round(total_cost, 4),
        cost_per_passenger=round(total_cost / inputs.passengers, 4),
        cost_per_km=round(cost_per_km, 4),
        cost_per_mile=round(cost_per_mile, 4),
    )
