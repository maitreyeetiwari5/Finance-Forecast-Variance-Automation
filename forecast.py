"""
Rolling forecast logic.

Method: trailing 3-month moving average of ACTUALS, used to forecast
the next month. This is deliberately simple and auditable — the kind
of method an FP&A team can explain to stakeholders without a black box.

For each (business_unit, line_item, month):
- forecast[t]        = mean(actual[t-3], actual[t-2], actual[t-1])
- variance_vs_budget = actual[t] - budget[t]           (the classic FP&A number)
- variance_vs_fcst   = actual[t] - forecast[t]          (how well our model tracks reality)
- variance_pct       = variance_vs_budget / budget[t]

The first 3 months of each series have no forecast (not enough trailing
history) and are excluded from forecast comparison, but still carry
budget/actual variance.
"""

import pandas as pd

IN_PATH = "budget_vs_actuals.csv"
OUT_PATH = "forecast_vs_actual.csv"

WINDOW = 3  # trailing months used for the moving average

def build_forecast(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["month"] = pd.to_datetime(df["month"])
    df.sort_values(["business_unit", "line_item", "month"], inplace=True)

    # Forecast for month t = mean of actuals in the WINDOW months strictly
    # before t, computed independently within each (business_unit, line_item)
    # series so history never leaks across series.
    #
    # transform() (not groupby().apply()+reset_index(drop=True)) guarantees
    # the result stays aligned to df's original index — apply() returns a
    # Series ordered by group key, and reset_index(drop=True) would then
    # assign values back positionally, silently mismatching rows if group
    # order ever diverged from row order.
    df["forecast"] = df.groupby(["business_unit", "line_item"])["actual"].transform(
        lambda s: s.shift(1).rolling(window=WINDOW, min_periods=WINDOW).mean()
    )

    df["variance_vs_budget"] = df["actual"] - df["budget"]
    df["variance_vs_budget_pct"] = df["variance_vs_budget"] / df["budget"]

    df["variance_vs_forecast"] = df["actual"] - df["forecast"]
    df["variance_vs_forecast_pct"] = df["variance_vs_forecast"] / df["forecast"]

    return df

if __name__ == "__main__":
    raw = pd.read_csv(IN_PATH)
    result = build_forecast(raw)
    result.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(result)} rows to {OUT_PATH}\n")

    # Quick sanity check: forecast accuracy overall (mean absolute % error,
    # only where forecast exists)
    valid = result.dropna(subset=["forecast"])
    # Standard MAPE: |actual - forecast| / actual
    mape = ((valid["actual"] - valid["forecast"]).abs() / valid["actual"].abs()).mean() * 100
    print(f"Overall forecast MAPE (moving-average model): {mape:.1f}%")

    # Show one full series so the mechanics are inspectable
    sample = result[
        (result["business_unit"] == "Retail Sales") & (result["line_item"] == "Opex: Marketing")
    ][["month", "budget", "actual", "forecast", "variance_vs_budget_pct"]]
    print("\nSample series — Retail Sales / Opex: Marketing (note the two scripted overspend months):")
    print(sample.to_string(index=False))
