from config import (
    website_path,
    regex_content_include_pattern,
    regex_content_exclude_pattern,
    regex_path_include_pattern,
    regex_path_exclude_pattern,
    custom_soup_and_loop_logic,
)

import os
import scrapy
import time  # Import the time library
import re  # import the regex library
from bs4 import BeautifulSoup
from scrapy.http import HtmlResponse
from scrapy.spiders import Spider
from webcrawler.pipelines import JsonExportPipeline

def human_readable_time(seconds):
    """Converts time in seconds to a human-readable string."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{int(hours)}h, {int(minutes)}m, {int(seconds)}s"
    elif minutes:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

class HelficopySpider(scrapy.Spider):
    name = "helficopy"

    print(f"Scraper v1.0")

    custom_settings = {
        'ITEM_PIPELINES': {'webcrawler.pipelines.JsonExportPipeline': 300},
    }

    def __init__(self, *args, **kwargs):
        super(HelficopySpider, self).__init__(*args, **kwargs)
        self.matches = 0
        self.total_files = 0
        self.processed_files = 0
        self.all_start_time = None  # Initialize the all_start_time
        self.start_time = None  # Initialize the start_time
        self.current_directory = os.getcwd()  # Get current working directory
        self.relative_folder_path = 'downloaded/' # Relative path to the folder to crawl
        self.website_path = website_path # Website path from config.py
        self.folder_path = os.path.join(self.current_directory, self.relative_folder_path, self.website_path) # Make the folder_path absolute

    def start_requests(self):

        print(f"Scraping files from {self.folder_path}")

        self.all_start_time = time.time()  # Record the start time

        # Initialize list to store filtered files
        filtered_files = []

        # if use_path_regex:
        if regex_path_include_pattern is not None:
            print(f"Including file paths using pattern: {regex_path_include_pattern}")

        if regex_path_exclude_pattern is not None:
            print(f"Excluding file paths using pattern: {regex_path_exclude_pattern}")

        if regex_content_include_pattern is not None:
            print(f"Filtering file contents using pattern: {regex_content_include_pattern}")

        if regex_content_exclude_pattern is not None:
            print(f"Excluding file contents using pattern: {regex_content_exclude_pattern}")

        # Preliminary loop to filter files
        for root, dirs, files in os.walk(self.folder_path):
            for file in files:
                if file.endswith('.html'):
                    file_path = os.path.join(root, file)

                    # Verify that file_path matches the regex pattern
                    if regex_path_include_pattern is not None and not re.search(regex_path_include_pattern, file_path):
                        continue

                    # Verify that file_path does not match the regex pattern
                    if regex_path_exclude_pattern is not None and re.search(regex_path_exclude_pattern, file_path):
                        continue


                    # if regex_content_include_pattern is not None:

                    #     # Check if file_path is a file and if it contains the regex pattern
                    #     if os.path.isfile(file_path):
                    #         with open(file_path, 'r', encoding='utf-8') as f:
                    #             content = f.read()
                    #             if re.search(regex_content_include_pattern, content):
                    #                 if regex_content_exclude_pattern is not None and re.search(regex_content_exclude_pattern, content):
                    #                     continue
                    #                 filtered_files.append(file_path)
                    #                 self.total_files += 1

                    # Check if file_path is a file
                    if os.path.isfile(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                            # Exclude the file if regex_content_exclude_pattern is found in the content
                            if regex_content_exclude_pattern is not None and re.search(regex_content_exclude_pattern, content):
                                # print(f"Content exclude: {regex_content_exclude_pattern} {file_path}")
                                continue

                            # Include the file if regex_content_include_pattern is found in the content or not specified
                            if regex_content_include_pattern is None or re.search(regex_content_include_pattern, content):
                                # print(f"Adding: {file_path}")
                                filtered_files.append(file_path)
                                self.total_files += 1
                    else:
                        # Check if file_path is a file and if it contains the regex pattern
                        if os.path.isfile(file_path):
                            self.total_files += 1
                            filtered_files.append(file_path)

        print(f"Found {self.total_files} files to scrape in {human_readable_time(time.time() - self.all_start_time)}")

        self.start_time = time.time()  # Record the start time

        # Actual crawling starts here using the filtered list
        for file_path in filtered_files:
            file_path = file_path.replace("#", "%23")
            yield scrapy.Request('file://' + file_path, callback=self.parse)

    def parse(self, response):
        self.processed_files += 1
        percentage_complete = (self.processed_files / self.total_files) * 100

        # Calculate elapsed and remaining time
        elapsed_time = time.time() - self.start_time
        all_elapsed_time = time.time() - self.all_start_time
        remaining_time = ((self.total_files - self.processed_files) / self.processed_files) * elapsed_time

        # Convert elapsed and remaining time to human-readable strings
        remaining_time_str = human_readable_time(remaining_time)
        elapsed_time_str = human_readable_time(all_elapsed_time)

        # Get the URL of the current page
        url = response.url[7:]  # Remove 'file://' prefix
        url = url.replace(self.folder_path, "https://"+self.website_path)
        url = url.replace(".html", "")

        # Call custom_soup_and_loop_logic function and yield results
        yield from custom_soup_and_loop_logic(self, response.body, url, BeautifulSoup)

        # Print progress
        # print(f"{percentage_complete:.2f}% = {elapsed_time_str}, ({self.matches} matches) remaining: {remaining_time_str} - {url} - {response.url[7:].replace(self.current_directory+'/', '')}")
        print(f"{percentage_complete:.2f}% = {elapsed_time_str}, ({self.matches} matches) remaining: {remaining_time_str} - {url}")

