"""
Built-in sample data for the IGS Daily Monitor dashboard adapter.

All values are transcribed from the daily IGS report screenshots so the
dashboard works immediately with no live pipeline connection. This is the
single Python source of truth for the sample payload; the React app carries
its own mirror in src/data/sampleData.ts.
"""

from __future__ import annotations

ALGO_ID_MAP = {24: "ALGO-A", 85: "ALGO-B", 187: "ALGO-B2"}


# ---- Slippage summary (headline P&L + %) --------------------------------
SLIPPAGE_SUMMARY = [
    {
        "algoId": 24, "algoName": "ALGO-A",
        "slippageModelIgsPct": 0.1207, "slippageClosePricePct": -0.0008,
        "cumulativeDailyClosePct": -0.001, "cumulativeModelClosePct": 0.1927,
        "todayClosePnl": -1182.60, "todayModelPnl": 171315.33,
        "cumulativeDailyClosePnl": -1476.47, "cumulativeModelPnl": 273490.48,
    },
    {
        "algoId": 85, "algoName": "ALGO-B",
        "slippageModelIgsPct": 0.1158, "slippageClosePricePct": -0.001,
        "cumulativeDailyClosePct": -0.0013, "cumulativeModelClosePct": 0.1835,
        "todayClosePnl": -2693.60, "todayModelPnl": 300642.71,
        "cumulativeDailyClosePnl": -3346.18, "cumulativeModelPnl": 476525.24,
    },
    {
        "algoId": 187, "algoName": "ALGO-B2",
        "slippageModelIgsPct": 0.1225, "slippageClosePricePct": -0.0011,
        "cumulativeDailyClosePct": -0.0014, "cumulativeModelClosePct": 0.1943,
        "todayClosePnl": -10472.02, "todayModelPnl": 1153143.98,
        "cumulativeDailyClosePnl": -12891.10, "cumulativeModelPnl": 1828795.82,
    },
]

# ---- Best / worst stocks by ₹ slippage P&L per algo ---------------------
_BEST_WORST = {
    "ALGO-A": {
        "best": [
            ("ZEV.IN", "Zephyr E-Commerce Ventures", 959.26, 0.00),
            ("BPL.IN", "Bluewave Pharma Labs", 558.20, 0.00),
            ("IEW.IN", "Auric Speciality Chemicals", 448.15, 0.00),
            ("CRL.IN", "Helix Diagnostics", 364.50, 0.00),
            ("ASC.IN", "Amberly Aroma Chemicals", 187.70, 0.00),
        ],
        "worst": [
            ("PIG.IN", "Polaris Industrial Gases", -760.50, -0.00),
            ("CPD.IN", "Clearpath Diagnostics", -456.30, -0.00),
            ("CBP.IN", "Cobalt Pharmaceuticals", -319.98, -0.00),
            ("HDX.IN", "Vulcan Castings", -283.00, -0.00),
            ("MPL.IN", "Sterling Wealth Advisors", -264.80, -0.00),
        ],
    },
    "ALGO-B": {
        "best": [
            ("ZEV.IN", "Zephyr E-Commerce Ventures", 1702.61, 0.00),
            ("BPL.IN", "Bluewave Pharma Labs", 881.70, 0.00),
            ("IEW.IN", "Auric Speciality Chemicals", 696.42, 0.00),
            ("CRL.IN", "Helix Diagnostics", 592.20, 0.00),
            ("ASC.IN", "Amberly Aroma Chemicals", 310.20, 0.00),
        ],
        "worst": [
            ("PIG.IN", "Polaris Industrial Gases", -1330.50, -0.00),
            ("CPD.IN", "Clearpath Diagnostics", -702.70, -0.00),
            ("CBP.IN", "Cobalt Pharmaceuticals", -550.94, -0.00),
            ("HDX.IN", "Vulcan Castings", -509.00, -0.00),
            ("MPL.IN", "Sterling Wealth Advisors", -500.90, -0.00),
        ],
    },
    "ALGO-B2": {
        "best": [
            ("ZEV.IN", "Zephyr E-Commerce Ventures", 6470.31, 0.00),
            ("BPL.IN", "Bluewave Pharma Labs", 3367.60, 0.00),
            ("IEW.IN", "Auric Speciality Chemicals", 2661.68, 0.00),
            ("CRL.IN", "Helix Diagnostics", 2288.40, 0.00),
            ("ASC.IN", "Amberly Aroma Chemicals", 1171.20, 0.00),
        ],
        "worst": [
            ("PIG.IN", "Polaris Industrial Gases", -5213.50, -0.00),
            ("CPD.IN", "Clearpath Diagnostics", -2741.80, -0.00),
            ("CBP.IN", "Cobalt Pharmaceuticals", -2117.54, -0.00),
            ("HDX.IN", "Vulcan Castings", -2006.00, -0.00),
            ("MPL.IN", "Sterling Wealth Advisors", -1905.20, -0.00),
        ],
    },
}

