import click
from ingest import main as ingestmain


@click.group()
def hsn():
    pass


@hsn.command()
def ingest():

    # skip if no new
    skip_if_no_new: bool = True

    # run main ingest code
    ingestmain(skip_if_no_new)


if __name__ == "__main__":
    hsn(obj={})
