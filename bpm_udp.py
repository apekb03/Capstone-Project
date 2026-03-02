"""
bpm_udp.py — Simple UDP BPM receiver (debug tool)

This listens on your PC and prints BPM values coming from your Android app.

How to use:
1) Put your PC IP into the Android app: 192.168.1.161
2) Make sure the Android app is sending to UDP port 5005 (recommended to match your game).
3) Run:  python bpm_udp.py
"""

import socket
import time
import json

PC_IP = "0.0.0.0"   # listen on all network interfaces
PORT = 5005         # must match what your phone is sending to

def parse_bpm(msg: str):
    msg = msg.strip()
    if not msg:
        return None

    # JSON: {"bpm":82}
    if msg.startswith("{") and msg.endswith("}"):
        try:
            obj = json.loads(msg)
            bpm = obj.get("bpm", None)
            if bpm is None:
                return None
            return int(round(float(bpm)))
        except Exception:
            return None

    # "BPM:82" or "anything:82"
    if ":" in msg:
        parts = msg.split(":")
        for p in reversed(parts):
            p = p.strip()
            if p.replace(".", "", 1).isdigit():
                return int(round(float(p)))

    # plain number "82"
    if msg.replace(".", "", 1).isdigit():
        return int(round(float(msg)))

    return None

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((PC_IP, PORT))
    sock.settimeout(1.0)

    print(f"Listening for BPM on UDP {PC_IP}:{PORT} ... (Ctrl+C to stop)")
    last = None
    last_time = 0.0

    while True:
        try:
            data, addr = sock.recvfrom(512)
            msg = data.decode("utf-8", errors="ignore")
            bpm = parse_bpm(msg)
            if bpm is None:
                continue

            # clamp to realistic range
            bpm = max(40, min(200, bpm))

            now = time.time()
            # only print if it changed or at least 0.5s passed
            if bpm != last or (now - last_time) > 0.5:
                print(f"From {addr[0]}:{addr[1]}  ->  BPM = {bpm}   (raw='{msg.strip()}')")
                last, last_time = bpm, now

        except socket.timeout:
            continue

if __name__ == "__main__":
    main()
