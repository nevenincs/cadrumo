"""Every generated fixture family, declared once: producer, inputs, outputs and check.

A family's output root is data. A generated window family writes into the
window projections of the selected CMake build tree, named by ``{window}``, and
is removable; a family whose outputs were committed in place would name
its source directory and set ``committed``, and the code that seeds, stamps or
checks them would not change.

Commands are argument vectors. ``{python}`` stands for the interpreter running
this tooling, ``{output}`` for the scratch directory a determinism run
writes into, and ``{window}`` for the window projections' directory. Every command runs from the repository root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..first_party_source import PRODUCT_SOURCE_ROOTS
from .location import WINDOW_ROOT

PYTHON: Final[str] = "{python}"
OUTPUT: Final[str] = "{output}"

#: Environment switches that once made a test write a recording. No command
#: reads them now, and every command runs without them, so a switch left set in
#: a shell can never turn a check into a writer.
RECORDING_SWITCHES: Final[tuple[str, ...]] = (
    "CADRUMO_STAGED_CHECK_UNRECORDED",
    "CADRUMO_ASSET_WORDS_UNRECORDED",
    "CADRUMO_RECORD_ENTRY_OPTION_PERIODS",
)


@dataclass(frozen=True, slots=True)
class InputGroup:
    """A named set of repository files or directories, given relative to the repository root.

    Every named path must exist: a mistyped path is refused, never digested as empty.
    """

    label: str
    paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Command:
    """An argument vector and the environment entries it adds to the inherited environment."""

    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Prerequisite:
    """A repository path a family's commands need, and the recipe that provides it."""

    path: str
    remedy: str


@dataclass(frozen=True, slots=True)
class FixtureFamily:
    """One producer's projection.

    A family with no producer is check-only: its outputs are committed
    assertions, so it is neither seeded nor stamped, only checked.

    ``check_proves_outputs`` says the check renders every output afresh and
    compares its text with the stored one. Only such a family's unstamped
    outputs may be adopted by stamping them after a passing check, without
    producing them again.
    """

    name: str
    summary: str
    inputs: tuple[InputGroup, ...]
    check: tuple[Command, ...]
    producer: Command | None = None
    output_root: str | None = None
    outputs: tuple[str, ...] = ()
    committed: bool = True
    determinism: Command | None = None
    prerequisites: tuple[Prerequisite, ...] = ()
    check_proves_outputs: bool = False


FRONTEND: Final[str] = "native/desktop/frontend"
PERSONA_ROOT: Final[str] = "dev/fixtures/personas"

_SCRIPTS: Final[str] = f"{FRONTEND}/scripts"
_PERSONAS: Final = InputGroup("personas", (PERSONA_ROOT,))
_PRODUCT: Final = InputGroup("product-source", PRODUCT_SOURCE_ROOTS)
_LOCK: Final = InputGroup("lockfile", ("uv.lock",))
_FRONTEND_LOCK: Final = InputGroup("frontend-lockfile", (f"{FRONTEND}/package-lock.json",))
_FRONTEND_PACKAGES: Final = Prerequisite(f"{FRONTEND}/node_modules", "just setup-desktop-frontend")
#: The development modules every producer imports for its paths, output and scratch directories.
_TOOLING: Final = (
    "dev/paths.py",
    "dev/prettier_json.py",
    "dev/temporary_output.py",
    "dev/fixture_projections/producer_output.py",
)


