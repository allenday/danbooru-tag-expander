#!/usr/bin/env python
"""Example usage of the TagExpander.

This example demonstrates how to use the TagExpander class 
to expand a set of Danbooru tags.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from danbooru_tools.utils.tag_expander import TagExpander
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def main():
    """Run the example."""
    # Check if credentials are available
    if not os.getenv("DANBOORU_API_KEY") or not os.getenv("DANBOORU_USERNAME"):
        print("Error: Please set DANBOORU_USERNAME and DANBOORU_API_KEY "
              "in your .env file or environment variables.")
        sys.exit(1)
    
    # Initialize the tag expander
    expander = TagExpander()
    
    # Example tags to expand
    tags = ["blonde_hair", "blue_eyes", "school_uniform"]
    
    print(f"Expanding tags: {', '.join(tags)}")
    print()
    
    # Expand the tags
    expanded_tags, frequency = expander.expand_tags(tags)
    
    # Display the results
    print(f"Original tags ({len(tags)}):")
    print(", ".join(tags))
    print()
    
    print(f"Expanded tags ({len(expanded_tags)}):")
    # Sort by frequency (highest first)
    for tag in sorted(expanded_tags, key=lambda t: (-frequency[t], t)):
        print(f"  {tag} (frequency: {frequency[tag]})")
    
    print()
    print("Top 5 most frequent tags:")
    for tag, count in frequency.most_common(5):
        print(f"  {tag}: {count}")


if __name__ == "__main__":
    main() 