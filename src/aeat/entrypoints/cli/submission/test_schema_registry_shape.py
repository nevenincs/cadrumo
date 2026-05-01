"""Stream B invariant: SCHEMA_REGISTRY entry shape consistency (wave 123).

Every :class:`SchemaEntry` in ``SCHEMA_REGISTRY`` pairs a schema
module with a ``kind`` tag (``"record"`` or ``"envelope"``) and a
header-builder function. A mis-paired entry (e.g., a record-style
module registered with ``kind="envelope"``) would make the CLI
dispatch attempt ``serialise_envelope`` on a module that has no
``ENVELOPE`` attribute — crashing at call time rather than at
registry load.

Wave 123 locks the pairing at collection so the failure surface
is the registry, not Kent's next ``aeat submission export`` run.

Rules enforced per entry:

- ``kind == "record"`` → module must expose ``RECORD_SPECS`` (tuple)
  and ``RECORD_LENGTH`` (int), and must NOT expose ``ENVELOPE``.
- ``kind == "envelope"`` → module must expose ``ENVELOPE`` (tuple)
  and must NOT expose ``RECORD_SPECS``.
- Every entry's ``build_headers`` callable must accept a
  :class:`CliInputs` and return a ``dict[str, str]``.
- Registry keys must follow ``(modelo, ejercicio)`` string pair
  convention, where modelo is a 3-digit numeric string and
  ejercicio is a 4-digit numeric string.
"""

from __future__ import annotations

import re

import pytest

from ._schema_registry import SCHEMA_REGISTRY, CliInputs, SchemaEntry

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_MODELO_RE = re.compile(r"^\d{3}$")
_EJERCICIO_RE = re.compile(r"^\d{4}$")


class TestRegistryEntryShape:
    @pytest.mark.parametrize(
        ("key", "entry"),
        sorted(SCHEMA_REGISTRY.items()),
        ids=lambda v: ".".join(v) if isinstance(v, tuple) else repr(v)[:20],
    )
    def test_record_kind_has_record_attributes(self, key: tuple[str, str], entry: SchemaEntry) -> None:
        if entry.kind != "record":
            pytest.skip("envelope entry")
        mod = entry.module
        assert hasattr(mod, "RECORD_SPECS"), f"{mod.__name__}: missing RECORD_SPECS"
        assert hasattr(mod, "RECORD_LENGTH"), f"{mod.__name__}: missing RECORD_LENGTH"
        assert not hasattr(mod, "ENVELOPE"), (
            f"{mod.__name__}: kind='record' but module exposes ENVELOPE — fix the registry tag or the module."
        )
        assert isinstance(mod.RECORD_LENGTH, int) and mod.RECORD_LENGTH > 0

    @pytest.mark.parametrize(
        ("key", "entry"),
        sorted(SCHEMA_REGISTRY.items()),
        ids=lambda v: ".".join(v) if isinstance(v, tuple) else repr(v)[:20],
    )
    def test_envelope_kind_has_envelope_attributes(self, key: tuple[str, str], entry: SchemaEntry) -> None:
        if entry.kind != "envelope":
            pytest.skip("record entry")
        mod = entry.module
        assert hasattr(mod, "ENVELOPE"), f"{mod.__name__}: missing ENVELOPE"
        assert not hasattr(mod, "RECORD_SPECS"), (
            f"{mod.__name__}: kind='envelope' but module exposes RECORD_SPECS — fix the registry tag or the module."
        )
        assert len(mod.ENVELOPE) >= 1

    @pytest.mark.parametrize(
        ("key", "entry"),
        sorted(SCHEMA_REGISTRY.items()),
        ids=lambda v: ".".join(v) if isinstance(v, tuple) else repr(v)[:20],
    )
    def test_build_headers_returns_dict(self, key: tuple[str, str], entry: SchemaEntry) -> None:
        """Calling build_headers with a minimal valid CliInputs must return a
        ``dict[str, str]`` — proves the callable is shape-compatible with the
        serialiser's expected headers mapping."""
        ejercicio = key[1]
        inputs = CliInputs(
            ejercicio=ejercicio,
            periodo="1T",
            nif="X1234567L",
            apellidos="DOE RODRIGUEZ",
            nombre="KENT",
            tipo_declaracion="I",
        )
        headers = entry.build_headers(inputs)
        assert isinstance(headers, dict), f"{key} build_headers returned {type(headers).__name__}, expected dict"
        assert headers, f"{key} build_headers returned empty dict"
        for k, v in headers.items():
            assert isinstance(k, str), f"{key} build_headers yielded non-str key {k!r}"
            assert isinstance(v, str), f"{key} build_headers yielded non-str value for {k!r}: {v!r}"

    @pytest.mark.parametrize(
        ("key", "entry"),
        sorted(SCHEMA_REGISTRY.items()),
        ids=lambda v: ".".join(v) if isinstance(v, tuple) else repr(v)[:20],
    )
    def test_required_headers_covered_by_build_headers(self, key: tuple[str, str], entry: SchemaEntry) -> None:
        """Every field in the module's REQUIRED_HEADER_FIELDS must be populated
        by the registry's build_headers — otherwise a default ``aeat submission
        export`` call would always fail the required-header guard even though
        the registry claimed the modelo is supported."""
        inputs = CliInputs(
            ejercicio=key[1],
            periodo="1T",
            nif="X1234567L",
            apellidos="DOE",
            nombre="KENT",
            tipo_declaracion="I",
        )
        headers = entry.build_headers(inputs)
        required = set(entry.module.REQUIRED_HEADER_FIELDS)
        uncovered = required - set(headers.keys())
        assert not uncovered, (
            f"{key} build_headers misses required fields {sorted(uncovered)} — "
            f"a default export would fail the required-header guard."
        )


class TestRegistryKeyShape:
    @pytest.mark.parametrize(
        "key",
        sorted(SCHEMA_REGISTRY.keys()),
        ids=lambda k: ".".join(k),
    )
    def test_key_is_two_string_tuple(self, key: tuple[str, str]) -> None:
        assert isinstance(key, tuple) and len(key) == 2
        modelo, ejercicio = key
        assert _MODELO_RE.match(modelo), f"modelo key {modelo!r} does not match ^\\d{{3}}$"
        assert _EJERCICIO_RE.match(ejercicio), f"ejercicio key {ejercicio!r} does not match ^\\d{{4}}$"
