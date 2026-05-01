# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# bus/can_bus.py — CAN Bus simulation (broadcast, prioritized)
# ============================================================

import threading
import queue
from config import LOG_PREFIX


class CANMessage:
    """
    Represents a single CAN bus message.

    Lower message ID = higher priority (standard CAN arbitration).
    Data is a dict payload (simulating encoded bytes).
    """

    def __init__(self, msg_id: int, data: dict):
        self.msg_id = msg_id
        self.data = data

    def __lt__(self, other: "CANMessage") -> bool:
        """Enable priority queue ordering by message ID."""
        return self.msg_id < other.msg_id

    def __repr__(self) -> str:
        return f"CANMessage(id=0x{self.msg_id:03X}, data={self.data})"


class CANBus:
    """
    Simulated CAN bus.

    - Broadcast: all subscribers receive every message.
    - Priority queue: lower CAN ID is delivered first.
    - Thread-safe: designed for concurrent ECU threads.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._priority_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._subscribers: list = []
        self._message_log: list = []
        self._running = True

    def send(self, msg_id: int, data: dict) -> None:
        """
        Put a CAN message onto the bus.
        Lower msg_id = higher priority.
        """
        message = CANMessage(msg_id, data)
        # PriorityQueue uses (priority, item) tuples
        self._priority_queue.put((msg_id, message))
        print(f"{LOG_PREFIX['CAN']} TX  id=0x{msg_id:03X}  data={data}")

    def receive(self) -> CANMessage | None:
        """
        Non-blocking receive of the highest-priority message.
        Returns None if the queue is empty.
        """
        try:
            _, message = self._priority_queue.get_nowait()
            self._message_log.append(message)
            return message
        except queue.Empty:
            return None

    def receive_all(self) -> list[CANMessage]:
        """
        Drain all currently queued messages in priority order.
        Returns a list of CANMessage objects.
        """
        messages = []
        while True:
            msg = self.receive()
            if msg is None:
                break
            messages.append(msg)
        return messages

    def flush(self) -> None:
        """Discard all pending messages (used on shutdown or reset)."""
        while not self._priority_queue.empty():
            try:
                self._priority_queue.get_nowait()
            except queue.Empty:
                break

    def get_message_log(self) -> list[CANMessage]:
        """Return a copy of all messages ever received."""
        return list(self._message_log)
