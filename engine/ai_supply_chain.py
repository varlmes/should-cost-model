"""Lightweight AI supply-chain workflows inspired by rahulissar/ai-supply-chain."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from re import sub

import pandas as pd


DEFAULT_VENDOR_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_supply_chain_vendor_data.csv"

COLUMN_LIST = [
    "Supplier Code",
    "Supplier Name",
    "Item Name",
    "Item Description",
    "Quantity",
    "Unit Price",
    "Total Price",
    "Segment",
    "Segment Title",
]

PRICING_COLUMNS = ["Unit Price", "Total Price"]
PRIMARY_KEYS = ["Supplier Code", "Segment"]
TEXTUAL_COLUMNS = ["supplier_cleaned", "item_desc", "item_name"]
SERVICE_KEYWORDS = {
    "amendment", "agreement", "bill", "clubs", "government", "govt", "license",
    "maintenance", "membership", "rent", "service", "services", "utility", "utilities",
}
VENDOR_STOPWORDS = {
    "biz", "bv", "blank", "co", "comp", "company", "corp", "corporation", "confidential",
    "dba", "inc", "incorp", "incorporat", "incorporate", "incorporated", "incorporation",
    "international", "intl", "intnl", "limited", "llc", "ltd", "llp", "machines",
    "pvt", "pte", "private", "unknown", "lp", "l", "p",
}


@dataclass(frozen=True)
class SupplyChainSummary:
    raw_rows: int
    cleaned_rows: int
    supplier_count: int
    cluster_count: int
    strategic_categories: int
    tail_categories: int
    classification_accuracy: float
    notes: list[str]


def load_vendor_data(path_or_buffer=DEFAULT_VENDOR_PATH) -> pd.DataFrame:
    df = pd.read_csv(path_or_buffer, encoding="utf-8-sig")
    df.columns = [col.strip() for col in df.columns]
    return df


def demo_spend_data(vendors: pd.DataFrame) -> pd.DataFrame:
    segments = [
        (100, "IT Hardware", "laptop docking station", "computer equipment and monitor"),
        (110, "Telecom Services", "mobile service plan", "wireless service agreement"),
        (120, "Office Supplies", "paper toner", "office consumables"),
        (130, "Facilities Maintenance", "maintenance visit", "building repair service"),
        (140, "Logistics", "freight shipment", "transport and delivery"),
        (150, "Software License", "cloud software license", "annual user license agreement"),
    ]
    rows = []
    for idx, row in vendors.reset_index(drop=True).iterrows():
        seg, title, item, desc = segments[idx % len(segments)]
        qty = (idx % 7) + 1
        unit = [120.0, 45.0, 18.5, 350.0, 225.0, 980.0][idx % len(segments)]
        if "DELL" in str(row["Supplier Name"]).upper():
            seg, title, item, desc, unit = 100, "IT Hardware", "server accessory", "computer hardware equipment", 620.0
        elif "AT" in str(row["Supplier Name"]).upper():
            seg, title, item, desc, unit = 110, "Telecom Services", "data service", "mobile telecom service agreement", 80.0
        elif "PITNEY" in str(row["Supplier Name"]).upper():
            seg, title, item, desc, unit = 140, "Logistics", "postage meter", "mailroom shipping service", 260.0
        rows.append({
            "Supplier Code": row["Supplier Code"],
            "Supplier Name": row["Supplier Name"],
            "Item Name": item,
            "Item Description": desc,
            "Quantity": qty,
            "Unit Price": f"${unit:,.2f}",
            "Total Price": f"${qty * unit:,.2f}",
            "Segment": seg,
            "Segment Title": title,
        })
    return pd.DataFrame(rows)


def pre_processing(df: pd.DataFrame) -> pd.DataFrame:
    out = df[COLUMN_LIST].dropna().copy()
    for col in PRIMARY_KEYS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    for col in PRICING_COLUMNS:
        out[col] = out[col].astype(str).str.replace(r"[^\d.]+", "", regex=True)
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna().drop_duplicates()
    out = out[out["Total Price"] > 0].reset_index(drop=True)
    return out


def preprocess_text_values(values, include_english_stopwords: bool = False) -> list[str]:
    return [_clean_text(str(value), include_english_stopwords) for value in values]


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["supplier_cleaned"] = preprocess_text_values(out["Supplier Name"])
    out["item_desc"] = preprocess_text_values(out["Item Description"], include_english_stopwords=True)
    out["item_name"] = preprocess_text_values(out["Item Name"], include_english_stopwords=True)
    out["bow"] = out[TEXTUAL_COLUMNS].agg(" ".join, axis=1).str.strip()
    service_pattern = "|".join(sorted(SERVICE_KEYWORDS))
    out["Is_Service"] = out["bow"].str.contains(service_pattern, case=False, regex=True).astype(int)
    return out


def spend_agg(df: pd.DataFrame, columns: list[str], percentage: float = 80.5) -> pd.DataFrame:
    grouped = df.groupby(columns)["Total Price"].agg(["sum", "count"]).reset_index()
    grouped = grouped.sort_values("count", ascending=False).reset_index(drop=True)
    grouped["cum_sum_count"] = grouped["count"].cumsum()
    grouped["cum_perc_count"] = (100 * grouped["cum_sum_count"] / grouped["count"].sum()).round(1)
    grouped["cum_sum_sum"] = grouped["sum"].cumsum()
    grouped["cum_perc_sum"] = (100 * grouped["cum_sum_sum"] / grouped["sum"].sum()).round(1)
    grouped["spend_type"] = grouped["cum_perc_count"].gt(float(percentage)).map({True: "Tail Spend", False: "Strategic Spend"})
    return grouped


def spend_grouper(category_df: pd.DataFrame, percentage: float = 80.5) -> pd.DataFrame:
    out = category_df.copy()
    out["Final_Category"] = out.apply(
        lambda row: "Other Services"
        if row["cum_perc_count"] > percentage and row["Is_Service"] == 1
        else "Other Goods"
        if row["cum_perc_count"] > percentage
        else row["Segment Title"],
        axis=1,
    )
    out["Final_Code"] = pd.factorize(out["Final_Category"])[0]
    return out


def vendor_clusters(vendors: pd.DataFrame, threshold: float = 0.72) -> pd.DataFrame:
    suppliers = vendors[["Supplier Code", "Supplier Name"]].drop_duplicates().copy()
    suppliers["Cleaned_Name"] = preprocess_text_values(suppliers["Supplier Name"])
    clusters: list[int] = []
    cluster_names: dict[int, list[str]] = {}
    next_cluster = 0
    for name in suppliers["Cleaned_Name"]:
        best_cluster = None
        best_score = 0.0
        for cluster, names in cluster_names.items():
            score = max(_similarity(name, existing) for existing in names)
            if score > best_score:
                best_score = score
                best_cluster = cluster
        if best_cluster is None or best_score < threshold:
            best_cluster = next_cluster
            cluster_names[best_cluster] = []
            next_cluster += 1
        cluster_names[best_cluster].append(name)
        clusters.append(best_cluster)
    suppliers["Cluster"] = clusters
    suppliers["StandardName"] = suppliers.groupby("Cluster")["Cleaned_Name"].transform(_standard_name)
    suppliers["Score_with_standard"] = suppliers.apply(lambda row: round(_similarity(row["Cleaned_Name"], row["StandardName"]) * 100, 1), axis=1)
    return suppliers


def classify_spend(featured: pd.DataFrame, grouped_categories: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    labels = grouped_categories[["Segment Title", "Final_Category", "Final_Code"]].drop_duplicates()
    data = featured.merge(labels, on="Segment Title", how="left")
    train = data.iloc[::2].copy()
    test = data.iloc[1::2].copy()
    profiles: dict[str, Counter] = defaultdict(Counter)
    for _, row in train.iterrows():
        profiles[row["Final_Category"]].update(row["bow"].split())
    fallback = train["Final_Category"].mode().iloc[0] if not train.empty else "Other Goods"
    predictions = []
    for _, row in test.iterrows():
        scores = {cat: sum(counter.get(token, 0) for token in row["bow"].split()) for cat, counter in profiles.items()}
        predictions.append(max(scores, key=scores.get) if scores and max(scores.values()) > 0 else fallback)
    test["Predicted_Category"] = predictions
    test["Correct"] = test["Predicted_Category"].eq(test["Final_Category"])
    accuracy = float(test["Correct"].mean()) if not test.empty else 0.0
    return test, accuracy


def run_supply_chain_workflows(vendor_data: pd.DataFrame | None = None) -> dict[str, object]:
    vendors = load_vendor_data() if vendor_data is None else vendor_data.copy()
    spend_raw = demo_spend_data(vendors)
    cleaned = pre_processing(spend_raw)
    featured = feature_engineering(cleaned)
    supplier_spend = spend_agg(featured, ["Supplier Code", "Supplier Name"])
    category_spend = spend_agg(featured, ["Segment Title"])
    category_spend = category_spend.merge(featured.groupby("Segment Title")["Is_Service"].max().reset_index(), on="Segment Title", how="left")
    grouped = spend_grouper(category_spend)
    clusters = vendor_clusters(vendors)
    classified, accuracy = classify_spend(featured, grouped)
    summary = SupplyChainSummary(
        raw_rows=len(spend_raw),
        cleaned_rows=len(cleaned),
        supplier_count=vendors["Supplier Code"].nunique(),
        cluster_count=clusters["Cluster"].nunique(),
        strategic_categories=int((grouped["spend_type"] == "Strategic Spend").sum()),
        tail_categories=int((grouped["spend_type"] == "Tail Spend").sum()),
        classification_accuracy=round(accuracy, 4),
        notes=[
            "Vendor clustering uses cleaned legal-entity names plus a deterministic similarity threshold.",
            "Spend aggregation follows the source repository's cumulative-count strategic/tail-spend split.",
            "The classification tab mirrors the original pipeline with a lightweight keyword classifier instead of the source RandomForest/TF-IDF dependency chain.",
        ],
    )
    return {
        "vendors": vendors,
        "spend_raw": spend_raw,
        "cleaned": cleaned,
        "featured": featured,
        "supplier_spend": supplier_spend,
        "category_spend": grouped,
        "clusters": clusters,
        "classified": classified,
        "summary": summary,
    }


def _clean_text(text: str, include_english_stopwords: bool = False) -> str:
    text = text.encode("ascii", "ignore").decode("utf-8", "ignore")
    text = sub(r"[^A-Za-z0-9\s]", " ", text).lower()
    words = [word for word in text.split() if word not in VENDOR_STOPWORDS]
    if include_english_stopwords:
        words = [word for word in words if word not in {"and", "or", "the", "for", "of", "to", "a", "an"}]
    return " ".join(words).strip()


def _similarity(a: str, b: str) -> float:
    token_a = set(a.split())
    token_b = set(b.split())
    token_score = len(token_a & token_b) / max(len(token_a | token_b), 1)
    seq_score = SequenceMatcher(None, a, b).ratio()
    return max(token_score, seq_score)


def _standard_name(names: pd.Series) -> str:
    tokens = []
    for name in names:
        tokens.extend(name.split())
    if not tokens:
        return ""
    counts = Counter(tokens)
    common = [token for token, _count in counts.most_common(2)]
    return " ".join(common).upper()
