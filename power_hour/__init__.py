"""Power Hour package.

Note: We intentionally avoid importing heavy submodules (like moviepy-dependent
builder) at package import time so that lightweight commands (e.g., YouTube
HTML generator) do not require those dependencies.
"""

__all__: list[str] = []
