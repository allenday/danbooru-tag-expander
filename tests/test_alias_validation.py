#!/usr/bin/env python3
"""Tests for alias directionality validation functionality."""

import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from danbooru_tag_expander import TagExpander
from danbooru_tag_graph import DanbooruTagGraph


class TestAliasValidation(unittest.TestCase):
    """Test cases for alias directionality validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_client = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_alias_directionality_no_graph(self):
        """Test validation when no graph is present."""
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                use_cache=False
            )
            
            # Should not raise any errors
            expander._validate_alias_directionality()

    def test_validate_alias_directionality_no_bidirectional_aliases(self):
        """Test validation with no bidirectional aliases."""
        # Create external graph with proper directional aliases
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("old_tag", is_deprecated=True, fetched=True)
        external_graph.add_tag("new_tag", is_deprecated=False, fetched=True)
        external_graph.add_alias("old_tag", "new_tag")  # old_tag -> new_tag
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Should not modify anything
            edges_before = list(external_graph.graph.edges(data=True))
            expander._validate_alias_directionality()
            edges_after = list(external_graph.graph.edges(data=True))
            
            self.assertEqual(edges_before, edges_after)

    def test_validate_alias_directionality_fixes_bidirectional_canonical_status(self):
        """Test validation fixes bidirectional aliases using canonical status."""
        # Create external graph with bidirectional aliases
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("deprecated_tag", is_deprecated=True, fetched=True)
        external_graph.add_tag("canonical_tag", is_deprecated=False, fetched=True)
        
        # Add bidirectional alias edges manually
        external_graph.graph.add_edge("deprecated_tag", "canonical_tag", edge_type="alias")
        external_graph.graph.add_edge("canonical_tag", "deprecated_tag", edge_type="alias")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Should have only one directional edge: deprecated -> canonical
            edges = [(u, v, data) for u, v, data in external_graph.graph.edges(data=True) 
                    if data.get('edge_type') == 'alias']
            
            self.assertEqual(len(edges), 1)
            u, v, data = edges[0]
            self.assertEqual(u, "deprecated_tag")
            self.assertEqual(v, "canonical_tag")

    def test_validate_alias_directionality_fixes_bidirectional_length_heuristic(self):
        """Test validation fixes bidirectional aliases using length heuristic."""
        # Create external graph with bidirectional aliases (same canonical status)
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("short", is_deprecated=False, fetched=True)
        external_graph.add_tag("very_long_tag_name", is_deprecated=False, fetched=True)
        
        # Add bidirectional alias edges manually
        external_graph.graph.add_edge("short", "very_long_tag_name", edge_type="alias")
        external_graph.graph.add_edge("very_long_tag_name", "short", edge_type="alias")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Should have only one directional edge: longer -> shorter
            edges = [(u, v, data) for u, v, data in external_graph.graph.edges(data=True) 
                    if data.get('edge_type') == 'alias']
            
            self.assertEqual(len(edges), 1)
            u, v, data = edges[0]
            self.assertEqual(u, "very_long_tag_name")
            self.assertEqual(v, "short")

    def test_validate_alias_directionality_fixes_bidirectional_alphabetical_heuristic(self):
        """Test validation fixes bidirectional aliases using alphabetical heuristic."""
        # Create external graph with bidirectional aliases (same length, same canonical status)
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("zebra", is_deprecated=False, fetched=True)
        external_graph.add_tag("apple", is_deprecated=False, fetched=True)
        
        # Add bidirectional alias edges manually
        external_graph.graph.add_edge("zebra", "apple", edge_type="alias")
        external_graph.graph.add_edge("apple", "zebra", edge_type="alias")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Should have only one directional edge: later alphabetically -> earlier
            edges = [(u, v, data) for u, v, data in external_graph.graph.edges(data=True) 
                    if data.get('edge_type') == 'alias']
            
            self.assertEqual(len(edges), 1)
            u, v, data = edges[0]
            self.assertEqual(u, "zebra")
            self.assertEqual(v, "apple")

    def test_validate_alias_directionality_multiple_bidirectional_pairs(self):
        """Test validation fixes multiple bidirectional alias pairs."""
        # Create external graph with multiple bidirectional aliases
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("old1", is_deprecated=True, fetched=True)
        external_graph.add_tag("new1", is_deprecated=False, fetched=True)
        external_graph.add_tag("old2", is_deprecated=True, fetched=True)
        external_graph.add_tag("new2", is_deprecated=False, fetched=True)
        
        # Add bidirectional alias edges manually
        external_graph.graph.add_edge("old1", "new1", edge_type="alias")
        external_graph.graph.add_edge("new1", "old1", edge_type="alias")
        external_graph.graph.add_edge("old2", "new2", edge_type="alias")
        external_graph.graph.add_edge("new2", "old2", edge_type="alias")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Should have only two directional edges: old -> new
            edges = [(u, v, data) for u, v, data in external_graph.graph.edges(data=True) 
                    if data.get('edge_type') == 'alias']
            
            self.assertEqual(len(edges), 2)
            
            # Check that all edges go from deprecated to canonical
            for u, v, data in edges:
                u_deprecated = external_graph.graph.nodes[u].get('deprecated', False)
                v_deprecated = external_graph.graph.nodes[v].get('deprecated', False)
                self.assertTrue(u_deprecated)  # Source should be deprecated
                self.assertFalse(v_deprecated)  # Target should be canonical

    def test_validate_alias_directionality_mixed_edge_types(self):
        """Test validation only affects alias edges, not other edge types."""
        # Create external graph with mixed edge types
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("tag1", is_deprecated=False, fetched=True)
        external_graph.add_tag("tag2", is_deprecated=False, fetched=True)
        external_graph.add_tag("tag3", is_deprecated=False, fetched=True)
        
        # Add implication edge (should not be affected)
        external_graph.add_implication("tag1", "tag2")
        
        # Add bidirectional alias edges
        external_graph.graph.add_edge("tag2", "tag3", edge_type="alias")
        external_graph.graph.add_edge("tag3", "tag2", edge_type="alias")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Count edges before
            implication_edges_before = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                                      if data.get('edge_type') == 'implication']
            alias_edges_before = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                                if data.get('edge_type') == 'alias']
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Count edges after
            implication_edges_after = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                                     if data.get('edge_type') == 'implication']
            alias_edges_after = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                               if data.get('edge_type') == 'alias']
            
            # Implication edges should be unchanged
            self.assertEqual(implication_edges_before, implication_edges_after)
            
            # Alias edges should be reduced from 2 to 1
            self.assertEqual(len(alias_edges_before), 2)
            self.assertEqual(len(alias_edges_after), 1)

    def test_validate_alias_directionality_preserves_correct_direction(self):
        """Test validation preserves already correct directional aliases."""
        # Create external graph with correct directional aliases
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("deprecated1", is_deprecated=True, fetched=True)
        external_graph.add_tag("canonical1", is_deprecated=False, fetched=True)
        external_graph.add_tag("deprecated2", is_deprecated=True, fetched=True)
        external_graph.add_tag("canonical2", is_deprecated=False, fetched=True)
        
        # Add correct directional aliases
        external_graph.add_alias("deprecated1", "canonical1")
        external_graph.add_alias("deprecated2", "canonical2")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Get edges before validation
            edges_before = set((u, v) for u, v, data in external_graph.graph.edges(data=True) 
                             if data.get('edge_type') == 'alias')
            
            # Validate
            expander._validate_alias_directionality()
            
            # Get edges after validation
            edges_after = set((u, v) for u, v, data in external_graph.graph.edges(data=True) 
                            if data.get('edge_type') == 'alias')
            
            # Should be unchanged
            self.assertEqual(edges_before, edges_after)

    def test_validate_alias_directionality_complex_scenario(self):
        """Test validation in a complex scenario with multiple types of issues."""
        # Create external graph with various scenarios
        external_graph = DanbooruTagGraph()
        
        # Correct directional alias (should be preserved)
        external_graph.add_tag("correct_old", is_deprecated=True, fetched=True)
        external_graph.add_tag("correct_new", is_deprecated=False, fetched=True)
        external_graph.add_alias("correct_old", "correct_new")
        
        # Bidirectional alias with clear canonical status (should be fixed)
        external_graph.add_tag("bidirectional_old", is_deprecated=True, fetched=True)
        external_graph.add_tag("bidirectional_new", is_deprecated=False, fetched=True)
        external_graph.graph.add_edge("bidirectional_old", "bidirectional_new", edge_type="alias")
        external_graph.graph.add_edge("bidirectional_new", "bidirectional_old", edge_type="alias")
        
        # Bidirectional alias with same canonical status (should use heuristics)
        external_graph.add_tag("heuristic_long", is_deprecated=False, fetched=True)
        external_graph.add_tag("short", is_deprecated=False, fetched=True)
        external_graph.graph.add_edge("heuristic_long", "short", edge_type="alias")
        external_graph.graph.add_edge("short", "heuristic_long", edge_type="alias")
        
        # Implication (should be unaffected)
        external_graph.add_tag("implies_from", is_deprecated=False, fetched=True)
        external_graph.add_tag("implies_to", is_deprecated=False, fetched=True)
        external_graph.add_implication("implies_from", "implies_to")
        
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
            
            # Validate and fix
            expander._validate_alias_directionality()
            
            # Check results
            alias_edges = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                          if data.get('edge_type') == 'alias']
            implication_edges = [(u, v) for u, v, data in external_graph.graph.edges(data=True) 
                               if data.get('edge_type') == 'implication']
            
            # Should have 3 alias edges (all directional)
            self.assertEqual(len(alias_edges), 3)
            
            # Should have 1 implication edge (unchanged)
            self.assertEqual(len(implication_edges), 1)
            self.assertIn(("implies_from", "implies_to"), implication_edges)
            
            # Check specific alias directions
            alias_edge_set = set(alias_edges)
            self.assertIn(("correct_old", "correct_new"), alias_edge_set)
            self.assertIn(("bidirectional_old", "bidirectional_new"), alias_edge_set)
            self.assertIn(("heuristic_long", "short"), alias_edge_set)


if __name__ == '__main__':
    unittest.main() 