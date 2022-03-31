import click
from .ingest import ingest
from .update import update


@click.group()
def hsn():
    pass


hsn.add_command(ingest)
hsn.add_command(update)


def app():
    hsn(obj={})


if __name__ == "__main__":
    app()
