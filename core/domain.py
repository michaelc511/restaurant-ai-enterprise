# F12: Domain pack loader - picks the active domains/<DOMAIN>/domain.py, so core/, engines/ and
# engine_api.py stay domain-agnostic and a new domain is a new folder, not a copy of the repo.
import importlib
import os
from pathlib import Path
from types import ModuleType

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())  # F12: DOMAIN may come from .env, and this can be the first module imported

DOMAINS_DIR = Path(__file__).resolve().parent.parent / "domains"
DOMAIN = os.environ.get("DOMAIN", "restaurant")  # F12: which domains/<name>/ pack is active


def available_domains() -> list[str]:
    return sorted(p.name for p in DOMAINS_DIR.iterdir() if (p / "domain.py").exists())


def load_domain(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"domains.{name}.domain")
    except ModuleNotFoundError as e:
        if e.name not in (f"domains.{name}", f"domains.{name}.domain"):  # a real missing import inside the pack
            raise
        raise ValueError(f"Unknown domain: {name}. Choose one of {available_domains()}") from e


domain = load_domain(DOMAIN)
