"""Compatibility imports for shared registry predecessor-date validation."""

from .revision_contracts import RevisionWindow, validate_predecessor_date_agreement

EditionWindow = RevisionWindow

__all__ = ("EditionWindow", "RevisionWindow", "validate_predecessor_date_agreement")
