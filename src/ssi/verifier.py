import json
import jcs
import argparse
import datetime
import logging
import ssl
import time
import requests
import threading
import multiprocessing
import psutil
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
    auth_server_url = f"https://{authz_server_ip}:{authz_server_port}"

    # Begin time measurement
    start = time.perf_counter()

    try:
        r = requests.get(
            auth_server_url,
            headers={'X-Auth-Code': jwt_token},
            timeout=2,
            cert=(f"{args.input_folder}/certs/client.crt", f"{args.input_folder}/certs/client.key"),
            verify=f"{args.input_folder}/certs/ca.crt"
        )
        if r.status_code == 200:
            logging.info("Access granted (HTTP 200)")
        else:
            logging.info("Access denied (HTTP 403)")
    except Exception as e:
        logging.info("Authorization server unreachable (HTTP 500)")
        logging.info(e)
    finally:
        # End time measurement
        end = time.perf_counter()
        elapsed = end - start
        logging.info(f"Elapsed time for authorization: {elapsed}")


def handle_ue(socket, ECDH_privkey, sign_privkey, sign_pubkey, sign_user_pubkey,
              sign_issuer_pubkey, authz_server_ip, authz_server_port, session_id):
    """
    Runs one UE's authentication+authorization exchange to completion.
    Called in its own thread per accepted session by the server loop
    below, so that the verifier can serve multiple UEs concurrently: a
    protocol failure here must only abort THIS session (hence `return`
    instead of `sys.exit`, which would otherwise kill every other UE
    session sharing the same verifier process).
    """
    def info(msg, *fmt_args):
        logging.info(f"[UE session {session_id}] " + msg, *fmt_args)

    socket.recv()
    info("Connection from user")

    # Begin time measurement
    start = time.perf_counter()

    info("Generating X25519 keys, ED25519 keys, symmetric keys and nonces...")
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=5)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k1, k3, k5 = params["symm_keys"]
    th0, iv1, iv3, iv5, nc = params["nonces"]

    th0_B64 = from_bytes_to_B64(th0)
    socket.send({"th0": th0_B64})
    info("Sent th0 = %s (base64)", th0_B64)

    m1_encrypted = socket.recv()
    m1_plain = extract_msg(m1_encrypted, sign_pubkey, ECDH_privkey)
    info("m1 received and decrypted successfully")

    th0_res = m1_plain["th0"]
    th1 = m1_plain["th1"]
    ECDH_user_pubkey = m1_plain["DIDDoc"]
    ECDH_user_pubkey_signature = m1_plain["DIDDoc_signature"]

    if th0_res != from_bytes_to_B64(th0):
        info("Nonce not valid. Protocol aborted")
        return

    if verify_signature(from_B64_to_bytes(ECDH_user_pubkey_signature),
                            from_B64_to_bytes(ECDH_user_pubkey),
                            sign_user_pubkey) is not None:
        info("Signature not valid. Protocol aborted")
        return

    info("Nonce and signature successfully verified")

    DIDDoc_signature = sign(from_pubkey_to_bytes(ephemeral_pub), sign_privkey)

    m2 = {
        "th1": th1,
        "DIDDoc": from_pubkey_to_B64(ephemeral_pub),
        "DIDDoc_signature": from_bytes_to_B64(DIDDoc_signature)
    }

    socket.send(
        prepare_msg(k1, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m2, iv1))
    info("Sent m2")

    m3_encrypted = socket.recv()
    m3_plain = extract_msg(m3_encrypted, sign_pubkey, ephemeral_priv)
    info("m3 received and decrypted successfully")

    m4 = {
        "attr": ["plmnId", "maxPing", "minThroughputMbps", "uptimePercentage", "isolationLevel", "expirationDate"],
        "uri": m3_plain["uri"],
        "nc": from_bytes_to_B64(nc)
    }

    socket.send(
        prepare_msg(k3, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m4, iv3))
    info("Sent m4")

    m5_encrypted = socket.recv()
    m5_plain = extract_msg(m5_encrypted, sign_pubkey, ephemeral_priv)
    info("m5 received and decrypted successfully")

    verifiable_pres = m5_plain["verifiable_pres"]

    verifiable_pres_signature = m5_plain["verifiable_pres_signature"]
    if verify_signature(from_B64_to_bytes(verifiable_pres_signature),
                            from_json_to_bytes(verifiable_pres),
                            sign_user_pubkey) is not None:
        info("VP signature not valid. Protocol aborted")
        return

    verifiable_cred = verifiable_pres["verifiable_cred"]
    attr_res = verifiable_cred["attr"]
    issuer_sig = verifiable_cred["issuer_sig"]

    info("VC: %s", verifiable_cred)

    if verify_signature(from_B64_to_bytes(issuer_sig),
                            from_bytes_to_B64(jcs.canonicalize(attr_res)).encode("UTF-8"),
                            sign_issuer_pubkey) is not None:
        info("VC signature not valid. Protocol aborted")
        return

    nc_res = from_B64_to_bytes(m5_plain["verifiable_pres"]["m4"]["nc"])

    if nc != nc_res:
        info("Nonce not valid. Protocol aborted")
        return

    if set(attr_res.keys()) != set(m4["attr"]):
        info("VC attributes not valid. Protocol aborted")
        return

    if (datetime.datetime.strptime(attr_res["expirationDate"], "%Y-%m-%d %H:%M:%S") <
            datetime.datetime.utcnow()):
        info("VC expired. Protocol aborted")
        return

    verifiable_pres_bytes = from_json_to_bytes(verifiable_pres)
    verifiable_pres_bytes_hash = get_hash(verifiable_pres_bytes)

    jwt_payload = {
        "verifiable_pres_hash": from_bytes_to_B64(verifiable_pres_bytes_hash),
        "plmnId": attr_res["plmnId"],
        "maxPing": attr_res["maxPing"],
        "minThroughputMbps": attr_res["minThroughputMbps"],
        "uptimePercentage": attr_res["uptimePercentage"],
        "isolationLevel": attr_res["isolationLevel"],
        "siteId": m3_plain["uri"]["siteId"],
        "sliceId": m3_plain["uri"]["sliceId"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }

    jwt_token = emit_jwt_token(jwt_payload, sign_privkey)

    m6 = {
        "jwt_token": jwt_token
    }

    socket.send(
        prepare_msg(k5, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey),
                    ephemeral_pub, sign_user_pubkey, m6, k5))
    info("Sent m6 (JWT token)")

    # End time measurement
    end = time.perf_counter()
    elapsed = end - start
    info(f"Elapsed time for SSI: {elapsed}. . Communication volume: {socket.get_volume_kb()} KBs")

    info(f"Contacting the Authorization Server at https://{authz_server_ip}:{authz_server_port}")
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

    logging.info(f"Opening concurrent verifier socket on port {args.verifier_port}...")
    router = open_socket(user=False, verifier_port=args.verifier_port)

    # One process-wide RAM monitor: since all UE sessions are threads
    # inside this single process, a per-session monitor would just poll
    # the same PID redundantly under concurrent load.
    monitor_proc = multiprocessing.Process(target=monitor_ram, args=(os.getpid(), "verifier"), daemon=True)
    monitor_proc.start()

    session_id = 0
    while True:
        session = router.accept()
        session_id += 1
        threading.Thread(
            target=handle_ue,
            args=(session, ECDH_privkey, sign_privkey, sign_pubkey, sign_user_pubkey,
                  sign_issuer_pubkey, args.authz_server_ip, args.authz_server_port, session_id),
            daemon=True,
        ).start()
