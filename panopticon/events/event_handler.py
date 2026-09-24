from panopticon.events.models import BaseEvent


class EventHandler:

    def publish(self, event: BaseEvent) -> None:
        """Publish the event to the desired source

        Args:
            event (BaseEvent): Event to be published.
        """
        # TODO: This will publish to Redis stream
        print(event.model_dump_json())
