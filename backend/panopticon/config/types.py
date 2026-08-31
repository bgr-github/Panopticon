from enum import Enum


class ModuleType(str, Enum):
    ssh = "SSH"
    event_handler = "Event Handler"
