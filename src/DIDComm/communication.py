import zmq
import json
import base64


class Socket:
    def __init__(self, socket_type):
        # Usa un contesto globale per evitare warning in produzione
        self.socket = zmq.Context().socket(socket_type)
        self.bytes_sent = 0
        self.bytes_recv = 0

    def send(self, msg):
        data = json.dumps(msg).encode("utf-8")
        self.socket.send(data)
        self.bytes_sent += len(data)

    def recv(self):
        data = self.socket.recv()
        self.bytes_recv += len(data)
        return json.loads(data.decode("utf-8"))

    def send_wait(self, msg: bytes) -> bytes:
        self.send(msg)
        return self.recv()

    def close(self):
        self.socket.close()

    def get_volume(self) -> int:
        return self.bytes_sent + self.bytes_recv


class VerifierSocket(Socket):
    def __init__(self, local_port: int):
        # zmq.REP order: .recv(), .send(), .recv(), ...
        super().__init__(zmq.REP)
        self.socket.bind(f"tcp://*:{local_port}")


class UserSocket(Socket):
    def __init__(self,  verifier_ip: str, verifier_port: int):
        # zmq.REQ order: .send(), .recv(), .send(), ...
        super().__init__(zmq.REQ)
        self.socket.connect(f"tcp://{verifier_ip}:{verifier_port}")


def from_bytes_to_B64(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("Data must be of type bytes")
    return base64.b64encode(data).decode("utf-8")

def from_B64_to_bytes(data: str) -> bytes:
    if not isinstance(data, str):
        raise TypeError("Data must be of type str")
    return base64.b64decode(data)
