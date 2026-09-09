"""Sphinx configuration for the Powerlog documentation."""

import os
import sys
from datetime import date

# Make the package importable when building without an install.
sys.path.insert(0, os.path.abspath("../src"))

from powerlog import __version__  # noqa: E402

# -- Project information ----------------------------------------------------

project = "Powerlog"
author = (
    "Ahmedur Rahman Shovon, Yihao Sun, Zhiling Lan, Swann Perarnau, "
    "Thomas Gilray, Kristopher Micinski, Michael E. Papka, Sidharth Kumar"
)
copyright = f"{date.today().year}, Powerlog authors"
release = __version__
version = __version__

# -- General configuration --------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinxarg.ext",
    "sphinx_copybutton",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- Autodoc ----------------------------------------------------------------

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_preserve_defaults = True
autosummary_generate = True

napoleon_google_docstring = True
napoleon_numpy_docstring = False

# -- Intersphinx ------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output ------------------------------------------------------------

html_theme = "furo"
html_title = f"Powerlog {release}"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/arsho/powerlog/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# -- Misc -------------------------------------------------------------------

copybutton_prompt_text = r"\$ |>>> "
copybutton_prompt_is_regexp = True
