from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | Path = ".env", override: bool = False) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a local .env file.

    Existing process environment variables win by default, so a temporary
    terminal override can still take precedence over the local file.
    """
    env_path = Path(path)
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if not key:
            continue
        if not override and key in os.environ:
            continue

        os.environ[key] = value
        loaded[key] = value

    return loaded


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
