"""Gate: a format's current version is authored in exactly one place.

Two persisted formats were found stating their current version twice, and both
were found by a person reading source rather than by anything mechanical. The
portable export bundle carried a named constant beside a model default holding
the same number; the five rental-register shapes carried the number once on the
domain model and once again as a column default on the persistence row, two
independent literals nothing compared. Neither would have announced itself: the
declarations agreed on the day they were written, and a disagreement only
surfaces later, as a record stamped with one number and validated against
another.

**What this gate asserts, and why it is the right property.** A version-bearing
FIELD must not author its own number. It either carries no default -- the writer
supplies the version from the constant that owns it -- or its default references
that constant by name. A literal in that position is one of exactly two things,
and both are the defect:

* a SECOND declaration, when a constant for the format already exists; or
* the SOLE declaration, unnamed -- which is worse, because a name is what makes
  a future second declaration comparable at all. The rental-register pair had no
  name on either side, which is precisely why two literals could sit in two
  packages disagreeing with nothing to compare them.

So the property gated here is the enabling one: once no field authors its own
number, every declaration of a format's current version is a NAME, and two names
for one format are visible to the enrolment binding gate that discovers formats
by constant name.

**The blind spots, stated rather than implied.**

* A field whose name is not ``schema_version`` or ``*_schema_version``. A
  version called ``version`` is not scanned, because that spelling is also
  argon2's protocol number and a dozen unrelated counters, and a gate that
  cries wolf on those trains authors to ignore it.
* A number restated in PROSE. A docstring claiming which version is current is
  the same defect in a form nothing compiles, and only review catches it.
* A ``Literal[N]`` annotation restating the number its own default binds from a
  constant. That is a real restatement, and it is deliberately out of scope
  because it fails LOUDLY: bump the constant and the next construction raises at
  parse. This gate is aimed at the silent direction.
* Two named constants for one format, in different modules. That is the
  enrolment binding gate's axis, not this one -- and it only becomes visible
  once this gate's property holds.

Unlike the enrolment binding gate, this one does NOT share the
discover-by-constant-name blind spot: it discovers by FIELD name, so it sees
exactly the shapes that gate cannot -- a version that never got a name at all.

See Also:
    :mod:`~core.tests.test_persisted_format_enrolment_binding`
        The complementary axis: inventory keys and version constants must
        account for each other.
    :mod:`~tests.test_persisted_version_literal_inventory`
        The same discipline one layer out, for test fixtures restating a
        constant they should bind.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Final, NamedTuple

import pytest

from ...tests import SRC_CADRUMO, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

_VERSION_FIELD_SUFFIX: Final[str] = "_schema_version"
_VERSION_FIELD_NAME: Final[str] = "schema_version"

_DEAD_SECOND_DECLARATION: Final[str] = (
    "A named constant for this very format already exists, so this default is a second "
    "declaration standing ready to disagree with it. The writer and the reader both bind the "
    "constant, which is what makes this one dead rather than competing -- the same state the "
    "rental-register column defaults were found in."
)
_UNNAMED_SOLE_DECLARATION: Final[str] = (
    "The only declaration this format has, and it carries no name, so nothing can compare a "
    "second one against it. Naming it is a durability decision about a format nobody has "
    "classified yet, not a mechanical rename, and it belongs with that classification."
)
_RESPONSE_CONTRACT: Final[str] = (
    "A response or service contract version rather than a persisted format's: the number rides "
    "on an emitted payload, not on bytes this product promises to keep reading, so there is no "
    "durability declaration for it to be a second copy of."
)

#: ``(path, class, field)`` -> why that site still authors a literal version.
#:
#: Keyed by the enclosing CLASS and the field rather than by line number, so an
#: edit above the site cannot silently move an entry onto a different
#: declaration. Every entry is a standing defect with a stated shape, NOT an
#: exemption that makes the site correct -- :func:`test_every_standing_entry_names_a_live_site`
#: fails the moment one stops naming a real site, so a fixed site's entry cannot
#: rot into a rubber stamp that pre-authorises the next literal in that class.
STANDING_LITERAL_VERSION_DECLARATIONS: Final[Mapping[tuple[str, str, str], str]] = {
    (
        "src/cadrumo/adapters/persistence/operations/_lease.py",
        "_OperationLeaseRecord",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/adapters/persistence/storage/custody/_capsule_records.py",
        "ProfileCustodyDeletionMarker",
        "schema_version",
    ): (
        f"{_UNNAMED_SOLE_DECLARATION} Its module declares a constant for the capsule COMMIT, which "
        "is a different record; the deletion marker has none of its own."
    ),
    (
        "src/cadrumo/adapters/persistence/storage/custody/_label_head_models.py",
        "ProfileLabelHead",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/adapters/persistence/storage/custody/_label_head_models.py",
        "ProfileLabelHeadPendingAdvance",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/application/_bucket_deletion_contracts.py",
        "BucketDeletionFingerprint",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/application/operations/_journal.py",
        "OperationPersistedSnapshot",
        "schema_version",
    ): (
        f"{_UNNAMED_SOLE_DECLARATION} It sits at three, so this format's version has already moved "
        "twice with no name attached to the number at any point."
    ),
    (
        "src/cadrumo/application/operations/_leases.py",
        "OperationLeaseObservation",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/application/operations/_leases.py",
        "OperationLeaseResult",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/application/user_profile/_login_session.py",
        "_ProfileLoginHandoverJournal",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/domain/calculations/registry/_schema_exports.py",
        "FilingEnvelopeDefinition",
        "schema_version",
    ): (
        f"{_UNNAMED_SOLE_DECLARATION} This declares an envelope GRAMMAR rather than an instance, "
        "so whether it is a persisted format at all is part of the open question."
    ),
    (
        "src/cadrumo/domain/contribuyente/__init__.py",
        "TaxResidenceProfile",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/domain/contribuyente/_family_profile.py",
        "RentaFamilyProfile",
        "schema_version",
    ): _UNNAMED_SOLE_DECLARATION,
    (
        "src/cadrumo/application/aggregation/_service.py",
        "PerModeloAggregationContract",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/application/modelo/_m145_communication.py",
        "M145CommunicationServiceContract",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/application/modelo/_m145_communication_records.py",
        "M145CommunicationValidationResult",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/application/modelo/_m145_communication_records.py",
        "M145CommunicationExportResult",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/application/operator_surface/_models.py",
        "OperatorSurfaceContract",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/application/repair_integrity.py",
        "RepairRemediationDecision",
        "schema_version",
    ): _RESPONSE_CONTRACT,
    (
        "src/cadrumo/domain/calculations/registry/_censo_modelos.py",
        "CensoModeloFoundationContract",
        "schema_version",
    ): _RESPONSE_CONTRACT,

}
"""The literal-authoring sites standing when this gate landed, each classified.

