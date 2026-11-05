"""Every generated fixture family, declared once: producer, inputs, outputs and check.

A family's output root is data. While the projections are committed in place
the root is their source directory and the family is not removable; moving the
projections into the build tree changes the root and the ``committed`` flag
here, not the code that seeds, stamps or checks them.

Commands are argument vectors. ``{python}`` stands for the interpreter running
this tooling, and ``{output}`` for the scratch directory a determinism run
writes into. Every command runs from the repository root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..first_party_source import PRODUCT_SOURCE_ROOTS

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
FIXTURE_ROOT: Final[str] = f"{FRONTEND}/src/dev/fixtures"
PERSONA_ROOT: Final[str] = "dev/fixtures/personas"

_SCRIPTS: Final[str] = f"{FRONTEND}/scripts"
_PERSONAS: Final = InputGroup("personas", (PERSONA_ROOT,))
_PRODUCT: Final = InputGroup("product-source", PRODUCT_SOURCE_ROOTS)
_LOCK: Final = InputGroup("lockfile", ("uv.lock",))
_FRONTEND_LOCK: Final = InputGroup("frontend-lockfile", (f"{FRONTEND}/package-lock.json",))
_FRONTEND_PACKAGES: Final = Prerequisite(f"{FRONTEND}/node_modules", "just setup-desktop-frontend")
#: The development modules every producer imports for its paths, output and scratch directories.
_TOOLING: Final = (
    "dev/_paths.py",
    "dev/prettier_json.py",
    "dev/temporary_output.py",
    "dev/fixture_projections/producer_output.py",
)


def _python_script(path: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", path, *arguments)


def _python_module(module: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", "-m", module, *arguments)


def _pytest(*targets: str) -> tuple[str, ...]:
    return _python_module("pytest", "-q", "-n0", "-p", "no:cacheprovider", *targets)


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
    extra_checks: tuple[Command, ...] = (),
) -> FixtureFamily:
    """A Python producer: it writes in place, checks the stored text with ``--check``, redirects with ``--output``."""
    inputs = _common(*sources)
    if questions is not None:
        inputs = (*inputs, InputGroup("questions", (questions,)))
    return FixtureFamily(
        name=name,
        summary=summary,
        inputs=inputs,
        producer=Command(entry),
        check=(Command((*entry, "--check")), *extra_checks),
        output_root=FIXTURE_ROOT,
        outputs=outputs,
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
    extra_checks: tuple[Command, ...] = (),
) -> FixtureFamily:
    path = f"{_SCRIPTS}/{script}"
    return _python_producer(
        name,
        _python_script(path),
        (path, *support),
        outputs,
        summary,
        questions=questions,
        extra_checks=extra_checks,
    )


_MODELO_PRODUCER: Final = f"{_SCRIPTS}/modelo_fixtures.py"
_LEDGER_TESTS: Final = "src/cadrumo/application/ledger/tests"
_ASSET_TESTS: Final = "src/cadrumo/application/actividad_asset/tests"

FAMILIES: Final[tuple[FixtureFamily, ...]] = (
    FixtureFamily(
        name="modelo-envelopes",
        summary="The window's Modelo wire types, relay bounds and scenario envelopes, read through the application.",
        inputs=(
            *_common(_MODELO_PRODUCER, f"{_SCRIPTS}/modelo-fixtures.mjs"),
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
        ),
        producer=Command(("node", f"{_SCRIPTS}/modelo-fixtures.mjs")),
        # Its check renders the wire types and bounds afresh but only validates
        # the stored envelopes against their models, so it does not prove their bytes.
        check=(Command(("node", f"{_SCRIPTS}/modelo-fixtures.mjs", "--check")),),
        output_root=f"{FRONTEND}/src",
        outputs=("dev/fixtures/modelo/*.json", "shell/modeloContract.ts", "shell/relayBounds.ts"),
        determinism=Command(_python_script(_MODELO_PRODUCER, "envelopes", OUTPUT)),
        prerequisites=(_FRONTEND_PACKAGES,),
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
        "ledger-entry-options",
        "ledger_entry_options.py",
        ("ledgerEntryOptions.json",),
        "The periods the ledger's period read answers, recorded into the entry options.",
        questions="dev/fixtures/ledger-entry-option-questions",
        support=(f"{_LEDGER_TESTS}/entry_option_periods_recording_support.py",),
        # The producer writes only the periods; these read-only tests hold the
        # fixture's other sections to what the backend serves.
        extra_checks=(
            Command(_pytest(f"{_LEDGER_TESTS}/test_entry_options.py", f"{_LEDGER_TESTS}/test_entry_limits.py")),
        ),
    ),
    FixtureFamily(
        name="docs-sequence-seeds",
        summary="The persona-derived profile frames of the documentation seed recipes.",
        inputs=(),
        check=(Command(_python_module("dev.docs.sequences", "seeds", "--check")),),
    ),
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
