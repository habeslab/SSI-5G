"""Builds the canonicalized, Base64-encoded VC payload signed by the
issuer(s). Shared by issuer.py, issuer_mininet.py and issuer_baseline.py
so the exact same message (and therefore the same signing cost) is used
across the threshold-signature scheme and the single-issuer baseline.
"""
import base64
import datetime
import os

import jcs


def build_message_b64(validity_days=180):
    expiration_date = datetime.datetime.utcnow() + datetime.timedelta(days=validity_days)
    message_dict = {
        "plmnId": os.getenv("SUB_PLMN_ID"),
        "maxPing": os.getenv("SUB_MAX_PING"),
        "minThroughputMbps": os.getenv("SUB_MIN_THROUGHPUT_MBPS"),
        "uptimePercentage": os.getenv("SUB_UPTIME_PERCENTAGE"),
        "isolationLevel": os.getenv("SUB_ISOLATION_LEVEL"),
        "expirationDate": expiration_date.strftime("%Y-%m-%d %H:%M:%S")
    }
    message_json = jcs.canonicalize(message_dict)
    return base64.b64encode(message_json).decode("utf-8")
