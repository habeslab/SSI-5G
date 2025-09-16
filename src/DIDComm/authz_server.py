from http.server import BaseHTTPRequestHandler, HTTPServer
from utils import *
import logging
import argparse

# Logging configuration
os.makedirs("./logs", exist_ok=True)
logging.basicConfig(
    filename='./logs/authz_server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)


class AAAHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            jwt_token = self.headers.get('X-Auth-Code')
            jwt_token_plain = decode_jwt_token(jwt_token, sign_verifier_pubkey)
            logging.info("Received JWT token:")
            logging.info(jwt_token_plain)

            if jwt_token_plain is not None:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'ACCESS GRANTED')
            else:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'UNAUTHORIZED')
        except Exception as e:
            self.send_response(500)
            self.wfile.write(str(e).encode("utf-8"))
            self.end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Authorization server for granting access to resources")
    parser.add_argument("--authz_server_ip", type=str, required=True,
                        help="IP address of the cloud Authorization Server")
    parser.add_argument("--authz_server_port", type=int, required=True,
                        help="Port of the cloud Authorization Server")
    parser.add_argument("--input_folder", type=str, required=True,
                        help="Path of the folder containing JSON input file")
    args = parser.parse_args()

    with open(f"{args.input_folder}/authz_server_input.json", "r", encoding="utf-8") as file:
        authz_server_input = json.load(file)

    sign_verifier_pubkey = from_B64_to_ed25519_pubkey(authz_server_input["sign_verifier_pubkey"])
    authz_server_ip = args.authz_server_ip
    authz_server_port = args.authz_server_port

    logging.info(f"Starting authorization server on http://{authz_server_ip}:{authz_server_port}")
    HTTPServer((authz_server_ip, authz_server_port), AAAHandler).serve_forever()