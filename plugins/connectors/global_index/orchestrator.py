"""P2 pilot: single import surface for global index spot (delegates to fetch_global)."""

from __future__ import annotations

from typing import Any, Dict

from plugins.data_collection.index import fetch_global as _fg


def run_global_index_spot(**kwargs: Any) -> Dict[str, Any]:
    """Thin orchestrator; keeps JSON contract identical to ``fetch_global_index_spot``."""
    return _fg.fetch_global_index_spot(**kwargs)
