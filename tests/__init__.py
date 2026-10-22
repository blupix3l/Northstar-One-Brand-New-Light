"""
Regression tests for NorthStar search fixes.

Run with:  python -m unittest discover -s tests
(or)       python -m unittest tests.test_is_url tests.test_provider_merge tests.test_concurrent_search -v

These tests use stdlib only (unittest) and avoid network access by
injecting lightweight fake providers.
"""

import os
import sys
import tempfile
import unittest

# Make the project root importable when run from anywhere.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
