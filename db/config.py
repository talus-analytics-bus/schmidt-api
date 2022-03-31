"""Configure database engine connection for SQL Alchemy"""
# standard packages
import logging

# local modules
from . import configtools

# constants
logger = logging.getLogger(__name__)

# load config and connect
conn_params = configtools.load_db_config()
# db_conn_str = (
#     f"""postgresql+psycopg2://{conn_params['username']}:"""
#     f"""{conn_params['password']}@{conn_params['host']}"""
#     f"""/{conn_params['database']}"""
# )

logger.info(
    f"Connected to database `{conn_params['database']}`"
    f" at host `{conn_params['host']}`"
)
