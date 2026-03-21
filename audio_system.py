import queue
import threading


class SoundManager:
    """
    Lightweight async sound wrapper.
    On Windows, uses winsound.Beep in a worker thread.
    On other platforms or failures, safely no-ops.
    """

    _PATTERNS = {
        "pop": [(820, 18)],
        "health": [(640, 24), (780, 28)],
        "combo_up": [(880, 24), (1080, 26), (1320, 34)],
        "mission": [(760, 20), (940, 22), (1160, 30)],
        "miss": [(360, 40)],
        "game_over": [(520, 55), (420, 70), (320, 90)],
        "new_best": [(980, 25), (1180, 28), (1380, 35)],
    }

    def __init__(self):
        self._q = queue.Queue(maxsize=128)
        self._enabled = False
        self._winsound = None
        try:
            import winsound  # type: ignore

            self._winsound = winsound
            self._enabled = True
        except Exception:
            self._enabled = False

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def play(self, name: str):
        if not self._enabled:
            return
        pattern = self._PATTERNS.get(name)
        if not pattern:
            return
        try:
            self._q.put_nowait(pattern)
        except queue.Full:
            pass

    def _run(self):
        while True:
            pattern = self._q.get()
            if not self._enabled or self._winsound is None:
                continue
            for freq, ms in pattern:
                try:
                    self._winsound.Beep(int(freq), int(ms))
                except Exception:
                    break
