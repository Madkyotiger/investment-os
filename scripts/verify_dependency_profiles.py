from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAVY_MODULES = ("yfinance", "openbb", "financetoolkit", "edgar", "akshare", "tushare")
PROFILES = {
    "core": {
        "extras": (),
        "required": ("numpy", "pandas", "yaml", "investment_os"),
        "forbidden": HEAVY_MODULES,
    },
    "market": {
        "extras": ("market",),
        "required": ("numpy", "pandas", "yaml", "investment_os", "yfinance"),
        "forbidden": ("openbb", "financetoolkit", "edgar", "akshare", "tushare"),
    },
    "global-research": {
        "extras": ("global-research",),
        "required": ("investment_os", "yfinance", "openbb", "financetoolkit", "edgar"),
        "forbidden": (),
    },
    "china": {
        "extras": ("china",),
        "required": ("investment_os", "akshare", "tushare"),
        "forbidden": (),
    },
}


def probe_code(profile: str) -> str:
    config = PROFILES[profile]
    required = repr(config["required"])
    forbidden = repr(config["forbidden"])
    return (
        "import importlib, importlib.util\n"
        f"required = {required}\n"
        f"forbidden = {forbidden}\n"
        "for module in required:\n"
        "    importlib.import_module(module)\n"
        "present = [module for module in forbidden if importlib.util.find_spec(module) is not None]\n"
        "assert not present, f'unexpected modules: {present}'\n"
        f"print('profile={profile} status=pass')\n"
    )


def verify_profile(profile: str) -> None:
    config = PROFILES[profile]
    command = ["uv", "run", "--frozen", "--isolated", "--link-mode", "copy"]
    for extra in config["extras"]:
        command.extend(["--extra", extra])
    command.extend(["python", "-c", probe_code(profile)])
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify locked dependency profiles without changing the project environment."
    )
    parser.add_argument(
        "profiles",
        nargs="*",
        metavar="PROFILE",
        help="Profiles to verify. The default checks every profile.",
    )
    args = parser.parse_args()
    unknown = [profile for profile in args.profiles if profile not in PROFILES]
    if unknown:
        parser.error(f"unknown profile: {', '.join(unknown)}")

    for profile in args.profiles or PROFILES:
        verify_profile(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
