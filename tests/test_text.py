"""Keep the repo free of em dashes and en dashes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("\u2012", "\u2013", "\u2014", "\u2015", "\u2212")
SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".txt", ""}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache"}


def test_repo_text_has_no_em_or_en_dashes():
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.suffix not in SUFFIXES and path.name != "LICENSE":
            continue
        text = path.read_text(encoding="utf-8")
        for character in BANNED:
            if character in text:
                offenders.append(f"{path.relative_to(ROOT)} contains U+{ord(character):04X}")
    assert offenders == []
