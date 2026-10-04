"""Project storage and process settings from their installed Python owners."""

import json
import os
import sys
from pathlib import Path

from cadrumo.core.config import Settings, load_settings
from cadrumo.core.i18n.render import output_language
from cadrumo.core.logging import LOG_FILE_FORMAT, default_log_file_path
from cadrumo.core.storage_environment import configured_storage_root, tool_storage_environment

STORAGE_ROOT_FIELD = "cadrumo_local_storage_root"
storage_variable = STORAGE_ROOT_FIELD.upper()
if STORAGE_ROOT_FIELD not in Settings.model_fields or storage_variable not in Settings.storage_env_var_names():
    raise SystemExit("storage_root_variable_unowned")
settings = load_settings()
storage = configured_storage_root()
if Path(settings.cadrumo_local_storage_root).resolve() != storage:
    raise SystemExit("storage_root_disagreement")
# Children re-resolve storage against their own working directory unless the
# resolved root travels with them as an absolute Settings value.
environment = dict(os.environ)
environment[storage_variable] = str(storage)
log_file = default_log_file_path()
json.dump(
    dict(
        environment=environment,
        storage=str(storage),
        storage_variable=storage_variable,
        cache=tool_storage_environment()["XDG_CACHE_HOME"],
        logs=str(log_file.parent),
        log_file=str(log_file),
        log_format=LOG_FILE_FORMAT,
        log_max_bytes=settings.cadrumo_log_file_max_bytes,
        log_backups=settings.cadrumo_log_file_backup_count,
        output_language=output_language(),
        home=str(Path.home().resolve()),
    ),
    sys.stdout,
)
