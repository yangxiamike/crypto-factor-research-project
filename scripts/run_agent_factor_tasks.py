from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from factor_research.agent_mining import run_agent_factor_tasks
from factor_research.runtime import DataInsufficientError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run approved agent factor tasks from YAML on DuckDB market data."
    )
    parser.add_argument("--db-path", required=True, help="DuckDB file path.")
    parser.add_argument("--tasks", required=True, help="Task config path (YAML).")
    parser.add_argument(
        "--snapshot-time",
        default=None,
        help="Optional snapshot time (e.g. 2026-04-24 00:00:00).",
    )
    parser.add_argument(
        "--horizon-hours",
        type=int,
        default=8,
        help="Default horizon for tasks without horizons field. Default: 8.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        result = run_agent_factor_tasks(
            db_path=args.db_path,
            tasks_config_path=args.tasks,
            snapshot_time=args.snapshot_time,
            default_horizon_hours=args.horizon_hours,
        )
    except DataInsufficientError as exc:
        print(f"[INFO] 数据不足，未执行完成: {exc}")
        return 0
    except Exception as exc:
        print(f"[ERROR] 运行失败: {exc}")
        return 1

    print("=== Agent Factor Task Batch ===")
    print(f"run_id={result.run_id}")
    print(f"snapshot_time={result.snapshot_time}")
    print(f"universe_mode={result.universe_mode}")
    print(f"tasks_total={result.tasks_total}, tasks_approved={result.tasks_approved}")
    print(
        "summary: "
        + ", ".join(
            f"{key}={value}" for key, value in sorted(result.summary_by_execution.items())
        )
    )

    for task in result.task_results:
        print(
            f"- task_id={task.task_id} factor={task.factor_name} "
            f"input_status={task.input_status} status={task.status} "
            f"execution={task.execution_status} profile_runs={task.executed_profiles}"
        )
        if task.message:
            print(f"  message={task.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
