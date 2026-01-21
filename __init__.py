"""
VerifyRef - High-performance academic reference verification tool
Copyright (C) 2025 Hosein Hadipour <hsn.hadipour@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

A comprehensive tool for verifying the authenticity of academic references 
in PDF documents using multiple databases and AI-powered verification with 
advanced parallel processing optimization.

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Author Name"
__email__ = "author@example.com"
__license__ = "GPLv3"

# Lazy import to avoid circular import issues
def __getattr__(name):
    if name == "main":
        from . import verifyref
        return verifyref.main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "main",
    "__version__",
    "__author__",
    "__email__",
    "__license__",
]
