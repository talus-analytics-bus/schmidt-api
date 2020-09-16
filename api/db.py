##
# # API and database setup file.
##

# Standard libraries

# Third party libraries
from flask import Flask
from flask_restplus import Api
from flask_cors import CORS

# Local libraries
from config import Config
from .db_models import db


# Setup for Flask API Server ###################################################

# Load Flask app
app = Flask(__name__)

# Allow Cross Origin Requests
CORS(app)

# Load Flask API
api = Api(app, version='0.1')

app.config['NAME'] = 'Pandemic Respository (Schmidt) API'
app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
app.config['SWAGGER_UI_REQUEST_DURATION'] = True
app.config['RESTPLUS_MASK_SWAGGER'] = False
app.config['pg_config'] = {}

# Import standard config class to configure the database.
appconfig = Config('config.ini')


# Setup for Pony ORM ###########################################################

# Bind database object to the target database (postgres assumed) using the
# dbconfig.ini and command line-derived configuration arguments.
db.bind(
    provider='postgres',
    user=appconfig.db['username'],
    password=appconfig.db['password'],
    host=appconfig.db['host'],
    database=appconfig.db['database']
)

# Generate mapping (create tables if they don't already exist) to store data.
# Change this argument to True if the tables you need don't yet exist.
db.generate_mapping(create_tables=True)
