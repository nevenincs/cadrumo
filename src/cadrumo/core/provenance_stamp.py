"""The provenance stamp's grammar: one constructor, one parser, one home.

A provenance stamp is the durable record of HOW a value was reached --
``llm:<transport>-<reader>:<model>`` with an optional trailing qualifier. It is
written by the readers in the inference subpackage and read back by the consent
withdrawal survey in the application layer, and those two may not import each
other. Declared here, in ``core``, because it is a closed grammar shared across
a boundary neither side can cross: any other home leaves it written down twice.

**The transport segment is load-bearing, not decoration.** A consent withdrawal
enumerates cloud-derived artefacts BY that segment, so a stamp that omits it, or
that formats it differently, describes an artefact the withdrawal cannot see --
and that is precisely the artefact most needing re-derivation. Five producers
once hand-formatted this string and one of them did not follow the grammar at
all, misparsing its own reader name as its transport.

**The constructor is not the guarantee; the gate is.** A canonical function that
producers may ignore is a convention, and a convention is what produced five
hand-formatted strings. The gate asserting every producer routes through here
lives in the test suite, because a sixth producer that hand-formats a sixth
string is the failure this module exists to prevent, not the one it can fix.

See Also:
    :class:`~core.config.LLMProvider`
        The transport axis a stamp's first segment names.
"""

from __future__ import annotations

from .config_support import LLMProvider

__all__ = [
    "LOCAL_TRANSPORT_LABEL",
    "build_provenance_stamp",
    "provenance_stamp_transport",
    "provenance_transport_label",
]

LOCAL_TRANSPORT_LABEL = "local"
"""Transport token an on-host read stamps.

The word rather than the enum value, because the token is operator-facing
provenance rather than a serialized enum: it answers "did this leave the host".
"""

_STAMP_PREFIX = "llm"


def provenance_transport_label(provider: LLMProvider) -> str:
    """Return the transport token a reader stamps for ``provider``.

    Derived from the enum rather than listed, so a provider added later gets a
    token by construction instead of being silently omitted from a hand-kept
    map -- and the newest transport is exactly the one a hand-kept map misses.
    """
    if provider is LLMProvider.LOCAL:
        return LOCAL_TRANSPORT_LABEL
    return provider.value.lower()


def build_provenance_stamp(
    *,
    provider: LLMProvider,
    reader: str,
    model: str,
    qualifier: str | None = None,
) -> str:
    """Build the one canonical provenance stamp for a model-produced value.

    Args:
        provider: The transport the read actually ran at. Passed as the enum
            rather than a pre-rendered label so a caller cannot supply a
            transport the read did not use, which is how a stamp comes to say
            ``local`` for a read served off-host.
        reader: Which reader produced the value (``vision``, ``text-extract``,
            ``column-role-map``). May contain hyphens: the transport and reader
            share one segment but the split takes the FIRST hyphen, and the
            transport is enum-derived and so hyphen-free by construction. What
            a reader may not do is omit the transport, which is how one
            producer's stamp came to parse its own reader name as its
            transport.
        model: The model identifier, or a marker such as ``configured`` when the
            caller pinned none.
        qualifier: Optional trailing detail, such as the rate provenance a
            compiled prompt was built under.

    Returns:
        ``llm:<transport>-<reader>:<model>`` plus ``:<qualifier>`` when given.

    Raises:
        ValueError: When ``reader`` is blank, contains ``:`` (which would open a
            second stamp segment and shift every field after it), or ``model``
            is blank. Refused rather than sanitised: a stamp is an audit record,
            and quietly rewriting one produces a record that answers the audit
            question confidently and wrongly.
    """
    if not reader.strip() or not model.strip():
        msg = f"a provenance stamp needs a reader and a model; got reader={reader!r} model={model!r}"
        raise ValueError(msg)
    if ":" in reader:
        msg = f"reader {reader!r} must not contain ':': it would open a second stamp segment"
        raise ValueError(msg)
    stamp = f"{_STAMP_PREFIX}:{provenance_transport_label(provider)}-{reader}:{model}"
    return f"{stamp}:{qualifier}" if qualifier else stamp


def provenance_stamp_transport(stamp: str) -> str | None:
    """Return the transport a provenance stamp names, or ``None``.

    ``None`` means the stamp does not name one -- a hand-formatted stamp, a
    non-LLM origin such as a rule or a manual classification, or a shape this
    grammar does not cover.

    **An unreadable stamp is NOT read as on-host.** Returning ``None`` rather
    than :data:`LOCAL_TRANSPORT_LABEL` is the whole point: it is a question this
    function cannot answer, and answering it optimistically would drop exactly
    the artefact a withdrawal most needs to surface. What to do with the
    uncertainty is the caller's decision, not this function's.
    """
    segments = stamp.split(":")
    if len(segments) < 2 or segments[0] != _STAMP_PREFIX:
        return None
    transport, separator, reader = segments[1].partition("-")
    if not separator or not transport or not reader:
        return None
    return transport
