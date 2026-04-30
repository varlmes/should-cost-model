"""Alibaba RFQ CSV analysis and lead scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from re import sub

import pandas as pd


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "alibaba_rfq_listings.csv"

EXPECTED_COLUMNS = [
    "RFQ ID",
    "Title",
    "Buyer Name",
    "Buyer Image",
    "Inquiry Time",
    "Quotes Left",
    "Country",
    "Quantity Required",
    "Email Confirmed",
    "Experienced Buyer",
    "Complete Order via RFQ",
    "Typical Replies",
    "Interactive User",
    "Inquiry URL",
    "Inquiry Date",
    "Scraping Date",
]

BADGE_COLUMNS = [
    "Email Confirmed",
    "Experienced Buyer",
    "Complete Order via RFQ",
    "Typical Replies",
    "Interactive User",
]


@dataclass(frozen=True)
class RFQInputs:
    query: str = ""
    min_quantity: float = 0.0
    min_quotes_left: int = 0
    email_confirmed_only: bool = False
    max_rows: int = 100


@dataclass(frozen=True)
class RFQSummary:
    total_rows: int
    filtered_rows: int
    email_confirmed: int
    avg_quotes_left: float
    total_quantity: float
    top_score: int
    notes: list[str]


def load_rfq_csv(path_or_buffer=DEFAULT_DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path_or_buffer)
    df = _normalize_columns(df)
    df["Quotes Left"] = pd.to_numeric(df["Quotes Left"], errors="coerce").fillna(0).astype(int)
    df["Quantity Required"] = df["Quantity Required"].apply(_parse_quantity)
    for col in BADGE_COLUMNS:
        df[col] = df[col].fillna("No").astype(str).str.strip().str.title()
    df["Inquiry URL"] = df["Inquiry URL"].fillna("").astype(str).apply(_normalize_url)
    df["Lead Score"] = df.apply(_lead_score, axis=1)
    df["Matched Keywords"] = df["Title"].fillna("").astype(str).apply(_keywords)
    return df


def analyze_rfqs(df: pd.DataFrame, inputs: RFQInputs) -> tuple[RFQSummary, pd.DataFrame]:
    filtered = df.copy()
    if inputs.query.strip():
        query = inputs.query.strip().lower()
        filtered = filtered[
            filtered["Title"].fillna("").str.lower().str.contains(query, regex=False)
            | filtered["Buyer Name"].fillna("").str.lower().str.contains(query, regex=False)
            | filtered["Country"].fillna("").str.lower().str.contains(query, regex=False)
        ]
    if inputs.min_quantity > 0:
        filtered = filtered[filtered["Quantity Required"] >= inputs.min_quantity]
    if inputs.min_quotes_left > 0:
        filtered = filtered[filtered["Quotes Left"] >= inputs.min_quotes_left]
    if inputs.email_confirmed_only:
        filtered = filtered[filtered["Email Confirmed"] == "Yes"]

    filtered = filtered.sort_values(["Lead Score", "Quotes Left", "Quantity Required"], ascending=[False, False, False])
    filtered = filtered.head(max(1, inputs.max_rows)).reset_index(drop=True)

    summary = RFQSummary(
        total_rows=len(df),
        filtered_rows=len(filtered),
        email_confirmed=int((filtered["Email Confirmed"] == "Yes").sum()) if not filtered.empty else 0,
        avg_quotes_left=round(float(filtered["Quotes Left"].mean()), 2) if not filtered.empty else 0.0,
        total_quantity=round(float(filtered["Quantity Required"].sum()), 2) if not filtered.empty else 0.0,
        top_score=int(filtered["Lead Score"].max()) if not filtered.empty else 0,
        notes=[
            "Lead score rewards verified buyer signals, available quote slots, and larger requested quantities.",
            "This page analyzes structured RFQ CSV data. Live Alibaba scraping should be run separately and only where permitted by site terms and applicable law.",
            "The included dataset is the sample CSV from vin8bit/alibaba-rfq-scraper.",
        ],
    )
    return summary, filtered


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [col.strip().rstrip(".") for col in out.columns]
    for col in EXPECTED_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[EXPECTED_COLUMNS]


def _parse_quantity(value) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).replace(",", "").strip()
    match = sub(r"[^0-9.]", "", text)
    try:
        return float(match) if match else 0.0
    except ValueError:
        return 0.0


def _normalize_url(value: str) -> str:
    if value.startswith("//"):
        return "https:" + value
    return value


def _lead_score(row: pd.Series) -> int:
    score = 0
    score += 20 if row.get("Email Confirmed") == "Yes" else 0
    score += 15 if row.get("Experienced Buyer") == "Yes" else 0
    score += 15 if row.get("Complete Order via RFQ") == "Yes" else 0
    score += 10 if row.get("Typical Replies") == "Yes" else 0
    score += 10 if row.get("Interactive User") == "Yes" else 0
    score += min(int(row.get("Quotes Left", 0)) * 2, 20)
    quantity = float(row.get("Quantity Required", 0) or 0)
    if quantity >= 10_000:
        score += 20
    elif quantity >= 1_000:
        score += 15
    elif quantity >= 100:
        score += 10
    elif quantity > 0:
        score += 5
    return score


def _keywords(title: str) -> str:
    words = [word.lower() for word in sub(r"[^A-Za-z0-9 ]", " ", title).split()]
    stop = {"for", "with", "and", "the", "new", "sale", "best", "custom", "customized"}
    keep = []
    for word in words:
        if len(word) < 4 or word in stop or word in keep:
            continue
        keep.append(word)
        if len(keep) == 5:
            break
    return ", ".join(keep)
