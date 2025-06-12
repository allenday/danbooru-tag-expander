"""Tests for safe filename generation and caching with problematic tag characters."""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from danbooru_tag_expander import TagExpander
import urllib.parse


class TestSafeFilenames(unittest.TestCase):
    """Test cases for safe filename generation with problematic characters."""

    def setUp(self):
        """Set up the test case."""
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a temporary directory for cache testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a TagExpander with the mock client and temp cache dir
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=True, 
                cache_dir=self.temp_dir
            )

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_safe_cache_filename_generation(self):
        """Test that safe cache filenames are generated correctly."""
        # Test cases with problematic characters
        test_cases = [
            ("simple_tag", "implications_simple_tag.json"),
            ("tag/with/slashes", "implications_tag%2Fwith%2Fslashes.json"),
            ("tag?with?question", "implications_tag%3Fwith%3Fquestion.json"),
            ("tag:with:colon", "implications_tag%3Awith%3Acolon.json"),
            ("tag<with>brackets", "implications_tag%3Cwith%3Ebrackets.json"),
            ("tag|with|pipe", "implications_tag%7Cwith%7Cpipe.json"),
            ("tag*with*asterisk", "implications_tag%2Awith%2Aasterisk.json"),
            ("tag with spaces", "implications_tag%20with%20spaces.json"),
            ("tag#with#hash", "implications_tag%23with%23hash.json"),
            ("tag&with&ampersand", "implications_tag%26with%26ampersand.json"),
        ]
        
        for tag, expected_filename in test_cases:
            with self.subTest(tag=tag):
                actual_filename = self.expander._get_safe_cache_filename('implications', tag)
                self.assertEqual(actual_filename, expected_filename)

    def test_safe_cache_filename_aliases(self):
        """Test that safe cache filenames work for aliases too."""
        tag = "tag/with/slash"
        expected_filename = "aliases_tag%2Fwith%2Fslash.json"
        actual_filename = self.expander._get_safe_cache_filename('aliases', tag)
        self.assertEqual(actual_filename, expected_filename)

    def test_caching_with_problematic_tag_names(self):
        """Test that caching works with tags containing problematic characters."""
        problematic_tag = "character/alice_(wonderland)"
        
        # Mock API responses
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and params.get("search[name]") == problematic_tag:
                return [{"name": problematic_tag, "is_deprecated": False}]
            elif endpoint == "tag_implications.json" and params.get("search[antecedent_name]") == problematic_tag:
                return [{"antecedent_name": problematic_tag, "consequent_name": "character", "status": "active"}]
            elif endpoint == "tags.json" and params.get("search[name]") == "character":
                return [{"name": "character", "is_deprecated": False}]
            elif endpoint == "tags.json" and params.get("search[name_matches]") == problematic_tag:
                return [{"name": problematic_tag, "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test implications caching
        implications = self.expander.get_tag_implications(problematic_tag)
        self.assertEqual(implications, ["character"])
        
        # Check that cache file was created with safe filename
        safe_filename = self.expander._get_safe_cache_filename('implications', problematic_tag)
        cache_file_path = os.path.join(self.temp_dir, safe_filename)
        self.assertTrue(os.path.exists(cache_file_path))
        
        # Test that we can read from the cache file
        implications_cached = self.expander.get_tag_implications(problematic_tag)
        self.assertEqual(implications_cached, ["character"])
        
        # Test aliases caching
        aliases = self.expander.get_tag_aliases(problematic_tag)
        self.assertEqual(aliases, [])
        
        # Check that aliases cache file was created
        aliases_safe_filename = self.expander._get_safe_cache_filename('aliases', problematic_tag)
        aliases_cache_file_path = os.path.join(self.temp_dir, aliases_safe_filename)
        self.assertTrue(os.path.exists(aliases_cache_file_path))

    def test_url_encoding_reversibility(self):
        """Test that URL encoding is reversible (for debugging purposes)."""
        test_tags = [
            "tag/with/slashes",
            "tag?with?question",
            "tag:with:colon",
            "tag with spaces",
            "complex/tag?with:multiple<problematic>characters|and*more",
        ]
        
        for original_tag in test_tags:
            with self.subTest(tag=original_tag):
                # Encode the tag
                encoded = urllib.parse.quote(original_tag, safe='')
                # Decode it back
                decoded = urllib.parse.unquote(encoded)
                # Should be identical to original
                self.assertEqual(original_tag, decoded)

    def test_no_filename_collisions(self):
        """Test that different tags don't create filename collisions."""
        # These tags should create different encoded filenames
        tags = [
            "tag/slash",
            "tag%2Fslash",  # This is already URL encoded
            "tag\\slash",   # Backslash
            "tag slash",    # Space
        ]
        
        filenames = set()
        for tag in tags:
            filename = self.expander._get_safe_cache_filename('implications', tag)
            # Each should be unique
            self.assertNotIn(filename, filenames, f"Collision detected for tag: {tag}")
            filenames.add(filename)

    def test_extremely_long_tag_names(self):
        """Test handling of very long tag names that might exceed filename limits."""
        # Create a very long tag name
        long_tag = "very_long_tag_name_" + "x" * 200 + "/with/slashes"
        
        # Should not raise an exception
        filename = self.expander._get_safe_cache_filename('implications', long_tag)
        
        # Should be properly encoded
        self.assertIn("%2F", filename)  # Should contain encoded slashes
        self.assertTrue(filename.startswith("implications_"))
        self.assertTrue(filename.endswith(".json"))

    def test_edge_case_empty_tag(self):
        """Test handling of edge case with empty tag name."""
        filename = self.expander._get_safe_cache_filename('implications', '')
        self.assertEqual(filename, "implications_.json")

    def test_unicode_characters_in_tags(self):
        """Test handling of Unicode characters in tag names."""
        unicode_tag = "tag_with_ñ_and_中文_characters"
        
        # Should handle Unicode properly
        filename = self.expander._get_safe_cache_filename('implications', unicode_tag)
        
        # Should be encoded
        self.assertTrue(filename.startswith("implications_"))
        self.assertTrue(filename.endswith(".json"))
        
        # Should be reversible
        encoded_part = filename[len("implications_"):-len(".json")]
        decoded = urllib.parse.unquote(encoded_part)
        self.assertEqual(decoded, unicode_tag)

    def test_backwards_compatibility_with_simple_tags(self):
        """Test that simple tags without problematic characters still work."""
        simple_tag = "simple_tag_123"
        
        # Mock API responses
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and params.get("search[name]") == simple_tag:
                return [{"name": simple_tag, "is_deprecated": False}]
            elif endpoint == "tag_implications.json" and params.get("search[antecedent_name]") == simple_tag:
                return []
            elif endpoint == "tags.json" and params.get("search[name_matches]") == simple_tag:
                return [{"name": simple_tag, "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Should work normally
        implications = self.expander.get_tag_implications(simple_tag)
        self.assertEqual(implications, [])
        
        # Should create cache file
        safe_filename = self.expander._get_safe_cache_filename('implications', simple_tag)
        cache_file_path = os.path.join(self.temp_dir, safe_filename)
        self.assertTrue(os.path.exists(cache_file_path))
        
        # For simple tags, the encoded filename should be identical to the original approach
        # (since no special characters need encoding)
        expected_simple_filename = f"implications_{simple_tag}.json"
        self.assertEqual(safe_filename, expected_simple_filename)


if __name__ == "__main__":
    unittest.main() 