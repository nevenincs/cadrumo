"""Concurrent finding intake for the codebase sanitization audit.

The CLI intentionally stays standard-library only so audit workers can call it
from any checked-out workspace without importing the project package.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / ".tmp" / "codebase-sanitization-findings.sqlite3"
DEFAULT_AUDIT_DOC = PROJECT_ROOT / ".vault" / "audit" / "2026-05-05-codebase-sanitization-audit.md"

SCHEMA_VERSION = 1
FINDINGS_HEADER = "## Findings"
CONTEXT_HEADER = "## Context Cross-References"
RECOMMENDATIONS_HEADER = "## Recommendations"


@dataclass(frozen=True)
class Finding:
    """A single structured audit finding."""

    path: str
    line: int
    marker: str
    reference: str
    chunk: str
    agent: str
    excerpt: str


@dataclass(frozen=True)
class FindingContext:
    """A feature/vault cross-reference for one finding."""

    finding_id: int
    feature: str
    cause: str
    vault_refs: str
    confidence: str
    agent: str


def main(argv: list[str] | None = None) -> int:
    """Run the audit findings CLI."""

    parser = argparse.ArgumentParser(description="Concurrent finding intake for the Python sanitization audit.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path. Default: {DEFAULT_DB}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create or migrate the findings database.")
    init_parser.add_argument("--reset", action="store_true", help="Delete existing findings before initializing.")

    add_parser = subparsers.add_parser("add", help="Add one structured finding.")
    add_parser.add_argument("--file", required=True, help="Repo-relative Python file path.")
    add_parser.add_argument("--line", required=True, type=_positive_int, help="One-based source line number.")
    add_parser.add_argument("--marker", required=True, help="Matched marker, e.g. TODO, stub, compatibility.")
    add_parser.add_argument("--ref", required=True, dest="reference", help="Short reference for the suspected issue.")
    add_parser.add_argument("--chunk", default="", help="Chunk identifier assigned to the auditing worker.")
    add_parser.add_argument("--agent", default="", help="Auditing worker identifier.")
    add_parser.add_argument("--excerpt", default="", help="Optional compact source excerpt.")
    add_parser.add_argument("--json", action="store_true", help="Emit the stored row as JSON.")

    list_parser = subparsers.add_parser("list", help="List stored findings.")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON lines instead of text rows.")

    context_parser = subparsers.add_parser("context", help="Add feature and vault context for one finding.")
    context_parser.add_argument("--finding-id", required=True, type=_positive_int, help="Finding id from list --json.")
    context_parser.add_argument("--feature", required=True, help="Feature tag or '(none)'.")
    context_parser.add_argument("--cause", required=True, help="Short possible cause/context.")
    context_parser.add_argument(
        "--vault-ref",
        action="append",
        default=[],
        help="Vault document stem or path; repeat for multiple refs.",
    )
    context_parser.add_argument(
        "--confidence",
        choices=("low", "medium", "high"),
        default="medium",
        help="Confidence in the feature/cause match.",
    )
    context_parser.add_argument("--agent", default="", help="Auditing worker identifier.")
    context_parser.add_argument("--json", action="store_true", help="Emit the stored context as JSON.")

    context_list_parser = subparsers.add_parser("context-list", help="List stored finding contexts.")
    context_list_parser.add_argument("--json", action="store_true", help="Emit JSON lines instead of text rows.")

    subparsers.add_parser("stats", help="Print finding count and per-chunk counts.")

    export_parser = subparsers.add_parser("export", help="Render findings into the rolling audit document.")
    export_parser.add_argument("--audit-doc", type=Path, default=DEFAULT_AUDIT_DOC, help="Audit Markdown document.")

    args = parser.parse_args(argv)
    db_path = args.db.resolve()

    if args.command == "init":
        if args.reset and db_path.exists():
            db_path.unlink()
        with connect(db_path) as conn:
            initialize(conn)
        print(f"initialized\t{db_path}")
        return 0

    with connect(db_path) as conn:
        initialize(conn)
        if args.command == "add":
            finding = Finding(
                path=_normalize_path(args.file),
                line=args.line,
                marker=args.marker.strip(),
                reference=args.reference.strip(),
                chunk=args.chunk.strip(),
                agent=args.agent.strip(),
                excerpt=args.excerpt.strip(),
            )
            row = add_finding(conn, finding)
            if args.json:
                print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            else:
                print(f"stored\t{row['id']}\t{row['path']}:{row['line']}")
            return 0

        if args.command == "list":
            for row in list_findings(conn):
                if args.json:
                    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
                else:
                    print(format_row(row))
            return 0

        if args.command == "context":
            context = FindingContext(
                finding_id=args.finding_id,
                feature=args.feature.strip(),
                cause=args.cause.strip(),
                vault_refs="; ".join(_single_line(ref) for ref in args.vault_ref if ref.strip()),
                confidence=args.confidence,
                agent=args.agent.strip(),
            )
            row = add_context(conn, context)
            if args.json:
                print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            else:
                print(f"context\t{row['finding_id']}\t{row['feature']}")
            return 0

        if args.command == "context-list":
            for row in list_contexts(conn):
                if args.json:
                    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
                else:
                    print(format_context_row(row))
            return 0

        if args.command == "stats":
            print_stats(conn)
            return 0

        if args.command == "export":
            rows = list_findings(conn)
            contexts = list_contexts(conn)
            export_audit_doc(args.audit_doc.resolve(), rows, contexts)
            print(f"exported\t{len(rows)}\t{args.audit_doc}")
            return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def connect(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection tuned for concurrent short writes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Create the findings schema if needed."""

    with transaction(conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                line INTEGER NOT NULL CHECK (line > 0),
                marker TEXT NOT NULL CHECK (length(marker) > 0),
                reference TEXT NOT NULL CHECK (length(reference) > 0),
                chunk TEXT NOT NULL DEFAULT '',
                agent TEXT NOT NULL DEFAULT '',
                excerpt TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE(path, line, marker, reference)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finding_context (
                finding_id INTEGER PRIMARY KEY,
                feature TEXT NOT NULL CHECK (length(feature) > 0),
                cause TEXT NOT NULL CHECK (length(cause) > 0),
                vault_refs TEXT NOT NULL DEFAULT '',
                confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
                agent TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                FOREIGN KEY(finding_id) REFERENCES findings(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )


def add_finding(conn: sqlite3.Connection, finding: Finding) -> dict[str, object]:
    """Store one finding and return the canonical row."""

    if not finding.marker:
        raise SystemExit("--marker must not be empty")
    if not finding.reference:
        raise SystemExit("--ref must not be empty")
    if Path(finding.path).is_absolute():
        raise SystemExit("--file must be repo-relative")

    for attempt in range(5):
        try:
            with transaction(conn):
                conn.execute(
                    """
                    INSERT INTO findings(path, line, marker, reference, chunk, agent, excerpt)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path, line, marker, reference) DO UPDATE SET
                        chunk = excluded.chunk,
                        agent = excluded.agent,
                        excerpt = excluded.excerpt
                    """,
                    (
                        finding.path,
                        finding.line,
                        finding.marker,
                        finding.reference,
                        finding.chunk,
                        finding.agent,
                        finding.excerpt,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT id, path, line, marker, reference, chunk, agent, excerpt, created_at
                    FROM findings
                    WHERE path = ? AND line = ? AND marker = ? AND reference = ?
                    """,
                    (finding.path, finding.line, finding.marker, finding.reference),
                ).fetchone()
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))

    if row is None:
        raise RuntimeError("finding was not stored")
    return dict(row)


def add_context(conn: sqlite3.Connection, context: FindingContext) -> dict[str, object]:
    """Store cross-reference context for one finding."""

    if not context.feature:
        raise SystemExit("--feature must not be empty")
    if not context.cause:
        raise SystemExit("--cause must not be empty")
    if conn.execute("SELECT 1 FROM findings WHERE id = ?", (context.finding_id,)).fetchone() is None:
        raise SystemExit(f"finding id not found: {context.finding_id}")

    for attempt in range(5):
        try:
            with transaction(conn):
                conn.execute(
                    """
                    INSERT INTO finding_context(
                        finding_id, feature, cause, vault_refs, confidence, agent
                    )
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(finding_id) DO UPDATE SET
                        feature = excluded.feature,
                        cause = excluded.cause,
                        vault_refs = excluded.vault_refs,
                        confidence = excluded.confidence,
                        agent = excluded.agent,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    """,
                    (
                        context.finding_id,
                        context.feature,
                        context.cause,
                        context.vault_refs,
                        context.confidence,
                        context.agent,
                    ),
                )
                row = conn.execute(
                    """
                    SELECT finding_id, feature, cause, vault_refs, confidence, agent, created_at, updated_at
                    FROM finding_context
                    WHERE finding_id = ?
                    """,
                    (context.finding_id,),
                ).fetchone()
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))

    if row is None:
        raise RuntimeError("finding context was not stored")
    return dict(row)


def list_findings(conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Return findings in deterministic source order."""

    rows = conn.execute(
        """
        SELECT id, path, line, marker, reference, chunk, agent, excerpt, created_at
        FROM findings
        ORDER BY path COLLATE NOCASE, line, marker COLLATE NOCASE, reference COLLATE NOCASE
        """
    ).fetchall()
    return [dict(row) for row in rows]


def list_contexts(conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Return context rows joined to findings in deterministic source order."""

    rows = conn.execute(
        """
        SELECT
            c.finding_id,
            f.path,
            f.line,
            f.marker,
            f.reference,
            c.feature,
            c.cause,
            c.vault_refs,
            c.confidence,
            c.agent,
            c.created_at,
            c.updated_at
        FROM finding_context AS c
        JOIN findings AS f ON f.id = c.finding_id
        ORDER BY f.path COLLATE NOCASE, f.line, f.marker COLLATE NOCASE, f.reference COLLATE NOCASE
        """
    ).fetchall()
    return [dict(row) for row in rows]


def print_stats(conn: sqlite3.Connection) -> None:
    """Print total and chunk counts."""

    total = conn.execute("SELECT COUNT(*) AS total FROM findings").fetchone()["total"]
    context_total = conn.execute("SELECT COUNT(*) AS total FROM finding_context").fetchone()["total"]
    print(f"total\t{total}")
    print(f"context_total\t{context_total}")
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(chunk, ''), '(none)') AS chunk, COUNT(*) AS count
        FROM findings
        GROUP BY COALESCE(NULLIF(chunk, ''), '(none)')
        ORDER BY chunk
        """
    ).fetchall()
    for row in rows:
        print(f"chunk\t{row['chunk']}\t{row['count']}")


def export_audit_doc(
    path: Path,
    rows: Iterable[dict[str, object]],
    contexts: Iterable[dict[str, object]],
) -> None:
    """Replace the findings section in the vault audit document."""

    text = path.read_text(encoding="utf-8")
    findings_index = text.index(FINDINGS_HEADER)
    context_index = text.find(CONTEXT_HEADER)
    recommendations_index = text.index(RECOMMENDATIONS_HEADER)
    before = text[:findings_index]
    after = text[recommendations_index:]
    rendered_rows = "\n".join(format_row(row) for row in rows)
    if not rendered_rows:
        rendered_rows = "No suspected markers recorded."
    rendered_contexts = "\n".join(format_context_row(row) for row in contexts)
    if not rendered_contexts:
        rendered_contexts = "No feature or vault context recorded yet."
    findings = (
        "## Findings\n\n"
        "Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3`.\n\n"
        "```text\n"
        "file:line | marker | short reference\n"
        f"{rendered_rows}\n"
        "```\n\n"
    )
    context_block = (
        "## Context Cross-References\n\n"
        "Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3` context records.\n\n"
        "```text\n"
        "file:line | marker | feature | confidence | vault refs | possible cause/context\n"
        f"{rendered_contexts}\n"
        "```\n\n"
    )
    if context_index != -1 and context_index < recommendations_index:
        path.write_text(before + findings + context_block + after, encoding="utf-8")
    else:
        path.write_text(before + findings + context_block + after, encoding="utf-8")


def format_row(row: dict[str, object]) -> str:
    """Render one row in the rolling audit format."""

    path = str(row["path"]).replace("\\", "/")
    line = int(row["line"])
    marker = _single_line(str(row["marker"]))
    reference = _single_line(str(row["reference"]))
    excerpt = _single_line(str(row.get("excerpt") or ""))
    suffix = f" | {excerpt}" if excerpt else ""
    return f"{path}:{line} | {marker} | {reference}{suffix}"


def format_context_row(row: dict[str, object]) -> str:
    """Render one context row in the audit format."""

    path = str(row["path"]).replace("\\", "/")
    line = int(row["line"])
    marker = _single_line(str(row["marker"]))
    feature = _single_line(str(row["feature"]))
    confidence = _single_line(str(row["confidence"]))
    refs = _single_line(str(row.get("vault_refs") or "(none)"))
    cause = _single_line(str(row["cause"]))
    return f"{path}:{line} | {marker} | {feature} | {confidence} | {refs} | {cause}"


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection) -> Iterable[None]:
    """Run a short immediate transaction."""

    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _normalize_path(raw: str) -> str:
    return raw.strip().replace("\\", "/")


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def _single_line(raw: str) -> str:
    return " ".join(unquote(raw).split())


if __name__ == "__main__":
    sys.exit(main())
