# download.py
#
# Getting a copy of a site onto the disk as projects/<domain>. Most sites come
# from an artifact a github workflow uploaded, the core site from a plain zip.

import http.client
import json
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator, Optional

from sites import ARTIFACT_NAME, PROJECTS_DIR, REGISTRY_PATH, registry

GITHUB_API = 'https://api.github.com'
USER_AGENT = 'drupal-helfi-scraping-tool'
TOKEN_VARIABLES = ('GITHUB_TOKEN', 'GH_TOKEN')
REDIRECT_CODES = (301, 302, 303, 307, 308)

TOKEN_HELP = (
    'A github token is needed to download an artifact, even from a public repository.\n'
    'Create one at https://github.com/settings/tokens and add it to .env.local:\n'
    '\n'
    '  GITHUB_TOKEN=...\n'
    '\n'
    "A classic token needs the 'public_repo' scope. A fine grained token needs\n"
    'read access to Actions on the repository.'
)


class DownloadError(Exception):
    """Raised when a copy of a site cannot be fetched or unpacked."""


def github_token() -> tuple[Optional[str], Optional[str]]:
    """The token to talk to github with, and the variable it came from."""
    for name in TOKEN_VARIABLES:
        value = (os.environ.get(name) or '').strip()
        if value:
            return value, name

    return None, None


def github_request(url: str, token: Optional[str]) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': USER_AGENT,
            **({'Authorization': f'Bearer {token}'} if token else {}),
        },
    )


def github_error(error: urllib.error.HTTPError, url: str) -> DownloadError:
    """A DownloadError explaining an http error from the github api."""
    if error.code == 401:
        detail = 'The token was rejected. Check GITHUB_TOKEN in .env.local.'
    elif error.code == 403:
        if error.headers.get('x-ratelimit-remaining') == '0':
            detail = 'Rate limited by github. Try again in a while.'
        else:
            detail = (
                'Access denied. If the organisation uses single sign-on, the token '
                'has to be authorised for it.'
            )
    elif error.code == 404:
        detail = 'Not found. Check the repository name, and that the token can read it.'
    else:
        detail = error.reason

    return DownloadError(f'{url}\n  github said {error.code}: {detail}')


def github_json(url: str, token: Optional[str]) -> dict:
    """The json body of a github api response, which is always an object."""
    try:
        with urllib.request.urlopen(github_request(url, token)) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise github_error(error, url)
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach {url}: {error.reason}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stops urllib from following github's redirect on our behalf."""

    # The arguments are urllib's to pass, so they are left as it declares them.
    def redirect_request(self, req, fp, code, msg, headers, newurl) -> None:
        return None


def open_artifact(url: str, token: str) -> http.client.HTTPResponse:
    """Opens the artifact zip for reading."""
    opener = urllib.request.build_opener(NoRedirect)

    try:
        return opener.open(github_request(url, token))
    except urllib.error.HTTPError as error:
        location = error.headers.get('Location') if error.code in REDIRECT_CODES else None
        if not location:
            raise github_error(error, url)
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach {url}: {error.reason}')

    # The redirect points at storage with the credentials already in the url,
    # and it answers with an error if an Authorization header comes along too.
    try:
        return urllib.request.urlopen(
            urllib.request.Request(location, headers={'User-Agent': USER_AGENT})
        )
    except urllib.error.HTTPError as error:
        raise github_error(error, location)
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach the artifact: {error.reason}')


def open_url(url: str) -> http.client.HTTPResponse:
    """Opens a plain zip url for reading, the way the core copy is served."""
    try:
        return urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        )
    except urllib.error.HTTPError as error:
        raise DownloadError(f'{url}\n  the server said {error.code}: {error.reason}')
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach {url}: {error.reason}')


def megabytes(count: int) -> str:
    size = count / 1024 / 1024
    return f'{size:.1f} MB' if size < 10 else f'{size:.0f} MB'


def stream_to_file(response: http.client.HTTPResponse, destination: Path) -> None:
    """Copies the response into a file, reporting how it is going."""
    total = int(response.headers.get('Content-Length') or 0)
    copied = 0
    # Nothing to report until the download has been going for a while.
    reported = time.monotonic()

    with open(destination, 'wb') as target:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break

            target.write(chunk)
            copied += len(chunk)

            now = time.monotonic()
            if now - reported > 1:
                reported = now
                if total:
                    print(
                        f'  {copied / total * 100:.0f}% of {megabytes(total)}',
                        end='\r',
                        flush=True,
                    )
                else:
                    print(f'  {megabytes(copied)}', end='\r', flush=True)

    # Wide enough to wipe the progress that was left on the line.
    print(f'\r  {megabytes(copied)} downloaded.'.ljust(30))


def artifacts_in(repo: str, token: str) -> Iterator[dict]:
    """Every copy of a site in a repository, newest first."""
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {'name': ARTIFACT_NAME, 'per_page': 100, 'page': page}
        )
        answer = github_json(
            f'{GITHUB_API}/repos/{repo}/actions/artifacts?{query}', token
        )

        artifacts = answer.get('artifacts') or []
        if not artifacts:
            return

        yield from artifacts

        if page * 100 >= answer.get('total_count', 0):
            return

        page += 1


