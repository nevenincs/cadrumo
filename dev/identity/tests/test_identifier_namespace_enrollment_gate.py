"""Ratchet gate: an identifier-named model field carries an alias, not bare ``str``.

WHAT THIS ASSERTS. Every field on a production pydantic model whose NAME matches
the identifier-namespace vocabulary must carry a type, not a bare ``str``. A
value that names an expediente, a CSV, a bucket or a transaction is a member of
some identity namespace; declaring it ``str`` means the model boundary asserts
nothing about it, and two values from unrelated namespaces become mutually
substitutable with no layer objecting.

HOW THE VOCABULARY IS DERIVED, and why it is derived rather than listed. It is
computed at runtime from the alias family :mod:`~core.identity` actually
exports: every name in that package's ``__all__`` that IS a type alias -- a
:class:`typing.TypeAliasType` from a PEP 695 ``type X = ...``, or an
``Annotated[...]`` object -- contributes its name in snake_case, plus the same
name with a leading ``aeat_`` issuer token stripped (so ``AeatExpedienteId``
admits the field name ``expediente_id`` as well as ``aeat_expediente_id``). A
field matches when a vocabulary token is the field name itself or a trailing
token-run of it, so ``parent_transaction_id`` and ``winning_expediente_id``
match while ``financial_default_csv_encoding`` does not.

Deriving from the live family is what keeps the gate honest as the family
grows: a new alias widens the vocabulary with no edit here. It also means this
gate cannot be satisfied by DELETING an alias, because deleting one narrows the
vocabulary and strands its sites in the ledgers below, which the staleness
assertions then fail.

Only the ISSUER token is stripped, never a distinguishing one. Reducing
``filing_record_id`` to ``record_id``, or ``calculation_revision_id`` to
``revision_id``, would erase exactly the token that separates two namespaces --
a registry revision id and a calculation revision id are different concepts
that share a suffix -- so the reduction that looks like generosity is really a
conflation, and it is not performed. The single exception is DECLARED in
:data:`_SHARED_STEMS` with its reason and is anchored by a test.

WHAT THIS DOES NOT ASSERT: that a field carries the RIGHT alias. The property
is enrolment -- something other than bare ``str`` -- because a field may be
correctly typed by an authority outside this package (a registry casilla id, a
:class:`enum.StrEnum`), and a gate demanding a ``core.identity`` name
specifically would report those as violations. Choosing between two aliases
stays a review judgement.

THE REHOMED FREE-TEXT EXCLUSIONS. Three sub-populations were documented as
deliberately outside this taxonomy on the ``IdentifierNamespace`` enum, which
has since been deleted as a dormant symbol with no consumer. The documentation
outlived the enum because the exclusions are still true, so it lives here now,
in :data:`_FREE_TEXT_POPULATIONS`, where this gate is its only consumer. Each
population is falsifiable rather than prose: a test asserts its representative
field tokens are NOT in the derived vocabulary, so adding an alias that named
one of them would fail the claim and force a re-adjudication rather than
silently widening the gate.

ONE LEDGER, WITH NO BASELINE. :data:`_ADJUDICATED` names the exceptional sites
ruled bare-by-design, each with a falsifiable production anchor and a stated
reason. It is not a backlog: every other bare identifier field fails the
ratchet immediately. Keys are ``(path, model, field)``, never line numbers,
because a line number is invalidated by every edit above it and an exemption
that moves silently is an exemption nobody re-reads.

KNOWN LIMITS, stated rather than left implied by a green run.

Only pydantic models are in reach. Model membership is resolved by walking
every production class's base names and taking the fixpoint from ``BaseModel``,
matched by bare class name across the corpus. A frozen ``dataclass`` is
therefore invisible: ``AeatParty.tax_id`` in the einvoice record batch is a real
dual-role identifier field this gate does not see, and it is named here so a
green run is not read as covering it.

Function parameters and return annotations are out of reach for the same
reason -- the subject is a field on a model -- so a bare ``str`` parameter naming
an identifier is not reported.

A ``short_``-prefixed field is excluded structurally, not by allowlist. It is a
TRUNCATED display companion -- twelve characters of a sixty-four character
identity -- so the full alias is strictly NARROWER than the value the field
exists to carry, and typing it would refuse every value the surface serves. The
exclusion is anchored: a test asserts every excluded ``short_<x>`` has a sibling
``<x>`` field on the same model, so dropping or renaming the full field makes
the companion's exclusion fail rather than pass vacuously.

The scan reads the CURRENT WORKTREE. This is a gate for the change being tested,
so a pinned ``HEAD`` view would allow an uncommitted bare field to evade the
ratchet. Its source snapshot is collected once per module fixture, yielding a
reproducible report for that test invocation without using an alternate index.

See Also:
    :mod:`~core.identity`
        The alias family the vocabulary is derived from.
"""

