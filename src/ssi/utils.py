from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import json
import time
import psutil
import communication
import base64
import jwt



def generate_params(n_x25519_keys=0, n_ed25519_keys=0, n_symm_keys=0, n_nonces=0):
    x25519_privkeys, x25519_pubkeys = [], []
    ed25519_privkeys, ed25519_pubkeys = [], []

    for _ in range(n_x25519_keys):
        # Generate private and public X25519 keys
        x25519_priv = x25519.X25519PrivateKey.generate()
        x25519_pub = x25519_priv.public_key()
        x25519_privkeys.append(x25519_priv)
        x25519_pubkeys.append(x25519_pub)

    for _ in range(n_ed25519_keys):
        ed25519_priv = ed25519.Ed25519PrivateKey.generate()
        ed25519_pub = ed25519_priv.public_key()
        ed25519_privkeys.append(ed25519_priv)
        ed25519_pubkeys.append(ed25519_pub)

    # Generate symmetric keys
    symm_keys = [AESGCM.generate_key(bit_length=256) for i in range(n_symm_keys)]

    # Generate nonces
    nonces = [os.urandom(12) for i in range(n_nonces)]

    return {
        "x25519_privkeys": x25519_privkeys,
        "x25519_pubkeys": x25519_pubkeys,
        "ed25519_privkeys": ed25519_privkeys,
        "ed25519_pubkeys": ed25519_pubkeys,
        "symm_keys": symm_keys,
        "nonces": nonces
    }


def open_socket(user: bool, verifier_ip=None, verifier_port=None):
    if user and (verifier_ip is None or verifier_port is None):
        raise ValueError("Verifier IP or port is None: couldn't connect to verifier")

    if not user and (verifier_port is None):
        raise ValueError("Verifier port is None: couldn't open verifier socket")

    if user:
        return communication.UserSocket(verifier_ip, verifier_port)
    return communication.VerifierSocket(verifier_port)


def prepare_msg(k, epheremal_priv, ECDH_counterpart_pubkey, ephemeral_pub, sign_counterpart_pubkey, payload, iv):
    k_wrapped = wrap_key(k, epheremal_priv.exchange(ECDH_counterpart_pubkey))
    ephemeral_pub_wrapped = wrap_key(from_pubkey_to_bytes(ephemeral_pub), from_pubkey_to_bytes(sign_counterpart_pubkey))
    m_encrypted = encrypt(from_json_to_bytes(payload), iv, k)

    return {
        "k_wrapped": k_wrapped,
        "ephemeral_pub_wrapped": ephemeral_pub_wrapped,
        "m_encrypted": m_encrypted,
        "iv": from_bytes_to_B64(iv)
    }




def extract_msg(msg, sign_pubkey, ECDH_privkey):
    k_wrapped = msg["k_wrapped"]
    ephemeral_pub_wrapped = msg["ephemeral_pub_wrapped"]
    msg_encrypted = msg["m_encrypted"]
    iv = msg["iv"]

    # Unwrap ephemeral user public key
    ephemeral_pub = from_bytes_to_x25519_pubkey(unwrap_key(
        from_B64_to_bytes(ephemeral_pub_wrapped["nonce"]),
        from_B64_to_bytes(ephemeral_pub_wrapped["ciphertext"]),
        from_B64_to_bytes(ephemeral_pub_wrapped["tag"]),
        from_pubkey_to_bytes(sign_pubkey)
    ))

    # Unwrap k
    k = unwrap_key(
        from_B64_to_bytes(k_wrapped["nonce"]),
        from_B64_to_bytes(k_wrapped["ciphertext"]),
        from_B64_to_bytes(k_wrapped["tag"]),
        ECDH_privkey.exchange(ephemeral_pub)
    )

    # Get msg plaintext
    msg = decrypt(
        from_B64_to_bytes(msg_encrypted["ciphertext"]),
        k,
        from_B64_to_bytes(iv),
        from_B64_to_bytes(msg_encrypted["tag"])
    )

    return from_bytes_to_json(msg)


def wrap_key(k, k_wrap):
    backend = default_backend()

    # Derive key from k_wrap
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bit -> AES-256
        salt=None,
        info=b"key-wrapping",
        backend=backend
    )
    derived_key = hkdf.derive(k_wrap)

    # Encrypt k by AES-GCM
    nonce = os.urandom(12)
    cipher = Cipher(algorithms.AES(derived_key), modes.GCM(nonce), backend=backend)
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(k) + encryptor.finalize()

    return {
        "nonce": from_bytes_to_B64(nonce),
        "ciphertext": from_bytes_to_B64(ciphertext),
        "tag": from_bytes_to_B64(encryptor.tag)
    }


