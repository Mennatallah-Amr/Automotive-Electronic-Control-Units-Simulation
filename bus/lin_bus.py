# ============================================================
# AZIZA - Distributed Automotive ECU Simulation
# bus/lin_bus.py — LIN Bus simulation (master-slave, non-critical)
# ============================================================

import threading
from config import LOG_PREFIX, LIN_MASTER_ID


class LINFrame:
    """
    Represents a LIN bus frame.

    frame_id: identifies which slave node is addressed.
    data: payload dict (e.g., lighting state, door status).
    is_response: True if this is a slave response frame.
    """

    def __init__(self, frame_id: str, data: dict, is_response: bool = False):
        self.frame_id = frame_id
        self.data = data
        self.is_response = is_response

    def __repr__(self) -> str:
        direction = "RSP" if self.is_response else "REQ"
        return f"LINFrame({direction}, id={self.frame_id}, data={self.data})"


class LINSlave:
    """
    A LIN bus slave node.

    Slaves register a handler function that processes requests
    and return a response payload dict.
    """

    def __init__(self, slave_id: str, handler):
        self.slave_id = slave_id
        self._handler = handler  # Callable[[dict], dict]

    def handle_request(self, request_data: dict) -> dict:
        return self._handler(request_data)


class LINBus:
    """
    Simulated LIN bus (master-slave topology).

    The master sends request frames to named slaves and receives
    synchronous response frames. Used for non-critical body
    functions (lighting, doors, HVAC).

    Only one master is allowed per LIN cluster (automotive spec).
    """

    def __init__(self, master_id: str = LIN_MASTER_ID):
        self.master_id = master_id
        self._slaves: dict[str, LINSlave] = {}
        self._lock = threading.Lock()
        self._transaction_log: list[dict] = []

    def register_slave(self, slave_id: str, handler) -> None:
        """
        Register a slave node with an ID and a request handler.
        handler: Callable[[dict], dict]
        """
        with self._lock:
            self._slaves[slave_id] = LINSlave(slave_id, handler)
            print(f"{LOG_PREFIX['LIN']} Slave registered: {slave_id}")

    def master_request(self, slave_id: str, request_data: dict) -> dict | None:
        """
        Master sends a request frame to a specific slave.
        Returns the slave's response dict, or None if slave not found.
        """
        request_frame = LINFrame(frame_id=slave_id, data=request_data, is_response=False)
        print(f"{LOG_PREFIX['LIN']} MASTER→{slave_id}  REQ={request_data}")

        with self._lock:
            slave = self._slaves.get(slave_id)

        if slave is None:
            print(f"{LOG_PREFIX['LIN']} ERROR: slave '{slave_id}' not registered.")
            return None

        response_data = slave.handle_request(request_data)
        response_frame = LINFrame(frame_id=slave_id, data=response_data, is_response=True)
        print(f"{LOG_PREFIX['LIN']} {slave_id}→MASTER  RSP={response_data}")

        self._transaction_log.append({
            "slave": slave_id,
            "request": request_data,
            "response": response_data,
        })

        return response_data

    def get_transaction_log(self) -> list[dict]:
        """Return full master-slave transaction history."""
        return list(self._transaction_log)
