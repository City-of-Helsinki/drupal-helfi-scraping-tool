# config.py
#
# Loading a crawl module is a function call, not an import side effect, so that
# nothing has to be decided before this file is imported.

import importlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

from sites import DEFAULT_LAYOUT

CRAWLS_DIR = Path(__file__).resolve().parent / 'crawls'

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
    # Which site to run against and what shape its copy is in. Both come from
    # the command line, not from the module, so they are filled in afterwards.
    website_path: str = ''
    layout: str = DEFAULT_LAYOUT

    @classmethod
    def load(cls, name: str) -> 'CrawlConfig':
        """Imports a crawl module by name or by file path and returns its configuration."""
        # A file of your own, taken as written, extension and all. Anything else
        # is the name of a module in crawls/.
        given = Path(name).expanduser()

        if given.is_file():
            path = given.resolve()
            module = import_file(path)
        else:
            path = module_path(name)

            if not path.is_file():
                raise CrawlModuleError(
                    f"No crawl module named '{name}'.\n\n"
                    'Available modules:\n'
                    + '\n'.join(f' - {available}' for available in available_modules())
                    + '\n\nA path to a file of your own works too, e.g. ./my-search.py'
                )

            module = importlib.import_module('crawls.' + name.replace('/', '.'))

        missing = [
            attribute for attribute in REQUIRED_ATTRIBUTES if not hasattr(module, attribute)
        ]
        if missing:
            raise CrawlModuleError(
                f'Crawl module {path} is missing: {", ".join(missing)}.\n'
                'See app/crawls/custom/_example.py for a template.'
            )

        # Backwards compatability.
        if hasattr(module, 'website_path'):
            print(
                f'Warning: {path} still sets website_path. The site is now an '
                "argument: 'scrape <site> <module>'. The line can be removed.",
                file=sys.stderr,
            )

        return cls(
            name=name,
            **{attribute: getattr(module, attribute) for attribute in REQUIRED_ATTRIBUTES},
        )


def available_modules() -> list[str]:
    """The crawl module names that can be passed to CrawlConfig.load()."""
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


def module_path(name: str) -> Path:
    """Where the file for a crawl module name is expected to be."""
    # 'custom/list-of-links' lives in the gitignored crawls/custom/ folder.
    if name.startswith('custom/'):
        return CRAWLS_DIR / 'custom' / f"{name[len('custom/'):]}.py"

    return CRAWLS_DIR / f'{name}.py'


def import_file(path: Path) -> ModuleType:
    """Imports a crawl module from a file outside crawls/."""
    # The name only has to be unique in sys.modules; the file is what matters.
    safe_name = ''.join(c if c.isalnum() else '_' for c in path.stem)
    spec = importlib.util.spec_from_file_location(f'crawl_file_{safe_name}', path)
    module = importlib.util.module_from_spec(spec)

    # Registered before it runs, the way import does, and left there so that the
    # function it defines keeps its globals while the workers are calling it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


