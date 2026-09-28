# Finance Forecast & Variance Automation

An end-to-end FP&A automation prototype: rolling forecasts, self-calibrating variance thresholds, and auto-drafted close commentary built to demonstrate what automating the mechanical parts of monthly variance review looks like, without faking the parts that need human judgment.

**[Live dashboard](https://maitreyeetiwari5.github.io/Finance-Forecast-Variance-Automation
/)** - filter by business unit and line item to see the forecast, flagged variances, and drafted commentary update together.

**[Excel workbook](fpa_variance_analysis.xlsx)** - the same analysis as a 3-sheet report (Summary, Variance Detail, Action Items) for anyone who wants it in Excel.

**[Methodology, assumptions & limitations](METHODOLOGY.md)** - how every number is produced, the full threshold calibration trail, a data dictionary for each output file, and where the approach stops being reliable.

## Problem

Monthly variance review doesn't scale by adding headcount. Reviewing budget-vs-actual across dozens of line items each month means either hours of manual scanning, or a single flat threshold that over-flags noisy categories (campaign-driven marketing spend) while missing real issues in stable ones (salaries, where even a small deviation matters).

The mechanical parts: detecting what changed, judging materiality, drafting a first-pass explanation are a good fit for automation. The judgment of *why* something changed is not, and this project doesn't pretend otherwise.

## Pipeline

Run in order:

| Step | Script | Output |
| --- | --- | --- |
| 1 | `generate_data.py` | `budget_vs_actuals.csv` - synthetic monthly budget/actuals, 5 business units × 6 line items × 18 months, with 6 scripted anomaly events |
| 2 | `forecast.py` | `forecast_vs_actual.csv` - trailing 3-month moving-average forecast per series |
| 3 | `calibrate_thresholds.py` | `threshold_calibration.csv` - robust (median + MAD) threshold calibration per line item |
| 4 | `validate_thresholds.py` | K-sweep validated against the 6 known scripted events (console output) |
| 5 | `controls.py` | `flagged_variances.csv` - variance flags using calibrated thresholds, dual-triggered on budget and forecast variance |
| 6 | `commentary.py` (+ `event_log.py`) | `commentary_draft.csv` - auto-drafted commentary; known drivers pulled from the event log, unknowns routed for analyst review |
| 7 | `build_dashboard.py` | `dashboard/index.html` - the published dashboard |
| 8 | `export_excel.py` | `fpa_variance_analysis.xlsx` - a 3-sheet Excel deliverable (Summary / Variance Detail / Action Items) |

```bash
pip install -r requirements.txt
python generate_data.py
python forecast.py
python calibrate_thresholds.py
python validate_thresholds.py
python controls.py
python commentary.py
python build_dashboard.py
python export_excel.py
```

## Key design choices

- **Forecast method:** a trailing 3-month moving average, chosen over a more complex model specifically for auditability, any FP&A stakeholder can reconstruct the number by hand.
- **Threshold calibration:** thresholds are learned per line item from historical variance (median + scaled MAD, robust to the outliers it's meant to catch), then validated against 6 known ground-truth anomalies rather than trusted blindly. A naive calibration pass initially missed one known event - validation caught it before it shipped.
- **Commentary generation:** rule-based, not AI-generated. The tool never invents a cause for a flagged variance. It checks a known-events log and states the driver only when one is on file; otherwise it drafts an objective description and marks it "pending analyst review."

## Results

- Forecast accuracy: **7.0% MAPE**
- Flag rate after calibration: **12.8%** (down from 34.8% with hardcoded materiality thresholds)
- Known anomaly recall: **6/6** caught (naive calibration caught only 4/6)
- Commentary: 6 of 69 flagged rows matched a known driver and were auto-explained; the rest were honestly routed for analyst review

## Excel deliverable

`fpa_variance_analysis.xlsx` mirrors a traditional FP&A output, a 3-sheet workbook (Summary, Variance Detail, Action Items) with color-coded status but the status and commentary are driven by the same calibrated thresholds and event-log lookup as the rest of the pipeline, not a separate hardcoded rule set. Action Items are sorted known-driver rows first, largest variance first within each group, so the rows most worth a reviewer's time surface at the top.

## Stack

Python (pandas, numpy) for data generation, forecasting, and calibration. Chart.js for the dashboard. Self-contained HTML/JS front end, no build step, no server required.

## Note on the data

All figures are synthetic, generated with scripted anomalies (a campaign overspend, a fuel cost spike, a hiring freeze, and others) specifically so the calibration and detection logic could be validated against known ground truth.
