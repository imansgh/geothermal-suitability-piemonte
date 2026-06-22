"""Interactive Streamlit dashboard for geothermal suitability screening.

Run from the repository root::

    streamlit run dashboard/app.py

The dashboard is a thin presentation layer over ``gsp.pipeline``: it adjusts
the reference depth and grid resolution, then renders the map, the ranking
chart, the depth-temperature scatter, and the interpolation validation report.
All computation happens in the package, so the dashboard and the CLI always
agree.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from gsp.data.models import SuitabilityClass
from gsp.pipeline import run_pipeline
from gsp.viz.charts import (
    depth_temperature_scatter,
    power_search_curve,
    suitability_ranking,
)
from gsp.viz.maps import SUITABILITY_COLORS, build_map

st.set_page_config(
    page_title="Geothermal Suitability — Po Plain", layout="wide", page_icon="🌋"
)

st.title("🌋 Geothermal Suitability Screening — Po Plain, Piemonte")
st.caption(
    "Legacy hydrocarbon wells screened for geothermal reuse from corrected "
    "bottom-hole-temperature archives. A screening aid, not a site-specific "
    "feasibility study."
)

# --- Sidebar controls ---
with st.sidebar:
    st.header("Controls")
    reference_depth = st.slider(
        "Reference depth for predicted-T overlay (m)",
        min_value=1000, max_value=5000, value=2000, step=250,
    )
    resolution = st.select_slider(
        "Interpolation grid resolution", options=[40, 60, 80, 100, 120], value=80
    )
    show_overlay = st.checkbox("Show interpolated temperature overlay", value=True)
    st.markdown("---")
    st.markdown(
        "**Method**: deepest BHT reading per well → Horner/Hybrid correction → "
        "multi-criteria classification. Spatial overlay interpolates the "
        "geothermal *gradient* (depth-normalised) with LOOCV-tuned IDW."
    )


@st.cache_data(show_spinner="Running screening pipeline…")
def _cached_pipeline(res: int) -> dict:
    out = run_pipeline(interpolate=True, grid_resolution=res)
    return {
        "results": out.results,
        "measurements": out.measurements,
        "field": out.field,
        "power_search": out.power_search,
    }


data = _cached_pipeline(resolution)
results = data["results"]
field = data["field"]

# --- Top metrics ---
counts = Counter(r.suitability for r in results)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Wells screened", len(results))
c2.metric("Power generation", counts.get(SuitabilityClass.POWER_GENERATION, 0))
c3.metric("Direct use", counts.get(SuitabilityClass.DIRECT_USE, 0))
c4.metric("Ground-source HP", counts.get(SuitabilityClass.GROUND_SOURCE_HP, 0))
if field is not None:
    c5.metric("LOOCV RMSE", f"{field.loocv_rmse_c_per_km:g} °C/km")

# --- Map ---
st.subheader("Interactive suitability map")
all_meas: dict[str, list[tuple[float, float, float]]] = {}
for m in data["measurements"]:
    all_meas.setdefault(m.well, []).append((m.depth_m, m.t_raw_c, m.t_corrected_c))

fmap = build_map(
    results,
    field if show_overlay else None,
    reference_depth_m=float(reference_depth),
    all_measurements=all_meas,
)
try:
    from streamlit_folium import st_folium

    st_folium(fmap, width=None, height=560, returned_objects=[])
except ImportError:
    st.components.v1.html(fmap._repr_html_(), height=560)

# --- Charts ---
col_left, col_right = st.columns(2)
with col_left:
    st.subheader("Wells ranked by corrected temperature")
    st.plotly_chart(suitability_ranking(results), use_container_width=True)
with col_right:
    st.subheader("Depth vs temperature")
    st.plotly_chart(
        depth_temperature_scatter(data["measurements"]), use_container_width=True
    )

# --- Validation ---
st.subheader("Interpolation validation (leave-one-out cross-validation)")
if data["power_search"] is not None and field is not None:
    vcol1, vcol2 = st.columns([2, 1])
    with vcol1:
        st.plotly_chart(
            power_search_curve(data["power_search"].sweep, field.best_power),
            use_container_width=True,
        )
    with vcol2:
        st.markdown(
            f"""
**Selected IDW power**: {field.best_power:g}
**LOOCV RMSE**: {field.loocv_rmse_c_per_km:g} °C/km
**LOOCV MAE**: {field.loocv_mae_c_per_km:g} °C/km

The gradient RMSE is comparable to the gradient's own spatial spread,
reflecting a sparse, irregular well network. The interpolated surface is a
**screening visualisation**, not a predictive model. Per-well
classifications rest on measured data, never on the surface.
"""
        )

# --- Data table ---
st.subheader("Screening results")
df = pd.DataFrame(
    [
        {
            "Well": r.well,
            "Province": r.province,
            "Depth (m)": r.depth_m,
            "T raw (°C)": r.t_raw_c,
            "T corrected (°C)": r.t_corrected_c,
            "Gradient (°C/km)": r.gradient_c_per_km,
            "Suitability": r.suitability.value,
            "# readings": r.n_measurements,
        }
        for r in results
    ]
)


def _highlight(row: pd.Series) -> list[str]:
    cls = SuitabilityClass(row["Suitability"])
    color = SUITABILITY_COLORS[cls]
    return [f"background-color: {color}22"] * len(row)


st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, height=420)

st.download_button(
    "Download results as CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="geothermal_screening_po_plain.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption(
    "Data: BHT archives (ViDEPI / GEOTHOPICA), corrected via Horner/Hybrid "
    "methods. Methodology and limitations documented in the repository. "
    "© Iman Saghafifar · MIT License."
)
