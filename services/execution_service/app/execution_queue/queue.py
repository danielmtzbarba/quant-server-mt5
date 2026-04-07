from common_logging import setup_logging

logger = setup_logging("execution-service")


class MT5CommandQueue:
    _instance = None
    _queue = {}  # Dict of login -> list of commands

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MT5CommandQueue, cls).__new__(cls)
        return cls._instance

    def queue_command(self, login: str, action: str, **kwargs):
        if login not in self._queue:
            self._queue[login] = []

        command = {"action": action.upper()}
        command.update(kwargs)
        self._queue[login].append(command)
        logger.info(f"Queued MT5 command for {login}: {command}")

    def get_next(self, login: str):
        if login not in self._queue or not self._queue[login]:
            return {"action": "NONE"}
        return self._queue[login].pop(0)

    def get_all_pending(self, login: str = None):
        if login:
            return self._queue.get(login, [])
        return self._queue


# Singleton instance
mt5_queue = MT5CommandQueue()
