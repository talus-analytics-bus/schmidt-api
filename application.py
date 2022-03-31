from api.main import app as application
from db.db import db

# load API
from api.routing.routes import api  # noqa: F401

# Generate mapping (create tables if they don't already exist) to store data.
# Change this argument to True if the tables you need don't yet exist.
db.generate_mapping(create_tables=True)


def main():
    application.run(host="localhost", port=5002, debug=True)


if __name__ == "__main__":
    main()
