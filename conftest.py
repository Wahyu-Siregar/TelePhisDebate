"""Pytest configuration for TelePhisDebate."""

import os

import pytest


def _integration_enabled() -> bool:
    value = os.getenv("RUN_INTEGRATION_TESTS", "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def pytest_collection_modifyitems(config, items):
    """Skip integration tests by default unless explicitly enabled."""
    if _integration_enabled():
        return

    skip_integration = pytest.mark.skip(
        reason="integration test disabled (set RUN_INTEGRATION_TESTS=1 to enable)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