def latest_artifact(repo: str, token: str, allow_failed: bool) -> tuple[dict, dict]:
    """The newest usable copy of a site, as (artifact, workflow run)."""
    expired = 0
    unsuccessful = []

    for artifact in artifacts_in(repo, token):
        if artifact.get('expired'):
            expired += 1
            continue

        # Whether the run succeeded is not in the listing, so it takes a second
        # request to find out.
        run_id = (artifact.get('workflow_run') or {}).get('id')
        run = (
            github_json(f'{GITHUB_API}/repos/{repo}/actions/runs/{run_id}', token)
            if run_id
            else {}
        )
        conclusion = run.get('conclusion')

        # The workflow uploads whatever it managed to mirror even when it fails,
        # so a failed run means a copy with pages missing from it.
        if conclusion != 'success' and not allow_failed:
            unsuccessful.append(conclusion or 'unfinished')
            continue

        return artifact, run

    problems = []
    if expired:
        problems.append(f'{expired} expired')
    if unsuccessful:
        problems.append(f'{len(unsuccessful)} from runs that did not succeed')

    raise DownloadError(
        f"No usable '{ARTIFACT_NAME}' artifact in {repo}"
        + (f' ({", ".join(problems)})' if problems else '')
        + '.\n'
        f'Artifacts are kept for 40 days, so the workflow may need to be run again:\n'
        f'  https://github.com/{repo}/actions'
        + ('\nOr pass --allow-failed to take the copy from a failed run.' if unsuccessful else '')
    )


def install_unpacked(unpacked: Path, domain: str) -> None:
    """Puts an unpacked download in place as projects/<domain>."""
    if not (unpacked / domain).is_dir():
        contents = ', '.join(child.name for child in sorted(unpacked.iterdir()))
        raise DownloadError(
            f'The zip has no {domain} folder in it, so it is not a copy of that '
            f'site.\nIt contains: {contents or "(nothing)"}'
        )

    # A kopio zip is a whole httrack run, so the copy is everything in it and
    # the pages are one folder in. Keeping all of it is what makes the other
    # hosts it mirrored a detail of the copy instead of sites of their own.
    source = unpacked if registry.site(domain).layout == 'kopio' else unpacked / domain
    final = PROJECTS_DIR / domain

    print(f'Moving the copy into {PROJECTS_DIR}')

    # Removing the previous copy rather than writing over it is what makes a page
    # that no longer exists disappear from it. Nothing is kept aside in case the
    # move fails: a download is repeatable, and running it again is a better
    # answer than the bookkeeping that keeping a spare copy of two gigabytes
    # would take.
    if final.exists():
        shutil.rmtree(final)

    # A rename when the temporary directory is on the same filesystem as
    # projects/, a file by file copy when it is not.
    shutil.move(source, final)


def install_zip(response: http.client.HTTPResponse, domain: str) -> None:
    """Streams a zip download into place as the copy of a site."""
    # The zip and the copy unpacked out of it are both thrown away at the end, so
    # they are written wherever the system keeps temporary files and never inside
    # projects/. Both are as large as the site, so TMPDIR is worth pointing at a
    # roomier filesystem if the default one is small.
    with tempfile.TemporaryDirectory(prefix='scraping-tool-') as temporary:
        archive = Path(temporary) / 'download.zip'
        unpacked = Path(temporary) / 'unpacked'
        unpacked.mkdir()

        with response:
            stream_to_file(response, archive)

        print('Unpacking')
        # extractall keeps every member inside the destination, absolute paths
        # and .. in the zip included.
        try:
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(unpacked)
        except zipfile.BadZipFile:
            raise DownloadError(
                'What was downloaded is not a zip file, so there is nothing to '
                'unpack.\nCheck that the address still serves the copy.'
            )

        # The zip is of no use once it is unpacked, and deleting it here keeps the
        # disk from holding it and both copies of the site at the same time.
        archive.unlink()

        install_unpacked(unpacked, domain)

    print(f'Ready to scrape: {domain}')


def download_zip(url: str, domain: str) -> None:
    """Downloads and unpacks a plain zip file, the way the core copy arrives."""
    print(f'Downloading {url}')

    install_zip(open_url(url), domain)


def download_artifact(domain: str, repo: str, allow_failed: bool) -> None:
    """Downloads and unpacks the copy a github workflow made of a site."""
    token, _source = github_token()
    if not token:
        raise DownloadError(TOKEN_HELP)

    print(f"Looking for the latest '{ARTIFACT_NAME}' in {repo}")
    artifact, run = latest_artifact(repo, token, allow_failed)

    print(
        f'Found the copy from {artifact.get("created_at", "?")[:10]}, '
        f'run {run.get("run_number", "?")} '
        f'({run.get("head_sha", "")[:7]}, {run.get("conclusion")})'
    )
    print(f'  {run.get("html_url")}')

    install_zip(open_artifact(artifact['archive_download_url'], token), domain)


def prepare_projects_dir() -> None:
    """Makes sure the downloaded copy has somewhere to go."""
    # A download is the only thing that writes to projects/, so a fresh clone
    # gets the folder from here rather than from a placeholder kept in git.
    try:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise DownloadError(f'Cannot create {PROJECTS_DIR}: {error}')

    if not os.access(PROJECTS_DIR, os.W_OK):
        raise DownloadError(f'{PROJECTS_DIR} is not writable.')


def download_site(site: str, allow_failed: bool = False) -> None:
    """Downloads a listed site, from wherever its entry says it comes from."""
    # An unlisted site is reported before anything is written to projects/.
    entry = registry.site(site)

    prepare_projects_dir()

    if entry.repo:
        return download_artifact(entry.domain, entry.repo, allow_failed)

    if entry.url:
        return download_zip(entry.url, entry.domain)

    raise DownloadError(
        f'{entry.domain} has neither a repo nor a url in {REGISTRY_PATH.name}, '
        f'so there is nowhere to download it from.\nAdd one of them to its '
        f'entry.\n'
    )
