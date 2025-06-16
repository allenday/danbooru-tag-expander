#!/usr/bin/env python3
"""Tests for the CLI module."""

import unittest
import tempfile
import shutil
import os
import sys
import json
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO
from danbooru_tag_expander.tag_expander_cli import (
    main, parse_args, setup_logging, read_tags_from_file, expand_tags
)


class TestCLI(unittest.TestCase):
    """Test cases for CLI functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_tags_file = os.path.join(self.temp_dir, "test_tags.txt")
        
        # Create a test tags file
        with open(self.test_tags_file, 'w') as f:
            f.write("1girl\nsolo\ncat\n")

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_args_with_tags(self):
        """Test parsing command line arguments with tags."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', 'solo']):
            args = parse_args()
            
            self.assertEqual(args.tags, ['1girl', 'solo'])
            self.assertIsNone(args.file)
            self.assertEqual(args.format, 'text')
            self.assertEqual(args.sort, 'freq')
            self.assertFalse(args.no_cache)
            self.assertFalse(args.quiet)

    def test_parse_args_with_file(self):
        """Test parsing command line arguments with file input."""
        with patch('sys.argv', ['danbooru-tag-expander', '--file', 'tags.txt']):
            args = parse_args()
            
            self.assertIsNone(args.tags)
            self.assertEqual(args.file, 'tags.txt')

    def test_parse_args_with_options(self):
        """Test parsing command line arguments with various options."""
        with patch('sys.argv', [
            'danbooru-tag-expander',
            '--tags', '1girl',
            '--format', 'json',
            '--sort', 'alpha',
            '--no-cache',
            '--quiet',
            '--delay', '1.0',
            '--username', 'testuser',
            '--api-key', 'testkey',
            '--site-url', 'https://test.com',
            '--cache-dir', '/tmp/cache'
        ]):
            args = parse_args()
            
            self.assertEqual(args.tags, ['1girl'])
            self.assertEqual(args.format, 'json')
            self.assertEqual(args.sort, 'alpha')
            self.assertTrue(args.no_cache)
            self.assertTrue(args.quiet)
            self.assertEqual(args.delay, 1.0)
            self.assertEqual(args.username, 'testuser')
            self.assertEqual(args.api_key, 'testkey')
            self.assertEqual(args.site_url, 'https://test.com')
            self.assertEqual(args.cache_dir, '/tmp/cache')

    def test_parse_args_mutually_exclusive_tags_and_file(self):
        """Test that tags and file arguments are mutually exclusive."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', '--file', 'tags.txt']):
            with self.assertRaises(SystemExit):
                parse_args()

    def test_parse_args_missing_required_input(self):
        """Test that either tags or file is required."""
        with patch('sys.argv', ['danbooru-tag-expander']):
            with self.assertRaises(SystemExit):
                parse_args()

    def test_read_tags_from_file_success(self):
        """Test reading tags from a file successfully."""
        tags = read_tags_from_file(self.test_tags_file)
        
        expected_tags = ['1girl', 'solo', 'cat']
        self.assertEqual(tags, expected_tags)

    def test_read_tags_from_file_empty_lines(self):
        """Test reading tags from file with empty lines and whitespace."""
        test_file = os.path.join(self.temp_dir, "test_empty.txt")
        with open(test_file, 'w') as f:
            f.write("1girl\n\n  solo  \n\ncat\n  \n")
        
        tags = read_tags_from_file(test_file)
        expected_tags = ['1girl', 'solo', 'cat']
        self.assertEqual(tags, expected_tags)

    def test_read_tags_from_file_not_found(self):
        """Test reading from non-existent file."""
        with patch('sys.stderr', new_callable=StringIO):
            with self.assertRaises(SystemExit):
                read_tags_from_file('nonexistent.txt')

    def test_setup_logging_info_level(self):
        """Test setting up logging at INFO level."""
        import logging
        
        with patch('logging.StreamHandler') as mock_handler_class:
            with patch('logging.Formatter') as mock_formatter_class:
                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler
                mock_formatter = MagicMock()
                mock_formatter_class.return_value = mock_formatter
                
                setup_logging(logging.INFO)
                
                # Check that StreamHandler was created
                mock_handler_class.assert_called_once_with(sys.stderr)
                
                # Check that handler level was set
                mock_handler.setLevel.assert_called_once_with(logging.INFO)
                
                # Check that formatter was created and set
                mock_formatter_class.assert_called_once_with('%(levelname)s: %(message)s')
                mock_handler.setFormatter.assert_called_once_with(mock_formatter)

    def test_setup_logging_debug_level(self):
        """Test setting up logging at DEBUG level."""
        import logging
        
        with patch('logging.StreamHandler') as mock_handler_class:
            with patch('logging.Formatter') as mock_formatter_class:
                mock_handler = MagicMock()
                mock_handler_class.return_value = mock_handler
                mock_formatter = MagicMock()
                mock_formatter_class.return_value = mock_formatter
                
                setup_logging(logging.DEBUG)
                
                # Check that StreamHandler was created
                mock_handler_class.assert_called_once_with(sys.stderr)
                
                # Check that handler level was set
                mock_handler.setLevel.assert_called_once_with(logging.DEBUG)

    @patch('danbooru_tag_expander.tag_expander_cli.TagExpander')
    def test_expand_tags_text_format(self, mock_expander_class):
        """Test tag expansion with text output format."""
        # Mock the expander instance
        mock_expander = MagicMock()
        mock_expander_class.return_value = mock_expander
        mock_expander.expand_tags.return_value = (
            {'1girl', 'solo', 'female'},
            {'1girl': 2, 'solo': 1, 'female': 2}
        )
        
        # Mock args
        args = MagicMock()
        args.format = 'text'
        args.sort = 'freq'
        args.no_cache = False
        args.cache_dir = None
        args.delay = 0.5
        args.username = 'test'
        args.api_key = 'test'
        args.site_url = None
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            expand_tags(['1girl', 'solo'], args)
            
            output = mock_stdout.getvalue()
            self.assertIn('Original tags (2):', output)
            self.assertIn('Expanded tags (3):', output)
            self.assertIn('1girl', output)
            self.assertIn('solo', output)

    @patch('danbooru_tag_expander.tag_expander_cli.TagExpander')
    def test_expand_tags_json_format(self, mock_expander_class):
        """Test tag expansion with JSON output format."""
        mock_expander = MagicMock()
        mock_expander_class.return_value = mock_expander
        mock_expander.expand_tags.return_value = (
            {'1girl', 'solo'},
            {'1girl': 1, 'solo': 1}
        )
        
        args = MagicMock()
        args.format = 'json'
        args.sort = 'freq'
        args.no_cache = False
        args.cache_dir = None
        args.delay = 0.5
        args.username = 'test'
        args.api_key = 'test'
        args.site_url = None
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            expand_tags(['1girl'], args)
            
            output = mock_stdout.getvalue()
            # Should be valid JSON
            result = json.loads(output)
            self.assertIn('original_tags', result)
            self.assertIn('expanded_tags', result)
            self.assertIn('frequencies', result)

    @patch('danbooru_tag_expander.tag_expander_cli.TagExpander')
    def test_expand_tags_csv_format(self, mock_expander_class):
        """Test tag expansion with CSV output format."""
        mock_expander = MagicMock()
        mock_expander_class.return_value = mock_expander
        mock_expander.expand_tags.return_value = (
            {'1girl', 'solo'},
            {'1girl': 2, 'solo': 1}
        )
        
        args = MagicMock()
        args.format = 'csv'
        args.sort = 'freq'
        args.no_cache = False
        args.cache_dir = None
        args.delay = 0.5
        args.username = 'test'
        args.api_key = 'test'
        args.site_url = None
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            expand_tags(['1girl'], args)
            
            output = mock_stdout.getvalue()
            lines = output.strip().split('\n')
            # CSV uses quotes around all fields
            self.assertEqual(lines[0].strip(), '"tag","frequency"')  # Header
            self.assertIn('"1girl","2"', output)
            self.assertIn('"solo","1"', output)

    @patch('danbooru_tag_expander.tag_expander_cli.TagExpander')
    def test_expand_tags_alpha_sort(self, mock_expander_class):
        """Test tag expansion with alphabetical sorting."""
        mock_expander = MagicMock()
        mock_expander_class.return_value = mock_expander
        mock_expander.expand_tags.return_value = (
            {'zebra', 'apple', 'banana'},
            {'zebra': 3, 'apple': 1, 'banana': 2}
        )
        
        args = MagicMock()
        args.format = 'csv'
        args.sort = 'alpha'
        args.no_cache = False
        args.cache_dir = None
        args.delay = 0.5
        args.username = 'test'
        args.api_key = 'test'
        args.site_url = None
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            expand_tags(['test'], args)
            
            output = mock_stdout.getvalue()
            lines = output.strip().split('\n')[1:]  # Skip header
            
            # Should be alphabetically sorted, CSV uses quotes
            tags = [line.split(',')[0].strip('"') for line in lines]
            self.assertEqual(tags, ['apple', 'banana', 'zebra'])

    @patch('danbooru_tag_expander.tag_expander_cli.TagExpander')
    def test_expand_tags_with_cache_disabled(self, mock_expander_class):
        """Test tag expansion with cache disabled."""
        mock_expander = MagicMock()
        mock_expander_class.return_value = mock_expander
        mock_expander.expand_tags.return_value = ({'1girl'}, {'1girl': 1})
        
        args = MagicMock()
        args.format = 'text'
        args.sort = 'freq'
        args.no_cache = True
        args.cache_dir = None
        args.delay = 0.5
        args.username = 'test'
        args.api_key = 'test'
        args.site_url = None
        
        with patch('sys.stdout', new_callable=StringIO):
            expand_tags(['1girl'], args)
            
            # Verify TagExpander was called with use_cache=False
            mock_expander_class.assert_called_once_with(
                username='test',
                api_key='test',
                site_url=None,
                use_cache=False,
                cache_dir=None,
                request_delay=0.5
            )

    @patch.dict(os.environ, {'DANBOORU_USERNAME': 'env_user', 'DANBOORU_API_KEY': 'env_key'})
    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_with_environment_credentials(self, mock_setup_logging, mock_expand_tags):
        """Test main function using environment credentials."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl']):
            main()
            
            mock_setup_logging.assert_called_once()
            mock_expand_tags.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)  # Clear environment
    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_missing_api_key(self, mock_setup_logging, mock_expand_tags):
        """Test main function with missing API key."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', '--username', 'test']):
            with patch('sys.stderr', new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)

    @patch.dict(os.environ, {}, clear=True)  # Clear environment
    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_missing_username(self, mock_setup_logging, mock_expand_tags):
        """Test main function with missing username."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', '--api-key', 'test']):
            with patch('sys.stderr', new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)

    @patch('danbooru_tag_expander.tag_expander_cli.read_tags_from_file')
    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_with_file_input(self, mock_setup_logging, mock_expand_tags, mock_read_tags):
        """Test main function with file input."""
        mock_read_tags.return_value = ['1girl', 'solo']
        with patch('sys.argv', ['danbooru-tag-expander', '--file', 'tags.txt', '--username', 'test', '--api-key', 'test']):
            main()
            
            mock_read_tags.assert_called_once_with('tags.txt')
            mock_expand_tags.assert_called_once()

    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_with_quiet_flag(self, mock_setup_logging, mock_expand_tags):
        """Test main function with quiet flag."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', '--quiet', '--username', 'test', '--api-key', 'test']):
            main()
            
            # Should set up logging with ERROR level when quiet is True
            import logging
            mock_setup_logging.assert_called_once_with(logging.ERROR)

    @patch('danbooru_tag_expander.tag_expander_cli.expand_tags')
    @patch('danbooru_tag_expander.tag_expander_cli.setup_logging')
    def test_main_with_log_level(self, mock_setup_logging, mock_expand_tags):
        """Test main function with specific log level."""
        with patch('sys.argv', ['danbooru-tag-expander', '--tags', '1girl', '--log-level', 'DEBUG', '--username', 'test', '--api-key', 'test']):
            main()
            
            import logging
            mock_setup_logging.assert_called_once_with(logging.DEBUG)


if __name__ == '__main__':
    unittest.main() 