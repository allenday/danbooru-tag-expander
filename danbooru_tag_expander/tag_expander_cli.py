#!/usr/bin/env python
"""Command-line interface for the Danbooru tag expander.

This script allows users to expand a set of Danbooru tags via the command line.
"""

import argparse
import os
import sys
import logging
from typing import List
from dotenv import load_dotenv
from danbooru_tag_expander import TagExpander

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger("danbooru_tag_expander")


def setup_logging(log_level):
    """Set up logging configuration."""
    # Create stderr handler
    handler = logging.StreamHandler(sys.stderr)
    
    # Set level for both logger and handler
    logger.setLevel(log_level)
    handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    
    # Remove existing handlers and add the new one to ensure clean setup
    # This prevents duplicate messages if this function is called multiple times
    # or if a handler was added elsewhere.
    logger.handlers = [handler]


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Expand Danbooru tags with their implications and aliases."
    )
    
    # Create a mutually exclusive group for tags input
    input_group = parser.add_mutually_exclusive_group(required=True)
    
    input_group.add_argument(
        "--tags", "-t", nargs="+", help="One or more tags to expand"
    )
    
    input_group.add_argument(
        "--file", "-f", help="Path to a file containing tags (one per line)"
    )
    
    parser.add_argument(
        "--username", "-u", help="Danbooru username (overrides .env)"
    )
    
    parser.add_argument(
        "--api-key", "-k", help="Danbooru API key (overrides .env)"
    )
    
    parser.add_argument(
        "--site-url", "-s", help="Danbooru site URL (overrides .env)"
    )
    
    parser.add_argument(
        "--no-cache", action="store_true", 
        help="Disable caching of API responses"
    )
    
    parser.add_argument(
        "--cache-dir", "-c", 
        help="Directory for cache (overrides .env)"
    )
    
    parser.add_argument(
        "--format", choices=["text", "json", "csv"], default="text",
        help="Output format (default: text). Options: "
             "text - human-readable format; "
             "json - {'original_tags': [tags], 'expanded_tags': [all expanded tags], "
             "'frequencies': {tag: frequency}}; "
             "csv - two-column format with headers 'tag,frequency'"
    )
    
    parser.add_argument(
        "--sort", choices=["alpha", "freq"], default="freq",
        help="Sort results by name (alpha) or frequency (freq, default)"
    )
    
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between API requests in seconds (default: 0.5)"
    )
    
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Reduce output verbosity (equivalent to --log-level ERROR)"
    )
    
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO", help="Set logging level (default: INFO)"
    )
    
    return parser.parse_args()


def read_tags_from_file(file_path):
    """Read tags from a file, one tag per line.
    
    Args:
        file_path: Path to the file containing tags
        
    Returns:
        List of tags
    """
    try:
        with open(file_path, 'r') as f:
            # Read tags, strip whitespace, and filter out empty lines
            tags = [line.strip() for line in f if line.strip()]
        return tags
    except Exception as e:
        logger.error(f"Error reading tags from file: {e}")
        sys.exit(1)


def expand_tags(tags: List[str], args) -> None:
    """Expand the provided tags and display results.
    
    Args:
        tags: List of tags to expand
        args: Command-line arguments
    """
    # Create the tag expander
    expander = TagExpander(
        username=args.username,
        api_key=args.api_key,
        site_url=args.site_url,
        use_cache=not args.no_cache,
        cache_dir=args.cache_dir,
        request_delay=args.delay,
    )
    
    logger.info(f"Expanding {len(tags)} tags...")
    
    # Expand the tags
    expanded_tags, frequency = expander.expand_tags(tags)
    
    # Display results based on format
    if args.format == "json":
        import json
        result = {
            "original_tags": tags,
            "expanded_tags": list(expanded_tags),
            "frequencies": {tag: count for tag, count in frequency.items()}
        }
        print(json.dumps(result, indent=2))
    elif args.format == "csv":
        import csv
        import io
        
        # Create a string buffer to write CSV to
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        
        # Write header
        writer.writerow(["tag", "frequency"])
        
        # Sort results
        if args.sort == "alpha":
            sorted_tags = sorted(expanded_tags)
        else:  # Sort by frequency
            sorted_tags = sorted(expanded_tags, key=lambda t: (-frequency[t], t))
        
        # Write data rows
        for tag in sorted_tags:
            writer.writerow([tag, frequency[tag]])
        
        # Print the CSV output
        print(output.getvalue(), end='')
    else:
        # Text format
        print(f"Original tags ({len(tags)}):")
        print(", ".join(tags))
        print()
        
        print(f"Expanded tags ({len(expanded_tags)}):")
        
        # Sort results
        if args.sort == "alpha":
            sorted_tags = sorted(expanded_tags)
            for tag in sorted_tags:
                freq = frequency[tag]
                print(f"{tag} (frequency: {freq})")
        else:  # Sort by frequency
            sorted_tags = sorted(expanded_tags, key=lambda t: (-frequency[t], t))
            for tag in sorted_tags:
                freq = frequency[tag]
                print(f"{tag} (frequency: {freq})")


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging based on arguments
    if args.quiet:
        log_level = logging.ERROR
    else:
        log_level = getattr(logging, args.log_level)
    
    setup_logging(log_level)
    
    # Check if required environment variables are set
    if not args.api_key and not os.getenv("DANBOORU_API_KEY"):
        logger.error("Danbooru API key is required. "
                   "Provide it with --api-key or set DANBOORU_API_KEY in .env file.")
        sys.exit(1)
    
    if not args.username and not os.getenv("DANBOORU_USERNAME"):
        logger.error("Danbooru username is required. "
                   "Provide it with --username or set DANBOORU_USERNAME in .env file.")
        sys.exit(1)
    
    # Get tags either from command line or file
    if args.file:
        tags = read_tags_from_file(args.file)
    else:
        tags = args.tags
    
    # Expand tags
    expand_tags(tags, args)


if __name__ == "__main__":
    main() 
