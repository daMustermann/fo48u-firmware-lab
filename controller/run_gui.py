import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fo48u_controller.gui import main

raise SystemExit(main())