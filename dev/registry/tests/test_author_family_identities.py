"""The edition-free identities authored for the two previously unkeyed families."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_surfaces import validate_family_identity_uniqueness

from ..author_family_identities import (
    PROJECTION_ENDPOINTS,
    VERIFICATION_PREDICATES,
    IdentityDerivationError,
    author_identities,
    derive_projection_endpoint_id,
    derive_verification_predicate_id,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENDPOINT_TOML = """\
# An authored comment the pass must not discard.
[[revisions."2024".projection_endpoints]]
legal_refs = ["ley-27-2014:art-41"]
source_refs = ["aeat-dr-200-2024"]
[revisions."2024".projection_endpoints.projection_ref]
projection_kind = "m200_administrador"
slot = 1
field = "nif"

[[revisions."2024".projection_endpoints]]
legal_refs = ["ley-27-2014:art-41"]
source_refs = ["aeat-dr-200-2024"]
[revisions."2024".projection_endpoints.projection_ref]
projection_kind = "m200_administrador"
slot = 2
field = "nif"
"""

_PREDICATE_TOML = """\
[[revisions."2025".verification_predicates]]
predicate_id = "modelo-131-2025-c11-cap-by-c10"
expression = 'cap_le_when_positive(["11", "10"])'
legal_refs = ["orden-hac-1347-2024:anexo-2"]
source_refs = ["aeat-dr-131-2025"]
"""


def _tree(root: Path, modelo: str, revision: str, family: str, body: str) -> Path:
    directory = root / "modelos" / modelo / "revisions" / revision / family
    directory.mkdir(parents=True)
    path = directory / "0001-members.toml"
    path.write_text(body, encoding="utf-8", newline="")
    return path


def test_projection_endpoint_identity_names_the_endpoint_not_its_casilla_address() -> None:
    """The identity carries the projection's semantic axes and drops its casilla address."""
    identity = derive_projection_endpoint_id(
        {
            "projection_ref": {
                "projection_kind": "m303_prorrata_activity",
                "slot": 3,
                "field": "operaciones_con_derecho",
                "casilla_id": "0701",
            },
        },
    )
    assert identity == "m303-prorrata-activity:field-operaciones-con-derecho.slot-3"


def test_projection_endpoint_identity_is_independent_of_authored_key_order() -> None:
    """Two authorings of one endpoint that differ only in key order derive one identity."""
    forward = derive_projection_endpoint_id(
        {"projection_ref": {"projection_kind": "m200_administrador", "slot": 1, "field": "nif"}},
    )
    reversed_keys = derive_projection_endpoint_id(
        {"projection_ref": {"field": "nif", "slot": 1, "projection_kind": "m200_administrador"}},
    )
    assert forward == reversed_keys == "m200-administrador:field-nif.slot-1"


def test_projection_endpoint_without_a_typed_reference_is_refused() -> None:
    """A declaration carrying no projection_ref has no identity to derive."""
    with pytest.raises(IdentityDerivationError, match="no projection_ref"):
        derive_projection_endpoint_id({"legal_refs": ["ley-27-2014:art-41"]})


@pytest.mark.parametrize(
    ("predicate_id", "expected"),
    [
        ("modelo-100-2025-retenciones-trabajo-declaradas", "implies-nonzero:retenciones-trabajo-declaradas"),
        ("modelo-100-2024-retenciones-trabajo-declaradas", "implies-nonzero:retenciones-trabajo-declaradas"),
        ("modelo-123-2019-2023-base-declarada", "implies-nonzero:base-declarada"),
        ("modelo-123-2024-y-siguientes-base-declarada", "implies-nonzero:base-declarada"),
        ("m210-representante-fiscal-required", "implies-nonzero:representante-fiscal-required"),
    ],
)
def test_verification_predicate_identity_sheds_the_declaring_edition(predicate_id: str, expected: str) -> None:
    """Editions of one invariant derive one identity, whatever scope their names carry."""
    identity = derive_verification_predicate_id(
        {"predicate_id": predicate_id, "expression": 'implies_nonzero(["0012", "0596"])'},
    )
    assert identity == expected


def test_verification_predicate_identity_keeps_a_statutory_year() -> None:
    """A cutoff year belongs to the invariant, not to the edition, and stays in the identity."""
    identity = derive_verification_predicate_id(
        {
            "predicate_id": "modelo-100-2025-deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013",
            "expression": 'deduccion_requires_adquisicion_before(["0547", "0550", "0551", "2013-01-01"])',
        },
    )
    assert identity == (
        "deduccion-requires-adquisicion-before:deduccion-vivienda-habitual-requiere-adquisicion-anterior-2013"
    )


