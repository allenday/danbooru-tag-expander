#!/usr/bin/env python3
"""Tests for core tag expansion functionality."""

import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tag_expander import TagExpander
from danbooru_tag_graph import DanbooruTagGraph


class TestTagExpansion(unittest.TestCase):
    """Test cases for core tag expansion functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = MagicMock()
        
        # Create a test graph with various relationships
        self.test_graph = DanbooruTagGraph()
        
        # Add tags with different statuses
        self.test_graph.add_tag("1girl", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("female", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("solo", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("1boy", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("male", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("old_tag", is_deprecated=True, fetched=True)
        self.test_graph.add_tag("new_tag", is_deprecated=False, fetched=True)
        
        # Add implications
        self.test_graph.add_implication("1girl", "female")
        self.test_graph.add_implication("1boy", "male")
        
        # Add aliases
        self.test_graph.add_alias("old_tag", "new_tag")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_expand_tags_basic(self):
        """Test basic tag expansion with implications."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags(["1girl", "solo"])
            
            # Check expanded tags
            expected_tags = {"1girl", "female", "solo"}
            self.assertEqual(expanded, expected_tags)
            
            # Check frequencies
            self.assertEqual(frequencies["1girl"], 1)  # Original tag
            self.assertEqual(frequencies["female"], 1)  # Implied by 1girl
            self.assertEqual(frequencies["solo"], 1)    # Original tag

    def test_expand_tags_with_aliases(self):
        """Test tag expansion with aliases."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags(["old_tag"])
            
            # Should replace old_tag with new_tag
            expected_tags = {"new_tag"}
            self.assertEqual(expanded, expected_tags)
            
            # Both tags should have same frequency
            self.assertEqual(frequencies["new_tag"], 1)

    def test_expand_tags_complex_chain(self):
        """Test tag expansion with complex chains of implications and aliases."""
        # Add more complex relationships to test graph
        self.test_graph.add_tag("complex_old", is_deprecated=True, fetched=True)
        self.test_graph.add_tag("complex_new", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("implied1", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("implied2", is_deprecated=False, fetched=True)
        
        self.test_graph.add_alias("complex_old", "complex_new")
        self.test_graph.add_implication("complex_new", "implied1")
        self.test_graph.add_implication("implied1", "implied2")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags(["complex_old"])
            
            # Should follow complete chain
            expected_tags = {"complex_new", "implied1", "implied2"}
            self.assertEqual(expanded, expected_tags)
            
            # Check frequencies
            self.assertEqual(frequencies["complex_new"], 1)
            self.assertEqual(frequencies["implied1"], 1)
            self.assertEqual(frequencies["implied2"], 1)

    def test_expand_tags_multiple_paths(self):
        """Test tag expansion with multiple paths to same tag."""
        # Create a diamond pattern: A -> B -> D and A -> C -> D
        self.test_graph.add_tag("A", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("B", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("C", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("D", is_deprecated=False, fetched=True)
        
        self.test_graph.add_implication("A", "B")
        self.test_graph.add_implication("B", "D")
        self.test_graph.add_implication("A", "C")
        self.test_graph.add_implication("C", "D")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags(["A"])
            
            # Should include all tags in paths
            expected_tags = {"A", "B", "C", "D"}
            self.assertEqual(expanded, expected_tags)
            
            # D should have frequency 2 (reached through two paths)
            self.assertEqual(frequencies["D"], 2)

    def test_expand_tags_no_cache(self):
        """Test tag expansion without cache."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Mock API responses
            expander._fetch_tag_implications = MagicMock(return_value=["implied_tag"])
            expander._fetch_tag_aliases = MagicMock(return_value=[])
            expander._fetch_tag_deprecated_status = MagicMock(return_value=False)
            
            expanded, frequencies = expander.expand_tags(["test_tag"])
            
            expected_tags = {"test_tag", "implied_tag"}
            self.assertEqual(expanded, expected_tags)
            
            # Verify API methods were called
            expander._fetch_tag_implications.assert_called_with("test_tag")
            expander._fetch_tag_aliases.assert_called_with("test_tag")

    def test_expand_tags_empty_input(self):
        """Test tag expansion with empty input."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags([])
            
            self.assertEqual(expanded, set())
            self.assertEqual(frequencies, Counter())

    def test_expand_tags_unknown_tag(self):
        """Test tag expansion with unknown tag."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            # Add unknown tag to graph but don't fetch its relationships
            self.test_graph.add_tag("unknown_tag", is_deprecated=False, fetched=False)
            
            expanded, frequencies = expander.expand_tags(["unknown_tag"])
            
            # Should only include the original tag
            self.assertEqual(expanded, {"unknown_tag"})
            self.assertEqual(frequencies["unknown_tag"], 1)

    def test_expand_tags_mixed_known_unknown(self):
        """Test tag expansion with mix of known and unknown tags."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            # Add unknown tag to graph but don't fetch its relationships
            self.test_graph.add_tag("unknown_tag", is_deprecated=False, fetched=False)
            
            expanded, frequencies = expander.expand_tags(["1girl", "unknown_tag"])
            
            # Should expand known tag but keep unknown tag as is
            expected_tags = {"1girl", "female", "unknown_tag"}
            self.assertEqual(expanded, expected_tags)
            
            self.assertEqual(frequencies["1girl"], 1)
            self.assertEqual(frequencies["female"], 1)
            self.assertEqual(frequencies["unknown_tag"], 1)

    def test_expand_tags_duplicate_input(self):
        """Test tag expansion with duplicate input tags."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            expanded, frequencies = expander.expand_tags(["1girl", "1girl", "solo"])
            
            # Should handle duplicates correctly
            expected_tags = {"1girl", "female", "solo"}
            self.assertEqual(expanded, expected_tags)
            
            # Frequencies should reflect duplicates
            self.assertEqual(frequencies["1girl"], 2)
            self.assertEqual(frequencies["female"], 2)  # Implied twice
            self.assertEqual(frequencies["solo"], 1)


if __name__ == '__main__':
    unittest.main() 