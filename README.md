# Danbooru Tag Expander

A Python tool for expanding Danbooru tags with their implications and aliases. This tool helps you get a complete set of related tags when working with Danbooru's tagging system.

## Features

- Expand tags with their implications and aliases
- Support for both command-line and programmatic usage
- Configurable output formats (text, JSON, CSV)
- Progress tracking and detailed logging
- Caching support for better performance

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
from danbooru_tools.tag_expander import TagExpander

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