# ---- Alerts -------------------------------------------------------------
ALERTS = [
    {"alertType": "Model Portfolio Drawdown", "metric": "Drawdown %",
     "currentValue": "-0.00%", "threshold": "7%", "breach": "No",
     "actionRequired": "None", "severity": "ok"},
    {"alertType": "Stock-Level Stop Loss", "metric": "No. of Stocks Breaching -18%",
     "currentValue": "0", "threshold": "-18%", "breach": "No",
     "actionRequired": "None", "severity": "ok"},
    {"alertType": "Exposure Level", "metric": "No. of Stocks Breaching 9.5%",
     "currentValue": "0", "threshold": "9.50%", "breach": "No",
     "actionRequired": "None", "severity": "ok"},
    {"alertType": "Composite Z-Score", "metric": "Z-Score",
     "currentValue": "3.61", "threshold": "—", "breach": "—",
     "actionRequired": "Informational", "severity": "info"},
    {"alertType": "Composite Z-Score Alpha", "metric": "Z-Score Alpha",
     "currentValue": "3.56", "threshold": "—", "breach": "—",
     "actionRequired": "Informational", "severity": "info"},
    {"alertType": "Composite Z-Score Combined", "metric": "Combined Z-Score",
     "currentValue": "3.59", "threshold": "—", "breach": "—",
     "actionRequired": "Informational", "severity": "info"},
]

Z_SCORES = {"composite": 3.61, "alpha": 3.56, "combined": 3.59}

# ---- Stop-loss watch ----------------------------------------------------
STOP_LOSS_WATCH = [
    {"symbol": "HNB.IN", "name": "Heritage National Bank", "resetPrice": 941.8501,
     "lastPrice": 786.8999, "chgPct": 0.0, "daysHeld": 58, "execWeightPct": 0.1,
     "pctChangePct": -16.45, "slHit": False},
]

# ---- Exposure -----------------------------------------------------------
EXPOSURE = [
    {"algoName": "IGS_algo_b2", "osid": 3177322, "quantity": 28226, "avgPrice": 1629.13,
     "marketPrice": 2095.5, "isin": "INE003C01036", "execWeightPct": 6.14, "gainLossPct": 29.0,
     "marketValue": 59147583.0, "symbol": "MPL.IN", "coname": "Sterling Wealth Advisors"},
    {"algoName": "IGS_algo_b", "osid": 3177322, "quantity": 7863, "avgPrice": 1631.82,
     "marketPrice": 2095.5, "isin": "INE003C01036", "execWeightPct": 6.2, "gainLossPct": 28.0,
     "marketValue": 16476916.5, "symbol": "MPL.IN", "coname": "Sterling Wealth Advisors"},
    {"algoName": "IGS_algo_b2", "osid": 3023076, "quantity": 7335, "avgPrice": 6254.28,
     "marketPrice": 7729.0, "isin": "INE001A01018", "execWeightPct": 5.88, "gainLossPct": 24.0,
     "marketValue": 56692215.0, "symbol": "CFI.IN", "coname": "Corestone Fluorochem Intl."},
    {"algoName": "IGS_algo_b", "osid": 3023076, "quantity": 2038, "avgPrice": 6243.59,
     "marketPrice": 7729.0, "isin": "INE001A01018", "execWeightPct": 5.92, "gainLossPct": 24.0,
     "marketValue": 15751702.0, "symbol": "CFI.IN", "coname": "Corestone Fluorochem Intl."},
    {"algoName": "IGS_algo_b2", "osid": 3022797, "quantity": 6323, "avgPrice": 7652.43,
     "marketPrice": 8888.5, "isin": "INE002B01027", "execWeightPct": 5.83, "gainLossPct": 16.0,
     "marketValue": 56201985.5, "symbol": "NVC.IN", "coname": "Novacare Hospitals"},
    {"algoName": "IGS_algo_b", "osid": 3022797, "quantity": 1755, "avgPrice": 7643.73,
     "marketPrice": 8888.5, "isin": "INE002B01027", "execWeightPct": 5.87, "gainLossPct": 16.0,
     "marketValue": 15599317.5, "symbol": "NVC.IN", "coname": "Novacare Hospitals"},
]

