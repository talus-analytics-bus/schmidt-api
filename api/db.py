##
# Database and Flask app setup.
##

# Third party libraries
from flask import Flask
from flask_cors import CORS
from pony import orm
from pony.orm.core import Database

# Local libraries
from config import Config

# Setup for Flask API Server ##################################################
# Load Flask app
app = Flask(__name__)

# Allow Cross Origin Requests
CORS(app)

app.config["NAME"] = "Health Security Net API"
app.config["SWAGGER_UI_DOC_EXPANSION"] = "list"
app.config["SWAGGER_UI_REQUEST_DURATION"] = True
app.config["RESTPLUS_MASK_SWAGGER"] = False
app.config["pg_config"] = {}

# Import standard config class to configure the database.
appconfig = Config("config.ini")

# Setup for Pony ORM ##########################################################
# Bind database object to the target database (postgres assumed) using the
# dbconfig.ini and command line-derived configuration arguments.
db: Database = orm.Database()
db.bind(
    provider="postgres",
    user=appconfig.db["username"],
    password=appconfig.db["password"],
    host=appconfig.db["host"],
    database=appconfig.db["database"],
)
