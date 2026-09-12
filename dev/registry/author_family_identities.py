"""Author the edition-free identity of projection endpoints and verification predicates.

A declaration family inherits across editions only when its members carry a
stable identity that names the same member in every edition. Two families
carried none: ``projection_endpoints`` identified its members by nothing at all,
and ``verification_predicates`` carried a narrative ``predicate_id`` scoped to
the edition that declared it. Both are given an ``id`` here, derived from the
member's own semantic fields.

The derivations are deliberately total and mechanical -- a member's identity is
a function of what the member already says, never of where it sits in a file,
which offset it renders at, or which year declares it:

``projection_endpoints``
    The endpoint's own typed reference: the projection kind, then every semantic
    axis of that reference. ``casilla_id`` is excluded, because the numbered box
    a projection resolves to is the edition's address for the endpoint and
    renumbers between editions, while the endpoint itself does not.

``verification_predicates``
    The predicate's kind (its expression operator) and its subject (the authored
    ``predicate_id`` with the declaring edition's scope removed). A year inside
    the subject that is part of the invariant -- a statutory cutoff such as
    ``anterior-2013`` -- is not an edition token and is kept.

Collisions are refused, never renamed: two members of one revision deriving the
same identity means the corpus does not distinguish them, and a generated
suffix would invent a distinction nobody authored.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PROJECTION_ENDPOINTS: Final = "projection_endpoints"
VERIFICATION_PREDICATES: Final = "verification_predicates"

#: The axis of a projection reference that is an edition-scoped address rather
#: than part of the endpoint's identity.
_ADDRESS_AXES: Final = frozenset({"casilla_id"})

#: Segments a predicate subject sheds: the modelo it belongs to, the editions it
#: was authored for, and the Spanish "and following" span wording.
_EDITION_SCOPE_SEGMENTS: Final = frozenset({"y", "siguientes"})
_MODELO_PREFIX: Final = re.compile(r"^(?:modelo-\d{3}|m\d{3})-")
_YEAR_SEGMENT: Final = re.compile(r"^\d{4}$")
_EXPRESSION_OPERATOR: Final = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IDENTITY_GRAMMAR: Final = re.compile(r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$")


class IdentityDerivationError(Exception):
    """A member carries no derivable identity, or two members derive the same one."""


def _kebab(value: object) -> str:
    """Render one authored token in the registry identifier grammar."""
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def derive_projection_endpoint_id(member: Mapping[str, object]) -> str:
    """Return the edition-free identity of one projection endpoint declaration.

    Args:
        member: The declaration as authored, carrying its ``projection_ref``.

    Returns:
        ``<projection-kind>:<axis>-<value>[.<axis>-<value>...]``, the axes in a
        fixed alphabetical order so the identity does not depend on the order
        the author wrote the reference's keys in.

    Raises:
        IdentityDerivationError: The declaration carries no typed reference, or
            the reference names no projection kind.
    """
    reference = member.get("projection_ref")
    if not isinstance(reference, Mapping):
        raise IdentityDerivationError("projection endpoint declares no projection_ref table")
    kind = reference.get("projection_kind")
    if not isinstance(kind, str) or not kind:
        raise IdentityDerivationError("projection_ref declares no projection_kind")
    axes = [
        f"{_kebab(name)}-{_kebab(value)}"
        for name, value in sorted(reference.items())
        if name != "projection_kind" and name not in _ADDRESS_AXES and value is not None
    ]
    identity = _kebab(kind) if not axes else f"{_kebab(kind)}:{'.'.join(axes)}"
    return _validated(identity)


def derive_verification_predicate_id(member: Mapping[str, object]) -> str:
    """Return the edition-free identity of one verification predicate.

    Args:
        member: The predicate as authored, carrying ``predicate_id`` and
            ``expression``.

    Returns:
        ``<operator>:<subject>`` -- the predicate's kind and the subject its
        authored identifier names once the declaring edition's scope is removed.

    Raises:
        IdentityDerivationError: The predicate names no expression operator, or
            its identifier is edition scope and nothing else.
    """
    expression = member.get("expression")
    if not isinstance(expression, str):
        raise IdentityDerivationError("verification predicate declares no expression")
    operator = _EXPRESSION_OPERATOR.match(expression)
    if operator is None:
        raise IdentityDerivationError(f"expression names no predicate operator: {expression!r}")
    predicate_id = member.get("predicate_id")
    if not isinstance(predicate_id, str) or not predicate_id:
        raise IdentityDerivationError("verification predicate declares no predicate_id")
    subject = _predicate_subject(predicate_id)
    return _validated(f"{_kebab(operator.group(1))}:{subject}")


def _predicate_subject(predicate_id: str) -> str:
    """Strip the declaring edition's scope from an authored predicate identifier."""
    remainder = _MODELO_PREFIX.sub("", predicate_id.strip().lower())
    segments = remainder.split("-")
    while segments and (_YEAR_SEGMENT.match(segments[0]) or segments[0] in _EDITION_SCOPE_SEGMENTS):
        segments = segments[1:]
    subject = "-".join(segment for segment in segments if segment)
    if not subject:
        raise IdentityDerivationError(f"predicate_id {predicate_id!r} is edition scope and nothing else")
    return subject


