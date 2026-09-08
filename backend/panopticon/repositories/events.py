from panopticon.adapters.postgres import Database


class EventRepository:

    database: Database

    def __init__(self, database: Database):
        self.database = database
