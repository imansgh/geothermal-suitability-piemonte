"""Interactive Folium map of well screening results and the gradient field.

Renders the screened wells as colour-coded markers and overlays the
interpolated geothermal-gradient surface as a faded raster image. Cells far
from any control well are made progressively transparent so the map never
implies confidence where there is no data — the visual encodes the LOOCV
caveat directly.
"""

from __future__ import annotations

import base64
import io

import folium
import numpy as np

from gsp.data.models import SuitabilityClass, WellScreeningResult
from gsp.interpolation.field import GradientField

__all__ = ["SUITABILITY_COLORS", "build_map"]

SUITABILITY_COLORS: dict[SuitabilityClass, str] = {
    SuitabilityClass.POWER_GENERATION: "#d73027",
    SuitabilityClass.DIRECT_USE: "#fc8d59",
    SuitabilityClass.GROUND_SOURCE_HP: "#fee08b",
    SuitabilityClass.BELOW_THRESHOLD: "#4575b4",
}

SUITABILITY_RADIUS: dict[SuitabilityClass, int] = {
    SuitabilityClass.POWER_GENERATION: 16,
    SuitabilityClass.DIRECT_USE: 12,
    SuitabilityClass.GROUND_SOURCE_HP: 9,
    SuitabilityClass.BELOW_THRESHOLD: 7,
}


