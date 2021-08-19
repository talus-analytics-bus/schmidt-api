"""Run data ingest application"""
# standard modules
from os import sys

# local modules
from application import db
from ingest import SchmidtPlugin

if __name__ == "__main__":
    # constants
    # airtable base ID (non-sensitive)
    airtable_key = "appLd31oBE5L3Q3cs"

    # initialize db connection and plugin for ingest
    plugin = SchmidtPlugin()

    # update core policy data, if appropriate
    client = plugin.load_client(airtable_key)

    # update various entity instances
    client.clear_records(db)
    client.do_qaqc()
    client.update_metadata(db, delete_old=True)
    client.update_glossary(db, delete_old=True)
    client.update_items(db, delete_old=True)
    client.update_funders(db)
    client.update_authors(db)
    client.update_events(db)
    client.update_files(db, do_scrape_text=True)

    # collate search text for each item from other metadata
    client.update_item_search_text(db)

    # exit
    sys.exit(0)
