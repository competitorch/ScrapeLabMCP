"""uvx entry point — patches sys.path before importing server."""
import sys
from pathlib import Path


def main():
    src_dir = str(Path(__file__).parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from server import main as server_main
    server_main()
