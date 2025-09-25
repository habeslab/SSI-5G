from http.server import BaseHTTPRequestHandler, HTTPServer
from utils import *
import logging
import ssl
import argparse

# Logging configuration
os.makedirs("./logs", exist_ok=True)
logging.basicConfig(
    filename='./logs/authz_server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)


def is_allowed(jwt_token):
    site_id = jwt_token["siteId"]
    slice_id = jwt_token["sliceId"]
    plmn_id = jwt_token["plmnId"]
    max_ping = int(jwt_token["maxPing"])
    min_throughput_mbps = int(jwt_token["minThroughputMbps"])
    uptime_percentage = int(jwt_token["uptimePercentage"])
    isolation_level = int(jwt_token["isolationLevel"])

    if site_id not in network_resources:
        logging.info(f"Site ID {site_id} is not valid")
        return False
    logging.info(f"Site ID {site_id} is valid")

    if slice_id not in network_resources[site_id]:
        logging.info(f"Slice ID {slice_id} is not valid")
        return False
    logging.info(f"Slice ID {slice_id} is valid")

    if plmn_id != network_resources[site_id][slice_id]["plmnId"]:
        logging.info(f"PLMN ID {plmn_id} is not valid")
        return False

    logging.info(f"PLMN ID {plmn_id} is valid")

    if max_ping < network_resources[site_id][slice_id]["maxPing"]:
        logging.info(
            f'Max ping {max_ping} is not valid. Requested at least {network_resources[site_id][slice_id]["maxPing"]:}')
        return False

    if int(min_throughput_mbps) > int(network_resources[site_id][slice_id]["minThroughputMbps"]):
        logging.info(
            f'Min throughput {min_throughput_mbps} is not valid. Requested max {network_resources[site_id][slice_id]["minThroughputMbps"]:}')
        return False

    if int(uptime_percentage) > int(network_resources[site_id][slice_id]["uptimePercentage"]):
        logging.info(
            f'Uptime percentage {uptime_percentage} is not valid. Requested max {network_resources[site_id][slice_id]["uptimePercentage"]:}')
        return False

    if int(isolation_level) > int(network_resources[site_id][slice_id]["isolationLevel"]):
        logging.info(
            f'Isolation level {isolation_level} is not valid. Requested max {network_resources[site_id][slice_id]["isolationLevel"]:}')
        return False

    logging.info("Access granted")
    return True


def run_server():
    server_address = (authz_server_ip, authz_server_port)
    httpd = HTTPServer(server_address, AuthzHandler)

    # Configure SSL
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED  # Enable mutual authentication
    context.load_cert_chain(
        certfile=f"{args.input_folder}/certs/server.crt",
        keyfile=f"{args.input_folder}/certs/server.key")
    context.load_verify_locations(f"{args.input_folder}/certs/ca.crt")  # CA certificate

    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()


class AuthzHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            jwt_token = self.headers.get('X-Auth-Code')
            jwt_token_plain = decode_jwt_token(jwt_token, sign_verifier_pubkey)
            logging.info("Received JWT token:")
            logging.info(jwt_token_plain)

            if jwt_token_plain is not None and is_allowed(jwt_token_plain):
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
                        help="Path of the folder containing JSON input file and TLS certificates")
    args = parser.parse_args()

    with open(f"{args.input_folder}/authz_server_input.json", "r", encoding="utf-8") as file:
        authz_server_input = json.load(file)

    sign_verifier_pubkey = from_B64_to_ed25519_pubkey(authz_server_input["sign_verifier_pubkey"])
    network_resources = authz_server_input["network_resources"]
    authz_server_ip = args.authz_server_ip
    authz_server_port = args.authz_server_port

    logging.info(f"Starting authorization server on https://{authz_server_ip}:{authz_server_port}")
    # HTTPServer((authz_server_ip, authz_server_port), AAAHandler).serve_forever()
    run_server()