def _python_script(path: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", path, *arguments)


def _python_module(module: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", "-m", module, *arguments)


def _common(*producer: str) -> tuple[InputGroup, ...]:
    return (InputGroup("producer", (*producer, *_TOOLING)), _PERSONAS, _PRODUCT, _LOCK)


def _python_producer(
    name: str,
    entry: tuple[str, ...],
    sources: tuple[str, ...],
    outputs: tuple[str, ...],
    summary: str,
    *,
    questions: str | None = None,
) -> FixtureFamily:
    """A Python producer: it writes into its folder of the window projections.

    ``--check`` compares the stored text and ``--output`` redirects the same bytes.
    """
    inputs = _common(*sources)
    if questions is not None:
        inputs = (*inputs, InputGroup("questions", (questions,)))
    return FixtureFamily(
        name=name,
        summary=summary,
        inputs=inputs,
        producer=Command(entry),
        check=(Command((*entry, "--check")),),
        output_root=WINDOW_ROOT,
        outputs=tuple(f"{name}/{output}" for output in outputs),
        committed=False,
        determinism=Command((*entry, "--output", OUTPUT)),
        check_proves_outputs=True,
    )


def _desktop_fixture(name: str, module: str, output: str, summary: str) -> FixtureFamily:
    return _python_producer(name, _python_module(f"dev.{module}"), (f"dev/{module}.py",), (output,), summary)


def _script(
    name: str,
    script: str,
    outputs: tuple[str, ...],
    summary: str,
    *,
    questions: str | None = None,
    support: tuple[str, ...] = (),
) -> FixtureFamily:
    path = f"{_SCRIPTS}/{script}"
    return _python_producer(
        name,
        _python_script(path),
        (path, *support),
        outputs,
        summary,
        questions=questions,
    )


_MODELO_PRODUCER: Final = f"{_SCRIPTS}/modelo_fixtures.py"
_MODELO_DRIVER: Final = f"{_SCRIPTS}/modelo-fixtures.mjs"
#: The module bound's one definition, which the producer sizes its modules within and reports, and the driver's
#: refusal of a generated module past it.
_MODULE_BOUND: Final = ("dev/quality/typescript_module_size.py", f"{_SCRIPTS}/generated-module-bound.mjs")
#: The Modelo wire types and the envelopes read the same application, host sources and personas.
_MODELO_INPUTS: Final = (
    *_common(_MODELO_PRODUCER, _MODELO_DRIVER, *_MODULE_BOUND),
    InputGroup(
        "host-source",
        (
            "native/desktop/src-tauri/src/shell/modelo",
            "native/desktop/src-tauri/src/shell/relay.rs",
            "native/desktop/src-tauri/src/agent/person.rs",
            "native/application/src/person_operations.rs",
            "native/application/src/person_operations",
        ),
    ),
    _FRONTEND_LOCK,
)
_LEDGER_TESTS: Final = "src/cadrumo/application/ledger/tests"
_ASSET_TESTS: Final = "src/cadrumo/application/actividad_asset/tests"

FAMILIES: Final[tuple[FixtureFamily, ...]] = (
    FixtureFamily(
        name="modelo-envelopes",
        summary="The window's Modelo scenario envelopes, read through the application for the catalogue's personas.",
        inputs=_MODELO_INPUTS,
        producer=Command(("node", _MODELO_DRIVER, "--envelopes", "--fixtures", WINDOW_ROOT)),
        # Its check validates a seeded envelope against its model, and has nothing to check while none is seeded;
        # it does not prove the stored bytes, which the determinism build and the tests that read them do.
        check=(Command(("node", _MODELO_DRIVER, "--envelopes", "--check", "--fixtures", WINDOW_ROOT)),),
        output_root=WINDOW_ROOT,
        outputs=("modelo/*.json",),
        committed=False,
        determinism=Command(_python_script(_MODELO_PRODUCER, "envelopes", OUTPUT)),
        prerequisites=(_FRONTEND_PACKAGES,),
    ),
    FixtureFamily(
        name="modelo-wire-types",
        summary="The window's Modelo wire types and relay bounds, generated from the registered contracts.",
        inputs=_MODELO_INPUTS,
        producer=Command(("node", _MODELO_DRIVER, "--contract")),
        check=(Command(("node", _MODELO_DRIVER, "--contract", "--check")),),
        output_root=f"{FRONTEND}/src",
        outputs=("shell/modeloContract/*.ts", "shell/relayBounds.ts", "shell/moduleBound.json"),
        determinism=Command(("node", _MODELO_DRIVER, "--contract", "--output", OUTPUT)),
        prerequisites=(_FRONTEND_PACKAGES,),
        check_proves_outputs=True,
    ),
    _script(
        "ledger-served-words",
        "ledger_served_words.py",
        ("ledgerServedWords.json",),
        "The sentences the Ledger operations serve with each refusal, in every language.",
    ),
    _script(
        "ledger-recordings",
        "ledger_recordings.py",
        (
            "ledgerInvoicePreview.json",
            "ledgerInvoiceMatch.json",
            "ledgerInvoiceDuplicate.json",
            "ledgerRuleTrial.json",
            "ledgerSplitCheck.json",
        ),
        "What the Ledger's pure reads answer for each recorded question.",
        questions="dev/fixtures/ledger-recording-questions",
    ),
    _desktop_fixture(
        "desktop-profile",
        "desktop_profile_fixture",
        "userProfile.json",
        "The desktop demo profile projected through the profile schema and overview.",
    ),
    _desktop_fixture(
        "desktop-household",
        "desktop_household_fixture",
        "household.json",
        "The household states read through the profile operations in every language.",
    ),
    _desktop_fixture(
        "desktop-imputation-election",
        "desktop_imputation_election_fixture",
        "imputationElection.json",
        "The imputation election states read through the profile operations.",
    ),
    _desktop_fixture(
        "desktop-year-authority",
        "desktop_year_authority_fixture",
        "yearAuthority.json",
        "The year bounds, support envelope and per-year Modelo 100 editions the backend serves.",
    ),
    _desktop_fixture(
        "desktop-withholding-refusal-words",
        "desktop_withholding_refusal_words_fixture",
        "ledgerWithholdingRefusalWords.json",
        "The withholding refusal sentences the backend serves, in every language.",
    ),
    _script(
        "ledger-staged-check",
        "ledger_staged_check.py",
        ("ledgerStagedCheck.json",),
        "The staged-check answers for every committed question.",
        questions="dev/fixtures/ledger-staged-check-questions",
        support=(f"{_LEDGER_TESTS}/staged_check_recording_support.py",),
    ),
    _script(
        "assets-served-words",
        "assets_served_words.py",
        ("assetsServedWords.json",),
        "The register's sentences for every committed question.",
        questions="dev/fixtures/assets-served-words-questions",
        support=(f"{_ASSET_TESTS}/served_words_recording_support.py",),
    ),
    _script(
        "assets-register",
        "assets_register.py",
        ("assetsRegister.json",),
        "What the register answers for the Assets fixtures' scenario register, replayed from its steps.",
        questions="dev/fixtures/assets-register-scenario",
        support=(
            f"{_ASSET_TESTS}/register_recording_support.py",
            f"{_ASSET_TESTS}/register_support.py",
            f"{_ASSET_TESTS}/ledger_support.py",
        ),
    ),
    _script(
        "ledger-entry-options",
        "ledger_entry_options.py",
        ("ledgerEntryOptions.json",),
        "The entry options the ledger serves: vocabularies, classification rules, limits and periods.",
        questions="dev/fixtures/ledger-entry-option-questions",
        support=(f"{_LEDGER_TESTS}/entry_option_periods_recording_support.py",),
    ),
    FixtureFamily(
        name="docs-sequence-seeds",
        summary="The persona-derived profile frames of the documentation seed recipes.",
        inputs=(),
        check=(Command(_python_module("dev.docs.sequences", "seeds", "--check")),),
    ),
)


def window_families(families: tuple[FixtureFamily, ...] = FAMILIES) -> tuple[FixtureFamily, ...]:
    """The generated families whose outputs are the window projections the desktop frontend imports."""
    return tuple(
        family
        for family in families
        if family.producer is not None and not family.committed and family.output_root == WINDOW_ROOT
    )


def family_named(name: str, families: tuple[FixtureFamily, ...] = FAMILIES) -> FixtureFamily:
    """Return the family called ``name``.

    Raises:
        KeyError: When no family has that name; the message lists the known names.
    """
    for family in families:
        if family.name == name:
            return family
    known = ", ".join(family.name for family in families)
    raise KeyError(f"No fixture family {name!r}; known families: {known}")
