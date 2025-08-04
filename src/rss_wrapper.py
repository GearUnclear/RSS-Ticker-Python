#!/usr/bin/env python3
"""
Wrapper script to maintain backward compatibility with the original rss.py.
This allows the refactored code to be used with the same interface.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import and run the main function
from src.main import main

if __name__ == "__main__":
    main() 