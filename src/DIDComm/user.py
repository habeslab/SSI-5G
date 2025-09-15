import json
import argparse
import logging
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *

# Configurazione del logging
logging.basicConfig(
    filename='user.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def user(ECDH_privkey, sign_privkey, sign_pubkey, ECDH_verifier_pubkey,
         sign_verifier_pubkey, verifiable_cred, verifier_ip, verifier_port):
    logging.info("Generating X25519 keys, ED25519 keys, symmetric keys and nonces...")
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=4)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k0, k2, k4 = params["symm_keys"]
    th1, iv0, iv2, iv4 = params["nonces"]

    logging.info(f"Connecting to verifier at {verifier_ip}:{verifier_port}...")
    socket = open_socket(user=True, verifier_ip=verifier_ip, verifier_port=verifier_port)

    socket.send({})
    recvd = socket.recv()
    logging.info("Connected")
    logging.info("Received th0 = %s (base64)", recvd['th0'])
    th0 = from_B64_to_bytes(recvd['th0'])

    DIDDoc_signature = sign(from_pubkey_to_bytes(ephemeral_pub), sign_privkey)
    logging.info('DIDDoc successfully signed')
    m1 = {
        "th0": from_bytes_to_B64(th0),
        "th1": from_bytes_to_B64(th1),
        "DIDDoc": from_pubkey_to_B64(ephemeral_pub),
        "DIDDoc_signature": from_bytes_to_B64(DIDDoc_signature)
    }

    socket.send(prepare_msg(k0, ephemeral_priv, ECDH_verifier_pubkey, ephemeral_pub,
                            sign_verifier_pubkey, m1, iv0))
    logging.info("Sent m1")

    m2_encrypted = socket.recv()
    m2_plain = extract_msg(m2_encrypted, sign_pubkey, ephemeral_priv)
    logging.info("m2 received and decrypted successfully")

    th1_res = m2_plain["th1"]
    ECDH_verifier_pubkey = m2_plain["DIDDoc"]
    ECDH_verifier_pubkey_signature = m2_plain["DIDDoc_signature"]

    assert th1_res == from_bytes_to_B64(th1), "Nonce not valid. Protocol aborted"
    assert verify_signature(from_B64_to_bytes(ECDH_verifier_pubkey_signature),
                            from_B64_to_bytes(ECDH_verifier_pubkey),
                            sign_verifier_pubkey) is None, \
        "Signature not valid. Protocol aborted"
    logging.info("Nonce and signature successfully verified")

    m3 = {
        "uri": "URI"
    }

    socket.send(prepare_msg(k2, ephemeral_priv,
                            from_B64_to_x25519_pubkey(ECDH_verifier_pubkey),
                            ephemeral_pub, sign_verifier_pubkey, m3, iv2))
    logging.info("Sent m3")

    m4_encrypted = socket.recv()
    m4_plain = extract_msg(m4_encrypted, sign_pubkey, ephemeral_priv)
    logging.info("m4 received and decrypted successfully")

    uri_res = m4_plain["uri"]
    assert uri_res == m3["uri"], "URI not valid. Protocol aborted"

    verifiable_pres = {
        "m4": m4_plain,
        "verifiable_cred": verifiable_cred,
    }

    verifiable_pres_signature = sign(from_json_to_bytes(verifiable_pres), sign_privkey)

    m5 = {
        "verifiable_pres": verifiable_pres,
        "verifiable_pres_signature": from_bytes_to_B64(verifiable_pres_signature),
    }

    socket.send(prepare_msg(k4, ephemeral_priv,
                            from_B64_to_x25519_pubkey(ECDH_verifier_pubkey),
                            ephemeral_pub, sign_verifier_pubkey, m5, iv4))
    logging.info("Sent m5")

    m6_encrypted = socket.recv()
    m6_plain = extract_msg(m6_encrypted, sign_pubkey, ephemeral_priv)
    logging.info("m6 (resource) received and decrypted successfully")
    logging.info("m6 content: %s", m6_plain)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="User client for verifier connection")
    parser.add_argument("--verifier_ip", type=str, required=True,
                        help="IP address of the verifier")
    parser.add_argument("--verifier_port", type=int, required=True,
                        help="Port of the verifier")
    args = parser.parse_args()

    with open("./inputs/user_input.json", "r", encoding="utf-8") as file:
        user_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(user_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(user_input["sign_privkey"])
    sign_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_pubkey"])
    ECDH_verifier_pubkey = from_B64_to_x25519_pubkey(user_input["ECDH_verifier_pubkey"])
    sign_verifier_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_verifier_pubkey"])
    verifiable_cred = user_input["verifiable_cred"]

    user(ECDH_privkey, sign_privkey, sign_pubkey,
         ECDH_verifier_pubkey, sign_verifier_pubkey,
         verifiable_cred, args.verifier_ip, args.verifier_port)
