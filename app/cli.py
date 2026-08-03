#!/usr/bin/env python3
"""Command line interface for the Drupal Helfi scraping tool.
"""

import argparse
import dataclasses
import datetime
import os
import signal
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

# Relative, so a run writes into the directory it was started from.
DEFAULT_OUTPUT = 'scraped_data.json'

# crawls/ and webcrawler/ are imported by name.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Lets scrapy find the project settings without relying on scrapy.cfg discovery.
os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'webcrawler.settings')

from config import CRAWLS_DIR, CrawlConfig, CrawlModuleError, available_modules
from download import DownloadError, download_site, github_access_name
from paths import CONFIG_DIR, DATA_DIR
from sites import (
    PROJECTS_DIR,
    PROJECTS_ENVIRONMENT_VARIABLE,
    REGISTRY_PATH,
    SiteError,
    registry,
    site_domain,
)
from webcrawler.pipelines import STDOUT_PATH, to_stdout


class CommandError(Exception):
    """A problem worth reporting to the user without a traceback."""


def module_list():
    """The available crawl modules."""
    modules = available_modules()
    if not modules:
        return ' (none found)'

    return '\n'.join(f' - {module}' for module in modules)


def command_list(args):
    print('Available crawl modules:')
    print(module_list())


def command_sites(args):
    print(f'Site copies in {PROJECTS_DIR}')
    print()

    for name, entry in sorted(registry.sites.items()):
        modified = registry.downloaded_at(name)

        if modified is None:
            state = 'missing'
        else:
            state = datetime.date.fromtimestamp(modified).isoformat()

        if entry.repo:
            source = entry.repo
        elif entry.url:
            source = entry.url
        else:
            source = f'no repo or url in {REGISTRY_PATH.name}'

        print(f'  {name:<38}{state:<13}{source}')


def user_directory(path):
    """One of the directories under $HOME, and whether it is being used."""
    if path is None:
        return 'none, there is no home directory'

    if not path.is_dir():
        return f'{path} (not there, the app folder is used instead)'

    return str(path)


def resolved_from(path):
    """Which of the directories a path that has a fallback ended up in."""
    for root, name in ((CONFIG_DIR, 'config directory'), (DATA_DIR, 'data directory')):
        if root is not None and Path(path).is_relative_to(root):
            return name

    return 'app folder'


def command_env(args):
    try:
        import scrapy
        scrapy_version = scrapy.__version__
    except ImportError:
        scrapy_version = 'not installed'

    # This is the command people run when something is wrong, so it reports
    # missing dependencies instead of failing on them.
    try:
        from webcrawler.spiders.helficopy import worker_count
        default_workers = worker_count()
    except ImportError:
        default_workers = 'unknown, dependencies are missing'

    if PROJECTS_DIR.is_dir():
        downloaded = sum(1 for name in registry.sites if registry.downloaded_at(name))
        copies = f'{downloaded} downloaded'
    else:
        copies = 'missing, run download'

    listed = f'{len(registry.sites)} sites'

    access = github_access_name() or 'none, needed to download artifacts'

    # Where the site copies came from is worth spelling out, since the
    # environment variable overrides both directories.
    if (os.environ.get(PROJECTS_ENVIRONMENT_VARIABLE) or '').strip():
        copies_from = PROJECTS_ENVIRONMENT_VARIABLE
    else:
        copies_from = resolved_from(PROJECTS_DIR)

    print(f'app directory:    {APP_DIR}')
    print(f'config directory: {user_directory(CONFIG_DIR)}')
    print(f'data directory:   {user_directory(DATA_DIR)}')
    print(f'site copies:      {PROJECTS_DIR} ({copies_from}, {copies})')
    print(f'site registry:    {REGISTRY_PATH} ({resolved_from(REGISTRY_PATH)}, {listed})')
    print(f'crawl modules:    {CRAWLS_DIR}')
    print(f'github access:    {access}')
    print(f'default output:   {os.path.abspath(DEFAULT_OUTPUT)}')
    print(f'default workers:  {default_workers}')
    print(f'python:           {sys.version.split()[0]}')
    print(f'scrapy:           {scrapy_version}')


# Downloading


