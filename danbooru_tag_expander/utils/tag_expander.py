"""Tag expander utility for Danbooru.

This module provides functionality to expand a set of tags by retrieving
their implications and aliases from the Danbooru API using a high-performance
NetworkX graph-based cache system.
"""

import os
import time
import logging
from collections import Counter
from typing import List, Set, Tuple
from pybooru import Danbooru
from dotenv import load_dotenv

from danbooru_tag_graph import DanbooruTagGraph

# Load environment variables from .env file
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)

class TagExpander:
    """A utility for expanding Danbooru tags with their implications and aliases using graph cache."""

    def __init__(self, 
                 username: str = None, 
                 api_key: str = None, 
                 site_url: str = None,
                 use_cache: bool = True,
                 cache_dir: str = None,
                 request_delay: float = 0.5,
                 tag_graph: DanbooruTagGraph = None):
        """Initialize the TagExpander.
        
        Args:
            username: Danbooru username. If None, uses DANBOORU_USERNAME from .env
            api_key: Danbooru API key. If None, uses DANBOORU_API_KEY from .env
            site_url: Danbooru site URL. If None, uses DANBOORU_SITE_URL from .env 
                      or the official Danbooru site
            use_cache: Whether to use graph cache. Will be set to False if no cache_dir is configured
            cache_dir: Directory for cache. If None, uses DANBOORU_CACHE_DIR from .env.
                      If no cache directory is configured, caching will be disabled.
            request_delay: Seconds to wait between API requests
            tag_graph: External DanbooruTagGraph instance to use. If provided, cache settings are ignored.
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

        # Set up graph cache
        if tag_graph is not None:
            # Use externally provided graph
            self.tag_graph = tag_graph
            self.use_cache = True
            logger.info("Using externally provided DanbooruTagGraph")
        elif use_cache:
            # Set up internal graph cache
            self.cache_dir = cache_dir or os.getenv("DANBOORU_CACHE_DIR")
            self.use_cache = self.cache_dir is not None
            
            if self.use_cache:
                os.makedirs(self.cache_dir, exist_ok=True)
                
                # Use graph-based cache
                graph_cache_file = os.path.join(self.cache_dir, "danbooru_tag_graph.pickle")
                self.tag_graph = DanbooruTagGraph(cache_file=graph_cache_file)
                
                # Import from old JSON cache if graph is empty and JSON files exist
                if (self.tag_graph.graph.number_of_nodes() == 0 and 
                    any(f.endswith('.json') for f in os.listdir(self.cache_dir) if os.path.isfile(os.path.join(self.cache_dir, f)))):
                    logger.info("Migrating from JSON cache to graph cache...")
                    self.tag_graph.import_from_json_cache(self.cache_dir)
                    self.tag_graph.save_graph()
                    logger.info("Migration complete")
                
                logger.info(f"Graph cache enabled. Cache file: {graph_cache_file}")
                stats = self.tag_graph.stats()
                logger.info(f"Graph stats: {stats}")
            else:
                self.tag_graph = None
                logger.info("Caching disabled: no cache directory configured")
        else:
            self.tag_graph = None
            self.use_cache = False
            logger.info("Caching disabled by configuration")
        
        # Rate limiting
        self.request_delay = request_delay
        self._last_request_time = 0
        
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
            logger.debug(f"Requesting {endpoint} with params {params}...")
            raw_response = self.client._get(endpoint, params)
            logger.debug(f"Raw API response: {raw_response}")
            return raw_response
        except Exception as e:
            logger.error(f"Error: {e}")
            logger.exception(f"Full error details during API request to {endpoint}:")
            return []

    def expand_tags(self, tags: List[str]) -> Tuple[Set[str], Counter]:
        """Expand a set of tags with their implications and aliases.

        Calculates frequencies based on the following rules:
        1. Original input tags start with a frequency of 1.
        2. Implications add frequency: If A implies B, freq(B) increases by freq(A).
           This is applied transitively.
        3. Aliases share frequency: If X and Y are aliases, freq(X) == freq(Y).
           This is based on the combined frequency of their conceptual group.

        Args:
            tags: A list of initial tags to expand

        Returns:
            A tuple containing:
            - The final expanded set of tags (with implications and aliases)
            - A Counter with the frequency of each tag in the final set
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot expand tags without cache.")
        
        logger.info(f"Expanding {len(tags)} tags using graph cache...")
        
        # Ensure all required tags are fetched
        self._ensure_tags_fetched(tags)
        
        # Use graph for expansion
        expanded_tags, frequencies = self.tag_graph.expand_tags(tags, include_deprecated=False)
        
        logger.info(f"Expanded {len(tags)} tags to {len(expanded_tags)} tags using graph cache")
        return expanded_tags, Counter(frequencies)
    
    def _ensure_tags_fetched(self, initial_tags: List[str]) -> None:
        """Ensure all tags and their transitive relationships are fetched."""
        to_process = set(initial_tags)
        
        while to_process:
            # Get unfetched tags from current batch
            unfetched = self.tag_graph.get_unfetched_tags(list(to_process))
            
            if unfetched:
                logger.debug(f"Fetching data for {len(unfetched)} unfetched tags...")
                newly_discovered = self._fetch_and_populate_tags(unfetched)
                to_process.update(newly_discovered)
                self.tag_graph.auto_save()
            
            # Remove processed tags
            to_process -= set(unfetched) if unfetched else to_process
    
    def _fetch_and_populate_tags(self, tags: List[str]) -> Set[str]:
        """Fetch and populate tag data, returning newly discovered tags."""
        newly_discovered = set()
        
        for tag in tags:
            logger.debug(f"Fetching data for tag: {tag}")
            
            # Check deprecated status
            is_deprecated = self._fetch_tag_deprecated_status(tag)
            
            if not is_deprecated:
                # Get implications and aliases from API
                implications = self._fetch_tag_implications(tag)
                aliases = self._fetch_tag_aliases(tag)
                
                # Add to graph with fetched=True
                self.tag_graph.add_tag(tag, is_deprecated=is_deprecated, fetched=True)
                
                for implied_tag in implications:
                    self.tag_graph.add_implication(tag, implied_tag)
                    newly_discovered.add(implied_tag)
                
                for alias_tag in aliases:
                    self.tag_graph.add_alias(tag, alias_tag)
                    newly_discovered.add(alias_tag)
            else:
                # Just add the deprecated tag as fetched
                self.tag_graph.add_tag(tag, is_deprecated=True, fetched=True)
        
        return newly_discovered
    
    def _fetch_tag_deprecated_status(self, tag: str) -> bool:
        """Fetch deprecated status from API."""
        try:
            params = {"search[name]": tag, "only": "name,is_deprecated"}
            response = self._api_request("tags.json", params)
            
            if response and isinstance(response, list) and len(response) > 0:
                tag_info = response[0]
                return tag_info.get("is_deprecated", False)
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking if tag '{tag}' is deprecated: {e}")
            return False
    
    def _fetch_tag_implications(self, tag: str) -> List[str]:
        """Fetch implications from API."""
        implications = []
        try:
            params = {"search[antecedent_name]": tag}
            response = self._api_request("tag_implications.json", params)
            
            if response and isinstance(response, list):
                for implication in response:
                    if "consequent_name" in implication and implication.get("status") == "active":
                        consequent_tag = implication["consequent_name"]
                        # Only add if consequent is not deprecated
                        if not self._fetch_tag_deprecated_status(consequent_tag):
                            implications.append(consequent_tag)
            
            logger.debug(f"Found {len(implications)} implications for '{tag}'")
        except Exception as e:
            logger.error(f"Error getting implications for tag '{tag}': {e}")
        
        return implications
    
    def _fetch_tag_aliases(self, tag: str) -> List[str]:
        """Fetch aliases from API."""
        aliases = []
        try:
            params = {"search[name_matches]": tag, "only": "name,consequent_aliases"}
            response = self._api_request("tags.json", params)
            
            if response and isinstance(response, list) and len(response) > 0:
                alias_dicts = response[0].get("consequent_aliases", [])
                for alias in alias_dicts:
                    if alias.get("status") == "active":
                        alias_name = alias["antecedent_name"]
                        # Only add if alias is not deprecated
                        if not self._fetch_tag_deprecated_status(alias_name):
                            aliases.append(alias_name)
            
            logger.debug(f"Found {len(aliases)} aliases for '{tag}'")
        except Exception as e:
            logger.error(f"Error getting aliases for tag '{tag}': {e}")
        
        return aliases 
