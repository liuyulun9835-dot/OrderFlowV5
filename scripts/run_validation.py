"""CLI entrypoint to run validator pipelines."""
from __future__ import annotations

import argparse
from pathlib import Path

from validation import validator_v2


def run_v1() -> None:
    raise NotImplementedError("Validator v1 is not implemented in this repository.")


def run_v2() -> None:
    artifacts = validator_v2.run()
    for name, path in artifacts.items():
        print(f"generated {name}: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OrderFlow validator")
    parser.add_argument("--mode", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()
    if args.mode == "v1":
        run_v1()
    else:
        run_v2()


if __name__ == "__main__":
    main()
