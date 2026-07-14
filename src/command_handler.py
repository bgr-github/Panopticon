import copy
import importlib
import pkgutil
import commands
from logger import log_event
from filesystem import FakeFS


def load_commands():
    """
    Loads each Python file from the commands/ directory and saves them to a command registry.
    """

    registry = {}
    for _, module_name, _ in pkgutil.iter_modules(commands.__path__):
        module = importlib.import_module(f"commands.{module_name}")
        if not hasattr(module, "run"):
            continue

        if hasattr(module, "NAME"):
            name = module.NAME
        else:
            name = module_name

        registry[name] = {
            "name": name,
            "man": getattr(module, "MAN", None),
            "fn": module.run,
        }

    return registry


class CommandHandler:
    def __init__(self, process):
        self.process = process
        self.session = process.get_extra_info("session")
        self.profile = process.get_extra_info("profile")
        self.session["fs"] = FakeFS(copy.deepcopy(process.get_extra_info("fs")))
        self.session["cwd"] = f"/home/{self.session.get('username', 'guest')}"

        self.registry = load_commands()

        self.session["commands"] = sorted(self.registry.keys())
        self.session["registry"] = self.registry

    def command(self, cmd):
        """
        Each command is passed through here to run the corresponding module.
        """

        parts = cmd.split()
        if not parts:
            return
        name = parts[0]
        args = parts[1:]

        entry = self.registry.get(name)
        if entry is None:
            output = f"{name}: command not found"
        else:
            try:
                output = entry["fn"](args, self.session) or ""
            except Exception:
                output = ""
                import traceback

                traceback.print_exc()
                log_event("command_error", session=self.session["id"], command=cmd)

        if output and not output.endswith("\n"):
            output += "\n"
        self.process.stdout.write(output)
