"""The benchmark keeps workload timing summaries distinct from paired semantics."""

from __future__ import annotations

import pytest

from ..indexed_authority_benchmark import _summary

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_summary_uses_backend_workload_medians_and_pairs_only_shared_semantics() -> None:
    samples: list[dict[str, object]] = [
        {
            "backend": "json",
            "workload": "modelo-100",
            "post_import_admission_and_first_seconds": 0.25,
            "incremental_authority_rss_bytes": 10,
            "warm_context_median_seconds": 0.1,
            "identity_digest": "generation-a",
            "detail": {"modelo": "100", "revision": "2025"},
        },
        {
            "backend": "json",
            "workload": "modelo-100",
            "post_import_admission_and_first_seconds": 0.35,
            "incremental_authority_rss_bytes": 30,
            "warm_context_median_seconds": 0.3,
            "identity_digest": "generation-a",
            "detail": {"modelo": "100", "revision": "2025"},
        },
        {
            "backend": "json",
            "workload": "fact",
            "post_import_admission_and_first_seconds": 1.0,
            "incremental_authority_rss_bytes": 100,
            "identity_digest": "generation-a",
            "detail": {"fact_id": "fact-a"},
        },
        {
            "backend": "json",
            "workload": "enumeration",
            "post_import_admission_and_first_seconds": 0.5,
            "incremental_authority_rss_bytes": 40,
            "identity_digest": "generation-a",
            "detail": {"modelos": 2, "revisions": 4},
        },
        {
            "backend": "sqlite",
            "workload": "modelo-100",
            "post_import_admission_and_first_seconds": 0.6,
            "incremental_authority_rss_bytes": 50,
            "warm_context_median_seconds": 0.5,
            "identity_digest": "generation-a",
            "detail": {"modelo": "100", "revision": "2025"},
        },
        {
            "backend": "sqlite",
            "workload": "modelo-100",
            "post_import_admission_and_first_seconds": 0.8,
            "incremental_authority_rss_bytes": 70,
            "warm_context_median_seconds": 0.7,
            "identity_digest": "generation-a",
            "detail": {"modelo": "100", "revision": "2025"},
        },
        {
            "backend": "sqlite",
            "workload": "fact",
            "post_import_admission_and_first_seconds": 0.9,
            "incremental_authority_rss_bytes": 110,
            "identity_digest": "generation-b",
            "detail": {"fact_id": "fact-b"},
        },
    ]

    assert _summary(samples) == {
        "json": {
            "fresh_processes": 4,
            "workloads": {
                "enumeration": {
                    "runs": 1,
                    "post_import_admission_and_first_median_seconds": 0.5,
                    "incremental_authority_rss_median_bytes": 40.0,
                },
                "fact": {
                    "runs": 1,
                    "post_import_admission_and_first_median_seconds": 1.0,
                    "incremental_authority_rss_median_bytes": 100.0,
                },
                "modelo-100": {
                    "runs": 2,
                    "post_import_admission_and_first_median_seconds": 0.3,
                    "incremental_authority_rss_median_bytes": 20.0,
                    "warm_context_median_seconds": 0.2,
                },
            },
        },
        "sqlite": {
            "fresh_processes": 3,
            "workloads": {
                "fact": {
                    "runs": 1,
                    "post_import_admission_and_first_median_seconds": 0.9,
                    "incremental_authority_rss_median_bytes": 110.0,
                },
                "modelo-100": {
                    "runs": 2,
                    "post_import_admission_and_first_median_seconds": 0.7,
                    "incremental_authority_rss_median_bytes": 60.0,
                    "warm_context_median_seconds": 0.6,
                },
            },
        },
        "paired_semantics": {
            "fact": {"identity_digest_equal": False, "operation_detail_equal": False},
            "modelo-100": {"identity_digest_equal": True, "operation_detail_equal": True},
        },
    }
