"""Root-grammar invariants for the CLI surface.

The CLI exposes exactly two roots (`config` and `app`) with a fixed
noun-group ordering. These tests assert that the rejected verbs and
surfaces are not mounted, so the CLI grammar stays the intentional
one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


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

    ``config rekey`` became ``config passphrase change``; ``config
    show-recovery`` / ``config verify-recovery`` became the ``config recovery``
    subgroup (``status`` / ``create`` / ``rotate`` / ``verify``). None of the
    old spellings may resolve."""

    for verb in ("rekey", "show-recovery", "verify-recovery"):
        result = invoke_cached_cli(["config", verb, "--help"])
        assert result.exit_code != 0, (verb, result.output)


def test_recovery_verbs_reject_mnemonic_argv_options() -> None:
    """No recovery verb accepts the mnemonic (or any secret) as an argv value.

    The retired ``--recovery-key`` channel put the 24 words in the process
    table and shell history; secrets now arrive only via no-echo prompts or
    ``--secrets-stdin``."""

    for args in (
        ["config", "recover", "--recovery-key", "a b c"],
        ["config", "recovery", "verify", "--recovery-key", "a b c"],
        ["config", "recover", "--new-passphrase", "x"],
        ["config", "recover", "--confirm-new-passphrase", "x"],
    ):
        result = invoke_cached_cli(args)
        assert result.exit_code != 0, (args, result.output)


def test_recovery_grammar_registers_exactly_the_accepted_leaves() -> None:
    """`config recovery` mounts status/create/rotate/verify and nothing else."""

    for leaf in ("status", "create", "rotate", "verify"):
        result = invoke_cached_cli(["config", "recovery", leaf, "--help"])
        assert result.exit_code == 0, (leaf, result.output)

    for leaf in ("show", "mint", "print", "export"):
        result = invoke_cached_cli(["config", "recovery", leaf, "--help"])
        assert result.exit_code != 0, (leaf, result.output)


_RETIRED_CUSTODY_SPELLINGS = (
    "config rekey",
    "config show-recovery",
    "config verify-recovery",
    "--recovery-key",
)


def test_retired_custody_spellings_absent_from_source_and_docs() -> None:
    """The removed spellings are gone from production source, locales, and docs.

    Scans the Python source tree, the four locale catalogues, the operator
    docs, and the CLI sequence contracts. A retired spelling in any of those
    surfaces would hand an operator (or the agent harness) a dead instruction.
    """
    from ....core.paths import PROJECT_ROOT

    scanned: list[Path] = []
    src_root = PROJECT_ROOT / "src" / "cadrumo"
    scanned.extend(src_root.rglob("*.py"))
    scanned.extend((src_root / "locales").glob("*.yml"))
    docs_root = PROJECT_ROOT / "docs"
    scanned.extend(docs_root.glob("*.md"))
    for sub in ("how-to", "explanation", "reference", "verification", "architecture"):
        subdir = docs_root / sub
        if subdir.is_dir():
            scanned.extend(subdir.rglob("*.md"))
    sequences = docs_root / "_sequences"
    if sequences.is_dir():
        scanned.extend(sequences.rglob("*.seq"))

    # Rejection-probe tests legitimately carry a retired spelling to prove the
    # CLI refuses it; they are the enforcement, not a citation.
    exempt = {
        Path(__file__).resolve(),
        (Path(__file__).parent / "test_config_recovery_lifecycle.py").resolve(),
    }
    offenders: list[str] = []
    for path in scanned:
        if path.resolve() in exempt:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for spelling in _RETIRED_CUSTODY_SPELLINGS:
            if spelling in text:
                offenders.append(f"{path}: {spelling}")
    assert offenders == []


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
    those surfaces would hand an operator (or the agent harness) an instruction
    the live CLI refuses."""
    from ....core.paths import PROJECT_ROOT

    scanned: list[Path] = []
    src_root = PROJECT_ROOT / "src" / "cadrumo"
    scanned.extend(src_root.rglob("*.py"))
    scanned.extend((src_root / "locales").glob("*.yml"))
    docs_root = PROJECT_ROOT / "docs"
    scanned.extend(docs_root.glob("*.md"))
    for sub in ("how-to", "explanation", "reference", "verification", "architecture"):
        subdir = docs_root / sub
        if subdir.is_dir():
            scanned.extend(subdir.rglob("*.md"))
    sequences = docs_root / "_sequences"
    if sequences.is_dir():
        scanned.extend(sequences.rglob("*.seq"))

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
