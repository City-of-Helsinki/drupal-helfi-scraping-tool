"""Progress reporting for interactive terminals."""

import logging
import shutil
import sys
import time

# How wide the [####....] part is, regardless of the terminal.
BAR_WIDTH = 20

MIN_LABEL_WIDTH = 12


def human_readable_time(seconds):
    """Converts time in seconds to a human-readable string."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{int(hours)}h, {int(minutes)}m, {int(seconds)}s"
    elif minutes:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"


def shorten(text, width):
    """Keeps the end of the text (more useful for urls)."""
    if len(text) <= width:
        return text

    return '…' + text[-(width - 1):]


class ClearBeforeLog(logging.Filter):
    """Clears the progressbar before a log record is written over it."""

    def __init__(self, bar):
        super().__init__()
        self.bar = bar

    def filter(self, record):
        self.bar.clear()
        return True


class ProgressBar:

    def __init__(self, total, stream=None, prefix='', min_interval=0.1, enabled=True):
        self.stream = stream if stream is not None else sys.stdout
        # Without a total there is no way to say how far along this is.
        self.total = total
        self.prefix = prefix
        # Hide progressbar on pipes or a file outputs.
        self.enabled = enabled and self.stream.isatty()
        self.min_interval = min_interval
        self.last_draw = 0.0
        self.drawn = False

    def keep_clear_of_logging(self):
        """Stops log records from landing on top of the progressbar."""
        if not self.enabled:
            return

        for handler in logging.getLogger().handlers:
            handler.addFilter(ClearBeforeLog(self))

    def update(self, done, fields=(), label=''):
        """Redraws the line, at most every min_interval seconds."""
        if not self.enabled:
            return

        # The last update is always drawn, so the finished state is the one left
        # on screen.
        finished = bool(self.total) and done >= self.total
        now = time.monotonic()
        if not finished and now - self.last_draw < self.min_interval:
            return

        self.last_draw = now

        parts = []
        if self.total:
            filled = int(BAR_WIDTH * min(done, self.total) / self.total)
            parts.append(
                f"[{'#' * filled}{'.' * (BAR_WIDTH - filled)}] "
                f"{done / self.total * 100:5.1f}%"
            )
        parts.extend(fields)
        stats = ' · '.join(parts)

        width = shutil.get_terminal_size().columns - 1 - len(self.prefix)
        line = stats[:width]

        room = width - len(stats) - 3  # the ' · ' the label would be joined with
        if label and room >= MIN_LABEL_WIDTH:
            line = f"{stats} · {shorten(label, room)}"

        # \x1b[K wipes whatever the previous, possibly longer, line left there.
        self.stream.write(f"\r{self.prefix}{line}\x1b[K")
        self.stream.flush()
        self.drawn = True

    def clear(self):
        """Takes the progressbar off the line, so something else can have it."""
        if not self.drawn:
            return

        self.drawn = False
        self.stream.write("\r\x1b[K")
        self.stream.flush()
