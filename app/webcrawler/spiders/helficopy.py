from config import (
    website_path,
    regex_content_include_pattern,
    regex_content_exclude_pattern,
    regex_path_include_pattern,
    regex_path_exclude_pattern,
    custom_soup_and_loop_logic,
)

import multiprocessing
import os
import scrapy
import signal
import time  # Import the time library
import re  # import the regex library
from bs4 import BeautifulSoup
from w3lib.url import safe_url_string

# Compile once instead of leaning on the re module cache for every file.
path_include_re = re.compile(regex_path_include_pattern) if regex_path_include_pattern is not None else None
path_exclude_re = re.compile(regex_path_exclude_pattern) if regex_path_exclude_pattern is not None else None
content_include_re = re.compile(regex_content_include_pattern) if regex_content_include_pattern is not None else None
content_exclude_re = re.compile(regex_content_exclude_pattern) if regex_content_exclude_pattern is not None else None

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

def worker_count():
    """How many worker processes to use. Override with the SCRAPE_WORKERS env variable."""
    configured = os.getenv('SCRAPE_WORKERS')
    if configured:
        return max(1, int(configured))
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:  # not available on every platform
        return max(1, os.cpu_count() or 1)

class SpiderProxy:
    """Stand-in for the spider handed to custom_soup_and_loop_logic inside a worker.

    Workers cannot mutate the real spider, so they count their own matches and the
    parent adds them up as the results come back.
    """

    def __init__(self, website_path, folder_path):
        self.matches = 0
        self.website_path = website_path
        self.folder_path = folder_path

# Per worker process state, filled in by init_worker().
worker_folder_path = None
worker_website_path = None

def init_worker(folder_path, site_path):
    """Runs once in every worker process."""
    global worker_folder_path, worker_website_path
    worker_folder_path = folder_path
    worker_website_path = site_path

    # Forking inherits the shutdown handlers scrapy installed in the parent, which
    # would keep the workers alive when the pool tries to terminate them.
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # let the parent deal with ctrl-c
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

def filter_file(file_path):
    """Applies the file content patterns. Returns the path when it should be scraped."""
    if not os.path.isfile(file_path):
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Exclude the file if regex_content_exclude_pattern is found in the content
    if content_exclude_re is not None and content_exclude_re.search(content):
        return None

    # Include the file if regex_content_include_pattern is found in the content or not specified
    if content_include_re is None or content_include_re.search(content):
        return file_path

    return None

def public_url(file_path):
    """Turns a local file path into the https url of the page it is a copy of."""
    # Matches what scrapy.Request did to the file:// url the spider used to yield.
    url = safe_url_string('file://' + file_path.replace("#", "%23"))[7:]
    url = url.replace(worker_folder_path, "https://" + worker_website_path)
    return url.replace(".html", "")

def scrape_file(file_path):
    """Scrapes a single file in a worker process. Returns (url, items, matches)."""
    with open(file_path, 'rb') as f:
        body = f.read()

    url = public_url(file_path)
    proxy = SpiderProxy(worker_website_path, worker_folder_path)
    items = list(custom_soup_and_loop_logic(proxy, body, url, BeautifulSoup))

    return url, items, proxy.matches

class HelficopySpider(scrapy.Spider):
    name = "helficopy"

    print(f"Scraper v2.0")

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
        self.workers = worker_count()

        # Reading files and parsing html is pure python work, so threads would just
        # queue up behind the GIL. Fork a pool of processes instead. Forking here,
        # before the item pipeline opens its output file, keeps the workers from
        # inheriting a copy of it.
        self.pool = multiprocessing.get_context('fork').Pool(
            processes=self.workers,
            initializer=init_worker,
            initargs=(self.folder_path, self.website_path),
        )

    def closed(self, reason):
        self.pool.terminate()
        self.pool.join()

    async def start(self):

        print(f"Scraping files from {self.folder_path} with {self.workers} workers")

        self.all_start_time = time.time()  # Record the start time

        # if use_path_regex:
        if regex_path_include_pattern is not None:
            print(f"Including file paths using pattern: {regex_path_include_pattern}")

        if regex_path_exclude_pattern is not None:
            print(f"Excluding file paths using pattern: {regex_path_exclude_pattern}")

        if regex_content_include_pattern is not None:
            print(f"Filtering file contents using pattern: {regex_content_include_pattern}")

        if regex_content_exclude_pattern is not None:
            print(f"Excluding file contents using pattern: {regex_content_exclude_pattern}")

        filtered_files = self.filtered_files()
        self.total_files = len(filtered_files)

        print(f"Found {self.total_files} files to scrape in {human_readable_time(time.time() - self.all_start_time)}")

        self.start_time = time.time()  # Record the start time

        # Actual scraping happens in the worker processes. imap keeps the results in
        # the same order the files were found in, so the output does not depend on
        # which worker happened to finish first.
        chunk_size = max(1, min(16, self.total_files // (self.workers * 16)))
        for url, items, matches in self.pool.imap(scrape_file, filtered_files, chunksize=chunk_size):
            self.processed_files += 1
            self.matches += matches

            for item in items:  # async generators cannot yield from
                yield item

            self.print_progress(url)

    def filtered_files(self):
        """The list of files to scrape, in os.walk order."""
        candidates = []

        # Path patterns are cheap, so they are applied while walking the folder.
        for root, dirs, files in os.walk(self.folder_path):
            for file in files:
                if not file.endswith('.html'):
                    continue

                file_path = os.path.join(root, file)

                # Verify that file_path matches the regex pattern
                if path_include_re is not None and not path_include_re.search(file_path):
                    continue

                # Verify that file_path does not match the regex pattern
                if path_exclude_re is not None and path_exclude_re.search(file_path):
                    continue

                candidates.append(file_path)

        # Without content patterns there is nothing to look for inside the files,
        # so skip reading them altogether.
        if content_include_re is None and content_exclude_re is None:
            return [path for path in candidates if os.path.isfile(path)]

        # Otherwise every file has to be read, which is what the workers are for.
        chunk_size = max(1, min(256, len(candidates) // (self.workers * 4)))
        return [
            path
            for path in self.pool.imap(filter_file, candidates, chunksize=chunk_size)
            if path is not None
        ]

    def print_progress(self, url):
        percentage_complete = (self.processed_files / self.total_files) * 100

        # Calculate elapsed and remaining time
        elapsed_time = time.time() - self.start_time
        all_elapsed_time = time.time() - self.all_start_time
        remaining_time = ((self.total_files - self.processed_files) / self.processed_files) * elapsed_time

        # Convert elapsed and remaining time to human-readable strings
        remaining_time_str = human_readable_time(remaining_time)
        elapsed_time_str = human_readable_time(all_elapsed_time)

        print(f"{percentage_complete:.2f}% = {elapsed_time_str}, ({self.matches} matches) remaining: {remaining_time_str} - {url}")
