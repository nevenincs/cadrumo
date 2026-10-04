"""Project storage and process settings from their installed Python owners."""

import json
import os
import sys

from cadrumo.core.config import load_settings
from cadrumo.core.logging import default_log_file_path
from cadrumo.core.storage_environment import configured_storage_root, tool_storage_environment

settings = load_settings()
json.dump(
    dict(
        environment=dict(os.environ),
        storage=str(configured_storage_root()),
        cache=tool_storage_environment()["XDG_CACHE_HOME"],
        logs=str(default_log_file_path().parent),
        log_max_bytes=settings.cadrumo_log_file_max_bytes,
        log_backups=settings.cadrumo_log_file_backup_count,
    ),
    sys.stdout,
)
