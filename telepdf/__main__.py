from __future__ import annotations

import argparse

from .http_app import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TelePDF local web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