def _gradient_overlay_png(field: GradientField, depth_m: float) -> tuple[str, list[list[float]]]:
    """Render the predicted-T grid to a translucent PNG data URI.

    Cells beyond a support distance fade out, so the overlay visually
    de-emphasises poorly-constrained regions.

    Args:
        field: The interpolated gradient field.
        depth_m: Reference depth for the predicted-T surface.

    Returns:
        ``(data_uri, bounds)`` where bounds is ``[[south, west], [north, east]]``.

    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.colors as mcolors
    from matplotlib import colormaps
    temp = field.predicted_temperature(depth_m)
    # Normalise to a fixed, interpretable range for direct-use screening.
    norm = mcolors.Normalize(vmin=30.0, vmax=150.0)
    cmap = colormaps["inferno"]
    rgba = cmap(norm(temp))

    # Fade by support: full alpha within 15 km, transparent beyond 45 km.
    near = field.grid_nearest_km
    alpha = np.clip(1.0 - (near - 15.0) / 30.0, 0.0, 0.78)
    rgba[..., 3] = alpha

    # Flip vertically: image origin is top-left, grid origin is bottom-left.
    img = (rgba[::-1] * 255).astype(np.uint8)

    from PIL import Image

    pil = Image.fromarray(img, mode="RGBA")
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    bounds = [
        [float(field.grid_lat.min()), float(field.grid_lon.min())],
        [float(field.grid_lat.max()), float(field.grid_lon.max())],
    ]
    return uri, bounds


def build_map(
    results: list[WellScreeningResult],
    field: GradientField | None = None,
    *,
    reference_depth_m: float = 2000.0,
    all_measurements: dict[str, list[tuple[float, float, float]]] | None = None,
) -> folium.Map:
    """Build the interactive screening map.

    Args:
        results: Per-well screening results.
        field: Optional interpolated gradient field to overlay.
        reference_depth_m: Reference depth for the predicted-T overlay.
        all_measurements: Optional mapping of well -> list of
            ``(depth_m, t_raw_c, t_corrected_c)`` for the popup profile table.

    Returns:
        A configured :class:`folium.Map`.

    """
    center_lat = float(np.mean([r.lat for r in results]))
    center_lon = float(np.mean([r.lon for r in results]))
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles=None)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB Dark Matter",
        name="Dark",
        max_zoom=19,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB Positron",
        name="Light",
        max_zoom=19,
    ).add_to(m)
    folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap").add_to(m)

    # Gradient overlay (faded by support distance).
    if field is not None:
        uri, bounds = _gradient_overlay_png(field, reference_depth_m)
        folium.raster_layers.ImageOverlay(
            image=uri,
            bounds=bounds,
            opacity=1.0,
            name=f"Predicted T @ {reference_depth_m:.0f} m (IDW, faded by support)",
            interactive=False,
            cross_origin=False,
        ).add_to(m)

    # Well markers.
    fg = folium.FeatureGroup(name="Wells (screened)", show=True)
    for r in results:
        color = SUITABILITY_COLORS[r.suitability]
        radius = SUITABILITY_RADIUS[r.suitability]
        profile_rows = ""
        if all_measurements and r.well in all_measurements:
            for depth, t_raw, t_corr in sorted(all_measurements[r.well]):
                profile_rows += (
                    f"<tr><td style='padding:2px 8px;color:#aaa'>{depth:.0f} m</td>"
                    f"<td style='padding:2px 8px;color:#fc8d59'>{t_raw:.1f}&deg;C</td>"
                    f"<td style='padding:2px 8px;color:#4fd1c5'>{t_corr:.1f}&deg;C</td></tr>"
                )
        profile_block = ""
        if profile_rows:
            profile_block = (
                "<div style='font-size:11px;color:#aaa;margin:8px 0 4px'>All readings:</div>"
                "<table style='width:100%;border-collapse:collapse;font-size:11px'>"
                "<tr style='color:#666'><th style='text-align:left;padding:2px 8px'>Depth</th>"
                "<th style='padding:2px 8px'>T raw</th><th style='padding:2px 8px'>T corr.</th></tr>"
                f"{profile_rows}</table>"
            )

        popup = folium.Popup(
            f"""
            <div style="font-family:monospace;background:#1a1a2e;color:#eee;padding:14px;
                 border-radius:8px;min-width:270px;font-size:12px">
              <div style="font-size:14px;font-weight:bold;color:#fff;margin-bottom:6px">{r.well}</div>
              <span style="display:inline-block;background:{color};color:#111;padding:2px 10px;
                    border-radius:20px;font-size:11px;font-weight:bold;margin-bottom:10px">
                {r.suitability.value}
              </span>
              <table style="width:100%;border-collapse:collapse">
                <tr><td style="color:#aaa;padding:2px 0">Depth (governing)</td>
                    <td style="color:#fff;text-align:right">{r.depth_m:.0f} m</td></tr>
                <tr><td style="color:#aaa;padding:2px 0">T corrected</td>
                    <td style="color:#4fd1c5;text-align:right;font-weight:bold">{r.t_corrected_c:.1f}&deg;C</td></tr>
                <tr><td style="color:#aaa;padding:2px 0">T raw</td>
                    <td style="color:#fc8d59;text-align:right">{r.t_raw_c:.1f}&deg;C</td></tr>
                <tr><td style="color:#aaa;padding:2px 0">Gradient</td>
                    <td style="color:#fff;text-align:right">{r.gradient_c_per_km:.1f}&deg;C/km</td></tr>
                <tr><td style="color:#aaa;padding:2px 0">Province</td>
                    <td style="color:#fff;text-align:right">{r.province}</td></tr>
              </table>
              {profile_block}
            </div>
            """,
            max_width=320,
        )

        folium.CircleMarker(
            location=[r.lat, r.lon],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.88,
            weight=2,
            popup=popup,
            tooltip=f"{r.well} | {r.t_corrected_c:.1f}\u00b0C | {r.suitability.value}",
        ).add_to(fg)
    fg.add_to(m)

    _add_legend(m, results, field, reference_depth_m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def _add_legend(
    m: folium.Map,
    results: list[WellScreeningResult],
    field: GradientField | None,
    reference_depth_m: float,
) -> None:
    """Attach the suitability legend and validation note to the map."""
    from collections import Counter

    counts = Counter(r.suitability for r in results)
    cv_note = ""
    if field is not None:
        cv_note = (
            f"<hr style='border-color:#444;margin:8px 0'>"
            f"<div style='font-size:10px;color:#aaa'>"
            f"Overlay: predicted T @ {reference_depth_m:.0f} m from IDW gradient "
            f"(power {field.best_power:g}).<br>"
            f"LOOCV gradient RMSE {field.loocv_rmse_c_per_km:g} &deg;C/km. "
            f"Cells far from wells are faded.</div>"
        )

    rows = ""
    for cls in SuitabilityClass:
        rows += (
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:5px'>"
            f"<div style='width:13px;height:13px;border-radius:50%;"
            f"background:{SUITABILITY_COLORS[cls]};flex-shrink:0'></div>"
            f"<span>{cls.value} ({counts.get(cls, 0)})</span></div>"
        )

    html = f"""
    <div style="position:fixed;bottom:28px;left:28px;z-index:1000;background:rgba(20,20,30,0.93);
         border:1px solid #444;border-radius:10px;padding:14px 18px;font-family:monospace;
         color:#eee;font-size:12px;min-width:240px;box-shadow:0 4px 20px rgba(0,0,0,0.5)">
      <div style="font-size:13px;font-weight:bold;margin-bottom:10px;color:#fff">
        Geothermal Suitability
      </div>
      {rows}
      {cv_note}
      <hr style="border-color:#444;margin:8px 0">
      <div style="font-size:10px;color:#aaa">
        {len(results)} legacy wells &middot; Po Plain, Piemonte<br>
        BHT corrected (Horner / Hybrid)<br>
        Screening aid, not a feasibility study.
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))  # type: ignore[attr-defined]
