"""PyInstaller entry point for the BandPrepare CLI.

A standalone launcher (absolute import) so PyInstaller can run it as the top-level
script — ``bandprepare.cli`` is normally reached via the console-script entry, and
``bandprepare.__main__`` uses a relative import that cannot be a frozen entry
point. This shares the same one-folder bundle as the GUI launcher (a second EXE
target over the same COLLECT), so the CLI binary reuses the bundled libraries.
See ``bandprepare.spec``.
"""

import sys

from bandprepare.cli import main

if __name__ == "__main__":
    sys.exit(main())
