from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import generate_params, open_socket


def user(did, privkey, ECDH_pubkey, sign_pubkey, issuer_sign_pubkey, issuer_ECDH_pubkey):
    params = generate_params(n_keys=3, n_nonces=4)
    ephemeral_priv, ephemeral_pub = params[0], params[1]
    k0, k2, k4 = params[2]
    th1, iv0, iv2, iv4 = params[3]

    socket = open_socket(user=true, user_port=7000)





