"""Narrow exceptions for the bucket-event-history domain."""

from __future__ import annotations


class BucketsError(Exception):
    """Base error for the bucket-event-history domain."""


class BucketEventValidationError(BucketsError, ValueError):
    """Raised when a bucket event fails validation."""
