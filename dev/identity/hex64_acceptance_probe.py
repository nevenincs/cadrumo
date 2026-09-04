"""Behavioural probe for the hex-64 census: does a field actually accept non-hex?

WHY A SECOND INSTRUMENT. ``dev/identity/hex64_redeclaration_census.py`` reads
DECLARATIONS. It can prove a field declares a length and no pattern; it cannot
prove what that field accepts at runtime, because a hand-written
``field_validator`` elsewhere in the class may enforce the shape the annotation
omits -- exactly what ``RawProvenance.source_sha256`` does. The census is
therefore an upper bound on the defect, and this closes the gap.

THE PROBLEM THIS SOLVES, and it is a harness problem rather than a matcher one.
The obvious probe constructs the real model and passes a bad digest. That fails
for an unrelated reason on most models here: they have other required fields, so
the constructor raises ``Field required`` before the constraint under test is
ever evaluated -- and a probe counting exceptions reads that as "refused". A
sweep built that way reported 31 fields as refusing when it had tested none of
them.

THE FIX IS TO STOP CONSTRUCTING THE MODEL. A field's constraint lives in its
annotation and its ``FieldInfo`` metadata, so the effective type can be rebuilt
as ``Annotated[annotation, *metadata]`` and validated ALONE, in a one-field
holder. No other field exists, so no other field can refuse. This reuses
:func:`cadrumo.tests.fixtures.identity_holder.single_field_holder`, the helper
the canonical hex-64 suite already validates aliases through.

THE VACUITY GATE IS RETAINED ANYWAY. Rebuilding a type can itself fail -- a
forward reference that will not resolve, a metadata entry that does not
reconstruct. So every probe validates a REAL SHA-256 digest first and reports
``VACUOUS`` if that is refused. A refusal probe that has never once seen an
acceptance is measuring its own harness.

Usage::

    python -m dev.identity.hex64_acceptance_probe HEAD
    python -m dev.identity.hex64_acceptance_probe HEAD --json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Annotated, Final

from .hex64_redeclaration_census import DeclarationKind, census

#: A real digest. The probe must accept this or it has not reached the constraint.
VALID_DIGEST: Final[str] = hashlib.sha256(b"probe").hexdigest()

#: Values a hex-64 constraint must refuse. Both are exactly 64 characters, so a
#: length-only constraint admits them and only a pattern rejects them.
INVALID_VALUES: Final[tuple[str, ...]] = ("Z" * 64, "!" * 64)


def admitted_shape(value: str) -> str:
    """Name what an admitted value actually is, for the report line.

    The label was derived from a leading ``Z`` and read ``upper-hex``. Neither
    probe value is hexadecimal at all - they are sixty-four ``Z`` characters
    and sixty-four exclamation marks - so that line told a reviewer the field
    had accepted an UPPERCASE DIGEST, which is near enough to correct that it
    invites triage as case-insensitivity. What the field actually accepted was
    sixty-four arbitrary letters standing in for a SHA-256.
    """
    if all(character in "0123456789abcdefABCDEF" for character in value):
        return "hex"
    if value.isalpha():
        return "non-hex-letters"
    if not any(character.isalnum() for character in value):
        return "punctuation"
    return "mixed"


class Verdict(StrEnum):
    """What the probe established about one field.

    Attributes:
        ACCEPTS_NON_HEX: The field admitted a 64-character non-hex value. A
            malformed digest reaches whatever this field persists.
        REFUSES: The field refused every invalid value, so something enforces
            the shape even though the annotation does not.
        VACUOUS: The field refused the VALID digest, so the probe never reached
            the constraint and this field is UNMEASURED -- never "passing".
        UNREACHED: The module, model or field could not be resolved.
    """

    ACCEPTS_NON_HEX = "accepts_non_hex"
    REFUSES = "refuses"
    VACUOUS = "vacuous"
    UNREACHED = "unreached"


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """One field's behavioural verdict.

    Attributes:
        path: Repository-relative module path.
        model: Enclosing model name.
        field: Field name.
        verdict: What was established.
        accepted: The invalid values the field admitted.
        detail: Why the probe could not measure, when it could not.
    """

    path: str
    model: str
    field: str
    verdict: Verdict
    accepted: tuple[str, ...]
    detail: str

    def rendered(self) -> str:
        """A single deterministic line for a report."""
        marks = ",".join(admitted_shape(value) for value in self.accepted)
        suffix = f" [{marks}]" if marks else (f" ({self.detail})" if self.detail else "")
        return f"{self.verdict.value.upper():<16} {self.path} {self.model}.{self.field}{suffix}"


def module_name_for(path: str) -> str:
    """Return the importable module name for a repository-relative source path."""
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def _effective_type(model: type, field: str) -> object:
    """Rebuild one field's constraint as a standalone annotated type.

    The constraint is split between the annotation and the ``FieldInfo``
    metadata, so neither alone reproduces it. Recombining them is what lets the
    field be validated without its model -- and therefore without its model's
    other required fields.
    """
    info = model.model_fields[field]
    if not info.metadata:
        return info.annotation
    return Annotated[tuple([info.annotation, *info.metadata])]


def _admits(holder: object, value: str) -> bool:
    """Whether ``holder`` validates ``value`` rather than refusing it.

    A refusal here IS the measurement, which is why the exception is swallowed
    rather than reported: by this point the vacuity gate has already proven the
    harness reaches the constraint, so the only thing a raise can mean is that
    the constraint rejected the value.
    """
    try:
        holder.build(value)  # type: ignore[attr-defined]
    except Exception:
        return False
    return True


def probe(path: str, model_name: str, field: str) -> ProbeResult:
    """Establish what one declared field actually accepts."""
    from cadrumo.tests.fixtures.identity_holder import single_field_holder

    def result(verdict: Verdict, accepted: tuple[str, ...] = (), detail: str = "") -> ProbeResult:
        return ProbeResult(path, model_name, field, verdict, accepted, detail)

    try:
        module = importlib.import_module(module_name_for(path))
        model = getattr(module, model_name)
        holder = single_field_holder(field, _effective_type(model, field))
    except Exception as exc:
        return result(Verdict.UNREACHED, detail=f"{type(exc).__name__}: {exc}"[:160])

    # The vacuity gate. Establish the harness reaches the constraint BEFORE
    # reading anything into a refusal.
    try:
        holder.build(VALID_DIGEST)
    except Exception as exc:
        return result(Verdict.VACUOUS, detail=f"{type(exc).__name__}: {exc}"[:160])

    accepted = tuple(value for value in INVALID_VALUES if _admits(holder, value))
    return result(Verdict.ACCEPTS_NON_HEX if accepted else Verdict.REFUSES, accepted)


def sweep(revision: str) -> tuple[ProbeResult, ...]:
    """Probe every ``unpatterned_length`` site the census finds at ``revision``."""
    sites = [
        item
        for item in census(revision)
        if item.kind is DeclarationKind.UNPATTERNED_LENGTH and item.symbol and item.field
    ]
    return tuple(probe(item.path, item.symbol, item.field) for item in sites)


def main(argv: list[str] | None = None) -> int:
    """Print the behavioural sweep for one pinned revision."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="Pinned git revision to scan, e.g. HEAD or a sha")
    parser.add_argument("--json", action="store_true", help="Emit results and summary as JSON")
    args = parser.parse_args(argv)

    results = sweep(args.revision)
    summary = {verdict.value: sum(1 for r in results if r.verdict is verdict) for verdict in Verdict}
    summary["probed"] = len(results)

    if args.json:
        # The reading note travels IN the payload rather than only in this
        # module's docstring. A consumer of --json never sees the text footer,
        # and "vacuous: 31" beside "refuses: 0" is exactly the shape someone
        # totals into an all-clear -- which is the misreading that already
        # nearly cost a confirmed defect.
        document = {
            "summary": summary,
            "reading_note": (
                "VACUOUS means UNMEASURED, never passing: the probe never reached the "
                "constraint, so the field's behaviour is unknown. Do not add it to a "
                "protected or passing count. REFUSES means only that the ANNOTATION "
                "enforced the shape; a field protected by a class-level field_validator "
                "reads as ACCEPTS_NON_HEX here, because a one-field holder carries no "
                "class validators."
            ),
            "records": [asdict(r) for r in results],
        }
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0

    for item in sorted(results, key=lambda r: (r.verdict.value, r.path, r.field)):
        print(item.rendered())
    print()
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("\nVACUOUS means UNMEASURED, never passing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
