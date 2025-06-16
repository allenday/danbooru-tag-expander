#!/usr/bin/env python3
"""Tests for error handling and edge cases in TagExpander."""

import unittest
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
from danbooru_tag_expander import TagExpander, RateLimitError
import pytest


@pytest.mark.unit
class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling and edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization_without_cache_dir(self):
        """Test initialization when no cache directory is configured."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            # No cache_dir provided and no environment variable
            with patch.dict(os.environ, {}, clear=True):
                expander = TagExpander(
                    username="test",
                    api_key="test",
                    use_cache=True,
                    cache_dir=None
                )
                
                self.assertIsNone(expander.tag_graph)
                self.assertFalse(expander.use_cache)

    def test_initialization_cache_disabled_by_configuration(self):
        """Test initialization with cache explicitly disabled."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False,
                cache_dir=self.temp_dir
            )
            
            self.assertIsNone(expander.tag_graph)
            self.assertFalse(expander.use_cache)

    def test_site_url_trailing_slash_removal(self):
        """Test that trailing slash is removed from site URL."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                site_url="https://example.com/",
                use_cache=False
            )
            
            self.assertEqual(expander.site_url, "https://example.com")

    @patch('danbooru_tag_expander.utils.tag_expander.Danbooru')
    def test_api_request_keyerror_429(self, mock_danbooru_class):
        """Test API request handling of KeyError with 429 (rate limit)."""
        mock_client = MagicMock()
        mock_danbooru_class.return_value = mock_client
        
        # Mock KeyError with "429" in the message
        mock_client._get.side_effect = KeyError("429")
        
        expander = TagExpander(
            username="test",
            api_key="test",
            use_cache=False
        )
        
        with self.assertRaises(RateLimitError) as context:
            expander._api_request("test.json", {})
        
        self.assertIn("Rate limit exceeded", str(context.exception))

    @patch('danbooru_tag_expander.utils.tag_expander.Danbooru')
    def test_api_request_keyerror_non_429(self, mock_danbooru_class):
        """Test API request handling of KeyError without 429."""
        mock_client = MagicMock()
        mock_danbooru_class.return_value = mock_client
        
        # Mock KeyError without "429" in the message
        mock_client._get.side_effect = KeyError("some other error")
        
        expander = TagExpander(
            username="test",
            api_key="test",
            use_cache=False
        )
        
        # Should return empty list, not raise exception
        result = expander._api_request("test.json", {})
        self.assertEqual(result, [])

    @patch('danbooru_tag_expander.utils.tag_expander.Danbooru')
    def test_api_request_rate_limit_in_exception_message(self, mock_danbooru_class):
        """Test API request handling of exceptions with rate limit keywords."""
        mock_client = MagicMock()
        mock_danbooru_class.return_value = mock_client
        
        # Mock exception with rate limit keywords
        mock_client._get.side_effect = Exception("too many requests")
        
        expander = TagExpander(
            username="test",
            api_key="test",
            use_cache=False
        )
        
        with self.assertRaises(RateLimitError) as context:
            expander._api_request("test.json", {})
        
        self.assertIn("Rate limit exceeded", str(context.exception))

    @patch('danbooru_tag_expander.utils.tag_expander.Danbooru')
    def test_api_request_generic_exception(self, mock_danbooru_class):
        """Test API request handling of generic exceptions."""
        mock_client = MagicMock()
        mock_danbooru_class.return_value = mock_client
        
        # Mock generic exception
        mock_client._get.side_effect = Exception("network error")
        
        expander = TagExpander(
            username="test",
            api_key="test",
            use_cache=False
        )
        
        # Should return empty list, not raise exception
        result = expander._api_request("test.json", {})
        self.assertEqual(result, [])

    def test_fetch_tag_deprecated_status_empty_response(self):
        """Test fetching deprecated status with empty API response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock empty response
            expander._api_request = MagicMock(return_value=[])
            
            result = expander._fetch_tag_deprecated_status("test_tag")
            self.assertFalse(result)

    def test_fetch_tag_deprecated_status_none_response(self):
        """Test fetching deprecated status with None response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock None response
            expander._api_request = MagicMock(return_value=None)
            
            result = expander._fetch_tag_deprecated_status("test_tag")
            self.assertFalse(result)

    def test_fetch_tag_deprecated_status_rate_limit_error(self):
        """Test fetching deprecated status with rate limit error."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock rate limit error
            expander._api_request = MagicMock(side_effect=RateLimitError("Rate limit"))
            
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_deprecated_status("test_tag")

    def test_fetch_tag_deprecated_status_generic_exception(self):
        """Test fetching deprecated status with generic exception."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock generic exception
            expander._api_request = MagicMock(side_effect=Exception("network error"))
            
            result = expander._fetch_tag_deprecated_status("test_tag")
            self.assertFalse(result)

    def test_fetch_tag_implications_empty_response(self):
        """Test fetching implications with empty API response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock empty response
            expander._api_request = MagicMock(return_value=[])
            
            result = expander._fetch_tag_implications("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_implications_none_response(self):
        """Test fetching implications with None response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock None response
            expander._api_request = MagicMock(return_value=None)
            
            result = expander._fetch_tag_implications("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_implications_rate_limit_error(self):
        """Test fetching implications with rate limit error."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock rate limit error
            expander._api_request = MagicMock(side_effect=RateLimitError("Rate limit"))
            
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_implications("test_tag")

    def test_fetch_tag_implications_generic_exception(self):
        """Test fetching implications with generic exception."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock generic exception
            expander._api_request = MagicMock(side_effect=Exception("network error"))
            
            result = expander._fetch_tag_implications("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_implications_with_deprecated_consequent(self):
        """Test fetching implications where consequent is deprecated."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock API response with implication
            expander._api_request = MagicMock(return_value=[
                {"consequent_name": "deprecated_tag", "status": "active"}
            ])
            
            # Mock deprecated status check to return True for consequent
            expander._fetch_tag_deprecated_status = MagicMock(return_value=True)
            
            result = expander._fetch_tag_implications("test_tag")
            # Should exclude deprecated consequent
            self.assertEqual(result, [])

    def test_fetch_tag_aliases_empty_response(self):
        """Test fetching aliases with empty API response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock empty response
            expander._api_request = MagicMock(return_value=[])
            
            result = expander._fetch_tag_aliases("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_aliases_none_response(self):
        """Test fetching aliases with None response."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock None response
            expander._api_request = MagicMock(return_value=None)
            
            result = expander._fetch_tag_aliases("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_aliases_rate_limit_error(self):
        """Test fetching aliases with rate limit error."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock rate limit error
            expander._api_request = MagicMock(side_effect=RateLimitError("Rate limit"))
            
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_aliases("test_tag")

    def test_fetch_tag_aliases_generic_exception(self):
        """Test fetching aliases with generic exception."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock generic exception
            expander._api_request = MagicMock(side_effect=Exception("network error"))
            
            result = expander._fetch_tag_aliases("test_tag")
            self.assertEqual(result, [])

    def test_fetch_tag_aliases_antecedent_mismatch(self):
        """Test fetching aliases with antecedent mismatch."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock API response with mismatched antecedent
            expander._api_request = MagicMock(return_value=[
                {
                    "antecedent_name": "different_tag",
                    "consequent_name": "target_tag",
                    "status": "active"
                }
            ])
            
            result = expander._fetch_tag_aliases("test_tag")
            # Should exclude mismatched antecedent
            self.assertEqual(result, [])

    def test_fetch_tag_aliases_with_deprecated_consequent(self):
        """Test fetching aliases where consequent is deprecated."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock API response with alias
            expander._api_request = MagicMock(return_value=[
                {
                    "antecedent_name": "test_tag",
                    "consequent_name": "deprecated_target",
                    "status": "active"
                }
            ])
            
            # Mock deprecated status check to return True for consequent
            expander._fetch_tag_deprecated_status = MagicMock(return_value=True)
            
            result = expander._fetch_tag_aliases("test_tag")
            # Should exclude deprecated consequent
            self.assertEqual(result, [])

    def test_batch_fetch_tags_rate_limit_error(self):
        """Test batch fetch with rate limit error."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=True,
                cache_dir=self.temp_dir
            )
            
            # Mock rate limit error during deprecated status check
            expander._fetch_tag_deprecated_status = MagicMock(side_effect=RateLimitError("Rate limit"))
            
            with self.assertRaises(RateLimitError):
                expander._batch_fetch_tags(["test_tag"])

    def test_environment_variable_fallbacks(self):
        """Test that environment variables are used as fallbacks."""
        with patch.dict(os.environ, {
            'DANBOORU_USERNAME': 'env_user',
            'DANBOORU_API_KEY': 'env_key',
            'DANBOORU_SITE_URL': 'https://env.example.com',
            'DANBOORU_CACHE_DIR': self.temp_dir
        }):
            with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
                expander = TagExpander()
                
                self.assertEqual(expander.username, 'env_user')
                self.assertEqual(expander.api_key, 'env_key')
                self.assertEqual(expander.site_url, 'https://env.example.com')
                self.assertEqual(expander.cache_dir, self.temp_dir)

    def test_explicit_parameters_override_environment(self):
        """Test that explicit parameters override environment variables."""
        with patch.dict(os.environ, {
            'DANBOORU_USERNAME': 'env_user',
            'DANBOORU_API_KEY': 'env_key',
            'DANBOORU_SITE_URL': 'https://env.example.com'
        }):
            with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
                expander = TagExpander(
                    username='explicit_user',
                    api_key='explicit_key',
                    site_url='https://explicit.example.com'
                )
                
                self.assertEqual(expander.username, 'explicit_user')
                self.assertEqual(expander.api_key, 'explicit_key')
                self.assertEqual(expander.site_url, 'https://explicit.example.com')

    def test_api_request_rate_limit_key_error(self):
        """Test that a KeyError '429' in _api_request raises RateLimitError."""
        self.mock_client._get.side_effect = KeyError("429")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            
            with self.assertRaises(RateLimitError):
                expander._api_request("tags.json", {})

    def test_api_request_rate_limit_exception(self):
        """Test that a generic exception with 'rate limit' in message raises RateLimitError."""
        self.mock_client._get.side_effect = Exception("rate limit exceeded")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            
            with self.assertRaises(RateLimitError):
                expander._api_request("tags.json", {})

    def test_api_request_other_key_error_returns_empty(self):
        """Test that other KeyErrors in _api_request return an empty list."""
        self.mock_client._get.side_effect = KeyError("some other error")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            result = expander._api_request("tags.json", {})
            self.assertEqual(result, [])

    def test_api_request_other_exception_returns_empty(self):
        """Test that other exceptions in _api_request return an empty list."""
        self.mock_client._get.side_effect = Exception("some other error")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            result = expander._api_request("tags.json", {})
            self.assertEqual(result, [])

    def test_fetch_methods_return_empty_on_error(self):
        """Test that fetch methods return empty lists on API errors."""
        self.mock_client._get.side_effect = Exception("API failure")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            
            implications = expander._fetch_tag_implications("test")
            self.assertEqual(implications, [])
            
            aliases = expander._fetch_tag_aliases("test")
            self.assertEqual(aliases, [])
            
            deprecated = expander._fetch_tag_deprecated_status("test")
            self.assertFalse(deprecated)

    def test_init_without_cache_dir(self):
        """Test that caching is disabled if no cache directory is provided or found."""
        with patch.dict('os.environ', {'DANBOORU_CACHE_DIR': ''}):
            with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
                expander = TagExpander(use_cache=True, cache_dir=None)
                self.assertFalse(expander.use_cache)
                self.assertIsNone(expander.tag_graph)

    def test_fetch_methods_raise_rate_limit(self):
        """Test that fetch methods propagate RateLimitError."""
        self.mock_client._get.side_effect = RateLimitError("rate limited")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test")
            
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_implications("test")
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_aliases("test")
            with self.assertRaises(RateLimitError):
                expander._fetch_tag_deprecated_status("test")

    def test_ensure_all_tags_fetched_handles_rate_limit(self):
        """Test that _ensure_all_tags_fetched correctly handles a RateLimitError."""
        with patch('danbooru_tag_expander.utils.tag_expander.DanbooruTagGraph') as mock_graph:
            # Setup mock graph instance
            graph_instance = mock_graph.return_value
            graph_instance.get_unfetched_tags.return_value = ["tag1"]

            with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
                expander = TagExpander(username="test", api_key="test", tag_graph=graph_instance)
                
                # Make the batch fetch raise a rate limit error
                with patch.object(expander, '_batch_fetch_tags', side_effect=RateLimitError("test limit")):
                    with self.assertRaises(RateLimitError):
                        expander._ensure_all_tags_fetched(["tag1"])

    def test_validate_alias_directionality_heuristic(self):
        """Test the alphabetical heuristic in _validate_alias_directionality."""
        with patch('danbooru_tag_expander.utils.tag_expander.DanbooruTagGraph') as mock_graph:
            graph_instance = mock_graph.return_value
            
            # Setup graph to have a bidirectional alias and same deprecation status
            graph_instance.graph.edges.return_value = [('b', 'a', {'edge_type': 'alias'}), ('a', 'b', {'edge_type': 'alias'})]
            graph_instance.is_tag_deprecated.return_value = False

            with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
                expander = TagExpander(username="test", api_key="test", tag_graph=graph_instance)
                expander._validate_alias_directionality()

                # 'b' should point to 'a' based on alphabetical heuristic
                graph_instance.add_alias.assert_called_once_with('b', 'a')


if __name__ == '__main__':
    unittest.main() 