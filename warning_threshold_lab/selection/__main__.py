from __future__ import annotations

import argparse
import json
import sys

from warning_threshold_lab.selection.analysis import SelectionError
from warning_threshold_lab.selection.service import select_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m warning_threshold_lab.selection",
        description="防汛预警候选策略离线方案选择（不连接真实发布系统）",
    )
    parser.add_argument("--input", required=True, help="分析输入 JSON（分数、过程、标签、候选、约束）")
    parser.add_argument("--output", required=True, help="选择记录输出 JSON 路径")
    parser.add_argument("--database", required=True, help="SQLite 数据库路径，与既有评分记录共存")
    args = parser.parse_args(argv)
    try:
        record = select_from_files(args.input, args.database, args.output)
    except (SelectionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    # 控制台给出可核对的摘要，完整记录已写入 --output。
    summary = {
        "selection_id": record["selection_id"],
        "status": record["status"],
        "selected": record["selected"],
        "output": args.output,
        "reasons": record["reasons"],
        "storage": record["storage"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
