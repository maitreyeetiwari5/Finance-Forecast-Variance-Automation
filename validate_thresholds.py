"""
Validation: the synthetic data has 6 scripted anomaly events baked in
(across 5 business unit / line item pairs; see generate_data.py EVENT_MONTHS) — a fuel cost spike, a hiring freeze,
a campaign overspend, etc. Because we control the ground truth here, we
can directly check whether a given set of calibrated thresholds actually
catches these known events, rather than just trusting the statistic.

This is the step that would be missing in a naive "calibrate off
historical variance and ship it" approach — the first calibration
(K=2.5) produced a Marketing threshold (48.8%) that would have MISSED
one of the two scripted Marketing overspend events (+30%). That's a
real finding, not a hypothetical: a threshold can look statistically
sound and still fail on the exact thing it exists to catch.

We sweep K down until every known event is caught, while tracking
overall flag rate so we don't just collapse to "flag everything."
"""

import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta

from calibrate_thresholds import mad_scaled, ORIGINAL_THRESHOLDS, FLOOR

FORECAST_PATH = "forecast_vs_actual.csv"
START_MONTH = date(2025, 4, 1)

# Mirrors EVENT_MONTHS in generate_data.py — converted from month index to
# actual calendar month for matching against the flagged output.
KNOWN_EVENTS_RAW = {
    ("Retail Sales", "Opex: Marketing"): [7, 14],
    ("Digital Products", "Revenue"): [10],
    ("Logistics", "Opex: Other"): [5],
    ("Enterprise Services", "Headcount Cost"): [12],
    ("Customer Support", "Opex: Salaries"): [9],
}

def known_events_df():
    rows = []
    for (bu, li), idxs in KNOWN_EVENTS_RAW.items():
        for i in idxs:
            m = (START_MONTH + relativedelta(months=i)).strftime("%Y-%m")
            rows.append({"business_unit": bu, "line_item": li, "month": m})
    return pd.DataFrame(rows)

def calibrate_with_k(df: pd.DataFrame, k: float) -> dict:
    thresholds = {}
    for line_item, grp in df.groupby("line_item"):
        median_abs = grp["variance_vs_budget_pct"].abs().median()
        scaled_mad = mad_scaled(grp["variance_vs_budget_pct"].dropna())
        thresholds[line_item] = max(median_abs + k * scaled_mad, FLOOR)
    return thresholds

def flag_rate_and_recall(df: pd.DataFrame, thresholds: dict, events: pd.DataFrame):
    df = df.copy()
    df["threshold"] = df["line_item"].map(thresholds)
    df["month"] = pd.to_datetime(df["month"]).dt.strftime("%Y-%m")
    df["flagged"] = (
        (df["variance_vs_budget_pct"].abs() > df["threshold"])
        | (df["variance_vs_forecast_pct"].abs() > df["threshold"])
    )
    flag_rate = df["flagged"].mean()

    merged = events.merge(df, on=["business_unit", "line_item", "month"], how="left")
    caught = merged["flagged"].sum()
    total_events = len(events)
    return flag_rate, caught, total_events

if __name__ == "__main__":
    df = pd.read_csv(FORECAST_PATH)
    events = known_events_df()

    print("K sweep — flag rate vs. known-event recall:\n")
    print(f"{'K':>4} | {'flag_rate':>9} | {'events_caught':>13}")
    print("-" * 34)

    best_k = None
    for k in [2.5, 2.0, 1.5, 1.2, 1.0, 0.8, 0.6]:
        thresholds = calibrate_with_k(df, k)
        flag_rate, caught, total = flag_rate_and_recall(df, thresholds, events)
        marker = ""
        if caught == total and best_k is None:
            best_k = k
            marker = "  <- smallest flag rate that still catches all known events"
        print(f"{k:>4} | {flag_rate:>8.1%} | {caught:>10}/{total}{marker}")

    print(f"\nChosen K = {best_k}")
    final_thresholds = calibrate_with_k(df, best_k)
    print("\nFinal calibrated thresholds:")
    for li, t in sorted(final_thresholds.items()):
        orig = ORIGINAL_THRESHOLDS[li]
        print(f"  {li:<20} original={orig:.0%}   calibrated={t:.1%}")
