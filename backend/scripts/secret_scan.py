"""Secret 扫描（spec §50）：检查仓库中是否出现真实凭据。

用法：python scripts/secret_scan.py <repo_root>
退出码 0 = 未发现；1 = 发现疑似泄漏。
"""

import re
import sys
from pathlib import Path

PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI 风格 API Key"),
    (re.compile(r"shpat_[A-Za-z0-9]{20,}"), "Shopify access token"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), "GitHub OAuth token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    (re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "私钥"),
    (re.compile(r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE), "硬编码密码"),
]

SKIP_DIRS = {
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".git",
    ".playwright-mcp",
    "dist",
    "build",
}
SKIP_FILES = {".env", "package-lock.json"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2", ".pyc"}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings: list[str] = []
    scanned = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES or path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for pattern, label in PATTERNS:
            for match in pattern.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                findings.append(f"{path.relative_to(root)}:{line_no} [{label}] {match.group()[:24]}...")

    print(f"scanned files: {scanned}")
    if findings:
        print(f"FINDINGS: {len(findings)}")
        for item in findings:
            print("  " + item)
        return 1
    print("no hardcoded secrets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
