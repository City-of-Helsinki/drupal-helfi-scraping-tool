import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

from app.paths import APP_DIR

# The crawl modules that ship with the tool.
CRAWLS_DIR = APP_DIR / 'crawls'

# Every crawl module has to define these.
REQUIRED_ATTRIBUTES = (
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
    regex_path_include_pattern: Optional[str]
    regex_path_exclude_pattern: Optional[str]
    regex_content_include_pattern: Optional[str]
    regex_content_exclude_pattern: Optional[str]
    custom_soup_and_loop_logic: Callable

    # Which site to run against. It comes from the command line argument
    # <site>, so it is filled in by cli.py.
    website_path: str

    @classmethod
    def load(cls, name: str, site: str) -> 'CrawlConfig':
        """Imports a crawl module by name or by file path and returns its configuration."""

        # A file to a custom crawl module or name of a module in crawls/.
        given = Path(name).expanduser()

        if given.is_file():
            path = given.resolve()

            # Import custom module.
            module = import_file(path)
        else:
            path = CRAWLS_DIR / f'{name}.py'

            if not path.is_file():
                raise CrawlModuleError(
                    f"No crawl module named '{name}'.\n\n"
                    'Available modules:\n'
                    + '\n'.join(f' - {available}' for available in available_modules())
                    + '\n\nA path to a file of your own works too, e.g. ./my-search.py'
                )

            # Import built-in crawl module.
            module = importlib.import_module('app.crawls.' + name)

        # Validate crawl module.
        missing = [
            attribute for attribute in REQUIRED_ATTRIBUTES if not hasattr(module, attribute)
        ]
        if missing:
            raise CrawlModuleError(
                f'Crawl module {path} is missing: {", ".join(missing)}.\n'
                'See app/crawls/_example.py for a template.'
            )

        # Backwards compatability.
        if hasattr(module, 'website_path'):
            print(
                f'Warning: {path} still sets website_path. The site is now an '
                "argument: 'scraping-tool scrape <site> <module>'. The line can "
                'be removed.',
                file=sys.stderr,
            )

        return cls(
            name=name,
            website_path=site,
            **{attribute: getattr(module, attribute) for attribute in REQUIRED_ATTRIBUTES},
        )


def available_modules() -> list[str]:
    """The crawl module names that can be passed to CrawlConfig.load()."""
    return sorted(
        path.stem
        for path in CRAWLS_DIR.glob('*.py')
        if not path.name.startswith('_')
    )


def import_file(path: Path) -> ModuleType:
    """Imports a crawl module from the file it was given as."""
    safe_name = ''.join(c if c.isalnum() else '_' for c in path.stem)
    spec = importlib.util.spec_from_file_location(f'crawl_file_{safe_name}', path)
    module = importlib.util.module_from_spec(spec)

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


