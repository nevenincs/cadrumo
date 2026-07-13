"""Tests for the ``cadrumo app registry`` companion-absent verification guard.

The four registry verification verbs refuse instructively when the corpus source
binaries shipped in the optional ``cadrumo_data`` companion are absent. These tests
isolate the guard's control flow and message assembly (the real locale strings
and refusal type) from the heavy full-registry scan that decides whether the
binaries are present.
"""

from __future__ import annotations

import pytest

from ....application.registry import CORPUS_SOURCES_INSTALL_HINT
from ....core.i18n import tr
from .._errors import CliRefusedBoundaryError
from .._registry_corpus import refuse_when_corpus_companion_absent

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_guard_refusal_is_a_noop_when_no_companion_binary_is_absent() -> None:
    # A no-op returns without raising.
    refuse_when_corpus_companion_absent(
        capability=tr("cli.registry.errors.capability.registry_verify"),
        missing_advisories=(),
    )


def test_guard_refuses_instructively_when_a_companion_binary_is_absent() -> None:
    capability = tr("cli.registry.errors.capability.workbooks_verify")

    with pytest.raises(CliRefusedBoundaryError) as excinfo:
        refuse_when_corpus_companion_absent(
            capability=capability,
            missing_advisories=("corpus/aeat_official/disenos_registro/modelo_100/files/dr.xlsx",),
        )

    # Translation happens at the CLI render layer, so the refusal carries the
    # locale key plus the interpolation context rather than a pre-rendered string.
    error = excinfo.value
    assert error.translated_message == "cli.registry.errors.corpus_companion_absent"
    assert error.context is not None
    assert error.context["capability"] == capability
    assert error.context["install"] == CORPUS_SOURCES_INSTALL_HINT
