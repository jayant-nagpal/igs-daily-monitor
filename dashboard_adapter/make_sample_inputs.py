"""Generate representative CSV + HTML sample inputs that mimic real pipeline
output, so the adapter's Mode 1 (CSV) and Mode 2 (HTML) can be exercised."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sample_data as sd  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_inputs")
os.makedirs(OUT, exist_ok=True)

# ---- CSV: exposure (matches ExecAPI export column names) --------------------
exp = pd.DataFrame([{
    "algoName": r["algoName"], "OSID": r["osid"], "Quantity": r["quantity"],
    "AvgPrice": r["avgPrice"], "MarketPrice": r["marketPrice"], "ISIN": r["isin"],
    "exec_weight%": r["execWeightPct"], "Gain/Loss%": r["gainLossPct"],
    "MarketValue": r["marketValue"], "symbol": r["symbol"], "coname": r["coname"],
} for r in sd.EXPOSURE])
exp.to_csv(os.path.join(OUT, "exposure.csv"), index=False)

# ---- CSV: price-cost drift (tracking error) -----------------------------
drift_rows = []
for algo, items in sd._DRIFT.items():
    for (sym, name, diff) in items:
        drift_rows.append({
            "algoName": algo, "symbol": sym, "Name": name,
            "reset_price": "", "Avg Cost": "",
            "Diff_ResetPrice_AvgPrice": f"{diff}%",
            "exec_weight%": "", "Gain/Loss%": "",
        })
pd.DataFrame(drift_rows).to_csv(os.path.join(OUT, "price_cost_drift.csv"), index=False)

# ---- HTML: alert table + slippage summary + stop-loss + best/worst ------
def slip_summary_html():
    df = pd.DataFrame([{
        "Algo_id": r["algoId"], "Algo_name": r["algoName"],
        "slippage_model_igs": f'{r["slippageModelIgsPct"]}%',
        "slippage_close_price": f'{r["slippageClosePricePct"]}%',
        "slippage_cumulative_igs_daily_close": f'{r["cumulativeDailyClosePct"]}%',
        "slippage_cumulative_igs_model_close": f'{r["cumulativeModelClosePct"]}%',
    } for r in sd.SLIPPAGE_SUMMARY])
    return "<h4>Summary Slippage</h4>" + df.to_html(index=False)

def alerts_html():
    df = pd.DataFrame([{
        "Alert Type": a["alertType"], "Metric": a["metric"],
        "Current Value": a["currentValue"], "Threshold": a["threshold"],
        "Breach?": a["breach"], "Action Required": a["actionRequired"],
    } for a in sd.ALERTS])
    return df.to_html(index=False)

def stoploss_html():
    df = pd.DataFrame([{
        "symbol": r["symbol"], "Name": r["name"], "reset_price": r["resetPrice"],
        "last_price": r["lastPrice"], "Chg%": f'{r["chgPct"]}%',
        "Days Held": r["daysHeld"], "exec_weight%": f'{r["execWeightPct"]}%',
        "pct_change%": f'{r["pctChangePct"]}%', "sl_hit": r["slHit"],
    } for r in sd.STOP_LOSS_WATCH])
    return "<p>Model Portfolio Bottom 5 position by pct change:" + df.to_html(index=False) + "</p>"

def stocks_html(algo, rank):
    df = pd.DataFrame([{
        "Symbol": s, "Name": n, "Slippage_PnL_₹": pnl, "Slippage_pct": f"{pct}%",
    } for (s, n, pnl, pct) in sd._BEST_WORST[algo][rank]])
    title = f"Top 5 {'Best' if rank == 'best' else 'Worst'} Stocks (₹ Slippage P&L)"
    return f"<h3>{algo} (Algo)</h3><h4>{title}</h4>" + df.to_html(index=False)

html = "<html><body>"
html += alerts_html()
html += stoploss_html()
html += slip_summary_html()
for algo in ["ALGO-A", "ALGO-B", "ALGO-B2"]:
    html += stocks_html(algo, "best")
    html += stocks_html(algo, "worst")
html += "</body></html>"
with open(os.path.join(OUT, "email_body.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Sample inputs written to", OUT)
for fn in sorted(os.listdir(OUT)):
    print("  -", fn)
