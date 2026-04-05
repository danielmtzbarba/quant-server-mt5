from common_logging import setup_logging

logger = setup_logging("execution-service")


class MT5CommandQueue:
    _instance = None
    _queue = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MT5CommandQueue, cls).__new__(cls)
        return cls._instance

    def queue_command(self, action: str, **kwargs):
        command = {"action": action.upper()}
        command.update(kwargs)
        self._queue.append(command)
        logger.info(f"Queued MT5 command: {command}")

    def get_next(self):
        if not self._queue:
            return {"action": "NONE"}
        return self._queue.pop(0)

    def get_all_pending(self):
        return self._queue


# Singleton instance
mt5_queue = MT5CommandQueue()