def test_verification_predicate_identity_carries_the_predicate_kind() -> None:
    """Two invariants sharing a subject but not an operator are distinct predicates."""
    subject = "modelo-131-2025-c11-cap-by-c10"
    capped = derive_verification_predicate_id({"predicate_id": subject, "expression": 'cap_le_when_positive(["a"])'})
    implied = derive_verification_predicate_id({"predicate_id": subject, "expression": 'implies_nonzero(["a"])'})
    assert capped == "cap-le-when-positive:c11-cap-by-c10"
    assert implied == "implies-nonzero:c11-cap-by-c10"
    assert capped != implied


def test_verification_predicate_without_an_operator_is_refused() -> None:
    """An expression naming no operator names no predicate kind."""
    with pytest.raises(IdentityDerivationError, match="no predicate operator"):
        derive_verification_predicate_id({"predicate_id": "modelo-100-2025-x", "expression": '["0012"]'})


def test_duplicate_identities_within_one_revision_are_refused(tmp_path: Path) -> None:
    """Two members of one revision deriving one identity are reported, not renamed."""
    duplicated = _ENDPOINT_TOML.replace("slot = 2", "slot = 1")
    _tree(tmp_path, "200", "2024", PROJECTION_ENDPOINTS, duplicated)
    outcome = author_identities(
        registry_root=tmp_path,
        families=[PROJECTION_ENDPOINTS],
        modelos=["200"],
        apply=True,
    )
    assert outcome.written == ()
    assert [collision.identity for collision in outcome.collisions] == ["m200-administrador:field-nif.slot-1"]
    assert outcome.collisions[0].members == ("0001-members.toml[0]", "0001-members.toml[1]")


def test_the_schema_refuses_a_revision_declaring_one_identity_twice() -> None:
    """The revision boundary refuses the collision the authoring pass refuses to write."""
    with pytest.raises(RegistryValidationError, match="duplicate ids: 'a:b'"):
        validate_family_identity_uniqueness("verification_predicates", ["a:b", "c:d", "a:b"])


def test_dry_run_derives_without_writing(tmp_path: Path) -> None:
    """A dry run reports every pending member and leaves the tree byte-identical."""
    endpoints = _tree(tmp_path, "200", "2024", PROJECTION_ENDPOINTS, _ENDPOINT_TOML)
    before = endpoints.read_bytes()
    report = tmp_path / "reports" / "dry-run.txt"
    exit_code = main(["--modelo", "200", "--dry-run", "--registry-root", str(tmp_path), "--report", str(report)])
    assert exit_code == 0
    assert endpoints.read_bytes() == before
    assert "pending=2" in report.read_text(encoding="utf-8")


def test_apply_writes_one_id_line_per_member_and_is_idempotent(tmp_path: Path) -> None:
    """The pass writes each id above its member, keeps the authored prose, and re-runs clean."""
    endpoints = _tree(tmp_path, "200", "2024", PROJECTION_ENDPOINTS, _ENDPOINT_TOML)
    predicates = _tree(tmp_path, "131", "2025", VERIFICATION_PREDICATES, _PREDICATE_TOML)

    assert main(["--all", "--registry-root", str(tmp_path)]) == 0

    written = endpoints.read_text(encoding="utf-8")
    assert "# An authored comment the pass must not discard." in written
    assert 'id = "m200-administrador:field-nif.slot-1"' in written
    assert 'id = "m200-administrador:field-nif.slot-2"' in written
    endpoint_members = tomllib.loads(written)["revisions"]["2024"][PROJECTION_ENDPOINTS]
    assert [member["id"] for member in endpoint_members] == [
        "m200-administrador:field-nif.slot-1",
        "m200-administrador:field-nif.slot-2",
    ]
    predicate_members = tomllib.loads(predicates.read_text(encoding="utf-8"))["revisions"]["2025"][
        VERIFICATION_PREDICATES
    ]
    assert [member["id"] for member in predicate_members] == ["cap-le-when-positive:c11-cap-by-c10"]

    after_first = endpoints.read_bytes()
    assert main(["--all", "--registry-root", str(tmp_path)]) == 0
    assert endpoints.read_bytes() == after_first


def test_a_collision_exits_nonzero_and_writes_nothing(tmp_path: Path) -> None:
    """The tool refuses the whole run rather than authoring the members it could."""
    duplicated = _ENDPOINT_TOML.replace("slot = 2", "slot = 1")
    endpoints = _tree(tmp_path, "200", "2024", PROJECTION_ENDPOINTS, duplicated)
    before = endpoints.read_bytes()
    assert main(["--all", "--registry-root", str(tmp_path)]) == 1
    assert endpoints.read_bytes() == before
