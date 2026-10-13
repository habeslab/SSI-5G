import zmq
import json
import threading
import queue


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

    def get_volume_kb(self) -> int:
        return (self.bytes_sent + self.bytes_recv) / 1024



class UserSocket(Socket):
    def __init__(self,  verifier_ip: str, verifier_port: int):
        # zmq.REQ order: .send(), .recv(), .send(), ...
        super().__init__(zmq.REQ)
        self.socket.connect(f"tcp://{verifier_ip}:{verifier_port}")


class VerifierSession:
    """
    Per-UE, socket-like view over a ConcurrentVerifierSocket: exposes the
    same send()/recv()/get_volume_kb() interface as Socket, so the
    verifier's per-connection protocol logic can run unmodified once per
    concurrently connected UE, oblivious to the fact that the underlying
    transport is a single shared ROUTER socket rather than one REP socket
    per UE.
    """
    def __init__(self, router: "ConcurrentVerifierSocket", identity: bytes):
        self._router = router
        self._identity = identity
        self._inbox = queue.Queue()
        self.bytes_sent = 0
        self.bytes_recv = 0

    def _deliver(self, data: bytes):
        self._inbox.put(data)

    def send(self, msg):
        data = json.dumps(msg).encode("utf-8")
        self._router._send(self._identity, data)
        self.bytes_sent += len(data)

    def recv(self):
        data = self._inbox.get()
        self.bytes_recv += len(data)
        return json.loads(data.decode("utf-8"))

    def get_volume_kb(self) -> int:
        return (self.bytes_sent + self.bytes_recv) / 1024

    def close(self):
        pass


class ConcurrentVerifierSocket:
    """
    ROUTER-based verifier endpoint able to serve multiple UE sessions
    concurrently on a single bound port (unlike the plain REP socket,
    which can only carry one stateful multi-message session at a time:
    interleaved messages from a second UE would otherwise corrupt the
    first UE's protocol state). REQ clients (UserSocket) require no
    change, since zmq.REQ already prefixes each outgoing message with
    the empty delimiter frame a ROUTER expects.

    A background thread demultiplexes incoming frames by ZMQ identity,
    creating one VerifierSession per newly-seen UE and queuing its
    messages there; accept() blocks until a new UE session appears.
    """
    def __init__(self, local_port: int):
        self._socket = zmq.Context().socket(zmq.ROUTER)
        self._socket.bind(f"tcp://*:{local_port}")
        self._send_lock = threading.Lock()
        self._sessions = {}
        self._new_sessions = queue.Queue()
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()

    def _dispatch_loop(self):
        while True:
            identity, _, payload = self._socket.recv_multipart()
            session = self._sessions.get(identity)
            if session is None:
                session = VerifierSession(self, identity)
                self._sessions[identity] = session
                self._new_sessions.put(session)
            session._deliver(payload)

    def _send(self, identity: bytes, data: bytes):
        with self._send_lock:
            self._socket.send_multipart([identity, b"", data])

    def accept(self) -> VerifierSession:
        return self._new_sessions.get()



