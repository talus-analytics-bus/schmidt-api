import click
from ingest import main as ingestmain


@click.command(help="Ingest data locally")
@click.option(
    "--force",
    "-f",
    default=False,
    is_flag=True,
    help="Forces ingest to be run even if no new items are found",
)
def ingest(force: bool = False):

    # run main ingest code
    ingestmain(not force)
