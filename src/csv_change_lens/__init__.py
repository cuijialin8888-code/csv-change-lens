"""Offline CSV comparison; reports omit cell values unless explicitly requested."""

from .core import InputError, compare_files

__version__ = "0.1.0"
__all__ = ["InputError", "compare_files", "__version__"]
