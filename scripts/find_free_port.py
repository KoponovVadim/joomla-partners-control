#!/usr/bin/env python3
import argparse
import socket

def is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Поиск свободного TCP-порта на loopback")
    parser.add_argument("--start", type=int, default=8100)
    parser.add_argument("--end", type=int, default=8999)
    args = parser.parse_args()
    for port in range(args.start, args.end + 1):
        if is_free(port):
            print(port); return
    raise SystemExit(f"Нет свободных портов в диапазоне {args.start}-{args.end}")
if __name__ == "__main__": main()

