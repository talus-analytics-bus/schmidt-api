import click
from ingest import main as ingestmain


@click.group()
def hsn():
    pass


@hsn.command()
@click.option(
    "--force",
    default=False,
    is_flag=True,
    help="Forces ingest to be run even if no new items are found",
)
def ingest(force: bool = False):

    # run main ingest code
    ingestmain(not force)


if __name__ == "__main__":
    hsn(obj={})
