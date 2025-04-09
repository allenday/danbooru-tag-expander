"""Tests for the TagExpander class."""

import unittest
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tools.utils.tag_expander import TagExpander


class TestTagExpander(unittest.TestCase):
    """Test cases for the TagExpander class."""

    def setUp(self):
        """Set up the test case."""
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client
        with patch('danbooru_tools.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(username="test", api_key="test", use_cache=False)
        
        # Replace the client with our mock
        self.expander.client = self.mock_client

    def test_get_tag_implications(self):
        """Test the get_tag_implications method."""
        # Set up the mock response
        self.mock_client._get.return_value = [
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag1"},
            {"antecedent_name": "test_tag", "consequent_name": "implied_tag2"}
        ]
        
        # Call the method
        implications = self.expander.get_tag_implications("test_tag")
        
        # Check that the API was called correctly
        self.mock_client._get.assert_called_once_with(
            "tag_implications", {"search[antecedent_name]": "test_tag"}
        )
        
        # Check the result
        self.assertEqual(implications, ["implied_tag1", "implied_tag2"])

    def test_get_tag_aliases(self):
        """Test the get_tag_aliases method."""
        # Set up the mock response
        self.mock_client._get.return_value = [
            {"antecedent_name": "test_tag", "consequent_name": "alias_tag1"},
            {"antecedent_name": "test_tag", "consequent_name": "alias_tag2"}
        ]
        
        # Call the method
        aliases = self.expander.get_tag_aliases("test_tag")
        
        # Check that the API was called correctly
        self.mock_client._get.assert_called_once_with(
            "tag_aliases", {"search[antecedent_name]": "test_tag"}
        )
        
        # Check the result
        self.assertEqual(aliases, ["alias_tag1", "alias_tag2"])

    def test_expand_tags(self):
        """Test the expand_tags method."""
        # Set up the mock responses
        def mock_get_tag_implications(tag):
            implications = {
                "tag1": ["implied1", "implied2"],
                "tag2": ["implied3"],
                "tag3": []
            }
            return implications.get(tag, [])
        
        def mock_get_tag_aliases(tag):
            aliases = {
                "implied1": ["alias1"],
                "implied2": ["alias2"],
                "implied3": [],
                "tag3": ["alias3"]
            }
            return aliases.get(tag, [])
        
        # Mock the method calls
        self.expander.get_tag_implications = MagicMock(side_effect=mock_get_tag_implications)
        self.expander.get_tag_aliases = MagicMock(side_effect=mock_get_tag_aliases)
        
        # Call the method
        tags = ["tag1", "tag2", "tag3"]
        expanded_tags, frequency = self.expander.expand_tags(tags)
        
        # Expected results
        expected_tags = {"tag1", "tag2", "tag3", "implied1", "implied2", "implied3", "alias1", "alias2", "alias3"}
        expected_frequency = Counter({
            "tag1": 1, "tag2": 1, "tag3": 1,
            "implied1": 1, "implied2": 1, "implied3": 1,
            "alias1": 1, "alias2": 1, "alias3": 1
        })
        
        # Check the results
        self.assertEqual(expanded_tags, expected_tags)
        self.assertEqual(frequency, expected_frequency)


if __name__ == "__main__":
    unittest.main() 