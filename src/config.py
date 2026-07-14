import yaml
from pathlib import Path


class ConfigError(Exception):
    """Exception raised when profile is missing required fields or malformed."""


# Sections and the keys each must contain
REQUIRED = {
    "host": ["hostname", "kernel_name", "kernel_release", "machine", "os"],
    "os_release": ["pretty_name", "id"],
    "filesystem": ["root"],
}


def load_profile(path):
    """Load a profile from YAML, validate and return dict."""

    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Profile not found: {path}")

    try:
        with open(path) as file:
            profile = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise ConfigError(f"Profile {path} is not valid YAML.: {error}")

    _validate(profile, path)

    return profile


def _validate(profile, path):
    """Validates the YAML profile."""

    if not isinstance(profile, dict):
        raise ConfigError(f"Profile: {path} must be a mapping at the top level.")

    for section, keys in REQUIRED.items():
        if section not in profile:
            raise ConfigError(f"Profile {path} is missing '{section}'.")
        if not isinstance(profile[section], dict):
            raise ConfigError(f"Profile {path}: '{section}' must be a mapping.")

        for key in keys:
            if key not in profile[section]:
                raise ConfigError(f"Profile {path}: '{section}' is missing '{key}'.")

    accounts = profile.get("accounts")
    if not accounts:
        raise ConfigError(f"Profile {path} does not define any accounts.")

    for i, account in enumerate(accounts):
        if "username" not in account:
            raise ConfigError(f"Profile {path}: account #{i+1} is missing 'username'.")
        account.setdefault("password", "")  # Absent password = no-password login.
