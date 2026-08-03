# sites.py

import os
import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).resolve().parent

# The container mounts projects/ outside the app directory, so the location is
# passed in. Running the cli directly finds it next to app/ instead.
PROJECTS_DIR_ENV = 'SCRAPING_TOOL_PROJECTS_DIR'
PROJECTS_DIR = Path(os.environ.get(PROJECTS_DIR_ENV) or APP_DIR.parent / 'projects')

REGISTRY_PATH = APP_DIR / 'sites.toml'

# What the reusable github workflow calls the copy it uploads. The same for
# every site, since they all call the same workflow.
ARTIFACT_NAME = 'scraping-tool-results'

# 'kopio'  the httrack copy of the www.hel.fi, from a kopio.hel.fi zip
# 'wget2'  what .github/workflows/scraping-tool.yml mirrors for other sites
LAYOUTS = ('kopio', 'wget2')
DEFAULT_LAYOUT = 'wget2'


class SiteError(Exception):
    """Raised when a site name or a registry entry cannot be used."""


@dataclass(frozen=True)
class Site:
    """A site the tool knows how to download."""

    domain: str
    repo: Optional[str] = None
    url: Optional[str] = None
    layout: str = DEFAULT_LAYOUT

    @classmethod
    def from_entry(cls, domain, entry) -> 'Site':
        """One [sites."domain"] table."""
        if not isinstance(entry, dict):
            raise SiteError('not a table')

        unknown = sorted(set(entry) - set(SITE_FIELDS))
        if unknown:
            raise SiteError(
                f'unknown key(s) {", ".join(unknown)}. '
                f'Known keys: {", ".join(SITE_FIELDS)}.'
            )

        values = {field: entry[field] for field in SITE_FIELDS if field in entry}

        layout = values.get('layout', DEFAULT_LAYOUT)
        if layout not in LAYOUTS:
            raise SiteError(
                f'layout "{layout}" is not one of {", ".join(LAYOUTS)}'
            )

        return cls(domain=domain, **values)


# The keys a site table may set: every field but the domain, which is the name
# of the table rather than a key inside it.
SITE_FIELDS = tuple(field.name for field in fields(Site) if field.name != 'domain')


def site_domain(site) -> str:
    """The hostname part of a site, which may also carry a path: www.hel.fi/fi."""
    return site.split('/')[0]


def check_site_name(site) -> str:
    """Rejects names that would point somewhere other than inside projects/."""
    if not site or site.startswith('/'):
        raise SiteError(f"'{site}' is not a usable site name.")

    if '..' in Path(site).parts:
        raise SiteError(f"'{site}' is not a usable site name.")

    return site


class Registry:
    """The sites listed in sites.toml, and where their copies are on disk."""

    def __init__(self, path=REGISTRY_PATH, projects_dir=PROJECTS_DIR):
        self.path = path
        self.projects_dir = projects_dir
        self._sites = None

    @property
    def sites(self) -> dict[str, Site]:
        """Every usable entry, keyed by domain.

        sites.toml is read by nearly every command. The config file
        is only parsed on first use and then cached.
        """
        if self._sites is None:
            self._sites = self._read()

        return self._sites

    def _read(self) -> dict[str, Site]:
        try:
            with open(self.path, 'rb') as registry_file:
                data = tomllib.load(registry_file)
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise SiteError(f'cannot read {self.path}: {error}') from error

        sites = {}
        for domain, entry in (data.get('sites') or {}).items():
            try:
                sites[domain] = Site.from_entry(domain, entry)
            except SiteError as error:
                print(
                    f'Warning: ignoring site "{domain}" in {self.path.name}: '
                    f'{error}',
                    file=sys.stderr,
                )

        return sites

    def known_sites(self) -> str:
        """The site names, one per line, for help and error messages."""
        listing = '\n'.join(f' - {name}' for name in sorted(self.sites))
        return listing or ' (none listed)'

    def site(self, site) -> Site:
        """The entry for a site. Accepts a path suffix."""
        domain = site_domain(site)
        entry = self.sites.get(domain)

        if entry is None:
            raise SiteError(
                f'{domain} is not in {self.path.name}.\n\nKnown sites:\n'
                + self.known_sites()
            )

        return entry

    def folder_path(self, site) -> str:
        """The folder to walk when scraping, path suffix included."""
        domain, _, rest = check_site_name(site).partition('/')
        root = self.projects_dir / domain

        # A kopio download is a whole httrack run, so the pages of the site are
        # one folder in, next to the other hosts it mirrored and httrack's own
        # files.
        if self.site(domain).layout == 'kopio':
            root = root / domain

        return str(root / rest) if rest else str(root)

    def exists(self, site) -> bool:
        return Path(self.folder_path(site)).is_dir()

    def downloaded_at(self, site) -> Optional[float]:
        """When the copy of a site was last replaced, or None if there is none."""
        try:
            return (self.projects_dir / site_domain(check_site_name(site))).stat().st_mtime
        except OSError:
            return None


# Registry singleton.
registry = Registry()
