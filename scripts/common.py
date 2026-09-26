"""Small helpers shared by the scripts."""
import os
from pathlib import Path

# The repo's top folder, no matter where the script is run from
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


def publish(markdown):
    """Print a report, and also add it to the GitHub Actions job summary when running in CI."""
    print(markdown)
    # GitHub sets this variable to a file path; anything written there shows on the run's summary page
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")
