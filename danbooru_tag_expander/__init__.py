"""Danbooru Tag Expander Package."""

import logging

__version__ = "0.2.0" 

# Define the package logger and add a NullHandler
# This prevents 'No handler found' warnings if the library is used
# by an application that doesn't configure logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Import the main class to make it available at the package level
from .utils.tag_expander import TagExpander 

# Define __all__ to control imports with '*', making TagExpander public
__all__ = ["TagExpander"]
