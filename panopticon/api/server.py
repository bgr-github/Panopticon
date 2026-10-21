import uvicorn

from panopticon.config.settings import settings
from panopticon.observability.logger import configure_logging


def main() -> None:
    """Runs the REST and SSE API as a separate configured service"""

    configure_logging("API")
    uvicorn.run(
        "panopticon.api.app:app",
        host=settings.api.host,
        port=settings.api.port,
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
