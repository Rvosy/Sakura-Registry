"""Compare records with an event's base commit; no shell interpolation."""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from registry.core import read_json, unique_object, validate_history
import json

base = os.environ.get("REGISTRY_BASE", "")
if not base or base == "0" * 40:
    print("Initial repository push: no previous records.")
else:
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("BASE_COMMIT_INVALID")
    previous = subprocess.run(["git", "show", f"{base}:plugins.json"], check=True, capture_output=True).stdout
    validate_history(read_json(Path("plugins.json")), json.loads(previous, object_pairs_hook=unique_object))
    print("Version history preserved.")
