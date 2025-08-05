#!/usr/bin/env python3
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

Setup script for VerifyRef
"""

from setuptools import setup, find_packages
import pathlib

# Read the README file
HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text(encoding='utf-8')

# Read requirements
REQUIREMENTS = (HERE / "requirements.txt").read_text(encoding='utf-8').strip().split('\n')
REQUIREMENTS = [req.strip() for req in REQUIREMENTS if req.strip() and not req.startswith('#')]

setup(
    name="verifyref",
    version="1.0.0",
    description="High-performance academic reference verification tool with parallel processing and AI-powered fraud detection",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/user/verifyref",
    author="Author Name",
    author_email="author@example.com",
    license="GPLv3",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Education",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Education",
        "Topic :: Text Processing :: Academic",
        "Operating System :: OS Independent",
    ],
    keywords="academic references verification bibliography fraud-detection parallel-processing ai-powered",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=REQUIREMENTS,
    extras_require={
        "ai": ["openai>=1.0.0"],
        "dev": ["pytest", "black", "flake8", "mypy"],
        "docs": ["sphinx", "sphinx-rtd-theme"],
    },
    entry_points={
        "console_scripts": [
            "verifyref=verifyref:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    project_urls={
        "Bug Reports": "https://github.com/your-username/verifyref/issues",
        "Source": "https://github.com/your-username/verifyref",
        "Documentation": "https://github.com/your-username/verifyref/blob/main/README.md",
    },
)
