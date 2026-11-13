"""离线方案选择包：按时间与过程隔离的嵌套交叉验证与发布/hold 结论。"""
from warning_threshold_lab.selection.analysis import (
    CandidateConfig,
    SelectionError,
    load_analysis,
    run_selection,
)
from warning_threshold_lab.selection.service import select_from_files, select_from_payload
from warning_threshold_lab.selection.storage import SelectionLedger

__all__ = [
    "CandidateConfig",
    "SelectionError",
    "SelectionLedger",
    "load_analysis",
    "run_selection",
    "select_from_files",
    "select_from_payload",
]
