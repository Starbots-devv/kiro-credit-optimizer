"""Offline checks for links, Skill metadata and accidental private artifacts."""

import ast
import os
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".kiro" / "skills" / "kiro-credit-optimizer"
SKIP = {
    ".git",
    ".venv",
    ".local",
    ".kiro-credits",
    "__pycache__",
    ".ruff_cache",
    "dist",
    "build",
}


def files():
    for directory, children, names in os.walk(ROOT):
        children[:] = [c for c in children if c not in SKIP and not c.endswith(".egg-info")]
        for name in names:
            yield Path(directory) / name


def anchors(text):
    result = set(re.findall(r'(?:id|name)="([^"]+)"', text))
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        result.add(re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-"))
    return result


def main():
    errors = []
    paths = list(files())
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix in {".sqlite3", ".db", ".key", ".pem"} or path.name.startswith(".env"):
            errors.append(f"Private-looking file in public source: {relative}")
        if path.suffix not in {".md", ".py", ".toml", ".yml", ".svg", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(
            r"gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----", text
        ):
            errors.append(f"Possible secret in {relative}")
        if path.suffix == ".py":
            ast.parse(text, filename=relative)
        if path.suffix == ".md":
            links = re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text)
            links += re.findall(r'(?:src|href)="([^"]+)"', text)
            for link in links:
                split = urlsplit(link)
                if split.scheme or split.netloc:
                    continue
                target = (path.parent / unquote(split.path)).resolve() if split.path else path
                if not target.is_relative_to(ROOT) or not target.exists():
                    errors.append(f"Broken local link in {relative}: {link}")
                elif (
                    split.fragment
                    and target.suffix == ".md"
                    and split.fragment not in anchors(target.read_text(encoding="utf-8"))
                ):
                    errors.append(f"Missing anchor in {relative}: {link}")
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        errors.append("Skill frontmatter is missing.")
    else:
        metadata = yaml.safe_load(parts[1])
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != SKILL.name
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata.get("name", ""))
        ):
            errors.append("Skill name must match its folder and Agent Skills naming rules.")
        if (
            not isinstance(metadata.get("description"), str)
            or not 1 <= len(metadata["description"]) <= 1024
        ):
            errors.append("Skill description must be 1..1024 characters.")
        if len(parts[2].split()) > 1500:
            errors.append("Skill entrypoint is too large; use progressive references.")
    if (SKILL / "LICENSE").read_bytes() != (ROOT / "LICENSE").read_bytes():
        errors.append("Portable Skill license differs from original repository license.")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project.get("dependencies"):
        errors.append("This release promises zero third-party runtime dependencies.")
    tree = ET.parse(ROOT / "assets" / "hero.svg")  # noqa: S314 - trusted repository SVG
    if tree.getroot().tag != "{http://www.w3.org/2000/svg}svg":
        errors.append("Hero must be valid SVG.")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Repository checks passed: {len(paths)} source files; local links, anchors, Skill metadata, SVG, license and private-artifact scan."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
