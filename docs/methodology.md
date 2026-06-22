# Methodology

This document records the modelling choices, assumptions, and limitations of
the geothermal suitability screening so that a reviewer can evaluate — and,
where necessary, override — each one. Every numeric threshold is externalised
in [`../src/gsp/screening/thresholds.yaml`](../src/gsp/screening/thresholds.yaml).

---

## 1. From readings to a per-well temperature

A single well may carry several BHT readings at different depths. The screening
uses the **deepest reading** as the governing value, because it best
represents the temperature of the deepest — and thermally most valuable —
interval reachable in a reuse scenario. Shallower readings are retained for the
depth–temperature profile shown in the map popups and the scatter chart, but
they do not drive the classification.

The package consumes **already-corrected** temperatures (Horner where multiple
build-up readings exist, hybrid otherwise). It does not re-derive the BHT
correction; that derivation belongs to the upstream thesis work and is treated
here as an input.

---

## 2. Apparent geothermal gradient

The apparent gradient is

```
gradient [°C/km] = (T_corrected − T_surface) / (depth / 1000)
```

with `T_surface = 15 °C` by default. This is a **first-order** estimate: it
assumes a single linear profile from surface to the reading depth and does not
resolve gradient variation between lithological units. It is adequate for
regional screening and for normalising temperature against depth prior to
spatial interpolation, but it is not a substitute for a measured continuous
temperature log.

---

## 3. Suitability classification

A well is assigned the highest-grade class whose **temperature and depth** gates
it satisfies:

| Class | Temperature | Depth | Rationale |
|---|---|---|---|
| Power Generation | ≥ 120 °C | ≥ 1000 m | Binary/ORC power becomes plausible |
| Direct Use | ≥ 60 °C | ≥ 1000 m | District heating, industrial/agricultural heat |
| Ground-Source Heat Pump | ≥ 40 °C | any | Heat-pump-assisted low-temperature use |
| Below Threshold | < 40 °C | — | Not attractive for the above |

These bands follow conventional low-enthalpy geothermal practice. They are
deliberately coarse: the goal is to **rank and triage** a portfolio, not to
certify any single well.

---

## 4. Spatial interpolation — and why it is interpreted cautiously

### Interpolate the gradient, not the temperature

Raw temperature is dominated by depth. With wells spanning 834–5245 m,
interpolating temperature directly mixes shallow-cool and deep-hot wells and
produces a physically meaningless surface (leave-one-out RMSE ≈ 28 °C, ~25 % of
the data range). Interpolating the **depth-normalised gradient** removes this
confound; a predicted temperature at any reference depth then follows from
`T = T_surface + gradient × depth`.

### Inverse-distance weighting with a cross-validated power

Inverse-distance weighting (IDW) is used because it is transparent and makes no
covariance assumptions that 31 irregularly spaced points cannot support. The
power exponent is **not** hard-coded: it is chosen by minimising leave-one-out
cross-validation (LOOCV) RMSE over a sweep of candidates. Distances use the
haversine (great-circle) formula so weighting stays physically meaningful across
the study area.

### Honest error reporting

LOOCV gives a gradient RMSE of **≈ 3.5 °C/km**. This is comparable to the
gradient's own spatial standard deviation (≈ 3.5 °C/km), which is the key honest
finding: **the sparse, irregular well network resolves little spatial structure
beyond the regional mean.** Consequently:

- The interpolated surface is presented as a **screening visualisation**, never
  as a predictive model.
- Per-well classifications rest entirely on **measured** data, never on the
  interpolated surface.
- On the map, cells beyond ~15 km from any well are progressively faded and
  cells beyond ~45 km are essentially transparent, so the figure never implies
  confidence where there is no data.

---

## 5. Limitations

- **Sparse, biased sampling.** Wells were sited for hydrocarbon exploration,
  not geothermal characterisation; their spatial distribution is irregular and
  clustered (e.g. the Trecate area).
- **Single-gradient assumption.** A linear surface-to-depth gradient ignores
  thermal-conductivity contrasts between the Quaternary–Pliocene clastics and
  the deeper Miocene/Oligocene marls and evaporites recorded in the
  litho-stratigraphy.
- **No permeability or flow.** Suitability here is thermal only. Reservoir
  productivity (permeability, transmissivity, sustainable flow rate) — which
  ultimately governs whether heat can be extracted — is **not** modelled.
- **No reservoir-engineering or economic screen.** Drilling cost, existing
  well integrity, surface infrastructure, and demand proximity are out of
  scope. (Well-integrity screening is addressed by a companion project, LWRA.)
- **Correction inherited, not validated here.** The accuracy of the underlying
  Horner/hybrid corrections is documented in the source thesis and is taken as
  given.

These limitations are why the deliverable is framed as a screening and triage
tool that points to where a detailed, data-rich feasibility study would be
worth commissioning — not as a statement that any specific well is
geothermally viable.
