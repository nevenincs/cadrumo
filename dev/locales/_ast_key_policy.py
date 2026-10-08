"""Canonical literal, translator, namespace, and declaration shape vocabulary."""

from __future__ import annotations

import re
from typing import Final

_KEY_PATTERN_PREFIX_MIN_PARTS = 2
"""A discovered f-string key prefix must carry at least two dotted
segments before the dynamic tail (e.g. ``cli.registry.metrics``)."""


_KEY_LITERAL_RE = re.compile(r"^[\w-]+(?:\.[\w-]+)+$", re.UNICODE)
"""A literal that qualifies as a translation-key prefix: word chars,
hyphens, and dots only, at least two dotted segments, no whitespace,
slashes, operators, or other punctuation. Hyphens are first-class key
characters — the wizard page catalogue keys segments by hyphenated page
ids (``wizard.setup.format.tax-id``), and a hyphen-blind shape check
leaves every such key invisible to the scanner even when it is declared
in a ``*_LOCALE_KEY`` constant."""


_DYNAMIC_TRANSLATION_ROOTS = frozenset(
    {
        "application",
        "cli",
        "errors",
        "flows",
        "profile",
        "sheets",
        "topic",
        "tui",
        "wizard",
    },
)
"""Top-level roots that can legitimately identify dynamic i18n namespaces.

Documented dynamic-dispatch survivors
--------------------------------------
The following f-string patterns in :mod:`application.wizard.catalogue`
produce dynamic translation keys. They are bounded (not open-ended) because
the tail is always an enum member value or a flow-registered question ID —
the set of runtime keys is fully enumerable from the domain model. They are
intentional survivors of the static-key constraint and are covered here by
the ``"wizard"`` root entry:

* ``tr(f"wizard.setup.{suffix}.{qid}.prompt")`` — ``suffix`` is drawn from
  the wizard flow's registered section ID (e.g. ``"taxpayer-type"``,
  ``"obligations"``, ``"residence"``); ``qid`` is a flow-registered question
  ID. Every concrete key exists in all locale files.

* ``tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value...}.label")``
  and equivalent patterns for ``LegalEntityForm``, ``IrpfIncomeCategory``,
  ``IrpfEstimationRegime``, ``IrpfSpecialRegime``, ``FiscalResidency``,
  ``CCAA``, and ``SUPPORTED_OUTPUT_LANGUAGES`` — the tail segment is an enum
  member value (snake_case with underscores replaced by hyphens). The full
  key space is bounded by the enum definition.

These patterns are picked up by :func:`_extract_fstring_prefixes` and emitted
as ``wizard.setup.*`` namespace markers, which the parity check validates
against concrete locale entries. No additional static registration is needed.

The ``"tui"`` entry earns its place by the same criterion, through a different
shape. A workspace screen renders every public enum on it with one helper that
selects a prefix from a declared table and appends the member value::

    _LABEL_PREFIXES = {"AeatSyncCensusStatus": "tui.aeat_sync.census_status", ...}
    return aeat_sync_copy(f"{prefix}.{value.value}")

The tail is an enum member value, so the key space is bounded by the enum
definitions exactly as the wizard patterns above are. Admitting the root does
NOT tolerate ``tui.*`` at large: a marker is still emitted only where a
concrete dotted prefix is written down in source and used as one, which
:func:`_interpolated_head_prefixes` requires by demanding the segment after the
interpolation begin with the dot.
"""


#: Keyword arguments whose dotted-literal value IS a translation key. The
#: finding constructors use ``message_locale_key``; the error registry and the
#: wizard verifiers use the other three; the CLI command-spec tables use
#: ``help_key`` for every command, group and option help string they declare.
#:
#: ``help_key`` currently recovers NOTHING on its own: all 893 sites wrap their
#: value, so the wrapper rule below already reaches every one, and removing this
#: entry leaves the scanner's output unchanged. It is kept because an unwrapped
#: ``help_key="cli..."`` is the form a new spec would most naturally reach for and
#: would otherwise be silently invisible. Stated rather than left implied, so nobody
#: later reads it as evidence that bare help kwargs exist.
_TRANSLATION_KEY_KWARGS: frozenset[str] = frozenset(
    {
        "translated_message",
        "message_key",
        "translation_key",
        "message_locale_key",
        "help_key",
        # A navigation entry's operator-facing label and a zone's empty-state
        # line are keys by the same convention as help_key: the parameter is
        # named for the key it takes, and every value passed to one is a
        # catalogue-rooted dotted literal. Both were reaching the catalogue
        # through call sites nothing here read, so their keys looked orphaned.
        "label_key",
        "empty_key",
        # These three are not a judgement call: the parameter is DECLARED
        # `TranslationKey`, so the type states what the value is. They were
        # missing because this set was grown one orphan at a time, which is
        # why `test_every_translation_key_annotated_parameter_is_declared_here`
        # now holds the set to the annotations rather than to whoever last
        # chased a key.
        "reason_key",
        "short_help_key",
        "prompt_key",
        "confirmation_prompt_key",
    },
)


