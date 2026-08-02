#!/usr/bin/env python3
"""Command line interface for the Drupal Helfi scraping tool.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DOWNLOADED_DIR = APP_DIR / 'downloaded'

LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

# crawls/ and webcrawler/ are imported by name.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Lets scrapy find the project settings without relying on scrapy.cfg discovery,
# which looks at the working directory.
os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'webcrawler.settings')

from config import CrawlModuleError, available_modules, load_crawl_config


class CommandError(Exception):
    """A problem worth reporting to the user without a traceback."""


def run_command(command):
    """Runs an external command, turning the usual failures into CommandError."""
    # The child writes straight to the terminal, so anything still sitting in our
    # own buffer has to go first or the output arrives out of order in a log.
    sys.stdout.flush()

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        raise CommandError(f"'{command[0]}' is not installed.")
    except subprocess.CalledProcessError as error:
        raise CommandError(f"'{command[0]}' failed with exit code {error.returncode}.")


def module_list():
    """The available crawl modules."""
    modules = available_modules()
    if not modules:
        return ' (none found)'

    return '\n'.join(f' - {module}' for module in modules)


def command_list(args):
    print('Available crawl modules:')
    print(module_list())


def command_env(args):
    try:
        import scrapy
        scrapy_version = scrapy.__version__
    except ImportError:
        scrapy_version = 'not installed'

    from webcrawler.pipelines import DEFAULT_OUTPUT

    # This is the command people run when something is wrong, so it reports
    # missing dependencies instead of failing on them.
    try:
        from webcrawler.spiders.helficopy import worker_count
        default_workers = worker_count()
    except ImportError:
        default_workers = 'unknown, dependencies are missing'

    downloaded_state = 'present' if DOWNLOADED_DIR.is_dir() else 'missing, run download'

    print(f'app directory:    {APP_DIR}')
    print(f'downloaded data:  {DOWNLOADED_DIR} ({downloaded_state})')
    print(f'default output:   {DEFAULT_OUTPUT}')
    print(f'default workers:  {default_workers}')
    print(f'python:           {sys.version.split()[0]}')
    print(f'scrapy:           {scrapy_version}')


def command_download(args):
    url = args.url
    if not url:
        raise CommandError('No URL given. Run: scrape download <url>')

    with tempfile.TemporaryDirectory() as temporary_directory:
        archive = Path(temporary_directory) / 'downloaded.zip'

        print(f'Downloading {url}')
        run_command(['wget', url, '-O', str(archive)])

        if DOWNLOADED_DIR.exists():
            print(f'Removing the previous copy at {DOWNLOADED_DIR}')
            shutil.rmtree(DOWNLOADED_DIR)

        print(f'Unpacking into {DOWNLOADED_DIR}')
        run_command(['unzip', '-q', str(archive), '-d', str(DOWNLOADED_DIR)])

    # Only the html is ever scraped, and the rest is most of the download size.
    removed = prune_non_html(DOWNLOADED_DIR)
    print(f'Removed {removed} non-html files. Ready to scrape.')


def prune_non_html(root):
    """Deletes everything that is not an .html file. Returns how many went."""
    removed = 0

    for directory, _directories, files in os.walk(root):
        for name in files:
            if not name.endswith('.html'):
                os.remove(os.path.join(directory, name))
                removed += 1

    return removed


def command_scrape(args):
    # Without a module there is nothing to scrape, and the thing people are
    # missing is the list of module names, so show that instead of a usage error.
    if args.module is None:
        args.parser.print_help()
        return 1

    if args.workers is not None and args.workers < 1:
        raise CommandError('--workers has to be at least 1.')

    # Resolved before scrapy starts up, so a typo in the module name is reported
    # immediately instead of somewhere inside the crawler.
    config = load_crawl_config(args.module)

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from webcrawler.spiders.helficopy import HelficopySpider, site_folder_path

    folder_path = site_folder_path(config.website_path)
    if not os.path.isdir(folder_path):
        raise CommandError(
            f'There is no copy of the site at {folder_path}.\n'
            f"Run 'download' first, or check the website_path in "
            f'{config.name}.'
        )

    settings = get_project_settings()
    settings.set('LOG_LEVEL', args.log_level)
    if args.output:
        settings.set('SCRAPED_DATA_OUTPUT', os.path.abspath(args.output))

    process = CrawlerProcess(settings)
    crawler = process.create_crawler(HelficopySpider)
    process.crawl(crawler, config=config, workers=args.workers)
    process.start()

    output_path = settings.get('SCRAPED_DATA_OUTPUT')
    if not output_path:
        from webcrawler.pipelines import DEFAULT_OUTPUT
        output_path = DEFAULT_OUTPUT

    matches = getattr(crawler.spider, 'matches', 0)
    print(f'Done, {matches} matches written to {output_path}')


def build_parser():
    parser = argparse.ArgumentParser(
        prog='scrape',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', metavar='<command>')

    scrape = subparsers.add_parser(
        'scrape',
        help='scrape the downloaded site using a crawl module',
        description='Scrape the downloaded site using the rules in a crawl module.',
        epilog='Available crawl modules:\n' + module_list(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scrape.add_argument(
        'module',
        nargs='?',
        help="crawl module to use, e.g. quotes or custom/my-search",
    )
    scrape.add_argument(
        '--workers',
        type=int,
        metavar='N',
        help='how many cpu cores to use (default: all of them)',
    )
    scrape.add_argument(
        '--output',
        metavar='PATH',
        help='where to write the results (default: app/scraped_data.json)',
    )
    scrape.add_argument(
        '--log-level',
        default='ERROR',
        choices=LOG_LEVELS,
        help='how noisy scrapy should be (default: ERROR)',
    )
    scrape.set_defaults(handler=command_scrape, parser=scrape)

    download = subparsers.add_parser(
        'download',
        help='download the latest copy of the site to scrape',
        description='Download and unpack the latest copy of the site into app/downloaded.',
        epilog='The url defaults to DOWNLOAD_URL environment variable if set',
    )
    download_url = os.environ.get('DOWNLOAD_URL')
    download.add_argument(
        'url',
        nargs='?',
        default=download_url,
        metavar='URL',
        # Only worth mentioning when there is something to mention.
        help='zip file to download' + (f' (default: {download_url})' if download_url else ''),
    )
    download.set_defaults(handler=command_download)

    listing = subparsers.add_parser('list', help='list the available crawl modules')
    listing.set_defaults(handler=command_list)

    environment = subparsers.add_parser(
        'env',
        help='show how the tool resolved its paths and settings',
    )
    environment.set_defaults(handler=command_env)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        return args.handler(args) or 0
    except (CommandError, CrawlModuleError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
