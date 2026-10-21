from typing import Protocol

from panopticon.events.models import BaseEvent


class EventStore(Protocol):
    """Storage contract used by the event collector independently of the database."""

    def initialise(self) -> None:
        """Prepares storage before the collector accepts events"""

        ...

    def save(self, event: BaseEvent) -> None:
        """Commits an event without duplicating an already stored event ID

        Args:
            event (BaseEvent): Event to persist
        """

        ...
