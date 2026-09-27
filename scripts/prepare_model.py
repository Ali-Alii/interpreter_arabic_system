"""Download pinned weights and verify that the model can load."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.engine import engine

if __name__ == '__main__':
    engine.load()
    print(f'Model ready on {engine.device}.')
