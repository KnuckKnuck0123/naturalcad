from __future__ import annotations

from collections import defaultdict, deque

_REQUESTS: dict[str, deque[float]] = defaultdict(deque)
_CACHE: dict[str, dict] = {}
_JOBS: dict[str, dict] = {}
_ARTIFACTS: dict[str, list[dict]] = defaultdict(list)
