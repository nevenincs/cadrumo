"""Independent contracts for streamed packaging artifact hashing."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path
from typing import Final

import pytest

from dev.packaging._hashing import sha256_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


#: Smoke entrypoints re-homed onto the canonical helper. Each is invoked as
#: ``python -m dev.packaging.<module>``, so it can import the package helper.
_REHOMED_SMOKE_MODULES: Final[tuple[str, ...]] = ("smoke_mcpb", "smoke_plugin_install")

#: Sites that still carry their own streamed SHA-256 rather than importing
#: :func:`sha256_path`, each mapped to the condition that would have to be
#: discharged before it could be unified. The divergence is DELIBERATE, not
#: an oversight, and this mapping is what keeps it from becoming permanent by
#: default: a reader who satisfies a discharge condition can retire that entry
#: and re-home the site, and a reader who cannot is told exactly why.
_UNUNIFIED_DIGEST_SITES: Final[dict[str, str]] = {
    # CI runs this as a bare script path under `uv run --no-project`
    # (.github/workflows/packaging-homebrew.yml), so the repository root is not
    # on sys.path and `from dev.packaging...` raises ImportError at launch.
    # DISCHARGE: prove a sys.path bootstrap (the `_REPO_ROOT` prologue the
    # module-invoked smokes use) is acceptable in the --no-project lane, or move
    # that workflow to `python -m dev.packaging.smoke_homebrew`.
    "dev/packaging/smoke_homebrew.py": "bare-script CI invocation; needs a sys.path bootstrap decision",
    # Same standalone shape: a stdlib+httpx tool with no dev-package imports.
    # DISCHARGE: same bootstrap decision as smoke_homebrew, applied here.
    "dev/corpus/sync_aeat_record_design_corpus.py": "standalone corpus tool; same bootstrap decision",
    # `sha256_file` is PUBLIC (exported in cohort_manifest.__all__) with external
    # consumers in evidence.py, distribution_evidence_emit.py, release_cohort.py
    # and dev/release tests.
    # DISCHARGE: those consumers are no longer under concurrent edit, so the
    # rename can land atomically across every call site in one commit.
    "dev/packaging/cohort_manifest.py": "public symbol; consumers under concurrent edit",
}


def test_sha256_path_hashes_real_multichunk_bytes(tmp_path: Path) -> None:
    """A file crossing the stream boundary has the standard-library digest."""
    payload = b"cohort-byte-contract\n" * 60_000
    artifact = tmp_path / "cohort-artifact.bin"
    artifact.write_bytes(payload)

    assert sha256_path(artifact) == hashlib.sha256(payload).hexdigest()


def _streams_sha256(function: ast.FunctionDef) -> bool:
    """Report whether ``function`` builds its own ``hashlib.sha256`` accumulator.

    Matched on the call rather than the attribute name so that reading a
    ``.sha256`` field off a manifest record is not mistaken for computing one.
    """
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sha256"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "hashlib"
        for node in ast.walk(function)
    )


@pytest.mark.parametrize("module_name", _REHOMED_SMOKE_MODULES)
def test_rehomed_smoke_module_declares_no_private_digest_helper(module_name: str) -> None:
    """A re-homed smoke entrypoint must not grow its own streamed digest back.

    Each of these modules previously carried a byte-identical private copy of
    ``sha256_path``. Asserting only that the canonical import is present would
    still pass if a second local helper reappeared beside it, so the check is on
    the absence of any function that streams ``hashlib.sha256`` itself.
    """
    source = (Path(__file__).resolve().parents[1] / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    redeclared = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and _streams_sha256(node)]

    assert redeclared == []


@pytest.mark.parametrize("relative_path", sorted(_UNUNIFIED_DIGEST_SITES))
def test_recorded_exemption_still_describes_a_real_duplicate(relative_path: str) -> None:
    """Every recorded exemption must still name a site that actually diverges.

    This is what stops the exemption list becoming permanent by default. When
    someone discharges a condition and re-homes one of these sites, this test
    fails and forces the stale entry out of the mapping.

    It is also the counting proof for the sibling refusal test: the same AST
    predicate that reports zero for a re-homed module reports a hit on each of
    these, so a zero there is a measured absence rather than a detector that
    never fires.
    """
    repository_root = Path(__file__).resolve().parents[3]
    tree = ast.parse((repository_root / relative_path).read_text(encoding="utf-8"))

    streaming_helpers = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and _streams_sha256(node)
    ]

    assert streaming_helpers, (
        f"{relative_path} no longer declares its own streamed digest; "
        f"discharge condition was {_UNUNIFIED_DIGEST_SITES[relative_path]!r} -- "
        "re-home it and remove this exemption entry"
    )


@pytest.mark.parametrize("module_name", _REHOMED_SMOKE_MODULES)
def test_rehomed_smoke_module_uses_the_canonical_helper(module_name: str) -> None:
    """The re-homed module resolves file digests through the one owner."""
    module = importlib.import_module(f"dev.packaging.{module_name}")

    assert module.sha256_path is sha256_path
