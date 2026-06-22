# Geothermal Suitability Screening — Po Plain (Piemonte)

[![CI](https://github.com/imansgh/geothermal-suitability-piemonte/actions/workflows/tests.yml/badge.svg)](https://github.com/imansgh/geothermal-suitability-piemonte/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Screening of **legacy hydrocarbon wells** for **geothermal reuse** in the
Piemonte sector of the Po Plain, Italy, built from **bottom-hole-temperature
(BHT) archives** and Horner/hybrid temperature corrections.

The workflow turns a sparse set of decades-old exploration-well temperature
readings into a transparent, validated geothermal screening: per-well
suitability classes, an interactive map, and a spatial gradient surface whose
prediction error is quantified and openly reported.

> **Scope.** This is a regional **screening aid**, not a site-specific
> geothermal feasibility study. Every classification threshold is externalised
> and documented; the interpolated surface always carries its cross-validation
> error so a reader can judge where it can and cannot be trusted.

---

## What it produces

```
BHT archive (raw + Horner/Hybrid corrected, per depth)
  + well coordinates (WGS84)
        │
        ├─► per-well screening   deepest reading → gradient → suitability class
        │       └─ Power Generation · Direct Use · Ground-Source HP · Below Threshold
        │
        ├─► spatial gradient field   LOOCV-tuned inverse-distance weighting
        │       └─ predicted-T surface at a chosen reference depth, faded by data support
        │
        └─► interactive map · ranking chart · depth–T scatter · validation report
```

---

## Headline results (31 wells)

| Suitability class | Wells | Criteria |
|---|---|---|
| 🔴 Power Generation | 2 | T ≥ 120 °C and depth ≥ 1000 m |
| 🟠 Direct Use | 17 | 60 ≤ T < 120 °C and depth ≥ 1000 m |
| 🟡 Ground-Source Heat Pump | 9 | 40 ≤ T < 60 °C |
| 🔵 Below Threshold | 3 | T < 40 °C |

Hottest wells: **SALI VERCELLESE 1** (140 °C @ 4743 m) and **VOLPEDO 4**
(124 °C @ 5245 m). Apparent gradients cluster around **21.5 ± 3.5 °C/km**,
consistent with a continental foreland-basin setting.

The spatial interpolation is performed on the **geothermal gradient**
(depth-normalised), not on raw temperature, because temperature is dominated by
depth across wells spanning 834–5245 m. Leave-one-out cross-validation gives a
gradient RMSE of **≈ 3.5 °C/km** — comparable to the gradient's own spatial
spread, which honestly reflects the limited spatial structure a sparse,
irregular network can resolve.

---

## Install

```bash
# Full environment (recommended)
pip install -e ".[all,dev]"

# Subsets
pip install -e "."             # core: loading, screening, interpolation
pip install -e ".[viz]"        # + folium / plotly / matplotlib figures
pip install -e ".[dashboard]"  # + Streamlit dashboard
```

> Core requires only `pydantic`, `PyYAML`, `pandas`, `numpy`, `openpyxl`.

---

## Quick start

### Command line

```bash
gsp screen                                   # ranked table + class summary
gsp screen --csv results.csv                 # also write results to CSV
gsp map --out map.html --depth 2000          # interactive map (predicted-T @ 2000 m)
gsp validate                                 # interpolation LOOCV report
```

### Python

```python
from gsp.pipeline import run_pipeline

out = run_pipeline(interpolate=True)
for r in out.results[:3]:
    print(r.well, r.t_corrected_c, r.suitability.value)

print("LOOCV gradient RMSE:", out.field.loocv_rmse_c_per_km, "°C/km")
```

### Interactive dashboard

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```
## Repository structure

```text
geothermal-suitability-piemonte/

├── src/gsp/
│   ├── data/              # Pydantic models and validated loaders
│   ├── screening/         # suitability engine and thresholds
│   ├── interpolation/    # IDW, LOOCV and gradient field
│   ├── viz/              # Folium maps and Plotly figures
│   ├── cli/              # command-line interface
│   └── pipeline.py       # orchestration layer
│
├── dashboard/            # Streamlit application
├── datasets/             # canonical BHT and coordinate tables
├── notebooks/            # reproducible walkthroughs
├── tests/                # pytest suite
├── docs/                 # methodology, assumptions and limitations
└── .github/workflows/    # CI
```

The package is organised around a small set of independent modules. Screening logic, interpolation, visualisation and user interfaces are separated to preserve transparency, reproducibility and ease of maintenance.

```

## Methodology

1. **Governing reading.** For each well, the **deepest** BHT measurement is
   taken as most representative of the recoverable thermal resource.
2. **Correction.** Temperatures are the Horner-corrected value where multiple
   readings allow it, otherwise the hybrid-corrected value (see the BHT source
   work). The package consumes already-corrected temperatures; it does not
   re-derive the correction.
3. **Gradient.** An apparent geothermal gradient is computed as
   `(T_corrected − T_surface) / depth`, with `T_surface = 15 °C` (configurable).
4. **Classification.** A well is assigned the highest-grade class whose
   temperature **and** depth gates it satisfies. All gates live in
   [`thresholds.yaml`](src/gsp/screening/thresholds.yaml).
5. **Spatial field.** The gradient field is interpolated by inverse-distance
   weighting; the power exponent is selected by minimising leave-one-out RMSE.
   A predicted-temperature surface at a chosen reference depth follows from
   `T = T_surface + gradient × depth`.
6. **Honest visualisation.** Map cells far from any well are progressively
   faded, and the LOOCV error is printed alongside every surface.

Full assumptions and limitations: [`docs/methodology.md`](docs/methodology.md).

---

## Data

Two canonical tables in [`datasets/`](datasets/):

- `bht_measurements.csv` — one row per BHT reading: well, depth, raw and
  corrected temperature, correction method.
- `well_coordinates.csv` — WGS84 coordinates, province, and elevation per well.

Source: BHT archives and well headers compiled from **ViDEPI** and
**GEOTHOPICA** public records for Piemonte. Corrected temperatures originate
from my MSc thesis on reusing legacy BHT archives for geothermal screening in
the Po Plain.

---

## Tests & quality

```bash
pytest                # full suite
pytest --cov=gsp      # with coverage
ruff check src tests  # lint
mypy src/gsp          # strict type check
```

CI runs on Python 3.12 and 3.13.

---
## Future work

- Uncertainty-aware interpolation
- Additional geothermal datasets
- Integration with legacy well integrity assessments
- Coupling with CO₂ storage screening workflows

  ---
## License

MIT — see [`LICENSE`](LICENSE). Data records are derived from public sources
(ViDEPI / GEOTHOPICA); please cite those archives and this repository if you
reuse the screening.
