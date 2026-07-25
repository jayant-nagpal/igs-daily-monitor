# IGS Daily Monitor — Dashboard Data Adapter

This adapter turns **already-produced** IGS pipeline output into a single clean
`latest.json` that the React dashboard reads.

```
existing pipeline output
        ↓
dashboard data adapter   (build_dashboard_payload.py)
        ↓
public/data/latest.json
        ↓
React dashboard reads latest.json
```

## First-build limitations (read this first)

- The dashboard **does not send emails**.
- The dashboard **does not change the email pipeline** — no email scripts,
  recipients, subjects, HTML, batch files, or scheduler behaviour are touched.
- The adapter **reads generated output files only**. It never connects to SQL,
  never calls ExecAPI / RiskAPI / SignalStore / any internal API, and never imports or runs
  the production scripts (`slippage_calc.py`, `stoploss_check.py`, …).
- Automation is added **later** by scheduling this adapter *after* the existing
  pipeline run (see "Future daily automation" below).
- If the current pipeline does not already save HTML/CSV/JSON output files, the
  first operational step is simply to **save or copy the already-generated
  report output** into the adapter's input folder. This can be done entirely
  outside the email script.

## Install

```bash
pip install -r dashboard_adapter/requirements.txt
```

Only `pandas`, `beautifulsoup4`, and `lxml` are needed (plus the Python standard
library). JSON / sample mode works even without pandas installed.

## Run

```bash
# Mode 1/2 — read a folder of pipeline output files (JSON / CSV / HTML)
python dashboard_adapter/build_dashboard_payload.py \
  --input-dir ./pipeline_output \
  --output ./igs-daily-monitor/public/data/latest.json

# Mode 3 — read a single manually-provided JSON already in dashboard schema
python dashboard_adapter/build_dashboard_payload.py \
  --input ./pipeline_output/latest_raw.json \
  --output ./igs-daily-monitor/public/data/latest.json

# Sample mode — no real files yet: emit screenshot sample data
python dashboard_adapter/build_dashboard_payload.py \
  --output ./igs-daily-monitor/public/data/latest.json
```

Every run also writes a dated copy `dashboard_payload_YYYY-MM-DD.json` next to
the output (disable with `--no-dated-copy`) and prints a concise summary with
row counts, missing sections, and warnings.

## Input modes

| Mode | Trigger | Reads |
| ---- | ------- | ----- |
| **1 — JSON/CSV (preferred)** | `--input-dir` containing `.json` / `.csv` | Structured exports from the pipeline output folder. A schema-shaped `.json` is used directly; otherwise CSVs are classified by column names. |
| **2 — HTML (fallback)** | `--input-dir` containing `.html` | Saved HTML email-body tables, parsed with `pandas.read_html`. Table types are inferred from column names because table titles aren't machine-readable. |
| **3 — manual JSON** | `--input <file.json>` | A single JSON file already matching the dashboard schema; it is validated, numerically normalised, and copied to `latest.json`. |
| **sample** | neither flag, or no usable files found | Built-in screenshot sample data (`sample_data.py`). |

### HTML table classification

`pandas.read_html` extracts every `<table>`; each is classified by its columns,
mirroring the real email tables:

| Detected type | Column signature (from the pipeline scripts) |
| ------------- | -------------------------------------------- |
| Slippage summary | `Algo_id`, `Algo_name`, `slippage_model_igs`, … |
| Slippage headline | `Metric`, `Slippage`, `P&L` |
| Best/worst stocks | `Symbol`, `Name`, `Slippage_PnL_₹` |
| Alert table | `Alert Type`, `Metric`, `Current Value`, `Threshold` |
| Stop-loss watch | `symbol`, `reset_price`, `last_price`, `pct_change%`, `sl_hit` |
| Exposure | `algoName`, `OSID`, `Quantity`, `AvgPrice`, `MarketPrice`, `exec_weight%` |
| Price-cost drift | `reset_price`, `Avg Cost`, `Diff_ResetPrice_AvgPrice` |

If a table cannot be classified, the adapter **does not fail** — it records a
warning (with the table shape and columns) in `dataHealth.warnings` and moves on.
Best/worst stocks are attached to the correct algo by reading the surrounding
`<h3>ALGO-A (Algo …)</h3>` / `<h4>Top 5 Best/Worst …</h4>` headings.

## What the adapter guarantees

- Validates required sections (`slippage`, `risk`) and reports what's present/missing.
- Normalises column names (case / spacing / separators insensitive).
- Converts percentage strings (`"0.1207%"`) to numbers (`0.1207`).
- Converts ₹ P&L strings (`"₹1,182.60"`, `"-2,693.60"`) to numbers.
- Preserves an explicit `-0.00%` as negative zero so the UI can render it faithfully.
- Preserves original text labels where useful (e.g. alert `currentValue`, `threshold`).
- Writes a clean `latest.json` **and** a dated copy.
- Prints a concise success message with row counts.

## Output schema

See the top-level contract in the project spec. Key sections:
`businessDate`, `generatedAt`, `source`, `slippage.{summary,algos}`,
`risk.{alerts,zScores,stopLossWatch,priceCostDrift,exposure}`,
`dataHealth.{sectionsPresent,sectionsMissing,warnings,rowCounts}`.

## Folder contents

```
dashboard_adapter/
├── README.md                    # this file
├── build_dashboard_payload.py   # the adapter (parse_args, load_input_files,
│                                #   parse_json_input, parse_csv_inputs,
│                                #   parse_html_tables, normalize_columns,
│                                #   parse_percent, parse_rupees, build_payload,
│                                #   validate_payload, write_payload)
├── sample_data.py               # screenshot sample data (single source of truth)
├── make_sample_inputs.py        # helper: writes representative CSV/HTML inputs
├── requirements.txt             # pandas, beautifulsoup4, lxml
├── sample_inputs/               # example CSV + HTML inputs (for Mode 1/2 demos)
│   ├── exposure.csv
│   ├── price_cost_drift.csv
│   └── email_body.html
└── sample_output/
    ├── latest.json                        # canonical sample payload
    └── dashboard_payload_2026-07-06.json  # dated copy
```

## Future daily automation

1. Existing email pipeline runs as usual (untouched).
2. Pipeline output files are saved or copied to a known folder (e.g. `./pipeline_output`).
3. `build_dashboard_payload.py` runs **after** the pipeline.
4. `latest.json` is copied to the dashboard data location (`public/data/latest.json`,
   or wherever `VITE_DASHBOARD_DATA_URL` points).
5. The dashboard reads the updated JSON on next load.

Production scheduling is intentionally **not** implemented yet — the architecture
is simply made ready for it. A future `.bat`/cron step would run the adapter and
publish `latest.json`; it must be a separate step that runs after, and never
modifies, the existing emailer.
