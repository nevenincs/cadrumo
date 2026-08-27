"""The redaction exemption list is the stdlib's field set, not the factory's.

:class:`SecretScrubbingFilter` scrubs every field on a record EXCEPT those in
``_STANDARD_LOG_RECORD_FIELDS``. That makes the set an exemption list, and its
membership decides what escapes redaction untouched.

It was built with ``logging.makeLogRecord({})``, which dispatches through the
process-global record factory rather than constructing a plain record. Any
field an installed factory adds therefore enrolled ITSELF as "standard" and was
skipped by the scrubber -- an exemption widened by global state that anything in
the process, including a third-party library, can set.

The same call was also the reason this module could not import while a factory
was installed: it invoked the factory during its own initialisation, and
cadrumo's factory reaches the observability layer, which imports straight back
into the half-built module.

Both halves are asserted through a real subprocess import, because the
condition is "a factory was installed BEFORE this module initialised" and that
cannot be staged in a process where it has already been imported.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

import pytest

from ..logging import _STANDARD_LOG_RECORD_FIELDS, SecretScrubbingFilter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Reproduces the real import order: cadrumo's OWN factory is installed, the
#: package is purged, and the module is imported afresh. The factory reaches
#: the observability layer, which imports back into the initialising module.
_CYCLE_PROBE = """
import sys
from cadrumo.core.logging import _install_run_context_record_factory

_install_run_context_record_factory()
for name in [n for n in sys.modules if n.startswith('cadrumo')]:
    del sys.modules[name]

import cadrumo.core.logging  # noqa: F401,E402
"""

#: Installs a factory that stamps an extra field, then reports what the freshly
#: imported module counted as standard. Mirrors the real hazard: the factory is
#: in place before ``cadrumo.core.logging`` is first imported.
_PROBE = (
    "import json, logging\n"
    "def factory(*args, **kwargs):\n"
    "    record = logging.LogRecord(*args, **kwargs)\n"
    "    record.smuggled = 'value that must not escape scrubbing'\n"
    "    return record\n"
    "logging.setLogRecordFactory(factory)\n"
    "from cadrumo.core.logging import _STANDARD_LOG_RECORD_FIELDS as fields\n"
    "print(json.dumps(sorted(fields)))\n"
)


def _exemption_set_after_factory_install() -> list[str]:
    """Import the module in a process where a factory is already installed."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline probe reproduce the import order.
        [sys.executable, "-c", _PROBE],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return list(json.loads(completed.stdout))


def test_a_factory_added_field_never_enters_the_exemption_set() -> None:
    """DISCRIMINATING: the field a factory adds must not exempt itself.

    Built through ``makeLogRecord`` this is the failing direction -- the
    factory's own field lands in the set that decides what the scrubber skips.
    """
    assert "smuggled" not in _exemption_set_after_factory_install()


def test_the_module_imports_while_its_own_factory_is_installed() -> None:
    """The other half: the factory must not run during this module's own init.

    Reproduced with cadrumo's real factory rather than the probe factory above,
    which adds a field but imports nothing -- only the real one reaches the
    observability layer, and that reach is what closes the cycle.
    """
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline probe reproduce the import order.
        [sys.executable, "-c", _CYCLE_PROBE],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_the_exemption_set_still_holds_the_stdlib_fields() -> None:
    """ANTI-TAUTOLOGY: an empty set would satisfy the exclusion above.

    Emptying ``_STANDARD_LOG_RECORD_FIELDS`` would pass every "not in" check
    here while scrubbing fields the stdlib owns, so the set is pinned to the
    plain record's own fields.
    """
    assert frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) == _STANDARD_LOG_RECORD_FIELDS
    assert {"levelname", "pathname", "thread"} <= _STANDARD_LOG_RECORD_FIELDS


def test_the_filter_scrubs_a_field_outside_the_exemption_set() -> None:
    """The consequence the exemption list governs, asserted end to end.

    A field the set does not cover reaches the scrubber; this is what a
    factory-added field silently stopped doing once it enrolled itself.
    """
    record = logging.LogRecord("probe", logging.INFO, "", 0, "", None, None)
    record.smuggled = "12345678Z"

    assert SecretScrubbingFilter().filter(record) is True
    assert "12345678Z" not in str(getattr(record, "smuggled", ""))
