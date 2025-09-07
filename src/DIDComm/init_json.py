from utils import *
import json
import os


def main():
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
        "user_ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_ECDH_privkey)),
        "user_sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_sign_privkey)),
        "verifier_ECDH_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_ECDH_pubkey)),
        "verifier_sign_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_sign_pubkey)),
    }

    verifier_input = {
        "verifier_ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_ECDH_privkey)),
        "verifier_sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_sign_privkey)),
        "user_ECDH_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_ECDH_pubkey)),
        "user_sign_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_sign_pubkey)),
        "issuer_sign_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(issuer_sign_pubkey)),
    }

    os.makedirs("./inputs", exist_ok=True)
    with open("./inputs/user_input.json", "w", encoding="utf-8") as file:
        json.dump(user_input, file, ensure_ascii=False, indent=4)

    with open("./inputs/verifier_input.json", "w", encoding="utf-8") as file:
        json.dump(verifier_input, file, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()