#: Single-argument constructors and helpers that WRAP a translation key without
#: changing it. Note ``_key`` is NOT unique to this purpose -- the AEAT session
#: store defines its own ``_key(path)`` returning a posix path -- so a wrapper is
#: only ever read as a key when its argument is a catalogue-rooted dotted literal.
#: The name alone is not the signal; the name plus the shape of what it wraps is.
#:
#: The CLI command specs never pass a bare string: every help key is
#: written ``help_key=TranslationKey("cli...")`` or ``help_key=_key("cli...")``, so
#: reading only ``ast.Constant`` values made 690 live keys invisible to this scanner
#: and reported them as catalogue-only extras — one strip away from deleting the
#: entire ledger and live CLI help surface.
_KEY_WRAPPER_CALLS: frozenset[str] = frozenset({"TranslationKey", "_key"})


#: CLI command-spec factories that take their translation key as a POSITIONAL
#: argument. The command-spec tables under ``entrypoints/cli/*_command_specs.py``
#: build every verb, group, option and argument through these few helpers, passing
#: the help key positionally rather than as ``help_key=``. Read as a declared table
#: rather than by generalising to "any positional dotted literal", which would let a
#: module path or a dotted identifier become a phantom catalogue key.
#:
#: Collection is additionally guarded by :func:`_is_dynamic_translation_prefix`, so
#: only literals rooted in a real catalogue namespace are taken.
_COMMAND_SPEC_KEY_FACTORIES: frozenset[str] = frozenset(
    {
        "_option",
        "_leaf",
        "_required",
        "_group",
        "ArgumentSpec",
        # Two more option factories, added because the keys they carry were
        # invisible: thirteen catalogue entries the source writes and this
        # scanner did not see, which the coverage and parity scanners would
        # therefore report as unused and which are one strip away from
        # deletion. Both were derived from the keys the owning gate reported
        # rather than guessed, and both are named here rather than reached by
        # widening the rule to any positional dotted literal - which the note
        # above rejects, because a module path would then become a phantom key.
        "_boolean_flag_option",
        "_repeatable_text_option",
        "_optional_text_option",
        "state_free_group_spec",
    },
)


_LOCALE_KEY_CONSTANT_SUFFIXES: tuple[str, str] = ("_LOCALE_KEY", "_LOCALE_KEYS")
"""Naming convention every module-level locale-key constant must carry.

Shared by :func:`_declares_locale_key_constant` (does this ASSIGNMENT declare
a locale-key registry?) and :func:`find_tr_constant_naming_violations` (does
this ``tr(CONSTANT)`` CALL SITE reference one?) so the two halves of the
contract — the declaration and the use — are held to one naming rule rather
than two independently-maintained copies that could drift apart."""


#: Prefix for a row table written inline at a call site, which has no name of
#: its own to be registered under. Not a valid Python identifier, so it can
#: never collide with a real assignment target.
_ANONYMOUS_TABLE: Final[str] = "<inline row table>#"


_KEY_PREFIX_RE = re.compile(r"^\w+(?:\.\w+)*\.$", re.UNICODE)
"""An f-string literal head qualifies as a key prefix when it ends in a
dot and carries at least one word segment before it (e.g. ``topic.``,
``cli.registry.metrics.``)."""


_AST_WALK_CACHE_ATTR: Final[str] = "_locale_scan_walk_nodes"
"""Private attribute used to memoise one module's deterministic walk order."""


_UPPER_CONSTANT_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""Python constant-naming shape: all-uppercase letters, digits, underscores."""