Deliberately NOT called an allowlist. Three distinct shapes live here and the
classification is the judgement: a dead second declaration beside an existing
constant, an unnamed sole declaration on a format nobody has classified, and a
response-contract version that is not this inventory's subject at all. Only the
last is arguably fine as it stands.

Nothing about an entry here makes its site correct. The value is that a NEW site
fails immediately, and that a reader can see the shape of every standing one
without re-deriving it.
"""


class LiteralVersionAuthoringSite(NamedTuple):
    """One version-bearing field authoring its number as a literal."""

    display_path: str
    class_name: str
    field: str
    lineno: int
    value: int | str
    form: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.display_path, self.class_name, self.field)

    def format(self) -> str:
        return (
            f"  {self.display_path}:{self.lineno} {self.class_name}.{self.field} authors {self.value!r} ({self.form})"
        )


def _is_version_field(name: str) -> bool:
    """Whether *name* is a schema-version field rather than some other counter.

    Exact-or-suffix on the lowercase spelling, so ``manifest_schema_version``
    counts and an enum MEMBER whose name merely contains the token -- such as a
    ``SCHEMA_VERSION_MISMATCH`` refusal reason -- does not.
    """
    return name == _VERSION_FIELD_NAME or name.endswith(_VERSION_FIELD_SUFFIX)


def _authoring_literal(node: ast.expr | None) -> int | str | None:
    """Return the literal *node* authors, or ``None`` when it authors nothing.

    ``True`` is an ``int`` in Python and is excluded: a version is never a flag.
    Both spellings this tree uses are accepted -- the rental registers version
    with strings and everything else with integers -- because a gate that saw
    only one of them would have missed the pair that motivated it.
    """
    if isinstance(node, ast.Constant) and not isinstance(node.value, bool) and isinstance(node.value, int | str):
        return node.value
    return None


def _default_literal(value: ast.expr) -> tuple[int | str, str] | None:
    """Return the literal and the form in which a field default authors it.

    Covers the three spellings the tree uses: a bare assignment, a pydantic
    ``Field(default=...)``, and a SQLAlchemy ``mapped_column(default=...)`` --
    the last being exactly how five persistence rows held a second copy of a
    number their domain models also held.
    """
    direct = _authoring_literal(value)
    if direct is not None:
        return direct, "bare default"
    if not isinstance(value, ast.Call):
        return None
    callee = value.func
    call_name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "call")
    for keyword in value.keywords:
        if keyword.arg != "default":
            continue
        literal = _authoring_literal(keyword.value)
        if literal is not None:
            return literal, f"{call_name}(default=...)"
    return None


def version_authoring_sites(display_path: str, tree: ast.AST) -> list[LiteralVersionAuthoringSite]:
    """Return every version-bearing field in *tree* authoring its own number.

    A pure ``(display_path, tree) -> sites`` function, so the discrimination
    tests below can feed it synthetic source and the bite proof can feed it real
    production source with one literal reintroduced -- neither needing a tracked
    file to change.
    """
    sites: list[LiteralVersionAuthoringSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                target, value = statement.target.id, statement.value
            elif (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                target, value = statement.targets[0].id, statement.value
            else:
                continue
            if value is None or not _is_version_field(target):
                continue
            authored = _default_literal(value)
            if authored is None:
                continue
            literal, form = authored
            sites.append(
                LiteralVersionAuthoringSite(
                    display_path=display_path,
                    class_name=node.name,
                    field=target,
                    lineno=statement.lineno,
                    value=literal,
                    form=form,
                )
            )
    return sites


def scan_items(items: Iterable[tuple[Path, ast.AST]]) -> list[LiteralVersionAuthoringSite]:
    """Return every authoring site across an injectable ``(path, tree)`` stream.

    Takes the stream rather than reaching for the production surface itself, so
    the whole gate path -- not merely its pure leaf -- can be exercised against
    real production source carrying one deliberately reintroduced literal.
    """
    sites: list[LiteralVersionAuthoringSite] = []
    for path, tree in items:
        sites.extend(version_authoring_sites(repo_relative(path), tree))
    return sites


def unclassified_sites(
    sites: Iterable[LiteralVersionAuthoringSite],
    standing: Mapping[tuple[str, str, str], str],
) -> list[LiteralVersionAuthoringSite]:
    """Return the authoring sites no standing entry accounts for."""
    return [site for site in sites if site.key not in standing]


def test_the_scan_surface_is_non_empty(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """An empty production surface would pass every assertion below vacuously."""
    assert production_ast_items(source_tree_ast), "production source surface is empty; the gate would enforce nothing"


def test_no_new_version_field_authors_its_own_number(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A version-bearing field binds the constant, or carries no default at all."""
    offenders = unclassified_sites(
        scan_items(production_ast_items(source_tree_ast)),
        STANDING_LITERAL_VERSION_DECLARATIONS,
    )

    assert not offenders, (
        f"{len(offenders)} version-bearing field(s) author their own number as a literal:\n"
        + "\n".join(sorted(site.format() for site in offenders))
        + "\n\nGive the format a named module-level constant and bind the default to it, or drop "
        "the default so the writer must stamp the version. A literal here is either a second "
        "declaration of a number a constant already owns, or the sole declaration of a number "
        "nothing can ever be compared against."
    )


