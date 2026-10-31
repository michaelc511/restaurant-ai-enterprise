"""F23-style unit tests for F12's domain pack loader - core/domain.py - and the restaurant pack it
loads by default. No API key or network."""
import pytest

from core.domain import available_domains, domain, load_domain


def test_default_domain_is_restaurant():
    assert domain.NAME == "restaurant"
    assert domain.COLLECTIONS == ["sushi", "steak", "italian"]


def test_every_collection_has_a_doc_and_an_eval_fixture():
    for collection in domain.COLLECTIONS:
        assert (domain.DOCS_DIR / f"{collection}.pdf").exists()
        assert (domain.EVALS_DIR / f"{collection}.json").exists()


def test_pack_defines_everything_the_engines_read():
    for name in ("RAG_PERSONA", "SYNTHESIZE_PERSONA", "ROUTE_QUESTION", "PLAN_PROMPT", "MCP_AGENT_PROMPT",
                 "OFF_TOPIC_MESSAGE", "INTENT_LABELS", "INTENT_DESCRIPTION", "INTENT_PROMPT"):
        assert getattr(domain, name)
    assert "off_topic" in domain.INTENT_LABELS  # core.guardrails.is_off_topic() relies on this label


def test_available_domains_lists_restaurant():
    assert available_domains() == ["hr", "restaurant"]


def test_unknown_domain_raises_with_the_available_choices():
    with pytest.raises(ValueError, match=r"Unknown domain: nope\. Choose one of \['hr', 'restaurant'"):
        load_domain("nope")


def test_hr_pack_loads_with_its_own_docs_and_fixtures():
    hr = load_domain("hr")

    assert hr.NAME == "hr"
    assert hr.COLLECTIONS == ["engineering", "sales", "operations"]
    for collection in hr.COLLECTIONS:
        assert (hr.DOCS_DIR / f"{collection}.pdf").exists()
        assert (hr.EVALS_DIR / f"{collection}.json").exists()
    assert "off_topic" in hr.INTENT_LABELS
    assert hr.SPECIALS_KEYWORDS == () and hr.HOURS_KEYWORDS == ()  # no restaurant specials/hours routing


def test_every_pack_defines_the_same_settings_as_restaurant():
    restaurant = load_domain("restaurant")
    settings = {n for n in vars(restaurant) if n.isupper()}
    for name in available_domains():
        assert settings <= {n for n in vars(load_domain(name)) if n.isupper()}, name
