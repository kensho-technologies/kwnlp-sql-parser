import codecs
import os

from setuptools import find_packages, setup


# single sourcing package version strategy taken from
# https://packaging.python.org/guides/single-sourcing-package-version


PACKAGE_NAME = "kwnlp_sql_parser"


def read_file(filename: str) -> str:
    """Read package file as text to get name and version."""
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, PACKAGE_NAME, filename), "r") as f:
        return f.read()


def find_version() -> str:
    """Only define version in one place."""
    for line in read_file("__init__.py").splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


def find_long_description() -> str:
    """Return the content of the README.rst file."""
    return read_file("../README.md")


setup(
    name=PACKAGE_NAME,
    version=find_version(),
    description="Utility for parsing Wikipedia SQL dumps into CSVs.",
    long_description=find_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/kensho-technologies/kwnlp-sql-parser",
    author="Kensho Technologies LLC.",
    author_email="kwnlp@kensho.com",
    license="Apache 2.0",
    packages=find_packages(exclude=["tests*"]),
    package_data={"": []},
    install_requires=[],
    extras_require={
        "dev": [
            "pre-commit",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="wikipedia sql dump open data",
    python_requires=">=3.6",
)
