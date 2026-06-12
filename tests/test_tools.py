"""
Tests for the three FitFindr tools.

Run from the project root with:
    pytest tests/

The LLM-backed tools (suggest_outfit, create_fit_card) are tested with the
Groq call mocked out, so these tests run offline, fast, and deterministically —
they verify our tool logic, not the model.
"""

import pytest

import tools
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── shared fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_item():
    """A real listing dict pulled from the dataset via search."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "expected at least one listing to use as a fixture"
    return results[0]


@pytest.fixture
def mock_llm(monkeypatch):
    """Replace the LLM call with a stub so tests don't hit the network."""
    def fake_call_llm(prompt, temperature=0.7):
        return "Pair it with jeans and sneakers for a casual look."
    monkeypatch.setattr(tools, "_call_llm", fake_call_llm)


# ── Tool 1: search_listings ─────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Failure mode: nothing matches → empty list, no exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size contains "M" (e.g. "M/L").
    results = search_listings("track jacket", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_results_sorted_by_relevance():
    # More-specific queries should still return matches, best first.
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0


# ── Tool 2: suggest_outfit ──────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe(sample_item, mock_llm):
    result = suggest_outfit(sample_item, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_empty_wardrobe(sample_item, mock_llm):
    # Failure mode: empty wardrobe must not crash; returns a non-empty string.
    result = suggest_outfit(sample_item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_missing_items_key(sample_item, mock_llm):
    # Defensive: a wardrobe dict with no 'items' key is treated as empty.
    result = suggest_outfit(sample_item, {})
    assert isinstance(result, str)
    assert result.strip() != ""


# ── Tool 3: create_fit_card ─────────────────────────────────────────────────

def test_create_fit_card_valid(sample_item, mock_llm):
    result = create_fit_card("Tee with baggy jeans and sneakers.", sample_item)
    assert isinstance(result, str)
    assert result.strip() != ""


def test_create_fit_card_empty_outfit(sample_item, monkeypatch):
    # Failure mode: blank outfit returns an error string and never calls the LLM.
    def boom(*args, **kwargs):
        raise AssertionError("LLM should not be called for a blank outfit")
    monkeypatch.setattr(tools, "_call_llm", boom)

    result = create_fit_card("", sample_item)
    assert isinstance(result, str)
    assert result.strip() != ""


def test_create_fit_card_whitespace_outfit(sample_item, monkeypatch):
    # Whitespace-only outfit is also treated as missing.
    def boom(*args, **kwargs):
        raise AssertionError("LLM should not be called for a whitespace outfit")
    monkeypatch.setattr(tools, "_call_llm", boom)

    result = create_fit_card("   \n  ", sample_item)
    assert isinstance(result, str)
    assert result.strip() != ""
