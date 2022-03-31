import click

from .options import dboptions
from db.update import update_database


@click.group(help="Update remote databases from local")
def update():
    pass


@update.command(help="Update production database from local")
@dboptions(env="PROD")
def prod(username: str, to_db: str, from_db: str):
    update_database(username, to_db, from_db)


@update.command(help="Update preview database from local")
@dboptions(env="PREVIEW")
def preview(username: str, to_db: str, from_db: str):
    update_database(username, to_db, from_db)
