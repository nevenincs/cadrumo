"""A Plan General de Contabilidad account code, and the hierarchy it implies.

The PGC numbers accounts by nesting: the first digit is the *grupo* (1-9), the
first two are the *subgrupo*, and further digits narrow to an account and then
to a subcuenta the filer may define. The shapes accepted here are the shapes
observed in the AEAT Manual práctico's Equivalencias tables: 882 account codes
of three digits (535), four digits (336) and five digits (11), and 45
two-digit subgroup tokens, with a leading digit always in 1-9.

**What this module deliberately does not decide.** The Manual writes some
equivalencias against a two-digit subgroup rather than an account, and it never
states whether that token stands for the subgroup's descendants. Reading it as
a prefix is a project inference, not the Manual's text. :meth:`CuentaPgc.is_within`
is therefore a plain string-prefix containment test on the code hierarchy — it
answers "is this account numerically inside that branch", which is a property of
PGC numbering, and it does **not** claim to answer "did the Manual mean to include
this account". A caller resolving an equivalencia must decide that separately and
carry its own grounding.

Account *normality* — whether a debit or credit balance is expected — is not
here either. It varies by account and, per the Equivalencias tables, the
parenthesis convention that might have encoded it means different things on the
Balance and on the PyG. It belongs to whatever declares an account's contract,
not to the code itself.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from ..errors import DomainValidationError

_ACCOUNT_CODE = re.compile(r"^[1-9]\d{2,4}$")
_SUBGROUP_CODE = re.compile(r"^[1-9]\d$")


class CuentaPgc(str):
    """A validated PGC account code of three to five digits.

    Subclasses :class:`str`, so a code compares, sorts and serialises as its own
    text. Construction refuses anything that is not a PGC account code shape:
    non-digits, a leading zero (no PGC grupo is 0), fewer than three digits (a
    one- or two-digit token is a grupo or subgrupo, not an account), or more
    than five.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> CuentaPgc:
        """Validate and construct a PGC account code."""
        text = str(value).strip()
        if not _ACCOUNT_CODE.match(text):
            raise DomainValidationError(
                f"{value!r} is not a PGC account code: expected three to five "
                f"digits with a leading grupo digit in 1-9"
            )
        return super().__new__(cls, text)

    @property
    def grupo(self) -> str:
        """The one-digit PGC grupo this account belongs to."""
        return self[:1]

    @property
    def subgrupo(self) -> str:
        """The two-digit PGC subgrupo this account belongs to."""
        return self[:2]

    def is_within(self, prefix: str) -> bool:
        """Whether this account is numerically inside the ``prefix`` branch.

        A string-prefix test over PGC numbering, nothing more. ``CuentaPgc("6001")``
        is within ``"6"``, ``"60"`` and ``"600"``. It does not decide whether a
        source that wrote ``"60"`` intended to cover ``6001``.
        """
        text = str(prefix).strip()
        if not text.isdigit() or not text:
            raise DomainValidationError(
                f"{prefix!r} is not a PGC code prefix: expected digits"
            )
        return self.startswith(text)

    @classmethod
    def is_subgroup_token(cls, value: str) -> bool:
        """Whether ``value`` is a two-digit subgrupo token rather than an account."""
        return bool(_SUBGROUP_CODE.match(str(value).strip()))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Validate through the constructor when used as a pydantic field."""
        return core_schema.no_info_after_validator_function(
            cls, core_schema.str_schema()
        )
