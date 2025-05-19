#!/usr/bin/env python
"""
A utility script to update deprecated pandas frequency codes in all project files.
"""
import os
import re
import sys

def find_and_replace_frequencies(start_dir):
    """Find and replace deprecated pandas frequencies in Python files"""
    replacements = [
        (r"freq='h'", r"freq='h'"),  # Hourly
        (r'freq="h"', r'freq="h"'),  # Hourly
        (r"freq='ME'", r"freq='ME'"),  # Month end
        (r'freq="ME"', r'freq="ME"'),  # Month end
        (r"freq='YE'", r"freq='YE'"),  # Year end
        (r'freq="YE"', r'freq="YE"'),  # Year end
    ]
    
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    modified = False
                    for pattern, replacement in replacements:
                        if re.search(pattern, content):
                            content = re.sub(pattern, replacement, content)
                            modified = True
                    
                    if modified:
                        print(f"Updating pandas frequencies in: {filepath}")
                        with open(filepath, 'w') as f:
                            f.write(content)
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Searching for pandas frequency codes in: {project_root}")
    find_and_replace_frequencies(project_root)
    print("Done!")
