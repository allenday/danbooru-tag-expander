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


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded (HTTP 429)."""
    pass


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
            
        Raises:
            RateLimitError: When HTTP 429 rate limit is exceeded
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
        except KeyError as e:
            # Check if this is a 429 KeyError from pybooru bug
            # pybooru throws KeyError when it encounters HTTP 429 because
            # 429 is not in its HTTP_STATUS_CODE mapping
            if "429" in str(e):
                logger.warning(f"Rate limit detected (HTTP 429) for {endpoint} with params {params}")
                raise RateLimitError(f"Rate limit exceeded for {endpoint}. Try again later.") from e
            else:
                logger.error(f"Unexpected KeyError: {e}")
                logger.exception(f"KeyError during API request to {endpoint}:")
                return []
        except Exception as e:
            # Check if this is a rate limit related error in the exception message
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in ['rate limit', 'too many requests', '429', 'throttled']):
                logger.warning(f"Rate limit detected in exception for {endpoint}: {e}")
                raise RateLimitError(f"Rate limit exceeded for {endpoint}: {e}") from e
            
            logger.error(f"API request error for {endpoint}: {e}")
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
            
        Raises:
            RuntimeError: When graph cache is not enabled
            RateLimitError: When API rate limit is exceeded (HTTP 429)
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot expand tags without cache.")
        
        logger.info(f"Expanding {len(tags)} tags using thread-safe graph cache...")
        
        # Ensure all required tags are fetched (thread-safe)
        # This may raise RateLimitError which will propagate to caller
        self._ensure_all_tags_fetched(tags)
        
        # Use thread-safe graph expansion
        expanded_tags, frequencies = self.tag_graph.expand_tags(tags, include_deprecated=False)
        
        logger.info(f"Expanded {len(tags)} tags to {len(expanded_tags)} tags")
        return expanded_tags, Counter(frequencies)
    
    def _ensure_all_tags_fetched(self, initial_tags: List[str]) -> None:
        """Ensure all tags and their transitive relationships are fetched (simplified).
        
        Raises:
            RateLimitError: When rate limit is exceeded during API calls
        """
        to_process = set(initial_tags)
        
        while to_process:
            # Thread-safe check for unfetched tags
            unfetched = self.tag_graph.get_unfetched_tags(list(to_process))
            
            if unfetched:
                logger.debug(f"Fetching data for {len(unfetched)} unfetched tags...")
                try:
                    newly_discovered = self._batch_fetch_tags(unfetched)
                    to_process.update(newly_discovered)
                    # Thread-safe auto-save
                    self.tag_graph.auto_save()
                except RateLimitError:
                    # Re-raise rate limit errors so expand_tags can handle them
                    raise
            else:
                break
    
    def _batch_fetch_tags(self, tags: List[str]) -> Set[str]:
        """Batch fetch and populate tag data (simplified with thread-safe operations).
        
        Raises:
            RateLimitError: When rate limit is exceeded during API calls
        """
        newly_discovered = set()
        
        for tag in tags:
            logger.debug(f"Fetching data for tag: {tag}")
            
            try:
                # Check deprecated status
                is_deprecated = self._fetch_tag_deprecated_status(tag)
                
                if not is_deprecated:
                    # Get implications and aliases from API
                    implications = self._fetch_tag_implications(tag)
                    aliases = self._fetch_tag_aliases(tag)
                    
                    # Thread-safe graph operations
                    self.tag_graph.add_tag(tag, is_deprecated=False, fetched=True)
                    
                    for implied_tag in implications:
                        self.tag_graph.add_implication(tag, implied_tag)
                        newly_discovered.add(implied_tag)
                    
                    for alias_tag in aliases:
                        self.tag_graph.add_alias(tag, alias_tag)
                        newly_discovered.add(alias_tag)
                else:
                    # Thread-safe add deprecated tag
                    self.tag_graph.add_tag(tag, is_deprecated=True, fetched=True)
            except RateLimitError:
                # Re-raise rate limit errors so applications can handle them
                logger.warning(f"Rate limit exceeded while fetching tag '{tag}' - stopping batch")
                raise
        
        return newly_discovered
    
    def _fetch_tag_deprecated_status(self, tag: str) -> bool:
        """Fetch deprecated status from API.
        
        Raises:
            RateLimitError: When rate limit is exceeded
        """
        try:
            params = {"search[name]": tag, "only": "name,is_deprecated"}
            response = self._api_request("tags.json", params)
            
            if response and isinstance(response, list) and len(response) > 0:
                tag_info = response[0]
                return tag_info.get("is_deprecated", False)
            else:
                return False
        except RateLimitError:
            # Re-raise rate limit errors so they can be handled by caller
            raise
        except Exception as e:
            logger.error(f"Error checking if tag '{tag}' is deprecated: {e}")
            return False
    
    def _fetch_tag_implications(self, tag: str) -> List[str]:
        """Fetch implications from API.
        
        Raises:
            RateLimitError: When rate limit is exceeded
        """
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
        except RateLimitError:
            # Re-raise rate limit errors so they can be handled by caller
            raise
        except Exception as e:
            logger.error(f"Error getting implications for tag '{tag}': {e}")
        
        return implications
    
    def _fetch_tag_aliases(self, tag: str) -> List[str]:
        """Fetch aliases from API.
        
        Raises:
            RateLimitError: When rate limit is exceeded
        """
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
        except RateLimitError:
            # Re-raise rate limit errors so they can be handled by caller
            raise
        except Exception as e:
            logger.error(f"Error getting aliases for tag '{tag}': {e}")
        
        return aliases 

    # High-performance semantic relationship methods
    # These methods provide fast access to cached relationships without full expansion overhead
    
    def get_implications(self, tag: str, include_deprecated: bool = False) -> List[str]:
        """Get direct implications for a tag from cached graph data.
        
        This method returns only the direct implications (one level) without
        transitive expansion. For complete transitive implications, use
        get_transitive_implications().
        
        Args:
            tag: The tag to get implications for
            include_deprecated: Whether to include deprecated implied tags
            
        Returns:
            List of directly implied tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot get implications without cache.")
        
        return self.tag_graph.get_implications(tag, include_deprecated=include_deprecated)
    
    def get_transitive_implications(self, tag: str, include_deprecated: bool = False) -> Set[str]:
        """Get all transitive implications for a tag from cached graph data.
        
        This method efficiently traverses the cached graph to find all tags
        that are transitively implied by the given tag, without the overhead
        of full tag expansion or frequency calculations.
        
        Performance: Uses cached graph traversal - no API calls required if
        tag relationships are already cached.
        
        Args:
            tag: The tag to get transitive implications for
            include_deprecated: Whether to include deprecated implied tags
            
        Returns:
            Set of all transitively implied tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot get transitive implications without cache.")
        
        return self.tag_graph.get_transitive_implications(tag, include_deprecated=include_deprecated)
    
    def get_aliases(self, tag: str, include_deprecated: bool = False) -> List[str]:
        """Get direct aliases for a tag from cached graph data.
        
        This method returns the direct aliases of a tag. For all tags in the
        same alias group (transitive aliases), use get_alias_group().
        
        Args:
            tag: The tag to get aliases for
            include_deprecated: Whether to include deprecated aliases
            
        Returns:
            List of alias tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot get aliases without cache.")
        
        return self.tag_graph.get_aliases(tag, include_deprecated=include_deprecated)
    
    def get_alias_group(self, tag: str, include_deprecated: bool = False) -> Set[str]:
        """Get all tags in the same alias group (transitive aliases) from cached graph data.
        
        This method efficiently finds all tags that are transitively connected
        through alias relationships, representing the complete equivalence class
        for the given tag.
        
        Performance: Uses cached graph traversal - no API calls required if
        tag relationships are already cached.
        
        Args:
            tag: The tag to get the alias group for
            include_deprecated: Whether to include deprecated tags
            
        Returns:
            Set of all tags in the same alias group
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot get alias group without cache.")
        
        return self.tag_graph.get_alias_group(tag, include_deprecated=include_deprecated)
    
    def get_semantic_relations(self, tag: str, include_deprecated: bool = False) -> dict:
        """Get complete semantic relationships for a tag from cached graph data.
        
        This method provides a comprehensive view of all semantic relationships
        for a tag, including both direct and transitive implications and aliases.
        
        Performance: Uses cached graph traversal - significantly faster than
        expand_tags() as it avoids API calls and frequency calculations.
        
        Args:
            tag: The tag to get semantic relations for
            include_deprecated: Whether to include deprecated tags
            
        Returns:
            Dictionary containing:
            - 'direct_implications': List of directly implied tags
            - 'transitive_implications': Set of all transitively implied tags  
            - 'direct_aliases': List of direct aliases
            - 'alias_group': Set of all tags in the same alias group
            - 'all_related': Set of all semantically related tags
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot get semantic relations without cache.")
        
        # Get all relationship types
        direct_implications = self.get_implications(tag, include_deprecated)
        transitive_implications = self.get_transitive_implications(tag, include_deprecated)
        direct_aliases = self.get_aliases(tag, include_deprecated)
        alias_group = self.get_alias_group(tag, include_deprecated)
        
        # Combine all related tags
        all_related = set()
        all_related.update(transitive_implications)
        all_related.update(alias_group)
        # Remove the original tag from all_related if it's in alias_group
        all_related.discard(tag)
        
        return {
            'direct_implications': direct_implications,
            'transitive_implications': transitive_implications,
            'direct_aliases': direct_aliases,
            'alias_group': alias_group,
            'all_related': all_related
        }
    
    def is_tag_cached(self, tag: str) -> bool:
        """Check if a tag's relationships are cached (fetched) in the graph.
        
        This method allows you to determine whether semantic relationship
        methods will return complete data or if the tag needs to be fetched
        first via expand_tags() or API calls.
        
        Args:
            tag: The tag to check
            
        Returns:
            True if tag relationships are cached, False otherwise
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot check cache status without cache.")
        
        return self.tag_graph.is_tag_fetched(tag) 
