from collections.abc import Generator
from panopticon.adapters.postgres import Database


def get_database() -> Generator[Database, None, None]:
    """Database helper"""

    database: Database = Database()

    try:
        yield database
    finally:
        database.close()
