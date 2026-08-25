"""Root-grammar invariants for the CLI surface.

The CLI exposes exactly two roots (`config` and `app`) with a fixed
noun-group ordering. These tests assert that the rejected verbs and
surfaces are not mounted, so the CLI grammar stays the intentional
one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import scan_directory
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import _isolated_state

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_isolated_state"]


def test_root_does_not_register_bare_reconcile_alias() -> None:
    """`cadrumo reconcile` is not a root verb; reconcile only lives
    under `aeat app modelo`."""

    result = invoke_cached_cli(["reconcile", "--help"])
    assert result.exit_code != 0, result.output


def test_app_does_not_register_deadlines_subgroup() -> None:
    """`aeat app deadlines` is not a verb tree. Deadline data is
    surfaced through the overview verb group."""

    result = invoke_cached_cli(["app", "deadlines", "--help"])
    assert result.exit_code != 0, result.output


def test_app_rejects_retired_consumer_command() -> None:
    """The product CLI does not provision downstream consumers."""

    result = invoke_cached_cli(["app", "agent", "--help"])
    assert result.exit_code != 0, result.output


def test_modelo_audit_export_remains_distinct_from_modelo_export() -> None:
    """`aeat app modelo export` (fichero-BOE exporter) and
    `aeat app modelo audit export` (evidence-bundle exporter) are
    distinct sibling verbs. Both must resolve, and each must carry
    its own purpose-specific help so operators are not confused."""

    audit_help = invoke_cached_cli(["app", "modelo", "audit", "export", "--help"])
    assert audit_help.exit_code == 0, audit_help.output

    modelo_export_help = invoke_cached_cli(["app", "modelo", "export", "--help"])
    assert modelo_export_help.exit_code == 0, modelo_export_help.output

    assert "fichero-BOE" in modelo_export_help.output
    assert "fichero-BOE" not in audit_help.output


def test_root_does_not_register_bare_audit_alias() -> None:
    """`cadrumo audit` is not a root verb. The evidence-bundle contract
    explicitly forbids root `cadrumo audit` or `aeat run` commands; the
    audit surface only lives under `aeat app modelo audit`."""

    result = invoke_cached_cli(["audit", "--help"])
    assert result.exit_code != 0, result.output


def test_root_does_not_register_bare_run_alias() -> None:
    """`aeat run` is not a root verb per the evidence-bundle contract."""

    result = invoke_cached_cli(["run", "--help"])
    assert result.exit_code != 0, result.output


def test_app_does_not_register_audit_subgroup_outside_modelo() -> None:
    """`aeat app audit` would split the audit verb tree away from the
    work-unit-bound modelo verb tree. The evidence-bundle contract scopes
    the surface to `aeat app modelo audit`; any sibling `aeat app
    audit` mount would be a redirection target that splits ownership."""

    result = invoke_cached_cli(["app", "audit", "--help"])
    assert result.exit_code != 0, result.output


def test_modelo_audit_verbs_only_register_canonical_three() -> None:
    """Only the three canonical audit verbs (show / check / export) are mounted
    under `aeat app modelo audit`. `replay` was retired (it duplicated `check`),
    and any other leaf (verify, status, list, browse, run, etc.) violates the
    ratified grammar from the evidence-bundle contract."""

    forbidden_leaves = (
        ("replay",),
        ("verify",),
        ("run",),
        ("status",),
        ("list",),
        ("browse",),
        ("inspect",),
    )
    for leaf in forbidden_leaves:
        result = invoke_cached_cli(["app", "modelo", "audit", *leaf, "--help"])
        assert result.exit_code != 0, (leaf, result.output)

    accepted_leaves = (("show",), ("check",), ("export",))
    for leaf in accepted_leaves:
        result = invoke_cached_cli(["app", "modelo", "audit", *leaf, "--help"])
        assert result.exit_code == 0, (leaf, result.output)


def test_config_does_not_register_retired_custody_spellings() -> None:
    """The retired custody spellings are unmounted everywhere.

    Two retirements, one assertion. The older one dropped ``config rekey``,
    ``config show-recovery`` and ``config verify-recovery``. The per-profile
    custody cutover then retired their successors too: the global recovery
    facade that mirrored a single shared master key is gone, taking the
    forgotten-passphrase door and the recovery-code subgroup with it —
    recovery enrolment and restore are per-profile custody operations now.

    None of these may resolve. A spelling that quietly re-mounts would hand an
    operator a verb with no owner behind it, on the data-custody path.

    The passphrase family is deliberately NOT asserted here. It does not
    resolve either, but no ruling retired it: credential rotation is missing
    from every layer, and ``test_config_custody_profile_lifecycle`` holds a
    deliberately-failing assertion that keeps that gap visible. Asserting the
    family retired here would contradict that module and encode a product
    decision nobody has taken.
    """

    for verb in (
        "rekey",
        "show-recovery",
        "verify-recovery",
        "recover",
        "recovery",
    ):
        result = invoke_cached_cli(["config", verb, "--help"])
        assert result.exit_code != 0, (verb, result.output)


#: Retired custody command spellings, each keyed to the retirement that removed
#: it. Membership is a claim that an accepted ruling deleted the door, NOT
#: merely that the verb does not resolve today: an absent verb whose absence
#: nobody ruled on is a missing capability, and enrolling it here would launder
#: that gap into a retirement. ``config passphrase`` is the live example and is
#: deliberately absent — ``test_config_custody_profile_lifecycle`` holds a
#: deliberately-failing assertion that credential rotation must exist, and this
#: module previously asserted the opposite of it.
#:
#: Every entry is anchored by
#: :func:`test_every_retired_spelling_still_names_an_unregistered_verb`, so an
#: entry cannot outlive its subject: re-mounting the family reds this list and
#: forces the entry out rather than letting a stale name pass vacuously.
_RETIRED_CUSTODY_SPELLINGS: tuple[tuple[str, str], ...] = (
    ("config rekey", "master-key rotation door removed by the first custody retirement"),
    ("config show-recovery", "recovery-code display door removed by the first custody retirement"),
    ("config verify-recovery", "recovery-code verification door removed by the first custody retirement"),
    ("--recovery-key", "flag that carried a recovery code on argv, removed with the doors above"),
    (
        "config recover",
        "forgotten-passphrase door of the global recovery facade, deleted by the "
        "per-profile custody cutover; restore is a per-profile custody operation now",
    ),
    (
        "config recovery",
        "recovery-code subgroup (status/create/rotate/verify) of the same global "
        "facade, deleted by the per-profile custody cutover",
    ),
)

#: Files permitted to carry a retired spelling, keyed by repo-relative path and
#: the enclosing function, never by line number. Each entry states why the
#: citation is enforcement rather than instruction. A stale entry FAILS: see
#: :func:`test_every_retired_spelling_exemption_is_still_load_bearing`.
_SPELLING_EXEMPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key.py",
        "test_single_artifact_torn_states_raise",
        "asserts the spelling is ABSENT from the torn-store refusal text; the citation is the probe, not an instruction",
    ),
)


def _retired_spelling_scan_corpus() -> list[Path]:
    """Source, the four locale catalogues, the operator docs, and the contracts."""
    from ....tests import REPO_ROOT

    scanned: list[Path] = []
    src_root = REPO_ROOT / "src" / "cadrumo"
    scanned.extend(scan_directory(src_root, pattern="*.py", recursive=True))
    scanned.extend(scan_directory(src_root / "locales", pattern="*.yml"))
    docs_root = REPO_ROOT / "docs"
    scanned.extend(scan_directory(docs_root, pattern="*.md"))
    for sub in ("how-to", "explanation", "reference", "verification", "architecture"):
        subdir = docs_root / sub
        if subdir.is_dir():
            scanned.extend(scan_directory(subdir, pattern="*.md", recursive=True))
    sequences = docs_root / "_sequences"
    if sequences.is_dir():
        scanned.extend(scan_directory(sequences, pattern="*.seq", recursive=True))

    # Floor the scan corpus: a relocation of the source tree or docs would empty
    # this walk and pass identically to a clean tree, so the retired-spelling guard
    # below would be silently vacuous.
    assert len(scanned) > 500, (
        f"scanned only {len(scanned)} source/locale/doc files under {src_root} and {docs_root}; "
        "the scan corpus collapsed (a package relocation or rename), so an empty offender list "
        "would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    return scanned


def _enclosing_function(path: Path, offset: int) -> str | None:
    """Name the ``def`` enclosing the character ``offset`` in a Python source file."""
    if path.suffix != ".py":
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    line = text.count("\n", 0, offset) + 1
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return None
    enclosing: str | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        end = node.end_lineno or node.lineno
        if node.lineno <= line <= end:
            enclosing = node.name
    return enclosing


def _retired_spelling_citations() -> list[tuple[str, str | None, str]]:
    """Every ``(repo-relative path, enclosing function, spelling)`` citation found."""
    from ....tests import REPO_ROOT

    # This module is the enforcement: every spelling is declared here by
    # construction, so scanning it would report the list against itself.
    this_file = Path(__file__).resolve()
    citations: list[tuple[str, str | None, str]] = []
    for path in _retired_spelling_scan_corpus():
        resolved = path.resolve()
        if resolved == this_file:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # A locale catalogue folds a long translated string across source
        # lines, so a two-word command path routinely straddles a newline and a
        # run of indentation. Searching the raw text misses it: the Spanish
        # catalogue carried a folded citation that this scan reported clean
        # while the sibling gate — which loads the YAML — flagged it. Collapse
        # whitespace runs for catalogues so the folded form reads as the
        # rendered one.
        haystack = " ".join(text.split()) if path.suffix in {".yml", ".yaml"} else text
        for spelling, _reason in _RETIRED_CUSTODY_SPELLINGS:
            offset = haystack.find(spelling)
            if offset < 0:
                continue
            # Report repo-relative where possible, absolute otherwise: a probe
            # may feed this scan a file from outside the tree, and a display
            # concern must never decide whether an offender is reported.
            try:
                display = resolved.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                display = resolved.as_posix()
            citations.append((display, _enclosing_function(resolved, offset), spelling))
    return citations


def test_retired_custody_spellings_absent_from_source_and_docs() -> None:
    """The removed spellings are gone from production source, locales, and docs.

    Scans the Python source tree, the four locale catalogues, the operator
    docs, and the CLI sequence contracts. A retired spelling in any of those
    surfaces would hand a downstream caller a dead instruction.

    This is the one guard that sees a citation carrying no ``aeat`` executable
    token — a bare command path in a policy inventory, a docstring, a comment.
    The sibling conformance gates resolve every ``aeat ...`` citation against
    the live tree and are strictly stronger where the token is present, so
    this list exists for the unprefixed remainder, not as a substitute.
    """
    exempt = {(path, function) for path, function, _reason in _SPELLING_EXEMPTIONS}
    offenders = [
        f"{path}::{function or '<module>'}: {spelling}"
        for path, function, spelling in _retired_spelling_citations()
        if (path, function) not in exempt
    ]
    assert offenders == [], (
        "retired custody spellings are still cited outside the enforcement surfaces:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_every_retired_spelling_still_names_an_unregistered_verb() -> None:
    """Each listed spelling still names a command path the live CLI refuses.

    The fixture anchor for the list above. A spelling whose family is mounted
    again is no longer retired, and leaving it enrolled would make the scan
    forbid the tree from citing a verb it now ships — the exact vacuity a
    pinned-name list invites. Re-mounting reds here first, so the entry is
    removed deliberately rather than discovered by a confusing scan failure.
    """
    for spelling, reason in _RETIRED_CUSTODY_SPELLINGS:
        assert reason.strip(), f"retired spelling {spelling!r} carries no stated reason"
        if spelling.startswith("-"):
            continue  # an option token, not a command path
        result = invoke_cached_cli([*spelling.split(), "--help"])
        assert result.exit_code != 0, (
            f"`{spelling}` resolves in the live CLI but is still enrolled as retired "
            f"({reason}); drop the entry rather than forbidding a live verb"
        )


def test_every_retired_spelling_exemption_is_still_load_bearing() -> None:
    """No exemption outlives the citation it excuses.

    An exemption is where the judgement moves, so a stale one is worse than no
    list: it silently widens the guard. Each entry must name a file that still
    exists, still carries a retired spelling, and still carries it inside the
    declared enclosing function.
    """
    live = {(path, function) for path, function, _spelling in _retired_spelling_citations()}
    stale = [
        f"{path}::{function} ({reason})"
        for path, function, reason in _SPELLING_EXEMPTIONS
        if (path, function) not in live
    ]
    assert stale == [], "retired-spelling exemptions no longer match a real citation; remove them:\n  " + "\n  ".join(
        stale
    )


def test_ledger_link_rejects_retired_evidence_id_grammar() -> None:
    """`aeat app ledger link --evidence-id` was retired: evidence assignment is
    reserved for `aeat app ledger attach`. The option must not resolve."""

    result = invoke_cached_cli(["app", "ledger", "link", "0" * 64, "--evidence-id", "x", "--help"])
    assert result.exit_code != 0, result.output


def test_config_reset_registers_exactly_start_status_resume() -> None:
    """`config reset` is a group mounting exactly start / status / resume.

    The retired flat scoped `config reset` action is gone: `config reset` is a
    command group whose only leaves are the crash-resumable lifecycle verbs.
    Any other leaf — or a flat action taking a positional scope — violates the
    ratified grammar."""

    for leaf in ("start", "status", "resume"):
        result = invoke_cached_cli(["config", "reset", leaf, "--help"])
        assert result.exit_code == 0, (leaf, result.output)

    for leaf in ("data", "auth", "profile", "all", "run", "execute"):
        result = invoke_cached_cli(["config", "reset", leaf, "--help"])
        assert result.exit_code != 0, (leaf, result.output)


def test_config_reset_rejects_the_retired_scope_flag() -> None:
    """The flat `config reset --scope ...` spelling is retired everywhere.

    DATA and AUTH reset scopes moved to their canonical doors (`repair
    quarantine`, `auth reset`); the single reset intent takes no `--scope`
    option on the group or on any lifecycle leaf."""

    for args in (
        ["config", "reset", "--scope", "profile", "--yes"],
        ["config", "reset", "--scope", "all", "--yes"],
        ["config", "reset", "start", "--scope", "profile", "--yes"],
        ["config", "reset", "resume", "--scope", "profile", "--yes"],
    ):
        result = invoke_cached_cli(args)
        assert result.exit_code != 0, (args, result.output)


def test_config_profile_sandbox_use_door_is_unmounted() -> None:
    """`config profile sandbox use` was removed with no alias.

    `config login` is the single accepted selector; a sandbox is entered by its
    canonical `sandbox:<name>` label through `config login`. The second
    selection door must not resolve."""

    result = invoke_cached_cli(["config", "profile", "sandbox", "use", "anything"])
    assert result.exit_code != 0, result.output
    help_result = invoke_cached_cli(["config", "profile", "sandbox", "use", "--help"])
    assert help_result.exit_code != 0, help_result.output


def test_config_profile_use_bare_name_selector_is_unmounted() -> None:
    """The retired bare-name `config profile use` selector does not resolve.

    Profile selection is `config login NAME` (UUID or exact label); no
    `config profile use` verb is mounted."""

    result = invoke_cached_cli(["config", "profile", "use", "anything"])
    assert result.exit_code != 0, result.output


_RETIRED_RESET_SANDBOX_SPELLINGS = (
    "config profile sandbox use",
    "config reset --scope",
    "reset --scope",
)


def test_retired_reset_and_sandbox_spellings_absent_from_source_and_docs() -> None:
    """The removed reset and sandbox spellings are gone from source, locales, docs.

    Scans the Python source tree, the four locale catalogues, the operator docs,
    and the CLI sequence contracts for the flat `config reset --scope` spelling
    and the removed `config profile sandbox use` door. A dead spelling in any of
    those surfaces would hand a downstream caller an instruction
    the live CLI refuses."""
    from ....tests import REPO_ROOT

    scanned: list[Path] = []
    src_root = REPO_ROOT / "src" / "cadrumo"
    scanned.extend(scan_directory(src_root, pattern="*.py", recursive=True))
    scanned.extend(scan_directory(src_root / "locales", pattern="*.yml"))
    docs_root = REPO_ROOT / "docs"
    scanned.extend(scan_directory(docs_root, pattern="*.md"))
    for sub in ("how-to", "explanation", "reference", "verification", "architecture"):
        subdir = docs_root / sub
        if subdir.is_dir():
            scanned.extend(scan_directory(subdir, pattern="*.md", recursive=True))
    sequences = docs_root / "_sequences"
    if sequences.is_dir():
        scanned.extend(scan_directory(sequences, pattern="*.seq", recursive=True))

    # Floor the scan corpus: a relocation of the source tree or docs would empty
    # this walk and pass identically to a clean tree, so the retired-spelling guard
    # below would be silently vacuous.
    assert len(scanned) > 500, (
        f"scanned only {len(scanned)} source/locale/doc files under {src_root} and {docs_root}; "
        "the scan corpus collapsed (a package relocation or rename), so an empty offender list "
        "would mean 'nothing was checked' rather than 'nothing is wrong'"
    )

    # Rejection-probe tests legitimately carry a retired spelling to prove the
    # CLI refuses it; they are the enforcement, not a citation.
    exempt = {
        Path(__file__).resolve(),
        (Path(__file__).parent / "test_config_profile_sandbox.py").resolve(),
    }
    offenders: list[str] = []
    for path in scanned:
        if path.resolve() in exempt:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for spelling in _RETIRED_RESET_SANDBOX_SPELLINGS:
            if spelling in text:
                offenders.append(f"{path}: {spelling}")
    assert offenders == []
