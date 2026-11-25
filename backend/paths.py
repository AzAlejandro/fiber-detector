import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_HOME = Path(os.environ.get('LOCO_DATA_DIR') or PROJECT_ROOT).expanduser().resolve()
OUTPUT_ROOT = DATA_HOME / 'outputs' / 'scribble_research'
