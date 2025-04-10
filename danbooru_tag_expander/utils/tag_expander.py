"""Tag expander utility for Danbooru.

This module provides functionality to expand a set of tags by retrieving
their implications and aliases from the Danbooru API.
"""

import os
import json
import time
import logging
import requests
from collections import Counter
from typing import Dict, List, Set, Tuple
from pybooru import Danbooru
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)

class TagExpander:
    """A utility for expanding Danbooru tags with their implications and aliases."""

    def __init__(self, 
                 username: str = None, 
                 api_key: str = None, 
                 site_url: str = None,
                 use_cache: bool = True,
                 cache_dir: str = None,
                 request_delay: float = 0.5,
                 verbose: bool = True,
                 log_level: int = logging.INFO):
        """Initialize the TagExpander.
        
        Args:
            username: Danbooru username. If None, uses DANBOORU_USERNAME from .env
            api_key: Danbooru API key. If None, uses DANBOORU_API_KEY from .env
            site_url: Danbooru site URL. If None, uses DANBOORU_SITE_URL from .env 
                      or the official Danbooru site
            use_cache: Whether to cache API responses. Will be set to False if no cache_dir is configured
            cache_dir: Directory for cache. If None, uses DANBOORU_CACHE_DIR from .env.
                      If no cache directory is configured, caching will be disabled.
            request_delay: Seconds to wait between API requests
            verbose: Whether to log verbose output
            log_level: Log level to use
        """
        # Get credentials from environment if not provided
        self.username = username or os.getenv("DANBOORU_USERNAME")
        self.api_key = api_key or os.getenv("DANBOORU_API_KEY")
        self.site_url = site_url or os.getenv("DANBOORU_SITE_URL") or "https://danbooru.donmai.us"
        
        # Ensure site_url doesn't end with a slash
        if self.site_url.endswith('/'):
            self.site_url = self.site_url[:-1]

        # Set up Danbooru client
        self.client = Danbooru(site_url=self.site_url, 
                               username=self.username, 
                               api_key=self.api_key)

        # Set up caching
        self.cache_dir = cache_dir or os.getenv("DANBOORU_CACHE_DIR")
        # Only enable caching if a cache directory is configured
        self.use_cache = use_cache and self.cache_dir is not None
        if self.use_cache:
            os.makedirs(self.cache_dir, exist_ok=True)
            if verbose:
                logger.info(f"Caching enabled. Using directory: {self.cache_dir}")
        elif verbose:
            if not use_cache:
                logger.info("Caching disabled by configuration")
            else:
                logger.info("Caching disabled: no cache directory configured")

        # Cache for API responses to reduce API calls
        self._implications_cache = {}
        self._aliases_cache = {}
        
        # Rate limiting
        self.request_delay = request_delay
        self._last_request_time = 0
        
        # Verbosity
        self.verbose = verbose
        
        # Configure logger handler if it doesn't already have one
        if not logger.handlers and verbose:
            self._setup_logger(log_level)
        
    def _setup_logger(self, log_level):
        """Set up the logger with appropriate handlers and formatting."""
        # Create handler for stderr
        handler = logging.StreamHandler()
        # Set level
        logger.setLevel(log_level)
        handler.setLevel(log_level)
        # Create formatter
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        # Add handler to logger
        logger.addHandler(handler)
        
    def _log(self, message, level=logging.INFO):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            logger.log(level, message)

    def _api_request(self, endpoint, params=None):
        """Make an API request to Danbooru.
        
        Args:
            endpoint: API endpoint to call
            params: Query parameters
            
        Returns:
            JSON response parsed into a Python object
        """
        # Apply rate limiting
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.request_delay:
            sleep_time = self.request_delay - time_since_last
            time.sleep(sleep_time)
        
        # Update last request time
        self._last_request_time = time.time()
        
        try:
            self._log(f"Requesting {endpoint} for params {params}...")
            raw_response = self.client._get(endpoint, params)
            if self.verbose:
                print(f"Raw API response: {raw_response}")
            return raw_response
        except Exception as e:
            logger.error(f"Error: {e}")
            if self.verbose:
                logger.error(f"Full error details: {str(e)}")
            return []

    def get_tag_implications(self, tag: str) -> List[str]:
        """Get all tag implications for a given tag.
        
        Args:
            tag: The tag to find implications for
            
        Returns:
            A list of implied tags
        """
        # Check cache first
        if tag in self._implications_cache:
            self._log(f"Using cached implications for '{tag}'")
            return self._implications_cache[tag]
        
        # Check disk cache if enabled
        if self.use_cache:
            cache_file = os.path.join(self.cache_dir, f"implications_{tag}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        implications = json.load(f)
                    self._implications_cache[tag] = implications
                    self._log(f"Loaded implications for '{tag}' from disk cache")
                    return implications
                except Exception as e:
                    logger.error(f"Error reading cache for tag '{tag}': {e}")
        
        # Query the API
        implications = []
        try:
            # Query for direct tag implications
            params = {"search[antecedent_name]": tag}
            response = self._api_request("tag_implications.json", params)
            
            if response and isinstance(response, list):
                # Extract the consequent tags (the implied tags)
                for implication in response:
                    if "consequent_name" in implication and implication.get("status") == "active":
                        implications.append(implication["consequent_name"])
            
            self._log(f"Found {len(implications)} implications for '{tag}'")
        except Exception as e:
            logger.error(f"Error getting implications for tag '{tag}': {e}")
        
        # Cache the result
        self._implications_cache[tag] = implications
        
        # Save to disk cache if enabled
        if self.use_cache:
            try:
                cache_file = os.path.join(self.cache_dir, f"implications_{tag}.json")
                with open(cache_file, 'w') as f:
                    json.dump(implications, f)
                self._log(f"Saved implications for '{tag}' to disk cache")
            except Exception as e:
                logger.error(f"Error saving cache for tag '{tag}': {e}")
        
        return implications

    def get_tag_aliases(self, tag: str) -> List[str]:
        """Get all tag aliases for a given tag.
        
        Args:
            tag: The tag to find aliases for
            
        Returns:
            A list of tag aliases (antecedent names)
        """
        # Check cache first
        if tag in self._aliases_cache:
            self._log(f"Using cached aliases for '{tag}'")
            return self._aliases_cache[tag]
        
        # Check disk cache if enabled
        if self.use_cache:
            cache_file = os.path.join(self.cache_dir, f"aliases_{tag}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        aliases = json.load(f)
                    self._aliases_cache[tag] = aliases
                    self._log(f"Loaded aliases for '{tag}' from disk cache")
                    return aliases
                except Exception as e:
                    logger.error(f"Error reading cache for tag '{tag}': {e}")
        
        # Query the API
        aliases = []
        try:
            # Query for tag aliases using the tags endpoint
            params = {"search[name_matches]": tag, "only": "name,consequent_aliases"}
            response = self._api_request("tags.json", params)
            
            if response and isinstance(response, list) and len(response) > 0:
                # Extract aliases from consequent_aliases field
                alias_dicts = response[0].get("consequent_aliases", [])
                # Extract just the antecedent_name from each alias
                aliases = [alias["antecedent_name"] for alias in alias_dicts if alias.get("status") == "active"]
            
            self._log(f"Found {len(aliases)} aliases for '{tag}'")
        except Exception as e:
            logger.error(f"Error getting aliases for tag '{tag}': {e}")
        
        # Cache the result
        self._aliases_cache[tag] = aliases
        
        # Save to disk cache if enabled
        if self.use_cache:
            try:
                cache_file = os.path.join(self.cache_dir, f"aliases_{tag}.json")
                with open(cache_file, 'w') as f:
                    json.dump(aliases, f)
                self._log(f"Saved aliases for '{tag}' to disk cache")
            except Exception as e:
                logger.error(f"Error saving cache for tag '{tag}': {e}")
        
        return aliases

    def expand_tags(self, tags: List[str]) -> Tuple[Set[str], Counter]:
        """Expand a set of tags with their implications and aliases.
        
        In graph theory terms:
        - Tags form nodes in a directed graph
        - Implications form directed edges between different concepts (A implies B)
        - Aliases form equivalence classes (subgraphs) where all nodes represent the same concept
        
        Frequency calculation:
        - For implications: frequencies sum across different source implications
          (if A implies X and B implies X, then freq(X) = freq(A) + freq(B))
        - For aliases: all nodes in an alias subgraph share the same frequency
          (if X and Y are aliases, then freq(X) = freq(Y) = total frequency of the concept)
        
        Args:
            tags: A list of initial tags to expand
            
        Returns:
            A tuple containing:
            - The final expanded set of tags (with implications and aliases)
            - A Counter with the frequency of each tag in the final set
        """
        # Initial tag set
        tag_set = set(tags)
        
        # Track which tags we've already processed for implications
        processed_tags = set()
        
        # Expanded set with implications (starts with original tags)
        expanded_with_implications = set(tag_set)
        
        # Track which tags contributed to each implication for frequency counting
        implication_sources = {}  # Maps implied tag -> set of source tags
        
        # Process implications until we reach closure (no new tags found)
        self._log("Finding implications for tags (transitive closure)...")
        
        # Queue of tags to process for implications
        queue = list(tag_set)
        
        # Process implications until the queue is empty
        while queue:
            current_tag = queue.pop(0)
            
            # Skip if we've already processed this tag
            if current_tag in processed_tags:
                continue
                
            self._log(f"Processing implications for tag: {current_tag}")
            
            # Get implications for current tag
            implications = self.get_tag_implications(current_tag)
            
            # Process each implication
            for implied_tag in implications:
                # Initialize the sources set if needed
                if implied_tag not in implication_sources:
                    implication_sources[implied_tag] = set()
                
                # Add the current tag as a source for this implication
                implication_sources[implied_tag].add(current_tag)
                
                # Add to expanded set if it's a new tag
                if implied_tag not in expanded_with_implications:
                    expanded_with_implications.add(implied_tag)
                    # Add to queue for further processing
                    queue.append(implied_tag)
            
            # Mark as processed
            processed_tags.add(current_tag)
        
        self._log(f"Implication expansion complete. Found {len(expanded_with_implications)} tags.")
        
        # Now process aliases
        final_expanded_set = set(expanded_with_implications)
        alias_sources = {}  # Maps alias -> set of source tags
        
        self._log(f"Finding aliases for {len(expanded_with_implications)} tags...")
        for i, tag in enumerate(expanded_with_implications):
            self._log(f"Processing aliases for tag {i+1}/{len(expanded_with_implications)}: {tag}")
            aliases = self.get_tag_aliases(tag)
            
            # Process each alias
            for alias in aliases:
                # Initialize the sources set if needed
                if alias not in alias_sources:
                    alias_sources[alias] = set()
                
                # Add the current tag as a source for this alias
                alias_sources[alias].add(tag)
                
                # Add to final set
                final_expanded_set.add(alias)
        
        # Track frequency
        frequency = Counter()
        
        # Count original tags (frequency 1 for each)
        for tag in tags:
            frequency[tag] += 1
        
        # Count implications (frequency = number of sources)
        for implied_tag, sources in implication_sources.items():
            frequency[implied_tag] += len(sources)
        
        # Process aliases (all members of an alias subgraph share the same frequency)
        alias_groups = {}  # Maps canonical tag -> set of aliases (including canonical)
        
        # First, group aliases together
        for alias, sources in alias_sources.items():
            # Use the first source as the canonical tag for this group
            canonical = next(iter(sources))
            if canonical not in alias_groups:
                alias_groups[canonical] = {canonical}
            alias_groups[canonical].add(alias)
            
        # Then ensure all aliases in a group share the same frequency
        for canonical, aliases in alias_groups.items():
            # Sum up all frequencies in the group
            group_freq = sum(frequency[tag] for tag in aliases)
            # Distribute evenly to all members
            for alias in aliases:
                frequency[alias] = group_freq
        
        self._log(f"Expanded {len(tags)} tags to {len(final_expanded_set)} tags")
        return final_expanded_set, frequency 
