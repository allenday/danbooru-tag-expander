"""Tests specifically for deprecated tag filtering functionality."""

import unittest
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tag_expander import TagExpander


class TestDeprecatedTagFiltering(unittest.TestCase):
    """Test cases specifically for deprecated tag filtering functionality."""

    def setUp(self):
        """Set up the test case."""
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(username="test", api_key="test", use_cache=False)

    def test_bug_report_issue_1_aqua_footwear_deprecated(self):
        """Test the specific bug case: aqua_footwear should be filtered out as deprecated."""
        # Mock the API response for aqua_footwear showing it's deprecated
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and params.get("search[name]") == "aqua_footwear":
                return [{"name": "aqua_footwear", "is_deprecated": True}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test that the tag is correctly identified as deprecated
        is_deprecated = self.expander.is_tag_deprecated("aqua_footwear")
        self.assertTrue(is_deprecated)
        
        # Test that get_tag_implications skips deprecated tag
        implications = self.expander.get_tag_implications("aqua_footwear")
        self.assertEqual(implications, [])
        
        # Test that get_tag_aliases skips deprecated tag
        aliases = self.expander.get_tag_aliases("aqua_footwear")
        self.assertEqual(aliases, [])

    def test_bug_report_issue_2_aqua_gloves_not_deprecated(self):
        """Test the specific bug case: aqua_gloves should not be filtered out."""
        # Mock the API responses for aqua_gloves
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and params.get("search[name]") == "aqua_gloves":
                return [{"name": "aqua_gloves", "is_deprecated": False}]
            elif endpoint == "tag_implications.json" and params.get("search[antecedent_name]") == "aqua_gloves":
                # Mock that aqua_gloves implies gloves
                return [{"antecedent_name": "aqua_gloves", "consequent_name": "gloves", "status": "active"}]
            elif endpoint == "tags.json" and params.get("search[name]") == "gloves":
                return [{"name": "gloves", "is_deprecated": False}]
            elif endpoint == "tags.json" and params.get("search[name_matches]") == "aqua_gloves":
                return [{"name": "aqua_gloves", "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test that the tag is correctly identified as not deprecated
        is_deprecated = self.expander.is_tag_deprecated("aqua_gloves")
        self.assertFalse(is_deprecated)
        
        # Test that get_tag_implications returns the expected implication
        implications = self.expander.get_tag_implications("aqua_gloves")
        self.assertEqual(implications, ["gloves"])
        
        # Test that get_tag_aliases works (returns empty in this case)
        aliases = self.expander.get_tag_aliases("aqua_gloves")
        self.assertEqual(aliases, [])

    def test_expand_tags_mixed_deprecated_and_valid(self):
        """Test expand_tags with a mix of deprecated and valid tags."""
        # Mock API responses
        def mock_api_request(endpoint, params):
            tag_name = params.get("search[name]") or params.get("search[antecedent_name]") or params.get("search[name_matches]")
            
            if endpoint == "tags.json" and "search[name]" in params:
                # Check deprecation status
                if tag_name == "deprecated_tag":
                    return [{"name": "deprecated_tag", "is_deprecated": True}]
                elif tag_name in ["valid_tag1", "valid_tag2", "gloves"]:
                    return [{"name": tag_name, "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                # Mock implications
                if tag_name == "valid_tag1":
                    return [{"antecedent_name": "valid_tag1", "consequent_name": "gloves", "status": "active"}]
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                # Mock aliases (none in this test)
                return [{"name": tag_name, "consequent_aliases": []}]
            
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test expand_tags with mixed input
        tags = ["valid_tag1", "deprecated_tag", "valid_tag2"]
        expanded_tags, frequency = self.expander.expand_tags(tags)
        
        # Should only include valid tags and their implications
        expected_tags = {"valid_tag1", "valid_tag2", "gloves"}
        expected_frequency = Counter({
            "valid_tag1": 1,
            "valid_tag2": 1, 
            "gloves": 1  # From valid_tag1 implication
        })
        
        self.assertEqual(expanded_tags, expected_tags)
        self.assertEqual(frequency, expected_frequency)

    def test_implications_to_deprecated_tags_filtered(self):
        """Test that implications pointing to deprecated tags are filtered out."""
        def mock_api_request(endpoint, params):
            tag_name = params.get("search[name]") or params.get("search[antecedent_name]")
            
            if endpoint == "tags.json" and "search[name]" in params:
                if tag_name == "source_tag":
                    return [{"name": "source_tag", "is_deprecated": False}]
                elif tag_name == "deprecated_target":
                    return [{"name": "deprecated_target", "is_deprecated": True}]
                elif tag_name == "valid_target":
                    return [{"name": "valid_target", "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                if tag_name == "source_tag":
                    return [
                        {"antecedent_name": "source_tag", "consequent_name": "deprecated_target", "status": "active"},
                        {"antecedent_name": "source_tag", "consequent_name": "valid_target", "status": "active"}
                    ]
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                return [{"name": tag_name, "consequent_aliases": []}]
            
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test that only non-deprecated implications are returned
        implications = self.expander.get_tag_implications("source_tag")
        self.assertEqual(implications, ["valid_target"])

    def test_aliases_with_deprecated_tags_filtered(self):
        """Test that deprecated aliases are filtered out."""
        def mock_api_request(endpoint, params):
            tag_name = params.get("search[name]") or params.get("search[name_matches]")
            
            if endpoint == "tags.json" and "search[name]" in params:
                if tag_name == "main_tag":
                    return [{"name": "main_tag", "is_deprecated": False}]
                elif tag_name == "deprecated_alias":
                    return [{"name": "deprecated_alias", "is_deprecated": True}]
                elif tag_name == "valid_alias":
                    return [{"name": "valid_alias", "is_deprecated": False}]
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                if tag_name == "main_tag":
                    return [{
                        "name": "main_tag",
                        "consequent_aliases": [
                            {"antecedent_name": "deprecated_alias", "status": "active"},
                            {"antecedent_name": "valid_alias", "status": "active"}
                        ]
                    }]
            
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test that only non-deprecated aliases are returned
        aliases = self.expander.get_tag_aliases("main_tag")
        self.assertEqual(aliases, ["valid_alias"])

    def test_colored_gloves_pattern_consistency(self):
        """Test that colored gloves tags behave consistently (addressing the bug report pattern)."""
        # Mock API responses for various colored gloves
        def mock_api_request(endpoint, params):
            tag_name = params.get("search[name]") or params.get("search[antecedent_name]") or params.get("search[name_matches]")
            
            if endpoint == "tags.json" and "search[name]" in params:
                # All gloves colors are not deprecated
                if tag_name in ["red_gloves", "blue_gloves", "green_gloves", "aqua_gloves", "gloves"]:
                    return [{"name": tag_name, "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                # All colored gloves imply gloves
                if tag_name in ["red_gloves", "blue_gloves", "green_gloves", "aqua_gloves"]:
                    return [{"antecedent_name": tag_name, "consequent_name": "gloves", "status": "active"}]
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                # No aliases for simplicity
                return [{"name": tag_name, "consequent_aliases": []}]
            
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test each colored gloves tag
        for color in ["red", "blue", "green", "aqua"]:
            tag = f"{color}_gloves"
            
            # Should not be deprecated
            self.assertFalse(self.expander.is_tag_deprecated(tag))
            
            # Should have gloves implication
            implications = self.expander.get_tag_implications(tag)
            self.assertEqual(implications, ["gloves"], f"Failed for {tag}")

    def test_cache_not_created_for_deprecated_tags(self):
        """Test that cache files are not created for deprecated tags when caching is enabled."""
        # Create expander with caching enabled
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(username="test", api_key="test", use_cache=True, cache_dir="/tmp/test_cache")
        
        # Mock API response for deprecated tag
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and params.get("search[name]") == "deprecated_tag":
                return [{"name": "deprecated_tag", "is_deprecated": True}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Mock os.path.exists to return False (no cache file exists)
        # Mock open and json.dump to track if cache write is attempted
        with patch('os.path.exists', return_value=False):
            with patch('builtins.open') as mock_open:
                with patch('json.dump') as mock_json_dump:
                    # Try to get implications for deprecated tag
                    implications = expander.get_tag_implications("deprecated_tag")
                    
                    # Should return empty list
                    self.assertEqual(implications, [])
                    
                    # Cache file should not be written
                    mock_open.assert_not_called()
                    mock_json_dump.assert_not_called()

    def test_performance_early_exit_for_deprecated_tags(self):
        """Test that deprecated tags are detected early to avoid unnecessary API calls."""
        call_count = {"count": 0}
        
        def mock_api_request(endpoint, params):
            call_count["count"] += 1
            if endpoint == "tags.json" and params.get("search[name]") == "deprecated_tag":
                return [{"name": "deprecated_tag", "is_deprecated": True}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Get implications for deprecated tag
        implications = self.expander.get_tag_implications("deprecated_tag")
        
        # Should return early with empty list
        self.assertEqual(implications, [])
        
        # Should only make one API call (for deprecation check)
        self.assertEqual(call_count["count"], 1)

    def test_edge_case_empty_input_with_deprecated_filtering(self):
        """Test edge case of empty input after filtering deprecated tags."""
        with patch.object(self.expander, 'is_tag_deprecated', return_value=True):
            # All input tags are deprecated
            expanded_tags, frequency = self.expander.expand_tags(["dep1", "dep2"])
            
            # Should return empty results
            self.assertEqual(expanded_tags, set())
            self.assertEqual(frequency, Counter())


if __name__ == "__main__":
    unittest.main() 