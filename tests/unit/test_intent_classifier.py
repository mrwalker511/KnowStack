"""Unit tests for the NL intent classifier."""
import pytest

from knowstack.nl.intent_classifier import IntentClassifier
from knowstack.retrieval.query_engine import QueryIntent


@pytest.fixture
def clf():
    return IntentClassifier()


def test_path_intent(clf):
    assert clf.classify("How does authentication flow through the app?") == QueryIntent.PATH
    assert clf.classify("path from login to database") == QueryIntent.PATH


def test_impact_intent(clf):
    assert clf.classify("What breaks if I change UserService?") == QueryIntent.IMPACT
    assert clf.classify("What depends on FeatureFlagManager?") == QueryIntent.IMPACT
    assert clf.classify("callers of authenticate") == QueryIntent.IMPACT


def test_structural_intent(clf):
    assert clf.classify("What calls the login function?") == QueryIntent.STRUCTURAL
    assert clf.classify("which files import auth?") == QueryIntent.STRUCTURAL
    assert clf.classify("where is authenticate defined?") == QueryIntent.STRUCTURAL


def test_semantic_intent(clf):
    assert clf.classify("Show me payment processing code") == QueryIntent.SEMANTIC
    assert clf.classify("retry logic implementation") == QueryIntent.SEMANTIC
