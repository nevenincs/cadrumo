"""Stream B invariant: REQUIRED_HEADER_FIELDS must reference real fields.

Every field_id listed in a schema's ``REQUIRED_HEADER_FIELDS`` must
exist as a :class:`RecordFieldSpec.field_id` in at least one segment
(for envelopes) or in the top-level ``RECORD_SPECS`` tuple (for
record-style schemas). Otherwise the serialiser's required-header
check is unsatisfiable — every call fails at the boundary with a
"required header X missing" error even when the caller supplied
everything they could.

Locks a sneaky drift class: someone adds a header to
``REQUIRED_HEADER_FIELDS`` without also adding the corresponding
field, or renames a field without updating the required set.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from . import modelo_130_2024, modelo_130_2025, modelo_303_2024, modelo_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _record_field_ids(module: ModuleType) -> frozenset[str]:
    return frozenset(s.field_id for s in module.RECORD_SPECS)


def _envelope_field_ids(module: ModuleType) -> frozenset[str]:
    out: set[str] = set()
    for seg in module.ENVELOPE:
        for s in seg.specs:
            out.add(s.field_id)
    return frozenset(out)


class TestRequiredHeadersResolvable:
    @pytest.mark.parametrize(
        "module",
        [modelo_130_2024, modelo_130_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_record_required_headers_all_exist(self, module: ModuleType) -> None:
        required = module.REQUIRED_HEADER_FIELDS
        field_ids = _record_field_ids(module)
        missing = required - field_ids
        assert not missing, (
            f"{module.__name__}: REQUIRED_HEADER_FIELDS names fields with no "
            f"matching RecordFieldSpec: {sorted(missing)}. Either add the field "
            f"to RECORD_SPECS or drop it from REQUIRED_HEADER_FIELDS."
        )

    @pytest.mark.parametrize(
        "module",
        [modelo_303_2024, modelo_303_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_envelope_required_headers_all_exist(self, module: ModuleType) -> None:
        required = module.REQUIRED_HEADER_FIELDS
        field_ids = _envelope_field_ids(module)
        missing = required - field_ids
        assert not missing, (
            f"{module.__name__}: REQUIRED_HEADER_FIELDS names fields with no "
            f"matching RecordFieldSpec in any ENVELOPE segment: {sorted(missing)}. "
            f"Either add the field or drop it from the required set."
        )

    @pytest.mark.parametrize(
        "module",
        [modelo_303_2024, modelo_303_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_envelope_required_headers_are_non_reserved(self, module: ModuleType) -> None:
        """Every required header must target a USER-SUPPLIED field (ALPHANUMERIC
        / NUMERIC / DATE). A RESERVED field carries a fixed literal that the
        caller can't influence; listing it as required misuses the contract.
        """
        from ._record_spec import FieldKind  # local import keeps top clean

        required = set(module.REQUIRED_HEADER_FIELDS)
        reserved_hits: list[tuple[str, str]] = []
        for seg in module.ENVELOPE:
            for s in seg.specs:
                if s.field_id in required and s.kind is FieldKind.RESERVED:
                    reserved_hits.append((seg.segment_id, s.field_id))
        assert not reserved_hits, (
            f"{module.__name__}: REQUIRED_HEADER_FIELDS lists RESERVED fields "
            f"(they carry fixed literals; callers can't change them): {reserved_hits}"
        )
