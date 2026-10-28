"""Logging imports what it needs on the host's thread, never on a logging thread.

A cold import of the settings graph is the slowest step in configuring logging,
and the delivery path binds more modules lazily to step around import cycles.
When the dispatch thread performs those imports, a flush right after
``configure_logging()`` waits on module I/O, and a producer's own first-record
import shares pydantic with that graph and waits on the same import locks. The
probes assert which thread loads which module, so they hold on any machine
speed; their generous bounds only guard against a hang.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ..type_guards import is_object_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DELIVERY_MODULES = (
    "cadrumo.core.config",
    "cadrumo.core.config_state_root",
    "cadrumo.core.log_file_handler",
    "cadrumo.core.observability.context",
    "cadrumo.core.classification.policies",
    "cadrumo.core.identity.documents",
    "cadrumo.core.identity.nif_iva",
    "cadrumo.core.authentication_links",
)

_PROBE = """
import json, logging, sys, threading
imports = []
def observe(event, args):
    if event == 'import':
        imports.append((threading.current_thread().name, args[0]))
sys.addaudithook(observe)
from cadrumo.core import logging as project

logger = project.get_logger('cadrumo.tests.delivery_imports')
project.configure_logging()
returned = len(imports)
loaded_by = {}
for thread, module in imports:
    loaded_by.setdefault(module, thread)

# These race the dispatch thread's configuration: the producer may import nothing.
logger.warning('record made while configuration runs %s', 'x')
logger.info('second record made while configuration runs')
producer_imports = [module for thread, module in imports[returned:] if thread == 'MainThread']
assert project.flush_logging(timeout=60), project.diagnostic_delivery_status()

settled = len(imports)
logger.warning(
    'identity %s account %s url %s header %s',
    'B12345678', 'ES9121000418450200051332', 'https://sede.agenciatributaria.gob.es/Sede/x?token=abc', 'Bearer abc.def',
    extra={'password': 'synthetic'},
)
logging.getLogger('synthetic.third_party').warning('foreign password=synthetic B12345678')
try:
    raise ValueError('synthetic')
except ValueError:
    logger.exception('exception record')
logger.info('structured %s', {'key': [1, 2]})
assert project.flush_logging(timeout=60), project.diagnostic_delivery_status()
print(json.dumps({
    'loaded_by': {module: loaded_by.get(module) for module in sys.argv[1:]},
    'producer_imports': producer_imports,
    'late_imports': [[thread, module] for thread, module in imports[settled:]],
}))
"""

_METADATA_PROBE = """
import json, sys
sys.argv = ['aeat', '--version']
from cadrumo.core import logging as project

project.configure_logging()
assert project.flush_logging(timeout=60), project.diagnostic_delivery_status()
print(json.dumps({'settings_loaded': 'cadrumo.core.config' in sys.modules}))
"""


def _run(tmp_path: Path, script: str, *arguments: str) -> dict[str, object]:
    completed = run_audited_process(
        [sys.executable, "-c", script, *arguments],
        env={
            **os.environ,
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "root"),
            "CADRUMO_LOG_DIR": str(tmp_path / "logs"),
            "CADRUMO_LOG_STDERR_LEVEL": "CRITICAL",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    loaded: object = json.loads(str(completed.stdout))
    assert is_object_mapping(loaded)
    return {str(key): value for key, value in loaded.items()}


@pytest.fixture(scope="module")
def delivery_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return _run(tmp_path_factory.mktemp("delivery_imports"), _PROBE, *_DELIVERY_MODULES)


def test_the_host_thread_loads_every_delivery_module_before_configure_logging_returns(
    delivery_report: dict[str, object],
) -> None:
    assert delivery_report["loaded_by"] == {module: "MainThread" for module in _DELIVERY_MODULES}


def test_a_record_made_while_configuration_runs_imports_nothing_on_the_producer(
    delivery_report: dict[str, object],
) -> None:
    assert delivery_report["producer_imports"] == []


def test_records_of_every_redaction_shape_need_no_import_once_configuration_has_settled(
    delivery_report: dict[str, object],
) -> None:
    assert delivery_report["late_imports"] == []


def test_a_metadata_invocation_configures_without_loading_settings(tmp_path: Path) -> None:
    assert _run(tmp_path, _METADATA_PROBE)["settings_loaded"] is False
