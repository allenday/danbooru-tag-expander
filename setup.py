"""Setup script for danbooru-tag-expander."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="danbooru-tag-expander",
    version="0.1.2",
    description="A tool for expanding Danbooru tags with their implications and aliases",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Allen Day",
    author_email="allenday@gmail.com",
    url="https://github.com/allenday/danbooru-tag-expander",
    packages=find_packages(),
    install_requires=[
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
        "tqdm>=4.62.0",
        "pybooru>=4.2.2"
    ],
    entry_points={
        "console_scripts": [
            "danbooru-tag-expander=danbooru_tag_expander.tag_expander_cli:main",
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
