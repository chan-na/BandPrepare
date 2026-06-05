"""PyInstaller entry point for the BandPrepare GUI.

A standalone launcher (absolute import) so PyInstaller can run it as the top-level
script — ``bandprepare.gui.__main__`` uses a relative import and cannot be a
frozen entry point. See ``bandprepare.spec``.
"""

import sys

from bandprepare.gui import main

if __name__ == "__main__":
    sys.exit(main())
