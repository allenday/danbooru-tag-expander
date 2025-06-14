"""Tests for rate limit error handling."""

import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from danbooru_tag_expander import TagExpander, RateLimitError


class TestRateLimitHandling(unittest.TestCase):
    """Test cases for rate limit error handling."""

    def setUp(self):
        """Set up the test case."""
        # Create a temporary directory for cache
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client and cache enabled
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=True,
                cache_dir=self.temp_dir
            )

    def tearDown(self):
        """Clean up after test."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pybooru_keyerror_429_raises_rate_limit_error(self):
        """Test that KeyError with '429' from pybooru bug raises RateLimitError."""
        # Mock pybooru to raise KeyError with '429' (simulating the bug)
        self.mock_client._get.side_effect = KeyError("429")
        
        # Should raise RateLimitError, not return empty results
        with self.assertRaises(RateLimitError) as context:
            self.expander.expand_tags(["test_tag"])
        
        self.assertIn("Rate limit exceeded", str(context.exception))
        self.assertIn("tags.json", str(context.exception))

    def test_rate_limit_in_exception_message_raises_rate_limit_error(self):
        """Test that exceptions with rate limit keywords raise RateLimitError."""
        # Mock pybooru to raise exception with rate limit message
        self.mock_client._get.side_effect = Exception("Too many requests - rate limit exceeded")
        
        # Should raise RateLimitError
        with self.assertRaises(RateLimitError) as context:
            self.expander.expand_tags(["test_tag"])
        
        self.assertIn("Rate limit exceeded", str(context.exception))

    def test_other_keyerror_does_not_raise_rate_limit_error(self):
        """Test that other KeyErrors don't raise RateLimitError."""
        # Mock pybooru to raise KeyError without '429'
        self.mock_client._get.side_effect = KeyError("some_other_key")
        
        # Should not raise RateLimitError, should return empty results
        expanded_tags, frequencies = self.expander.expand_tags(["test_tag"])
        
        # Should get empty results (tag marked as fetched but no relationships)
        self.assertEqual(expanded_tags, {"test_tag"})
        self.assertEqual(frequencies["test_tag"], 1)

    def test_other_exceptions_do_not_raise_rate_limit_error(self):
        """Test that other exceptions don't raise RateLimitError."""
        # Mock pybooru to raise a different exception
        self.mock_client._get.side_effect = ValueError("Invalid JSON")
        
        # Should not raise RateLimitError, should return empty results
        expanded_tags, frequencies = self.expander.expand_tags(["test_tag"])
        
        # Should get empty results (tag marked as fetched but no relationships)
        self.assertEqual(expanded_tags, {"test_tag"})
        self.assertEqual(frequencies["test_tag"], 1)

    def test_rate_limit_error_can_be_caught_by_application(self):
        """Test that applications can catch and handle RateLimitError."""
        # Mock pybooru to raise KeyError with '429'
        self.mock_client._get.side_effect = KeyError("429")
        
        # Application code should be able to catch RateLimitError
        rate_limit_caught = False
        try:
            self.expander.expand_tags(["test_tag"])
        except RateLimitError:
            rate_limit_caught = True
        except Exception:
            self.fail("Should have raised RateLimitError, not other exception")
        
        self.assertTrue(rate_limit_caught, "RateLimitError should have been raised and caught")

    def test_rate_limit_error_preserves_original_exception(self):
        """Test that RateLimitError preserves the original exception as cause."""
        # Mock pybooru to raise KeyError with '429'
        original_error = KeyError("429")
        self.mock_client._get.side_effect = original_error
        
        # Should raise RateLimitError with original as cause
        with self.assertRaises(RateLimitError) as context:
            self.expander.expand_tags(["test_tag"])
        
        self.assertIs(context.exception.__cause__, original_error)


if __name__ == '__main__':
    unittest.main() 