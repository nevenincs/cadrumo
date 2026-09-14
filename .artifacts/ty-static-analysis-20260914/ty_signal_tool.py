#!/usr/bin/env python3
"""Deterministic static signal analysis for a ty GitLab JSON diagnostic dump."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.0.0"
DEFAULT_TY_COMMAND = (
    "uv run --no-sync ty check src dev/__init__.py dev/_paths.py dev/actionlint.py "
    "dev/ci_contract.py dev/ci_reports.py dev/exit_codes.py dev/scripted_registration_channels.py "
    "dev/containers dev/corpus dev/env dev/identity dev/ingest_harness dev/init dev/quality "
    "dev/readme dev/registry dev/release dev/sanitizer dev/smoke dev/test_runs "
    "--output-format gitlab --color never"
)

BACKTICK = re.compile(r"`[^`]*`")
BACKTICK_VALUE = re.compile(r"`([^`]*)`")
CLASS_ATTRIBUTE = re.compile(r"^unresolved-attribute: Class `(?P<owner>[^`]+)` has no attribute `(?P<member>[^`]+)`")
OBJECT_ATTRIBUTE = re.compile(
    r"^unresolved-attribute: Object of type `(?P<owner>[^`]+)` has no attribute `(?P<member>[^`]+)`"
)
MISSING_ONE = re.compile(
    r"^missing-argument: No argument provided for required parameter `(?P<parameter>[^`]+)` "
    r"(?:of function|of bound method|of) `(?P<function>[^`]+)`"
)
MISSING_MANY = re.compile(
    r"^missing-argument: No arguments provided for required parameters (?P<parameters>.+?) "
    r"of function `(?P<function>[^`]+)`"
)
UNKNOWN_ARGUMENT = re.compile(
    r"^unknown-argument: Argument `(?P<parameter>[^`]+)` does not match any known parameter "
    r"(?:of function|of) `(?P<function>[^`]+)`"
)
INVALID_ARGUMENT = re.compile(r"^invalid-argument-type: .*?Expected `(?P<expected>[^`]+)`, found `(?P<found>[^`]+)`")
INVALID_ARGUMENT_FUNCTION = re.compile(r"^invalid-argument-type: Argument to function `(?P<function>[^`]+)`")
OVERRIDE = re.compile(r"^missing-override-decorator: Method `(?P<method>[^`]+)` overrides `(?P<base>[^`]+)`")


@dataclass(frozen=True)
class Diagnostic:
    rule: str
    description: str
    severity: str
    path: str
    line: int
    column: int


def stable_items(counter: Counter[Any]) -> list[tuple[Any, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def csv_bytes(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def validate_and_load(raw: bytes) -> list[Diagnostic]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"input is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("GitLab dump root must be a JSON array")
    diagnostics: list[Diagnostic] = []
    for index, item in enumerate(payload):
        try:
            rule = item["check_name"]
            description = item["description"]
            severity = item["severity"]
            location = item["location"]
            path = location["path"].replace("\\", "/")
            begin = location["positions"]["begin"]
            line = begin["line"]
            column = begin["column"]
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"diagnostic {index} does not match GitLab schema") from exc
        if not all(isinstance(value, str) for value in (rule, description, severity, path)):
            raise ValueError(f"diagnostic {index} has a non-string identity field")
        if not isinstance(line, int) or not isinstance(column, int):
            raise ValueError(f"diagnostic {index} has a non-integer begin position")
        diagnostics.append(Diagnostic(rule, description, severity, path, line, column))
    return diagnostics


def is_test_path(path: str) -> bool:
    marked = f"/{path}"
    return "/tests/" in marked or Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py")


def path_bucket(path: str) -> str:
    parts = Path(path).parts
    depth = 4 if parts and parts[0] == "src" else 3
    return "/".join(parts[: min(depth, len(parts))])


def percent(count: int, total: int) -> float:
    return round(100.0 * count / total, 2) if total else 0.0


def analyze(
    diagnostics: list[Diagnostic], *, input_name: str, input_sha256: str, input_size: int, ty_command: str
) -> dict[str, bytes]:
    total = len(diagnostics)
    rules: Counter[str] = Counter()
    files: Counter[str] = Counter()
    buckets: Counter[str] = Counter()
    templates: Counter[tuple[str, str]] = Counter()
    exact_messages: Counter[tuple[str, str]] = Counter()
    severities: Counter[str] = Counter()
    test_split: Counter[str] = Counter()
    file_rules: dict[str, Counter[str]] = defaultdict(Counter)

    class_attributes: Counter[tuple[str, str]] = Counter()
    class_owner_files: dict[str, set[str]] = defaultdict(set)
    class_attribute_ids: set[int] = set()
    object_attributes: Counter[tuple[str, str]] = Counter()
    other_unresolved: Counter[str] = Counter()

    missing_by_function: dict[str, Counter[str]] = defaultdict(Counter)
    unknown_by_function: dict[str, Counter[str]] = defaultdict(Counter)
    function_files: dict[str, set[str]] = defaultdict(set)
    function_diagnostic_ids: dict[str, set[int]] = defaultdict(set)
    missing_operation_ids: set[int] = set()
    profile_context_ids: set[int] = set()
    invalid_type_pairs: Counter[tuple[str, str]] = Counter()
    invalid_found_object_ids: set[int] = set()

    for diagnostic_id, diagnostic in enumerate(diagnostics):
        rules[diagnostic.rule] += 1
        files[diagnostic.path] += 1
        buckets[path_bucket(diagnostic.path)] += 1
        templates[(diagnostic.rule, BACKTICK.sub("`{}`", diagnostic.description))] += 1
        exact_messages[(diagnostic.rule, diagnostic.description)] += 1
        severities[diagnostic.severity] += 1
        test_split["test" if is_test_path(diagnostic.path) else "non_test"] += 1
        file_rules[diagnostic.path][diagnostic.rule] += 1

        if diagnostic.rule == "unresolved-attribute":
            if match := CLASS_ATTRIBUTE.match(diagnostic.description):
                owner, member = match.group("owner", "member")
                class_attributes[(owner, member)] += 1
                class_owner_files[owner].add(diagnostic.path)
                class_attribute_ids.add(diagnostic_id)
            elif match := OBJECT_ATTRIBUTE.match(diagnostic.description):
                object_attributes[match.group("owner", "member")] += 1
            else:
                other_unresolved[BACKTICK.sub("`{}`", diagnostic.description)] += 1

        parsed_call: tuple[str, tuple[str, ...], str] | None = None
        if match := MISSING_ONE.match(diagnostic.description):
            parsed_call = (match.group("function"), (match.group("parameter"),), "missing")
        elif match := MISSING_MANY.match(diagnostic.description):
            parsed_call = (match.group("function"), tuple(BACKTICK_VALUE.findall(match.group("parameters"))), "missing")
        elif match := UNKNOWN_ARGUMENT.match(diagnostic.description):
            parsed_call = (match.group("function"), (match.group("parameter"),), "unknown")
        if parsed_call:
            function, parameters, kind = parsed_call
            destination = missing_by_function if kind == "missing" else unknown_by_function
            for parameter in parameters:
                destination[function][parameter] += 1
            function_files[function].add(diagnostic.path)
            function_diagnostic_ids[function].add(diagnostic_id)
            if kind == "missing" and "operation" in parameters:
                missing_operation_ids.add(diagnostic_id)
            if kind == "missing" and ({"profile_decode_context", "profile_create_context"} & set(parameters)):
                profile_context_ids.add(diagnostic_id)

        if match := INVALID_ARGUMENT.match(diagnostic.description):
            invalid_type_pairs[match.group("expected", "found")] += 1
            if match.group("found") == "object":
                invalid_found_object_ids.add(diagnostic_id)

    rule_pairs: Counter[tuple[str, str]] = Counter()
    rule_pair_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path, counts in file_rules.items():
        for pair in combinations(sorted(counts), 2):
            rule_pairs[pair] += min(counts[pair[0]], counts[pair[1]])
            rule_pair_files[pair].add(path)

    signature_rows: list[dict[str, object]] = []
    for function in sorted(set(missing_by_function) | set(unknown_by_function)):
        missing = missing_by_function[function]
        unknown = unknown_by_function[function]
        signature_rows.append(
            {
                "function": function,
                "diagnostics": len(function_diagnostic_ids[function]),
                "files": len(function_files[function]),
                "missing": dict(stable_items(missing)),
                "unknown": dict(stable_items(unknown)),
            }
        )
    signature_rows.sort(key=lambda row: (-int(row["diagnostics"]), str(row["function"])))

    ports_functions = {
        function
        for function, missing in missing_by_function.items()
        if missing["ports"] and unknown_by_function.get(function)
    }
    ports_ids = (
        set().union(*(function_diagnostic_ids[function] for function in ports_functions)) if ports_functions else set()
    )
    ports_files = set().union(*(function_files[function] for function in ports_functions)) if ports_functions else set()

    top_eight_owners = {
        owner
        for owner, _count in stable_items(
            Counter(
                {
                    owner: sum(count for (candidate, _), count in class_attributes.items() if candidate == owner)
                    for owner, _ in class_attributes
                }
            )
        )[:8]
    }
    top_eight_ids = {
        index
        for index, diagnostic in enumerate(diagnostics)
        if (match := CLASS_ATTRIBUTE.match(diagnostic.description)) and match.group("owner") in top_eight_owners
    }

    def diagnostic_split(ids: set[int]) -> dict[str, int]:
        test_count = sum(is_test_path(diagnostics[index].path) for index in ids)
        return {"test_diagnostics": test_count, "non_test_diagnostics": len(ids) - test_count}

    override_ids = {
        index for index, diagnostic in enumerate(diagnostics) if diagnostic.rule == "missing-override-decorator"
    }

    ordered_candidates = [
        (
            "RC1-class-static-member-access",
            "unresolved-attribute exactly matching Class <owner> has no attribute <member>",
            class_attribute_ids,
        ),
        (
            "RC2-ports-signature-migration",
            "parsed missing/unknown diagnostics for functions that both require ports and reject old arguments",
            ports_ids,
        ),
        (
            "RC3-object-typed-argument-flow",
            "invalid-argument-type with parsed found type exactly object",
            invalid_found_object_ids,
        ),
        (
            "RC4-operation-propagation",
            "missing-argument whose parsed required-parameter list contains operation",
            missing_operation_ids,
        ),
        (
            "RC5-missing-override-contract",
            "all missing-override-decorator diagnostics",
            override_ids,
        ),
        (
            "RC6-profile-context-propagation",
            "missing-argument containing profile_decode_context or profile_create_context",
            profile_context_ids,
        ),
    ]
    assigned: set[int] = set()
    cluster_for_diagnostic: dict[int, str] = {}
    burn_down_clusters: list[dict[str, object]] = []
    for cluster_id, matcher, matched_ids in ordered_candidates:
        exclusive_ids = matched_ids - assigned
        for diagnostic_id in exclusive_ids:
            cluster_for_diagnostic[diagnostic_id] = cluster_id
        burn_down_clusters.append(
            {
                "id": cluster_id,
                "matcher": matcher,
                "raw_count": len(matched_ids),
                "exclusive_count": len(exclusive_ids),
                "overlap_with_earlier": len(matched_ids) - len(exclusive_ids),
                "files": len({diagnostics[index].path for index in matched_ids}),
                **diagnostic_split(matched_ids),
                "completion_signal": "raw_count == 0",
            }
        )
        assigned.update(matched_ids)
    residual_ids = set(range(total)) - assigned
    for diagnostic_id in residual_ids:
        cluster_for_diagnostic[diagnostic_id] = "RESIDUAL-unclustered"
    burn_down_clusters.append(
        {
            "id": "RESIDUAL-unclustered",
            "matcher": "all diagnostics not assigned by RC1-RC6 in order",
            "raw_count": len(residual_ids),
            "exclusive_count": len(residual_ids),
            "overlap_with_earlier": 0,
            "files": len({diagnostics[index].path for index in residual_ids}),
            **diagnostic_split(residual_ids),
            "completion_signal": "exclusive_count == 0",
        }
    )

    offender_counts: dict[str, Counter[str]] = defaultdict(Counter)
    offender_files: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    offender_subpatterns: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    diagnostic_index_rows: list[tuple[object, ...]] = []
    for diagnostic_id, diagnostic in enumerate(diagnostics):
        cluster_id = cluster_for_diagnostic[diagnostic_id]
        offender = diagnostic.rule
        subpattern = BACKTICK.sub("`{}`", diagnostic.description)
        if cluster_id == "RC1-class-static-member-access":
            match = CLASS_ATTRIBUTE.match(diagnostic.description)
            assert match is not None
            offender = match.group("owner")
            subpattern = match.group("member")
        elif cluster_id in {
            "RC2-ports-signature-migration",
            "RC4-operation-propagation",
            "RC6-profile-context-propagation",
        }:
            if match := MISSING_ONE.match(diagnostic.description):
                offender = match.group("function")
                subpattern = f"missing:{match.group('parameter')}"
            elif match := MISSING_MANY.match(diagnostic.description):
                offender = match.group("function")
                subpattern = "missing:" + "+".join(BACKTICK_VALUE.findall(match.group("parameters")))
            elif match := UNKNOWN_ARGUMENT.match(diagnostic.description):
                offender = match.group("function")
                subpattern = f"unknown:{match.group('parameter')}"
        elif cluster_id == "RC3-object-typed-argument-flow":
            offender_match = INVALID_ARGUMENT_FUNCTION.match(diagnostic.description)
            offender = offender_match.group("function") if offender_match else "<unscoped-invalid-argument>"
            type_match = INVALID_ARGUMENT.match(diagnostic.description)
            assert type_match is not None
            subpattern = f"{type_match.group('expected')} <- {type_match.group('found')}"
        elif cluster_id == "RC5-missing-override-contract":
            if match := OVERRIDE.match(diagnostic.description):
                offender = match.group("base")
                subpattern = match.group("method")

        offender_counts[cluster_id][offender] += 1
        offender_files[(cluster_id, offender)][diagnostic.path] += 1
        offender_subpatterns[(cluster_id, offender)][subpattern] += 1
        diagnostic_index_rows.append(
            (
                cluster_id,
                offender,
                subpattern,
                diagnostic.rule,
                diagnostic.path,
                diagnostic.line,
                diagnostic.column,
                diagnostic.description,
            )
        )

    offender_clusters: list[dict[str, object]] = []
    for cluster in burn_down_clusters:
        cluster_id = str(cluster["id"])
        offenders = []
        for offender, count in stable_items(offender_counts[cluster_id]):
            file_counter = offender_files[(cluster_id, offender)]
            offenders.append(
                {
                    "offender": offender,
                    "count": count,
                    "files": len(file_counter),
                    "top_files": [
                        {"path": path, "count": file_count} for path, file_count in stable_items(file_counter)[:20]
                    ],
                    "subpatterns": [
                        {"signal": signal, "count": signal_count}
                        for signal, signal_count in stable_items(offender_subpatterns[(cluster_id, offender)])
                    ],
                }
            )
        offender_clusters.append(
            {
                "id": cluster_id,
                "exclusive_count": cluster["exclusive_count"],
                "offender_count": len(offenders),
                "offenders": offenders,
            }
        )

    clusters = [
        {
            "id": "class-static-member-access",
            "definition": "unresolved-attribute diagnostics exactly matching Class <owner> has no attribute <member>",
            "diagnostics": sum(class_attributes.values()),
            "files": len(set().union(*class_owner_files.values())) if class_owner_files else 0,
            "owners": len(class_owner_files),
            "percent_total": percent(sum(class_attributes.values()), total),
            **diagnostic_split(class_attribute_ids),
        },
        {
            "id": "top-eight-class-member-owners",
            "definition": "subset of class-static-member-access for the eight highest-frequency owners",
            "diagnostics": len(top_eight_ids),
            "files": len({diagnostics[index].path for index in top_eight_ids}),
            "owners": sorted(top_eight_owners),
            "percent_total": percent(len(top_eight_ids), total),
            **diagnostic_split(top_eight_ids),
        },
        {
            "id": "ports-signature-migration",
            "definition": "all parsed missing/unknown call diagnostics for functions that both require missing ports and reject at least one old argument",
            "diagnostics": len(ports_ids),
            "files": len(ports_files),
            "functions": len(ports_functions),
            "percent_total": percent(len(ports_ids), total),
            **diagnostic_split(ports_ids),
        },
        {
            "id": "missing-operation-propagation",
            "definition": "missing-argument diagnostics whose parsed required-parameter list contains operation",
            "diagnostics": len(missing_operation_ids),
            "files": len({diagnostics[index].path for index in missing_operation_ids}),
            "functions": len({function for function, values in missing_by_function.items() if values["operation"]}),
            "percent_total": percent(len(missing_operation_ids), total),
            **diagnostic_split(missing_operation_ids),
        },
        {
            "id": "missing-profile-context",
            "definition": "missing-argument diagnostics containing profile_decode_context or profile_create_context",
            "diagnostics": len(profile_context_ids),
            "files": len({diagnostics[index].path for index in profile_context_ids}),
            "percent_total": percent(len(profile_context_ids), total),
            **diagnostic_split(profile_context_ids),
        },
        {
            "id": "missing-override-decorator",
            "definition": "all missing-override-decorator diagnostics",
            "diagnostics": rules["missing-override-decorator"],
            "files": len(
                {diagnostic.path for diagnostic in diagnostics if diagnostic.rule == "missing-override-decorator"}
            ),
            "percent_total": percent(rules["missing-override-decorator"], total),
            **diagnostic_split(override_ids),
        },
    ]

    summary = {
        "schema": "cadrumo.ty-static-signals.v1",
        "total": total,
        "unique_files": len(files),
        "unique_rules": len(rules),
        "unique_exact_messages": len(exact_messages),
        "unique_normalized_templates": len(templates),
        "severity": dict(stable_items(severities)),
        "test_split": dict(stable_items(test_split)),
        "rules": [
            {"rule": key, "count": value, "percent_total": percent(value, total)} for key, value in stable_items(rules)
        ],
        "path_buckets": [
            {"path_bucket": key, "count": value, "percent_total": percent(value, total)}
            for key, value in stable_items(buckets)
        ],
        "clusters": clusters,
        "notes": [
            "Clusters may overlap and must not be summed as independent diagnostics.",
            "Root-cause labels describe text signatures; no runtime or source-code inference is used.",
        ],
    }

    owner_counts: Counter[str] = Counter()
    owner_members: dict[str, set[str]] = defaultdict(set)
    for (owner, member), count in class_attributes.items():
        owner_counts[owner] += count
        owner_members[owner].add(member)

    outputs: dict[str, bytes] = {
        "summary.json": json_bytes(summary),
        "root-clusters.json": json_bytes({"schema": "cadrumo.ty-root-clusters.v1", "clusters": clusters}),
        "burn-down.json": json_bytes(
            {
                "schema": "cadrumo.ty-burn-down.v1",
                "input_sha256": input_sha256,
                "total_baseline": total,
                "delta_formula": "new_count - baseline_count; negative is progress",
                "ordered_exclusive_clusters": burn_down_clusters,
                "invariant": "sum(exclusive_count) == total_baseline",
            }
        ),
        "offender-clusters.json": json_bytes(
            {
                "schema": "cadrumo.ty-offender-clusters.v1",
                "input_sha256": input_sha256,
                "clusters": offender_clusters,
            }
        ),
        "diagnostic-index.csv": csv_bytes(
            ("cluster", "offender", "subpattern", "rule", "path", "line", "column", "description"),
            diagnostic_index_rows,
        ),
        "work-packets.csv": csv_bytes(
            ("cluster", "offender", "count", "file_count", "top_subpatterns", "top_files"),
            (
                (
                    cluster["id"],
                    offender["offender"],
                    offender["count"],
                    offender["files"],
                    json.dumps(offender["subpatterns"][:20], ensure_ascii=False, sort_keys=True),
                    json.dumps(offender["top_files"], ensure_ascii=False, sort_keys=True),
                )
                for cluster in offender_clusters
                for offender in cluster["offenders"]
            ),
        ),
        "call-signatures.json": json_bytes({"schema": "cadrumo.ty-call-signatures.v1", "functions": signature_rows}),
        "rules.csv": csv_bytes(
            ("rule", "count", "percent_total"),
            ((key, count, percent(count, total)) for key, count in stable_items(rules)),
        ),
        "files.csv": csv_bytes(
            ("path", "count", "percent_total"),
            ((key, count, percent(count, total)) for key, count in stable_items(files)),
        ),
        "message-templates.csv": csv_bytes(
            ("rule", "template", "count"),
            ((rule, template, count) for (rule, template), count in stable_items(templates)),
        ),
        "exact-messages.csv": csv_bytes(
            ("rule", "description", "count"),
            ((rule, description, count) for (rule, description), count in stable_items(exact_messages)),
        ),
        "class-attribute-owners.csv": csv_bytes(
            ("owner", "count", "files", "unique_members", "percent_class_attributes", "percent_total"),
            (
                (
                    owner,
                    count,
                    len(class_owner_files[owner]),
                    len(owner_members[owner]),
                    percent(count, sum(class_attributes.values())),
                    percent(count, total),
                )
                for owner, count in stable_items(owner_counts)
            ),
        ),
        "class-attribute-members.csv": csv_bytes(
            ("owner", "member", "count"),
            ((owner, member, count) for (owner, member), count in stable_items(class_attributes)),
        ),
        "object-attributes.csv": csv_bytes(
            ("owner", "member", "count"),
            ((owner, member, count) for (owner, member), count in stable_items(object_attributes)),
        ),
        "invalid-argument-type-pairs.csv": csv_bytes(
            ("expected", "found", "count"),
            ((expected, found, count) for (expected, found), count in stable_items(invalid_type_pairs)),
        ),
        "rule-cooccurrence.csv": csv_bytes(
            ("left_rule", "right_rule", "weighted_count", "file_count"),
            (
                (left, right, count, len(rule_pair_files[(left, right)]))
                for (left, right), count in stable_items(rule_pairs)
            ),
        ),
    }

    top_rules = stable_items(rules)[:12]
    top_owners = stable_items(owner_counts)[:20]
    top_functions = signature_rows[:20]
    top_exact_messages = stable_items(exact_messages)[:20]
    report = [
        "# ty static signal report",
        "",
        f"Input SHA-256: `{input_sha256}`  ",
        f"Diagnostics: **{total:,}** across **{len(files):,}** files  ",
        f"Tests: **{test_split['test']:,}** ({percent(test_split['test'], total):.2f}%)  ",
        f"Non-tests: **{test_split['non_test']:,}** ({percent(test_split['non_test'], total):.2f}%)",
        "",
        "## Rule Pareto",
        "",
        "| Rule | Count | % total |",
        "|---|---:|---:|",
        *[f"| `{rule}` | {count:,} | {percent(count, total):.2f}% |" for rule, count in top_rules],
        "",
        "## Reproducible signal clusters",
        "",
        "| Cluster | Exact definition | Diagnostics | Test | Non-test | Files | % total |",
        "|---|---|---:|---:|---:|---:|---:|",
        *[
            f"| `{cluster['id']}` | {cluster['definition']} | {cluster['diagnostics']:,} | "
            f"{cluster['test_diagnostics']:,} | {cluster['non_test_diagnostics']:,} | "
            f"{cluster['files']:,} | {cluster['percent_total']:.2f}% |"
            for cluster in clusters
        ],
        "",
        "Clusters overlap; percentages are not additive.",
        "",
        "## Ordered exclusive burn-down",
        "",
        "| Cluster | Raw | Exclusive | Earlier overlap | Test | Non-test | Completion |",
        "|---|---:|---:|---:|---:|---:|---|",
        *[
            f"| `{cluster['id']}` | {cluster['raw_count']:,} | {cluster['exclusive_count']:,} | "
            f"{cluster['overlap_with_earlier']:,} | {cluster['test_diagnostics']:,} | "
            f"{cluster['non_test_diagnostics']:,} | `{cluster['completion_signal']}` |"
            for cluster in burn_down_clusters
        ],
        "",
        "## Actual offender hierarchy",
        "",
        *[
            line
            for cluster in offender_clusters[:-1]
            for line in (
                f"### {cluster['id']}",
                "",
                "| Offender | Diagnostics | Files | Dominant sub-signals |",
                "|---|---:|---:|---|",
                *(
                    f"| `{offender['offender']}` | {offender['count']:,} | {offender['files']:,} | "
                    f"{', '.join(f'`{item["signal"]}` ({item["count"]})' for item in offender['subpatterns'][:5])} |"
                    for offender in cluster["offenders"][:10]
                ),
                "",
            )
        ],
        "## Top class/member owners",
        "",
        "| Owner | Diagnostics | Files | Unique members |",
        "|---|---:|---:|---:|",
        *[
            f"| `{owner}` | {count:,} | {len(class_owner_files[owner]):,} | {len(owner_members[owner]):,} |"
            for owner, count in top_owners
        ],
        "",
        "## Top parsed call-signature cascades",
        "",
        "| Function | Diagnostics | Files | Missing parameters | Unknown parameters |",
        "|---|---:|---:|---|---|",
        *[
            f"| `{row['function']}` | {row['diagnostics']:,} | {row['files']:,} | "
            f"`{json.dumps(row['missing'], sort_keys=True)}` | `{json.dumps(row['unknown'], sort_keys=True)}` |"
            for row in top_functions
        ],
        "",
        "## Top exact diagnostic messages",
        "",
        "| Rule | Exact description | Count |",
        "|---|---|---:|",
        *[
            f"| `{rule}` | {description.replace('|', '&#124;')} | {count:,} |"
            for (rule, description), count in top_exact_messages
        ],
        "",
        "## Method",
        "",
        "The tool validates GitLab JSON structure and derives signals only from `check_name`, "
        "`description`, and diagnostic locations. It does not read source files or import project code.",
        "",
    ]
    outputs["report.md"] = ("\n".join(report)).encode("utf-8")

    output_hashes = {name: sha256_bytes(content) for name, content in sorted(outputs.items())}
    manifest = {
        "schema": "cadrumo.ty-static-analysis-manifest.v1",
        "tool_version": TOOL_VERSION,
        "input": {"name": input_name, "sha256": input_sha256, "size_bytes": input_size},
        "ty_command": ty_command,
        "output_sha256": output_hashes,
    }
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="ty --output-format gitlab JSON file")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for deterministic reports")
    parser.add_argument("--ty-command", default=DEFAULT_TY_COMMAND, help="command that produced the dump")
    parser.add_argument("--expect-total", type=int, help="fail if the diagnostic total differs")
    parser.add_argument("--verify", action="store_true", help="byte-compare regenerated outputs without writing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.input.read_bytes()
    diagnostics = validate_and_load(raw)
    if args.expect_total is not None and len(diagnostics) != args.expect_total:
        print(f"expected {args.expect_total} diagnostics, found {len(diagnostics)}", file=sys.stderr)
        return 2
    outputs = analyze(
        diagnostics,
        input_name=args.input.name,
        input_sha256=sha256_bytes(raw),
        input_size=len(raw),
        ty_command=args.ty_command,
    )
    if args.verify:
        mismatches = []
        for name, expected in outputs.items():
            path = args.output_dir / name
            if not path.is_file() or path.read_bytes() != expected:
                mismatches.append(name)
        if mismatches:
            print(json.dumps({"status": "mismatch", "files": mismatches}, sort_keys=True))
            return 1
        print(json.dumps({"status": "verified", "outputs": len(outputs)}, sort_keys=True))
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (args.output_dir / name).write_bytes(content)
    print(json.dumps({"status": "written", "diagnostics": len(diagnostics), "outputs": len(outputs)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
