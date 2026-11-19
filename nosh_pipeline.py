"""Compatibility entry point; the RAG implementation lives in Backend/."""
import sys
from pathlib import Path
from importlib import import_module
sys.path.insert(0, str(Path(__file__).resolve().parent / "Backend"))
_pipeline = import_module("Backend.nosh_pipeline")
if __name__ == "__main__":
    _pipeline.main()
else:
    sys.modules[__name__] = _pipeline
