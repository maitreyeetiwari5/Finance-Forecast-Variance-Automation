"""
Controls layer: flags variance breaches per (business_unit, line_item, month).

Thresholds are set PER LINE ITEM, not flat across the board, because a line
item's natural volatility should set the bar for what counts as "unusual."
They are calibrated from each line item's own historical variance (median +
1.2x scaled MAD) and validated against the six known scripted events; see
calibrate_thresholds.py, validate_thresholds.py, and METHODOLOGY.md. The
values below are the output of that validated calibration.

A row is flagged if EITHER:
  - variance_vs_budget_pct breaches the line item's threshold   (a real
    over/underspend against plan), OR
  - variance_vs_forecast_pct breaches the line item's threshold  (a
    surprise relative to recent trend, even if budget itself was loose)

Both are checked independently so the flag reason is always traceable
back to a specific metric, not a blended score.
"""

import pandas as pd

IN_PATH = "forecast_vs_actual.csv"
OUT_PATH = "flagged_variances.csv"

# Materiality thresholds per line item (absolute % variance)
#
# CALIBRATED from historical variance distribution using a robust
# statistic (median + 1.2x scaled MAD — see calibrate_thresholds.py and
# validate_thresholds.py). K=1.2 was chosen by sweeping against 6 known
# scripted anomalies in the data: it's the smallest K that still catches
# all 6, cutting the overall flag rate from 34.8% (original hardcoded
# thresholds) to 12.8% without missing a real event. A naive K=2.5 pass
# only caught 4/6 — pooled historical noise pushed some thresholds above
# the magnitude of real anomalies, which is why recall was checked
# against ground truth rather than trusting the statistic alone.
THRESHOLDS = {
    "Revenue":          0.112,
    "COGS":             0.084,
    "Opex: Marketing":  0.285,
    "Opex: Salaries":   0.071,
    "Opex: Other":      0.163,
    "Headcount Cost":   0.075,
}

def flag_variances(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["threshold"] = df["line_item"].map(THRESHOLDS)

    df["budget_breach"] = df["variance_vs_budget_pct"].abs() > df["threshold"]

    # forecast_breach only applies where a forecast exists (first 3 months
    # of each series have none)
    df["forecast_breach"] = (
        df["variance_vs_forecast_pct"].notna()
        & (df["variance_vs_forecast_pct"].abs() > df["threshold"])
    )

    df["flagged"] = df["budget_breach"] | df["forecast_breach"]

    def reason(row):
        reasons = []
        if row["budget_breach"]:
            direction = "over" if row["variance_vs_budget_pct"] > 0 else "under"
            reasons.append(f"{abs(row['variance_vs_budget_pct']):.0%} {direction} budget")
        if row["forecast_breach"]:
            direction = "above" if row["variance_vs_forecast_pct"] > 0 else "below"
            reasons.append(f"{abs(row['variance_vs_forecast_pct']):.0%} {direction} trend forecast")
        return "; ".join(reasons) if reasons else ""

    df["flag_reason"] = df.apply(reason, axis=1)
    return df

if __name__ == "__main__":
    raw = pd.read_csv(IN_PATH)
    result = flag_variances(raw)
    result.to_csv(OUT_PATH, index=False)

    flagged = result[result["flagged"]]
    print(f"Wrote {len(result)} rows to {OUT_PATH}")
    print(f"{len(flagged)} of {len(result)} rows flagged ({len(flagged)/len(result):.1%})\n")

    print("Breakdown by line item:")
    print(
        result.groupby("line_item")["flagged"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "flagged", "count": "total"})
    )

    print("\nSample flagged rows:")
    cols = ["business_unit", "line_item", "month", "variance_vs_budget_pct",
            "variance_vs_forecast_pct", "flag_reason"]
    print(flagged[cols].head(10).to_string(index=False))
