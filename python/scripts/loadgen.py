#!/usr/bin/env python3
"""
Meminator load generator — sends requests at random intervals while the app is running.

Usage:
    python3 scripts/loadgen.py                  # default: 1-5s between requests
    python3 scripts/loadgen.py --min 0.5 --max 3
    python3 scripts/loadgen.py --min 1 --max 10 --url http://localhost:10114
"""

import argparse
import random
import time
import sys
import requests
from datetime import datetime


BASE_URL = "http://localhost:10114"
HEALTH_URL = f"{BASE_URL}/backend/health"
CREATE_URL = f"{BASE_URL}/backend/createPicture"


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", flush=True)


def wait_for_app(timeout=30):
    """Wait until the app is healthy before starting load."""
    log("Checking app health...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(HEALTH_URL, timeout=2)
            if r.ok:
                log("App is healthy — starting load generator")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    log(f"App not reachable after {timeout}s — is it running?", "ERROR")
    return False


def send_request(session):
    """Send a single createPicture request and log the result."""
    try:
        start = time.time()
        r = session.post(CREATE_URL, timeout=15)
        duration_ms = round((time.time() - start) * 1000)

        if r.ok:
            size_kb = round(len(r.content) / 1024, 1)
            log(f"✓  {r.status_code}  {duration_ms}ms  {size_kb}KB")
        else:
            log(f"✗  {r.status_code}  {duration_ms}ms", "WARN")

    except requests.Timeout:
        log("Request timed out", "WARN")
    except requests.ConnectionError:
        log("Connection refused — is the app still running?", "ERROR")


def run(min_delay, max_delay, base_url):
    global HEALTH_URL, CREATE_URL
    HEALTH_URL = f"{base_url}/backend/health"
    CREATE_URL = f"{base_url}/backend/createPicture"

    if not wait_for_app():
        sys.exit(1)

    log(f"Sending requests every {min_delay}–{max_delay}s  (Ctrl+C to stop)")

    session = requests.Session()
    count = 0

    try:
        while True:
            count += 1
            log(f"── Request #{count} ──────────────────")
            send_request(session)
            delay = random.uniform(min_delay, max_delay)
            log(f"Sleeping {delay:.1f}s")
            time.sleep(delay)
    except KeyboardInterrupt:
        log(f"Stopped after {count} requests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meminator load generator")
    parser.add_argument("--min", type=float, default=1.0, help="Min seconds between requests (default: 1)")
    parser.add_argument("--max", type=float, default=5.0, help="Max seconds between requests (default: 5)")
    parser.add_argument("--url", type=str, default=BASE_URL, help=f"Base URL (default: {BASE_URL})")
    args = parser.parse_args()

    if args.min >= args.max:
        print("Error: --min must be less than --max")
        sys.exit(1)

    run(args.min, args.max, args.url)