# ---- Price / cost drift (Diff_ResetPrice_AvgPrice %) --------------------
# (algoName, symbol, name, diffPct)
_DRIFT = {
    "ALGO-A": [
        ("OCP.IN", "Orchid Consumer Products", -10.48), ("IEW.IN", "Auric Speciality Chemicals", -6.04),
        ("LMF.IN", "Lumen Microfinance Ltd", -5.86), ("SLL.IN", "Crestline Laboratories", -5.28),
        ("RGL.IN", "Regalia Lifestyle", 5.55), ("HSF.IN", "Harbor Small Finance Bank", 6.54),
        ("CBP.IN", "Cobalt Pharmaceuticals", 7.8), ("SBI2.IN", "Stonebridge Infra Ltd", 8.39),
        ("NVC.IN", "Novacare Hospitals", 11.28), ("NCP.IN", "Northgate Chemicals & Pharma", 12.39),
        ("BCB.IN", "Beacon Bank", 12.44), ("TEC.IN", "Titanium Engines Co", 13.0),
        ("ZEV.IN", "Zephyr E-Commerce Ventures", 16.26), ("MPL.IN", "Sterling Wealth Advisors", 16.78),
        ("CFI.IN", "Corestone Fluorochem Intl.", 17.71), ("CCB.IN", "Coppertree Cables", 22.13),
        ("SWA.IN", "Meridian Ports & Logistics", 25.71), ("SLF.IN", "Silverleaf Labs", 26.98),
        ("VTX.IN", "Vertex Telecom", 27.31), ("VES.IN", "Voltaic Energy Systems", 60.88),
    ],
    "ALGO-B": [
        ("CSC.IN", "Cascade Logistics", -12.3), ("OCP.IN", "Orchid Consumer Products", -10.48),
        ("GFL.IN", "Granite Finance Ltd", -7.47), ("CDX.IN", "Ironclad Engineering Works", -7.07),
        ("SGC.IN", "Summit Global Capital", -6.94), ("IEW.IN", "Auric Speciality Chemicals", -6.04),
        ("HSF.IN", "Harbor Small Finance Bank", 6.57), ("NVC.IN", "Novacare Hospitals", 11.31),
        ("NCP.IN", "Northgate Chemicals & Pharma", 12.37), ("TEC.IN", "Titanium Engines Co", 13.02),
        ("ZEV.IN", "Zephyr E-Commerce Ventures", 16.24), ("MPL.IN", "Sterling Wealth Advisors", 16.95),
        ("CFI.IN", "Corestone Fluorochem Intl.", 17.68), ("CCB.IN", "Coppertree Cables", 21.89),
        ("SLF.IN", "Silverleaf Labs", 26.74), ("VTX.IN", "Vertex Telecom", 27.71),
        ("VES.IN", "Voltaic Energy Systems", 53.73),
    ],
    "ALGO-B2": [
        ("CSC.IN", "Cascade Logistics", -12.38), ("OCP.IN", "Orchid Consumer Products", -10.48),
        ("GFL.IN", "Granite Finance Ltd", -7.47), ("CDX.IN", "Ironclad Engineering Works", -7.07),
        ("SGC.IN", "Summit Global Capital", -6.95), ("IEW.IN", "Auric Speciality Chemicals", -6.04),
        ("HSF.IN", "Harbor Small Finance Bank", 6.64), ("PYE.IN", "Pyrotech Energy", 7.34),
        ("FPN.IN", "Falcon Pneumatics", 7.45), ("CBP.IN", "Cobalt Pharmaceuticals", 7.76),
    ],
}


def _build_stocks(algo, rank):
    return [
        {"algoName": algo, "rankType": rank, "symbol": s, "name": n,
         "slippagePnlRs": pnl, "slippagePct": pct}
        for (s, n, pnl, pct) in _BEST_WORST[algo][rank]
    ]


def _build_algos():
    algos = []
    for row in SLIPPAGE_SUMMARY:
        algo = row["algoName"]
        algos.append({
            "algoId": row["algoId"],
            "algoName": algo,
            "headlines": [
                {"metric": "Today vs Model (Reb D-Ref)",
                 "slippagePct": row["slippageModelIgsPct"], "pnlRs": row["todayModelPnl"]},
                {"metric": "Today vs Close",
                 "slippagePct": row["slippageClosePricePct"], "pnlRs": row["todayClosePnl"]},
                {"metric": "Cumulative w.r.t. daily close",
                 "slippagePct": row["cumulativeDailyClosePct"], "pnlRs": row["cumulativeDailyClosePnl"]},
                {"metric": "Cumulative w.r.t. Model Portfolio",
                 "slippagePct": row["cumulativeModelClosePct"], "pnlRs": row["cumulativeModelPnl"]},
            ],
            "bestStocks": _build_stocks(algo, "best"),
            "worstStocks": _build_stocks(algo, "worst"),
        })
    return algos


def _build_drift():
    rows = []
    for algo, items in _DRIFT.items():
        for (sym, name, diff) in items:
            rows.append({
                "algoName": algo, "symbol": sym, "name": name,
                "resetPrice": None, "avgCost": None,
                "diffResetPriceAvgPricePct": diff,
                "execWeightPct": None, "gainLossPct": None,
            })
    return rows


def build_sample_payload(business_date: str = "2026-07-06") -> dict:
    return {
        "businessDate": business_date,
        "generatedAt": f"{business_date}T18:30:00+05:30",
        "source": {
            "mode": "sample",
            "inputFiles": [],
            "notes": [
                "Fully synthetic sample data — fictional symbols, companies and books.",
                "priceCostDrift resetPrice/avgCost/execWeightPct/gainLossPct are null "
                "because only the diff % was visible in the source tables.",
            ],
        },
        "slippage": {
            "summary": SLIPPAGE_SUMMARY,
            "algos": _build_algos(),
        },
        "risk": {
            "alerts": ALERTS,
            "zScores": Z_SCORES,
            "stopLossWatch": STOP_LOSS_WATCH,
            "priceCostDrift": _build_drift(),
            "exposure": EXPOSURE,
        },
        "dataHealth": {
            "sectionsPresent": [],
            "sectionsMissing": [],
            "warnings": [],
            "rowCounts": {},
        },
    }
