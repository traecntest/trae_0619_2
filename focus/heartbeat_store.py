import threading
import time
from collections import defaultdict


class InMemoryHeartbeatStore:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._data_lock = threading.Lock()
        self._heartbeats = defaultdict(list)
        self._session_snapshots = {}

    def record_heartbeat(self, session_id, payload=None):
        with self._data_lock:
            entry = {
                "ts_real": time.time(),
                "payload": payload or {},
            }
            self._heartbeats[session_id].append(entry)

    def get_heartbeats(self, session_id):
        with self._data_lock:
            return list(self._heartbeats.get(session_id, []))

    def set_session_snapshot(self, session_id, snapshot):
        with self._data_lock:
            self._session_snapshots[session_id] = snapshot

    def get_session_snapshot(self, session_id):
        with self._data_lock:
            return self._session_snapshots.get(session_id)

    def clear_session(self, session_id):
        with self._data_lock:
            self._heartbeats.pop(session_id, None)
            self._session_snapshots.pop(session_id, None)


heartbeat_store = InMemoryHeartbeatStore()
