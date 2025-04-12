import unittest
from danbooru_tag_expander.utils.tag_expander import TagExpander

class TestTagExpander(unittest.TestCase):
    def setUp(self):
        """Set up a TagExpander instance for each test"""
        # Initialize with credentials from environment, disable cache for integration tests
        self.expander = TagExpander(use_cache=False)

    def test_tag_implications(self):
        """Test that tag implications are correctly retrieved"""
        # Test tile_floor -> tiles implication
        implications = self.expander.get_tag_implications("tile_floor")
        self.assertIn("tiles", implications, "tile_floor should implicate tiles")
        self.assertEqual(len(implications), 1, "tile_floor should have exactly one implication")

    def test_tag_aliases(self):
        """Test that tag aliases are correctly retrieved"""
        # Test tile -> tiles alias
        aliases = self.expander.get_tag_aliases("tiles")
        self.assertIn("tile", aliases, "tiles should have tile as an alias")

    def test_tag_expansion(self):
        """Test that tag expansion works correctly with implications"""
        # Test expanding a tag with known implications
        expanded_tags, frequencies = self.expander.expand_tags(["tile_floor"])
        
        # Check that both the original tag and its implication are present
        self.assertIn("tile_floor", expanded_tags, "Original tag should be present")
        self.assertIn("tiles", expanded_tags, "Implied tag should be present")
        self.assertIn("tile", expanded_tags, "Alias of implied tag should be present")
        
        # Check frequencies
        self.assertEqual(frequencies["tile_floor"], 1, "Original tag should have frequency 1")
        self.assertEqual(frequencies["tiles"], 1, "Implied tag should have frequency 1")
        self.assertEqual(frequencies["tile"], 1, "Alias should have frequency 1")

    def test_multiple_tags_expansion(self):
        """Test expanding multiple tags at once"""
        # Use tile_floor and another tag to test multiple tag handling
        expanded_tags, frequencies = self.expander.expand_tags(["tile_floor", "tiles"])
        
        # All related tags should be present
        self.assertIn("tile_floor", expanded_tags)
        self.assertIn("tiles", expanded_tags)
        self.assertIn("tile", expanded_tags)
        
        # Check frequencies:
        # - tiles appears twice (once from direct inclusion, once from implication)
        # - tile appears twice (as an alias of tiles, which appears twice)
        self.assertEqual(frequencies["tiles"], 2, "tiles should have frequency 2 (direct + implication)")
        self.assertEqual(frequencies["tile"], 2, "tile should have frequency 2 (alias of tiles which appears twice)")
        self.assertEqual(frequencies["tile_floor"], 1, "tile_floor should have frequency 1")

if __name__ == '__main__':
    unittest.main() 