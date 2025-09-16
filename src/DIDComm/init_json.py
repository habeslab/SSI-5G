from utils import *
import json
import os


def create_network_resources():
    slice1 = create_network_slice(
        plmn_id="22250",
        max_ping=100,
        min_throughput_mbps=30,
        uptime_percentage=80,
        isolation_level=2
    )

    slice2 = create_network_slice(
        plmn_id="22248",
        max_ping=200,
        min_throughput_mbps=50,
        uptime_percentage=90,
        isolation_level=1
    )

    slice3 = create_network_slice(
        plmn_id="22208",
        max_ping=20,
        min_throughput_mbps=400,
        uptime_percentage=95,
        isolation_level=1
    )

    slice4 = create_network_slice(
        plmn_id="22210",
        max_ping=50,
        min_throughput_mbps=50,
        uptime_percentage=50,
        isolation_level=3
    )

    slice5 = create_network_slice(
        plmn_id="22250",
        max_ping=10,
        min_throughput_mbps=1000,
        uptime_percentage=98,
        isolation_level=3
    )

    slice6 = create_network_slice(
        plmn_id="22208",
        max_ping=70,
        min_throughput_mbps=30,
        uptime_percentage=60,
        isolation_level=3
    )

    slice7 = create_network_slice(
        plmn_id="22250",
        max_ping=120,
        min_throughput_mbps=50,
        uptime_percentage=50,
        isolation_level=2
    )

    slice8 = create_network_slice(
        plmn_id="22210",
        max_ping=30,
        min_throughput_mbps=500,
        uptime_percentage=80,
        isolation_level=2
    )

    slice9 = create_network_slice(
        plmn_id="22248",
        max_ping=100,
        min_throughput_mbps=100,
        uptime_percentage=70,
        isolation_level=3
    )

    return {
        1: {
            1: slice1,
            2: slice2,
            3: slice3,
            4: slice4
        },
        2: {
            1: slice5,
            2: slice6
        },
        3: {
            1: slice7,
            2: slice8,
            3: slice9
        }
    }


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

    # Load issuer output from json
    with open("../tss/issuer_output.json", "r", encoding="utf-8") as file:
        issuer_output = json.load(file)

    issuer_output["verifiable_cred"]["attr"] = from_B64_to_json(issuer_output["verifiable_cred"]["attr"])

    user_input = {
        "ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_ECDH_privkey)),
        "sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(user_sign_privkey)),
        "sign_pubkey": from_pubkey_to_B64(user_sign_pubkey),
        "ECDH_verifier_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_ECDH_pubkey)),
        "sign_verifier_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_sign_pubkey)),
        "verifiable_cred": issuer_output["verifiable_cred"]
    }

    verifier_input = {
        "ECDH_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_ECDH_privkey)),
        "sign_privkey": from_bytes_to_B64(from_privkey_to_bytes(verifier_sign_privkey)),
        "sign_pubkey": from_pubkey_to_B64(verifier_sign_pubkey),
        "ECDH_user_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_ECDH_pubkey)),
        "sign_user_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(user_sign_pubkey)),
        "sign_issuer_pubkey": issuer_output["sign_issuer_pubkey"],
    }

    authz_server_input = {
        "sign_verifier_pubkey": from_bytes_to_B64(from_pubkey_to_bytes(verifier_sign_pubkey)),
        "network_resources": create_network_resources()
    }

    os.makedirs("./inputs", exist_ok=True)

    print("User input saved in ./inputs/user_input.json")
    with open("./inputs/user_input.json", "w", encoding="utf-8") as file:
        json.dump(user_input, file, ensure_ascii=False, indent=4)

    print("Verifier input saved in ./inputs/verifier_input.json")
    with open("./inputs/verifier_input.json", "w", encoding="utf-8") as file:
        json.dump(verifier_input, file, ensure_ascii=False, indent=4)

    print("Authorization server input saved in ./inputs/authz_server_input.json")
    with open("./inputs/authz_server_input.json", "w", encoding="utf-8") as file:
        json.dump(authz_server_input, file, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()