"""Test configuration and fixtures."""

import pytest
import logging

@pytest.fixture(autouse=True)
def disable_logging():
    """Disable logging for all tests."""
    logging.disable(logging.CRITICAL) 