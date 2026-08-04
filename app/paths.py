# paths.py
#
# Where the tool keeps its files. Anything a user writes or downloads belongs in
# their own directories, so that an installed copy of the tool can be replaced
# without taking their crawl modules or their site copies with it.
#
# Every location falls back to the folder the code sits in when the user
# directory is not there, which is what a git checkout of this repository uses.
# For a copy installed with pipx that folder is inside the virtual environment,
# so the fallbacks are only reached there when the user has no home directory.

import os
from pathlib import Path
from typing import Optional

APP_NAME = 'scraping-tool'

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent


def user_dir(variable, default) -> Optional[Path]:
    """This tool's directory under $HOME, whether or not it is there.

    Follows the XDG base directory spec: the variable when it is set, otherwise
    a plain folder in the home directory, which is also what the spec falls back
    to and works the same on macOS.
    """
    base = os.environ.get(variable)

    if base:
        return Path(base).expanduser() / APP_NAME

    try:
        home = Path.home()
    except RuntimeError:
        # No $HOME and no passwd entry for this user, which is how the container
        # runs. There is no user directory to speak of, so everything falls back
        # to the program folder.
        return None

    return home / default / APP_NAME


CONFIG_DIR = user_dir('XDG_CONFIG_HOME', '.config')
DATA_DIR = user_dir('XDG_DATA_HOME', Path('.local') / 'share')


def in_config_dir(name, fallback) -> Path:
    """A file or folder in the config directory, or the one shipped with the code.

    The entry itself has to be there, rather than just the config directory, so
    that keeping one of them in the config directory does not hide the other.
    """
    if CONFIG_DIR is None:
        return fallback

    candidate = CONFIG_DIR / name

    return candidate if candidate.exists() else fallback
