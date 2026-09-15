"""Sphinx configuration for the Powerlog documentation."""

import os
import sys
from datetime import date

# Make the package importable when building without an install.
sys.path.insert(0, os.path.abspath("../src"))

from powerlog import __version__  # noqa: E402

# -- Project information ----------------------------------------------------

project = "Powerlog"
author = "Ahmedur Rahman Shovon"
copyright = f"{date.today().year}, {author}"
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
    ".md": "markdown",
    ".rst": "restructuredtext",
}

# -- MyST (Markdown) --------------------------------------------------------

# The documentation is written in Markdown; these extensions cover the
# constructs it uses that plain CommonMark lacks.
myst_enable_extensions = [
    "deflist",      # term/definition lists
    "dollarmath",   # $...$ and $$...$$ maths
    "colon_fence",  # ::: directive fences, readable inside Markdown
]

# Give every heading down to <h3> an anchor, so in-page links work.
myst_heading_anchors = 3


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
