from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
DENY_PATH_PARTS = {
    "research-memory",
    "research",
    "receipts",
    "handoffs",
    "audits",
    "work",
    "reports",
}
DENY_FILENAMES = {"CURRENT.md", ".env", "credentials.json", "secrets.json"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".csv", ".sh", ".txt"}
PATTERNS = {
    "private_identity": re.compile(r"(?i)\b(Jef|Kyoti|AgentKey|JBrain)\b"),
    "windows_user_path": re.compile(r"(?i)(?:[A-Z]:\\Users\\|/mnt/[a-z]/Users/)[^\s'\"]+"),
    "linux_home_path": re.compile(r"/home/(?!runner\b|user\b)[A-Za-z0-9._-]+/"),
    "chat_or_base_id": re.compile(r"\b(?:oc_[a-z0-9]{12,}|rq[A-Za-z0-9]{12,})\b"),
    "token_shape": re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{20,})\b"),
    "assigned_secret": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{12,}['\"]"),
    "private_email": re.compile(r"\b[A-Z0-9._%+-]+@(?!example\.com\b)[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
}


def candidate_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
        )
        names = [name for name in result.stdout.decode().split("\0") if name]
        if names:
            return [ROOT / name for name in names]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        pass
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    findings: list[str] = []
    for path in candidate_files():
        rel = path.relative_to(ROOT)
        if path.is_symlink():
            findings.append(f"symlink:{rel}")
            continue
        if rel.name in DENY_FILENAMES or any(part in DENY_PATH_PARTS for part in rel.parts):
            findings.append(f"denied_path:{rel}")
        if path.stat().st_size > 1_000_000:
            findings.append(f"large_file:{rel}:{path.stat().st_size}")
        if path == SELF or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non_utf8_text:{rel}")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}:{rel}")
    if findings:
        print("public_release_guard=fail")
        for finding in sorted(set(findings)):
            print(f"finding={finding}")
        return 1
    print(f"public_release_guard=pass files={len(candidate_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