def command_download(args):
    # A download replaces a two gigabyte copy, so it is always asked for by
    # name rather than falling back to whichever site a default would pick.
    if not args.site:
        raise CommandError(
            'No site given. Run: scrape sites download <site>\n\nKnown sites:\n'
            + registry.known_sites()
        )

    return download_site(args.site, args.allow_failed)


# Scraping


def missing_site(site):
    """What to say when there is no copy of the site to scrape."""
    present = [name for name in sorted(registry.sites) if registry.downloaded_at(name)]

    message = f'There is no copy of {site} at {registry.folder_path(site)}.\n'
    if present:
        message += f'Downloaded sites: {", ".join(present)}.\n'
    message += (
        f"Run 'scrape sites download {site_domain(site)}', or 'scrape sites' to "
        f'see the choices.'
    )

    return message


def command_scrape(args):
    # Without a site or a module there is nothing to scrape
    if args.site is None or args.module is None:
        args.parser.print_help()
        return 1

    if args.workers is not None and args.workers < 1:
        raise CommandError('--workers has to be at least 1.')

    entry = registry.site(args.site)
    config = CrawlConfig.load(args.module)

    # Bind CrawConfig to the site we have loaded.
    config = dataclasses.replace(
        config,
        website_path=args.site,
        layout=entry.layout,
    )

    if not registry.exists(args.site):
        raise CommandError(missing_site(args.site))

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from webcrawler.spiders.helficopy import HelficopySpider

    settings = get_project_settings()
    settings.set('LOG_LEVEL', args.log_level)
    output = args.output if args.output == STDOUT_PATH else os.path.abspath(args.output)
    settings.set('SCRAPED_DATA_OUTPUT', output)

    # Install SIGPIPE handler.
    if to_stdout(settings):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    process = CrawlerProcess(settings)
    crawler = process.create_crawler(HelficopySpider)
    process.crawl(crawler, config=config, workers=args.workers)
    process.start()

    matches = getattr(crawler.spider, 'matches', 0)

    if not to_stdout(settings):
        print(f'Done, {matches} matches written to {settings.get("SCRAPED_DATA_OUTPUT")}')


def build_parser():
    parser = argparse.ArgumentParser(
        prog='scrape',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', metavar='<command>')

    scrape = subparsers.add_parser(
        'scrape',
        help='scrape a downloaded site using a crawl module',
        description='Scrape a downloaded site using the rules in a crawl module.',
        epilog=(
            'Available sites:\n' + registry.known_sites()
            + '\n\nAvailable crawl modules:\n' + module_list()
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scrape.add_argument(
        'site',
        nargs='?',
        help='site to scrape, e.g. www.hel.fi, www.hel.fi/fi or historia.hel.fi',
    )
    scrape.add_argument(
        'module',
        nargs='?',
        help=(
            'crawl module to use or a path to a file of your own like ./my-search.py'
        ),
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
        default=DEFAULT_OUTPUT,
        help=f'where to write the results (default: ./{DEFAULT_OUTPUT})',
    )
    scrape.add_argument(
        '--log-level',
        default='WARNING',
        choices=LOG_LEVELS,
        help='how noisy the crawl should be (default: WARNING)',
    )
    scrape.set_defaults(handler=command_scrape, parser=scrape)

    site_listing = subparsers.add_parser(
        'sites',
        help='list the sites, and download copies of them',
        description='List the sites and which ones have been downloaded.',
        epilog='Known sites:\n' + registry.known_sites(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    site_listing.set_defaults(handler=command_sites)
    site_commands = site_listing.add_subparsers(dest='sites_command', metavar='<command>')

    download = site_commands.add_parser(
        'download',
        help='download the latest copy of a site',
        description=(
            'Download and unpack the latest copy of a site into projects/<site>.\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    download.add_argument(
        'site',
        nargs='?',
        metavar='SITE',
        help='site to download',
    )
    download.add_argument(
        '--allow-failed',
        action='store_true',
        help='accept a copy from a workflow run that did not succeed',
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
    try:
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.command is None:
            parser.print_help()
            return 1

        return args.handler(args) or 0
    except (CommandError, CrawlModuleError, DownloadError, SiteError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nInterrupted.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