from __future__ import annotations

import ast
import re
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core import identity, scan_directory

from ..identifier_noun_census import annotation_text, is_bare_str

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Production source root in the CURRENT worktree. The parent path calculation
#: is anchored to this test file rather than the process cwd.
_SOURCE_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: Repository root in the CURRENT worktree, used only to render stable anchors.
_REPOSITORY_ROOT: Final[Path] = _SOURCE_ROOT.parents[1]

#: The root pydantic base every model in this tree ultimately derives from.
_MODEL_ROOT: Final[str] = "BaseModel"

#: Prefix marking a truncated display companion of a full identity.
_DISPLAY_COMPANION_PREFIX: Final[str] = "short_"

#: Leading token naming the ISSUING AUTHORITY rather than the concept. Stripped
#: so an alias named for AEAT admits the unqualified field spelling the tree
#: actually uses. Only the issuer is stripped; see the module docstring.
_ISSUER_PREFIX: Final[str] = "aeat_"

_CAMEL_BOUNDARY: Final[re.Pattern[str]] = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass(frozen=True, slots=True)
class _SharedStem:
    """One identity concept spelled by more than one alias.

    A stem is admitted ONLY when two or more aliases name the same underlying
    identifier and the field spelling in the tree is the common stem rather
    than either alias name. Every entry is anchored by a test asserting its
    aliases still exist, so a rename cannot leave the stem asserting a
    vocabulary nothing backs.

    Attributes:
        stem: The snake_case field-name token the concept is spelled with.
        aliases: The alias names on the identity facade that share it.
        reason: Why one stem covers both, stated rather than assumed.
    """

    stem: str
    aliases: tuple[str, ...]
    reason: str


