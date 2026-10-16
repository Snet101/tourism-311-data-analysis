"""Save both predeclared keyword specifications; never select a winning result."""

import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tourism_pipeline import RULES, load_config, run, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config, base, _ = load_config(args.config)
    args.out.mkdir(parents=True, exist_ok=False)
    save_json(args.out / "status.json", {"state": "incomplete"})
    summaries = []
    try:
        for name in RULES:
            spec = copy.deepcopy(config)
            spec["keyword_rule"] = name
            for kind in ["requests", "trends"]:
                for source in spec[kind]:
                    source["path"] = str((base / source["path"]).resolve())
            path = args.out / (name + "-config.json")
            save_json(path, spec)
            target = run(path, args.out / name)
            summaries.append(
                {
                    "rule": name,
                    "correlations": json.loads((target / "correlations.json").read_text()),
                    "audit": json.loads((target / "audit.json").read_text()),
                }
            )
        save_json(args.out / "sensitivity.json", summaries)
        save_json(args.out / "status.json", {"state": "complete"})
    except Exception:
        save_json(args.out / "status.json", {"state": "failed"})
        raise


if __name__ == "__main__":
    main()
