"""QA validator rule tests."""

from __future__ import annotations

from app.qa.validator import validate_spec
from tests.conftest import _words, make_spec


def test_valid_spec_passes(spec):
    result = validate_spec(spec)
    assert result.isValid, result.errors


def test_direct_answer_40_words_passes(spec):
    spec["directAnswer"] = _words(40)
    assert validate_spec(spec).isValid


def test_direct_answer_43_words_passes(spec):
    spec["directAnswer"] = _words(43)
    assert validate_spec(spec).isValid


def test_direct_answer_39_words_fails(spec):
    spec["directAnswer"] = _words(39)
    result = validate_spec(spec)
    assert not result.isValid
    assert any("40-43" in error for error in result.errors)


def test_direct_answer_44_words_fails(spec):
    spec["directAnswer"] = _words(44)
    assert not validate_spec(spec).isValid


def test_banned_string_detected(spec):
    spec["about"]["whatIs"] += " A converters tool for everyone."
    result = validate_spec(spec)
    assert any("banned string" in error for error in result.errors)


def test_placeholder_detected(spec):
    spec["h1"] = "Word Counter {name}"
    result = validate_spec(spec)
    assert any("placeholder" in error for error in result.errors)


def test_category_leak_detected(spec):
    spec["faqs"][0]["answer"] = "This text tool is free."
    result = validate_spec(spec)
    assert any("category name" in error for error in result.errors)


def test_tier1_short_whatis_fails(spec):
    spec["about"]["whatIs"] = _words(50)
    result = validate_spec(spec)
    assert any("200 words" in error for error in result.errors)


def test_faq_uniqueness_enforced(spec):
    other = make_spec()
    other["faqs"] = [{"question": item["question"], "answer": "x"} for item in spec["faqs"]]
    result = validate_spec(spec, other_specs=[other])
    assert any("uniqueness" in error for error in result.errors)


def test_example_output_verified(spec):
    spec["example"][0]["output"] = "999"
    result = validate_spec(spec)
    assert any("example[1]" in error for error in result.errors)


def test_related_tool_registry_checked(spec):
    spec["relatedTools"] = ["not-registered"]
    result = validate_spec(spec, registry=["word-counter"])
    assert any("not in registry" in error for error in result.errors)


def test_warnings_do_not_block(spec):
    spec["seo"]["title"] = "Short"
    result = validate_spec(spec)
    assert not result.isValid
    assert any("50-60" in error for error in result.errors)
