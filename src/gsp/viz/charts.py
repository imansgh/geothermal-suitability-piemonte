"""Plotly chart builders for the screening results.

Three figures that summarise the portfolio without overstating the data:

* a depth-temperature scatter showing every reading and the correction shift,
* a per-well corrected-temperature ranking coloured by suitability class,
* the IDW power-search curve, so the interpolation choice is visible.

All figures are pure functions of the result objects.
"""

from __future__ import annotations

import plotly.graph_objects as go

from gsp.data.models import BHTMeasurement, WellScreeningResult
from gsp.viz.maps import SUITABILITY_COLORS

__all__ = [
    "depth_temperature_scatter",
    "suitability_ranking",
    "power_search_curve",
]


def depth_temperature_scatter(measurements: list[BHTMeasurement]) -> go.Figure:
    """Depth vs temperature, showing raw and corrected readings.

    Args:
        measurements: All BHT measurements.

    Returns:
        A Plotly figure with raw and corrected series and the correction shift.

    """
    depths = [m.depth_m for m in measurements]
    t_raw = [m.t_raw_c for m in measurements]
    t_corr = [m.t_corrected_c for m in measurements]

    fig = go.Figure()
    # Correction shift lines.
    for m in measurements:
        fig.add_trace(
            go.Scatter(
                x=[m.t_raw_c, m.t_corrected_c],
                y=[m.depth_m, m.depth_m],
                mode="lines",
                line={"color": "rgba(150,150,150,0.35)", "width": 1},
                showlegend=False,
                hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=t_raw,
            y=depths,
            mode="markers",
            name="Raw BHT",
            marker={"color": "#fc8d59", "size": 7, "symbol": "circle-open"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=t_corr,
            y=depths,
            mode="markers",
            name="Corrected (Horner/Hybrid)",
            marker={"color": "#4fd1c5", "size": 8},
        )
    )
    fig.update_layout(
        title="Depth vs Temperature — BHT correction",
        xaxis_title="Temperature (\u00b0C)",
        yaxis_title="Depth (m)",
        yaxis={"autorange": "reversed"},
        template="plotly_white",
        height=520,
        legend={"x": 0.02, "y": 0.02},
    )
    return fig


def suitability_ranking(results: list[WellScreeningResult]) -> go.Figure:
    """Horizontal bar ranking of wells by corrected temperature.

    Args:
        results: Per-well screening results.

    Returns:
        A Plotly figure ranking wells, coloured by suitability class.

    """
    ordered = sorted(results, key=lambda r: r.t_corrected_c)
    wells = [r.well for r in ordered]
    temps = [r.t_corrected_c for r in ordered]
    colors = [SUITABILITY_COLORS[r.suitability] for r in ordered]

    fig = go.Figure(
        go.Bar(
            x=temps,
            y=wells,
            orientation="h",
            marker={"color": colors},
            text=[f"{t:.0f}\u00b0C" for t in temps],
            textposition="outside",
            hovertemplate="%{y}: %{x:.1f}\u00b0C<extra></extra>",
        )
    )
    # Threshold reference lines.
    for x, label in ((60, "Direct use"), (120, "Power gen.")):
        fig.add_vline(
            x=x,
            line={"color": "#888", "dash": "dash", "width": 1},
            annotation_text=label,
            annotation_position="top",
        )
    fig.update_layout(
        title="Wells ranked by corrected temperature",
        xaxis_title="Corrected temperature (\u00b0C)",
        template="plotly_white",
        height=max(420, 18 * len(results)),
        showlegend=False,
        margin={"l": 160},
    )
    return fig


def power_search_curve(sweep: list[tuple[float, float]], best_power: float) -> go.Figure:
    """LOOCV RMSE vs IDW power, marking the selected power.

    Args:
        sweep: ``(power, rmse)`` pairs from the tuning search.
        best_power: The selected power exponent.

    Returns:
        A Plotly figure of the cross-validation curve.

    """
    powers = [p for p, _ in sweep]
    rmses = [r for _, r in sweep]
    fig = go.Figure(go.Scatter(x=powers, y=rmses, mode="lines+markers", line={"color": "#4575b4"}))
    fig.add_vline(
        x=best_power,
        line={"color": "#d73027", "dash": "dash"},
        annotation_text=f"selected p={best_power:g}",
        annotation_position="top",
    )
    fig.update_layout(
        title="IDW power selection (leave-one-out CV)",
        xaxis_title="IDW power exponent",
        yaxis_title="LOOCV RMSE (\u00b0C/km)",
        template="plotly_white",
        height=380,
    )
    return fig
