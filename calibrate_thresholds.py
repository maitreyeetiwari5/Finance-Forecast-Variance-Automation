"""
Threshold calibration: learn each line item's natural variance behavior
from its own history, rather than relying solely on hardcoded materiality
conventions.

Why MAD (median absolute deviation) instead of mean/std:
Standard deviation is pulled around by the very outlier months we're
trying to detect (the scripted events). A handful of large variances
inflates std, which would make the resulting threshold MORE permissive
on exactly the line items with real anomalies — the opposite of what we
want. MAD is a robust statistic: it isn't distorted by a small number of
extreme points, so it reflects "typical" variance more honestly.

new_threshold = median(|variance_pct|) + K * MAD_scaled

MAD_scaled = MAD * 1.4826  (the 1.4826 factor makes MAD comparable to a
standard deviation under a normal distribution, a standard convention)

K = 2.5 is the first-pass cutoff: roughly "notably outside typical behavior"
without being so tight that ordinary noise months keep tripping it.
NOTE: this first pass caught only 4 of the 6 known events. validate_thresholds.py
sweeps K and selects K = 1.2 as the final value used in controls.py.
threshold_calibration.csv is kept as the record of this rejected first pass.

We floor every calibrated threshold at 4% — below that, we'd be flagging
essentially every month for even the steadiest line items, which stops
being a useful control and starts being noise itself.
"""

import pandas as pd
import numpy as np

FORECAST_PATH = "forecast_vs_actual.csv"

ORIGINAL_THRESHOLDS = {
    "Revenue":          0.05,
    "COGS":             0.05,
    "Opex: Marketing":  0.15,
    "Opex: Salaries":   0.05,
    "Opex: Other":      0.12,
    "Headcount Cost":   0.06,
}

K = 2.5
FLOOR = 0.04

def mad_scaled(series: pd.Series) -> float:
    med = series.median()
    mad = (series - med).abs().median()
    return mad * 1.4826

def calibrate(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for line_item, grp in df.groupby("line_item"):
        vb = grp["variance_vs_budget_pct"].abs().dropna()
        median_abs = vb.median()
        scaled_mad = mad_scaled(grp["variance_vs_budget_pct"].dropna())
        raw_threshold = median_abs + K * scaled_mad
        calibrated = max(raw_threshold, FLOOR)

        rows.append({
            "line_item": line_item,
            "original_threshold": ORIGINAL_THRESHOLDS[line_item],
            "median_abs_variance": round(median_abs, 4),
            "mad_scaled": round(scaled_mad, 4),
            "calibrated_threshold_raw": round(raw_threshold, 4),
            "calibrated_threshold": round(calibrated, 4),
        })
    return pd.DataFrame(rows).sort_values("line_item")

if __name__ == "__main__":
    df = pd.read_csv(FORECAST_PATH)
    table = calibrate(df)
    print(table.to_string(index=False))
    table.to_csv("threshold_calibration.csv", index=False)
    print("\nWrote threshold_calibration.csv")
