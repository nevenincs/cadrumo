"""Every provision an IVA registry table cites is resolved against real law.

The tables under ``registry/aeat/iva/`` carry regulatory values -- rates, recargo
tiers, place-of-supply placements, territorial exclusions -- and each row names
the provision that establishes it. That citation is the only thing standing
between a value and a wrong filing, and until a table's loader resolves it the
citation is validated by nothing: an identifier naming a provision nobody defined
parses exactly like one naming a provision the BOE actually carries.

This module is the one place an IVA table's citations are turned into verified
grounding, and it does it by delegating to the registry's own evidence validator
rather than by re-implementing a check beside each table. That delegation is the
load-bearing part. :func:`~domain.calculations.registry.verify_legal_reference_grounding`
resolves the cited catalogue entry's ``corpus_ref`` to the ANCHORED unit of the
bundled consolidated text and checks the entry's ``required_text`` inside that
unit; a check written locally against a whole consolidated law would pass on any
phrase occurring anywhere in six hundred thousand characters, which is a
different and much weaker property wearing the same name.

WHY VERIFICATION HAPPENS AT LOAD RATHER THAN IN A TEST. A table whose grounding
is asserted only by a test ships its rows to every caller that imports it and
fails afterwards, in a lane nobody is looking at. Refusing at the loader means an
ungrounded regulatory value cannot be read at all, which is the same posture the
registry takes for binding validation: invariants are enforced when the data is
built, and resolve-time helpers are backstops rather than the gate.

WHY CITATIONS ARE COLLECTED BY THE CALLER. The tables do not agree on a field
name -- the rate and recargo tables write ``legal_refs`` while the
place-of-supply table writes ``legal_references`` alongside an
``establishing_reference`` -- so a sweep here that discovered citations by
searching for one field name would silently examine none of the other table and
pass. Each loader hands over the citations it has already parsed into its own
typed rows, so a table cannot be covered by accident and cannot be skipped by
one.

See Also:
    :func:`~domain.calculations.registry.verify_legal_reference_grounding`
        The registry's evidence validator, and the anchor-scoped resolution
        every citation here is checked through. The grounding-only variant: a
        rate table's citations are checked for real corpus backing, which is a
        different question from whether an operator has countersigned them for
        filing, and a table that loads is not thereby a table that may be filed.
    :class:`~domain.iva.IvaRateRecord`
        The rate row whose ``legal_refs`` were the first to be routed this way.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.hashing import content_hash_hex, sha256_file
from ...core.resources.bundled_data import bundled_path
from .errors import IvaCatalogueError

if TYPE_CHECKING:
    # Type-only: importing these at runtime would close the cycle the local
    # imports below exist to avoid. The registry's binding modules consume the
    # public IVA facade, and these loaders are part of that facade.
    from ..calculations.registry.schema_references import LegalReference, SourceReference


def registry_catalogues(
    *,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> tuple[Mapping[str, LegalReference], Mapping[str, SourceReference], Path]:
    """Return the legal and source catalogues, with the root they resolve against.

    A tree that cannot be loaded raises the registry loader's own error
    untouched. Wrapping it in an IVA error here would replace a diagnostic
    naming the offending file and line with one naming this module, which is
    the wrong end of the problem.

    Returns:
        The legal catalogue keyed by reference id, the source catalogue keyed by
        source id, and the bundled root every ``corpus_ref`` is relative to.
    """
    # Keep this import local: the registry's binding modules consume the public
    # IVA facade, and these loaders are part of that facade, so a module-level
    # import here would close an import cycle.
    from ..calculations.registry.loader import load_shared_catalogues

    resolved_source_root = bundled_path() if source_root is None else source_root.resolve()
    resolved_registry_root = (
        resolved_source_root / "registry" / "aeat" if registry_root is None else registry_root.resolve()
    )
    catalogues = load_shared_catalogues(resolved_registry_root)
    return catalogues.legal, catalogues.sources, resolved_source_root


def legal_evidence_fingerprints(
    reference_ids: Iterable[str],
    *,
    legal: Mapping[str, LegalReference],
    source_root: Path,
) -> tuple[tuple[str, ...], ...]:
    """Fingerprint cited legal records and the corpus bytes their checks read.

    A catalogue cache can safely reuse a green verification only while both the
    legal declaration and its cited document plus extracted-corpus sidecar are
    byte-identical.  Missing or escaping files are represented in the key so
    their later creation or correction cannot retain a prior cache result; the
    verifier remains responsible for producing the user-facing refusal.
    """
    fingerprints: list[tuple[str, ...]] = []
    for reference_id in sorted(set(reference_ids)):
        reference = legal.get(reference_id)
        if reference is None:
            fingerprints.append(("legal", reference_id, "unknown"))
            continue
        fingerprints.append(
            ("legal", reference_id, content_hash_hex(reference.model_dump(mode="json"))),
        )
        corpus_path = reference.corpus_ref.partition("#")[0]
        document = source_root / corpus_path
        fingerprints.extend(_evidence_file_fingerprint(document, source_root=source_root))
        fingerprints.extend(
            _evidence_file_fingerprint(
                document.with_name(document.name + ".extracted.json"),
                source_root=source_root,
            ),
        )
    return tuple(fingerprints)


def _evidence_file_fingerprint(path: Path, *, source_root: Path) -> tuple[tuple[str, ...], ...]:
    """Describe one cited corpus file without pre-empting verifier diagnostics."""
    try:
        resolved_root = source_root.resolve()
        resolved = path.resolve()
    except OSError as exc:
        return (("evidence", str(path), "unresolvable", str(exc)),)
    if resolved_root not in resolved.parents and resolved != resolved_root:
        return (("evidence", str(path), "escapes_source_root"),)
    try:
        stat = resolved.stat()
        digest = sha256_file(resolved)
    except OSError as exc:
        return (("evidence", str(resolved), "unavailable", str(exc)),)
    return (("evidence", str(resolved), str(stat.st_size), str(stat.st_mtime_ns), digest),)


def legal_ref_failures(
    row: str,
    reference_ids: Iterable[str],
    legal: Mapping[str, LegalReference],
    source_root: Path,
    verified: set[str],
) -> list[str]:
    """Resolve and verify one row's legal refs, memoising the ids that pass.

    Accumulating rather than raising, so one load reports every ungrounded row
    it found instead of the first. A caller that raises on the first failure
    turns a table with four broken citations into four successive debugging
    rounds.

    Args:
        row: A label identifying the row, quoted verbatim into each failure.
        reference_ids: The provision identifiers the row cites.
        legal: The legal catalogue the identifiers must resolve in.
        source_root: The root every ``corpus_ref`` resolves against.
        verified: Ids already verified in this load, extended in place. Shared
            across rows because verification reads and normalises corpus text,
            which is the expensive half of a load.

    Returns:
        One message per failure, empty when every citation verified.
    """
    # Keep this import local: see :func:`registry_catalogues`.
    from ..calculations.registry.errors import RegistryValidationError
    from ..calculations.registry.legal import verify_legal_reference_grounding

    failures: list[str] = []
    for ref_id in reference_ids:
        if ref_id in verified:
            continue
        reference = legal.get(ref_id)
        if reference is None:
            failures.append(f"{row}: unknown legal_ref {ref_id!r}")
            continue
        try:
            verify_legal_reference_grounding(reference, source_root=source_root)
        except RegistryValidationError as exc:
            failures.append(f"{row}: invalid legal_ref {ref_id!r}: {exc}")
            continue
        verified.add(ref_id)
    return failures


def verify_table_legal_refs(table: str, citations: Sequence[tuple[str, Sequence[str]]]) -> None:
    """Verify every citation a registry table's rows carry, or refuse the table.

    Args:
        table: The table's name, used to head the refusal.
        citations: One ``(row_label, reference_ids)`` pair per row, in the order
            the rows were parsed.

    Raises:
        IvaCatalogueError: When any cited provision is absent from the legal
            catalogue, or is present but does not resolve to bundled legal text
            carrying its declared ``required_text`` at its declared anchor. The
            message enumerates every failure rather than the first.
    """
    legal, _sources, source_root = registry_catalogues()
    verified: set[str] = set()
    failures: list[str] = []
    for row, reference_ids in citations:
        failures.extend(legal_ref_failures(row, reference_ids, legal, source_root, verified))
    if failures:
        raise IvaCatalogueError(
            f"{table}: legal grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )
