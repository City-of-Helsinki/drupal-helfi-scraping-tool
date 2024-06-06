# config.py

import os
import importlib

# Get the module name from the environment variable or default to 'all'
scrape_module = os.getenv('SCRAPE_MODULE', 'all')
module_name = f'crawls.{scrape_module}'

# Dynamically import the module
try:
    # Attempt to dynamically import the chosen module
    module = importlib.import_module(module_name)
    print(f"Using crawl module: {scrape_module}")
except ModuleNotFoundError:
    # Fallback to 'all' if the chosen module is not found
    print(f"Warning: Module '{scrape_module}' not found. Falling back to 'all'.")
    module = importlib.import_module('crawls.all')

# Extract the required attributes from the module
website_path = getattr(module, 'website_path')
regex_content_include_pattern = getattr(module, 'regex_content_include_pattern')
regex_content_exclude_pattern = getattr(module, 'regex_content_exclude_pattern')
regex_path_include_pattern = getattr(module, 'regex_path_include_pattern')
regex_path_exclude_pattern = getattr(module, 'regex_path_exclude_pattern')
custom_soup_and_loop_logic = getattr(module, 'custom_soup_and_loop_logic')
