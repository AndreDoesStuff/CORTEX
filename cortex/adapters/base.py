"""Adapter contract. Every adapter takes a SourceConfig and emits Signals.

Adapters are READ-ONLY. They must never issue a write/mutation to any source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import httpx

from ..models import Signal
from ..registry import SourceConfig


class SourceSkipped(Exception):
    """Raised when a source can't run (e.g. missing creds, no repos configured).

    Non-fatal: the CLI reports it and continues with the other sources.
    """


class Adapter(ABC):
    #: registry `type` this adapter handles
    type: str

    def __init__(self, source: SourceConfig):
        self.source = source

    @abstractmethod
    def fetch(self, since: datetime | None, client: httpx.Client) -> list[Signal]:
        """Return normalized signals, optionally bounded to activity since `since`."""
        raise NotImplementedError
