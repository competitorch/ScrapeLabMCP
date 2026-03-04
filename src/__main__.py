"""Entry point for `uvx scrapelab-mcp` and `python -m src`."""
import sys
from pathlib import Path


def main():
    # Add src/ to sys.path so bare imports (from browser_manager import ...) work
    src_dir = str(Path(__file__).parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from server import main as _main
    _main()


if __name__ == "__main__":
    main()
