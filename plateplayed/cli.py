"""Command-line entry point: ``plateplayed <command>``."""

from __future__ import annotations

import argparse
import logging
import os
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


def cmd_migrate(args: argparse.Namespace) -> int:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config as AlembicConfig

    config = load_config(args.config)
    os.environ["PLATEPLAYED_DB_URL"] = config.database_url
    os.environ["PLATEPLAYED_CONFIG"] = args.config
    ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    command.upgrade(AlembicConfig(str(ini)), "head")
    print(f"Migrations applied to {config.database_url}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from .stream import probe_stream

    config = load_config(args.config)
    streams = config.streams if args.all else config.enabled_streams
    if not streams:
        print("No streams configured." if args.all else "No enabled streams.")
        return 1

    failures = 0
    for stream in streams:
        print(f"• {stream.name}  ({stream.url})")
        probe = probe_stream(stream.url, timeout=args.timeout)
        if probe.ok:
            res = f"{probe.width}x{probe.height}" if probe.width else "unknown size"
            fps = f"{probe.fps:.0f} fps" if probe.fps else "fps unknown"
            print(f"    OK — {res} @ {fps} (decoded {probe.frames_read} frames)")
        else:
            failures += 1
            print(f"    FAIL — {probe.error}")

    print(f"\n{len(streams) - failures}/{len(streams)} stream(s) OK.")
    return 1 if failures else 0


def cmd_serve(args: argparse.Namespace) -> int:
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
    sub.add_parser("migrate", parents=[common], help="Apply Alembic migrations to the database")

    check = sub.add_parser("check", parents=[common], help="Probe configured streams (resolution/FPS)")
    check.add_argument("--all", action="store_true", help="Include disabled streams")
    check.add_argument("--timeout", type=float, default=30.0, help="Per-stream timeout (seconds)")

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
        "migrate": cmd_migrate,
        "check": cmd_check,
        "serve": cmd_serve,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
