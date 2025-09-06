from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import communication


def generate_params(n_keys, n_nonces):
    # Generate ephemeral private and public keys
    print("Generating private and public keys...")
    ephemeral_priv = x25519.X25519PrivateKey.generate()
    ephemeral_pub = ephemeral_priv.public_key()

    # Generate symmetric keys
    print("Generating symmetric keys...")
    symm_keys = [AESGCM.generate_key(bit_length=256) for i in range(n_keys)]

    # Generate nonces
    print("Generating nonces...")
    nonces = [os.urandom(12) for i in range(n_nonces)]

    return ephemeral_priv, ephemeral_pub, symm_keys, nonces



def open_socket(user: bool, verifier_ip=None, verifier_port=None):
    if user and (verifier_ip is None or verifier_port is None):
        raise ValueError("Verifier IP or port is None: couldn't connect to verifier")

    if not user and (verifier_port is None):
        raise ValueError("Verifier port is None: couldn't open verifier socket")

    if user:
        return communication.UserSocket(verifier_ip, verifier_port)
    return communication.VerifierSocket(verifier_port)



