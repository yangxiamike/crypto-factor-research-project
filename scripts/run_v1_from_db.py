from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from factor_research.runtime import DataInsufficientError, run_v1_from_db


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run factor research v1 workflow from DuckDB market/universe tables."
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="DuckDB file path.",
    )
    parser.add_argument(
        "--snapshot-time",
        default=None,
        help="Optional snapshot time (e.g. 2026-01-31 00:00:00).",
    )
    parser.add_argument(
        "--horizon-hours",
        type=int,
        default=24,
        help="Forward return horizon in hours. Default: 24.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        results, meta = run_v1_from_db(
            db_path=args.db_path,
            snapshot_time=args.snapshot_time,
            horizon_hours=args.horizon_hours,
        )
    except DataInsufficientError as exc:
        print(f"[INFO] 数据不足，未执行完成: {exc}")
        return 0
    except Exception as exc:
        print(f"[ERROR] 运行失败: {exc}")
        return 1

    print("=== V1 From DB: Profile Evaluation ===")
    print(
        "meta: "
        f"snapshot_time={meta['snapshot_time']}, "
        f"horizon_hours={meta['horizon_hours']}, "
        f"universe_mode={meta.get('universe_mode', 'unknown')}, "
        f"rows={meta['rows']}, "
        f"n_dates={meta['n_dates']}, "
        f"n_assets={meta['n_assets']}"
    )

    for item in results:
        print(f"\n[Profile] {item.profile}")
        for name, value in item.metrics.items():
            print(f"  - {name}: {value:.6f}")
        print(f"  - decision: {item.decision}")
        if item.reasons:
            print(f"  - reasons: {', '.join(item.reasons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
