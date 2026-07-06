"""
RemoteFlash — configuration persistence.

Loads/saves the user's profiles and preferences to a JSON file in the home
directory. The legacy filename is kept on purpose so existing profiles survive.
"""

import json
from dataclasses import asdict
from pathlib import Path

from models import ConnectionProfile

# Legacy filename kept on purpose: existing profiles survive the rename
CONFIG_FILE = Path.home() / ".ssh_flasher_pro.json"


class ConfigManager:
    @staticmethod
    def load() -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return ConfigManager._default_config()

    @staticmethod
    def save(config: dict):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2, default=str)

    @staticmethod
    def _default_config() -> dict:
        return {
            "profiles": [asdict(ConnectionProfile())],
            "active_profile_idx": 0,
            "ssh_timeout": 10,
            "remote_dir": "/tmp",
            "delete_after_flash": False,
            "command_history": [],
            "custom_commands": [
                "avrdude -p m328p -c usbasp -U flash:w:",
                "avrdude -p m128 -c usbasp -U flash:w:",
                "avrdude -p m2560 -c wiring -U flash:w:",
                "esptool.py write_flash 0x0",
                "dfu-util -D",
            ],
            "last_file_path": None,
        }
