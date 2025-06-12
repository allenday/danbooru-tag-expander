"""Tests for the TagExpander class."""

import unittest
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tag_expander import TagExpander


class TestTagExpander(unittest.TestCase):
    """Test cases for the TagExpander class."""

    def setUp(self):
        """Set up the test case."""
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(username="test", api_key="test", use_cache=False)

    def test_is_tag_deprecated_true(self):
        """Test is_tag_deprecated method for a deprecated tag."""
        # Set up the mock response for a deprecated tag
        mock_response = [{"name": "aqua_footwear", "is_deprecated": True}]
        self.mock_client._get.return_value = mock_response
        
        # Call the method
        is_deprecated = self.expander.is_tag_deprecated("aqua_footwear")
        
        # Check that the API was called correctly
        self.mock_client._get.assert_called_once_with(
            "tags.json", {"search[name]": "aqua_footwear", "only": "name,is_deprecated"}
        )
        
        # Check the result
        self.assertTrue(is_deprecated)

    def test_is_tag_deprecated_false(self):
        """Test is_tag_deprecated method for a non-deprecated tag."""
        # Set up the mock response for a non-deprecated tag
        mock_response = [{"name": "aqua_gloves", "is_deprecated": False}]
        self.mock_client._get.return_value = mock_response
        
        # Call the method
        is_deprecated = self.expander.is_tag_deprecated("aqua_gloves")
        
        # Check that the API was called correctly
        self.mock_client._get.assert_called_once_with(
            "tags.json", {"search[name]": "aqua_gloves", "only": "name,is_deprecated"}
        )
        
        # Check the result
        self.assertFalse(is_deprecated)

    def test_is_tag_deprecated_missing_field(self):
        """Test is_tag_deprecated method when is_deprecated field is missing."""
        # Set up the mock response without is_deprecated field
        mock_response = [{"name": "some_tag"}]
        self.mock_client._get.return_value = mock_response
        
        # Call the method
        is_deprecated = self.expander.is_tag_deprecated("some_tag")
        
        # Check the result (should default to False)
        self.assertFalse(is_deprecated)

    def test_is_tag_deprecated_tag_not_found(self):
        """Test is_tag_deprecated method when tag is not found."""
        # Set up the mock response for tag not found
        mock_response = []
        self.mock_client._get.return_value = mock_response
        
        # Call the method
        is_deprecated = self.expander.is_tag_deprecated("nonexistent_tag")
        
        # Check the result (should default to False)
        self.assertFalse(is_deprecated)

    def test_is_tag_deprecated_api_error(self):
        """Test is_tag_deprecated method when API throws an error."""
        # Set up the mock to raise an exception
        self.mock_client._get.side_effect = Exception("API Error")
        
        # Call the method
        is_deprecated = self.expander.is_tag_deprecated("error_tag")
        
        # Check the result (should default to False for safety)
        self.assertFalse(is_deprecated)

    def test_get_tag_implications_skips_deprecated_tag(self):
        """Test that get_tag_implications skips deprecated tags."""
        # Mock is_tag_deprecated to return True for the input tag
        with patch.object(self.expander, 'is_tag_deprecated', return_value=True):
            # Call the method
            implications = self.expander.get_tag_implications("deprecated_tag")
            
            # Check that no API call was made and empty list is returned
            self.mock_client._get.assert_not_called()
            self.assertEqual(implications, [])

    def test_get_tag_implications_filters_deprecated_consequents(self):
        """Test that get_tag_implications filters out deprecated consequent tags."""
        # Set up the mock response with mixed deprecated/non-deprecated implications
        mock_response = [
            {"antecedent_name": "test_tag", "consequent_name": "valid_tag", "status": "active"},
            {"antecedent_name": "test_tag", "consequent_name": "deprecated_tag", "status": "active"}
        ]
        self.mock_client._get.return_value = mock_response
        
        # Mock is_tag_deprecated to return False for input and valid_tag, True for deprecated_tag
        def mock_deprecated_check(tag):
            return tag == "deprecated_tag"
        
        with patch.object(self.expander, 'is_tag_deprecated', side_effect=mock_deprecated_check):
            # Call the method
            implications = self.expander.get_tag_implications("test_tag")
            
            # Check that only the valid tag is returned
            self.assertEqual(implications, ["valid_tag"])

    def test_get_tag_aliases_skips_deprecated_tag(self):
        """Test that get_tag_aliases skips deprecated tags."""
        # Mock is_tag_deprecated to return True for the input tag
        with patch.object(self.expander, 'is_tag_deprecated', return_value=True):
            # Call the method
            aliases = self.expander.get_tag_aliases("deprecated_tag")
            
            # Check that no API call was made and empty list is returned
            self.mock_client._get.assert_not_called()
            self.assertEqual(aliases, [])

    def test_get_tag_aliases_filters_deprecated_aliases(self):
        """Test that get_tag_aliases filters out deprecated alias tags."""
        # Set up the mock response with mixed deprecated/non-deprecated aliases
        mock_response = [{
            "name": "test_tag",
            "consequent_aliases": [
                {"antecedent_name": "valid_alias", "status": "active"},
                {"antecedent_name": "deprecated_alias", "status": "active"}
            ]
        }]
        self.mock_client._get.return_value = mock_response
        
        # Mock is_tag_deprecated to return False for input and valid_alias, True for deprecated_alias
        def mock_deprecated_check(tag):
            return tag == "deprecated_alias"
        
        with patch.object(self.expander, 'is_tag_deprecated', side_effect=mock_deprecated_check):
            # Call the method
            aliases = self.expander.get_tag_aliases("test_tag")
            
            # Check that only the valid alias is returned
            self.assertEqual(aliases, ["valid_alias"])

    def test_expand_tags_filters_deprecated_input_tags(self):
        """Test that expand_tags filters out deprecated tags from input."""
        # Mock is_tag_deprecated to return True for deprecated_tag, False for others
        def mock_deprecated_check(tag):
            return tag == "deprecated_tag"
        
        def mock_get_tag_implications(tag):
            return []  # No implications for simplicity
        
        def mock_get_tag_aliases(tag):
            return []  # No aliases for simplicity
        
        with patch.object(self.expander, 'is_tag_deprecated', side_effect=mock_deprecated_check):
            with patch.object(self.expander, 'get_tag_implications', side_effect=mock_get_tag_implications):
                with patch.object(self.expander, 'get_tag_aliases', side_effect=mock_get_tag_aliases):
                    # Call the method with mixed tags
                    tags = ["valid_tag", "deprecated_tag", "another_valid_tag"]
                    expanded_tags, frequency = self.expander.expand_tags(tags)
                    
                    # Check that deprecated tag is filtered out
                    expected_tags = {"valid_tag", "another_valid_tag"}
                    expected_frequency = Counter({"valid_tag": 1, "another_valid_tag": 1})
                    
                    self.assertEqual(expanded_tags, expected_tags)
                    self.assertEqual(frequency, expected_frequency)

    def test_expand_tags_all_deprecated_input_tags(self):
        """Test that expand_tags handles all deprecated input tags gracefully."""
        # Mock is_tag_deprecated to return True for all tags
        with patch.object(self.expander, 'is_tag_deprecated', return_value=True):
            # Call the method with all deprecated tags
            tags = ["deprecated_tag1", "deprecated_tag2"]
            expanded_tags, frequency = self.expander.expand_tags(tags)
            
            # Check that empty results are returned
            self.assertEqual(expanded_tags, set())
            self.assertEqual(frequency, Counter())

    def test_get_tag_implications(self):
        """Test the get_tag_implications method."""
        # Set up the mock response
        mock_response = [
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag1", "status": "active"},
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag2", "status": "active"}
        ]
        self.mock_client._get.return_value = mock_response
        
        # Mock is_tag_deprecated to return False (no deprecated tags)
        with patch.object(self.expander, 'is_tag_deprecated', return_value=False):
            # Call the method
            implications = self.expander.get_tag_implications("test_tag")
            
            # Check that the API was called correctly
            self.mock_client._get.assert_called_once_with(
                "tag_implications.json", {"search[antecedent_name]": "test_tag"}
            )
            
            # Check the result
            self.assertEqual(implications, ["implied_tag1", "implied_tag2"])

    def test_get_tag_aliases(self):
        """Test the get_tag_aliases method."""
        # Set up the mock response
        mock_response = [{
            "name": "test_tag",
            "consequent_aliases": [
                {"antecedent_name": "alias_tag1", "status": "active"},
                {"antecedent_name": "alias_tag2", "status": "active"}
            ]
        }]
        self.mock_client._get.return_value = mock_response
        
        # Mock is_tag_deprecated to return False (no deprecated tags)
        with patch.object(self.expander, 'is_tag_deprecated', return_value=False):
            # Call the method
            aliases = self.expander.get_tag_aliases("test_tag")
            
            # Check that the API was called correctly
            self.mock_client._get.assert_called_once_with(
                "tags.json", {"search[name_matches]": "test_tag", "only": "name,consequent_aliases"}
            )
            
            # Check the result
            self.assertEqual(aliases, ["alias_tag1", "alias_tag2"])

    def test_expand_tags_with_aliases_and_implications(self):
        """Test that aliases share frequencies while implications sum."""
        def mock_get_tag_implications(tag):
            implications = {
                "cat": ["animal"],
                "kitten": ["cat"],
                "feline": ["animal"]
            }
            return implications.get(tag, [])
        
        def mock_get_tag_aliases(tag):
            aliases = {
                "cat": ["feline"],
                "feline": ["cat"]
            }
            return aliases.get(tag, [])
        
        # Mock is_tag_deprecated to return False (no deprecated tags)
        with patch.object(self.expander, 'is_tag_deprecated', return_value=False):
            # Mock the method calls
            self.expander.get_tag_implications = MagicMock(side_effect=mock_get_tag_implications)
            self.expander.get_tag_aliases = MagicMock(side_effect=mock_get_tag_aliases)
            
            # Call the method with initial tags
            tags = ["cat", "kitten"]
            expanded_tags, frequency = self.expander.expand_tags(tags)
            
            # Expected results
            expected_tags = {"cat", "feline", "kitten", "animal"}
            expected_frequency = Counter({
                "cat": 2,      # 1 from original + 1 from kitten implication
                "feline": 2,   # Same as cat (they're aliases)
                "kitten": 1,   # Just from original tag
                "animal": 2    # 1 from cat implication + 1 from feline implication (alias of cat)
            })
            
            # Check the results
            self.assertEqual(expanded_tags, expected_tags)
            self.assertEqual(frequency, expected_frequency)

    def test_expand_tags_multiple_implications(self):
        """Test that multiple implications to the same tag sum correctly."""
        def mock_get_tag_implications(tag):
            implications = {
                "A": ["X"],
                "B": ["X"],
                "C": ["X"]
            }
            return implications.get(tag, [])
        
        def mock_get_tag_aliases(tag):
            return []  # No aliases in this test
        
        # Mock is_tag_deprecated to return False (no deprecated tags)
        with patch.object(self.expander, 'is_tag_deprecated', return_value=False):
            # Mock the method calls
            self.expander.get_tag_implications = MagicMock(side_effect=mock_get_tag_implications)
            self.expander.get_tag_aliases = MagicMock(side_effect=mock_get_tag_aliases)
            
            # Call the method with initial tags
            tags = ["A", "B", "C"]
            expanded_tags, frequency = self.expander.expand_tags(tags)
            
            # Expected results
            expected_tags = {"A", "B", "C", "X"}
            expected_frequency = Counter({
                "A": 1,
                "B": 1,
                "C": 1,
                "X": 3  # Sum of all implications
            })
            
            # Check the results
            self.assertEqual(expanded_tags, expected_tags)
            self.assertEqual(frequency, expected_frequency)


if __name__ == "__main__":
    unittest.main() 