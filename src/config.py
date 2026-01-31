import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict


DEFAULT_CONFIG = {
    "scan_interval_seconds": 5,
    "max_hash_file_size_mb": 10,
    "ui_scale": 1.0,
    "window_width": 900,
    "window_height": 600,
    "report_permissions": "0644",
}


@dataclass
class AppConfig:
    scan_interval_seconds: int
    max_hash_file_size_mb: int
    ui_scale: float
    window_width: int
    window_height: int
    report_permissions: str

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        if not os.path.exists(path):
            return cls(**DEFAULT_CONFIG)
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged: Dict[str, Any] = {**DEFAULT_CONFIG, **data}
        return cls(**merged)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2, ensure_ascii=False)

    def report_permissions_mode(self) -> int:
        try:
            return int(self.report_permissions, 8)
        except ValueError:
            return int(DEFAULT_CONFIG["report_permissions"], 8)
