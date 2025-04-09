"""Setup script for danbooru-tools."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="danbooru-tag-expander",
    version="0.1.0",
    description="A tool for expanding Danbooru tags with their implications and aliases",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Allen Day",
    author_email="allenday@allenday.com",
    url="https://github.com/allenday/danbooru-tag-expander",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "requests",
        "tqdm"
    ],
    entry_points={
        "console_scripts": [
            "danbooru-tag-expander=danbooru_tools.tag_expander_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.6",
) 