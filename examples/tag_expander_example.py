#!/usr/bin/env python3
"""Example usage of the tag expander."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Danbooru credentials from environment
username = os.getenv("DANBOORU_USERNAME")
api_key = os.getenv("DANBOORU_API_KEY")

from danbooru_tag_expander.utils.tag_expander import TagExpander

def main():
    """Run the example."""
    # Initialize the tag expander
    expander = TagExpander(
        username=username,
        api_key=api_key,
    )

    # Example tags to expand
    tags = ["1girl", "solo"]

    # Expand the tags
    expanded_tags, frequency = expander.expand_tags(tags)

    # Print the results
    print(f"Original tags: {tags}")
    print(f"Expanded tags: {expanded_tags}")
    print("Tag frequencies:")
    for tag, count in frequency.most_common():
        print(f"  {tag}: {count}")

if __name__ == "__main__":
    main() 