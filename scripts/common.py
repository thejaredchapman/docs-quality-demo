"""Small helpers shared by the scripts."""
import os
from pathlib import Path

import yaml

# The repo's top folder, no matter where the script is run from
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
GUIDE_PATH = REPO_ROOT / "STYLE_GUIDE.md"
# Both generated from STYLE_GUIDE.md by scripts/build_rules.py
CHECKLIST_PATH = REPO_ROOT / "checklist.yaml"
CONTENT_TYPES_PATH = REPO_ROOT / "content_types.yaml"

# Every page declares one of these in its frontmatter, for example `type: how-to`
CONTENT_TYPES = ("tutorial", "how-to", "reference", "troubleshooting", "landing")


def publish(markdown):
    """Print a report, and also add it to the GitHub Actions job summary when running in CI."""
    print(markdown)
    # GitHub sets this variable to a file path; anything written there shows on the run's summary page
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def split_frontmatter(text):
    """Split a page into (frontmatter dict, body text, number of file lines before the body).

    Frontmatter is a YAML block between two `---` lines at the very top of the page.
    A page with no frontmatter, or with broken YAML, gets an empty dict, so the
    structure check can report "no type" instead of crashing.
    """
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                try:
                    meta = yaml.safe_load("\n".join(lines[1:index])) or {}
                except yaml.YAMLError:
                    meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                return meta, "\n".join(lines[index + 1:]), index + 1
    return {}, text, 0


def read_page(path):
    """Read a docs page and split off its frontmatter. See split_frontmatter."""
    return split_frontmatter(Path(path).read_text(encoding="utf-8"))
