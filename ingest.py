"""Run data ingest application"""
# standard modules
from os import sys

# local modules
from api import schema
from api import db
from ingest import SchmidtPlugin

if __name__ == "__main__":
    # constants
    # airtable base ID (non-sensitive)
    airtable_key = 'appLd31oBE5L3Q3cs'

    # initialize db connection and plugin for ingest
    plugin = SchmidtPlugin()

    # update core policy data, if appropriate
    client = plugin.load_client(airtable_key)

    # load and process metadata from data dictionary(ies)
    client.update_metadata(db)
    client.update_items(db)
    client.update_authors(db)
    client.update_funders(db)

    # exit
    sys.exit(0)
