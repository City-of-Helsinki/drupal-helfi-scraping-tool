import multiprocessing
import os
import scrapy
import signal
import time  # Import the time library
import re  # import the regex library
from bs4 import BeautifulSoup
from w3lib.url import safe_url_string

from sites import registry

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

def worker_count(configured=None):
    """How many worker processes to use. Defaults to every core available."""
    if configured:
        return max(1, int(configured))
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:  # not available on every platform
        return max(1, os.cpu_count() or 1)

def compile_pattern(pattern):
    """Compile once instead of leaning on the re module cache for every file."""
    return re.compile(pattern) if pattern is not None else None

class WorkerState:
    """Everything a worker process needs to scrape a file on its own.

    The crawl module is chosen at runtime, so this is built in the spider and
    handed to the workers rather than living in module level globals.
    """

    def __init__(self, config, folder_path):
        self.folder_path = folder_path
        self.website_path = config.website_path
        self.layout = config.layout
        self.logic = config.custom_soup_and_loop_logic
        self.path_include_re = compile_pattern(config.regex_path_include_pattern)
        self.path_exclude_re = compile_pattern(config.regex_path_exclude_pattern)
        self.content_include_re = compile_pattern(config.regex_content_include_pattern)
        self.content_exclude_re = compile_pattern(config.regex_content_exclude_pattern)

class SpiderProxy:
    """Stand-in for the spider handed to custom_soup_and_loop_logic inside a worker.

    Workers cannot mutate the real spider, so they count their own matches and the
    parent adds them up as the results come back.
    """

    def __init__(self, website_path, folder_path):
        self.matches = 0
        self.website_path = website_path
        self.folder_path = folder_path

# Filled in by init_worker(), once per worker process.
worker = None

def init_worker(state):
    """Runs once in every worker process."""
    global worker
    worker = state

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
    if worker.content_exclude_re is not None and worker.content_exclude_re.search(content):
        return None

    # Include the file if regex_content_include_pattern is found in the content or not specified
    if worker.content_include_re is None or worker.content_include_re.search(content):
        return file_path

    return None

def kopio_url(file_path):
    """The url of a page in the httrack copy of the core site."""
    # Matches what scrapy.Request did to the file:// url the spider used to yield.
    url = safe_url_string('file://' + file_path.replace("#", "%23"))[7:]
    url = url.replace(worker.folder_path, "https://" + worker.website_path)
    return url.replace(".html", "")

def wget2_url(file_path):
    """The url of a page in a copy made by the scraping-tool workflow."""
    page = os.path.relpath(file_path, worker.folder_path).removesuffix('.html')

    # wget2 --mirror saves the page of a folder url inside that folder.
    if page == 'index':
        page = ''
    elif page.endswith('/index'):
        page = page[:-len('index')]

    # --restrict-file-names=windows escapes the characters a windows filesystem
    # will not take, which is how a query string ends up inside a filename. Only
    # the ? that begins it is turned back; anything escaped after that point was
    # escaped inside a value and belongs in the url as it is.
    page = page.replace('%3F', '?', 1)

    return safe_url_string('https://' + worker.website_path + '/' + page.replace('#', '%23'))

URL_BUILDERS = {
    'kopio': kopio_url,
    'wget2': wget2_url,
}

def public_url(file_path):
    """Turns a local file path into the https url of the page it is a copy of."""
    return URL_BUILDERS[worker.layout](file_path)

def scrape_file(file_path):
    """Scrapes a single file in a worker process. Returns (url, items, matches)."""
    with open(file_path, 'rb') as f:
        body = f.read()

    url = public_url(file_path)
    proxy = SpiderProxy(worker.website_path, worker.folder_path)
    items = list(worker.logic(proxy, body, url, BeautifulSoup))

    return url, items, proxy.matches

class HelficopySpider(scrapy.Spider):
    name = "helficopy"

    custom_settings = {
        'ITEM_PIPELINES': {'webcrawler.pipelines.JsonExportPipeline': 300},
    }

    def __init__(self, config=None, workers=None, *args, **kwargs):
        super(HelficopySpider, self).__init__(*args, **kwargs)
        self.matches = 0
        self.total_files = 0
        self.processed_files = 0
        self.all_start_time = None  # Initialize the all_start_time
        self.start_time = None  # Initialize the start_time
        self.config = config
        self.website_path = config.website_path # Website path from the crawl module
        self.folder_path = registry.folder_path(self.website_path)
        self.workers = worker_count(workers)
        self.state = WorkerState(config, self.folder_path)

        # Reading files and parsing html is pure python work, so threads would just
        # queue up behind the GIL. Fork a pool of processes instead. Forking here,
        # before the item pipeline opens its output file, keeps the workers from
        # inheriting a copy of it. Forking also means the state below is inherited
        # as is, so the compiled patterns and the crawl module's own function do
        # not have to survive pickling.
        self.pool = multiprocessing.get_context('fork').Pool(
            processes=self.workers,
            initializer=init_worker,
            initargs=(self.state,),
        )

    def closed(self, reason):
        self.pool.terminate()
        self.pool.join()

    async def start(self):

        print(f"Using crawl module: {self.config.name}")
        print(f"Scraping site: {self.website_path} ({self.config.layout} copy)")
        print(f"Scraping files from {self.folder_path} with {self.workers} workers")

        self.all_start_time = time.time()  # Record the start time

        # if use_path_regex:
        if self.config.regex_path_include_pattern is not None:
            print(f"Including file paths using pattern: {self.config.regex_path_include_pattern}")

        if self.config.regex_path_exclude_pattern is not None:
            print(f"Excluding file paths using pattern: {self.config.regex_path_exclude_pattern}")

        if self.config.regex_content_include_pattern is not None:
            print(f"Filtering file contents using pattern: {self.config.regex_content_include_pattern}")

        if self.config.regex_content_exclude_pattern is not None:
            print(f"Excluding file contents using pattern: {self.config.regex_content_exclude_pattern}")

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

            self.log_progress(url)

    def filtered_files(self):
        """The list of files to scrape, in os.walk order."""
        candidates = []
        path_include_re = self.state.path_include_re
        path_exclude_re = self.state.path_exclude_re

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
        if self.state.content_include_re is None and self.state.content_exclude_re is None:
            return [path for path in candidates if os.path.isfile(path)]

        # Otherwise every file has to be read, which is what the workers are for.
        chunk_size = max(1, min(256, len(candidates) // (self.workers * 4)))
        return [
            path
            for path in self.pool.imap(filter_file, candidates, chunksize=chunk_size)
            if path is not None
        ]

    def log_progress(self, url):
        """One line per file scraped, at INFO so --log-level can turn it off."""
        percentage_complete = (self.processed_files / self.total_files) * 100

        # Calculate elapsed and remaining time
        elapsed_time = time.time() - self.start_time
        all_elapsed_time = time.time() - self.all_start_time
        remaining_time = ((self.total_files - self.processed_files) / self.processed_files) * elapsed_time

        # Convert elapsed and remaining time to human-readable strings
        remaining_time_str = human_readable_time(remaining_time)
        elapsed_time_str = human_readable_time(all_elapsed_time)

        self.logger.info(
            f"{percentage_complete:.2f}% = {elapsed_time_str}, ({self.matches} matches) "
            f"remaining: {remaining_time_str} - {url}"
        )
