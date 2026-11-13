from __future__ import annotations
import argparse
import json
from warning_threshold_lab.service import run_fixture

def main() -> int:
    parser = argparse.ArgumentParser(description='暴雨预警阈值复盘与校准实验室')
    parser.add_argument("fixture")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    result = run_fixture(args.fixture, args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
