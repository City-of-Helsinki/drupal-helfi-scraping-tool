"""
Where the tool keeps its files.
"""

import os
from pathlib import Path

APP_NAME = 'scraping-tool'

APP_DIR = Path(__file__).resolve().parent


def user_dir(variable, default) -> Path:
    """Get directories from XDG Base Directory spec.

    Defaults to directories relative to users home directory."""
    base = os.environ.get(variable) or Path.home() / default
    path = Path(base).expanduser() / APP_NAME

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    return path


CONFIG_DIR = user_dir('XDG_CONFIG_HOME', '.config')
DATA_DIR = user_dir('XDG_DATA_HOME', Path('.local') / 'share')
