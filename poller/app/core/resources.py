"""Shared async resource protocols for application-managed components."""
from typing import Protocol


class AsyncResource(Protocol):
    """Lifecycle-managed async resource."""

    async def start(self) -> None:
        """Start the resource."""

    async def stop(self) -> None:
        """Stop the resource."""
