"""Runtime-tunable settings stored in RPG_LLM_DATA (not committed)."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _data_dir() -> Path:
    return Path(os.getenv("RPG_LLM_DATA_DIR", "./RPG_LLM_DATA"))


def _settings_path() -> Path:
    return _data_dir() / "mattermost_bot" / "settings.json"


@dataclass
class RuntimeSettings:
    """
    A small, JSON-backed settings store.

    This is intentionally permissive: unknown keys are preserved, and values are
    validated only where we rely on them.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _cache: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _cache_mtime: float = field(default=0.0, init=False, repr=False)

    def load(self) -> Dict[str, Any]:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            try:
                stat = path.stat()
            except FileNotFoundError:
                self._cache = {}
                self._cache_mtime = 0.0
                return {}

            if stat.st_mtime <= self._cache_mtime and self._cache:
                return self._cache

            try:
                data = json.loads(path.read_text())
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}

            self._cache = data
            self._cache_mtime = stat.st_mtime
            return data

    def save(self, data: Dict[str, Any]) -> None:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
            tmp.replace(path)
            try:
                self._cache = data
                self._cache_mtime = path.stat().st_mtime
            except Exception:
                pass

    def get(self) -> Dict[str, Any]:
        return self.load()

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        data = self.load()
        merged = _deep_merge_dicts(data, patch)
        self.save(merged)
        return merged

    def set_path(self, dotted_path: str, value: Any) -> Dict[str, Any]:
        data = self.load()
        _set_dotted(data, dotted_path, value)
        self.save(data)
        return data


def _deep_merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_dicts(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def _set_dotted(obj: Dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = [p for p in dotted_path.split(".") if p]
    cur: Dict[str, Any] = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]  # type: ignore[assignment]
    if parts:
        cur[parts[-1]] = value


def parse_scalar(value: str) -> Any:
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    # int
    try:
        if v.isdigit() or (v.startswith("-") and v[1:].isdigit()):
            return int(v)
    except Exception:
        pass
    # float
    try:
        return float(v)
    except Exception:
        return v

