import zmq


class Socket:
    def __init__(self, socket_type):
        # Usa un contesto globale per evitare warning in produzione
        self.socket = zmq.Context().socket(socket_type)
        self.bytes_sent = 0
        self.bytes_recv = 0

    def send(self, msg: bytes):
        if not isinstance(msg, bytes):
            raise TypeError("msg deve essere di tipo 'bytes'")
        self.socket.send(msg)
        self.bytes_sent += len(msg)

    def recv(self) -> bytes:
        data = self.socket.recv()
        self.bytes_recv += len(data)
        return data

    def send_wait(self, msg: bytes) -> bytes:
        self.send(msg)
        return self.recv()

    def close(self):
        self.socket.close()

    def get_volume(self) -> int:
        return self.bytes_sent + self.bytes_recv


class UserSocket(Socket):
    def __init__(self, local_port: int):
        # zmq.REP order: .recv(), .send(), .recv(), ...
        super().__init__(zmq.REP)
        self.socket.bind(f"tcp://*:{local_port}")


class VerifierSocket(Socket):
    def __init__(self, server_ip: str, server_port: int):
        # zmq.REQ order: .send(), .recv(), .send(), ...
        super().__init__(zmq.REQ)
        self.socket.connect(f"tcp://{server_ip}:{server_port}")
