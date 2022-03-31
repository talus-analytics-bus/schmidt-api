import subprocess


def update_database(username: str, to_db: str, from_db: str):
    """Update remote database with local."""
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
