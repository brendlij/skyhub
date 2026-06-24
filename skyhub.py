import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SERVER_DIR = REPO_ROOT / "server"
NODE_DIR = REPO_ROOT / "node"


def venv_python(role_dir: Path, venv_name: str) -> str:
    if os.name == "nt":
        candidate = role_dir / venv_name / "Scripts" / "python.exe"
    else:
        candidate = role_dir / venv_name / "bin" / "python"

    if candidate.exists():
        return str(candidate)

    return sys.executable


def server_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()

    if args.data_dir:
        env["SKYHUB_SERVER_DATA_DIR"] = str(Path(args.data_dir).resolve())

    return env


def node_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()

    if args.node_id:
        env["SKYHUB_NODE_NODE_ID"] = args.node_id

    if args.server_ws_base_url:
        env["SKYHUB_NODE_SERVER_WS_BASE_URL"] = args.server_ws_base_url

    if args.camera_driver:
        env["SKYHUB_NODE_CAMERA_DRIVER"] = args.camera_driver

    if args.captures_dir:
        env["SKYHUB_NODE_CAPTURES_DIR"] = str(Path(args.captures_dir).resolve())

    return env


def start_server(args: argparse.Namespace) -> subprocess.Popen:
    python = venv_python(SERVER_DIR, ".venv-server")
    command = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    return subprocess.Popen(command, cwd=SERVER_DIR, env=server_env(args))


def start_node(args: argparse.Namespace) -> subprocess.Popen:
    python = venv_python(NODE_DIR, ".venv-node")
    return subprocess.Popen(
        [python, "-m", "app.main"],
        cwd=NODE_DIR,
        env=node_env(args),
    )


def terminate(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 10

    for process in processes:
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)

        if process.poll() is None:
            process.kill()


def wait_for_processes(processes: list[subprocess.Popen]) -> int:
    while True:
        for process in processes:
            return_code = process.poll()
            if return_code is not None:
                terminate(processes)
                return return_code

        time.sleep(0.5)


def run_server(args: argparse.Namespace) -> int:
    process = start_server(args)
    try:
        return process.wait()
    except KeyboardInterrupt:
        terminate([process])
        return 130


def run_node(args: argparse.Namespace) -> int:
    process = start_node(args)
    try:
        return process.wait()
    except KeyboardInterrupt:
        terminate([process])
        return 130


def run_standalone(args: argparse.Namespace) -> int:
    if not args.server_ws_base_url:
        args.server_ws_base_url = f"ws://127.0.0.1:{args.port}/ws/nodes"

    processes: list[subprocess.Popen] = []

    try:
        processes.append(start_server(args))
        time.sleep(args.node_start_delay)
        processes.append(start_node(args))
        return wait_for_processes(processes)

    except KeyboardInterrupt:
        terminate(processes)
        return 130

    except Exception:
        terminate(processes)
        raise


def add_common_server_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir")


def add_common_node_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--node-id")
    parser.add_argument("--server-ws-base-url")
    parser.add_argument("--camera-driver", choices=["mock", "picamera2"])
    parser.add_argument("--captures-dir")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skyhub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="run the SkyHub server")
    add_common_server_args(server_parser)
    server_parser.set_defaults(func=run_server)

    node_parser = subparsers.add_parser("node", help="run a SkyHub camera node")
    add_common_node_args(node_parser)
    node_parser.set_defaults(func=run_node)

    standalone_parser = subparsers.add_parser(
        "standalone",
        help="run server and node together on this machine",
    )
    add_common_server_args(standalone_parser)
    add_common_node_args(standalone_parser)
    standalone_parser.add_argument("--node-start-delay", type=float, default=1)
    standalone_parser.set_defaults(func=run_standalone)

    return parser


def main() -> int:
    def stop_from_signal(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_from_signal)

    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
