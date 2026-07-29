from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_config() -> dict:
    with (ROOT / "configs" / "config.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)

