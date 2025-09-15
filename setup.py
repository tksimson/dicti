#!/usr/bin/env python3
"""
Setup script for Dicti - Linux Live Dictation
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="dicti",
    version="0.1.0",
    author="tksimson",
    author_email="tksimson@users.noreply.github.com",
    description="Linux Live Dictation - Real-time speech-to-text with Whisper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tksimson/dicti",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.13",
    install_requires=[
        "openai-whisper>=20240930",
        "ffmpeg-python>=0.2.0",
        "pyperclip>=1.8.2",
        "keyboard>=0.13.5",
        "numpy>=1.24.0",
        "torch>=2.0.0",
        "torchaudio>=2.0.0",
        "psutil>=5.9.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "dicti=main:main",
        ],
    },
    keywords="dictation speech-to-text whisper linux real-time",
    project_urls={
        "Bug Reports": "https://github.com/tksimson/dicti/issues",
        "Source": "https://github.com/tksimson/dicti",
        "Documentation": "https://github.com/tksimson/dicti#readme",
    },
)
