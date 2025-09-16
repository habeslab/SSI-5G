import json
import jcs
import argparse
import datetime
import logging
import sys
import requests
from http.server import BaseHTTPRequestHandler
from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *

# Configurazione del logging
os.makedirs("./logs", exist_ok=True)
logging.basicConfig(
    filename='./logs/verifier.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)


def contact_authz_server(jwt_token, authz_server_ip, authz_server_port):
    auth_server_url = f"http://{authz_server_ip}:{authz_server_port}"

    try:
        r = requests.get(auth_server_url, headers={'X-Auth-Code': jwt_token}, timeout=2)
        if r.status_code == 200:
            logging.info("Access granted (HTTP 200)")
        else:
            logging.info("Access denied (HTTP 403)")
    except Exception as e:
        logging.info("Authorization server unreachable (HTTP 500)")
        logging.info(e)


def verifier(ECDH_privkey, sign_privkey, sign_pubkey, sign_user_pubkey,
             sign_issuer_pubkey, verifier_port, authz_server_ip, authz_server_port):
    logging.info("Generating X25519 keys, ED25519 keys, symmetric keys and nonces...")
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=5)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k1, k3, k5 = params["symm_keys"]
    th0, iv1, iv3, iv5, nc = params["nonces"]

    logging.info(f"Opening socket on port {verifier_port}...")
    socket = open_socket(user=False, verifier_port=verifier_port)

    socket.recv()
    logging.info("Connection from user")

    th0_B64 = from_bytes_to_B64(th0)
    socket.send({"th0": th0_B64})
    logging.info("Sent th0 = %s (base64)", th0_B64)

    m1_encrypted = socket.recv()
    m1_plain = extract_msg(m1_encrypted, sign_pubkey, ECDH_privkey)
    logging.info("m1 received and decrypted successfully")

    th0_res = m1_plain["th0"]
    th1 = m1_plain["th1"]
    ECDH_user_pubkey = m1_plain["DIDDoc"]
    ECDH_user_pubkey_signature = m1_plain["DIDDoc_signature"]

    if th0_res != from_bytes_to_B64(th0):
        logging.info("Nonce not valid. Protocol aborted")
        sys.exit(1)

    if verify_signature(from_B64_to_bytes(ECDH_user_pubkey_signature),
                            from_B64_to_bytes(ECDH_user_pubkey),
                            sign_user_pubkey) is not None:
        logging.info("Signature not valid. Protocol aborted")
        sys.exit(1)

    logging.info("Nonce and signature successfully verified")

    DIDDoc_signature = sign(from_pubkey_to_bytes(ephemeral_pub), sign_privkey)

    m2 = {
        "th1": th1,
        "DIDDoc": from_pubkey_to_B64(ephemeral_pub),
        "DIDDoc_signature": from_bytes_to_B64(DIDDoc_signature)
    }

    socket.send(
        prepare_msg(k1, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m2, iv1))
    logging.info("Sent m2")

    m3_encrypted = socket.recv()
    m3_plain = extract_msg(m3_encrypted, sign_pubkey, ephemeral_priv)
    logging.info("m3 received and decrypted successfully")

    m4 = {
        "attr": ["plmnId", "siteId", "sliceId", "expirationDate"],
        "uri": m3_plain["uri"],
        "nc": from_bytes_to_B64(nc)
    }

    socket.send(
        prepare_msg(k3, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m4, iv3))
    logging.info("Sent m4")

    m5_encrypted = socket.recv()
    m5_plain = extract_msg(m5_encrypted, sign_pubkey, ephemeral_priv)
    logging.info("m5 received and decrypted successfully")

    verifiable_pres = m5_plain["verifiable_pres"]

    verifiable_pres_signature = m5_plain["verifiable_pres_signature"]
    if verify_signature(from_B64_to_bytes(verifiable_pres_signature),
                            from_json_to_bytes(verifiable_pres),
                            sign_user_pubkey) is not None:
        logging.info("VP signature not valid. Protocol aborted")
        sys.exit(1)

    verifiable_cred = verifiable_pres["verifiable_cred"]
    attr_res = verifiable_cred["attr"]
    issuer_sig = verifiable_cred["issuer_sig"]

    logging.info("VC: %s", verifiable_cred)

    if verify_signature(from_B64_to_bytes(issuer_sig),
                            from_bytes_to_B64(jcs.canonicalize(attr_res)).encode("UTF-8"),
                            sign_issuer_pubkey) is not None:
        logging.info("VC signature not valid. Protocol aborted")
        sys.exit(1)

    nc_res = from_B64_to_bytes(m5_plain["verifiable_pres"]["m4"]["nc"])

    if nc != nc_res:
        logging.info("Nonce not valid. Protocol aborted")
        sys.exit(1)

    if set(attr_res.keys()) != set(m4["attr"]):
        logging.info("VC attributes not valid. Protocol aborted")
        sys.exit(1)

    if (datetime.datetime.strptime(attr_res["expirationDate"], "%Y-%m-%d %H:%M:%S") <
            datetime.datetime.utcnow()):
        logging.info("VC expired. Protocol aborted")
        sys.exit(1)

    verifiable_pres_bytes = from_json_to_bytes(verifiable_pres)
    verifiable_pres_bytes_hash = get_hash(verifiable_pres_bytes)

    jwt_payload = {
        "verifiable_pres_hash": from_bytes_to_B64(verifiable_pres_bytes_hash),
        "siteId": attr_res["siteId"],
        "plmnId": attr_res["plmnId"],
        "sliceId": attr_res["sliceId"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }

    jwt_token = emit_jwt_token(jwt_payload, sign_privkey)

    m6 = {
        "jwt_token": jwt_token
    }

    socket.send(
        prepare_msg(k5, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m6, k5))
    logging.info("Sent m6 (JWT token)")

    logging.info(f"Contacting the Authorization Server at http://{authz_server_ip}:{authz_server_port}")
    contact_authz_server(jwt_token, authz_server_ip, authz_server_port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Verifier server for user connection")
    parser.add_argument("--verifier_port", type=int, required=True,
                        help="Port on which the verifier listens")
    parser.add_argument("--input_folder", type=str, required=True,
                        help="Path of the folder containing JSON input file")
    parser.add_argument("--authz_server_ip", type=str, required=True,
                        help="IP address of the cloud Authorization Server")
    parser.add_argument("--authz_server_port", type=str, required=True,
                        help="Port of the cloud Authorization Server")
    args = parser.parse_args()

    with open(f"{args.input_folder}/verifier_input.json", "r", encoding="utf-8") as file:
        verifier_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(verifier_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(verifier_input["sign_privkey"])
    sign_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_pubkey"])
    ECDH_user_pubkey = from_B64_to_x25519_pubkey(verifier_input["ECDH_user_pubkey"])
    sign_user_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_user_pubkey"])
    sign_issuer_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_issuer_pubkey"])

    verifier(ECDH_privkey, sign_privkey, sign_pubkey,
             sign_user_pubkey, sign_issuer_pubkey, args.verifier_port, args.authz_server_ip, args.authz_server_port)
