import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ConfigKeeper')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'NotionAutomator')))

from notion_recipe_parser import NotionRecipeParser


class TestNotionRecipeParser(unittest.TestCase):
    """Test NotionRecipeParser class"""
    
    def setUp(self):
        self.parser = NotionRecipeParser()
    
    @patch('notion_recipe_parser.get_post_title_website_from_url')
    @patch('notion_recipe_parser.NotionRecipeParser._extract_post_parts')
    def test_parse_recipe_from_url(self, mock_extract, mock_get_title):
        # Setup mocks
        mock_get_title.return_value = (
            {'id': 'page123'},
            'My Recipe',
            'example.com'
        )
        mock_extract.return_value = [
            {'type': 'paragraph', 'text': 'Recipe content'}
        ]
        
        # Execute
        result = self.parser.parse_recipe_from_url('https://notion.so/test')
        
        # Verify
        self.assertEqual(result['post']['id'], 'page123')
        self.assertEqual(result['title'], 'My Recipe')
        self.assertEqual(result['website'], 'example.com')
        self.assertEqual(len(result['post_parts']), 1)
        mock_get_title.assert_called_once_with('https://notion.so/test')
        mock_extract.assert_called_once_with('page123')
    
    @patch('notion_recipe_parser.get_page_content')
    @patch('notion_recipe_parser.get_page_content_blocks')
    @patch('notion_recipe_parser.extract_text_from_block')
    @patch('notion_recipe_parser.NotionRecipeParser.get_toggle_children')
    def test_extract_post_parts_with_toggle(
        self,
        mock_get_children,
        mock_extract_text,
        mock_get_blocks,
        mock_get_content
    ):
        # Setup mocks
        mock_get_content.return_value = {'content': 'data'}
        mock_get_blocks.return_value = [
            {'type': 'paragraph', 'text': 'Regular paragraph'},
            {'type': 'toggle', 'text': 'Recipe toggle', 'id': 'toggle1'}
        ]
        mock_get_children.return_value = [
            {'type': 'heading_2', 'text': 'Ingredients'},
            {'type': 'bulleted_list_item', 'text': 'Item 1'}
        ]
        mock_extract_text.side_effect = ['Ingredients text', 'Item 1 text']
        
        # Execute
        result = self.parser._extract_post_parts('page123')
        
        # Verify
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'heading_2')
        self.assertEqual(result[0]['text'], 'Ingredients text')
        self.assertEqual(result[1]['type'], 'bulleted_list_item')
        self.assertEqual(result[1]['text'], 'Item 1 text')
    
    @patch('notion_recipe_parser.get_page_content')
    @patch('notion_recipe_parser.get_page_content_blocks')
    def test_extract_post_parts_no_toggle(self, mock_get_blocks, mock_get_content):
        # Setup mocks with no toggle elements
        mock_get_content.return_value = {'content': 'data'}
        mock_get_blocks.return_value = [
            {'type': 'paragraph', 'text': 'Just a paragraph'},
            {'type': 'heading_2', 'text': 'A heading'}
        ]
        
        # Execute
        result = self.parser._extract_post_parts('page123')
        
        # Verify - should be empty since no toggle found
        self.assertEqual(result, [])
    
    @patch('notion_recipe_parser.get_page_block_children')
    def test_get_toggle_children_success(self, mock_get_children):
        # Mock response
        mock_get_children.return_value = {
            'results': [
                {'type': 'paragraph', 'id': 'child1'},
                {'type': 'heading_3', 'id': 'child2'}
            ]
        }
        
        toggle_element = {
            'type': 'toggle',
            'id': 'toggle_id_123',
            'text': 'Toggle content'
        }
        
        # Execute
        result = self.parser.get_toggle_children(toggle_element, 'page123')
        
        # Verify
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'paragraph')
        self.assertEqual(result[1]['type'], 'heading_3')
        mock_get_children.assert_called_once_with(page_block_id='toggle_id_123')
    
    def test_get_toggle_children_not_toggle(self):
        element = {'type': 'paragraph', 'id': 'para1'}
        
        result = self.parser.get_toggle_children(element, 'page123')
        
        self.assertEqual(result, [])
    
    def test_get_toggle_children_no_id(self):
        toggle_element = {'type': 'toggle', 'text': 'No ID toggle'}
        
        result = self.parser.get_toggle_children(toggle_element, 'page123')
        
        self.assertEqual(result, [])
    
    @patch('notion_recipe_parser.get_page_block_children')
    def test_get_toggle_children_with_block_id(self, mock_get_children):
        mock_get_children.return_value = {'results': [{'type': 'paragraph'}]}
        
        toggle_element = {
            'type': 'toggle',
            'block_id': 'block_id_456'
        }
        
        result = self.parser.get_toggle_children(toggle_element, 'page123')
        
        mock_get_children.assert_called_once_with(page_block_id='block_id_456')
    
    @patch('notion_recipe_parser.get_page_block_children')
    def test_get_toggle_children_with_raw_block(self, mock_get_children):
        mock_get_children.return_value = {'results': [{'type': 'heading_2'}]}
        
        toggle_element = {
            'type': 'toggle',
            'raw_block': {'id': 'raw_id_789'}
        }
        
        result = self.parser.get_toggle_children(toggle_element, 'page123')
        
        mock_get_children.assert_called_once_with(page_block_id='raw_id_789')
    
    @patch('notion_recipe_parser.get_page_block_children')
    def test_get_toggle_children_api_error(self, mock_get_children):
        mock_get_children.side_effect = Exception("Notion API error")
        
        toggle_element = {'type': 'toggle', 'id': 'toggle123'}
        
        result = self.parser.get_toggle_children(toggle_element, 'page123')
        
        self.assertEqual(result, [])
    
    def test_custom_callback(self):
        """Test that custom callback is used"""
        messages = []
        
        def custom_callback(msg):
            messages.append(msg)
        
        parser = NotionRecipeParser(callback=custom_callback)
        
        # Mock the parse method to trigger callback
        with patch('notion_recipe_parser.get_post_title_website_from_url') as mock_get_title:
            mock_get_title.return_value = ({'id': '123'}, 'Test', 'site.com')
            with patch.object(parser, '_extract_post_parts', return_value=[]):
                parser.parse_recipe_from_url('https://notion.so/test')
        
        # Verify callback was called
        self.assertTrue(any('Processing Notion page' in msg for msg in messages))


if __name__ == '__main__':
    unittest.main()
