"""
Unit tests for notion_rate_limiter module
"""

import unittest
import time
from unittest.mock import Mock, patch

from notion_rate_limiter import (
    NotionTokenBucketRateLimiter,
    retry_on_429,
    rate_limiter,
    MAX_REQUESTS_PER_SECOND,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE
)


class TestNotionTokenBucketRateLimiter(unittest.TestCase):
    """Test NotionTokenBucketRateLimiter class"""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes with correct values"""
        limiter = NotionTokenBucketRateLimiter(rate=3.0, capacity=5)
        self.assertEqual(limiter.rate, 3.0)
        self.assertEqual(limiter.capacity, 5)
        self.assertEqual(limiter.tokens, 5)  # Should start full
        self.assertIsNotNone(limiter.last_update)
        self.assertIsNotNone(limiter.lock)
    
    def test_rate_limiter_default_values(self):
        """Test rate limiter uses default values when not specified"""
        limiter = NotionTokenBucketRateLimiter()
        self.assertEqual(limiter.rate, 3.0)
        self.assertEqual(limiter.capacity, 5)
    
    def test_rate_limiter_single_acquisition(self):
        """Test acquiring a single token"""
        limiter = NotionTokenBucketRateLimiter(rate=10.0, capacity=5)
        initial_tokens = limiter.tokens
        limiter.acquire(1)
        # Should have consumed 1 token
        self.assertLess(limiter.tokens, initial_tokens)
    
    def test_rate_limiter_multiple_acquisitions(self):
        """Test acquiring multiple tokens at once"""
        limiter = NotionTokenBucketRateLimiter(rate=10.0, capacity=5)
        initial_tokens = limiter.tokens
        limiter.acquire(3)
        # Should have consumed 3 tokens
        self.assertAlmostEqual(limiter.tokens, initial_tokens - 3, delta=0.1)
    
    def test_rate_limiter_blocks_when_empty(self):
        """Test that rate limiter blocks when tokens are depleted"""
        limiter = NotionTokenBucketRateLimiter(rate=10.0, capacity=2)
        
        # Acquire all tokens
        limiter.acquire(2)
        self.assertLess(limiter.tokens, 1)
        
        # Next acquire should block briefly until tokens refill
        start = time.time()
        limiter.acquire(1)
        elapsed = time.time() - start
        
        # Should have waited at least 0.05 seconds (accounting for timing variations)
        self.assertGreater(elapsed, 0.05)
        self.assertLess(elapsed, 0.2)  # But not too long
    
    def test_rate_limiter_refills_tokens_over_time(self):
        """Test that tokens refill over time"""
        limiter = NotionTokenBucketRateLimiter(rate=100.0, capacity=5)  # Fast refill
        
        # Acquire all tokens
        limiter.acquire(5)
        self.assertLess(limiter.tokens, 1)
        
        # Wait for refill
        time.sleep(0.1)  # Should refill 10 tokens, capped at 5
        
        # Try to acquire - should succeed without blocking
        start = time.time()
        limiter.acquire(1)
        elapsed = time.time() - start
        
        # Should be nearly instant
        self.assertLess(elapsed, 0.05)
    
    def test_rate_limiter_caps_at_capacity(self):
        """Test that tokens don't exceed capacity"""
        limiter = NotionTokenBucketRateLimiter(rate=10.0, capacity=3)
        
        # Wait longer than needed to refill
        time.sleep(1.0)
        
        # Even after waiting, should be capped at capacity
        limiter.acquire(1)
        # After acquiring 1, should have capacity - 1
        self.assertLessEqual(limiter.tokens, 2.1)


