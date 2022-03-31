from setuptools import setup, find_namespace_packages

setup(
    name="hsn",
    version="1.0.0",
    description="Health Security Net (HSN) command line interface (CLI)",
    author="Mike Van Maele",
    author_email="mvanmaele@talusanalytics.com",
    entry_points={"console_scripts": ["hsn = cli.hsn:app"]},
    packages=find_namespace_packages(
        where=".", include=["api.*", "cli.*", "db.*", "ingest.*"]
    ),
    # scripts=["sh/*.sh"],
)
