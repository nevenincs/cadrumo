"""Report pytest collection failures confined to fixture-support imports."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

FAILED = re.compile(r"^COLLECTION FAILED (?P<node>.+)$", re.MULTILINE)
BOUNDARY = re.compile(r"^COLLECTION FAILED |^=+ short test summary info =+", re.MULTILINE)
FIXTURE_SIGNAL = re.compile(
    r"FIXTURES_DIR|fixture(?:s)?(?:\.|'|\b)|_fixtures?\b|fixture_support\b",
    re.IGNORECASE,
)
ERROR = re.compile(r"^E   (?P<error>.+)$", re.MULTILINE)


def fixture_failures(log: Path) -> tuple[list[tuple[str, str]], Counter[str]]:
    text = log.read_text(encoding="utf-8", errors="replace")
    matches = list(FAILED.finditer(text))
    failures: list[tuple[str, str]] = []
    signatures: Counter[str] = Counter()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start() : end]
        boundary = BOUNDARY.search(block, len(match.group(0)))
        if boundary:
            block = block[: boundary.start()]
        if not FIXTURE_SIGNAL.search(block):
            continue
        error = ERROR.findall(block)
        signature = error[-1] if error else "collection failure without E-line"
        failures.append((match.group("node"), signature))
        signatures[signature] += 1
    return failures, signatures


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: tmp_fixture_collection_progress.py RUN_LOG")
    failures, signatures = fixture_failures(Path(sys.argv[1]))
    print(f"fixture_collection_errors={len(failures)}")
    for signature, count in signatures.most_common():
        print(f"{count:4}  {signature}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
