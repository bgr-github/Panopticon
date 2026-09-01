from enum import StrEnum

# Common fields shared between all events
COMMON_FIELDS: set[str] = {
    "id",
    "session_id",
    "event_type",
    "src_ip",
    "src_port",
    "timestamp",
}


# All module names as strings
class Module(StrEnum):
    SSH = "SSH"
    INGESTION = "Ingestion"
    EVENT_HANDLER = "Event Handler"
    API = "API"
    DATABASE = "Database"
