#!/usr/bin/env python3
"""Tests for semantic relationship methods in TagExpander."""

import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from danbooru_tag_expander import TagExpander
from danbooru_tag_graph import DanbooruTagGraph


class TestSemanticRelationships(unittest.TestCase):
    """Test cases for semantic relationship methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = MagicMock()
        
        # Create a test graph with various relationships
        self.test_graph = DanbooruTagGraph()
        
        # Add tags with different statuses
        self.test_graph.add_tag("canonical_tag", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("deprecated_tag", is_deprecated=True, fetched=True)
        self.test_graph.add_tag("another_deprecated", is_deprecated=True, fetched=True)
        self.test_graph.add_tag("implied_tag", is_deprecated=False, fetched=True)
        self.test_graph.add_tag("transitive_tag", is_deprecated=False, fetched=True)
        
        # Add relationships
        self.test_graph.add_alias("deprecated_tag", "canonical_tag")  # deprecated -> canonical
        self.test_graph.add_alias("another_deprecated", "canonical_tag")  # another -> canonical
        self.test_graph.add_implication("canonical_tag", "implied_tag")  # canonical -> implied
        self.test_graph.add_implication("implied_tag", "transitive_tag")  # implied -> transitive

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_aliased_from_include_deprecated_true(self):
        """Test get_aliased_from with include_deprecated=True (default)."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            # Should get all incoming aliases
            aliased_from = expander.get_aliased_from("canonical_tag")
            self.assertEqual(set(aliased_from), {"deprecated_tag", "another_deprecated"})

    def test_get_aliased_from_include_deprecated_false(self):
        """Test get_aliased_from with include_deprecated=False."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            # Should get no aliases since all antecedents are deprecated
            aliased_from = expander.get_aliased_from("canonical_tag", include_deprecated=False)
            self.assertEqual(aliased_from, [])

    def test_get_aliases_outgoing_only(self):
        """Test get_aliases returns only outgoing aliases."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            # Deprecated tag should have outgoing alias to canonical
            aliases = expander.get_aliases("deprecated_tag")
            self.assertEqual(aliases, ["canonical_tag"])
            
            # Canonical tag should have no outgoing aliases
            aliases = expander.get_aliases("canonical_tag")
            self.assertEqual(aliases, [])

    def test_get_semantic_relations_complete(self):
        """Test get_semantic_relations returns complete relationships."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            relations = expander.get_semantic_relations("canonical_tag")
            
            # Check direct implications
            self.assertEqual(relations['direct_implications'], ["implied_tag"])
            
            # Check transitive implications
            self.assertEqual(relations['transitive_implications'], {"implied_tag", "transitive_tag"})
            
            # Check direct aliases (outgoing)
            self.assertEqual(relations['direct_aliases'], [])  # canonical has no outgoing
            
            # Check incoming aliases
            self.assertEqual(set(relations['aliased_from']), {"deprecated_tag", "another_deprecated"})
            
            # Check alias group
            self.assertEqual(relations['alias_group'], {"canonical_tag", "deprecated_tag", "another_deprecated"})
            
            # Check canonical status
            self.assertTrue(relations['is_canonical'])
            
            # Check all related tags
            expected_related = {
                "deprecated_tag", "another_deprecated",  # from alias group
                "implied_tag", "transitive_tag"         # from implications
            }
            self.assertEqual(relations['all_related'], expected_related)

    def test_get_semantic_relations_deprecated_tag(self):
        """Test get_semantic_relations for a deprecated tag."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=self.test_graph
            )
            
            relations = expander.get_semantic_relations("deprecated_tag")
            
            # Should inherit implications from its canonical form
            self.assertEqual(relations['direct_implications'], ["implied_tag"])
            self.assertEqual(relations['transitive_implications'], {"implied_tag", "transitive_tag"})
            
            # Should show outgoing alias to canonical
            self.assertEqual(relations['direct_aliases'], ["canonical_tag"])
            
            # Should not be canonical
            self.assertFalse(relations['is_canonical'])

    def test_get_semantic_relations_no_cache(self):
        """Test get_semantic_relations without cache enabled."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            with self.assertRaises(RuntimeError) as context:
                expander.get_semantic_relations("test_tag")
            self.assertIn("Graph cache is not enabled", str(context.exception))

    def test_get_semantic_relations_unfetched_tag(self):
        """Test get_semantic_relations with an unfetched tag."""
        # Create graph with unfetched tag
        graph = DanbooruTagGraph()
        graph.add_tag("unfetched_tag", is_deprecated=False, fetched=False)
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=graph
            )
            
            relations = expander.get_semantic_relations("unfetched_tag")
            
            # All relationship lists should be empty
            self.assertEqual(relations['direct_implications'], [])
            self.assertEqual(relations['transitive_implications'], set())
            self.assertEqual(relations['direct_aliases'], [])
            self.assertEqual(relations['aliased_from'], [])
            self.assertEqual(relations['alias_group'], {"unfetched_tag"})
            self.assertTrue(relations['is_canonical'])  # Default to True if unknown
            self.assertEqual(relations['all_related'], set())

    def test_get_semantic_relations_complex_implications(self):
        """Test get_semantic_relations with complex implication chains."""
        # Create graph with multiple implication paths
        graph = DanbooruTagGraph()
        graph.add_tag("start", is_deprecated=False, fetched=True)
        graph.add_tag("middle1", is_deprecated=False, fetched=True)
        graph.add_tag("middle2", is_deprecated=False, fetched=True)
        graph.add_tag("end", is_deprecated=False, fetched=True)
        
        # Two paths: start -> middle1 -> end and start -> middle2 -> end
        graph.add_implication("start", "middle1")
        graph.add_implication("middle1", "end")
        graph.add_implication("start", "middle2")
        graph.add_implication("middle2", "end")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=graph
            )
            
            relations = expander.get_semantic_relations("start")
            
            # Direct implications should include both middle tags
            self.assertEqual(set(relations['direct_implications']), {"middle1", "middle2"})
            
            # Transitive implications should include all reachable tags
            self.assertEqual(relations['transitive_implications'], {"middle1", "middle2", "end"})

    def test_get_semantic_relations_mixed_deprecated_implications(self):
        """Test get_semantic_relations with mixed deprecated status in implications."""
        # Create graph with deprecated tags in implication chain
        graph = DanbooruTagGraph()
        graph.add_tag("start", is_deprecated=False, fetched=True)
        graph.add_tag("deprecated_middle", is_deprecated=True, fetched=True)
        graph.add_tag("end", is_deprecated=False, fetched=True)
        
        graph.add_implication("start", "deprecated_middle")
        graph.add_implication("deprecated_middle", "end")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=graph
            )
            
            # Test with include_deprecated=True
            relations = expander.get_semantic_relations("start", include_deprecated=True)
            self.assertEqual(set(relations['direct_implications']), {"deprecated_middle"})
            self.assertEqual(relations['transitive_implications'], {"deprecated_middle", "end"})
            
            # Test with include_deprecated=False
            relations = expander.get_semantic_relations("start", include_deprecated=False)
            self.assertEqual(relations['direct_implications'], [])
            self.assertEqual(relations['transitive_implications'], {"end"})


if __name__ == '__main__':
    unittest.main() 