"""Tag expander utility for Danbooru.

This module provides functionality to expand a set of tags by retrieving
their implications and aliases from the Danbooru API using a high-performance
NetworkX graph-based cache system.
"""

import os
import time
import logging
from collections import Counter
from typing import List, Set, Tuple, Dict, Union, Any
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
            self.use_cache = bool(self.cache_dir)
            
            if self.use_cache:
                os.makedirs(self.cache_dir, exist_ok=True)
                
                # Use graph-based cache
                graph_cache_file = os.path.join(self.cache_dir, "danbooru_tag_graph.pickle")
                self.tag_graph = DanbooruTagGraph(cache_file=graph_cache_file)
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
        
    def _api_request(self, endpoint: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Make an API request with rate limit handling.

        Args:
            endpoint: API endpoint to call
            params: Query parameters

        Returns:
            List of response objects

        Raises:
            RateLimitError: When API rate limit is exceeded
        """
        try:
            response = self.client._get(endpoint, params)
            return response
        except KeyError as e:
            # Handle pybooru bug where rate limit returns KeyError with '429'
            if str(e) == "'429'":
                raise RateLimitError(f"Rate limit exceeded for {endpoint}. Try again later.") from e
            return []  # Return empty list for other KeyErrors
        except Exception as e:
            # Check if error message indicates rate limit
            if any(phrase in str(e).lower() for phrase in ["rate limit", "too many requests"]):
                raise RateLimitError(f"Rate limit exceeded for {endpoint}: {str(e)}") from e
            return []  # Return empty list for other exceptions

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
            RuntimeError: When graph cache is not enabled and use_cache is True
        """
        if self.use_cache:
            self._validate_cache_enabled()
        else:
            raise RuntimeError("Graph cache is not enabled. Cannot expand tags without cache.")

        # Populate graph for all initial tags to ensure data is available
        for tag in tags:
            self._populate_graph_for_tag(tag)

        # Step 1: Resolve input tags to canonical forms and set initial frequencies.
        canonical_frequencies = Counter()
        for tag in tags:
            alias_group = self.get_alias_group(tag)
            canonical_tag = next((t for t in alias_group if self.is_canonical(t)), tag)
            canonical_frequencies[canonical_tag] += 1

        # Step 2: Expand implications and aggregate frequencies using a topological-like traversal.
        final_frequencies = canonical_frequencies.copy()
        
        tags_to_process = list(canonical_frequencies.keys())
        head = 0
        while head < len(tags_to_process):
            current_tag = tags_to_process[head]
            head += 1
            
            parent_freq = final_frequencies[current_tag]
            
            for implied_tag in self.get_implications(current_tag):
                final_frequencies[implied_tag] += parent_freq
                
                if implied_tag not in tags_to_process:
                    tags_to_process.append(implied_tag)
                    
        expanded_tags = set(final_frequencies.keys())

        # Step 3: Expand aliases and distribute the final calculated frequencies.
        final_expanded_tags = set()
        final_alias_frequencies = Counter()
        
        processed_for_aliases = set()
        for tag in expanded_tags:
            if tag in processed_for_aliases:
                continue
                
            alias_group = self.get_alias_group(tag)
            
            # Sum the frequencies of all members of the alias group that are in our expanded set.
            total_alias_freq = sum(final_frequencies[t] for t in alias_group if t in expanded_tags)
            
            # Assign this total frequency to all members of the alias group.
            for alias in alias_group:
                final_alias_frequencies[alias] = total_alias_freq
                final_expanded_tags.add(alias)
            
            processed_for_aliases.update(alias_group)

        if self.use_cache and self.tag_graph:
            self.tag_graph.auto_save()

        return final_expanded_tags, final_alias_frequencies

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
        
        # CRITICAL: Validate and fix any bidirectional alias issues after processing
        self._validate_alias_directionality()
    
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
                    
                    # CRITICAL FIX: Only add alias if this tag is actually an antecedent
                    # The _fetch_tag_aliases method already filters for antecedent relationships,
                    # but we need to ensure we're not creating bidirectional relationships
                    for alias_tag in aliases:
                        # Add directed alias relationship: tag (antecedent) -> alias_tag (consequent)
                        # This means 'tag' is deprecated and redirects to 'alias_tag'
                        logger.debug(f"Adding directed alias: {tag} -> {alias_tag}")
                        self.tag_graph.graph.add_edge(tag, alias_tag, edge_type='alias')
                        newly_discovered.add(alias_tag)
                        
                        # CRITICAL: Ensure the consequent tag is also marked as fetched
                        # but do NOT fetch its aliases to avoid bidirectional creation
                        if not self.tag_graph.is_tag_fetched(alias_tag):
                            logger.debug(f"Marking consequent tag as fetched: {alias_tag}")
                            self.tag_graph.add_tag(alias_tag, is_deprecated=False, fetched=True)
                else:
                    # Thread-safe add deprecated tag
                    self.tag_graph.add_tag(tag, is_deprecated=True, fetched=True)
            except RateLimitError:
                # Re-raise rate limit errors so applications can handle them
                logger.warning(f"Rate limit exceeded while fetching tag '{tag}' - stopping batch")
                raise
        
        return newly_discovered
    
    def _populate_graph_for_tag(self, tag: str) -> None:
        """Populate the graph with a tag and its relationships.

        Args:
            tag: The tag to populate
        """
        if not self.tag_graph:
            return

        # Skip if tag is already in graph and fully fetched
        if self.tag_graph.is_tag_fetched(tag):
            return

        # Add or update the tag, marking it as fetched
        is_deprecated = self._fetch_tag_deprecated_status(tag)
        self.tag_graph.add_tag(tag, is_deprecated=is_deprecated, fetched=True)

        # If the tag is deprecated, we don't need to fetch its implications or aliases,
        # but we should fetch the tag it aliases to.
        if is_deprecated:
            aliases = self._fetch_tag_aliases(tag)
            for alias in aliases:
                self.tag_graph.graph.add_edge(tag, alias, edge_type='alias')
                # Recursively populate the canonical tag
                self._populate_graph_for_tag(alias)
            return

        # Get implications and add them to the graph
        implications = self._fetch_tag_implications(tag)
        for implied_tag in implications:
            self.tag_graph.add_implication(tag, implied_tag)
            # Recursively populate implications for the implied tag
            self._populate_graph_for_tag(implied_tag)

        # Get aliases and add them to the graph
        aliases = self._fetch_tag_aliases(tag)
        for alias in aliases:
            self.tag_graph.graph.add_edge(tag, alias, edge_type='alias')
            # Recursively populate aliases
            self._populate_graph_for_tag(alias)

    def _fetch_tag_implications(self, tag: str) -> List[str]:
        """Fetch implications for a tag from the API.

        Args:
            tag: The tag to fetch implications for

        Returns:
            List of implied tags
        """
        try:
            params = {"search[antecedent_name]": tag}
            response = self._api_request("tag_implications.json", params)
            if not response:
                return []
            return [item["consequent_name"] for item in response if item["status"] == "active" and not self._fetch_tag_deprecated_status(item["consequent_name"])]
        except Exception as e:
            if isinstance(e, KeyError) and str(e) == "'429'":
                raise RateLimitError(f"Rate limit exceeded for {tag}") from e
            elif any(phrase in str(e).lower() for phrase in ["rate limit", "too many requests"]):
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            logger.error(f"Error fetching implications for {tag}: {e}")
            return []

    def _fetch_tag_aliases(self, tag: str) -> List[str]:
        """Fetch aliases for a tag from the API.

        Args:
            tag: The tag to fetch aliases for

        Returns:
            List of alias tags
        """
        try:
            params = {"search[antecedent_name]": tag}
            response = self._api_request("tag_aliases.json", params)
            if not response:
                return []
            return [
                item["consequent_name"]
                for item in response
                if item["status"] == "active"
                and item.get("antecedent_name") == tag
                and not self._fetch_tag_deprecated_status(item["consequent_name"])
            ]
        except Exception as e:
            if isinstance(e, KeyError) and str(e) == "'429'":
                raise RateLimitError(f"Rate limit exceeded for {tag}") from e
            elif any(phrase in str(e).lower() for phrase in ["rate limit", "too many requests"]):
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            logger.error(f"Error fetching aliases for {tag}: {e}")
            return []

    def _fetch_tag_deprecated_status(self, tag: str) -> bool:
        """Fetch deprecated status for a tag from the API.

        Args:
            tag: The tag to fetch status for

        Returns:
            True if the tag is deprecated, False otherwise
        """
        try:
            params = {"search[name]": tag}
            response = self._api_request("tags.json", params)
            if not response:
                return False
            return response[0].get("is_deprecated", False)
        except Exception as e:
            if isinstance(e, KeyError) and str(e) == "'429'":
                raise RateLimitError(f"Rate limit exceeded for {tag}") from e
            elif any(phrase in str(e).lower() for phrase in ["rate limit", "too many requests"]):
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            logger.error(f"Error fetching deprecated status for {tag}: {e}")
            return False

    # High-performance semantic relationship methods
    # These methods provide fast access to cached relationships without full expansion overhead
    
    def get_implications(self, tag: str) -> List[str]:
        """Get direct implications for a tag from cached graph data.
        
        Args:
            tag: The tag to get implications for
            
        Returns:
            List of directly implied tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return self.tag_graph.get_implications(tag)

    def get_transitive_implications(self, tag: str, include_deprecated: bool = False) -> Set[str]:
        """Get all transitive implications for a tag from cached graph data.
        
        Args:
            tag: The tag to get transitive implications for
            include_deprecated: Whether to include deprecated implied tags
            
        Returns:
            Set of all transitively implied tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        
        all_implications = set()
        
        # A queue for breadth-first search (BFS) to find all descendants
        to_process = [tag]
        
        # Keep track of visited nodes to avoid getting stuck in cycles
        visited = set()

        while to_process:
            current_tag = to_process.pop(0)
            
            if current_tag in visited:
                continue
            visited.add(current_tag)

            # Get direct implications for the current tag
            direct_implications = self.get_implications(current_tag)
            
            for implied_tag in direct_implications:
                if implied_tag not in all_implications:
                    all_implications.add(implied_tag)
                    to_process.append(implied_tag)
        
        # Filter deprecated tags if needed
        if not include_deprecated:
            all_implications = {t for t in all_implications if not self.tag_graph.is_tag_deprecated(t)}
        
        return all_implications

    def get_aliases(self, tag: str) -> List[str]:
        """Get outgoing aliases for a tag from cached graph data.
        
        Args:
            tag: The tag to get aliases for
            
        Returns:
            List of alias target tag names
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return self.tag_graph.get_aliases(tag)

    def get_aliased_from(self, tag: str, include_deprecated: bool = True) -> List[str]:
        """Get incoming aliases for a tag from cached graph data.
        
        Args:
            tag: The tag to get incoming aliases for
            include_deprecated: Whether to include deprecated source tags
            
        Returns:
            List of tags that alias to this tag
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return self.tag_graph.get_aliased_from(tag, include_deprecated=include_deprecated)

    def get_alias_group(self, tag: str) -> Set[str]:
        """Get the complete alias group for a tag from cached graph data.
        
        Args:
            tag: The tag to get alias group for
            
        Returns:
            Set of all tags in the same alias group
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return self.tag_graph.get_alias_group(tag)

    def get_semantic_relations(self, tag: str, include_deprecated: bool = False) -> Dict[str, Union[List[str], Set[str]]]:
        """Get all semantic relationships for a tag.
        
        Args:
            tag: The tag to get relationships for
            include_deprecated: Whether to include deprecated tags
            
        Returns:
            Dictionary containing:
            - direct_implications: List of directly implied tags
            - transitive_implications: Set of transitively implied tags
            - direct_aliases: List of outgoing aliases
            - aliased_from: List of incoming aliases
            - alias_group: Set of all tags in the same alias group
            - is_canonical: Whether this tag is canonical
            - all_related: Set of all semantically related tags
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        
        # Get all relationships
        direct_implications = self.get_implications(tag)
        transitive_implications = self.get_transitive_implications(tag, include_deprecated=include_deprecated)
        direct_aliases = self.get_aliases(tag)
        aliased_from = self.get_aliased_from(tag, include_deprecated=include_deprecated)

        # Filter deprecated aliases if needed
        if not include_deprecated:
            direct_aliases = [t for t in direct_aliases if not self.tag_graph.is_tag_deprecated(t)]
            aliased_from = [t for t in aliased_from if not self.tag_graph.is_tag_deprecated(t)]

        # Get alias group and canonical status
        alias_group = {tag}  # Start with the current tag
        alias_group.update(direct_aliases)
        alias_group.update(aliased_from)

        # A tag is canonical if it has no outgoing aliases but might have incoming ones
        is_canonical = len(direct_aliases) == 0

        # Get all related tags
        all_related = set()
        all_related.update(direct_implications)
        all_related.update(transitive_implications)
        all_related.update(direct_aliases)
        all_related.update(aliased_from)

        return {
            'direct_implications': direct_implications,
            'transitive_implications': transitive_implications,
            'direct_aliases': direct_aliases,
            'aliased_from': aliased_from,
            'alias_group': alias_group,
            'is_canonical': is_canonical,
            'all_related': all_related
        }

    def is_tag_cached(self, tag: str) -> bool:
        """Check if a tag is in the cache.
        
        Args:
            tag: The tag to check
            
        Returns:
            True if the tag is in the cache, False otherwise
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return tag in self.tag_graph.graph

    def _validate_cache_enabled(self):
        """Validate that the graph cache is enabled and available.

        Raises:
            RuntimeError: When graph cache is not enabled
        """
        if not self.use_cache or not self.tag_graph:
            raise RuntimeError("Graph cache is not enabled. Cannot perform operation without cache.")

    def _validate_alias_directionality(self) -> None:
        """Validate that alias relationships are properly directional and fix any bidirectional issues.
        
        This method checks for and fixes any bidirectional alias relationships that might have been
        created incorrectly, ensuring that aliases are properly directional (antecedent -> consequent).
        
        When the API returns bidirectional relationships, this method uses heuristics to determine
        the correct direction based on tag naming patterns and other factors.
        """
        if not self.tag_graph:
            return
            
        logger.debug("Validating alias directionality...")
        
        # Get all alias edges
        alias_edges = [(u, v) for u, v, data in self.tag_graph.graph.edges(data=True) 
                       if data.get('edge_type') == 'alias']
        
        bidirectional_pairs = set()
        
        # Check for bidirectional alias relationships
        for u, v in alias_edges:
            if (v, u) in alias_edges:
                # Add as a sorted tuple to avoid duplicates
                pair = tuple(sorted([u, v]))
                bidirectional_pairs.add(pair)
                logger.warning(f"Found bidirectional alias relationship: {u} <-> {v}")
        
        # Fix bidirectional relationships
        for pair in bidirectional_pairs:
            u, v = pair
            
            # Determine which direction is correct based on deprecated status from the API
            u_is_deprecated = self.tag_graph.is_tag_deprecated(u)
            v_is_deprecated = self.tag_graph.is_tag_deprecated(v)
            
            correct_direction = None
            
            if u_is_deprecated and not v_is_deprecated:
                # u is deprecated, v is canonical: u -> v is correct
                correct_direction = (u, v)
                logger.info(f"Resolving with API deprecated status: {u} (deprecated) -> {v} (canonical)")
            elif not u_is_deprecated and v_is_deprecated:
                # v is deprecated, u is canonical: v -> u is correct
                correct_direction = (v, u)
                logger.info(f"Resolving with API deprecated status: {v} (deprecated) -> {u} (canonical)")
            else:
                # Both have same deprecated status - this is an ambiguous case.
                # Fallback to a deterministic heuristic (alphabetical order).
                logger.warning(f"Ambiguous bidirectional alias: {u} <-> {v}. Both have the same deprecated status ({u_is_deprecated}). Falling back to alphabetical heuristic.")
                if u < v:
                    correct_direction = (v, u)  # later -> earlier alphabetically
                    logger.info(f"Using alphabetical heuristic: {v} -> {u}")
                else:
                    correct_direction = (u, v)  # later -> earlier alphabetically
                    logger.info(f"Using alphabetical heuristic: {u} -> {v}")
            
            if correct_direction:
                antecedent, consequent = correct_direction
                
                # Remove both edges
                if self.tag_graph.graph.has_edge(u, v):
                    logger.info(f"Removing bidirectional edge: {u} -> {v}")
                    self.tag_graph.graph.remove_edge(u, v)
                if self.tag_graph.graph.has_edge(v, u):
                    logger.info(f"Removing bidirectional edge: {v} -> {u}")
                    self.tag_graph.graph.remove_edge(v, u)
                
                # Add the correct directional edge
                logger.info(f"Adding correct directional alias: {antecedent} -> {consequent}")
                self.tag_graph.add_alias(antecedent, consequent)
        
        if bidirectional_pairs:
            logger.info(f"Fixed {len(bidirectional_pairs)} bidirectional alias relationships")
        else:
            logger.debug("No bidirectional alias issues found")

    def is_canonical(self, tag: str) -> bool:
        """Check if a tag is canonical (not deprecated/aliased to another tag).
        
        A canonical tag is one that doesn't have outgoing alias edges, meaning
        it's not deprecated or redirected to another tag. These are the preferred
        tags that should be used in tagging.
        
        Args:
            tag: The tag to check for canonical status
            
        Returns:
            True if the tag is canonical (no outgoing aliases), False if deprecated
            
        Raises:
            RuntimeError: When graph cache is not enabled
        """
        self._validate_cache_enabled()
        return len(self.get_aliases(tag)) == 0