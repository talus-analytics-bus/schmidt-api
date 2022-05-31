import os
from typing import Callable

import click


def dboptions(env: str):

    validate_preview_or_prod(env)

    def wrapper(func):
        ops = [
            click.option(
                "--username",
                "-U",
                help="Your local PostgreSQL server username."
                " Defaults to value of env var PG_USERNAME.",
                default=os.getenv("PG_USERNAME"),
            ),
            click.option(
                "--to-db",
                "-t",
                help="Name of remote preview database (e.g., on AWS) to update to."
                f" Defaults to value of PG_{env}_DATABASE.",
                default=os.getenv(f"PG_{env}_DATABASE"),
            ),
            click.option(
                "--from-db",
                "-f",
                help="Name of local database to update from."
                " Defaults to value of PG_LOCAL_DATABASE.",
                default=os.getenv("PG_LOCAL_DATABASE"),
            ),
        ]
        for op in ops:
            func = op(func)
        return func

    return wrapper


def validate_preview_or_prod(env: str):
    if env not in ("PREVIEW", "PROD"):
        raise ValueError(env)
