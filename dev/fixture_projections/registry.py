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


@dataclass(frozen=True, slots=True)
class InputGroup:
    """A named set of repository files or directories, given relative to the repository root."""

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


FRONTEND: Final[str] = "native/desktop/frontend"
FIXTURE_ROOT: Final[str] = f"{FRONTEND}/src/dev/fixtures"
PERSONA_ROOT: Final[str] = "dev/fixtures/personas"

_PERSONAS: Final = InputGroup("personas", (PERSONA_ROOT,))
_PRODUCT: Final = InputGroup("product-source", PRODUCT_SOURCE_ROOTS)
_LOCK: Final = InputGroup("lockfile", ("uv.lock",))
_FRONTEND_LOCK: Final = InputGroup("frontend-lockfile", (f"{FRONTEND}/package-lock.json",))
_FRONTEND_PACKAGES: Final = Prerequisite(f"{FRONTEND}/node_modules", "just setup-desktop-frontend")
#: The development modules every producer imports for its paths and scratch directories.
_TOOLING: Final = ("dev/_paths.py", "dev/temporary_output.py")


def _python_script(path: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", path, *arguments)


def _python_module(module: str, *arguments: str) -> tuple[str, ...]:
    return (PYTHON, "-B", "-m", module, *arguments)


def _pytest(*targets: str) -> tuple[str, ...]:
    return _python_module("pytest", "-q", "-n0", "-p", "no:cacheprovider", *targets)


def _common(*producer: str) -> tuple[InputGroup, ...]:
    return (InputGroup("producer", (*producer, *_TOOLING)), _PERSONAS, _PRODUCT, _LOCK)


def _desktop_fixture(name: str, module: str, output: str, summary: str) -> FixtureFamily:
    source = f"dev/{module}.py"
    return FixtureFamily(
        name=name,
        summary=summary,
        inputs=_common(source),
        producer=Command(_python_module(f"dev.{module}")),
        check=(Command(_python_module(f"dev.{module}", "--check")),),
        output_root=FIXTURE_ROOT,
        outputs=(output,),
    )


def _recorded_by_test(
    name: str, test_module: str, record_test: str, switch: tuple[str, str], output: str, summary: str
) -> FixtureFamily:
    return FixtureFamily(
        name=name,
        summary=summary,
        inputs=_common(test_module),
        producer=Command(_pytest(f"{test_module}::{record_test}"), environment=(switch,)),
        check=(Command(_pytest(test_module)),),
        output_root=FIXTURE_ROOT,
        outputs=(output,),
    )


_MODELO_PRODUCER: Final = f"{FRONTEND}/scripts/modelo_fixtures.py"
_LEDGER_TESTS: Final = "src/cadrumo/application/ledger/tests"

FAMILIES: Final[tuple[FixtureFamily, ...]] = (
    FixtureFamily(
        name="modelo-envelopes",
        summary="The window's Modelo scenario envelopes, read through the application's read path.",
        inputs=(
            *_common(_MODELO_PRODUCER, f"{FRONTEND}/scripts/modelo-fixtures.mjs"),
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
        producer=Command(("node", f"{FRONTEND}/scripts/modelo-fixtures.mjs")),
        check=(Command(("node", f"{FRONTEND}/scripts/modelo-fixtures.mjs", "--check")),),
        output_root=f"{FIXTURE_ROOT}/modelo",
        outputs=("*.json",),
        determinism=Command(_python_script(_MODELO_PRODUCER, "envelopes", OUTPUT)),
        prerequisites=(_FRONTEND_PACKAGES,),
    ),
    FixtureFamily(
        name="ledger-served-words",
        summary="The sentences the Ledger operations serve with each refusal, in every language.",
        inputs=_common(f"{FRONTEND}/scripts/ledger_served_words.py"),
        producer=Command(_python_script(f"{FRONTEND}/scripts/ledger_served_words.py")),
        check=(Command(_python_script(f"{FRONTEND}/scripts/ledger_served_words.py", "--check")),),
        output_root=FIXTURE_ROOT,
        outputs=("ledgerServedWords.json",),
    ),
    FixtureFamily(
        name="ledger-recordings",
        summary="What the Ledger's pure reads answer for each recorded question.",
        inputs=(
            *_common(f"{FRONTEND}/scripts/ledger_recordings.py"),
            InputGroup("questions", ("dev/fixtures/ledger-recording-questions",)),
        ),
        producer=Command(_python_script(f"{FRONTEND}/scripts/ledger_recordings.py")),
        check=(Command(_python_script(f"{FRONTEND}/scripts/ledger_recordings.py", "--check")),),
        output_root=FIXTURE_ROOT,
        outputs=(
            "ledgerInvoicePreview.json",
            "ledgerInvoiceMatch.json",
            "ledgerInvoiceDuplicate.json",
            "ledgerRuleTrial.json",
            "ledgerSplitCheck.json",
        ),
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
    _recorded_by_test(
        "ledger-staged-check",
        f"{_LEDGER_TESTS}/test_staged_check_recording.py",
        "test_record_the_questions_the_fixtures_could_not_answer",
        ("CADRUMO_STAGED_CHECK_UNRECORDED", "all"),
        "ledgerStagedCheck.json",
        "The staged-check answers for every question the recording holds.",
    ),
    _recorded_by_test(
        "assets-served-words",
        "src/cadrumo/application/actividad_asset/tests/test_served_words_recording.py",
        "test_record_the_questions_the_fixtures_could_not_answer",
        ("CADRUMO_ASSET_WORDS_UNRECORDED", "all"),
        "assetsServedWords.json",
        "The register's sentences for every question the recording holds.",
    ),
    FixtureFamily(
        name="ledger-entry-options",
        summary="The periods the ledger's period read answers, recorded into the entry options.",
        inputs=_common(
            f"{_LEDGER_TESTS}/test_entry_options_period_recording.py",
            f"{_LEDGER_TESTS}/test_entry_options.py",
            f"{_LEDGER_TESTS}/test_entry_limits.py",
        ),
        producer=Command(
            _pytest(f"{_LEDGER_TESTS}/test_entry_options_period_recording.py::test_record_the_periods"),
            environment=(("CADRUMO_RECORD_ENTRY_OPTION_PERIODS", "1"),),
        ),
        check=(
            Command(
                _pytest(
                    f"{_LEDGER_TESTS}/test_entry_options_period_recording.py",
                    f"{_LEDGER_TESTS}/test_entry_options.py",
                    f"{_LEDGER_TESTS}/test_entry_limits.py",
                )
            ),
        ),
        output_root=FIXTURE_ROOT,
        outputs=("ledgerEntryOptions.json",),
    ),
    FixtureFamily(
        name="docs-sequences",
        summary="The committed documentation sequence goldens, executed against the real CLI.",
        inputs=(),
        check=(Command(_python_module("dev.docs.sequences", "check")),),
    ),
)


def family_named(name: str) -> FixtureFamily:
    """Return the family called ``name``.

    Raises:
        KeyError: When no family has that name; the message lists the known names.
    """
    for family in FAMILIES:
        if family.name == name:
            return family
    known = ", ".join(family.name for family in FAMILIES)
    raise KeyError(f"No fixture family {name!r}; known families: {known}")
