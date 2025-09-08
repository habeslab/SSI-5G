from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *
import json



def user(ECDH_privkey, sign_privkey, sign_pubkey, ECDH_verifier_pubkey, sign_verifier_pubkey, verifiable_cred):
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

    th1_res = m2_plain["th1"]
    ECDH_verifier_pubkey = m2_plain["DIDDoc"]
    ECDH_verifier_pubkey_signature = m2_plain["DIDDoc_signature"]

    assert th1_res == from_bytes_to_B64(th1), "Nonce not valid. Protocol aborted"
    assert verify_signature(from_B64_to_bytes(ECDH_verifier_pubkey_signature), from_B64_to_bytes(ECDH_verifier_pubkey),
                            sign_verifier_pubkey) is None, \
        "Signature not valid. Protocol aborted"
    print("Nonce and signature successfully verified")

    m3 = {
        "did_issuer": "DID_I",
        "did_verifier": "DID_V",
        "did_user": "DID_U",
        "uri": "URI"
    }

    socket.send(prepare_msg(k2, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_verifier_pubkey), ephemeral_pub, sign_verifier_pubkey, m3, iv2))
    print("Sent m3")

    m4_encrypted = socket.recv()
    m4_plain = extract_msg(m4_encrypted, sign_pubkey, ephemeral_priv)
    print("m4 received and decrypted successfully")

    attr = m4_plain["attr"]
    uri_res = m4_plain["uri"]
    nc = m4_plain["nc"]

    assert uri_res == m3["uri"], "URI not valid. Protocol aborted"

    verifiable_pres = {
        "nc": nc,
        "m4": m4_plain,
        "verifiable_cred": verifiable_cred,
    }

    verifiable_pres_signature = sign(from_json_to_bytes(verifiable_pres), sign_privkey)

    m5 = {
        "verifiable_pres": verifiable_pres,
        "verifiable_pres_signature": from_bytes_to_B64(verifiable_pres_signature),
    }

    socket.send(prepare_msg(k4, ephemeral_priv, from_B64_to_x25519_pubkey(ECDH_verifier_pubkey), ephemeral_pub,
                            sign_verifier_pubkey, m5, iv4))
    print("Sent m5")

    m6_encrypted = socket.recv()
    m6_plain = extract_msg(m6_encrypted, sign_pubkey, ephemeral_priv)
    print("m6 (resource) received and decrypted successfully")
    print(m6_plain)


if __name__ == '__main__':
    with open("./inputs/user_input.json", "r", encoding="utf-8") as file:
        user_input = json.load(file)

    ECDH_privkey = from_B64_to_x25519_privkey(user_input["ECDH_privkey"])
    sign_privkey = from_B64_to_ed25519_privkey(user_input["sign_privkey"])
    sign_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_pubkey"])
    ECDH_verifier_pubkey = from_B64_to_x25519_pubkey(user_input["ECDH_verifier_pubkey"])
    sign_verifier_pubkey = from_B64_to_ed25519_pubkey(user_input["sign_verifier_pubkey"])
    verifiable_cred = user_input["verifiable_cred"]

    user(ECDH_privkey, sign_privkey, sign_pubkey, ECDH_verifier_pubkey, sign_verifier_pubkey, verifiable_cred)





