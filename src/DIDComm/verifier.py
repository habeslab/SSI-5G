from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import generate_params, open_socket


def verifier(did, privkey, ECDH_pubkey, sign_pubkey, issuer_sign_pubkey, issuer_ECDH_pubkey):
    params = generate_params(n_keys=3, n_nonces=5)
    ephemeral_priv, ephemeral_pub = params[0], params[1]
    k1, k3, k5 = params[2]
    th0, iv1, iv3, iv5, nc = params[3]

    socket = open_socket(user=False, verifier_port=7000)

    while(True):
        socket.recv()
        socket.send({})


if __name__ == '__main__':
    verifier(None, None, None, None, None, None)



