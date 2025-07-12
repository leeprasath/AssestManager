import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
from config import DATABASE_URL

# Streamlit setup
st.set_page_config(page_title="Vector License Usage Dashboard", layout="wide")
st.title("📊 Vector License Usage Dashboard")

# Connect to PostgreSQL
try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        df_db = pd.read_sql("SELECT * FROM license_usage_log", conn)
except Exception as e:
    st.error(f"❌ Failed to connect to database: {e}")
    st.stop()

# -------- 🔼 Upload Section in Sidebar --------
st.sidebar.header("📤 Upload Usage Data")
uploaded_file = st.sidebar.file_uploader("Upload Power BI Export CSV", type=["csv"])

if uploaded_file:
    df_upload = pd.read_csv(uploaded_file)

    st.subheader("🔍 Preview of Uploaded Data")
    st.dataframe(df_upload.head(10), use_container_width=True)

    required_columns = [
        "vni_asset_number", "license_id", "project_name", "domain_name", "team_name",
        "current_user_id", "duration_days", "duration_hours"
    ]

    if not all(col in df_upload.columns for col in required_columns):
        st.error("❌ CSV is missing one or more required columns.")
    else:
        try:
            # Clean column types
            df_upload["license_id"] = pd.to_numeric(df_upload["license_id"], errors="coerce")
            df_upload["duration_days"] = pd.to_numeric(df_upload["duration_days"], errors="coerce")
            df_upload["duration_hours"] = pd.to_numeric(df_upload["duration_hours"], errors="coerce")

            with engine.begin() as conn:
                df_upload.to_sql("license_usage_log", conn, if_exists="append", index=False)

            st.success(f"✅ Uploaded {len(df_upload)} records to database.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"❌ Failed to insert into database: {e}")

# -------- 📊 Dashboard Tab --------
# Safe license_id conversion
def clean_license_id(x):
    try:
        return str(int(float(x)))
    except:
        return None

df = df_db[df_db["license_id"].notna()].copy()
df["license_id"] = df["license_id"].apply(clean_license_id)

tab1 = st.tabs(["📊 Usage Summary"])[0]

with tab1:
    st.subheader("📋 Full License Usage Table")
    st.dataframe(df, use_container_width=True)

    st.caption("ℹ️ To clear all data, use your PostgreSQL shell:\n`DELETE FROM license_usage_log;`")

    st.subheader("⚙️ Filter Licenses with Low Usage")
    threshold = st.number_input(
        "Show licenses with total usage less than (days):",
        min_value=1, max_value=30, value=6, step=1
    )

    usage_by_license = (
        df.groupby("license_id")[["duration_days"]]
        .sum()
        .reset_index()
    )

    low_usage = usage_by_license[usage_by_license["duration_days"] < threshold].copy()
    low_usage["license_id"] = low_usage["license_id"].apply(clean_license_id)
    low_usage = low_usage[low_usage["license_id"].notna()]

    if low_usage.empty:
        st.success(f"✅ No licenses with total usage less than {threshold} days.")
    else:
        st.subheader(f"📉 Licenses with Total Usage < {threshold} Days")

        fig = px.bar(
            low_usage.sort_values(by="duration_days", ascending=True),
            x="license_id",
            y="duration_days",
            title=f"Total Usage Duration (Days) per License ID [< {threshold} days]",
            labels={"duration_days": "Total Days", "license_id": "License ID"},
        )
        fig.update_layout(
            xaxis_tickangle=-90,
            xaxis=dict(type="category"),
            yaxis=dict(range=[-0.5, low_usage["duration_days"].max() + 1])
        )
        st.plotly_chart(fig, use_container_width=True)

        enriched = pd.merge(
            low_usage,
            df[["license_id", "project_name", "domain_name", "team_name"]].drop_duplicates(),
            on="license_id",
            how="left"
        )

        st.subheader("🗂️ License Details Below Threshold")
        st.dataframe(enriched.sort_values(by="duration_days"), use_container_width=True)
        
        st.subheader("🧾 Duplicate License ID Entries (Excluding Durations)")

        # Find license_ids that appear more than once
        duplicate_ids = df["license_id"].value_counts()
        duplicate_ids = duplicate_ids[duplicate_ids > 1].index.tolist()

        # Filter rows with duplicate license_id
        df_duplicates = df[df["license_id"].isin(duplicate_ids)].copy()

        # Drop duration columns
        cols_to_show = [col for col in df_duplicates.columns if col not in ["duration_days", "duration_hours"]]

        if df_duplicates.empty:
            st.info("✅ No duplicate license IDs found.")
        else:
            st.dataframe(df_duplicates[cols_to_show].sort_values(by="license_id"), use_container_width=True)

