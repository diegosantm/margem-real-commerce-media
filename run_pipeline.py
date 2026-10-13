"""
Run the whole project end to end:

    python run_pipeline.py            # SQL layers + validation + dashboard
    python run_pipeline.py --regen    # also regenerate the synthetic data first

Writes warehouse/margem_real.duckdb, validation/validation_report.md and docs/index.html.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
SQL_FILES = sorted((ROOT / "sql").glob("*.sql"))
DB_PATH = ROOT / "warehouse" / "margem_real.duckdb"


def run_sql() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    for f in SQL_FILES:
        t0 = time.time()
        con.execute(f.read_text(encoding="utf-8"))
        print(f"  ok  {f.name:<32} {time.time() - t0:5.2f}s")
    con.close()


def main() -> None:
    import os
    os.chdir(ROOT)  # SQL files read data/raw/... relative to the repo root
    if "--regen" in sys.argv:
        print("[1/4] generating synthetic data")
        subprocess.run([sys.executable, "generator/generate_data.py"], check=True)
    print("[2/4] building warehouse")
    run_sql()
    print("[3/4] validating")
    ok = subprocess.run([sys.executable, "validation/validate.py"]).returncode == 0
    print("[4/4] building dashboard")
    subprocess.run([sys.executable, "dashboard/build_dashboard.py"], check=True)
    if not ok:
        sys.exit("validation failed: see validation/validation_report.md")


if __name__ == "__main__":
    main()
