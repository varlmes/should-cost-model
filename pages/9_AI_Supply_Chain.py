import io

import pandas as pd
import streamlit as st

from engine.ai_supply_chain import load_vendor_data, run_supply_chain_workflows

st.set_page_config(page_title="AI Supply Chain", page_icon="⚙", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
  .ai-hero { background: radial-gradient(circle at 18% 18%, rgba(92,214,184,.9) 0, transparent 22%), linear-gradient(135deg, #111518 0%, #21323a 55%, #3f4630 100%); color: #f2fff9; padding: 28px 32px; border: 1px solid rgba(255,255,255,.14); margin-bottom: 18px; }
  .ai-kicker { letter-spacing: .18em; text-transform: uppercase; color: #bef5e5; font-size: .72rem; }
  .ai-price { font-size: 3rem; line-height: 1; font-weight: 800; margin: 10px 0 6px; }
  .ai-band { color: #dff9f1; }
  .rule { border: none; border-top: 1px solid #d4dad7; margin: 22px 0; }
</style>
""",
    unsafe_allow_html=True,
)


def pct(value: float) -> str:
    return f"{value:.1%}"


def csv_button(label: str, df: pd.DataFrame, filename: str):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    st.download_button(label, buffer.getvalue(), file_name=filename, mime="text/csv")


st.markdown("#### — Sourcing Operations Suite")
st.title("AI Supply Chain")
st.caption("Vendor normalization, spend aggregation, tail-spend grouping, and lightweight spend classification.")
st.markdown("Reference project: [rahulissar/ai-supply-chain](https://github.com/rahulissar/ai-supply-chain)")
st.markdown('<hr class="rule">', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Upload Vendor CSV",
    type=["csv"],
    help="Expected columns: Supplier Code, Supplier Name. Leave blank to use the repository sample vendor data.",
)

try:
    vendor_df = load_vendor_data(uploaded) if uploaded else load_vendor_data()
    results = run_supply_chain_workflows(vendor_df)
except Exception as exc:
    st.error(f"AI supply-chain workflow failed: {exc}")
    st.stop()

summary = results["summary"]
st.markdown(
    f"""
<div class="ai-hero">
  <div class="ai-kicker">Vendor Normalization + Spend Classification</div>
  <div class="ai-price">{summary.cluster_count:,} vendor clusters</div>
  <div class="ai-band">Suppliers: {summary.supplier_count:,} | Cleaned spend rows: {summary.cleaned_rows:,} | Raw demo spend rows: {summary.raw_rows:,}</div>
  <div class="ai-band">Strategic categories: {summary.strategic_categories:,} | Tail categories: {summary.tail_categories:,} | Classification accuracy: {pct(summary.classification_accuracy)}</div>
</div>
""",
    unsafe_allow_html=True,
)

cols = st.columns(4)
cols[0].metric("Suppliers", f"{summary.supplier_count:,}")
cols[1].metric("Clusters", f"{summary.cluster_count:,}")
cols[2].metric("Strategic Categories", f"{summary.strategic_categories:,}")
cols[3].metric("Classifier Accuracy", pct(summary.classification_accuracy))

tabs = st.tabs([
    "Data Preprocessing",
    "Feature Engineering",
    "Spend Aggregation",
    "Vendor Normalization",
    "Classification Engine",
    "Settings / Notes",
])

with tabs[0]:
    st.subheader("Data Preprocessing")
    st.dataframe(results["cleaned"], width="stretch", hide_index=True)
    csv_button("Download Cleaned Spend (.csv)", results["cleaned"], "ai_supply_chain_cleaned_spend.csv")

with tabs[1]:
    st.subheader("Text Feature Engineering")
    feature_cols = [
        "Supplier Name",
        "Item Name",
        "Item Description",
        "supplier_cleaned",
        "item_desc",
        "item_name",
        "bow",
        "Is_Service",
    ]
    st.dataframe(results["featured"][feature_cols], width="stretch", hide_index=True)
    st.caption("Mirrors the source merge_desc, gen_itemtype, and text preprocessing workflow.")
    csv_button("Download Featured Rows (.csv)", results["featured"], "ai_supply_chain_featured_rows.csv")

with tabs[2]:
    st.subheader("Spend Aggregation + Tail Grouping")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Supplier Spend**")
        st.dataframe(results["supplier_spend"], width="stretch", hide_index=True)
    with c2:
        st.markdown("**Category Spend**")
        st.dataframe(results["category_spend"], width="stretch", hide_index=True)
    csv_button("Download Category Grouping (.csv)", results["category_spend"], "ai_supply_chain_category_grouping.csv")

with tabs[3]:
    st.subheader("Vendor Name Normalization")
    clusters = results["clusters"].sort_values(["Cluster", "Score_with_standard", "Supplier Name"], ascending=[True, False, True])
    st.dataframe(clusters, width="stretch", hide_index=True)
    st.caption("Uses cleaned names, pairwise similarity, deterministic clustering, and a cluster-level standard name.")
    csv_button("Download Vendor Clusters (.csv)", clusters, "ai_supply_chain_vendor_clusters.csv")

with tabs[4]:
    st.subheader("Spend Classification Engine")
    classified = results["classified"][
        [
            "Supplier Name",
            "Item Name",
            "Segment Title",
            "Final_Category",
            "Predicted_Category",
            "Correct",
            "Quantity",
            "Unit Price",
            "Total Price",
            "Is_Service",
        ]
    ]
    st.dataframe(classified, width="stretch", hide_index=True)
    st.caption("Represents the source RandomForest/TF-IDF pipeline with a lightweight keyword classifier for dependency-free app runtime.")
    csv_button("Download Classification Results (.csv)", classified, "ai_supply_chain_classification_results.csv")

with tabs[5]:
    st.subheader("Settings / Notes")
    settings_df = pd.DataFrame([
        ("Source algorithms", "pre_processing, preprocess_text, merge_desc, gen_itemtype, spend_agg, spend_grouper, company_clusters, standard_name, classification workflow"),
        ("Service keywords", "amendment, agreement, bill, clubs, government, license, maintenance, membership, rent, service, utility"),
        ("Strategic/tail threshold", "80.5% cumulative row count, matching the source example"),
        ("Vendor sample", "data/ai_supply_chain_vendor_data.csv"),
    ], columns=["Setting", "Value"])
    st.dataframe(settings_df, width="stretch", hide_index=True)
    for note in summary.notes:
        st.caption(f"- {note}")

st.markdown(
    """
<div style="font-family:'Courier New', monospace; font-size:.68rem; color:#7b8782; margin-top:28px; border-top:1px solid #d4dad7; padding-top:10px;">
  AI Supply Chain | Preprocessing + feature engineering + spend aggregation + vendor normalization + classification | Inspired by rahulissar/ai-supply-chain.
</div>
""",
    unsafe_allow_html=True,
)
