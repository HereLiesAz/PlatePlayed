"""Command-line entry point: ``plateplayed <command>``."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .db import init_db
from .pipeline import Pipeline


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    Pipeline(config).run()
    return 0


def cmd_init_db(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    init_db(config.database_url)
    print(f"Database initialized at {config.database_url}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import os

    import uvicorn

    os.environ["PLATEPLAYED_CONFIG"] = args.config
    uvicorn.run("plateplayed.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Shared options accepted both before and after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", default="config.yaml", help="Config file path")
    common.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    parser = argparse.ArgumentParser(
        prog="plateplayed",
        description="Watch YouTube streams and log license plates.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", parents=[common], help="Start watching streams and logging plates")
    sub.add_parser("init-db", parents=[common], help="Create database tables and exit")

    serve = sub.add_parser("serve", parents=[common], help="Run the web dashboard / API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    dispatch = {
        "run": cmd_run,
        "init-db": cmd_init_db,
        "serve": cmd_serve,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
