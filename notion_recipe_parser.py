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
                - post_parts: List of parsed content elements
        """
        post, title, website = get_post_title_website_from_url(post_url)
        self.callback(f"\n[INFO][NotionRecipeParser] Processing Notion page with title: '{title}'")
        
        post_id = post.get("id")
        post_parts = self._extract_post_parts(post_id)
        
        return {
            'post': post,
            'title': title,
            'website': website,
            'post_parts': post_parts
        }
    
    def _extract_post_parts(self, post_id):
        """
        Extract post parts from a Notion page by processing toggle blocks.
        
        Args:
            post_id: ID of the Notion page
            
        Returns:
            list: List of dictionaries with 'type' and 'text' keys
        """
        post_body = get_page_content(post_id)
        post_elements = get_page_content_blocks(post_body)
        post_parts = []

        if not post_elements:
            self.callback(f"[WARNING][NotionRecipeParser] No content blocks found in page ID: {post_id}")
            return post_parts
        
        for idx, element in enumerate(post_elements):
            element_text = element.get('text', '')
            
            if element.get('type') != NOTION_BLOCK_TOGGLE:
                continue
            
            self.callback(f"[NotionRecipeParser] Found toggle: '{element_text}' - fetching children...")
            
            toggle_children = self.get_toggle_children(element, post_id)
            
            for j, child in enumerate(toggle_children):
                child_type = child.get('type')
                child_text = extract_text_from_block(child)
                post_parts.append({'type': child_type, 'text': child_text})
                self.callback(f"[DEBUG]   Toggle child {j}: {{'type': '{child_type}', 'text': '{child_text}'}}")
            break
        
        return post_parts
    
    def get_toggle_children(self, toggle_element, page_id):
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
            
            print(f"[DEBUG] Toggle has {len(children)} children")
            return children
            
        except Exception as e:
            print(f"[ERROR] Failed to get toggle children: {e}")
            return []