def unwrap_key(nonce, ciphertext, tag, k_wrap: bytes):
    backend = default_backend()

    # Get the derived key
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"key-wrapping",
        backend=backend
    )
    derived_key = hkdf.derive(k_wrap)

    # Decrypt ciphertext by AES-GCM
    cipher = Cipher(algorithms.AES(derived_key), modes.GCM(nonce, tag), backend=backend)
    decryptor = cipher.decryptor()
    k = decryptor.update(ciphertext) + decryptor.finalize()

    return k


def sign(msg, privkey):
    return privkey.sign(msg)


def verify_signature(sig, msg, pubkey):
    return pubkey.verify(sig, msg)


# Encrypt by AES-GCM
def encrypt(plaintext, iv, key):
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()

    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag

    return {
        "ciphertext": from_bytes_to_B64(ciphertext),
        "tag": from_bytes_to_B64(tag)
    }


# Decrypt by AES-GCM
def decrypt(ciphertext, key, iv, tag):
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=backend)
    decryptor = cipher.decryptor()

    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


def from_bytes_to_B64(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("Data must be of type bytes")
    return base64.b64encode(data).decode("utf-8")

def from_B64_to_bytes(data: str) -> bytes:
    if not isinstance(data, str):
        raise TypeError("Data must be of type str")
    return base64.b64decode(data)


def from_privkey_to_bytes(key):
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )


def from_pubkey_to_bytes(key):
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


def from_bytes_to_x25519_privkey(key_bytes):
    return x25519.X25519PrivateKey.from_private_bytes(key_bytes)


def from_bytes_to_x25519_pubkey(key_bytes):
    return x25519.X25519PublicKey.from_public_bytes(key_bytes)


def from_bytes_to_ed25519_privkey(key_bytes):
    return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)


def from_bytes_to_ed25519_pubkey(key_bytes):
    return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)


def from_B64_to_x25519_privkey(data):
    return from_bytes_to_x25519_privkey(from_B64_to_bytes(data))


def from_B64_to_ed25519_privkey(data):
    return from_bytes_to_ed25519_privkey(from_B64_to_bytes(data))


def from_B64_to_x25519_pubkey(data):
    return from_bytes_to_x25519_pubkey(from_B64_to_bytes(data))


def from_B64_to_ed25519_pubkey(data):
    return from_bytes_to_ed25519_pubkey(from_B64_to_bytes(data))


def from_json_to_bytes(data):
    data_str = json.dumps(data)
    return data_str.encode("utf-8")


def from_bytes_to_json(data):
    data_str = data.decode("utf-8")
    return json.loads(data_str)


def from_pubkey_to_B64(key):
    return from_bytes_to_B64(from_pubkey_to_bytes(key))


def from_B64_to_json(data):
    data_bytes = from_B64_to_bytes(data)
    data_str = data_bytes.decode('utf-8')
    return json.loads(data_str)


def from_json_to_B64(data):
    data_str = json.dumps(data)
    data_bytes = data_str.encode('utf-8')
    b64_bytes = base64.b64encode(data_bytes)
    return b64_bytes.decode('utf-8')


def get_hash(data: bytes):
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()


def emit_jwt_token(payload, key):
    return jwt.encode(payload, key, algorithm="EdDSA")


def decode_jwt_token(token, key):
    try:
        return jwt.decode(token, key, algorithms=["EdDSA"])
    except jwt.ExpiredSignatureError:
        print("Token expired")
        return None
    except jwt.InvalidTokenError:
        print("Token not valid")
        return None


def create_network_slice(plmn_id, max_ping, min_throughput_mbps, uptime_percentage, isolation_level):
    return {
        "plmnId": plmn_id,
        "maxPing": max_ping,
        "minThroughputMbps": min_throughput_mbps,
        "uptimePercentage": uptime_percentage,
        "isolationLevel": isolation_level
    }


def monitor_ram(pid, role: str):
    p = psutil.Process(pid)

    with open(f"./logs/ram_log_{role}.csv", "w") as f:
        f.write("time_sec,ram_MB\n")
        start = time.time()
        while p.is_running():
            try:
                rss = p.memory_info().rss / 1024 ** 2  # RAM in MB
                elapsed = time.time() - start
                f.write(f"{elapsed:.1f},{rss:.3f}\n")
                f.flush()
                time.sleep(1)
            except psutil.NoSuchProcess:
                break