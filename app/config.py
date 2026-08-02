# config.py
#
# Loading a crawl module is a function call, not an import side effect, so that
# nothing has to be decided before this file is imported.

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

CRAWLS_DIR = Path(__file__).resolve().parent / 'crawls'

# Every crawl module has to define these.
REQUIRED_ATTRIBUTES = (
    'website_path',
    'regex_path_include_pattern',
    'regex_path_exclude_pattern',
    'regex_content_include_pattern',
    'regex_content_exclude_pattern',
    'custom_soup_and_loop_logic',
)


class CrawlModuleError(Exception):
    """Raised when the requested crawl module cannot be used."""


@dataclass(frozen=True)
class CrawlConfig:
    """What a crawl module tells the spider to do."""

    name: str
    website_path: str
    regex_path_include_pattern: Optional[str]
    regex_path_exclude_pattern: Optional[str]
    regex_content_include_pattern: Optional[str]
    regex_content_exclude_pattern: Optional[str]
    custom_soup_and_loop_logic: Callable


def available_modules():
    """The crawl module names that can be passed to load_crawl_config()."""
    shared = sorted(
        path.stem
        for path in CRAWLS_DIR.glob('*.py')
        if not path.name.startswith('_')
    )
    custom = sorted(
        f'custom/{path.stem}'
        for path in (CRAWLS_DIR / 'custom').glob('*.py')
    )

    return shared + custom


def module_path(name):
    """Where the file for a crawl module name is expected to be."""
    # 'custom/list-of-links' lives in the gitignored crawls/custom/ folder.
    if name.startswith('custom/'):
        return CRAWLS_DIR / 'custom' / f"{name[len('custom/'):]}.py"

    return CRAWLS_DIR / f'{name}.py'


def load_crawl_config(name):
    """Imports a crawl module by name and returns its configuration."""
    path = module_path(name)

    # Checked up front so that a typo is reported as a typo. An ImportError
    # raised from inside a module that does exist is the author's own bug and is
    # left to propagate with its traceback intact.
    if not path.is_file():
        raise CrawlModuleError(
            f"No crawl module named '{name}'.\n\n"
            'Available modules:\n'
            + '\n'.join(f' - {available}' for available in available_modules())
        )

    module = importlib.import_module('crawls.' + name.replace('/', '.'))

    missing = [attribute for attribute in REQUIRED_ATTRIBUTES if not hasattr(module, attribute)]
    if missing:
        raise CrawlModuleError(
            f'Crawl module {path} is missing: {", ".join(missing)}.\n'
            'See app/crawls/custom/_example.py for a template.'
        )

    return CrawlConfig(
        name=name,
        **{attribute: getattr(module, attribute) for attribute in REQUIRED_ATTRIBUTES},
    )
