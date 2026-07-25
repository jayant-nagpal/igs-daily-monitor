// ============================================================
// IGS Daily Monitor — bundled sample data (fallback)
// Auto-generated mirror of dashboard_adapter/sample_output/latest.json
// Used when neither VITE_DASHBOARD_DATA_URL nor /data/latest.json is reachable.
// ============================================================
import type { DashboardData } from '../types/dashboard';

export const sampleData: DashboardData = {
  "businessDate": "2026-07-06",
  "generatedAt": "2026-07-13T12:41:32+05:30",
  "source": {
    "mode": "sample",
    "inputFiles": [],
    "notes": [
      "Fully synthetic sample data — fictional symbols, companies and books.",
      "priceCostDrift resetPrice/avgCost/execWeightPct/gainLossPct are null because only the diff % was visible in the source tables."
    ]
  },
  "slippage": {
    "summary": [
      {
        "algoId": 24,
        "algoName": "ALGO-A",
        "slippageModelIgsPct": 0.1207,
        "slippageClosePricePct": -0.0008,
        "cumulativeDailyClosePct": -0.001,
        "cumulativeModelClosePct": 0.1927,
        "todayClosePnl": -1182.6,
        "todayModelPnl": 171315.33,
        "cumulativeDailyClosePnl": -1476.47,
        "cumulativeModelPnl": 273490.48
      },
      {
        "algoId": 85,
        "algoName": "ALGO-B",
        "slippageModelIgsPct": 0.1158,
        "slippageClosePricePct": -0.001,
        "cumulativeDailyClosePct": -0.0013,
        "cumulativeModelClosePct": 0.1835,
        "todayClosePnl": -2693.6,
        "todayModelPnl": 300642.71,
        "cumulativeDailyClosePnl": -3346.18,
        "cumulativeModelPnl": 476525.24
      },
      {
        "algoId": 187,
        "algoName": "ALGO-B2",
        "slippageModelIgsPct": 0.1225,
        "slippageClosePricePct": -0.0011,
        "cumulativeDailyClosePct": -0.0014,
        "cumulativeModelClosePct": 0.1943,
        "todayClosePnl": -10472.02,
        "todayModelPnl": 1153143.98,
        "cumulativeDailyClosePnl": -12891.1,
        "cumulativeModelPnl": 1828795.82
      }
    ],
    "algos": [
      {
        "algoId": 24,
        "algoName": "ALGO-A",
        "headlines": [
          {
            "metric": "Today vs Model (Reb D-Ref)",
            "slippagePct": 0.1207,
            "pnlRs": 171315.33
          },
          {
            "metric": "Today vs Close",
            "slippagePct": -0.0008,
            "pnlRs": -1182.6
          },
          {
            "metric": "Cumulative w.r.t. daily close",
            "slippagePct": -0.001,
            "pnlRs": -1476.47
          },
          {
            "metric": "Cumulative w.r.t. Model Portfolio",
            "slippagePct": 0.1927,
            "pnlRs": 273490.48
          }
        ],
        "bestStocks": [
          {
            "algoName": "ALGO-A",
            "rankType": "best",
            "symbol": "ZEV.IN",
            "name": "Zephyr E-Commerce Ventures",
            "slippagePnlRs": 959.26,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "best",
            "symbol": "BPL.IN",
            "name": "Bluewave Pharma Labs",
            "slippagePnlRs": 558.2,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "best",
            "symbol": "IEW.IN",
            "name": "Auric Speciality Chemicals",
            "slippagePnlRs": 448.15,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "best",
            "symbol": "CRL.IN",
            "name": "Helix Diagnostics",
            "slippagePnlRs": 364.5,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "best",
            "symbol": "ASC.IN",
            "name": "Amberly Aroma Chemicals",
            "slippagePnlRs": 187.7,
            "slippagePct": 0.0
          }
        ],
        "worstStocks": [
          {
            "algoName": "ALGO-A",
            "rankType": "worst",
            "symbol": "PIG.IN",
            "name": "Polaris Industrial Gases",
            "slippagePnlRs": -760.5,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "worst",
            "symbol": "CPD.IN",
            "name": "Clearpath Diagnostics",
            "slippagePnlRs": -456.3,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "worst",
            "symbol": "CBP.IN",
            "name": "Cobalt Pharmaceuticals",
            "slippagePnlRs": -319.98,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "worst",
            "symbol": "HDX.IN",
            "name": "Vulcan Castings",
            "slippagePnlRs": -283.0,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-A",
            "rankType": "worst",
            "symbol": "MPL.IN",
            "name": "Sterling Wealth Advisors",
            "slippagePnlRs": -264.8,
            "slippagePct": -0.0
          }
        ]
      },
      {
        "algoId": 85,
        "algoName": "ALGO-B",
        "headlines": [
          {
            "metric": "Today vs Model (Reb D-Ref)",
            "slippagePct": 0.1158,
            "pnlRs": 300642.71
          },
          {
            "metric": "Today vs Close",
            "slippagePct": -0.001,
            "pnlRs": -2693.6
          },
          {
            "metric": "Cumulative w.r.t. daily close",
            "slippagePct": -0.0013,
            "pnlRs": -3346.18
          },
          {
            "metric": "Cumulative w.r.t. Model Portfolio",
            "slippagePct": 0.1835,
            "pnlRs": 476525.24
          }
        ],
        "bestStocks": [
          {
            "algoName": "ALGO-B",
            "rankType": "best",
            "symbol": "ZEV.IN",
            "name": "Zephyr E-Commerce Ventures",
            "slippagePnlRs": 1702.61,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "best",
            "symbol": "BPL.IN",
            "name": "Bluewave Pharma Labs",
            "slippagePnlRs": 881.7,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "best",
            "symbol": "IEW.IN",
            "name": "Auric Speciality Chemicals",
            "slippagePnlRs": 696.42,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "best",
            "symbol": "CRL.IN",
            "name": "Helix Diagnostics",
            "slippagePnlRs": 592.2,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "best",
            "symbol": "ASC.IN",
            "name": "Amberly Aroma Chemicals",
            "slippagePnlRs": 310.2,
            "slippagePct": 0.0
          }
        ],
        "worstStocks": [
          {
            "algoName": "ALGO-B",
            "rankType": "worst",
            "symbol": "PIG.IN",
            "name": "Polaris Industrial Gases",
            "slippagePnlRs": -1330.5,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "worst",
            "symbol": "CPD.IN",
            "name": "Clearpath Diagnostics",
            "slippagePnlRs": -702.7,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "worst",
            "symbol": "CBP.IN",
            "name": "Cobalt Pharmaceuticals",
            "slippagePnlRs": -550.94,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "worst",
            "symbol": "HDX.IN",
            "name": "Vulcan Castings",
            "slippagePnlRs": -509.0,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B",
            "rankType": "worst",
            "symbol": "MPL.IN",
            "name": "Sterling Wealth Advisors",
            "slippagePnlRs": -500.9,
            "slippagePct": -0.0
          }
        ]
      },
      {
        "algoId": 187,
        "algoName": "ALGO-B2",
        "headlines": [
          {
            "metric": "Today vs Model (Reb D-Ref)",
            "slippagePct": 0.1225,
            "pnlRs": 1153143.98
          },
          {
            "metric": "Today vs Close",
            "slippagePct": -0.0011,
            "pnlRs": -10472.02
          },
          {
            "metric": "Cumulative w.r.t. daily close",
            "slippagePct": -0.0014,
            "pnlRs": -12891.1
          },
          {
            "metric": "Cumulative w.r.t. Model Portfolio",
            "slippagePct": 0.1943,
            "pnlRs": 1828795.82
          }
        ],
        "bestStocks": [
          {
            "algoName": "ALGO-B2",
            "rankType": "best",
            "symbol": "ZEV.IN",
            "name": "Zephyr E-Commerce Ventures",
            "slippagePnlRs": 6470.31,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "best",
            "symbol": "BPL.IN",
            "name": "Bluewave Pharma Labs",
            "slippagePnlRs": 3367.6,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "best",
            "symbol": "IEW.IN",
            "name": "Auric Speciality Chemicals",
            "slippagePnlRs": 2661.68,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "best",
            "symbol": "CRL.IN",
            "name": "Helix Diagnostics",
            "slippagePnlRs": 2288.4,
            "slippagePct": 0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "best",
            "symbol": "ASC.IN",
            "name": "Amberly Aroma Chemicals",
            "slippagePnlRs": 1171.2,
            "slippagePct": 0.0
          }
        ],
        "worstStocks": [
          {
            "algoName": "ALGO-B2",
            "rankType": "worst",
            "symbol": "PIG.IN",
            "name": "Polaris Industrial Gases",
            "slippagePnlRs": -5213.5,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "worst",
            "symbol": "CPD.IN",
            "name": "Clearpath Diagnostics",
            "slippagePnlRs": -2741.8,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "worst",
            "symbol": "CBP.IN",
            "name": "Cobalt Pharmaceuticals",
            "slippagePnlRs": -2117.54,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "worst",
            "symbol": "HDX.IN",
            "name": "Vulcan Castings",
            "slippagePnlRs": -2006.0,
            "slippagePct": -0.0
          },
          {
            "algoName": "ALGO-B2",
            "rankType": "worst",
            "symbol": "MPL.IN",
            "name": "Sterling Wealth Advisors",
            "slippagePnlRs": -1905.2,
            "slippagePct": -0.0
          }
        ]
      }
    ]
  },
  "risk": {
    "alerts": [
      {
        "alertType": "Model Portfolio Drawdown",
        "metric": "Drawdown %",
        "currentValue": "-0.00%",
        "threshold": "7%",
        "breach": "No",
        "actionRequired": "None",
        "severity": "ok"
      },
      {
        "alertType": "Stock-Level Stop Loss",
        "metric": "No. of Stocks Breaching -18%",
        "currentValue": "0",
        "threshold": "-18%",
        "breach": "No",
        "actionRequired": "None",
        "severity": "ok"
      },
      {
        "alertType": "Exposure Level",
        "metric": "No. of Stocks Breaching 9.5%",
        "currentValue": "0",
        "threshold": "9.50%",
        "breach": "No",
        "actionRequired": "None",
        "severity": "ok"
      },
      {
        "alertType": "Composite Z-Score",
        "metric": "Z-Score",
        "currentValue": "3.61",
        "threshold": "—",
        "breach": "—",
        "actionRequired": "Informational",
        "severity": "info"
      },
      {
        "alertType": "Composite Z-Score Alpha",
        "metric": "Z-Score Alpha",
        "currentValue": "3.56",
        "threshold": "—",
        "breach": "—",
        "actionRequired": "Informational",
        "severity": "info"
      },
      {
        "alertType": "Composite Z-Score Combined",
        "metric": "Combined Z-Score",
        "currentValue": "3.59",
        "threshold": "—",
        "breach": "—",
        "actionRequired": "Informational",
        "severity": "info"
      }
    ],
    "zScores": {
      "composite": 3.61,
      "alpha": 3.56,
      "combined": 3.59
    },
    "stopLossWatch": [
      {
        "symbol": "HNB.IN",
        "name": "Heritage National Bank",
        "resetPrice": 941.8501,
        "lastPrice": 786.8999,
        "chgPct": 0.0,
        "daysHeld": 58,
        "execWeightPct": 0.1,
        "pctChangePct": -16.45,
        "slHit": false
      }
    ],
    "priceCostDrift": [
      {
        "algoName": "ALGO-A",
        "symbol": "OCP.IN",
        "name": "Orchid Consumer Products",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -10.48,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "IEW.IN",
        "name": "Auric Speciality Chemicals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -6.04,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "LMF.IN",
        "name": "Lumen Microfinance Ltd",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -5.86,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "SLL.IN",
        "name": "Crestline Laboratories",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -5.28,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "RGL.IN",
        "name": "Regalia Lifestyle",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 5.55,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "HSF.IN",
        "name": "Harbor Small Finance Bank",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 6.54,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "CBP.IN",
        "name": "Cobalt Pharmaceuticals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 7.8,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "SBI2.IN",
        "name": "Stonebridge Infra Ltd",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 8.39,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "NVC.IN",
        "name": "Novacare Hospitals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 11.28,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "NCP.IN",
        "name": "Northgate Chemicals & Pharma",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 12.39,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "BCB.IN",
        "name": "Beacon Bank",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 12.44,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "TEC.IN",
        "name": "Titanium Engines Co",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 13.0,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "ZEV.IN",
        "name": "Zephyr E-Commerce Ventures",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 16.26,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "MPL.IN",
        "name": "Sterling Wealth Advisors",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 16.78,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "CFI.IN",
        "name": "Corestone Fluorochem Intl.",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 17.71,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "CCB.IN",
        "name": "Coppertree Cables",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 22.13,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "SWA.IN",
        "name": "Meridian Ports & Logistics",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 25.71,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "SLF.IN",
        "name": "Silverleaf Labs",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 26.98,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "VTX.IN",
        "name": "Vertex Telecom",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 27.31,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-A",
        "symbol": "VES.IN",
        "name": "Voltaic Energy Systems",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 60.88,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "CSC.IN",
        "name": "Cascade Logistics",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -12.3,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "OCP.IN",
        "name": "Orchid Consumer Products",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -10.48,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "GFL.IN",
        "name": "Granite Finance Ltd",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -7.47,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "CDX.IN",
        "name": "Ironclad Engineering Works",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -7.07,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "SGC.IN",
        "name": "Summit Global Capital",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -6.94,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "IEW.IN",
        "name": "Auric Speciality Chemicals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -6.04,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "HSF.IN",
        "name": "Harbor Small Finance Bank",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 6.57,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "NVC.IN",
        "name": "Novacare Hospitals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 11.31,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "NCP.IN",
        "name": "Northgate Chemicals & Pharma",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 12.37,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "TEC.IN",
        "name": "Titanium Engines Co",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 13.02,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "ZEV.IN",
        "name": "Zephyr E-Commerce Ventures",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 16.24,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "MPL.IN",
        "name": "Sterling Wealth Advisors",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 16.95,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "CFI.IN",
        "name": "Corestone Fluorochem Intl.",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 17.68,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "CCB.IN",
        "name": "Coppertree Cables",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 21.89,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "SLF.IN",
        "name": "Silverleaf Labs",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 26.74,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "VTX.IN",
        "name": "Vertex Telecom",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 27.71,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B",
        "symbol": "VES.IN",
        "name": "Voltaic Energy Systems",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 53.73,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "CSC.IN",
        "name": "Cascade Logistics",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -12.38,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "OCP.IN",
        "name": "Orchid Consumer Products",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -10.48,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "GFL.IN",
        "name": "Granite Finance Ltd",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -7.47,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "CDX.IN",
        "name": "Ironclad Engineering Works",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -7.07,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "SGC.IN",
        "name": "Summit Global Capital",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -6.95,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "IEW.IN",
        "name": "Auric Speciality Chemicals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": -6.04,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "HSF.IN",
        "name": "Harbor Small Finance Bank",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 6.64,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "PYE.IN",
        "name": "Pyrotech Energy",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 7.34,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "FPN.IN",
        "name": "Falcon Pneumatics",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 7.45,
        "execWeightPct": null,
        "gainLossPct": null
      },
      {
        "algoName": "ALGO-B2",
        "symbol": "CBP.IN",
        "name": "Cobalt Pharmaceuticals",
        "resetPrice": null,
        "avgCost": null,
        "diffResetPriceAvgPricePct": 7.76,
        "execWeightPct": null,
        "gainLossPct": null
      }
    ],
    "exposure": [
      {
        "algoName": "IGS_algo_b2",
        "osid": 3177322,
        "quantity": 28226,
        "avgPrice": 1629.13,
        "marketPrice": 2095.5,
        "isin": "INE003C01036",
        "execWeightPct": 6.14,
        "gainLossPct": 29.0,
        "marketValue": 59147583.0,
        "symbol": "MPL.IN",
        "coname": "Sterling Wealth Advisors"
      },
      {
        "algoName": "IGS_algo_b",
        "osid": 3177322,
        "quantity": 7863,
        "avgPrice": 1631.82,
        "marketPrice": 2095.5,
        "isin": "INE003C01036",
        "execWeightPct": 6.2,
        "gainLossPct": 28.0,
        "marketValue": 16476916.5,
        "symbol": "MPL.IN",
        "coname": "Sterling Wealth Advisors"
      },
      {
        "algoName": "IGS_algo_b2",
        "osid": 3023076,
        "quantity": 7335,
        "avgPrice": 6254.28,
        "marketPrice": 7729.0,
        "isin": "INE001A01018",
        "execWeightPct": 5.88,
        "gainLossPct": 24.0,
        "marketValue": 56692215.0,
        "symbol": "CFI.IN",
        "coname": "Corestone Fluorochem Intl."
      },
      {
        "algoName": "IGS_algo_b",
        "osid": 3023076,
        "quantity": 2038,
        "avgPrice": 6243.59,
        "marketPrice": 7729.0,
        "isin": "INE001A01018",
        "execWeightPct": 5.92,
        "gainLossPct": 24.0,
        "marketValue": 15751702.0,
        "symbol": "CFI.IN",
        "coname": "Corestone Fluorochem Intl."
      },
      {
        "algoName": "IGS_algo_b2",
        "osid": 3022797,
        "quantity": 6323,
        "avgPrice": 7652.43,
        "marketPrice": 8888.5,
        "isin": "INE002B01027",
        "execWeightPct": 5.83,
        "gainLossPct": 16.0,
        "marketValue": 56201985.5,
        "symbol": "NVC.IN",
        "coname": "Novacare Hospitals"
      },
      {
        "algoName": "IGS_algo_b",
        "osid": 3022797,
        "quantity": 1755,
        "avgPrice": 7643.73,
        "marketPrice": 8888.5,
        "isin": "INE002B01027",
        "execWeightPct": 5.87,
        "gainLossPct": 16.0,
        "marketValue": 15599317.5,
        "symbol": "NVC.IN",
        "coname": "Novacare Hospitals"
      }
    ]
  },
  "dataHealth": {
    "strictJson": true,
    "pipelineStatus": "ok",
    "producerStatus": {
      "alerts": { "status": "success" },
      "slippage": { "status": "success" },
      "stop_loss": { "status": "success" },
      "price_cost_drift": { "status": "success" },
      "exposure": { "status": "success" },
      "zscores": { "status": "success" }
    },
    "lastSuccessfulRunAt": "2026-07-13T12:41:32+05:30",
    "sectionsPresent": [
      "slippage.summary",
      "slippage.algos",
      "risk.alerts",
      "risk.zScores",
      "risk.stopLossWatch",
      "risk.priceCostDrift",
      "risk.exposure"
    ],
    "sectionsMissing": [],
    "warnings": [],
    "rowCounts": {
      "slippageSummary": 3,
      "slippageAlgos": 3,
      "alerts": 6,
      "stopLossWatch": 1,
      "priceCostDrift": 47,
      "exposure": 6,
      "zScores": 3
    }
  }
} as DashboardData;
