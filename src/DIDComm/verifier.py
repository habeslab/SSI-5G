from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *
import json


def verifier(ECDH_privkey, sign_privkey, ECDH_user_pubkey, sign_user_pubkey, sign_issuer_pubkey):
    print("Generating X25519 keys, ED25519 keys, symmetric keys and nonces...")
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=5)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k1, k3, k5 = params["symm_keys"]
    th0, iv1, iv3, iv5, nc = params["nonces"]

    print("Opening socket...")
    socket = open_socket(user=False, verifier_port=7000)

    socket.recv()
    print("Connection from user")

    th0_B64 = from_bytes_to_B64((th0))
    socket.send({"th0": th0_B64})
    print("Sent th0 =", th0_B64, "(base64)")

    m1 = socket.recv()
    print("Received m1:")
    print(m1)




if __name__ == '__main__':
    with open("./inputs/verifier_input.json", "r", encoding="utf-8") as file:
        verifier_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(verifier_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(verifier_input["sign_privkey"])
    ECDH_user_pubkey = from_B64_to_x25519_pubkey(verifier_input["ECDH_user_pubkey"])
    sign_user_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_user_pubkey"])
    sign_issuer_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_issuer_pubkey"])

    verifier(ECDH_privkey, sign_privkey, ECDH_user_pubkey, sign_user_pubkey, sign_issuer_pubkey)



