# Scientific & Engineering Review — Geothermal Suitability (Piemonte)

**Review date:** 2026-06-25
**Scope:** Computational core (`data`, `screening`, `interpolation`, `pipeline`)
and the two capabilities added in this review (`screening.robustness`,
`data.integrity`).

This is an honest audit. Assumptions are tagged **[P]** physically justified,
**[L]** literature-derived, **[E]** engineering judgement, **[A]** arbitrary. No
scientific claims or references are invented.

---

## 1. Purpose and validity envelope

`gsp` screens *legacy hydrocarbon wells* for geothermal reuse potential from a
sparse BHT archive (31 wells, 40 readings, 834–5245 m). It is a **regional
high-grading tool**, not a resource assessment. It does not model heat-in-place,
flow rate, reservoir permeability, or economics. The design is commendably
honest about this: classification is driven by **real well readings**, and the
interpolated map is treated as a validated *claim* (LOOCV error attached) rather
than decoration. Everything below is in that context.

## 2. Assumption classification

| Assumption | Value | Tag | Notes |
|---|---|---|---|
| Governing reading = deepest per well | — | **[E]** | Best proxy for recoverable resource; defensible and documented. |
| Surface temperature | 15 °C | **[E]/[L]** | Reasonable Po-Plain mean annual air temperature; affects every gradient linearly. Should be regionally sourced. |
| Linear surface→reading gradient | — | **[P-approx]** | First-order; ignores intra-section conductivity contrasts. Adequate for screening, stated as such. |
| Power-generation gate | ≥120 °C, ≥1000 m | **[L]** | Conventional binary/ORC lower bound. |
| Direct-use gate | ≥60 °C, ≥1000 m | **[L]** | Conventional direct-use threshold. |
| GSHP gate | ≥40 °C, ≥0 m | **[E]** | The 40 °C floor is judgement; GSHP does not strictly need 40 °C, so this gate is conservative-permissive. |
| Interpolate **gradient**, not temperature | — | **[P]** | Correct: removes the dominant depth control before spatial interpolation. A genuine strength. |
| IDW as interpolator | — | **[E]** | Justified for n=31: transparent, no covariance assumptions a small set cannot support. |
| IDW power exponent | tuned by LOOCV | **data-driven** | Not arbitrary — selected by minimising cross-validated RMSE. Best practice. |
| BHT corrected-T uncertainty | 10 °C (1σ) | **[E]/[A]** | New robustness knob. Order-of-magnitude default; must be calibrated per method. Used only for fragility flags, never for the nominal class. |

**Arbitrary items to challenge first:** the 40 °C GSHP floor and the 10 °C BHT
uncertainty default. Both are isolated in `thresholds.yaml`.

## 3. The central provenance gap (and how it is now bounded)

The single most important physics step — the BHT correction from `T_raw` to
`T_corrected` (analytical / Horner / hybrid) — is performed **upstream** and
shipped in the dataset; the package reads `T_corrected_C` directly. The
methodology already states this honestly. The review does **not** reverse-
engineer or re-claim that correction (doing so without its documented inputs —
time since circulation, circulation time — would be fabricated physics).

Instead the gap is now *bounded from both sides*:

* **`data.integrity`** verifies the corrected column is internally consistent
  with how the dataset says it was built: `T_corrected_C` equals the column
  named by `correction_method` (Hybrid→`T_hyb_C`, Horner→`T_horn_C`), the
  correction never cools (`corrected ≥ raw`), values are physical, and every
  measured well has coordinates. A clean report is a reproducibility statement.
  The shipped dataset passes (asserted in tests).
* **`screening.robustness`** propagates the *residual* uncertainty of the
  corrected temperature into the classification: each well is re-classified at
  `T ± 1σ` and flagged `is_robust` only if its class is stable across the band,
  with the °C margin to the nearest depth-eligible gate reported. This is
  deterministic (no RNG) and respects the depth gates exactly.

Together these convert an opaque input into one whose consistency is checked and
whose uncertainty is surfaced at the decision boundary — the conservative,
honest treatment the rest of the package already aspires to.

## 4. Engineering review & weaknesses

| ID | Severity | Finding |
|---|---|---|
| W1 | Info | BHT correction not reproducible in-repo (provenance gap, §3). Mitigated, not closed; closing it needs the upstream correction inputs, which are not in the dataset. |
| W2 | Low | `idw_grid` is a double Python loop (O(res²·n)); fine at res=80/n=31 but would not scale. Vectorising is a clean future optimisation. |
| W3 | Low | `surface_temperature_c` is a single regional constant; a per-well elevation lapse correction (elevation is already loaded) would refine shallow gradients. |
| W4 | Info | LOOCV reports RMSE/MAE but not a spatial reliability mask threshold; `grid_nearest_km` is exposed so the dashboard *can* fade unreliable cells — worth making explicit in docs. |

Both new modules are clean under `ruff` and `mypy --strict`.

## 5. References — adequacy and gaps

The methodology cites the right conventional thresholds. Honest gaps (recommended
to add; **not** fabricated as stating any specific number):

* **Academic/standard** — BHT correction theory and residual uncertainty
  (basis for the 10 °C robustness band): the Horner-plot method and its scatter,
  e.g. AAPG *Geothermal Survey of North America* correction literature, or
  Goutorbe et al. (2007), *Comparison of BHT correction methods*. Locate and
  cite before quoting any uncertainty figure.
* **Implementation** — IDW and leave-one-out cross-validation are textbook;
  a spatial-statistics reference (e.g. Isaaks & Srivastava, *An Introduction to
  Applied Geostatistics*) should support the interpolation/validation choice.
* **Insufficient evidence** — the 40 °C GSHP floor has no single citable source;
  it is engineering judgement and is labelled as such.

## 6. Prioritised roadmap

1. **(Done)** Robustness-to-BHT-uncertainty flags + dataset-integrity checks,
   with tests and config.
2. **(Low)** Add the BHT-correction and geostatistics references (§5).
3. **(Low)** Elevation-lapse refinement of surface temperature (W3).
4. **(Low)** Vectorise `idw_grid` (W2) and document the `grid_nearest_km`
   reliability mask (W4).

## 7. Portfolio assessment

Strengths for European PhD / geothermal & digital-subsurface roles: the project
interpolates the *physically correct* quantity (gradient), validates it
(LOOCV + data-driven power), and refuses to over-claim — classification rests on
measured readings, not the surface. The added robustness and integrity layers
make the BHT-provenance limitation explicit and *bounded*, which is exactly the
kind of conservative, reproducible engineering reviewers reward. The remaining
honest gap is in-repo reproduction of the BHT correction itself, which is
correctly attributed to the upstream thesis work.
