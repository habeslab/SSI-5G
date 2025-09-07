from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os
import communication
import base64



def generate_params(n_x25519_keys=0, n_ed25519_keys=0, n_symm_keys=0, n_nonces=0):
    x25519_privkeys, x25519_pubkeys = [], []
    ed25519_privkeys, ed25519_pubkeys = [], []

    for _ in range(n_x25519_keys):
        # Generate private and public X25519 keys
        print("Generating private and public X25519 keys...")
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
    print("Generating symmetric keys...")
    symm_keys = [AESGCM.generate_key(bit_length=256) for i in range(n_symm_keys)]

    # Generate nonces
    print("Generating nonces...")
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

    return nonce, ciphertext, encryptor.tag


def unwrap_key(nonce, ciphertext, tag, k_wrap):
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
    signature = privkey.sign(msg)
    return signature


# Encrypt by AES-GCM
def encrypt(plaintext, iv, key):
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=backend)
    encryptor = cipher.encryptor()

    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    tag = encryptor.tag

    return ciphertext, tag


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


