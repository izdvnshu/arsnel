"""Watch a folder with watchdog and sort new files once they finish writing."""

from __future__ import annotations

import os
import queue
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from arsnel.organizer.categories import Classifier
from arsnel.organizer.sorter import SortResult, organize_file, should_skip


def wait_until_stable(
    path: Path,
    settle_seconds: float = 2.0,
    *,
    timeout: float = 300.0,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """True once the file's size and mtime stop changing and it can be opened."""
    deadline = time.monotonic() + timeout
    last: tuple[int, int] | None = None
    while time.monotonic() < deadline:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return False
        signature = (stat.st_size, stat.st_mtime_ns)
        if signature == last:
            try:
                with path.open("rb"):
                    return True
            except PermissionError:
                pass  # still locked by the writer (common on Windows)
            except OSError:
                return False
        last = signature
        sleep(settle_seconds)
    return False


def watch(
    root: Path,
    classifier: Classifier,
    *,
    ignore_extensions: Iterable[str] = (),
    settle_seconds: float = 2.0,
    on_result: Callable[[SortResult], None] | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """Block, sorting new files in `root` until `stop_event` is set or Ctrl+C."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    ignore = list(ignore_extensions)
    pending: queue.Queue[Path] = queue.Queue()

    class Handler(FileSystemEventHandler):
        def on_created(self, event):  # noqa: ANN001
            if not event.is_directory:
                pending.put(Path(os.fsdecode(event.src_path)))

        def on_moved(self, event):  # noqa: ANN001
            # Browsers finish downloads by renaming `x.crdownload` -> `x.pdf`.
            if not event.is_directory:
                pending.put(Path(os.fsdecode(event.dest_path)))

    observer = Observer()
    observer.schedule(Handler(), str(root), recursive=False)
    observer.start()
    stop = stop_event or threading.Event()
    try:
        while not stop.is_set():
            try:
                path = pending.get(timeout=0.5)
            except queue.Empty:
                continue
            if should_skip(path, ignore) or not wait_until_stable(path, settle_seconds):
                continue
            result = organize_file(path, root, classifier, ignore)
            if result is not None and on_result is not None:
                on_result(result)
    finally:
        observer.stop()
        observer.join()
