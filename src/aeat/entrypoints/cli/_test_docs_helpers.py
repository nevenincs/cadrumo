"""Unit tests for :mod:`aeat.cli._docs_helpers`."""

from __future__ import annotations

import pytest

from ._docs_helpers import (
    build_append_request,
    build_replace_all_request,
    extract_plaintext,
    find_end_index,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


class TestExtractPlaintext:
    """Behaviour of ``extract_plaintext``."""

    def test_empty_document(self) -> None:
        assert extract_plaintext({}) == ""

    def test_single_paragraph(self) -> None:
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "hello world\n"}},
                            ],
                        }
                    }
                ]
            }
        }
        assert extract_plaintext(doc) == "hello world\n"

    def test_multiple_runs(self) -> None:
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "hello "}},
                                {"textRun": {"content": "world\n"}},
                            ],
                        }
                    }
                ]
            }
        }
        assert extract_plaintext(doc) == "hello world\n"

    def test_skips_non_paragraph_elements(self) -> None:
        doc = {
            "body": {
                "content": [
                    {"sectionBreak": {}},
                    {"paragraph": {"elements": [{"textRun": {"content": "kept\n"}}]}},
                    {"table": {}},
                ]
            }
        }
        assert extract_plaintext(doc) == "kept\n"

    def test_skips_runs_without_textrun(self) -> None:
        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"horizontalRule": {}},
                                {"textRun": {"content": "x\n"}},
                            ],
                        }
                    }
                ]
            }
        }
        assert extract_plaintext(doc) == "x\n"


class TestFindEndIndex:
    """Behaviour of ``find_end_index``."""

    def test_empty_body_returns_one(self) -> None:
        assert find_end_index({}) == 1

    def test_uses_last_element_end_minus_one(self) -> None:
        doc = {"body": {"content": [{"endIndex": 50}]}}
        assert find_end_index(doc) == 49

    def test_clamps_to_one_for_zero_end(self) -> None:
        doc = {"body": {"content": [{"endIndex": 1}]}}
        assert find_end_index(doc) == 1


class TestBuildRequests:
    """Behaviour of ``build_append_request`` and ``build_replace_all_request``."""

    def test_append_request_shape(self) -> None:
        result = build_append_request("hello", 42)
        assert result == [
            {"insertText": {"location": {"index": 42}, "text": "hello"}},
        ]

    def test_replace_all_request_shape(self) -> None:
        result = build_replace_all_request("foo", "bar")
        assert result == [
            {
                "replaceAllText": {
                    "containsText": {"text": "foo", "matchCase": True},
                    "replaceText": "bar",
                }
            }
        ]
