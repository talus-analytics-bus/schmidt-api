##
# Database and Flask app setup.
##

# Third party libraries
from pony import orm
from pony.orm.core import Database

# Local libraries
from .config import conn_params

# Setup for Pony ORM ##########################################################
# Bind database object to the target database (postgres assumed) using the
# dbconfig.ini and command line-derived configuration arguments.
db: Database = orm.Database()
db.bind(
    provider="postgres",
    user=conn_params["username"],
    password=conn_params["password"],
    host=conn_params["host"],
    database=conn_params["database"],
)
