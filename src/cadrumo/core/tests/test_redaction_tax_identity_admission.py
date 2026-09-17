"""The redaction funnel asks the host-bound gate before hashing a tax identity.

The gate is the only thing that separates a real identity from an identifier
of the same shape, so these tests bind explicit gates and prove the funnel
follows each answer: a refusal leaves the span alone, an admission hashes it,
and a gate that cannot answer falls back to lexical shape rather than letting
a candidate through unexamined.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from ..redaction.rules import redact_for_cli_output, redact_for_log
from ..redaction.tax_identity_admission import bind_tax_identity_admission, tax_identity_admission

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CIF_SHAPED = "B99999999"
_NIF_IVA_SHAPED = "SE556677889901"


@dataclass(frozen=True)
class _FixedAdmission:
    answer: bool | None

    def admits_spanish_identity(self, normalised: str) -> bool | None:
        return self.answer

    def admits_nif_iva(self, normalised: str) -> bool | None:
        return self.answer


@pytest.fixture
def unbound() -> Iterator[None]:
    """Suspend the host gate so the funnel's own fallback is observable."""
    with bind_tax_identity_admission(None):
        yield


def _hashed(value: str) -> bool:
    line = f"counterparty {value} declared"
    return value not in redact_for_log(line) and value not in redact_for_cli_output(line)


@pytest.mark.parametrize("value", [_CIF_SHAPED, _NIF_IVA_SHAPED])
def test_a_refusing_gate_leaves_the_span_alone(value: str) -> None:
    with bind_tax_identity_admission(_FixedAdmission(answer=False)):
        assert not _hashed(value)


@pytest.mark.parametrize("value", [_CIF_SHAPED, _NIF_IVA_SHAPED])
def test_an_admitting_gate_hashes_the_span(value: str) -> None:
    with bind_tax_identity_admission(_FixedAdmission(answer=True)):
        assert _hashed(value)


@pytest.mark.parametrize("value", [_CIF_SHAPED, _NIF_IVA_SHAPED])
def test_a_gate_without_authority_falls_back_to_shape(value: str) -> None:
    with bind_tax_identity_admission(_FixedAdmission(answer=None)):
        assert _hashed(value)


@pytest.mark.usefixtures("unbound")
@pytest.mark.parametrize("value", [_CIF_SHAPED, _NIF_IVA_SHAPED])
def test_an_unbound_host_falls_back_to_shape(value: str) -> None:
    assert tax_identity_admission() is None
    assert _hashed(value)


def test_a_cached_answer_is_not_reused_under_another_gate() -> None:
    line = f"counterparty {_CIF_SHAPED} declared"
    with bind_tax_identity_admission(_FixedAdmission(answer=False)):
        assert _CIF_SHAPED in redact_for_cli_output(line)
    with bind_tax_identity_admission(_FixedAdmission(answer=True)):
        assert _CIF_SHAPED not in redact_for_cli_output(line)


def test_binding_restores_the_previous_gate() -> None:
    outer = _FixedAdmission(answer=True)
    inner = _FixedAdmission(answer=False)
    with bind_tax_identity_admission(outer):
        with bind_tax_identity_admission(inner):
            assert tax_identity_admission() is inner
        assert tax_identity_admission() is outer
