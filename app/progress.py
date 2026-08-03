"""Single line progress reporting for interactive terminals."""

import logging
import shutil
import sys
import time

# How wide the [####....] part is, regardless of the terminal.
BAR_WIDTH = 20

# Below this there is no room left for anything useful, so the label is dropped.
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
    """Keeps the end of the text, which is the informative end of a url."""
    if len(text) <= width:
        return text

    return '…' + text[-(width - 1):]


class ClearBeforeLog(logging.Filter):
    """Takes the bar off the line before a log record is written over it."""

    def __init__(self, bar):
        super().__init__()
        self.bar = bar

    def filter(self, record):
        self.bar.clear()
        return True


class ProgressBar:
    """One line redrawn in place.

    Does nothing at all when the stream is not a terminal, so a run that is piped
    somewhere keeps whatever line based output the caller decided on instead.
    """

    def __init__(self, total, stream=None, prefix='', min_interval=0.1, enabled=True):
        self.stream = stream if stream is not None else sys.stdout
        # Without a total there is no way to say how far along this is, so the
        # bar and the percentage are left out and the fields carry the report.
        self.total = total
        self.prefix = prefix
        # A pipe or a file gets nothing, so the carriage returns never end up in
        self.enabled = enabled and self.stream.isatty()
        self.min_interval = min_interval
        self.last_draw = 0.0
        self.drawn = False

    def keep_clear_of_logging(self):
        """Stops log records from landing on top of the bar.

        The filter goes on the handlers rather than on a logger, because a logger
        only applies its own filters to the records it is called with, not to the
        ones that reach it from somewhere else.
        """
        if not self.enabled:
            return

        for handler in logging.getLogger().handlers:
            handler.addFilter(ClearBeforeLog(self))

    def update(self, done, fields=(), label=''):
        """Redraws the line, at most every min_interval seconds.

        The fields are already worded by the caller, because what is worth saying
        about a run of files is not what is worth saying about a download.
        """
        if not self.enabled:
            return

        # The last update is always drawn, so the finished state is the one left
        # on screen rather than whatever the throttle happened to allow.
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

        # One column short of the width, so the terminal does not wrap the line
        # onto the next one and leave the previous state behind.
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
        """Takes the bar off the line, so something else can have it.

        Does nothing when there is no bar on the line, so whatever is written next
        is not at risk of having its own line wiped.
        """
        if not self.drawn:
            return

        self.drawn = False
        self.stream.write("\r\x1b[K")
        self.stream.flush()
