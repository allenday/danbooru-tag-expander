# Danbooru Tag Expander

A Python tool for expanding Danbooru tags with their implications and aliases. This tool helps you get a complete set of related tags when working with Danbooru's tagging system.

## Features

- Expand tags with their implications and aliases
- **High-performance semantic relationship methods** for efficient tag processing
- **Correct directed alias handling** - aliases are treated as antecedent → consequent relationships
- Support for both command-line and programmatic usage
- Configurable output formats (text, JSON, CSV)
- Progress tracking and detailed logging
- Caching support for better performance

## Important: Directed Alias Relationships

**Fixed in v0.2.4**: Danbooru aliases are now correctly handled as **directed relationships** (antecedent → consequent) instead of bidirectional equivalences.

### What Changed

- **Before**: `get_aliases()` returned bidirectional relationships, treating deprecated and canonical tags as equivalent
- **After**: `get_aliases()` returns only outgoing aliases (antecedent → consequent), correctly identifying deprecated tags

### New API Methods

```python
# Get outgoing aliases (what this tag redirects to)
canonical_tags = expander.get_aliases("ugly_man")  # ["ugly_bastard"]

# Get incoming aliases (what tags redirect to this one)  
deprecated_tags = expander.get_aliased_from("ugly_bastard")  # ["ugly_man"]

# Check if a tag is canonical (preferred) vs deprecated
is_preferred = expander.is_canonical("ugly_bastard")  # True
is_deprecated = expander.is_canonical("ugly_man")     # False
```

### Impact on Applications

- **Graph topology**: Now correctly shows directed alias edges instead of bidirectional
- **Tag normalization**: Can distinguish canonical from deprecated tags
- **Semantic analysis**: Proper sink/source node identification in graphs

## Performance Optimization

**New in v0.2.3**: High-performance semantic relationship methods that provide complete transitive relationships without the overhead of full tag expansion:

- **27,000+ tags/second** throughput for cached relationships
- **No API calls** required for cached data
- **Complete semantic relationships** including transitive implications and directed aliases
- **Ideal for large-scale processing** of thousands of tags

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

### Advanced Usage: High-Performance Semantic Relationships

For applications that need complete semantic relationships without the overhead of full tag expansion, use the new high-performance methods:

```python
from danbooru_tag_expander import TagExpander

expander = TagExpander(
    username="your-username",
    api_key="your-api-key",
    use_cache=True
)

# First, ensure tags are cached (one-time cost)
expander.expand_tags(["aqua_bikini"])  # Populates cache via API

# Now use high-performance methods (no API calls, very fast)
tag = "aqua_bikini"

# Get direct implications only
direct_implications = expander.get_implications(tag)
# Returns: ["bikini", "swimwear", "clothing"]

# Get complete transitive implications (follows the full chain)
transitive_implications = expander.get_transitive_implications(tag)
# Returns: {"bikini", "swimwear", "clothing"} - includes all levels

# Get direct aliases
aliases = expander.get_aliases(tag)

# Get complete alias group (all equivalent tags)
alias_group = expander.get_alias_group(tag)

# Get comprehensive semantic relationships
relations = expander.get_semantic_relations(tag)
# Returns: {
#   'direct_implications': [...],
#   'transitive_implications': {...},
#   'direct_aliases': [...],
#   'alias_group': {...},
#   'all_related': {...}  # All semantically related tags
# }

# Check if tag relationships are cached
if expander.is_tag_cached(tag):
    # Safe to use high-performance methods
    all_related = expander.get_semantic_relations(tag)['all_related']
else:
    # Need to populate cache first
    expander.expand_tags([tag])
```

#### Performance Comparison

```python
# Traditional approach (slower, includes frequency calculations)
expanded_tags, frequencies = expander.expand_tags(["aqua_bikini"])

# New high-performance approach (faster, semantic relationships only)
relations = expander.get_semantic_relations("aqua_bikini")
all_related = {tag}.union(relations['all_related'])

# Performance difference:
# - Traditional: ~4.6 tags/second (requires API calls + frequency calculation)
# - High-performance: 27,000+ tags/second (cached graph traversal only)
```

#### Use Cases

The high-performance semantic methods are ideal for:

- **Building tag graphs** for large datasets (thousands of tags)
- **Real-time tag suggestion** systems
- **Semantic analysis** without frequency calculations
- **Batch processing** where you need relationships but not frequencies
- **Tag validation and expansion** in user interfaces

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