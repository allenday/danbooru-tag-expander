"""Danbooru Tag Expander Package."""

import logging

__version__ = "0.2.4" 

# Define the package logger and add a NullHandler
# This prevents 'No handler found' warnings if the library is used
# by an application that doesn't configure logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Import the main class and exceptions to make them available at the package level
from .utils.tag_expander import TagExpander, RateLimitError

# Define __all__ to control imports with '*', making TagExpander and RateLimitError public
__all__ = ["TagExpander", "RateLimitError"]
