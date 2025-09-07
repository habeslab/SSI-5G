from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *
import json





# sign_privkey deve essere generata così:
# sk = Ed25519PrivateKey.generate()
# pk = sk.public_key()
def user(ECDH_privkey, sign_privkey, sign_pubkey, ECDH_verifier_pubkey, sign_verifier_pubkey):
    print("Generating X25519 keys, ED25519 keys, symmetric keys and nonces...")
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=4)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k0, k2, k4 = params["symm_keys"]
    th1, iv0, iv2, iv4 = params["nonces"]

    print("Connecting to verifier...")
    socket = open_socket(user=True, verifier_ip="127.0.0.1", verifier_port=7000)

    socket.send({})
    recvd = socket.recv()
    print("Connected")
    print("Received th0 =", recvd['th0'], "(base64)")
    th0 = from_B64_to_bytes(recvd['th0'])

    DIDDoc_signature = sign(from_pubkey_to_bytes(ephemeral_pub), sign_privkey)
    print('DIDDoc successfully signed')
    m1 = {
        "th0": from_bytes_to_B64(th0),
        "th1": from_bytes_to_B64(th1),
        "DIDDoc": from_pubkey_to_B64(ephemeral_pub),
        "DIDDoc_signature": from_bytes_to_B64(DIDDoc_signature)
    }

    socket.send(prepare_msg(k0, ephemeral_priv, ECDH_verifier_pubkey, ephemeral_pub, sign_verifier_pubkey, m1, iv0))
    print("Sent m1")

    m2_encrypted = socket.recv()
    m2_plain = extract_msg(m2_encrypted, sign_pubkey, ephemeral_priv)
    print("m2 received and decrypted successfully")



if __name__ == '__main__':
    with open("./inputs/user_input.json", "r", encoding="utf-8") as file:
        user_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(user_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(user_input["sign_privkey"])
    sign_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_pubkey"])
    ECDH_verifier_pubkey = from_B64_to_x25519_pubkey(user_input["ECDH_verifier_pubkey"])
    sign_verifier_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_verifier_pubkey"])

    user(ECDH_privkey, sign_privkey, sign_pubkey, ECDH_verifier_pubkey, sign_verifier_pubkey)





