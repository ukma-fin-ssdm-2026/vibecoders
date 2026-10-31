import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "api"))

from seed import seed_db  # noqa: E402


if __name__ == "__main__":
    seed_db()
