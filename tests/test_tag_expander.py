"""Tests for the TagExpander class."""

import unittest
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tag_expander.utils.tag_expander import TagExpander


class TestTagExpander(unittest.TestCase):
    """Test cases for the TagExpander class."""

    def setUp(self):
        """Set up the test case."""
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(username="test", api_key="test", use_cache=False)

    def test_get_tag_implications(self):
        """Test the get_tag_implications method."""
        # Set up the mock response
        mock_response = [
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag1", "status": "active"},
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag2", "status": "active"}
        ]
        self.mock_client._get.return_value = mock_response
        
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
            "animal": 3    # 1 from cat + 1 from feline (alias of cat) + 1 from kitten->cat->animal
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