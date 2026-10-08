"""Recover hash replacements by aligning preserved text, independently of redaction rules."""

from __future__ import annotations

import re

from ..hashing import sha256_hex

_DIGEST = re.compile(r"sha256:([0-9a-f]{8})")


def recover_replaced_spans(source: str, emitted: str) -> set[str]:
    """Verify each replacement digest against its source span and preserve literal text.

    Existing digest text consumes itself. For new digests, unchanged text after
    the replacement bounds candidate endpoints. No production pattern or identity
    authority participates in recovery, so widening a rule remains detectable.
    """
    matches = list(_DIGEST.finditer(emitted))
    spans: set[str] = set()
    source_position = 0
    emitted_position = 0
    for index, match in enumerate(matches):
        literal = emitted[emitted_position : match.start()]
        assert source.startswith(literal, source_position), "redaction changed text outside a hash replacement"
        source_position += len(literal)
        emitted_position = match.end()
        if source.startswith(match.group(), source_position):
            source_position += len(match.group())
            continue
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(emitted)
        following = emitted[match.end() : next_start]
        if index + 1 == len(matches):
            assert source.endswith(following), "redaction changed trailing literal text"
            stop = len(source) - len(following)
            span = source[source_position:stop]
            assert span and sha256_hex(span.encode("utf-8"))[:8] == match.group(1), (
                "replacement digest has no matching source span"
            )
            spans.add(span)
            source_position = stop
            continue
        stop = source_position + 1
        while stop <= len(source):
            if following:
                stop = source.find(following, stop)
                if stop < 0:
                    break
            span = source[source_position:stop]
            if sha256_hex(span.encode("utf-8"))[:8] == match.group(1):
                spans.add(span)
                source_position = stop
                break
            stop += 1
        else:
            raise AssertionError("replacement digest has no matching source span")
        assert source_position == stop, "replacement digest has no matching source span"
    assert source[source_position:] == emitted[emitted_position:], "redaction changed trailing literal text"
    return spans
