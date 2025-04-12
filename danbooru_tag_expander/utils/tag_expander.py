"""Tag expander utility for Danbooru.

This module provides functionality to expand a set of tags by retrieving
their implications and aliases from the Danbooru API.
"""

import os
import json
import time
import logging
import requests
from collections import Counter, defaultdict, deque
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
                 request_delay: float = 0.5):
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
            logger.info(f"Caching enabled. Using directory: {self.cache_dir}")
        else:
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
            logger.exception(f"Full error details during API request to {endpoint}:") # Use exception to include traceback
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
            logger.debug(f"Using cached implications for '{tag}'")
            return self._implications_cache[tag]
        
        # Check disk cache if enabled
        if self.use_cache:
            cache_file = os.path.join(self.cache_dir, f"implications_{tag}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        implications = json.load(f)
                    self._implications_cache[tag] = implications
                    logger.debug(f"Loaded implications for '{tag}' from disk cache")
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
            
            logger.debug(f"Found {len(implications)} implications for '{tag}'")
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
                logger.debug(f"Saved implications for '{tag}' to disk cache")
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
            logger.debug(f"Using cached aliases for '{tag}'")
            return self._aliases_cache[tag]
        
        # Check disk cache if enabled
        if self.use_cache:
            cache_file = os.path.join(self.cache_dir, f"aliases_{tag}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        aliases = json.load(f)
                    self._aliases_cache[tag] = aliases
                    logger.debug(f"Loaded aliases for '{tag}' from disk cache")
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
            
            logger.debug(f"Found {len(aliases)} aliases for '{tag}'")
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
                logger.debug(f"Saved aliases for '{tag}' to disk cache")
            except Exception as e:
                logger.error(f"Error saving cache for tag '{tag}': {e}")
        
        return aliases

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
        # --- 1. Initial Expansion (Implications) ---
        original_tags = set(tags)
        implication_queue = deque(original_tags)
        processed_implications = set()
        expanded_set = set(original_tags)
        direct_implications: Dict[str, Set[str]] = defaultdict(set) # A -> {B, C}

        logger.info("Finding implications for tags (transitive closure)...")
        while implication_queue:
            current_tag = implication_queue.popleft()
            if current_tag in processed_implications:
                continue
            processed_implications.add(current_tag)

            logger.debug(f"Processing implications for tag: {current_tag}")
            implications = self.get_tag_implications(current_tag)
            for implied_tag in implications:
                direct_implications[current_tag].add(implied_tag)
                if implied_tag not in expanded_set:
                    expanded_set.add(implied_tag)
                    implication_queue.append(implied_tag)

        logger.info(f"Implication expansion complete. Found {len(expanded_set)} tags.")

        # --- 2. Alias Expansion ---
        alias_queue = deque(expanded_set)
        processed_aliases = set()
        final_expanded_set = set(expanded_set)
        direct_aliases: Dict[str, Set[str]] = defaultdict(set) # A -> {B, C} where A, B, C are aliases

        logger.info(f"Finding aliases for {len(expanded_set)} tags...")
        while alias_queue:
             current_tag = alias_queue.popleft()
             if current_tag in processed_aliases:
                 continue
             processed_aliases.add(current_tag)

             logger.debug(f"Processing aliases for tag: {current_tag}")
             aliases = self.get_tag_aliases(current_tag)
             tag_alias_group = {current_tag} | set(aliases)

             for alias in tag_alias_group:
                 # Store bidirectional alias relationships implicitly via the group
                 direct_aliases[current_tag].update(tag_alias_group - {current_tag}) # Add others to current's entry
                 direct_aliases[alias].update(tag_alias_group - {alias}) # Add others to alias's entry

                 if alias not in final_expanded_set:
                     final_expanded_set.add(alias)
                     # If a new alias is found, it might have implications we missed
                     if alias not in processed_implications:
                          implication_queue.append(alias) # Add back to implication queue
                     # Also need to check its aliases
                     if alias not in processed_aliases:
                          alias_queue.append(alias)


        # Re-run implication expansion if new tags were added via aliases
        if implication_queue:
             logger.info("Re-running implication expansion for tags added via aliases...")
             # Reset processed set for implication re-check, but keep expanded_set
             processed_implications.clear()
             while implication_queue:
                 current_tag = implication_queue.popleft()
                 if current_tag in processed_implications:
                     continue
                 processed_implications.add(current_tag)

                 logger.debug(f"Processing implications for tag: {current_tag}")
                 implications = self.get_tag_implications(current_tag)
                 for implied_tag in implications:
                     direct_implications[current_tag].add(implied_tag)
                     if implied_tag not in final_expanded_set:
                         # This tag is truly new (wasn't found in initial implication or alias pass)
                         final_expanded_set.add(implied_tag)
                         # Add to alias queue to check *its* aliases and implications later if needed
                         if implied_tag not in processed_aliases:
                             alias_queue.append(implied_tag) # Check aliases of newly found implied tag
                         if implied_tag not in processed_implications:
                             implication_queue.append(implied_tag) # Should already be covered, but safe


             # Need to re-run alias finding if new tags were added during implication re-run
             if alias_queue:
                 logger.info("Re-running alias expansion for tags added during implication re-run...")
                 # Reset processed set for alias re-check
                 processed_aliases.clear()
                 while alias_queue:
                      current_tag = alias_queue.popleft()
                      if current_tag in processed_aliases:
                          continue
                      processed_aliases.add(current_tag)
                      # Only process tags actually in our final set now
                      if current_tag not in final_expanded_set: continue

                      logger.debug(f"Processing aliases for tag: {current_tag}")
                      aliases = self.get_tag_aliases(current_tag)
                      tag_alias_group = {current_tag} | set(aliases)

                      for alias in tag_alias_group:
                          direct_aliases[current_tag].update(tag_alias_group - {current_tag})
                          direct_aliases[alias].update(tag_alias_group - {alias})

                          if alias not in final_expanded_set:
                              final_expanded_set.add(alias)
                              # Add back to queues if truly new
                              if alias not in processed_implications: implication_queue.append(alias)
                              if alias not in processed_aliases: alias_queue.append(alias)
                 # One final implication check if new aliases were added in the last step
                 if implication_queue:
                      logger.info("Final implication check...")
                      processed_implications.clear()
                      while implication_queue:
                         current_tag = implication_queue.popleft()
                         if current_tag in processed_implications: continue
                         processed_implications.add(current_tag)
                         if current_tag not in final_expanded_set: continue
                         implications = self.get_tag_implications(current_tag)
                         for implied_tag in implications:
                             direct_implications[current_tag].add(implied_tag)
                             if implied_tag not in final_expanded_set:
                                 final_expanded_set.add(implied_tag) # Add but don't re-queue, assume stable now

        # --- 3. Determine Canonical Tags using Disjoint Set Union (DSU) ---
        parent = {tag: tag for tag in final_expanded_set}
        def find_set(tag):
            if parent[tag] == tag:
                return tag
            parent[tag] = find_set(parent[tag]) # Path compression
            return parent[tag]

        def unite_sets(tag1, tag2):
            tag1 = find_set(tag1)
            tag2 = find_set(tag2)
            if tag1 != tag2:
                # Union by rank/size could be added for optimization, but usually not needed here
                parent[tag2] = tag1 # Make tag1 the parent

        for tag in final_expanded_set:
            # Ensure tag is in parent dict even if it had no explicit aliases found
            if tag not in parent: parent[tag] = tag
            # Process discovered aliases
            if tag in direct_aliases:
                for alias in direct_aliases[tag]:
                     if alias in parent: # Ensure alias exists in our set
                        unite_sets(tag, alias)

        canonical_map = {tag: find_set(tag) for tag in final_expanded_set}

        # --- 4. Build Canonical Implication Graph ---
        canonical_graph: Dict[str, Set[str]] = defaultdict(set)
        in_degree: Dict[str, int] = defaultdict(int)
        canonical_nodes = set(canonical_map.values())

        for u in final_expanded_set:
             canon_u = canonical_map[u]
             # Ensure all nodes exist in in_degree
             if canon_u not in in_degree: in_degree[canon_u] = 0
             for v in direct_implications.get(u, set()):
                 if v in canonical_map: # Ensure implied tag is in our final set
                     canon_v = canonical_map[v]
                     if canon_u != canon_v:
                         if canon_v not in canonical_graph[canon_u]:
                             canonical_graph[canon_u].add(canon_v)
                             # Ensure neighbor node exists
                             if canon_v not in in_degree: in_degree[canon_v] = 0
                             in_degree[canon_v] += 1

        # --- 5. Calculate Frequencies on Canonical Graph (Topological Sort) ---
        canonical_frequency = Counter()
        # Seed with original tags
        for tag in original_tags:
             if tag in canonical_map: # Ensure original tag is valid
                 canonical_frequency[canonical_map[tag]] += 1

        # Topological sort using Kahn's algorithm
        topo_queue = deque([node for node in canonical_nodes if in_degree[node] == 0])
        processed_nodes = 0

        while topo_queue:
            canon_u = topo_queue.popleft()
            processed_nodes += 1

            for canon_v in canonical_graph.get(canon_u, set()):
                 # Propagate frequency
                 canonical_frequency[canon_v] += canonical_frequency[canon_u]
                 in_degree[canon_v] -= 1
                 if in_degree[canon_v] == 0:
                     topo_queue.append(canon_v)

        # Check for cycles (shouldn't happen in Danbooru implications)
        if processed_nodes != len(canonical_nodes):
             # Handle cycle detection/error reporting if necessary
             logger.warning("Cycle detected in canonical implication graph, frequencies may be inaccurate.")
             # Fallback or error handling can be added here

        # --- 6. Distribute Canonical Frequencies to All Aliases ---
        final_frequency = Counter()
        for tag in final_expanded_set:
            final_frequency[tag] = canonical_frequency[canonical_map[tag]]

        logger.info(f"Expanded {len(original_tags)} tags to {len(final_expanded_set)} tags with calculated frequencies.")
        return final_expanded_set, final_frequency 