def test_every_standing_entry_names_a_live_site(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A standing entry that stops naming a real site is deleted, not left behind.

    An entry naming nothing is indistinguishable in a diff from one that still
    describes a real defect, and it silently pre-authorises the next literal that
    lands in that class.
    """
    live = {site.key for site in scan_items(production_ast_items(source_tree_ast))}
    stale = sorted(key for key in STANDING_LITERAL_VERSION_DECLARATIONS if key not in live)

    assert not stale, (
        "STANDING_LITERAL_VERSION_DECLARATIONS entries naming no live authoring site:\n"
        + "\n".join(f"  {path} :: {class_name}.{field}" for path, class_name, field in stale)
        + "\nThe site was fixed, renamed or moved; delete the entry in the same change."
    )


def test_every_standing_entry_states_a_shape() -> None:
    """The classification is the whole mechanism, so a thin reason is a silent pass."""
    for key, reason in STANDING_LITERAL_VERSION_DECLARATIONS.items():
        assert len(reason.split()) >= 12, f"{key} carries a reason too thin to classify it: {reason!r}"


def test_the_two_repaired_formats_stay_repaired(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Fixture anchor: the two formats this gate was built from must stay clean.

    Both were repaired before this gate existed, so neither appears in the
    standing table. That is exactly the state a rename could make vacuous -- if
    either module moved, this gate would pass while saying nothing about the two
    cases that motivated it. So each anchor names BOTH halves: the module that
    declares the owning constant, and the module whose field was carrying the
    duplicate literal. Finding the constant proves the anchor still names the
    right pair; finding no authoring site proves the repair holds.
    """
    anchors = (
        (
            "src/cadrumo/application/user_profile/_bundle.py",
            "BUNDLE_SCHEMA_VERSION",
            "src/cadrumo/application/user_profile/_bundle_export_contracts.py",
        ),
        (
            "src/cadrumo/domain/fincas/_models.py",
            "FINCA_SCHEMA_VERSION",
            "src/cadrumo/adapters/persistence/storage/sql/_orm.py",
        ),
    )
    sites_by_path: dict[str, list[LiteralVersionAuthoringSite]] = {}
    for site in scan_items(production_ast_items(source_tree_ast)):
        sites_by_path.setdefault(site.display_path, []).append(site)

    for constant_path, constant, field_path in anchors:
        source = (SRC_CADRUMO.parents[1] / constant_path).read_text(encoding="utf-8")
        assert constant in source, (
            f"{constant_path} no longer declares {constant}; this anchor names the wrong module and "
            "the gate would pass without covering the case it was built from"
        )
        for display_path in (constant_path, field_path):
            assert not sites_by_path.get(display_path), (
                f"{display_path} authors a literal version again:\n"
                + "\n".join(site.format() for site in sites_by_path.get(display_path, []))
            )


_SYNTHETIC_BARE_DEFAULT = """
class PortableBundle:
    schema_version: int = 3
"""

_SYNTHETIC_FIELD_DEFAULT = """
class MirrorManifest:
    manifest_schema_version: int = Field(default=1, ge=1)
"""

_SYNTHETIC_COLUMN_DEFAULT = """
class FincaRow:
    schema_version: Mapped[str] = mapped_column(String(8), default="1")
"""

_SYNTHETIC_BOUND = """
class PortableBundle:
    schema_version: int = BUNDLE_SCHEMA_VERSION
"""

_SYNTHETIC_REQUIRED = """
class PortableBundle:
    schema_version: int
"""

_SYNTHETIC_UNRELATED_VERSION = """
class ManifestKdfParams:
    version: int = 19
"""

_SYNTHETIC_ENUM_MEMBER = """
class ProfileSessionRefusalReason(StrEnum):
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
"""


def test_detector_fires_on_each_shape_the_two_repairs_had() -> None:
    """The three authoring spellings all fire, including the string one.

    The bundle carried a bare integer default; the rental-register rows carried
    a ``mapped_column`` default holding a STRING. A detector that saw only the
    integer spelling would have missed one of the two cases it exists for.
    """
    bare = version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_BARE_DEFAULT))
    assert [(s.class_name, s.field, s.value, s.form) for s in bare] == [
        ("PortableBundle", "schema_version", 3, "bare default")
    ]

    field = version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_FIELD_DEFAULT))
    assert [(s.class_name, s.field, s.value, s.form) for s in field] == [
        ("MirrorManifest", "manifest_schema_version", 1, "Field(default=...)")
    ]

    column = version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_COLUMN_DEFAULT))
    assert [(s.class_name, s.field, s.value, s.form) for s in column] == [
        ("FincaRow", "schema_version", "1", "mapped_column(default=...)")
    ]


def test_detector_stays_silent_on_the_two_correct_forms() -> None:
    """It discriminates, rather than reporting whatever it is handed.

    Both repaired shapes must read clean: the bundle's required field with no
    default, and a default bound to the constant that owns the number.
    """
    assert version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_BOUND)) == []
    assert version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_REQUIRED)) == []


def test_detector_ignores_a_counter_that_is_not_a_schema_version() -> None:
    """An unrelated ``version`` and an enum member are not authoring sites.

    ``ManifestKdfParams.version`` is argon2's protocol number, and a refusal
    reason merely spells the token in its member name. Flagging either would
    demand a binding that does not exist and train authors to read this gate's
    failures as noise.
    """
    assert version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_UNRELATED_VERSION)) == []
    assert version_authoring_sites("synthetic.py", ast.parse(_SYNTHETIC_ENUM_MEMBER)) == []
