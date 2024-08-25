import pytest
import os

def run_tests():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Run pytest on all test files in the current directory
    pytest.main([current_dir, "-v"])

if __name__ == "__main__":
    run_tests()