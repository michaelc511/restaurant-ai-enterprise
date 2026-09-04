"""F23: makes `core.*` importable regardless of the directory pytest is invoked
from or which import-mode it defaults to.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
