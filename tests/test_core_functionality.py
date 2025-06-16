"""Tests for core TagExpander functionality with graph cache."""

import unittest
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
from collections import Counter
from danbooru_tag_expander import TagExpander

@pytest.mark.unit
class TestTagExpanderCore(unittest.TestCase):
    """Test cases for the core TagExpander functionality."""

    def setUp(self):
        """Set up the test case."""
        # Create a temporary directory for cache
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock client
        self.mock_client = MagicMock()
        
        # Create a TagExpander with the mock client and cache enabled
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            self.expander = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=True,
                cache_dir=self.temp_dir
            )

    def tearDown(self):
        """Clean up after test."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_expand_tags_basic_functionality(self):
        """Test basic tag expansion functionality."""
        # Mock API responses for tag data
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                tag_name = params["search[name]"]
                # Mock deprecated status (all non-deprecated for simplicity)
                return [{"name": tag_name, "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                tag_name = params.get("search[antecedent_name]")
                # Mock some simple implications
                if tag_name == "kitten":
                    return [{"antecedent_name": "kitten", "consequent_name": "cat", "status": "active"}]
                elif tag_name == "cat":
                    return [{"antecedent_name": "cat", "consequent_name": "animal", "status": "active"}]
                elif tag_name == "animal":
                    return []  # animal has no further implications
                return []
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                # Mock aliases (none for simplicity)
                return [{"name": params["search[name_matches]"], "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test expanding tags with implications
        expanded_tags, frequencies = self.expander.expand_tags(["kitten"])
        
        # Should include the original tag plus its transitive implications
        expected_tags = {"kitten", "cat", "animal"}
        self.assertEqual(expanded_tags, expected_tags)
        
        # Check frequencies: kitten=1, cat=1 (from kitten), animal=1 (from cat)
        self.assertEqual(frequencies["kitten"], 1)
        self.assertEqual(frequencies["cat"], 1)
        self.assertEqual(frequencies["animal"], 1)

    def test_expand_tags_with_aliases(self):
        """Test tag expansion with aliases."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                tag_name = params["search[name]"]
                return [{"name": tag_name, "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                return []  # No implications for simplicity
            elif endpoint == "tag_aliases.json":
                # Use correct directed alias API format
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "feline":
                    return [{"antecedent_name": "feline", "consequent_name": "cat", "status": "active"}]
                return []
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test expanding tags with aliases (feline -> cat)
        expanded_tags, frequencies = self.expander.expand_tags(["feline"])
        
        # Should include both the original tag and its alias target
        expected_tags = {"feline", "cat"}
        self.assertEqual(expanded_tags, expected_tags)
        
        # Aliases should share the same frequency
        self.assertEqual(frequencies["feline"], 1)
        self.assertEqual(frequencies["cat"], 1)

    def test_expand_tags_multiple_input(self):
        """Test expanding multiple input tags."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                tag_name = params["search[name]"]
                return [{"name": tag_name, "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                tag_name = params.get("search[antecedent_name]")
                if tag_name in ["tag1", "tag2"]:
                    return [{"antecedent_name": tag_name, "consequent_name": "common", "status": "active"}]
                return []
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                return [{"name": params["search[name_matches]"], "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Test expanding multiple tags that imply the same tag
        expanded_tags, frequencies = self.expander.expand_tags(["tag1", "tag2"])
        
        # Should include original tags and their common implication
        expected_tags = {"tag1", "tag2", "common"}
        self.assertEqual(expanded_tags, expected_tags)
        
        # The common tag should have frequency 2 (from both inputs)
        self.assertEqual(frequencies["tag1"], 1)
        self.assertEqual(frequencies["tag2"], 1)
        self.assertEqual(frequencies["common"], 2)

    def test_expand_tags_no_cache_raises_error(self):
        """Test that expand_tags raises error when cache is disabled."""
        # Create expander without cache
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander_no_cache = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=False
            )
        
        # Should raise RuntimeError
        with self.assertRaises(RuntimeError) as context:
            expander_no_cache.expand_tags(["test"])
        
        self.assertIn("Graph cache is not enabled", str(context.exception))

    def test_external_tag_graph_injection(self):
        """Test that external DanbooruTagGraph can be injected."""
        from danbooru_tag_graph import DanbooruTagGraph
        
        # Create external graph with pre-populated data
        external_graph = DanbooruTagGraph()
        external_graph.add_tag("dog", fetched=True)
        external_graph.add_tag("animal", fetched=True)
        external_graph.add_implication("dog", "animal")
        
        # Create expander with external graph
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander = TagExpander(
                username="test",
                api_key="test",
                tag_graph=external_graph
            )
        
        # Should use the pre-populated graph without API calls
        expanded_tags, frequencies = expander.expand_tags(["dog"])
        
        # Should include both tags from the pre-populated graph
        expected_tags = {"dog", "animal"}
        self.assertEqual(expanded_tags, expected_tags)
        
        # Check frequencies
        self.assertEqual(frequencies["dog"], 1)
        self.assertEqual(frequencies["animal"], 1)
        
        # Verify no API calls were made since data was pre-populated
        self.mock_client._get.assert_not_called()

    def test_get_implications_direct(self):
        """Test getting direct implications from cached graph data."""
        # Set up mock API responses to populate cache
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                tag_name = params.get("search[antecedent_name]")
                if tag_name == "kitten":
                    return [{"antecedent_name": "kitten", "consequent_name": "cat", "status": "active"}]
                return []
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                return [{"name": params["search[name_matches]"], "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # First populate the cache
        self.expander.expand_tags(["kitten"])
        
        # Now test direct implications method
        implications = self.expander.get_implications("kitten")
        self.assertEqual(implications, ["cat"])
        
        # Test non-existent tag
        implications = self.expander.get_implications("nonexistent")
        self.assertEqual(implications, [])

    def test_get_transitive_implications(self):
        """Test getting transitive implications from cached graph data."""
        # Set up mock API responses for transitive chain: kitten -> cat -> animal
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                tag_name = params.get("search[antecedent_name]")
                if tag_name == "kitten":
                    return [{"antecedent_name": "kitten", "consequent_name": "cat", "status": "active"}]
                elif tag_name == "cat":
                    return [{"antecedent_name": "cat", "consequent_name": "animal", "status": "active"}]
                return []
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                return [{"name": params["search[name_matches]"], "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # First populate the cache
        self.expander.expand_tags(["kitten"])
        
        # Now test transitive implications method
        transitive_implications = self.expander.get_transitive_implications("kitten")
        expected = {"cat", "animal"}
        self.assertEqual(transitive_implications, expected)
        
        # Test direct implications vs transitive
        direct_implications = self.expander.get_implications("kitten")
        self.assertEqual(direct_implications, ["cat"])
        self.assertIn("animal", transitive_implications)
        self.assertNotIn("animal", direct_implications)

    def test_get_aliases_and_alias_group(self):
        """Test getting aliases and alias groups from cached graph data."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                return []  # No implications for simplicity
            elif endpoint == "tag_aliases.json":
                # Use correct directed alias API format
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "feline":
                    return [{"antecedent_name": "feline", "consequent_name": "cat", "status": "active"}]
                elif antecedent == "kitty":
                    return [{"antecedent_name": "kitty", "consequent_name": "cat", "status": "active"}]
                return []
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # First populate the cache with directed aliases: feline -> cat, kitty -> cat
        self.expander.expand_tags(["feline", "kitty", "cat"])
        
        # Test direct aliases (outgoing: antecedent -> consequent)
        feline_aliases = self.expander.get_aliases("feline")
        self.assertEqual(feline_aliases, ["cat"])
        
        # Canonical tags should have no outgoing aliases
        cat_aliases = self.expander.get_aliases("cat")
        self.assertEqual(cat_aliases, [])
        
        # Test alias group (should include all transitively connected aliases)
        alias_group = self.expander.get_alias_group("feline")
        # The alias group should include all tags connected through alias relationships
        self.assertIn("feline", alias_group)
        self.assertIn("cat", alias_group)
        self.assertIn("kitty", alias_group)

    def test_get_semantic_relations_comprehensive(self):
        """Test the comprehensive semantic relations method."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                tag_name = params.get("search[antecedent_name]")
                if tag_name == "kitten":
                    return [{"antecedent_name": "kitten", "consequent_name": "cat", "status": "active"}]
                elif tag_name == "cat":
                    return [{"antecedent_name": "cat", "consequent_name": "animal", "status": "active"}]
                return []
            elif endpoint == "tag_aliases.json":
                # Use correct directed alias API format
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "baby_cat":
                    return [{"antecedent_name": "baby_cat", "consequent_name": "kitten", "status": "active"}]
                return []
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # First populate the cache
        self.expander.expand_tags(["baby_cat", "kitten"])
        
        # Test comprehensive semantic relations for baby_cat (deprecated tag)
        relations = self.expander.get_semantic_relations("baby_cat")
        
        # Check structure includes new directed alias fields
        expected_keys = {'direct_implications', 'transitive_implications', 
                        'direct_aliases', 'aliased_from', 'alias_group', 
                        'is_canonical', 'all_related'}
        self.assertEqual(set(relations.keys()), expected_keys)
        
        # Check content for deprecated tag
        self.assertEqual(relations['direct_implications'], [])           # no direct implications
        self.assertEqual(relations['direct_aliases'], ["kitten"])        # aliases to kitten
        self.assertEqual(relations['aliased_from'], [])                  # nothing aliases to baby_cat
        self.assertFalse(relations['is_canonical'])                      # baby_cat is deprecated
        self.assertIn("baby_cat", relations['alias_group'])
        self.assertIn("kitten", relations['alias_group'])
        
        # all_related should contain alias targets
        expected_related = {"kitten"}  # baby_cat aliases to kitten
        self.assertEqual(relations['all_related'], expected_related)

    def test_is_tag_cached(self):
        """Test checking if a tag is cached."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                return []
            elif endpoint == "tags.json" and "search[name_matches]" in params:
                return [{"name": params["search[name_matches]"], "consequent_aliases": []}]
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Initially, tag should not be cached
        self.assertFalse(self.expander.is_tag_cached("test_tag"))
        
        # After expanding, tag should be cached
        self.expander.expand_tags(["test_tag"])
        self.assertTrue(self.expander.is_tag_cached("test_tag"))

    def test_semantic_methods_without_cache_raise_error(self):
        """Test that semantic relationship methods raise error when cache is disabled."""
        # Create expander without cache
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander_no_cache = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=False
            )
        
        # All semantic methods should raise RuntimeError
        methods_to_test = [
            ('get_implications', ["test"]),
            ('get_transitive_implications', ["test"]),
            ('get_aliases', ["test"]),
            ('get_alias_group', ["test"]),
            ('get_semantic_relations', ["test"]),
            ('is_tag_cached', ["test"])
        ]
        
        for method_name, args in methods_to_test:
            with self.subTest(method=method_name):
                method = getattr(expander_no_cache, method_name)
                with self.assertRaises(RuntimeError) as context:
                    method(*args)
                self.assertIn("Graph cache is not enabled", str(context.exception))

    def test_directed_alias_functionality(self):
        """Test the new directed alias functionality."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                return []  # No implications for simplicity
            elif endpoint == "tag_aliases.json":
                # Mock directed alias relationships
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "ugly_man":
                    return [{"antecedent_name": "ugly_man", "consequent_name": "ugly_bastard", "status": "active"}]
                elif antecedent == "old_tag":
                    return [{"antecedent_name": "old_tag", "consequent_name": "new_tag", "status": "active"}]
                return []
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Populate cache with directed alias relationships
        self.expander.expand_tags(["ugly_man", "ugly_bastard", "old_tag", "new_tag"])
        
        # Test outgoing aliases (antecedent -> consequent)
        outgoing_aliases = self.expander.get_aliases("ugly_man")
        self.assertEqual(outgoing_aliases, ["ugly_bastard"])
        
        # Canonical tags should have no outgoing aliases
        canonical_aliases = self.expander.get_aliases("ugly_bastard")
        self.assertEqual(canonical_aliases, [])
        
        # Test incoming aliases (what aliases TO this tag)
        incoming_aliases = self.expander.get_aliased_from("ugly_bastard")
        self.assertEqual(incoming_aliases, ["ugly_man"])
        
        # Deprecated tags should have no incoming aliases
        no_incoming = self.expander.get_aliased_from("ugly_man")
        self.assertEqual(no_incoming, [])
        
        # Test canonical status
        self.assertFalse(self.expander.is_canonical("ugly_man"))      # antecedent (deprecated)
        self.assertTrue(self.expander.is_canonical("ugly_bastard"))   # consequent (canonical)
        self.assertFalse(self.expander.is_canonical("old_tag"))       # antecedent (deprecated)
        self.assertTrue(self.expander.is_canonical("new_tag"))        # consequent (canonical)

    def test_updated_semantic_relations_with_directed_aliases(self):
        """Test that get_semantic_relations includes the new directed alias information."""
        def mock_api_request(endpoint, params):
            if endpoint == "tags.json" and "search[name]" in params:
                return [{"name": params["search[name]"], "is_deprecated": False}]
            elif endpoint == "tag_implications.json":
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "deprecated_tag":
                    return [{"antecedent_name": "deprecated_tag", "consequent_name": "implied_tag", "status": "active"}]
                return []
            elif endpoint == "tag_aliases.json":
                antecedent = params.get("search[antecedent_name]")
                if antecedent == "deprecated_tag":
                    return [{"antecedent_name": "deprecated_tag", "consequent_name": "canonical_tag", "status": "active"}]
                return []
            return []
        
        self.mock_client._get.side_effect = mock_api_request
        
        # Populate cache
        self.expander.expand_tags(["deprecated_tag", "canonical_tag"])
        
        # Test semantic relations for deprecated tag
        relations = self.expander.get_semantic_relations("deprecated_tag")
        
        # Check structure includes new fields
        expected_keys = {'direct_implications', 'transitive_implications', 
                        'direct_aliases', 'aliased_from', 'alias_group', 
                        'is_canonical', 'all_related'}
        self.assertEqual(set(relations.keys()), expected_keys)
        
        # Check directed alias content
        self.assertEqual(relations['direct_aliases'], ["canonical_tag"])  # outgoing
        self.assertEqual(relations['aliased_from'], [])                   # incoming (none)
        self.assertFalse(relations['is_canonical'])                       # deprecated tag
        
        # Test semantic relations for canonical tag
        canonical_relations = self.expander.get_semantic_relations("canonical_tag")
        self.assertEqual(canonical_relations['direct_aliases'], [])                    # no outgoing
        self.assertEqual(canonical_relations['aliased_from'], ["deprecated_tag"])      # incoming
        self.assertTrue(canonical_relations['is_canonical'])                           # canonical tag

    def test_directed_alias_methods_without_cache_raise_error(self):
        """Test that new directed alias methods raise error when cache is disabled."""
        # Create expander without cache
        with patch('danbooru_tag_expander.utils.tag_expander.Danbooru', return_value=self.mock_client):
            expander_no_cache = TagExpander(
                username="test", 
                api_key="test", 
                use_cache=False
            )
        
        # New directed alias methods should raise RuntimeError
        methods_to_test = [
            ('get_aliased_from', ["test"]),
            ('is_canonical', ["test"])
        ]
        
        for method_name, args in methods_to_test:
            with self.subTest(method=method_name):
                method = getattr(expander_no_cache, method_name)
                with self.assertRaises(RuntimeError) as context:
                    method(*args)
                self.assertIn("Graph cache is not enabled", str(context.exception))


if __name__ == '__main__':
    unittest.main() 