def _validated(identity: str) -> str:
    """Refuse a derived identity the registry identifier grammar would not admit."""
    if not _IDENTITY_GRAMMAR.match(identity) or len(identity) > 160:
        raise IdentityDerivationError(f"derived identity is outside the identifier grammar: {identity!r}")
    return identity


#: Every family this pass authors, with the derivation that owns its identity.
DERIVATIONS: Final[Mapping[str, Callable[[Mapping[str, object]], str]]] = {
    PROJECTION_ENDPOINTS: derive_projection_endpoint_id,
    VERIFICATION_PREDICATES: derive_verification_predicate_id,
}


@dataclass(frozen=True, slots=True)
class MemberIdentity:
    """One member's derived identity and the exact line its ``id`` belongs above."""

    path: Path
    family: str
    modelo: str
    revision: str
    index: int
    identity: str
    header_line: int
    already_declared: bool


@dataclass(frozen=True, slots=True)
class Collision:
    """Two or more members of one revision deriving the same identity."""

    family: str
    modelo: str
    revision: str
    identity: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuthoringOutcome:
    """What one run derived, what it refused, and what it wrote."""

    identities: tuple[MemberIdentity, ...]
    collisions: tuple[Collision, ...]
    written: tuple[Path, ...]

    @property
    def pending(self) -> tuple[MemberIdentity, ...]:
        """Members that still carry no ``id``."""
        return tuple(identity for identity in self.identities if not identity.already_declared)


def _header(family: str, revision: str) -> str:
    return f'[[revisions."{revision}".{family}]]'


