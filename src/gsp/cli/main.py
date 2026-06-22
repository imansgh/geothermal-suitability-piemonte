"""Command-line interface for the geothermal screening workflow.

Usage::

    gsp screen                       # print ranked table + class summary
    gsp screen --csv out.csv         # also write results to CSV
    gsp map --out map.html           # build the interactive map
    gsp validate                     # print interpolation LOOCV report

Kept deliberately small: it is a thin wrapper over ``gsp.pipeline`` so the CLI
and the dashboard always exercise the same code path.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from gsp.pipeline import run_pipeline

__all__ = ["main"]


def _cmd_screen(args: argparse.Namespace) -> int:
    out = run_pipeline(interpolate=False)
    results = out.results

    width = max(len(r.well) for r in results)
    print(f"{'Well':<{width}}  {'T_corr':>7}  {'Depth':>7}  {'Grad':>6}  Suitability")
    print("-" * (width + 40))
    for r in results:
        print(
            f"{r.well:<{width}}  {r.t_corrected_c:>6.1f}C  {r.depth_m:>6.0f}m  "
            f"{r.gradient_c_per_km:>5.1f}  {r.suitability.value}"
        )

    from collections import Counter

    counts = Counter(r.suitability.value for r in results)
    print("\nClass summary:")
    for cls, n in counts.most_common():
        print(f"  {cls:<26} {n}")

    if args.csv:
        path = Path(args.csv)
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "well",
                    "lat",
                    "lon",
                    "province",
                    "depth_m",
                    "t_raw_c",
                    "t_corrected_c",
                    "gradient_c_per_km",
                    "suitability",
                    "n_measurements",
                ]
            )
            for r in results:
                w.writerow(
                    [
                        r.well,
                        r.lat,
                        r.lon,
                        r.province,
                        r.depth_m,
                        r.t_raw_c,
                        r.t_corrected_c,
                        r.gradient_c_per_km,
                        r.suitability.value,
                        r.n_measurements,
                    ]
                )
        print(f"\nWrote {len(results)} rows to {path}")
    return 0


def _cmd_map(args: argparse.Namespace) -> int:
    from gsp.viz.maps import build_map

    out = run_pipeline(interpolate=True, grid_resolution=args.resolution)
    all_meas: dict[str, list[tuple[float, float, float]]] = {}
    for m in out.measurements:
        all_meas.setdefault(m.well, []).append((m.depth_m, m.t_raw_c, m.t_corrected_c))

    fmap = build_map(
        out.results,
        out.field,
        reference_depth_m=args.depth,
        all_measurements=all_meas,
    )
    path = Path(args.out)
    fmap.save(str(path))
    print(f"Saved map to {path}")
    if out.field is not None:
        print(
            f"Interpolation: IDW power {out.field.best_power:g}, "
            f"LOOCV gradient RMSE {out.field.loocv_rmse_c_per_km:g} C/km"
        )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    out = run_pipeline(interpolate=True)
    if out.power_search is None or out.field is None:
        print("Interpolation not available (too few wells).")
        return 1
    ps = out.power_search
    print("IDW power search (leave-one-out CV on geothermal gradient):")
    for p, rmse in ps.sweep:
        marker = "  <-- selected" if p == ps.best_power else ""
        print(f"  power {p:>4.1f}   RMSE {rmse:>6.2f} C/km{marker}")
    print(
        f"\nSelected power {ps.best_power:g}: "
        f"RMSE {out.field.loocv_rmse_c_per_km:g} C/km, "
        f"MAE {out.field.loocv_mae_c_per_km:g} C/km, n={ps.best.n}"
    )
    print(
        "\nNote: the gradient field's RMSE is comparable to the gradient's own "
        "spatial spread, reflecting a sparse, irregular well network. The "
        "interpolated surface is a screening visualisation, not a predictive "
        "model; per-well classifications rest on measured data, not the surface."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv``).

    Returns:
        Process exit code.

    """
    parser = argparse.ArgumentParser(
        prog="gsp",
        description="Geothermal suitability screening for Po Plain legacy wells.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_screen = sub.add_parser("screen", help="Print the ranked screening table.")
    p_screen.add_argument("--csv", help="Optional output CSV path.")
    p_screen.set_defaults(func=_cmd_screen)

    p_map = sub.add_parser("map", help="Build the interactive HTML map.")
    p_map.add_argument("--out", default="geothermal_map.html", help="Output HTML path.")
    p_map.add_argument("--depth", type=float, default=2000.0, help="Reference depth (m).")
    p_map.add_argument("--resolution", type=int, default=80, help="Grid resolution.")
    p_map.set_defaults(func=_cmd_map)

    p_val = sub.add_parser("validate", help="Print interpolation LOOCV report.")
    p_val.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
