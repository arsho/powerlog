"""Allow ``python -m powerlog`` to behave like the ``powerlog`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
