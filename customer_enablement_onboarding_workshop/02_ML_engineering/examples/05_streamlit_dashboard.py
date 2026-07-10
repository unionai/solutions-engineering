"""
Exercise 5: Streamlit Dashboard
=================================
Host a Streamlit app on Union — get an endpoint your team can access.

Concepts: AppEnvironment, flyte.serve(), flyte.deploy()

Deploy to Union:  python 05_streamlit_dashboard.py
"""

import sys
from pathlib import Path

import streamlit as st

import flyte
import flyte.app


# --- Streamlit app code ---
def main():
    st.set_page_config(page_title="Forecast Dashboard", layout="wide")
    st.title("Forecast Dashboard")

    # Sidebar controls
    product = st.sidebar.selectbox("Product Category", ["Electronics", "Clothing", "Home & Garden", "Sports"])
    months = st.sidebar.slider("Forecast Horizon (months)", 1, 12, 6)

    # Simulated forecast data
    import numpy as np
    import pandas as pd

    np.random.seed(hash(product) % 2**32)
    dates = pd.date_range("2025-04-01", periods=months, freq="MS")
    baseline = np.random.uniform(80, 120)
    forecast = baseline + np.cumsum(np.random.randn(months) * 5)

    df = pd.DataFrame({
        "Month": dates.strftime("%b %Y"),
        "Forecast": forecast.round(2),
        "Lower Bound": (forecast - np.random.uniform(5, 15, months)).round(2),
        "Upper Bound": (forecast + np.random.uniform(5, 15, months)).round(2),
    })

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{product} Price Forecast")
        chart_df = df.set_index("Month")[["Lower Bound", "Forecast", "Upper Bound"]]
        st.line_chart(chart_df)

    with col2:
        st.subheader("Data")
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Metrics
    st.subheader("Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Price", f"${forecast[0]:.2f}")
    m2.metric(f"{months}mo Forecast", f"${forecast[-1]:.2f}",
              delta=f"{forecast[-1] - forecast[0]:.2f}")
    m3.metric("Avg Forecast", f"${forecast.mean():.2f}")


# --- Union app environment ---
file_name = Path(__file__).name
app_env = flyte.app.AppEnvironment(
    name="forecast-dashboard",
    image=flyte.Image.from_debian_base(python_version=(3, 12)).with_pip_packages(
        "streamlit==1.41.1", "pandas", "numpy"
    ),
    args=[
        "streamlit", "run", file_name,
        "--server.port", "8080",
        "--", "--server",
    ],
    port=8080,
    resources=flyte.Resources(cpu="1", memory="1Gi"),
    requires_auth=False,
)


if __name__ == "__main__":
    if "--server" in sys.argv:
        # Running inside the container
        main()
    else:
        # Deploy to Union
        flyte.init_from_config(root_dir=Path(__file__).parent)
        app = flyte.serve(app_env)
        print(f"Dashboard URL: {app.url}")
