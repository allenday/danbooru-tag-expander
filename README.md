# Danbooru Tag Expander

A Python tool for expanding Danbooru tags with their implications and aliases. This tool helps you get a complete set of related tags when working with Danbooru's tagging system.

## Features

- Expand tags with their implications and aliases
- Support for both command-line and programmatic usage
- Configurable output formats (text, JSON, CSV)
- Progress tracking and detailed logging
- Caching support for better performance

## Graph Theory Concepts

The tag expansion system can be understood through graph theory:

### Tag Graph Structure
- Tags are nodes in a directed graph
- Two types of edges exist:
  1. Implications: Directed edges between different concepts (A → B means "A implies B")
  2. Aliases: Form equivalence classes (subgraphs) where all nodes represent the same concept

### Frequency Calculation
- For implications:
  - Multiple implications to the same tag sum their frequencies
  - Example: If A implies X and B implies X, then freq(X) = freq(A) + freq(B)
- For aliases:
  - All nodes in an alias subgraph share the same frequency
  - Example: If X and Y are aliases, then freq(X) = freq(Y) = total frequency of their concept
  - This reflects that aliases are different names for the same underlying concept

### Example
```
Given:
- Tags: [cat, feline, kitten]
- Aliases: cat ↔ feline (they're the same concept)
- Implications: kitten → cat

Results:
- Expanded tags: [cat, feline, kitten]
- Frequencies:
  - cat: 2 (1 from original + 1 from kitten implication)
  - feline: 2 (same as cat since they're aliases)
  - kitten: 1 (from original tag)
```

## Installation

You can install the package using pip:

```bash
pip install danbooru-tag-expander
```

## Usage

### Command Line

```bash
# Basic usage with tags
danbooru-tag-expander --tags "1girl" "solo"

# Using a file containing tags
danbooru-tag-expander --file tags.txt

# Output in different formats
danbooru-tag-expander --tags "1girl" --format json
danbooru-tag-expander --tags "1girl" --format csv

# Control logging verbosity
danbooru-tag-expander --tags "1girl" --quiet
danbooru-tag-expander --tags "1girl" --log-level DEBUG
```

### Python API

```python
from danbooru_tag_expander.tag_expander import TagExpander

# Create an expander instance
expander = TagExpander(
    username="your-username",  # Optional, can be set via environment
    api_key="your-api-key",    # Optional, can be set via environment
    use_cache=True             # Enable caching for better performance
)

# Expand tags
expanded_tags, frequencies = expander.expand_tags(["1girl", "solo"])

# Print results
print(f"Original tags: 1girl, solo")
print(f"Expanded tags: {', '.join(expanded_tags)}")
```

### Advanced Usage: External Graph Injection

For advanced use cases, you can inject an external `DanbooruTagGraph` instance from the separate [`danbooru-tag-graph`](https://pypi.org/project/danbooru-tag-graph/) package:

```python
from danbooru_tag_expander.tag_expander import TagExpander
from danbooru_tag_graph import DanbooruTagGraph

# Create and populate an external graph
graph = DanbooruTagGraph()
graph.add_tag("cat", fetched=True)
graph.add_tag("animal", fetched=True)
graph.add_implication("cat", "animal")

# Use the external graph
expander = TagExpander(
    username="your-username",
    api_key="your-api-key",
    tag_graph=graph  # Inject external graph
)

# This will use the pre-populated graph data
expanded_tags, frequencies = expander.expand_tags(["cat"])
```

This approach is useful for:
- Pre-loading tag relationships from external sources
- Sharing graph instances between multiple expanders
- Custom caching strategies
- Integration with external tag management systems

The [`danbooru-tag-graph`](https://pypi.org/project/danbooru-tag-graph/) package can also be used independently for graph-based tag relationship management.

## Configuration

The tool can be configured using environment variables or command-line arguments:

- `DANBOORU_USERNAME`: Your Danbooru username
- `DANBOORU_API_KEY`: Your Danbooru API key
- `DANBOORU_SITE_URL`: Custom Danbooru instance URL (optional)
- `DANBOORU_CACHE_DIR`: Custom cache directory location (optional)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.