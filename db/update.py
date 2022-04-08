import subprocess


def update_database(username: str, to_db: str, from_db: str):
    """Update remote database with local."""
    validate_args(username, to_db, from_db)
    res = subprocess.run(
        [
            "bash",
            "./sh/update-schmidt-aws-rds-from-local.sh",
            username,
            to_db,
            from_db,
        ],
    )
    return res


def validate_args(username, to_db, from_db):
    if username is None:
        raise ValueError(username)

    if to_db is None:
        raise ValueError(to_db)

    if from_db is None:
        raise ValueError(from_db)
