from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from utils import *


# sign_privkey deve essere generata così:
# sk = Ed25519PrivateKey.generate()
# pk = sk.public_key()
def user(ECDH_privkey, sign_privkey, ECDH_verifier_pubkey, sign_verifier_pubkey, issuer_ECDH_pubkey):
    params = generate_params(n_x25519_keys=1, n_symm_keys=3, n_nonces=4)
    ephemeral_priv, ephemeral_pub = params["x25519_privkeys"][0], params["x25519_pubkeys"][0]
    k0, k2, k4 = params["symm_keys"]
    th1, iv0, iv2, iv4 = params["nonces"]

    socket = open_socket(user=True, verifier_ip="127.0.0.1", verifier_port=7000)

    socket.send({})
    recvd = socket.recv()
    print("Received th0 =", recvd['th0'], "(base64)")
    th0 = from_B64_to_bytes(recvd['th0'])

    # DIDDoc = sign(ephemeral_pub, sign_privkey)
    # print('DIDDoc successfully signed')
    # m1 = {
    #     th0: th0,
    #     th1: th1,
    #     DIDDoc: DIDDoc,
    # }
    #
    # k0_wrapped = wrap_key(k0, ephemeral_priv.exchange(ECDH_verifier_pubkey))
    # ephemeral_pub_wrapped = wrap_key(ephemeral_pub, sign_verifier_pubkey)
    # m1_ciphertext = encrypt(m1, iv0, k0)
    #
    # socket.send({
    #     "k0_wrapped": k0_wrapped,
    #     "ephemeral_pub_wrapped": ephemeral_pub_wrapped,
    #     "m1_ciphertext": m1_ciphertext,
    #     "iv0": iv0
    # })





if __name__ == '__main__':
    user(None, None, None, None, None)