def read_members(path: Path, family: str) -> tuple[tuple[str, int, Mapping[str, object]], ...]:
    """Return ``(revision, index, member)`` for every member of ``family`` in ``path``."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    members: list[tuple[str, int, Mapping[str, object]]] = []
    for revision, table in document.get("revisions", {}).items():
        if not isinstance(table, Mapping):
            continue
        for index, member in enumerate(table.get(family, ())):
            if isinstance(member, Mapping):
                members.append((str(revision), index, member))
    return tuple(members)


def _header_lines(text: str, family: str) -> Mapping[str, tuple[int, ...]]:
    """Return, per revision, the line index of each member header of ``family``.

    The n-th header of a revision opens the n-th member of that revision's
    array, which is the pairing between the parsed members and the authored
    text that lets an ``id`` line be inserted without reserialising the file
    and discarding its authored comments.
    """
    lines = text.splitlines()
    found: dict[str, list[int]] = defaultdict(list)
    pattern = re.compile(
        rf'^\[\[\s*revisions\s*\.\s*(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*\.\s*{re.escape(family)}\s*\]\]\s*$'
    )
    for number, line in enumerate(lines):
        match = pattern.match(line)
        if match is not None:
            found[match.group(1) if match.group(1) is not None else match.group(2)].append(number)
    return {revision: tuple(numbers) for revision, numbers in found.items()}


def plan_file(path: Path, family: str, modelo: str) -> tuple[MemberIdentity, ...]:
    """Derive the identity of every member of ``family`` declared in ``path``."""
    text = path.read_text(encoding="utf-8")
    headers = _header_lines(text, family)
    derive = DERIVATIONS[family]
    planned: list[MemberIdentity] = []
    for revision, index, member in read_members(path, family):
        positions = headers.get(revision, ())
        if index >= len(positions):
            raise IdentityDerivationError(
                f"{path}: revision {revision!r} declares {index + 1} {family} members "
                f"but the file carries {len(positions)} member headers",
            )
        try:
            identity = derive(member)
        except IdentityDerivationError as error:
            raise IdentityDerivationError(f"{path}: {family}[{index}] in revision {revision!r}: {error}") from error
        planned.append(
            MemberIdentity(
                path=path,
                family=family,
                modelo=modelo,
                revision=revision,
                index=index,
                identity=identity,
                header_line=positions[index],
                already_declared=isinstance(member.get("id"), str),
            ),
        )
    return tuple(planned)


def find_collisions(identities: Iterable[MemberIdentity]) -> tuple[Collision, ...]:
    """Return every identity two members of one revision both derive."""
    grouped: dict[tuple[str, str, str, str], list[MemberIdentity]] = defaultdict(list)
    for identity in identities:
        grouped[(identity.family, identity.modelo, identity.revision, identity.identity)].append(identity)
    collisions = [
        Collision(
            family=family,
            modelo=modelo,
            revision=revision,
            identity=value,
            members=tuple(f"{member.path.name}[{member.index}]" for member in sorted(members, key=_member_order)),
        )
        for (family, modelo, revision, value), members in grouped.items()
        if len(members) > 1
    ]
    return tuple(sorted(collisions, key=lambda collision: (collision.modelo, collision.revision, collision.identity)))


def _member_order(member: MemberIdentity) -> tuple[str, int]:
    return (member.path.name, member.index)


def apply_identities(identities: Sequence[MemberIdentity]) -> tuple[Path, ...]:
    """Write the ``id`` line of every pending member into its authored TOML in place."""
    by_path: dict[Path, list[MemberIdentity]] = defaultdict(list)
    for identity in identities:
        if not identity.already_declared:
            by_path[identity.path].append(identity)
    written: list[Path] = []
    for path, members in sorted(by_path.items()):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        for member in sorted(members, key=lambda entry: entry.header_line, reverse=True):
            lines.insert(member.header_line + 1, f'id = "{member.identity}"\n')
        path.write_text("".join(lines), encoding="utf-8", newline="")
        written.append(path)
    return tuple(written)


def modelo_directories(registry_root: Path, modelos: Sequence[str]) -> tuple[tuple[str, Path], ...]:
    """Return ``(modelo, directory)`` for the requested modelos, or all of them."""
    root = registry_root / "modelos"
    selected = sorted(
        (directory.name, directory)
        for directory in root.iterdir()
        if directory.is_dir() and (not modelos or directory.name in set(modelos))
    )
    return tuple(selected)


def author_identities(
    *,
    registry_root: Path,
    families: Sequence[str],
    modelos: Sequence[str],
    apply: bool,
) -> AuthoringOutcome:
    """Derive, refuse, and optionally write the identities of the selected families."""
    identities: list[MemberIdentity] = []
    for modelo, directory in modelo_directories(registry_root, modelos):
        for family in families:
            for path in sorted(directory.glob(f"revisions/*/{family}/*.toml")):
                identities.extend(plan_file(path, family, modelo))
    collisions = find_collisions(identities)
    written: tuple[Path, ...] = ()
    if apply and not collisions:
        written = apply_identities(identities)
    return AuthoringOutcome(identities=tuple(identities), collisions=collisions, written=written)


def render_outcome(outcome: AuthoringOutcome, *, applied: bool) -> str:
    """Render one run as the per-modelo report the operator reads."""
    lines: list[str] = []
    per_family: dict[tuple[str, str], list[MemberIdentity]] = defaultdict(list)
    for identity in outcome.identities:
        per_family[(identity.family, identity.modelo)].append(identity)
    lines.append("family/modelo    members  pending")
    for (family, modelo), members in sorted(per_family.items()):
        pending = sum(1 for member in members if not member.already_declared)
        lines.append(f"{family}/{modelo}  {len(members)}  {pending}")
    lines.append(f"totals members={len(outcome.identities)} pending={len(outcome.pending)}")
    if outcome.collisions:
        lines.append(f"collisions={len(outcome.collisions)}")
        for collision in outcome.collisions:
            members = ", ".join(collision.members)
            lines.append(
                f"  collision {collision.family} modelo {collision.modelo} revision "
                f"{collision.revision}: {collision.identity} <- {members}",
            )
    else:
        lines.append("collisions=0")
    lines.append(f"written={len(outcome.written)} applied={applied}")
    for path in outcome.written:
        lines.append(f"  wrote {path}")
    return "\n".join(lines) + "\n"


def _bundled_registry_root() -> Path:
    from cadrumo.core.resources.bundled_data import bundled_path

    return Path(bundled_path("registry", "aeat")).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    """Derive and author family identities; exit 1 on a refused collision."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--family",
        action="append",
        choices=sorted(DERIVATIONS),
        default=None,
        help="family to author; repeatable, defaults to every family",
    )
    parser.add_argument("--modelo", action="append", default=None, help="modelo id to author; repeatable")
    parser.add_argument("--all", action="store_true", help="author every modelo in the tree")
    parser.add_argument("--dry-run", action="store_true", help="derive and report without writing")
    parser.add_argument("--report", type=Path, default=None, help="write the rendered report to this path")
    parser.add_argument("--registry-root", type=Path, default=None, help="registry root holding modelos/")
    arguments = parser.parse_args(argv)

    modelos: list[str] = list(arguments.modelo or ())
    if not modelos and not arguments.all:
        sys.stderr.write("refused: name --modelo at least once, or pass --all\n")
        return 2
    registry_root = arguments.registry_root or _bundled_registry_root()
    try:
        outcome = author_identities(
            registry_root=registry_root,
            families=list(arguments.family or sorted(DERIVATIONS)),
            modelos=modelos,
            apply=not arguments.dry_run,
        )
    except IdentityDerivationError as error:
        sys.stderr.write(f"refused: {error}\n")
        return 1
    rendered = render_outcome(outcome, applied=not arguments.dry_run)
    sys.stdout.write(rendered)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(rendered, encoding="utf-8", newline="\n")
    return 1 if outcome.collisions else 0


if __name__ == "__main__":
    raise SystemExit(main())
