"""Execute each notebook in an independent kernel using this interpreter."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=Path("runs/fixture"))
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    root = Path(__file__).resolve().parents[1]
    destination = args.run.resolve()
    os.environ["TOURISM_RUN"] = str(destination)
    with tempfile.TemporaryDirectory(prefix="tourism-kernel-") as temp:
        kernel = Path(temp) / "kernels" / "tourism-check"
        kernel.mkdir(parents=True)
        (kernel / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "Tourism validation",
                    "language": "python",
                }
            )
        )
        os.environ["JUPYTER_PATH"] = temp + os.pathsep + os.environ.get("JUPYTER_PATH", "")
        os.environ["IPYTHONDIR"] = str(Path(temp) / "ipython")
        for name in ["311_processing.ipynb", "tourism_search_trends.ipynb", "correlation_analysis.ipynb"]:
            notebook = nbformat.read(root / name, as_version=4)
            client = NotebookClient(
                notebook, timeout=180, kernel_name="tourism-check", resources={"metadata": {"path": str(root)}}
            )
            client.execute()
            nbformat.write(notebook, destination / ("executed-" + name))
            print("PASS:", name)


if __name__ == "__main__":
    main()
