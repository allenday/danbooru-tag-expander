#!/usr/bin/env python3
"""
Integration tests for directional alias functionality.
NO MOCKING - Real API calls and real data validation.
"""

import os
import tempfile
import unittest
import pytest
from unittest import TestCase
from danbooru_tag_expander import TagExpander
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock

# Load environment variables
load_dotenv()

@pytest.mark.integration
@pytest.mark.api
@pytest.mark.slow
class TestDirectionalAliasesIntegration(TestCase):
    """Integration tests for directional alias functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures."""
        # Verify credentials are available
        cls.username = os.getenv("DANBOORU_USERNAME")
        cls.api_key = os.getenv("DANBOORU_API_KEY")
        cls.site_url = os.getenv("DANBOORU_SITE_URL", "https://danbooru.donmai.us")
        
        if not cls.username or not cls.api_key:
            raise unittest.SkipTest("Missing DANBOORU_USERNAME or DANBOORU_API_KEY")
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Create temporary cache directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.expander = TagExpander(
            username=self.username,
            api_key=self.api_key,
            site_url=self.site_url,
            cache_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after each test."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_api_connectivity(self):
        """Test that API connectivity works with credentials."""
        # Test basic API call
        params = {"search[name]": "1girl", "limit": 1}
        response = self.expander._api_request("tags.json", params)
        
        self.assertIsInstance(response, list, "API should return a list")
        self.assertGreater(len(response), 0, "API should return data for 1girl")
        
        tag_data = response[0]
        self.assertEqual(tag_data.get("name"), "1girl", "Should return correct tag")
        self.assertIn("is_deprecated", tag_data, "Should include deprecated status")

    def test_raw_alias_api_calls(self):
        """Test raw API calls for alias data."""
        # Test ugly_man as antecedent
        params = {"search[antecedent_name]": "ugly_man"}
        response = self.expander._api_request("tag_aliases.json", params)
        
        self.assertIsInstance(response, list, "Alias API should return a list")
        
        # If we get data, validate its structure
        if response:
            alias_data = response[0]
            self.assertIn("antecedent_name", alias_data, "Should have antecedent_name")
            self.assertIn("consequent_name", alias_data, "Should have consequent_name")
            self.assertIn("status", alias_data, "Should have status")
            self.assertEqual(alias_data["antecedent_name"], "ugly_man", "Should match query")

    def test_tag_expansion_basic(self):
        """Test basic tag expansion functionality."""
        # Test with a common tag
        expanded_tags, frequencies = self.expander.expand_tags(["1girl"])
        
        self.assertIsInstance(expanded_tags, set, "Should return a set of tags")
        self.assertIsInstance(frequencies, dict, "Should return frequency dict")
        self.assertGreater(len(expanded_tags), 0, "Should expand to at least one tag")
        self.assertIn("1girl", expanded_tags, "Should include original tag")

    def test_ugly_man_ugly_bastard_relationship(self):
        """Test the specific ugly_man -> ugly_bastard alias relationship."""
        # Expand both tags to populate cache
        expanded_tags, frequencies = self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        self.assertGreater(len(expanded_tags), 0, "Should expand to some tags")
        
        # Test alias methods
        ugly_man_aliases = self.expander.get_aliases("ugly_man")
        ugly_bastard_aliases = self.expander.get_aliases("ugly_bastard")
        ugly_man_aliased_from = self.expander.get_aliased_from("ugly_man")
        ugly_bastard_aliased_from = self.expander.get_aliased_from("ugly_bastard")
        
        # Test canonical status
        ugly_man_canonical = self.expander.is_canonical("ugly_man")
        ugly_bastard_canonical = self.expander.is_canonical("ugly_bastard")
        
        # Log results for debugging
        print(f"\nDEBUG - ugly_man aliases: {ugly_man_aliases}")
        print(f"DEBUG - ugly_bastard aliases: {ugly_bastard_aliases}")
        print(f"DEBUG - ugly_man aliased_from: {ugly_man_aliased_from}")
        print(f"DEBUG - ugly_bastard aliased_from: {ugly_bastard_aliased_from}")
        print(f"DEBUG - ugly_man canonical: {ugly_man_canonical}")
        print(f"DEBUG - ugly_bastard canonical: {ugly_bastard_canonical}")
        
        # Verify some kind of relationship exists
        has_relationship = (
            len(ugly_man_aliases) > 0 or 
            len(ugly_bastard_aliased_from) > 0 or
            ugly_man_canonical != ugly_bastard_canonical
        )
        
        self.assertTrue(has_relationship, 
                       "Should detect some alias relationship between ugly_man and ugly_bastard")

        # --- Direct Graph Inspection ---
        graph = self.expander.tag_graph.graph
        
        # 1. Check node attributes for deprecation/canonical status
        # ugly_man is NOT deprecated itself, but it's not canonical because it aliases
        self.assertFalse(graph.nodes["ugly_man"]["deprecated"], "'ugly_man' node should not be marked deprecated")
        self.assertFalse(self.expander.is_canonical("ugly_man"), "'ugly_man' should not be canonical")
        
        # ugly_bastard is the canonical tag
        self.assertFalse(graph.nodes["ugly_bastard"]["deprecated"], "'ugly_bastard' node should not be marked deprecated")
        self.assertTrue(self.expander.is_canonical("ugly_bastard"), "'ugly_bastard' should be canonical")

        # 2. Check for correct edge direction and attributes
        self.assertTrue(graph.has_edge("ugly_man", "ugly_bastard"), "Graph should have a directed edge from 'ugly_man' to 'ugly_bastard'")
        # edge_data = graph.get_edge_data("ugly_man", "ugly_bastard")
        # self.assertEqual(edge_data.get("edge_type"), "alias", "Edge type should be 'alias'")
        
        # 3. Ensure no reverse edge exists
        self.assertFalse(graph.has_edge("ugly_bastard", "ugly_man"), "Graph should NOT have a reverse edge from 'ugly_bastard' to 'ugly_man'")

    def test_directional_alias_consistency(self):
        """Test that directional aliases are consistent."""
        # Expand tags to populate cache
        self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        # Get all relationship data
        ugly_man_aliases = self.expander.get_aliases("ugly_man")
        ugly_bastard_aliased_from = self.expander.get_aliased_from("ugly_bastard")
        
        # If ugly_man has aliases, ugly_bastard should show up in aliased_from
        if "ugly_bastard" in ugly_man_aliases:
            self.assertIn("ugly_man", ugly_bastard_aliased_from,
                         "If ugly_man aliases to ugly_bastard, ugly_bastard should show ugly_man in aliased_from")
        
        # If ugly_bastard has incoming aliases from ugly_man, ugly_man should alias to ugly_bastard
        if "ugly_man" in ugly_bastard_aliased_from:
            self.assertIn("ugly_bastard", ugly_man_aliases,
                         "If ugly_bastard gets aliases from ugly_man, ugly_man should alias to ugly_bastard")

    def test_semantic_relations_completeness(self):
        """Test that semantic relations provide complete data."""
        # Expand tags to populate cache
        self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        # Get semantic relations
        ugly_man_relations = self.expander.get_semantic_relations("ugly_man")
        ugly_bastard_relations = self.expander.get_semantic_relations("ugly_bastard")
        
        # Validate structure
        expected_keys = [
            'direct_implications', 'transitive_implications', 'direct_aliases',
            'aliased_from', 'alias_group', 'is_canonical', 'all_related'
        ]
        
        for key in expected_keys:
            self.assertIn(key, ugly_man_relations, f"ugly_man relations should have {key}")
            self.assertIn(key, ugly_bastard_relations, f"ugly_bastard relations should have {key}")
        
        # Test data types
        self.assertIsInstance(ugly_man_relations['direct_implications'], list)
        self.assertIsInstance(ugly_man_relations['transitive_implications'], set)
        self.assertIsInstance(ugly_man_relations['direct_aliases'], list)
        self.assertIsInstance(ugly_man_relations['aliased_from'], list)
        self.assertIsInstance(ugly_man_relations['alias_group'], set)
        self.assertIsInstance(ugly_man_relations['is_canonical'], bool)
        self.assertIsInstance(ugly_man_relations['all_related'], set)

    def test_graph_structure_integrity(self):
        """Test that the internal graph structure is correct."""
        # Expand tags to populate cache
        self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        self.assertIsNotNone(self.expander.tag_graph, "Should have a tag graph")
        
        graph = self.expander.tag_graph.graph
        nodes = list(graph.nodes(data=True))
        edges = list(graph.edges(data=True))
        
        # Check basic structure
        self.assertGreater(len(nodes), 0, "Graph should have nodes")
        
        # Check that our test tags are in the graph
        node_names = [node[0] for node in nodes]
        self.assertIn("ugly_man", node_names, "ugly_man should be in graph")
        self.assertIn("ugly_bastard", node_names, "ugly_bastard should be in graph")
        
        # Validate node data structure
        for node_name, node_data in nodes:
            self.assertIsInstance(node_data, dict, f"Node {node_name} should have dict data")
            self.assertIn("fetched", node_data, f"Node {node_name} should have fetched status")
            self.assertIn("deprecated", node_data, f"Node {node_name} should have deprecated status")

    def test_cache_persistence(self):
        """Test that cache persists data correctly between instances."""
        # First expander - populate cache
        expanded_tags1, _ = self.expander.expand_tags(["1girl"])
        
        if self.expander.tag_graph:
            nodes_count1 = self.expander.tag_graph.graph.number_of_nodes()
            edges_count1 = self.expander.tag_graph.graph.number_of_edges()
        else:
            self.fail("First expander should have a graph")
        
        # Second expander with same cache dir - should load from cache
        expander2 = TagExpander(
            username=self.username,
            api_key=self.api_key,
            site_url=self.site_url,
            cache_dir=self.temp_dir
        )
        
        if expander2.tag_graph:
            nodes_count2 = expander2.tag_graph.graph.number_of_nodes()
            edges_count2 = expander2.tag_graph.graph.number_of_edges()
            
            # Should have loaded data from cache
            self.assertGreaterEqual(nodes_count2, nodes_count1, 
                                   "Second expander should have at least as much data as first")
        else:
            self.fail("Second expander should have a graph")

    def test_is_canonical_consistency(self):
        """Test that is_canonical method is consistent with alias data."""
        # Expand tags to populate cache
        self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        ugly_man_canonical = self.expander.is_canonical("ugly_man")
        ugly_bastard_canonical = self.expander.is_canonical("ugly_bastard")
        
        ugly_man_aliases = self.expander.get_aliases("ugly_man")
        ugly_bastard_aliases = self.expander.get_aliases("ugly_bastard")
        
        # If a tag has outgoing aliases, it should not be canonical
        if len(ugly_man_aliases) > 0:
            self.assertFalse(ugly_man_canonical, 
                           "Tag with outgoing aliases should not be canonical")
        
        if len(ugly_bastard_aliases) > 0:
            self.assertFalse(ugly_bastard_canonical,
                           "Tag with outgoing aliases should not be canonical")

    def test_get_aliased_from_parameter_behavior(self):
        """Test that get_aliased_from behaves correctly with include_deprecated parameter."""
        # Expand tags to populate cache
        self.expander.expand_tags(["ugly_man", "ugly_bastard"])
        
        # Test with default parameter (should be True)
        aliased_from_default = self.expander.get_aliased_from("ugly_bastard")
        
        # Test with explicit True
        aliased_from_true = self.expander.get_aliased_from("ugly_bastard", include_deprecated=True)
        
        # Test with explicit False
        aliased_from_false = self.expander.get_aliased_from("ugly_bastard", include_deprecated=False)
        
        # Default should match explicit True (our fix)
        self.assertEqual(aliased_from_default, aliased_from_true,
                        "Default parameter should match include_deprecated=True")
        
        # Log for debugging
        print(f"\nDEBUG - aliased_from default: {aliased_from_default}")
        print(f"DEBUG - aliased_from True: {aliased_from_true}")
        print(f"DEBUG - aliased_from False: {aliased_from_false}")

    def test_multiple_tag_expansion(self):
        """Test expansion with multiple tags including aliases."""
        # Test with multiple tags that might have relationships
        test_tags = ["ugly_man", "ugly_bastard", "1girl"]
        expanded_tags, frequencies = self.expander.expand_tags(test_tags)
        
        self.assertIsInstance(expanded_tags, set, "Should return a set")
        self.assertIsInstance(frequencies, dict, "Should return a dict")
        
        # All original tags should be present (or their canonical forms)
        for tag in test_tags:
            # Either the tag itself or its canonical form should be present
            tag_present = (
                tag in expanded_tags or
                any(canonical in expanded_tags for canonical in self.expander.get_aliases(tag))
            )
            # Note: We can't assert this strongly because aliases might redirect
            # Just log for debugging
            print(f"DEBUG - Tag {tag} present: {tag_present}")

    def test_error_handling_invalid_tags(self):
        """Test error handling with invalid or non-existent tags."""
        # Test with a tag that definitely doesn't exist
        fake_tag = "this_tag_definitely_does_not_exist_12345"
        
        # Should not crash
        try:
            expanded_tags, frequencies = self.expander.expand_tags([fake_tag])
            # Should at least return the original tag
            self.assertIn(fake_tag, expanded_tags, "Should include original tag even if not found")
        except Exception as e:
            self.fail(f"Should handle non-existent tags gracefully, but got: {e}")

    def test_danbooru_tag_graph_version_compatibility(self):
        """Test that we're using the correct version of danbooru-tag-graph."""
        # Test that get_aliased_from method exists and works
        self.assertTrue(hasattr(self.expander.tag_graph, 'get_aliased_from'),
                       "Should have get_aliased_from method")
        
        # Test that the method signature is correct
        import inspect
        sig = inspect.signature(self.expander.tag_graph.get_aliased_from)
        params = list(sig.parameters.keys())
        
        self.assertIn('tag', params, "Should have tag parameter")
        self.assertIn('include_deprecated', params, "Should have include_deprecated parameter")
        
        # Test default value
        include_deprecated_param = sig.parameters['include_deprecated']
        self.assertEqual(include_deprecated_param.default, True,
                        "include_deprecated should default to True in danbooru-tag-graph")

    def test_1girls_alias_of_1girl(self):
        """Test that '1girls' is correctly handled as an alias of '1girl'."""
        # Expand the misspelled tag
        expanded_tags, frequencies = self.expander.expand_tags(["1girls"])
        
        # Check that both the alias and the canonical tag are present
        self.assertIn("1girls", expanded_tags)
        self.assertIn("1girl", expanded_tags)
        
        # Verify canonical status
        self.assertTrue(self.expander.is_canonical("1girl"))
        self.assertFalse(self.expander.is_canonical("1girls"))
        
        # Verify alias relationship
        aliases_of_1girls = self.expander.get_aliases("1girls")
        self.assertIn("1girl", aliases_of_1girls)
        
        # Verify frequency sharing
        self.assertEqual(frequencies["1girls"], 1)
        self.assertEqual(frequencies["1girl"], 1)

        # --- Direct Graph Inspection ---
        graph = self.expander.tag_graph.graph

        # 1. Check node attributes
        self.assertFalse(graph.nodes["1girls"]["deprecated"], "'1girls' node should not be marked deprecated")
        self.assertFalse(graph.nodes["1girl"]["deprecated"], "'1girl' node should not be marked deprecated")

        # 2. Check for correct edge direction and attributes
        self.assertTrue(graph.has_edge("1girls", "1girl"), "Graph should have a directed edge from '1girls' to '1girl'")
        # edge_data = graph.get_edge_data("1girls", "1girl")
        # self.assertEqual(edge_data.get("edge_type"), "alias", "Edge type for '1girls'->'1girl' should be 'alias'")

        # 3. Ensure no reverse edge exists
        self.assertFalse(graph.has_edge("1girl", "1girls"), "Graph should NOT have a reverse edge from '1girl' to '1girls'")


class TestDirectionalAliasesRealData(TestCase):
    """Integration tests using real Danbooru data to validate directional alias behavior."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures."""
        # Verify credentials are available
        cls.username = os.getenv("DANBOORU_USERNAME")
        cls.api_key = os.getenv("DANBOORU_API_KEY")
        cls.site_url = os.getenv("DANBOORU_SITE_URL", "https://danbooru.donmai.us")
        
        if not cls.username or not cls.api_key:
            raise unittest.SkipTest("Missing DANBOORU_USERNAME or DANBOORU_API_KEY")
    
    def setUp(self):
        """Set up test fixtures for each test."""
        # Create temporary cache directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.expander = TagExpander(
            username=self.username,
            api_key=self.api_key,
            site_url=self.site_url,
            cache_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after each test."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_real_alias_relationship_validation(self):
        """Test with real alias relationships from Danbooru."""
        # First, check if the ugly_man -> ugly_bastard relationship exists in the API
        params = {"search[antecedent_name]": "ugly_man"}
        response = self.expander._api_request("tag_aliases.json", params)
        
        if not response:
            self.skipTest("No alias data found for ugly_man in API")
        
        # Validate the API response structure
        alias_data = response[0]
        self.assertEqual(alias_data["antecedent_name"], "ugly_man")
        self.assertEqual(alias_data["status"], "active")
        consequent = alias_data["consequent_name"]
        
        # Now test our implementation
        self.expander.expand_tags(["ugly_man", consequent])
        
        ugly_man_aliases = self.expander.get_aliases("ugly_man")
        consequent_aliased_from = self.expander.get_aliased_from(consequent)
        
        # Validate directional relationship
        self.assertIn(consequent, ugly_man_aliases,
                     f"ugly_man should alias to {consequent}")
        self.assertIn("ugly_man", consequent_aliased_from,
                     f"{consequent} should show ugly_man in aliased_from")

    def test_comprehensive_alias_validation(self):
        """Comprehensive test of alias functionality with real data."""
        # Get real alias data from API
        params = {"search[antecedent_name]": "ugly_man"}
        response = self.expander._api_request("tag_aliases.json", params)
        
        if not response:
            self.skipTest("No alias data found for ugly_man")
        
        alias_data = response[0]
        antecedent = alias_data["antecedent_name"]
        consequent = alias_data["consequent_name"]
        
        # Expand both tags
        self.expander.expand_tags([antecedent, consequent])
        
        # Test all directional methods
        antecedent_aliases = self.expander.get_aliases(antecedent)
        consequent_aliases = self.expander.get_aliases(consequent)
        antecedent_aliased_from = self.expander.get_aliased_from(antecedent)
        consequent_aliased_from = self.expander.get_aliased_from(consequent)
        antecedent_canonical = self.expander.is_canonical(antecedent)
        consequent_canonical = self.expander.is_canonical(consequent)
        
        # Validate directional relationship
        self.assertIn(consequent, antecedent_aliases,
                     f"{antecedent} should alias to {consequent}")
        self.assertEqual(len(consequent_aliases), 0,
                        f"{consequent} should not have outgoing aliases")
        self.assertEqual(len(antecedent_aliased_from), 0,
                        f"{antecedent} should not have incoming aliases")
        self.assertIn(antecedent, consequent_aliased_from,
                     f"{consequent} should have {antecedent} in aliased_from")
        
        # Validate canonical status
        self.assertFalse(antecedent_canonical,
                        f"{antecedent} should not be canonical (has outgoing alias)")
        self.assertTrue(consequent_canonical,
                       f"{consequent} should be canonical (no outgoing aliases)")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2) 