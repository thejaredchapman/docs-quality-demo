"""MkDocs hooks: publish STYLE_GUIDE.md on the site, and show how each rule is checked.

The style guide lives at the repo root (it's the source for the CI checks), so
it isn't inside docs/. This hook adds it to the site as style-guide.md, and
turns each hidden rule tag into a visible "Checked by: ..." label.
"""
import re
from pathlib import Path

from mkdocs.structure.files import File

# Not imported from common.py: MkDocs loads this file by path, so scripts/ may not be importable
GUIDE_PATH = Path(__file__).resolve().parent.parent / "STYLE_GUIDE.md"
TAG = re.compile(r"<!--\s*rule\s+(.*?)\s*-->")
CHECK_NAMES = {
    "vale": "Vale",
    "structure": "Structure check",
    "claude": "Claude review",
    "drift": "UI drift check",
}


def render_rule_tags(markdown):
    """Replace each rule tag with a small label naming the check that enforces it."""
    def replace(match):
        fields = dict(token.split("=", 1) for token in match.group(1).split() if "=" in token)
        check = fields.get("check", "")
        return f'<span class="rule-check">Checked by: {CHECK_NAMES.get(check, check)}</span>'
    return TAG.sub(replace, markdown)


def on_files(files, config):
    files.append(File.generated(config, "style-guide.md", abs_src_path=str(GUIDE_PATH)))
    return files


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri == "style-guide.md":
        return render_rule_tags(markdown)
    return markdown
