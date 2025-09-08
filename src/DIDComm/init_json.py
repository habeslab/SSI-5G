from utils import *
import json
import os


def main():
    print("Generating user and verifier inputs...")

    # Generate user and verifier private and public keys for ECDH (X25519)
    keys = generate_params(n_x25519_keys=2)
    user_ECDH_privkey, user_ECDH_pubkey = keys["x25519_privkeys"][0], keys["x25519_pubkeys"][0]
    verifier_ECDH_privkey, verifier_ECDH_pubkey = keys["x25519_privkeys"][1], keys["x25519_pubkeys"][1]

    # Generate user, verifier and issuer private and public keys for signing (ED25519)
    keys = generate_params(n_ed25519_keys=3)
    user_sign_privkey, user_sign_pubkey = keys["ed25519_privkeys"][0], keys["ed25519_pubkeys"][0]
    verifier_sign_privkey, verifier_sign_pubkey = keys["ed25519_privkeys"][1], keys["ed25519_pubkeys"][1]
    issuer_sign_privkey, issuer_sign_pubkey = keys["ed25519_privkeys"][2], keys["ed25519_pubkeys"][2]


    user_input = {
        "ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_ECDH_privkey)),
        "sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_sign_privkey)),
        "sign_pubkey": from_pubkey_to_B64(user_sign_pubkey),
        "ECDH_verifier_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_ECDH_pubkey)),
        "sign_verifier_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_sign_pubkey)),
    }

    verifier_input = {
        "ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_ECDH_privkey)),
        "sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_sign_privkey)),
        "sign_pubkey": from_pubkey_to_B64(verifier_sign_pubkey),
        "ECDH_user_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_ECDH_pubkey)),
        "sign_user_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_sign_pubkey)),
        "sign_issuer_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(issuer_sign_pubkey)),
    }

    os.makedirs("./inputs", exist_ok=True)

    print("User input saved in ./inputs/user_input.json")
    with open("./inputs/user_input.json", "w", encoding="utf-8") as file:
        json.dump(user_input, file, ensure_ascii=False, indent=4)

    print("Verifier input saved in ./inputs/verifier_input.json")
    with open("./inputs/verifier_input.json", "w", encoding="utf-8") as file:
        json.dump(verifier_input, file, ensure_ascii=False, indent=4)

    attr = {
        "name": "francesco",
        "age": 23,
    }
    issuer_sig = sign(from_json_to_bytes(attr), issuer_sign_privkey)
    verifiable_cred = {
        "attr": attr,
        "issuer_sig": from_bytes_to_B64(issuer_sig)
    }

    print("Verifiable credentials saved in ./inputs/verifiable_cred.json")
    with open("./inputs/verifiable_cred.json", "w", encoding="utf-8") as file:
        json.dump(verifiable_cred, file, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()