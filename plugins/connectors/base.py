"""Shared types for connectors (incremental migration)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConnectorResult:
    success: bool
    data: Any = None
    error_code: Optional[str] = None
    quality_status: str = "ok"
    attempts: List[Dict[str, Any]] = field(default_factory=list)