class TestRetryOn429(unittest.TestCase):
    """Test retry_on_429 decorator function"""
    
    @patch('notion_rate_limiter.rate_limiter')
    def test_retry_on_429_success_on_first_try(self, mock_limiter):
        """Test successful function call on first attempt"""
        mock_func = Mock(return_value='success')
        
        result = retry_on_429(mock_func, 'arg1', 'arg2', kwarg='value')
        
        self.assertEqual(result, 'success')
        mock_func.assert_called_once_with('arg1', 'arg2', kwarg='value')
        mock_limiter.acquire.assert_called_once()
    
    @patch('notion_rate_limiter.rate_limiter')
    @patch('notion_rate_limiter.time.sleep')
    def test_retry_on_429_retries_on_rate_limit(self, mock_sleep, mock_limiter):
        """Test retry behavior on 429 error"""
        mock_func = Mock()
        # Fail twice with 429, then succeed
        mock_func.side_effect = [
            Exception('429 Too Many Requests'),
            Exception('429 rate limit exceeded'),
            'success'
        ]
        
        result = retry_on_429(mock_func, max_retries=3)
        
        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 3)
        # Should have slept twice (exponential backoff: 2^0=1, 2^1=2)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1)  # First retry: 2^0
        mock_sleep.assert_any_call(2)  # Second retry: 2^1
    
    @patch('notion_rate_limiter.rate_limiter')
    @patch('notion_rate_limiter.time.sleep')
    def test_retry_on_429_exponential_backoff(self, mock_sleep, mock_limiter):
        """Test exponential backoff timing"""
        mock_func = Mock()
        mock_func.side_effect = [
            Exception('rate limit'),
            Exception('rate limit'),
            Exception('rate limit'),
            'success'
        ]
        
        result = retry_on_429(mock_func, max_retries=3)
        
        self.assertEqual(result, 'success')
        # Check backoff values: 2^0, 2^1, 2^2
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(calls, [1, 2, 4])
    
    @patch('notion_rate_limiter.rate_limiter')
    @patch('notion_rate_limiter.time.sleep')
    def test_retry_on_429_gives_up_after_max_retries(self, mock_sleep, mock_limiter):
        """Test that retry gives up after max retries"""
        mock_func = Mock(side_effect=Exception('429 Too Many Requests'))
        
        with self.assertRaises(Exception) as context:
            retry_on_429(mock_func, max_retries=2)
        
        self.assertIn('429', str(context.exception))
        # Should try: initial + 2 retries = 3 times
        self.assertEqual(mock_func.call_count, 3)
        # Should sleep 2 times (after each failed retry except the last)
        self.assertEqual(mock_sleep.call_count, 2)
    
    @patch('notion_rate_limiter.rate_limiter')
    def test_retry_on_429_does_not_retry_non_rate_limit_errors(self, mock_limiter):
        """Test that non-rate-limit errors are not retried"""
        mock_func = Mock(side_effect=ValueError('Some other error'))
        
        with self.assertRaises(ValueError):
            retry_on_429(mock_func, max_retries=3)
        
        # Should only try once (no retries for non-429 errors)
        mock_func.assert_called_once()
    
    @patch('notion_rate_limiter.rate_limiter')
    @patch('notion_rate_limiter.time.sleep')
    def test_retry_on_429_recognizes_various_error_messages(self, mock_sleep, mock_limiter):
        """Test that different 429-related error messages are recognized"""
        error_messages = [
            '429 Too Many Requests',
            'Rate limit exceeded',
            'Too many requests, please slow down',
            'HTTP 429 error occurred',
            'Error: rate limit reached'
        ]
        
        for error_msg in error_messages:
            mock_func = Mock()
            mock_func.side_effect = [Exception(error_msg), 'success']
            
            result = retry_on_429(mock_func, max_retries=1)
            self.assertEqual(result, 'success', f"Failed to retry on: {error_msg}")
    
    @patch('notion_rate_limiter.rate_limiter')
    @patch('notion_rate_limiter.time.sleep')
    def test_retry_on_429_with_custom_max_retries(self, mock_sleep, mock_limiter):
        """Test using custom max_retries parameter"""
        mock_func = Mock(side_effect=Exception('429'))
        
        with self.assertRaises(Exception):
            retry_on_429(mock_func, max_retries=5)
        
        # Should try: initial + 5 retries = 6 times
        self.assertEqual(mock_func.call_count, 6)
    
    @patch('notion_rate_limiter.rate_limiter')
    def test_retry_on_429_preserves_function_arguments(self, mock_limiter):
        """Test that function arguments are preserved across retries"""
        mock_func = Mock()
        mock_func.side_effect = [Exception('429'), 'success']
        
        result = retry_on_429(mock_func, 'arg1', 'arg2', kwarg1='val1', kwarg2='val2')
        
        # Both calls should have same arguments
        self.assertEqual(mock_func.call_count, 2)
        for call in mock_func.call_args_list:
            self.assertEqual(call[0], ('arg1', 'arg2'))
            self.assertEqual(call[1], {'kwarg1': 'val1', 'kwarg2': 'val2'})


class TestGlobalRateLimiter(unittest.TestCase):
    """Test the global rate_limiter instance"""
    
    def test_global_rate_limiter_exists(self):
        """Test that global rate_limiter instance exists"""
        self.assertIsInstance(rate_limiter, NotionTokenBucketRateLimiter)
    
    def test_global_rate_limiter_has_correct_rate(self):
        """Test that global rate_limiter has correct rate"""
        self.assertEqual(rate_limiter.rate, MAX_REQUESTS_PER_SECOND)
    
    def test_global_rate_limiter_has_correct_capacity(self):
        """Test that global rate_limiter has correct capacity"""
        self.assertEqual(rate_limiter.capacity, 5)


class TestConstants(unittest.TestCase):
    """Test module constants"""
    
    def test_max_requests_per_second_value(self):
        """Test MAX_REQUESTS_PER_SECOND constant"""
        self.assertEqual(MAX_REQUESTS_PER_SECOND, 3.0)
    
    def test_max_retries_value(self):
        """Test MAX_RETRIES constant"""
        self.assertEqual(MAX_RETRIES, 3)
    
    def test_retry_backoff_base_value(self):
        """Test RETRY_BACKOFF_BASE constant"""
        self.assertEqual(RETRY_BACKOFF_BASE, 2)


if __name__ == '__main__':
    unittest.main()
