"""Core package. Import submodules directly (e.g. ``app.core.config``)."""

from typing import Any

__all__ = ["settings"]


def __getattr__(name: str) -> Any:
    if name == "settings":
        from app.core.config import settings

        return settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
