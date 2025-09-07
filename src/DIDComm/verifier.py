from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *


def verifier(ECDH_privkey, sign_privkey, ECDH_user_pubkey, sign_user_pubkey, issuer_ECDH_pubkey, issuer_sign_pubkey):
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=5)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k1, k3, k5 = params["symm_keys"]
    th0, iv1, iv3, iv5, nc = params["nonces"]

    socket = open_socket(user=False, verifier_port=7000)

    socket.recv()

    th0_B64 = from_bytes_to_B64((th0))
    socket.send({"th0": th0_B64})
    print("Sent th0 =", th0_B64, "(base64)")




if __name__ == '__main__':
    verifier(None, None, None, None, None, None)



