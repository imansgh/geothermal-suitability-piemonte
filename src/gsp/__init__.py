"""Geothermal Suitability screening for the Piemonte sector of the Po Plain.

A reproducible, data-driven workflow that screens legacy hydrocarbon wells for
geothermal reuse potential using bottom-hole-temperature (BHT) archives,
Horner/hybrid temperature corrections, and a transparent multi-criteria
suitability classification.

The package is deliberately conservative: every classification threshold is
externalised and documented, the spatial interpolation reports a
leave-one-out cross-validation (LOOCV) error, and no result is presented
without its quantified uncertainty. It is a screening aid, not a substitute
for site-specific geothermal feasibility study.
"""

__version__ = "0.1.0"
