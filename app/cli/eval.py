from __future__ import annotations

import argparse
import json

from app.cli.common import managed_session
from app.services.evaluation import EvaluationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="执行离线评测")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="执行评测")
    run_parser.add_argument("--dataset", required=True, help="数据集名称")
    run_parser.add_argument("--snapshot", default="default", help="参数快照名称")

    show_parser = subparsers.add_parser("show", help="查看评测结果")
    show_parser.add_argument("--eval-run-id", required=True, help="评测运行 ID")

    compare_parser = subparsers.add_parser("compare", help="对比两次评测结果")
    compare_parser.add_argument("--base-eval-run-id", required=True, help="基线评测运行 ID")
    compare_parser.add_argument("--target-eval-run-id", required=True, help="对比评测运行 ID")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    with managed_session() as session:
        service = EvaluationService(session)
        if args.command == "run":
            eval_run = service.run(dataset_name=args.dataset, snapshot_name=args.snapshot)
            report_paths = service.get_report_paths(eval_run.id)
            payload = {
                "eval_run_id": eval_run.id,
                "dataset_name": eval_run.dataset_name,
                "snapshot_name": eval_run.snapshot_name,
                "case_count": eval_run.case_count,
                "summary": eval_run.summary_json,
                "bad_cases": eval_run.bad_cases_json,
                "report_json_path": report_paths["json"],
                "report_markdown_path": report_paths["markdown"],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.command == "show":
            eval_run = service.get_by_id(args.eval_run_id)
            report_paths = service.get_report_paths(eval_run.id)
            payload = {
                "eval_run_id": eval_run.id,
                "dataset_name": eval_run.dataset_name,
                "snapshot_name": eval_run.snapshot_name,
                "case_count": eval_run.case_count,
                "summary": eval_run.summary_json,
                "bad_cases": eval_run.bad_cases_json,
                "report_json_path": report_paths["json"],
                "report_markdown_path": report_paths["markdown"],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.command == "compare":
            comparison = service.compare_runs(
                base_eval_run_id=args.base_eval_run_id,
                target_eval_run_id=args.target_eval_run_id,
            )
            report_paths = service.get_compare_report_paths(
                args.base_eval_run_id,
                args.target_eval_run_id,
            )
            payload = {
                **comparison,
                "report_json_path": report_paths["json"],
                "report_markdown_path": report_paths["markdown"],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
