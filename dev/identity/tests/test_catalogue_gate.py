"""The catalogue-convention gate, and the proofs that it fires on each kind of violation.

The gate accepts an identifier in tests and fixtures only as a role value inside
its own persona or a generated projection, a generic pool member or a refusal.
Each proof plants one value in a real file of an isolated directory and drives
the real scan and the real checksum; the catalogue under test is a small one
written here, so no result depends on the live catalogue. A final group reads
the live catalogue for the invariants the gate relies on.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

from ..catalogue_gate import (
    CATALOGUE_PATH,
    CatalogueError,
    ConventionViolation,
    classify,
    in_gate_scope,
    parse_catalogue,
    read_catalogue,
    scan_convention,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CONTROL_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _nif(counter: int) -> str:
    """A checksum-valid NIF built from its counter, so no literal is spelled for the gate to read."""
    return f"{counter:08d}{_CONTROL_LETTERS[counter % 23]}"


# Checksum-valid values. The two role values lie in the live generic pool and the
# unbound and refusal values are built, so this file states nothing the live
# gate would refuse; the isolated catalogue below is what binds them.
_ROLE_FIRST = "00001001N"
_ROLE_SECOND = "00001002J"
_POOL_EXPLICIT = "12345678Z"
_POOL_NIF_RANGE = "00001003Z"
_POOL_CIF_RANGE = "B00010009"
_POOL_NIE_RANGE = "Y0001000W"
_POOL_PREFIXED_NIF_RANGE = "K0001000B"
_UNBOUND = _nif(99)
_LISTED_REFUSAL = _nif(28)

_LAST_INSIDE = 1999

_CATALOGUE: dict[str, object] = {
    "format": 1,
    "convention": {
        "generic_pool": {
            "values": [_POOL_EXPLICIT],
            "ranges": [
                {"kind": "nif", "first": 1003, "last": _LAST_INSIDE},
                {"kind": "nie", "letters": ["X", "Y", "Z"], "first": 1000, "last": _LAST_INSIDE},
                {"kind": "prefixed_nif", "letters": ["K", "L", "M"], "first": 1000, "last": _LAST_INSIDE},
                {"kind": "cif", "letters": ["B"], "first": 1000, "last": _LAST_INSIDE},
            ],
        },
        "generated_projections": {"paths": ["docs/_sequences/"]},
    },
    "identities": [
        {"role": "uno.titular", "persona": "uno", "kind": "nif", "value": _ROLE_FIRST},
        {"role": "dos.titular", "persona": "dos", "kind": "nif", "value": _ROLE_SECOND},
    ],
    "refusals": [{"value": _LISTED_REFUSAL, "kind": "nif", "reason": "listed on purpose"}],
}


def _nie(letter: str, counter: int) -> str:
    """A checksum-valid NIE built from the official table, letter replaced by its digit first."""
    return f"{letter}{counter:07d}{_CONTROL_LETTERS[int(str(' XYZ'.index(letter) - 1) + f'{counter:07d}') % 23]}"


def _cif(letter: str, counter: int) -> str:
    """A checksum-valid CIF of a digit-control kind, from the official odd/even digit sum."""
    total = 0
    for position, digit in enumerate(f"{counter:07d}"):
        value = int(digit) * (2 if position % 2 == 0 else 1)
        total += value // 10 + value % 10
    return f"{letter}{counter:07d}{(10 - total % 10) % 10}"


def _plant(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _violations(root: Path, relative: str, value: str) -> list[ConventionViolation]:
    _plant(root, relative, f"tax_id = '{value}'\n")
    scan = scan_convention(root, catalogue=parse_catalogue(_CATALOGUE))
    return [finding.violation for finding in scan.findings if finding.path == relative]


def test_a_value_bound_to_no_role_and_outside_the_pool_is_off_convention(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_a.py", _UNBOUND) == [ConventionViolation.OFF_CONVENTION]


def test_a_persona_role_value_used_in_a_test_is_role_reuse_and_names_the_role(tmp_path: Path) -> None:
    _plant(tmp_path, "src/pkg/tests/test_b.py", f"tax_id = '{_ROLE_FIRST}'\n")
    scan = scan_convention(tmp_path, catalogue=parse_catalogue(_CATALOGUE))
    assert [(finding.violation, finding.role) for finding in scan.findings] == [
        (ConventionViolation.ROLE_REUSE, "uno.titular")
    ]


def test_a_finding_renders_without_the_value(tmp_path: Path) -> None:
    _plant(tmp_path, "src/pkg/tests/test_b.py", f"tax_id = '{_ROLE_FIRST}'\n")
    scan = scan_convention(tmp_path, catalogue=parse_catalogue(_CATALOGUE))
    assert scan.findings
    assert all(_ROLE_FIRST not in finding.rendered() for finding in scan.findings)


def test_an_es_prefixed_spelling_is_the_same_value(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_c.py", f"ES{_ROLE_SECOND}") == [ConventionViolation.ROLE_REUSE]


@pytest.mark.parametrize(
    "value", [_POOL_EXPLICIT, _POOL_NIF_RANGE, _POOL_CIF_RANGE, _POOL_NIE_RANGE, _POOL_PREFIXED_NIF_RANGE]
)
def test_a_generic_pool_member_is_accepted(tmp_path: Path, value: str) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_d.py", value) == []


def test_a_role_value_is_accepted_inside_its_own_persona_only() -> None:
    catalogue = parse_catalogue(_CATALOGUE)
    assert classify(catalogue, "dev/fixtures/personas/uno/persona.toml", _ROLE_FIRST) is None
    assert classify(catalogue, "dev/fixtures/personas/dos/persona.toml", _ROLE_FIRST) == (
        ConventionViolation.ROLE_REUSE,
        "uno.titular",
    )


def test_a_role_value_is_accepted_in_a_generated_projection(tmp_path: Path) -> None:
    assert _violations(tmp_path, "docs/_sequences/how-to/demo.seq", _ROLE_FIRST) == []


def test_an_unbound_value_is_still_refused_in_a_generated_projection(tmp_path: Path) -> None:
    assert _violations(tmp_path, "docs/_sequences/how-to/demo.seq", _UNBOUND) == [ConventionViolation.OFF_CONVENTION]


def test_a_listed_refusal_value_is_accepted() -> None:
    assert classify(parse_catalogue(_CATALOGUE), "src/pkg/tests/test_e.py", _LISTED_REFUSAL) is None


def test_source_outside_tests_and_fixtures_is_not_governed(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/module.py", _UNBOUND) == []


@pytest.mark.parametrize(
    ("relative", "governed"),
    [
        ("src/cadrumo/application/tests/test_x.py", True),
        ("dev/registry/tests/test_x.py", True),
        ("native/desktop/frontend/tests/model.spec.ts", True),
        ("native/application/src/runtime_client/tests/live.rs", True),
        ("src/cadrumo/tests/fixtures/financial/export.csv", True),
        ("native/desktop/frontend/src/dev/fixtures/userProfile.json", True),
        ("docs/_sequences/seeds/demo.seq", True),
        ("src/cadrumo/application/module.py", False),
        ("dev/fixtures/personas/identities.toml", False),
        ("tests/test_x.py", False),
    ],
)
def test_the_gate_governs_the_declared_test_and_fixture_trees(relative: str, governed: bool) -> None:
    assert in_gate_scope(relative) is governed


def test_a_pool_value_bound_to_a_role_is_refused_when_the_catalogue_is_read() -> None:
    clashing = {
        **_CATALOGUE,
        "identities": [{"role": "uno.titular", "persona": "uno", "kind": "nif", "value": _POOL_NIF_RANGE}],
    }
    with pytest.raises(CatalogueError, match="inside the generic pool"):
        parse_catalogue(clashing)


def test_a_catalogue_without_a_pool_is_refused() -> None:
    with pytest.raises(CatalogueError, match="generic_pool"):
        parse_catalogue({"format": 1, "convention": {}, "identities": []})


def test_the_live_catalogue_keeps_the_wide_generic_values_out_of_every_role() -> None:
    catalogue = read_catalogue(REPO_ROOT)
    for value in ("12345678Z", "00000000T"):
        assert catalogue.in_pool(value)
        assert value not in catalogue.roles


def test_the_live_catalogue_lies_where_the_gate_reads_it() -> None:
    assert (REPO_ROOT / CATALOGUE_PATH).is_file()


def test_a_dni_with_a_valid_check_letter_outside_the_pool_is_refused(tmp_path: Path) -> None:
    outside = _nif(30_000_000)
    assert outside[-1] == _CONTROL_LETTERS[30_000_000 % 23]
    assert _violations(tmp_path, "src/pkg/tests/test_f.py", outside) == [ConventionViolation.OFF_CONVENTION]


def test_a_nie_with_a_valid_check_letter_outside_the_pool_is_refused(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_g.py", _nie("X", 5_000_000)) == [
        ConventionViolation.OFF_CONVENTION
    ]


def test_a_cif_with_a_valid_control_outside_the_pool_is_refused(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_h.py", _cif("B", 5_000_000)) == [
        ConventionViolation.OFF_CONVENTION
    ]


@pytest.mark.parametrize(
    ("make", "first_inside", "last_inside"),
    [
        (lambda counter: _nie("Y", counter), 1000, _LAST_INSIDE),
        (lambda counter: _cif("B", counter), 1000, _LAST_INSIDE),
    ],
)
def test_each_pool_edge_admits_its_last_member_and_refuses_the_next_value(
    tmp_path: Path, make: Callable[[int], str], first_inside: int, last_inside: int
) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_i.py", make(first_inside)) == []
    assert _violations(tmp_path, "src/pkg/tests/test_i.py", make(last_inside)) == []
    assert _violations(tmp_path, "src/pkg/tests/test_i.py", make(first_inside - 1)) == [
        ConventionViolation.OFF_CONVENTION
    ]
    assert _violations(tmp_path, "src/pkg/tests/test_i.py", make(last_inside + 1)) == [
        ConventionViolation.OFF_CONVENTION
    ]


def test_the_live_catalogue_pool_is_a_bounded_block_for_every_shape() -> None:
    catalogue = read_catalogue(REPO_ROOT)
    assert catalogue.pool_ranges
    for pool_range in catalogue.pool_ranges:
        assert pool_range.last - pool_range.first < 1000
        assert pool_range.last < 10_000


def test_the_nif_pool_edges_admit_the_last_member_and_refuse_the_next_value(tmp_path: Path) -> None:
    assert _violations(tmp_path, "src/pkg/tests/test_j.py", _nif(1003)) == []
    assert _violations(tmp_path, "src/pkg/tests/test_j.py", _nif(_LAST_INSIDE)) == []
    assert _violations(tmp_path, "src/pkg/tests/test_j.py", _nif(_LAST_INSIDE + 1)) == [
        ConventionViolation.OFF_CONVENTION
    ]
    assert _violations(tmp_path, "src/pkg/tests/test_j.py", _nif(1000)) == [ConventionViolation.OFF_CONVENTION]
