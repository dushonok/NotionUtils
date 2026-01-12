import os
import sys

# Add parent directories to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ConfigKeeper')))

from notion_config import NOTION_BLOCK_TOGGLE
from notion_api import (
    get_post_title_website_from_url,
    get_page_property,
)
from notion_blocks_api import (
    get_page_content,
    get_page_content_blocks,
    get_page_block_children,
    extract_text_from_block,
)


class NotionRecipeParser:
    """
    Parser for extracting recipe content from Notion pages.
    Handles toggle blocks and converts them into structured post parts.
    """
    
    def __init__(self, callback=print):
        """
        Initialize the parser.
        
        Args:
            callback: Function to use for logging messages (default: print)
        """
        self.callback = callback
    
    def parse_recipe_from_url(self, post_url):
        """
        Parse a recipe from a Notion page URL.
        
        Args:
            post_url: URL of the Notion page containing the recipe
            
        Returns:
            dict: Dictionary containing:
                - post: The Notion post object
                - title: Title of the recipe
                - website: Website identifier
                - grouped_post_parts: Dict mapping heading_1 text to collected content
        """
        post, title, website = get_post_title_website_from_url(post_url)
        self.callback(f"\n[INFO][NotionRecipeParser] Processing Notion page with title: '{title}'")
        
        post_id = post.get("id")
        grouped_post_parts = self._extract_post_parts(post_id)
        
        return {
            'post': post,
            'title': title,
            'website': website,
            'grouped_post_parts': grouped_post_parts
        }
    
    def _extract_post_parts(self, post_id: str) -> dict:
        """
        Extract post parts from a Notion page by processing toggle blocks.
        
        Args:
            post_id: ID of the Notion page
            
        Returns:
            list: Dict mapping heading_N text to collected content
        """
        post_body = get_page_content(post_id)
        post_elements = get_page_content_blocks(post_body)
        
        if not post_elements:
            self.callback(f"[WARNING][NotionRecipeParser] No content blocks found in page ID: {post_id}")
            return {}
        
        post_parts = []
        for idx, element in enumerate(post_elements):
            element_text = element.get('text', '')
            
            if element.get('type') != NOTION_BLOCK_TOGGLE:
                continue
            
            self.callback(f"[NotionRecipeParser] Found toggle: '{element_text}' - fetching children...")
            
            toggle_children = self._get_toggle_children(element, post_id)
            
            for j, child in enumerate(toggle_children):
                child_type = child.get('type')
                child_text = extract_text_from_block(child)
                post_parts.append({'type': child_type, 'text': child_text})
                self.callback(f"[DEBUG]   Toggle child {j}: {{'type': '{child_type}', 'text': '{child_text}'}}")
            break
        
        # Group content hierarchically by heading levels (1-4)
        grouped_post_parts = self._build_nested_structure(post_parts)
        
        self.callback(f"[INFO][NotionRecipeParser] Grouped content into nested structure")

        return grouped_post_parts
    
    def _build_nested_structure(self, post_parts: list) -> dict:
        """
        Build a nested structure from post_parts based on heading hierarchy (1-4).
        
        Args:
            post_parts: List of dictionaries with 'type' and 'text' keys
            
        Returns:
            dict: Nested dictionary where each heading contains 'content' and nested headings
        """
        result = {}
        stack = [result]  # Stack to track current nesting level
        level_map = {0: result}  # Map heading levels to their dict containers

        MIN_HEADING_LEVEL = 1
        MAX_HEADING_LEVEL = 4
        HEADING_PREFIX = 'heading_'
        
        for part in post_parts:
            part_type = part['type']
            part_text = part['text']
            
            # Check if it's a heading (heading_1 through heading_4)
            if part_type.startswith(HEADING_PREFIX):
                try:
                    level = int(part_type.split('_')[1])
                    if MIN_HEADING_LEVEL <= level <= MAX_HEADING_LEVEL:
                        # Close all deeper levels
                        for l in list(level_map.keys()):
                            if l >= level:
                                del level_map[l]
                        
                        # Get parent container (one level up)
                        parent = level_map.get(level - 1, result)
                        
                        # Create new section for this heading
                        new_section = {}
                        parent[part_text] = new_section
                        level_map[level] = new_section
                    else:
                        # Not a heading level we care about, treat as content
                        self._add_content_to_current_section(level_map, part_text)
                except (ValueError, IndexError):
                    # Not a valid heading format, treat as content
                    self._add_content_to_current_section(level_map, part_text)
            else:
                # Regular content - add to the deepest current section
                self._add_content_to_current_section(level_map, part_text)
        
        # Convert content lists to joined strings
        self._finalize_content_strings(result)
        
        return result
    
    def _add_content_to_current_section(self, level_map, text):
        """
        Add content text to the deepest current section in the hierarchy.
        
        Args:
            level_map: Dictionary mapping heading levels to their containers
            text: Text content to add
        """
        if not level_map:
            return
        
        # Get the deepest level
        max_level = max(level_map.keys())
        current_section = level_map[max_level]
        
        # Add to 'content' key, creating it if needed
        if 'content' not in current_section:
            current_section['content'] = []
        
        current_section['content'].append(text)
    
    def _finalize_content_strings(self, structure):
        """
        Recursively convert content lists to newline-joined strings.
        
        Args:
            structure: Dictionary structure to process
        """
        # Handle root level content if it exists
        if 'content' in structure and isinstance(structure['content'], list):
            structure['content'] = '\n'.join(structure['content'])
        
        for key, value in structure.items():
            if isinstance(value, dict):
                # Convert content list to string if it exists
                if 'content' in value and isinstance(value['content'], list):
                    value['content'] = '\n'.join(value['content'])
                # Recursively process nested structures
                self._finalize_content_strings(value)
    
    def _get_toggle_children(self, toggle_element, page_id):
        """
        Get all child elements from a toggle block.
        
        Args:
            toggle_element: The toggle block element
            page_id: ID of the parent page (not currently used but kept for compatibility)
            
        Returns:
            list: List of child elements, or empty list if none found
        """
        # Check if this is a toggle block
        if toggle_element.get('type') != NOTION_BLOCK_TOGGLE:
            self.callback(f"[WARNING] Element is not a toggle, it's: {toggle_element.get('type')}")
            return []
        
        self.callback(f"[DEBUG] Full toggle element structure:")
        self.callback(f"[DEBUG]     Keys: {list(toggle_element.keys())}")
        self.callback(f"[DEBUG]     Full element: {toggle_element}")
        
        # Get the toggle block ID
        toggle_block_id = (
            toggle_element.get('id') or                    # Direct ID
            toggle_element.get('block_id') or              # Alternative field
            toggle_element.get('raw_block', {}).get('id')  # From raw block
        )
        if not toggle_block_id:
            self.callback("[ERROR] Toggle block has no ID")
            return []
        
        # Fetch children of the toggle block
        try:
            children_response = get_page_block_children(page_block_id=toggle_block_id)
            children = children_response.get('results', [])
            return children
            
        except Exception as e:
            raise ValueError(f"Could not retrieve toggle children: {e}") from e