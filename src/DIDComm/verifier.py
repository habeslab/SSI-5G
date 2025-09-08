from cryptography.hazmat.primitives.asymmetric import x25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *
import json
import jcs


def verifier(ECDH_privkey, sign_privkey, sign_pubkey, sign_user_pubkey, sign_issuer_pubkey):
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

    m1_encrypted = socket.recv()
    m1_plain = extract_msg(m1_encrypted, sign_pubkey, ECDH_privkey)
    print("m1 received and decrypted successfully")

    th0_res = m1_plain["th0"]
    th1 = m1_plain["th1"]
    ECDH_user_pubkey = m1_plain["DIDDoc"]
    ECDH_user_pubkey_signature = m1_plain["DIDDoc_signature"]

    assert th0_res == from_bytes_to_B64(th0), "Nonce not valid. Protocol aborted"
    assert verify_signature(from_B64_to_bytes(ECDH_user_pubkey_signature), from_B64_to_bytes(ECDH_user_pubkey), sign_user_pubkey) is None,\
        "Signature not valid. Protocol aborted"
    print("Nonce and signature successfully verified")

    DIDDoc_signature = sign(from_pubkey_to_bytes(ephemeral_pub), sign_privkey)

    m2 = {
        "th1": th1,
        "DIDDoc": from_pubkey_to_B64(ephemeral_pub),
        "DIDDoc_signature": from_bytes_to_B64(DIDDoc_signature)
    }

    socket.send(
        prepare_msg(k1, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey), ephemeral_pub, sign_user_pubkey,
                    m2, iv1))
    print("Sent m2")

    m3_encrypted = socket.recv()
    m3_plain = extract_msg(m3_encrypted, sign_pubkey, ephemeral_priv)
    print("m3 received and decrypted successfully")

    assert is_rule(m3_plain), "m3 has wrong format: protocol aborted"

    m4 = {
        "attr": ["name", "age"],
        "uri": "URI",
        "nc": from_bytes_to_B64(nc)
    }

    socket.send(
        prepare_msg(k3, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey), ephemeral_pub, sign_user_pubkey,
                    m4, iv3))
    print("Sent m4")

    m5_encrypted = socket.recv()
    m5_plain = extract_msg(m5_encrypted, sign_pubkey, ephemeral_priv)
    print("m5 received and decrypted successfully")

    verifiable_pres = m5_plain["verifiable_pres"]
    verifiable_pres_signature = m5_plain["verifiable_pres_signature"]
    assert verify_signature(from_B64_to_bytes(verifiable_pres_signature), from_json_to_bytes(verifiable_pres),
                            sign_user_pubkey) is None, "VP signature not valid. Protocol aborted"

    attr_res = verifiable_pres["verifiable_cred"]["attr"]
    issuer_sig = verifiable_pres["verifiable_cred"]["issuer_sig"]

    print("VC:")
    print(verifiable_pres["verifiable_cred"])

    assert verify_signature(from_B64_to_bytes(issuer_sig), from_bytes_to_B64(jcs.canonicalize(attr_res)).encode("UTF-8"),
                            sign_issuer_pubkey) is None, "VC signature not valid. Protocol aborted"

    nc_res = from_B64_to_bytes(m5_plain["verifiable_pres"]["nc"])
    assert nc_res == nc_res, "Nonce not valid. Protocol aborted"
    assert set(attr_res.keys()) == set(m4["attr"]), "VC attributes not valid. Protocol aborted"

    m6 = {
        "resource": "RESOURCE"
    }

    socket.send(
        prepare_msg(k5, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_user_pubkey), ephemeral_pub, sign_user_pubkey,
                    m6, k5))
    print("Sent m6")













if __name__ == '__main__':
    with open("./inputs/verifier_input.json", "r", encoding="utf-8") as file:
        verifier_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(verifier_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(verifier_input["sign_privkey"])
    sign_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_pubkey"])
    ECDH_user_pubkey = from_B64_to_x25519_pubkey(verifier_input["ECDH_user_pubkey"])
    sign_user_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_user_pubkey"])
    sign_issuer_pubkey = from_B64_to_ed25519_pubkey(verifier_input["sign_issuer_pubkey"])

    verifier(ECDH_privkey, sign_privkey, sign_pubkey, sign_user_pubkey, sign_issuer_pubkey)



