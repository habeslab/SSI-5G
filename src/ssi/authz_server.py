from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from utils import *
import logging
import ssl
import argparse
import time
import threading
import multiprocessing
import psutil

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

    if max_ping > network_resources[site_id][slice_id]["maxPing"]:
        logging.info(
            f'Max ping {max_ping} is not valid. Requested max {network_resources[site_id][slice_id]["maxPing"]:}')
        return False

    if int(min_throughput_mbps) < int(network_resources[site_id][slice_id]["minThroughputMbps"]):
        logging.info(
            f'Min throughput {min_throughput_mbps} is not valid. Requested at least {network_resources[site_id][slice_id]["minThroughputMbps"]:}')
        return False

    if int(uptime_percentage) < int(network_resources[site_id][slice_id]["uptimePercentage"]):
        logging.info(
            f'Uptime percentage {uptime_percentage} is not valid. Requested max {network_resources[site_id][slice_id]["uptimePercentage"]:}')
        return False

    if int(isolation_level) < int(network_resources[site_id][slice_id]["isolationLevel"]):
        logging.info(
            f'Isolation level {isolation_level} is not valid. Requested max {network_resources[site_id][slice_id]["isolationLevel"]:}')
        return False

    logging.info("Access granted")
    return True


class ConcurrentAuthzServer(ThreadingHTTPServer):
    # socketserver.TCPServer defaults request_queue_size to 5: under
    # concurrent UE load, dozens of near-simultaneous connections would
    # otherwise queue (or get refused) at the OS accept backlog before a
    # handler thread ever sees them, making the server look far slower
    # than the actual per-request JWT-verification cost.
    request_queue_size = 256
    daemon_threads = True


def run_server():
    server_address = (authz_server_ip, authz_server_port)
    # ThreadingHTTPServer: the plain HTTPServer handles one request at a
    # time, which would serialize authorization checks under concurrent
    # UE load and become an artificial bottleneck unrelated to the actual
    # cost of verifying a JWT.
    httpd = ConcurrentAuthzServer(server_address, AuthzHandler)

    # Configure SSL
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED  # Enable mutual authentication
    context.load_cert_chain(
        certfile=f"{args.input_folder}/certs/server.crt",
        keyfile=f"{args.input_folder}/certs/server.key")
    context.load_verify_locations(f"{args.input_folder}/certs/ca.crt")  # CA certificate

    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    # One process-wide RAM monitor: request handling now happens on
    # threads within this single process (ThreadingHTTPServer), so a
    # per-request monitor would just poll the same PID redundantly under
    # concurrent load.
    monitor_proc = multiprocessing.Process(target=monitor_ram, args=(os.getpid(), "authz"), daemon=True)
    monitor_proc.start()

    httpd.serve_forever()


_request_counter = 0
_request_counter_lock = threading.Lock()


class AuthzHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _request_counter
        with _request_counter_lock:
            _request_counter += 1
            request_id = _request_counter

        # Begin time measurement
        start = time.perf_counter()

        try:
            jwt_token = self.headers.get('X-Auth-Code')
            jwt_token_plain = decode_jwt_token(jwt_token, sign_verifier_pubkey)
            logging.info(f"[request {request_id}] Received JWT token:")
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
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))
        finally:
            # End time measurement
            end = time.perf_counter()
            elapsed = end - start
            logging.info(f"[request {request_id}] Elapsed time: {elapsed}")


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