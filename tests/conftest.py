"""Pytest path setup so `pytest` (optional dev dep) can import the modules
without an installed package. Standalone `python3 tests/<file>.py` runs also
work because each file inserts these paths itself."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "pythonbatchscripts", REPO / "dashboard_adapter"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
