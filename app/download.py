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

from progress import ProgressBar, human_readable_time
from sites import ARTIFACT_NAME, PROJECTS_DIR, REGISTRY_PATH, registry

GITHUB_API = 'https://api.github.com'
USER_AGENT = 'drupal-helfi-scraping-tool'
TOKEN_VARIABLES = ('GITHUB_TOKEN', 'GH_TOKEN')

TOKEN_HELP = (
    'A github token is needed to download an artifact, even from a public repository.\n'
    'Create one at https://github.com/settings/tokens and set it in the environment\n'
    'as GITHUB_TOKEN\n'
    '\n'
    "A classic token needs the 'public_repo' scope. A fine grained token needs\n"
    'read access to Actions on the repository.'
)


class DownloadError(Exception):
    """Raised when a copy of a site cannot be fetched or unpacked."""


def github_token() -> Optional[str]:
    """The token to talk to github with."""
    for name in TOKEN_VARIABLES:
        value = (os.environ.get(name) or '').strip()
        if value:
            return value

    return None


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
        detail = 'The token was rejected. Check the token in the environment.'
    elif error.code == 403:
        if error.headers.get('x-ratelimit-remaining') == '0':
            detail = 'Rate limited by github. Try again in a while.'
        else:
            detail = (
                'Access denied.'
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


class DropToken(urllib.request.HTTPRedirectHandler):
    """Leaves the github token behind when a redirect leads off github."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)

        # urllib copies every header onto the redirected request. The artifact
        # redirect points at storage with the credentials already in the url.
        if redirected is not None:
            redirected.headers.pop('Authorization', None)

        return redirected


def megabytes(count: int) -> str:
    size = count / 1024 / 1024
    return f'{size:.1f} MB' if size < 10 else f'{size:.0f} MB'


def download_fields(copied: int, total: int, elapsed: float) -> list[str]:
    """How a download in progress is worded, in the order it is read."""
    fields = [f'{megabytes(copied)} of {megabytes(total)}' if total else megabytes(copied)]

    # A rate needs some time to have passed to mean anything, and without one
    # there is nothing to work a remaining time out of either.
    rate = copied / elapsed if elapsed > 0.5 else 0
    if rate:
        fields.append(f'{megabytes(rate)}/s')

    if rate and total > copied:
        fields.append(f'{human_readable_time((total - copied) / rate)} left')

    return fields


def stream_to_file(response: http.client.HTTPResponse, destination: Path) -> None:
    """Copies the response into a file, reporting how it is going."""
    total = int(response.headers.get('Content-Length') or 0)
    copied = 0
    started = time.monotonic()
    # A server that does not say how large the file is leaves the bar out, so the
    # report is then the bytes as they arrive.
    progress = ProgressBar(total, prefix='  ')

    with open(destination, 'wb') as target:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break

            target.write(chunk)
            copied += len(chunk)

            progress.update(
                copied, download_fields(copied, total, time.monotonic() - started)
            )

    progress.clear()
    print(f'  {megabytes(copied)} downloaded.')


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
        + ('\nPass --allow-failed to take the copy from a failed run.' if unsuccessful else '')
    )


def install_unpacked(unpacked: Path, domain: str) -> None:
    """Puts an unpacked download in place as projects/<domain>."""
    if not (unpacked / domain).is_dir():
        contents = ', '.join(child.name for child in sorted(unpacked.iterdir()))
        raise DownloadError(
            f'The zip has no {domain} folder in it, so it is not a copy of that '
            f'site.\nIt contains: {contents or "(nothing)"}'
        )

    # A kopio zip contains other hosts in addition to www.hel.fi.
    # Unpack the kopio archive to a subdirectory.
    source = unpacked if registry.site(domain).layout == 'kopio' else unpacked / domain
    final = PROJECTS_DIR / domain

    print(f'Moving the copy into {PROJECTS_DIR}')

    # Remove the previous copy rather than write over it.
    if final.exists():
        shutil.rmtree(final)

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

        try:
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(unpacked)
        except zipfile.BadZipFile:
            raise DownloadError(
                'What was downloaded is not a zip file, so there is nothing to '
                'unpack.\nCheck that the address still serves the copy.'
            )

        # Remove the zip.
        archive.unlink()

        install_unpacked(unpacked, domain)

    print(f'Ready to scrape: {domain}')


def download_zip(url: str, domain: str) -> None:
    """Downloads and unpacks a plain zip file, the way the core copy arrives."""
    print(f'Downloading {url}')

    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': USER_AGENT})) as response:
            install_zip(response, domain)
    except urllib.error.HTTPError as error:
        raise DownloadError(f'{url}\n  the server said {error.code}: {error.reason}')
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach {url}: {error.reason}')


def download_artifact(domain: str, repo: str, allow_failed: bool) -> None:
    """Downloads and unpacks the copy a github workflow made of a site."""
    token = github_token()
    if not token:
        raise DownloadError(TOKEN_HELP)

    print(f"Looking for the latest '{ARTIFACT_NAME}' in {repo}")
    artifact, run = latest_artifact(repo, token, allow_failed)

    print(
        f'Found the copy from {artifact.get("created_at", "?")[:10]}, '
        f'run {run.get("run_number", "?")} '
        f'({run.get("conclusion")})'
    )
    print(f'  {run.get("html_url")}')

    opener = urllib.request.build_opener(DropToken)

    try:
        with opener.open(github_request(url, token)) as response:
            install_zip(response, domain)
    except urllib.error.HTTPError as error:
        raise github_error(error, url)
    except urllib.error.URLError as error:
        raise DownloadError(f'Could not reach {url}: {error.reason}')


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
