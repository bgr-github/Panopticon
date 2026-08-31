import asyncio

from panopticon.events.event_handler import EventHandler
from panopticon.events.models import ConnectionOpen


class FakeRedis:
    def __init__(self, message_id: bytes | str = b"1-0") -> None:
        self.message_id = message_id
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []

    async def xadd(self, stream_name: str, fields: dict[str, str]) -> bytes | str:
        self.xadd_calls.append((stream_name, fields))
        return self.message_id


def test_publish_writes_event_json_to_configured_stream(monkeypatch) -> None:
    from panopticon.events import event_handler as event_handler_module

    fake_redis = FakeRedis()
    monkeypatch.setattr(
        event_handler_module.Redis,
        "from_url",
        staticmethod(lambda *args, **kwargs: fake_redis),
    )

    handler = EventHandler()
    event = ConnectionOpen(session_id="session-1", src_ip="127.0.0.1", src_port=54321)

    message_id = asyncio.run(handler.publish(event))

    assert message_id == "1-0"
    assert len(fake_redis.xadd_calls) == 1

    stream_name, fields = fake_redis.xadd_calls[0]
    assert stream_name == event_handler_module.settings.redis.stream_name
    assert set(fields) == {"event"}
    assert '"event_type":"connection_open"' in fields["event"]


def test_publish_returns_string_message_id_when_redis_returns_string(monkeypatch) -> None:
    from panopticon.events import event_handler as event_handler_module

    fake_redis = FakeRedis(message_id="2-0")
    monkeypatch.setattr(
        event_handler_module.Redis,
        "from_url",
        staticmethod(lambda *args, **kwargs: fake_redis),
    )

    handler = EventHandler()
    event = ConnectionOpen(session_id="session-1", src_ip="127.0.0.1", src_port=54321)

    assert asyncio.run(handler.publish(event)) == "2-0"


def test_publish_background_schedules_publish(monkeypatch) -> None:
    from panopticon.events import event_handler as event_handler_module

    fake_redis = FakeRedis()
    monkeypatch.setattr(
        event_handler_module.Redis,
        "from_url",
        staticmethod(lambda *args, **kwargs: fake_redis),
    )

    async def run_test() -> None:
        handler = EventHandler()
        event = ConnectionOpen(session_id="session-1", src_ip="127.0.0.1", src_port=54321)

        handler.publish_background(event)
        await asyncio.sleep(0)

        assert len(fake_redis.xadd_calls) == 1

    asyncio.run(run_test())


def test_publish_callback_logs_task_failures(monkeypatch) -> None:
    from panopticon.events import event_handler as event_handler_module

    logged_errors: list[str] = []
    monkeypatch.setattr(
        event_handler_module.logger,
        "error",
        lambda module, message: logged_errors.append(message),
    )

    handler = EventHandler()

    async def run_test() -> None:
        task = asyncio.create_task(_raise_publish_error())

        await asyncio.sleep(0)
        handler._publish_callback(task)

    asyncio.run(run_test())

    assert logged_errors == ["Failed to publish event: redis unavailable"]


async def _raise_publish_error() -> None:
    raise RuntimeError("redis unavailable")