#: The declared stem reductions. Deliberately tiny: each is a claim that two
#: aliases name one concept, which is a judgement, not a derivation.
_SHARED_STEMS: Final[tuple[_SharedStem, ...]] = (
    _SharedStem(
        stem="tax_id",
        aliases=("SubjectTaxId", "TaxIdIdentityToken"),
        reason=(
            "A tax identifier is spelled tax_id throughout the tree, and TWO aliases "
            "carry it: SubjectTaxId asserts the Spanish NIF/NIE/CIF checksum, and "
            "TaxIdIdentityToken is the checksum-free comparison form for a bearer who "
            "may not be Spanish. Neither alias NAME is the field spelling, so without "
            "this stem every tax_id field would fall outside the vocabulary entirely."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _FreeTextPopulation:
    """One sub-population deliberately outside the identifier taxonomy.

    Rehomed from the deleted ``IdentifierNamespace`` enum, whose trailing
    comment block recorded these three as deliberately not members of the
    taxonomy, "recorded here so a later sweep does not enroll them by
    name-shape and call the surface closed". That enum is gone; the exclusions
    are still true, and this gate is now their home.

    Attributes:
        name: Short label for the population.
        reason: Why its members are not identity-namespace members.
        field_tokens: Representative field-name tokens. Asserted ABSENT from
            the derived vocabulary, so the exclusion is falsifiable: adding an
            alias that named one of these would fail the claim rather than
            quietly widen the gate.
    """

    name: str
    reason: str
    field_tokens: tuple[str, ...]


#: The three sub-populations, verbatim in substance from the deleted enum.
_FREE_TEXT_POPULATIONS: Final[tuple[_FreeTextPopulation, ...]] = (
    _FreeTextPopulation(
        name="AEAT-printed adjudicated-case prose",
        reason=(
            "Bounded free text the app neither controls nor can enumerate -- a "
            "declaration's estado, a debt's situacion. Typing them as a closed set "
            "would assert a vocabulary AEAT has never published, and a value outside "
            "it would be refused at the model boundary rather than reported."
        ),
        field_tokens=("estado", "situacion"),
    ),
    _FreeTextPopulation(
        name="Counterparty-issued document numbers",
        reason=(
            "An invoice_number is minted by a third party, not by AEAT and not by this "
            "app. It has no shape this codebase may constrain, because the issuer's "
            "numbering scheme is the issuer's to choose."
        ),
        field_tokens=("invoice_number", "document_number"),
    ),
    _FreeTextPopulation(
        name="Non-AEAT issuing authorities",
        reason=(
            "Google file, folder and spreadsheet ids; an X.509 certificate serial; an "
            "SPDX id. Each belongs to some other authority's namespace and none "
            "belongs in the AEAT group. Whether any warrants typing at all is a "
            "separate question this taxonomy does not answer."
        ),
        field_tokens=("file_id", "folder_id", "spreadsheet_id", "serial_number", "spdx_id"),
    ),
)

#: Live occurrences anchoring the AEAT-prose population. Each MUST still be a
#: bare free-text field on a production model: if one gains a closed type, the
#: population's claim is obsolete and must be re-adjudicated rather than left
#: standing as a stale carve-out.
_FREE_TEXT_ANCHORS: Final[tuple[tuple[str, str, str], ...]] = (
    ("src/cadrumo/adapters/outbound/aeat/sede/_declarations_schema.py", "Declaracion", "estado"),
    ("src/cadrumo/adapters/outbound/aeat/sede/_deudas.py", "Deuda", "situacion"),
)


@dataclass(frozen=True, slots=True)
class _Adjudication:
    """One site ruled bare-by-design, with the reason it was ruled so.

    Attributes:
        path: Repository-relative module path.
        model: Enclosing model class name.
        field: Field name.
        reason: Why this field must NOT be retyped. Required: an exemption
            whose reason is not stated is indistinguishable from an oversight.
    """

    path: str
    model: str
    field: str
    group: str
    reason: str

    def key(self) -> tuple[str, str, str]:
        """The identity this adjudication matches occurrences on."""
        return (self.path, self.model, self.field)


#: Sites ruled bare, each surviving the substitutability check in the opposite
#: direction: the alias is NARROWER than what the site legitimately accepts, so
#: promoting it would refuse a value the site exists to handle.
_ADJUDICATED: Final[tuple[_Adjudication, ...]] = (
    _Adjudication(
        path="src/cadrumo/application/auth/_sessions.py",
        model="ClaveAuthFacts",
        field="tax_id",
        group="raw/prevalidation tax inputs",
        reason=(
            "Auth facts are read from the authenticated session BEFORE the identity is "
            "known to be well-formed; the value is whatever the provider asserted. "
            "Validating at this boundary would refuse a session AEAT itself issued."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/auth/_sessions.py",
        model="ClaveCredentials",
        field="profile_tax_id",
        group="raw/prevalidation tax inputs",
        reason=(
            "The credential carries the identifier as SUPPLIED for the login attempt, "
            "not as validated. Refusing a malformed one here would turn a failed "
            "authentication into a model construction error with no operator diagnosis."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/core/setup_answers.py",
        model="SetupAnswers",
        field="tax_id",
        group="raw/prevalidation tax inputs",
        reason=(
            "Wizard answers are captured before validation runs, so the setup surface "
            "can report a bad identifier as an answerable question rather than crash "
            "while constructing the answer record."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/core/setup_answers.py",
        model="SetupAnswers",
        field="spouse_tax_id",
        group="raw/prevalidation tax inputs",
        reason=(
            "As SetupAnswers.tax_id: captured pre-validation, so a placeholder must "
            "survive capture to be corrected in a later answer."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="_ExtractedInvoiceFieldClaims",
        field="supplier_tax_id",
        group="raw/prevalidation tax inputs",
        reason=(
            "An LLM-extracted CLAIM, held verbatim as it appears in the document. "
            "SubjectTaxId canonicalises and uppercases, which broke anchor matching "
            "against the source text -- a real regression, not a hypothetical: the "
            "grounding step must find the claim back in the document byte-for-byte."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="_ExtractedInvoiceFieldClaims",
        field="customer_tax_id",
        group="raw/prevalidation tax inputs",
        reason="As the supplier claim on this model: verbatim extraction, anchor matching.",
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="ExtractedRoleEvidence",
        field="supplier_tax_id",
        group="raw/prevalidation tax inputs",
        reason="As the claim model: role evidence quotes the extracted text verbatim for anchoring.",
    ),
    _Adjudication(
        path="src/cadrumo/llm/_invoice_field_grounding.py",
        model="ExtractedRoleEvidence",
        field="customer_tax_id",
        group="raw/prevalidation tax inputs",
        reason="As the claim model: role evidence quotes the extracted text verbatim for anchoring.",
    ),
    _Adjudication(
        path="src/cadrumo/adapters/inbound/borrador/_schema.py",
        model="InboundBorradorObservation",
        field="tax_id",
        group="verbatim external evidence",
        reason=(
            "The parser preserves the filer identifier printed by the PDF; SubjectTaxId would canonicalise or refuse "
            "evidence before the extraction can report it."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/adapters/inbound/borrador/_schema.py",
        model="InboundBorradorObservation",
        field="registry_extraction_profile_id",
        group="semantic tail collisions",
        reason=(
            "This names a registry extraction-profile selector, not a user ProfileId; the match comes only from its "
            "profile_id suffix."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/adapters/inbound/declaracion/_schema.py",
        model="InboundDeclaracionObservation",
        field="tax_id",
        group="verbatim external evidence",
        reason=(
            "The parser records the tax identifier exactly as the declaration printed it, before identity validation "
            "can be a separate diagnostic."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/adapters/inbound/declaracion/_schema.py",
        model="InboundDeclaracionObservation",
        field="extraction_profile_id",
        group="semantic tail collisions",
        reason=(
            "This is an extraction-profile configuration key, not a ProfileId; its trailing profile_id spelling is "
            "coincidental."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/aggregation/_iva_ledger.py",
        model="IvaLedgerAggregationIssue",
        field="transaction_id",
        group="mixed-source diagnostic references",
        reason=(
            "An IVA candidate may carry a 1-128-character _LedgerId rather than a catalogued hex-64 TransactionId; "
            "constraining the exclusion report would hide the very candidate it must explain."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/auth/_diagnostics.py",
        model="AuthDiagnosticSummary",
        field="active_profile_id",
        group="redacted diagnostic projections",
        reason=(
            "The encrypted-artifact summary projects a redacted diagnostic value, not a profile identity boundary, so "
            "ProfileId would assert a value the redactor need not retain."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/auth/_diagnostics.py",
        model="AuthDiagnosticSummary",
        field="active_profile_label",
        group="redacted diagnostic projections",
        reason=(
            "The value is display text in a redacted diagnostic summary, not the ProfileLabel domain field; its name "
            "matches only the label vocabulary token."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/ledger/_evidence_draft.py",
        model="CounterpartyDraftSide",
        field="tax_id",
        group="verbatim external evidence",
        reason=(
            "The draft holds the counterparty identifier exactly as a document stated it so later grounding can "
            "distinguish evidence from a canonicalised identity."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/ledger/_models.py",
        model="BulkClassifyFailure",
        field="transaction_id",
        group="mixed-source diagnostic references",
        reason=(
            "A file-classification failure must report the supplied row reference even when it is malformed or not yet "
            "a catalogue TransactionId."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/modelo/_borrador_binding.py",
        model="Modelo100BorradorBindingCommand",
        field="borrador_snapshot_id",
        group="semantic tail collisions",
        reason=(
            "This selects a borrador snapshot under its own 1-128-character contract, not the hex-64 core SnapshotId "
            "namespace."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/user_profile/commands.py",
        model="ProfileSnapshot",
        field="snapshot_id",
        group="semantic tail collisions",
        reason=(
            "A filing-time profile snapshot has an application-specific 1-128-character identifier, distinct from the "
            "content-hash SnapshotId alias."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/application/user_profile/commands.py",
        model="ProfileStaleCheckReport",
        field="snapshot_id",
        group="semantic tail collisions",
        reason=(
            "The stale-report repeats the ProfileSnapshot identifier, whose 1-128-character contract is not the core "
            "content-hash SnapshotId namespace."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/calculations/registry/_invoice_bindings.py",
        model="InvoiceObservation",
        field="invoice_id",
        group="open ledger-source references",
        reason=(
            "Registry invoice observations accept a source-ledger reference up to 128 characters; it is not "
            "necessarily the core hex-64 InvoiceId namespace."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/invoices/_service.py",
        model="LinkInconsistency",
        field="invoice_id",
        group="mixed-source diagnostic references",
        reason=(
            "The diagnostic exists to report a dangling Transaction.invoice_id; InvoiceId would reject the unresolved "
            "reference before the inconsistency could be shown."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/modelos/_ledger_filing_snapshot.py",
        model="LedgerEvidenceRow",
        field="invoice_id",
        group="open ledger-source references",
        reason=(
            "This persistence projection mirrors Transaction.invoice_id beside distinct purchase-evidence references, "
            "preserving its open foreign-key contract rather than asserting InvoiceId."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/renta/_ledger_expenses.py",
        model="RentaDeductibleExpenseFact",
        field="invoice_id",
        group="open ledger-source references",
        reason="The Renta fact carries the 1-128-character ledger invoice reference, not a validated core InvoiceId.",
    ),
    _Adjudication(
        path="src/cadrumo/domain/renta/_ledger_expenses.py",
        model="RentaDeductibilityResult",
        field="invoice_id",
        group="open ledger-source references",
        reason=(
            "The result preserves the source fact's optional ledger invoice reference for review; it does not "
            "construct an InvoiceId."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/renta/_ledger_expenses.py",
        model="RentaDeductibleExpenseObservation",
        field="invoice_id",
        group="open ledger-source references",
        reason=(
            "The binding-ready observation carries through the unvalidated ledger invoice reference so binding can "
            "report the actual source fact."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/transactions/_models.py",
        model="Transaction",
        field="invoice_id",
        group="open ledger-source references",
        reason=(
            "Transaction stores an optional reconciliation foreign key that may be dangling until consistency "
            "verification; it is deliberately not an InvoiceId boundary."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/domain/transactions/_raw_transaction.py",
        model="RawTransaction",
        field="provider_transaction_id",
        group="verbatim external evidence",
        reason=(
            "This is the bank/feed's native row identifier, preserved verbatim and distinct from the derived core "
            "TransactionId hash."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/entrypoints/cli/_ledger_payloads.py",
        model="BulkClassifyFailurePayload",
        field="transaction_id",
        group="mixed-source diagnostic references",
        reason=(
            "The CLI failure payload mirrors the application failure's supplied row reference, which can be malformed "
            "or not yet a TransactionId."
        ),
    ),
    _Adjudication(
        path="src/cadrumo/entrypoints/cli/_ledger_payloads.py",
        model="LedgerLinkInconsistencyPayload",
        field="invoice_id",
        group="mixed-source diagnostic references",
        reason=(
            "The CLI mirrors a dangling invoice reference from LinkInconsistency; validating it as InvoiceId would "
            "suppress the reported mismatch."
        ),
    ),
)


def _snake(name: str) -> str:
    """Render a CamelCase alias name as its snake_case field spelling."""
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def identifier_aliases() -> tuple[str, ...]:
    """Every identifier ALIAS exported by :mod:`~core.identity`.

    An alias is a PEP 695 :class:`typing.TypeAliasType` or an ``Annotated[...]``
    object. Classes, functions and scalar constants on the same facade are not
    aliases and contribute no vocabulary: ``validate_identity`` is a function,
    ``IdentityDocument`` an enum, ``SPANISH_TAX_ID_WIDTH`` an int.
    """
    names: list[str] = []
    for name in identity.__all__:
        member = getattr(identity, name)
        if isinstance(member, typing.TypeAliasType) or typing.get_origin(member) is not None:
            names.append(name)
    return tuple(sorted(names))


def namespace_vocabulary() -> frozenset[str]:
    """The field-name tokens the live alias family names.

    Derived, never listed: see the module docstring for why, and for why only
    the issuer prefix is stripped.
    """
    tokens: set[str] = set()
    for alias in identifier_aliases():
        spelling = _snake(alias)
        tokens.add(spelling)
        if spelling.startswith(_ISSUER_PREFIX):
            tokens.add(spelling.removeprefix(_ISSUER_PREFIX))
    tokens.update(stem.stem for stem in _SHARED_STEMS)
    return frozenset(tokens)


def matched_token(field: str, vocabulary: frozenset[str]) -> str | None:
    """The vocabulary token a field name carries, or ``None``.

    Matched against every trailing token-run of the field name, so a qualifier
    the tree adds in front (``parent_``, ``winning_``, ``closed_previous_``)
    does not hide the concept. Anchoring at the TAIL rather than searching
    anywhere is what keeps an unrelated head token from matching.
    """
    parts = field.split("_")
    for index in range(len(parts)):
        candidate = "_".join(parts[index:])
        if candidate in vocabulary:
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class IdentifierField:
    """One identifier-named field on a production model.

    Attributes:
        path: Repository-relative module path in the current worktree.
        line: Line of the field's annotated assignment.
        model: Enclosing model class name.
        field: Field name.
        annotation: The annotation as written.
        token: The vocabulary token the field name matched.
        enrolled: Whether the annotation carries anything other than bare ``str``.
    """

    path: str
    line: int
    model: str
    field: str
    annotation: str
    token: str
    enrolled: bool

    def key(self) -> tuple[str, str, str]:
        """The identity a ledger entry matches on."""
        return (self.path, self.model, self.field)

    def rendered(self) -> str:
        """A single deterministic line for a report or a failure message."""
        state = "enrolled" if self.enrolled else "BARE"
        return f"{self.path}:{self.line} {self.model}.{self.field}: {self.annotation} [{state}] token={self.token}"


def _base_names(node: ast.ClassDef) -> tuple[str, ...]:
    """Every base of ``node`` reduced to its bare trailing name."""
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
        elif isinstance(base, ast.Subscript):
            inner = base.value
            names.append(inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", ""))
    return tuple(name for name in names if name)


def _model_class_names(trees: dict[str, ast.Module]) -> frozenset[str]:
    """Class names reachable from ``BaseModel`` by inheritance, as a fixpoint.

    Matched by BARE class name across the corpus rather than by resolved import,
    which is the deliberate trade: resolving imports would need the whole module
    graph, and a bare-name collision between a model and a non-model of the same
    name is the only way this over-reaches. The limit is stated in the module
    docstring rather than hidden behind a green run.
    """
    bases: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases.setdefault(node.name, set()).update(_base_names(node))
    models = {_MODEL_ROOT}
    changed = True
    while changed:
        changed = False
        for name, parents in bases.items():
            if name not in models and parents & models:
                models.add(name)
                changed = True
    return frozenset(models)


def _production_sources() -> tuple[tuple[str, str], ...]:
    """Read current non-test, non-generated production Python sources once."""
    entries: list[tuple[str, str]] = []
    for path in scan_directory(_SOURCE_ROOT, pattern="*.py", recursive=True):
        relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
        if "tests" in path.relative_to(_SOURCE_ROOT).parts or "generated" in path.relative_to(_SOURCE_ROOT).parts:
            continue
        entries.append((relative, path.read_text(encoding="utf-8")))
    return tuple(entries)


def _parsed(sources: tuple[tuple[str, str], ...]) -> dict[str, ast.Module]:
    """Parse each production source in the current snapshot."""
    trees: dict[str, ast.Module] = {}
    for path, source in sources:
        try:
            trees[path.replace("\\", "/")] = ast.parse(source)
        except SyntaxError:
            continue
    return trees


def _is_private_attr(statement: ast.AnnAssign) -> bool:
    """Whether ``statement`` is a Pydantic ``PrivateAttr`` rather than a field."""
    value = statement.value
    if not isinstance(value, ast.Call):
        return False
    function = value.func
    return (isinstance(function, ast.Name) and function.id == "PrivateAttr") or (
        isinstance(function, ast.Attribute) and function.attr == "PrivateAttr"
    )


def identifier_fields(sources: tuple[tuple[str, str], ...]) -> tuple[IdentifierField, ...]:
    """Every identifier-named production model field across pinned sources.

    Split from a revision-reading entry point so the bite proof and the
    contract tests can drive an explicit source snapshot, keeping them
    independent of whatever happens to be committed when they run.
    """
    trees = _parsed(sources)
    models = _model_class_names(trees)
    vocabulary = namespace_vocabulary()
    found: list[IdentifierField] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in models:
                continue
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                if _is_private_attr(statement):
                    continue
                name = statement.target.id
                if name.startswith(_DISPLAY_COMPANION_PREFIX):
                    continue
                token = matched_token(name, vocabulary)
                if token is None:
                    continue
                annotation = annotation_text(statement)
                found.append(
                    IdentifierField(
                        path=path,
                        line=statement.lineno,
                        model=node.name,
                        field=name,
                        annotation=annotation,
                        token=token,
                        enrolled=not is_bare_str(annotation),
                    )
                )
    return tuple(sorted(found, key=lambda item: (item.path, item.line, item.field)))


def unenrolled(fields: tuple[IdentifierField, ...]) -> tuple[IdentifierField, ...]:
    """The identifier-named fields still declared as a bare ``str``."""
    return tuple(item for item in fields if not item.enrolled)


def _worklist(lines: tuple[str, ...], header: str) -> str:
    """Render a failure as a worklist, so a red gate is actionable rather than noisy."""
    body = "\n".join(f"  {line}" for line in lines)
    return f"{header}\n{body}\n"


@pytest.fixture(scope="module")
def production_fields() -> tuple[IdentifierField, ...]:
    """The current-worktree identifier-named production model fields."""
    return identifier_fields(_production_sources())


def test_vocabulary_derives_from_the_live_alias_family() -> None:
    """The vocabulary is computed from aliases that exist, not from a stale list.

    A fixture anchor for the derivation itself: if the identity facade stopped
    exporting aliases, the vocabulary would empty and every other assertion here
    would pass vacuously.
    """
    aliases = identifier_aliases()
    vocabulary = namespace_vocabulary()
    assert aliases, "core.identity exports no type aliases; the vocabulary would be empty"
    for alias in aliases:
        assert _snake(alias) in vocabulary, f"alias {alias} contributed no vocabulary token"
    assert "expediente_id" in vocabulary, "the aeat_ issuer prefix is no longer being stripped"


def test_declared_shared_stems_still_name_live_aliases() -> None:
    """Every declared stem's aliases still exist, so the stem is not vacuous.

    A stem is a hand-made claim that two aliases name one concept. If either
    alias is renamed or removed, the claim is no longer backed and must be
    re-made rather than left asserting a vocabulary token nothing supports.
    """
    exported = set(identifier_aliases())
    for stem in _SHARED_STEMS:
        missing = tuple(alias for alias in stem.aliases if alias not in exported)
        assert not missing, (
            f"shared stem {stem.stem!r} names aliases that no longer exist on core.identity: "
            f"{missing}. Re-adjudicate the stem rather than leaving it standing."
        )
        assert len(stem.aliases) >= 2, f"shared stem {stem.stem!r} needs two or more aliases to be a stem"


def test_free_text_populations_are_outside_the_vocabulary() -> None:
    """The rehomed exclusions still hold against the derived vocabulary.

    This is the falsifiable half of the rehoming. If an alias were ever added
    naming one of these populations, the exclusion prose would silently become
    a lie; here it fails instead and forces a re-adjudication.
    """
    vocabulary = namespace_vocabulary()
    for population in _FREE_TEXT_POPULATIONS:
        assert population.reason.strip(), f"free-text population {population.name!r} states no reason"
        for token in population.field_tokens:
            assert token not in vocabulary, (
                f"{token!r} is excluded as {population.name!r} but IS now in the derived "
                f"vocabulary. An alias was added that names it; re-adjudicate the exclusion."
            )


def test_free_text_anchors_are_still_bare_free_text(production_fields: tuple[IdentifierField, ...]) -> None:
    """The AEAT-prose anchors still exist and still carry free text.

    Without this the population would pass vacuously once the fields were
    renamed or retyped: the exclusion would keep excusing code that no longer
    exists. The anchors are read from the class body directly rather than from
    the candidate set, because these fields deliberately do NOT match the
    vocabulary and so never appear as candidates.
    """
    trees = _parsed(_production_sources())
    for path, model, field in _FREE_TEXT_ANCHORS:
        tree = trees.get(path)
        assert tree is not None, f"free-text anchor module {path} no longer exists"
        annotations = {
            statement.target.id: annotation_text(statement)
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == model
            for statement in node.body
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
        }
        assert field in annotations, f"free-text anchor {model}.{field} no longer exists in {path}"
        assert is_bare_str(annotations[field]), (
            f"{model}.{field} is no longer free text ({annotations[field]}). The "
            f"AEAT-prose exclusion is obsolete and must be re-adjudicated."
        )


def test_display_companions_have_a_full_sibling() -> None:
    """Every excluded ``short_<x>`` field has a sibling ``<x>`` on the same model.

    The anchor for the structural ``short_`` exclusion. A truncated companion is
    excusable only because the full identity is declared beside it; if the full
    field is renamed or dropped, the companion is no longer a companion and the
    exclusion must be revisited rather than passing vacuously.

    Scoped to companions whose full sibling name is itself identifier
    vocabulary, so an unrelated ``short_description`` is not swept in.
    """
    trees = _parsed(_production_sources())
    models = _model_class_names(trees)
    vocabulary = namespace_vocabulary()
    orphans: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in models:
                continue
            names = {
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
            }
            for name in sorted(names):
                if not name.startswith(_DISPLAY_COMPANION_PREFIX):
                    continue
                full = name.removeprefix(_DISPLAY_COMPANION_PREFIX)
                if matched_token(full, vocabulary) is None or full in names:
                    continue
                orphans.append(f"{path} {node.name}.{name} has no sibling {full}")
    assert not orphans, _worklist(
        tuple(orphans),
        "Truncated display companions without the full identity beside them. The "
        "short_ exclusion assumes the full field is declared on the same model:",
    )


def test_no_unenrolled_identifier_field_outside_the_adjudications(
    production_fields: tuple[IdentifierField, ...],
) -> None:
    """No identifier-named model field is bare ``str`` unless adjudicated.

    The ratchet. A new bare identifier field fails here and must either be
    typed or entered in a ledger with a reason -- never silently accepted.
    """
    adjudicated = {entry.key() for entry in _ADJUDICATED}
    open_sites = tuple(item for item in unenrolled(production_fields) if item.key() not in adjudicated)
    assert not open_sites, _worklist(
        tuple(item.rendered() for item in open_sites),
        "Identifier-named model fields declared as bare `str` and not adjudicated. "
        "Type each with its core.identity alias, or record a falsifiable adjudication:",
    )


def test_no_stale_adjudication(production_fields: tuple[IdentifierField, ...]) -> None:
    """Every adjudicated site still answers a live bare occurrence.

    A stale exemption is worse than a missing one: it reads as a considered
    judgement about code that has since moved or been fixed, and it silently
    widens to whatever later occupies its key.
    """
    live = {item.key() for item in unenrolled(production_fields)}
    stale = tuple(entry for entry in _ADJUDICATED if entry.key() not in live)
    assert not stale, _worklist(
        tuple(f"{entry.path} {entry.model}.{entry.field}" for entry in stale),
        "Adjudicated exemptions answering no live bare field. The site was typed, "
        "renamed or removed; strike the entry:",
    )


def test_every_adjudication_states_a_reason() -> None:
    """An exemption without a stated reason is indistinguishable from an oversight."""
    silent = tuple(entry for entry in _ADJUDICATED if not entry.group.strip() or not entry.reason.strip())
    assert not silent, _worklist(
        tuple(f"{entry.path} {entry.model}.{entry.field}" for entry in silent),
        "Adjudicated exemptions with no group or stated reason:",
    )


def test_detector_reports_a_bare_identifier_field_and_ignores_an_enrolled_one() -> None:
    """The detector fires on a bare identifier field and stays silent on a typed one.

    Drives the real scanner over an explicit source snapshot, which is the same
    shape the sibling censuses under ``dev/identity/`` use for their contract
    tests. Without this, a matcher that silently stopped matching would make
    every assertion above pass while detecting nothing.
    """
    source = (
        "from pydantic import BaseModel\n"
        "class Probe(BaseModel):\n"
        "    expediente_id: str\n"
        "    transaction_id: TransactionId\n"
        "    short_work_unit_id: str\n"
        "    unrelated_label: str\n"
    )
    found = identifier_fields((("src/cadrumo/probe.py", source),))
    by_field = {item.field: item for item in found}
    assert set(by_field) == {"expediente_id", "transaction_id"}, (
        f"unexpected candidate set {sorted(by_field)}: a short_ companion and a "
        f"non-vocabulary field must not be reported"
    )
    assert not by_field["expediente_id"].enrolled
    assert by_field["transaction_id"].enrolled
    assert unenrolled(found) == (by_field["expediente_id"],)


def test_detector_excludes_pydantic_private_attrs() -> None:
    """A ``PrivateAttr`` is implementation state, never an operator model field."""
    source = (
        "from pydantic import BaseModel, PrivateAttr\n"
        "class Probe(BaseModel):\n"
        "    _active_profile_id: str = PrivateAttr(default='')\n"
        "    transaction_id: str\n"
    )
    found = identifier_fields((("src/cadrumo/probe.py", source),))
    assert [item.field for item in found] == ["transaction_id"]
