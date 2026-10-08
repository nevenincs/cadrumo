"""Classify exact temporal enrollment drift and source-pinned exclusions."""

from __future__ import annotations

from typing import Final

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from .temporal_enrollment_models import (
    LiteralEnrollmentDeclaration,
    LiteralEnrollmentFinding,
    RegistryRevisionSubject,
    TemporalEnrollmentExclusionPin,
)
from .temporal_enrollment_source import _subject_is_declared

__all__ = ["ENROLLMENT_EXCLUSION_PINS"]

# No live exclusion is needed.  This tuple is the single declaration home if a
# future law-selectable revision cannot participate in a bounded enrolment.
ENROLLMENT_EXCLUSION_PINS: Final[tuple[TemporalEnrollmentExclusionPin, ...]] = ()


def _declaration_finding(
    declaration: LiteralEnrollmentDeclaration,
    *,
    expected: frozenset[RegistryRevisionSubject] | None,
    authority: ValidatedRegistryAuthority,
    pins: tuple[TemporalEnrollmentExclusionPin, ...],
) -> LiteralEnrollmentFinding | None:
    declared, duplicates, absent = _declared_subject_drift(declaration, authority=authority)
    duplicate_pins, active_pins, dormant_pins = _declaration_pin_drift(
        declaration,
        pins=pins,
        authority=authority,
    )
    # Without a denominator there is nothing for a pin to exclude, so every
    # active pin on this declaration is reported rather than silently kept.
    outstanding = (expected - declared) if expected is not None else frozenset()
    unnecessary_pins = tuple(sorted(active_pins - outstanding))
    missing = tuple(sorted(expected - declared - active_pins)) if expected is not None else ()
    extra = tuple(sorted(declared - expected)) if expected is not None else ()
    if not _has_enrollment_drift(missing, extra, absent, duplicates, duplicate_pins, dormant_pins, unnecessary_pins):
        return None
    return LiteralEnrollmentFinding(
        path=declaration.path,
        symbol=declaration.symbol,
        missing=missing,
        extra=extra,
        duplicates=duplicates,
        duplicate_pins=duplicate_pins,
        dormant_pins=dormant_pins,
        unnecessary_pins=unnecessary_pins,
        absent=absent,
    )


def _declared_subject_drift(
    declaration: LiteralEnrollmentDeclaration,
    *,
    authority: ValidatedRegistryAuthority,
) -> tuple[set[RegistryRevisionSubject], tuple[RegistryRevisionSubject, ...], tuple[RegistryRevisionSubject, ...]]:
    declared = set(declaration.subjects)
    duplicates = tuple(sorted(subject for subject in declared if declaration.subjects.count(subject) > 1))
    absent = tuple(sorted(subject for subject in declared if not _subject_is_declared(subject, authority=authority)))
    return declared, duplicates, absent


def _declaration_pin_drift(
    declaration: LiteralEnrollmentDeclaration,
    *,
    pins: tuple[TemporalEnrollmentExclusionPin, ...],
    authority: ValidatedRegistryAuthority,
) -> tuple[
    tuple[RegistryRevisionSubject, ...],
    frozenset[RegistryRevisionSubject],
    tuple[RegistryRevisionSubject, ...],
]:
    matching_pins = _matching_declaration_pins(declaration, pins)
    duplicate_pins = _duplicate_exclusion_subjects(matching_pins)
    active_pins, dormant_pins = _active_and_dormant_pin_subjects(matching_pins, authority=authority)
    return duplicate_pins, active_pins, dormant_pins


def _matching_declaration_pins(
    declaration: LiteralEnrollmentDeclaration,
    pins: tuple[TemporalEnrollmentExclusionPin, ...],
) -> tuple[TemporalEnrollmentExclusionPin, ...]:
    return tuple(pin for pin in pins if pin.path == declaration.path and pin.symbol == declaration.symbol)


def _duplicate_exclusion_subjects(
    matching_pins: tuple[TemporalEnrollmentExclusionPin, ...],
) -> tuple[RegistryRevisionSubject, ...]:
    pinned_subjects = tuple(pin.subject for pin in matching_pins)
    return tuple(sorted(subject for subject in set(pinned_subjects) if pinned_subjects.count(subject) > 1))


def _active_and_dormant_pin_subjects(
    matching_pins: tuple[TemporalEnrollmentExclusionPin, ...],
    *,
    authority: ValidatedRegistryAuthority,
) -> tuple[frozenset[RegistryRevisionSubject], tuple[RegistryRevisionSubject, ...]]:
    active_pins = frozenset(pin.subject for pin in matching_pins if _pin_is_current(pin, authority=authority))
    dormant_pins = tuple(sorted(pin.subject for pin in matching_pins if pin.subject not in active_pins))
    return active_pins, dormant_pins


def _has_enrollment_drift(
    missing: tuple[RegistryRevisionSubject, ...],
    extra: tuple[RegistryRevisionSubject, ...],
    absent: tuple[RegistryRevisionSubject, ...],
    duplicates: tuple[RegistryRevisionSubject, ...],
    duplicate_pins: tuple[RegistryRevisionSubject, ...],
    dormant_pins: tuple[RegistryRevisionSubject, ...],
    unnecessary_pins: tuple[RegistryRevisionSubject, ...],
) -> bool:
    return bool(missing or extra or absent or duplicates or duplicate_pins or dormant_pins or unnecessary_pins)


def _pin_is_current(
    pin: TemporalEnrollmentExclusionPin,
    *,
    authority: ValidatedRegistryAuthority,
) -> bool:
    try:
        revision = authority.modelo(pin.modelo).revisions[pin.revision]
    except (KeyError, LookupError):
        return False
    source = authority.catalogues.sources.get(pin.source_ref)
    return pin.source_ref in revision.source_refs and source is not None and source.sha256 == pin.source_sha256
