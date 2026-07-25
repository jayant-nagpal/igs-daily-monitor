"""Dashboard adapter package: pipeline artifacts -> strict latest.json.

Marker module so `dashboard_adapter` is importable as a top-level package
(pip install -e ., pyproject.toml [project.scripts] igs-finalize). No
behavior lives here — see dashboard_contract.py, pipeline_exporter.py,
finalize_dashboard_run.py, export_dashboard.py for the real logic.
"""
