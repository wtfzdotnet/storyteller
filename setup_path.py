"""Path setup for storyteller package imports."""

import sys
from pathlib import Path

# Add both src and src/storyteller to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "src" / "storyteller"))
