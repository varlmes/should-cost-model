"""Supply-chain network optimization.

Implements a small capacitated plant-location model with embedded data and a
min-cost transportation solver so the Streamlit app can run without external LP
solver dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import product

LOCATIONS = ["USA", "Germany", "Japan", "Brazil", "India"]
SIZES = ["Low", "High"]

VARIABLE_COST = {
    "USA": 12.0,
    "Germany": 13.0,
    "Japan": 10.0,
    "Brazil": 8.0,
    "India": 5.0,
}

FREIGHT_COST_PER_CONTAINER = {
    "USA": {"USA": 0, "Germany": 12250, "Japan": 1100, "Brazil": 16100, "India": 8778},
    "Germany": {"USA": 13335, "Germany": 0, "Japan": 8617, "Brazil": 20244, "India": 10073},
    "Japan": {"USA": 15400, "Germany": 22750, "Japan": 0, "Brazil": 43610, "India": 14350},
    "Brazil": {"USA": 16450, "Germany": 22050, "Japan": 28000, "Brazil": 0, "India": 29750},
    "India": {"USA": 13650, "Germany": 15400, "Japan": 24500, "Brazil": 29400, "India": 0},
}

FIXED_COST_K_PER_MONTH = {
    "USA": {"Low": 6500, "High": 9500},
    "Germany": {"Low": 4980, "High": 7270},
    "Japan": {"Low": 6230, "High": 9100},
    "Brazil": {"Low": 3230, "High": 4730},
    "India": {"Low": 2110, "High": 6160},
}

CAPACITY_K_UNITS = {
    "USA": {"Low": 500, "High": 1500},
    "Germany": {"Low": 500, "High": 1500},
    "Japan": {"Low": 500, "High": 1500},
    "Brazil": {"Low": 500, "High": 1500},
    "India": {"Low": 500, "High": 3000},
}

BASE_DEMAND = {
    "USA": 2_800_000,
    "Germany": 90_000,
    "Japan": 1_700_000,
    "Brazil": 145_000,
    "India": 160_000,
}


@dataclass(frozen=True)
class NetworkInputs:
    demand_multiplier: float = 1.0
    freight_multiplier: float = 1.0
    fixed_cost_multiplier: float = 1.0
    variable_cost_multiplier: float = 1.0
    allow_stacked_capacity: bool = True


@dataclass(frozen=True)
class PlantDecision:
    location: str
    low_open: bool
    high_open: bool
    capacity_units: float
    fixed_cost: float
    utilization: float


@dataclass(frozen=True)
class LaneFlow:
    source: str
    destination: str
    units: float
    unit_cost: float
    total_cost: float


@dataclass(frozen=True)
class NetworkResult:
    inputs: NetworkInputs
    status: str
    total_cost: float
    fixed_cost: float
    variable_cost: float
    demand: dict[str, float]
    plant_decisions: list[PlantDecision]
    flows: list[LaneFlow]
    notes: list[str]


def lane_unit_cost(source: str, destination: str, inputs: NetworkInputs) -> float:
    manufacturing = VARIABLE_COST[source] * inputs.variable_cost_multiplier
    freight = (FREIGHT_COST_PER_CONTAINER[source][destination] / 1000.0) * inputs.freight_multiplier
    return manufacturing + freight


def optimize_network(inputs: NetworkInputs) -> NetworkResult:
    if inputs.demand_multiplier <= 0:
        raise ValueError("demand_multiplier must be > 0")
    if inputs.freight_multiplier < 0 or inputs.fixed_cost_multiplier < 0 or inputs.variable_cost_multiplier < 0:
        raise ValueError("cost multipliers must be >= 0")

    demand = {loc: val * inputs.demand_multiplier for loc, val in BASE_DEMAND.items()}
    total_demand = sum(demand.values())
    best: NetworkResult | None = None

    choices = _plant_choices(inputs.allow_stacked_capacity)
    for combo in product(choices, repeat=len(LOCATIONS)):
        capacities: dict[str, float] = {}
        fixed_cost = 0.0
        low_high = {}
        for loc, choice in zip(LOCATIONS, combo):
            low_open = "Low" in choice
            high_open = "High" in choice
            cap = 0.0
            if low_open:
                cap += CAPACITY_K_UNITS[loc]["Low"] * 1000
                fixed_cost += FIXED_COST_K_PER_MONTH[loc]["Low"] * 1000 * inputs.fixed_cost_multiplier
            if high_open:
                cap += CAPACITY_K_UNITS[loc]["High"] * 1000
                fixed_cost += FIXED_COST_K_PER_MONTH[loc]["High"] * 1000 * inputs.fixed_cost_multiplier
            capacities[loc] = cap
            low_high[loc] = (low_open, high_open)

        if sum(capacities.values()) + 1e-6 < total_demand:
            continue

        costs = {(i, j): lane_unit_cost(i, j, inputs) for i in LOCATIONS for j in LOCATIONS}
        flow_cost, flows = _min_cost_transport(capacities, demand, costs)
        total_cost = fixed_cost + flow_cost
        if best is None or total_cost < best.total_cost:
            production_by_plant = {loc: 0.0 for loc in LOCATIONS}
            lane_flows = []
            for (src, dst), qty in flows.items():
                if qty <= 1e-6:
                    continue
                production_by_plant[src] += qty
                unit_cost = costs[(src, dst)]
                lane_flows.append(LaneFlow(src, dst, round(qty, 2), round(unit_cost, 4), round(qty * unit_cost, 2)))
            plant_decisions = []
            for loc in LOCATIONS:
                low_open, high_open = low_high[loc]
                if not low_open and not high_open:
                    continue
                cap = capacities[loc]
                loc_fixed = 0.0
                if low_open:
                    loc_fixed += FIXED_COST_K_PER_MONTH[loc]["Low"] * 1000 * inputs.fixed_cost_multiplier
                if high_open:
                    loc_fixed += FIXED_COST_K_PER_MONTH[loc]["High"] * 1000 * inputs.fixed_cost_multiplier
                utilization = production_by_plant[loc] / cap if cap else 0.0
                plant_decisions.append(PlantDecision(loc, low_open, high_open, round(cap, 2), round(loc_fixed, 2), round(utilization, 4)))
            best = NetworkResult(
                inputs=inputs,
                status="Optimal",
                total_cost=round(total_cost, 2),
                fixed_cost=round(fixed_cost, 2),
                variable_cost=round(flow_cost, 2),
                demand={k: round(v, 2) for k, v in demand.items()},
                plant_decisions=plant_decisions,
                flows=sorted(lane_flows, key=lambda row: (row.source, row.destination)),
                notes=[
                    "Objective minimizes monthly fixed plant costs plus production and freight cost.",
                    "Demand constraints require each market to be fully served.",
                    "Capacity constraints limit outbound production by opened plant capacity tiers.",
                ],
            )

    if best is None:
        return NetworkResult(inputs, "Infeasible", 0.0, 0.0, 0.0, demand, [], [], ["Total capacity is below demand."])
    return best


def _plant_choices(allow_stacked: bool) -> list[tuple[str, ...]]:
    if allow_stacked:
        return [(), ("Low",), ("High",), ("Low", "High")]
    return [(), ("Low",), ("High",)]


def _min_cost_transport(supply: dict[str, float], demand: dict[str, float], costs: dict[tuple[str, str], float]) -> tuple[float, dict[tuple[str, str], float]]:
    """Successive shortest-path min-cost flow for the tiny complete network."""
    sources = list(supply)
    sinks = list(demand)
    node_count = 2 + len(sources) + len(sinks)
    super_source = 0
    source_offset = 1
    sink_offset = 1 + len(sources)
    super_sink = node_count - 1
    graph: list[list[list[float]]] = [[] for _ in range(node_count)]

    def add_edge(u: int, v: int, cap: float, cost: float, key=None):
        graph[u].append([v, cap, cost, len(graph[v]), key])
        graph[v].append([u, 0.0, -cost, len(graph[u]) - 1, None])

    for idx, src in enumerate(sources):
        add_edge(super_source, source_offset + idx, supply[src], 0.0)
    for i, src in enumerate(sources):
        for j, dst in enumerate(sinks):
            add_edge(source_offset + i, sink_offset + j, min(supply[src], demand[dst]), costs[(src, dst)], (src, dst))
    for idx, dst in enumerate(sinks):
        add_edge(sink_offset + idx, super_sink, demand[dst], 0.0)

    required = sum(demand.values())
    sent = 0.0
    total_cost = 0.0
    potentials = [0.0] * node_count
    flows = {(src, dst): 0.0 for src in sources for dst in sinks}

    while sent + 1e-6 < required:
        dist = [float("inf")] * node_count
        parent: list[tuple[int, int] | None] = [None] * node_count
        dist[super_source] = 0.0
        heap = [(0.0, super_source)]
        while heap:
            cur_dist, u = heappop(heap)
            if cur_dist > dist[u] + 1e-9:
                continue
            for edge_idx, edge in enumerate(graph[u]):
                v, cap, cost, _rev, _key = edge
                if cap <= 1e-9:
                    continue
                reduced = cost + potentials[u] - potentials[v]
                nd = cur_dist + reduced
                if nd + 1e-9 < dist[v]:
                    dist[v] = nd
                    parent[v] = (u, edge_idx)
                    heappush(heap, (nd, v))
        if parent[super_sink] is None:
            raise ValueError("transportation model infeasible")
        for n in range(node_count):
            if dist[n] < float("inf"):
                potentials[n] += dist[n]
        add = required - sent
        v = super_sink
        while v != super_source:
            u, edge_idx = parent[v]
            add = min(add, graph[u][edge_idx][1])
            v = u
        v = super_sink
        while v != super_source:
            u, edge_idx = parent[v]
            edge = graph[u][edge_idx]
            rev = int(edge[3])
            key = edge[4]
            edge[1] -= add
            graph[v][rev][1] += add
            total_cost += add * edge[2]
            if key is not None:
                flows[key] += add
            elif graph[v][rev][4] is not None:
                flows[graph[v][rev][4]] -= add
            v = u
        sent += add

    return total_cost, flows
