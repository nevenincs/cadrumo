"""Schema registration for the wizard-owned profile ``--json`` result payloads.

``ConfigProfileCreateResult`` and ``ConfigProfileEditResult`` are declared in
:mod:`cadrumo.application.wizard`, which is not one of the payload packages
``_ensure_result_schemas_registered`` walks. Their ``@register_schema``
decorators therefore only run if something under a payload package imports
them — without that, both profile verbs silently drop off the MCP surface.

This module exists to be that importer, and to be it ALONE. The re-export used
to sit in :mod:`_config_payloads`, which the ``config`` command group imports
transitively at group-resolution time; that pulled the whole wizard dependency
tail into every ``config`` verb — ``login`` included — and reddened the
cold-start guard in ``test_lazy_command_tree``. Nothing imports this module
eagerly: the registry walk loads it on demand when the manifest or the MCP
surface is built, which is exactly when the two schemas are needed and long
after argument parsing. Registration and cold start are both satisfied.

``register_schema`` is idempotent per class, so a later direct import of the
wizard package is harmless.
"""

from __future__ import annotations

from ...application.wizard import ConfigProfileCreateResult as ConfigProfileCreateResult
from ...application.wizard import ConfigProfileEditResult as ConfigProfileEditResult

__all__ = ["ConfigProfileCreateResult", "ConfigProfileEditResult"]
