#!/usr/bin/env python3
"""Command line interface for the Drupal Helfi scraping tool.
"""

import argparse
import datetime
import os
import signal
import sys

LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

DEFAULT_OUTPUT = 'scraped_data.json'

os.environ.setdefault('SCRAPY_SETTINGS_MODULE', 'app.webcrawler.settings')

from app.config import (
    CRAWLS_DIR,
    CrawlConfig,
    CrawlModuleError,
    available_modules,
)
from app.download import (
    DownloadError,
    download_site,
    require_github_cli,
)
from app.paths import CONFIG_DIR
from app.sites import (
    PROJECTS_DIR,
    REGISTRY_PATH,
    SiteError,
    registry,
    site_domain,
)
from app.webcrawler.pipelines import STDOUT_PATH, to_stdout


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


def command_env(args):
    try:
        import scrapy
        scrapy_version = scrapy.__version__
    except ImportError:
        scrapy_version = 'not installed'

    listed = f'{len(registry.sites)} sites'

    print(f'config directory: {CONFIG_DIR}')
    print(f'site copies:      {PROJECTS_DIR}')
    print(f'site registry:    {REGISTRY_PATH} ({listed})')
    print(f'crawl modules:    {CRAWLS_DIR}')

    try:
        require_github_cli()
    except DownloadError:
        print(f'github access:    github cli missing')

    print(f'default output:   {os.path.abspath(DEFAULT_OUTPUT)}')
    print(f'python:           {sys.version.split()[0]}')
    print(f'scrapy:           {scrapy_version}')


# Downloading


def command_download(args):
    if not args.site:
        raise CommandError(
            'No site given. Run: scraping-tool sites download <site>\n\nKnown sites:\n'
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
        f"Run 'scraping-tool sites download {site_domain(site)}', or "
        f"'scraping-tool sites' to see the choices."
    )

    return message


def command_scrape(args):
    # Without a site or a module there is nothing to scrape
    if args.site is None or args.module is None:
        args.parser.print_help()
        return 1

    if args.workers is not None and args.workers < 1:
        raise CommandError('--workers has to be at least 1.')

    config = CrawlConfig.load(args.module, args.site)

    if not registry.exists(args.site):
        raise CommandError(missing_site(args.site))

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from app.webcrawler.spiders.helficopy import HelficopySpider

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
        prog='scraping-tool',
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
