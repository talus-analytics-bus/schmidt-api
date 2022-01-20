import os
from typing import Set

from application import db
from api import schema
from . import SchmidtPlugin
from . import util


def main(skip_if_no_new: bool = True):
    """Run main data ingest.

    Args:
        skip_if_no_new (bool, optional): Skip ingest if no new records
        detected. Defaults to True.

    """

    # constants
    # airtable base ID (non-sensitive)
    base_id = "appLd31oBE5L3Q3cs"

    # initialize db connection and plugin for ingest
    plugin = SchmidtPlugin()

    # update core policy data, if appropriate
    client = plugin.load_client(base_id)

    # update various entity instances
    if skip_if_no_new:
        new_items, del_items = client.get_number_new_items()
        if (len(new_items) + len(del_items)) == 0:
            print("No new items, halting ingest")
            os.sys.exit(0)
        else:
            print("Found new or deleted items, continuing ingest")

    # write Excel of deleted items
    write_items_xlsx(del_items)

    client.clear_records(db)
    client.do_qaqc()
    client.update_metadata(db, delete_old=True)
    client.update_glossary(db, delete_old=True)
    client.update_items(db)
    client.update_funders(db)
    client.update_authors(db)
    client.update_events(db)
    client.update_files(db, do_scrape_text=True)

    # collate search text for each item from other metadata
    client.update_item_search_text(db)

    # write Excel of new items
    write_items_xlsx(new_items)

    # exit
    os.sys.exit(0)


def write_items_xlsx(
    item_ids: Set[int], fn_prefix: str = "", path: str = "ingest/logs/"
) -> None:
    """Writes an Excel with the given item IDs

    Args:
        item_ids (Set[int]): [description]

        fn_prefix (str, optional): Prefix of filename, which will be followed
        by '_ids' and today's date. Defaults to "".

        path (str, optional): [description]. Path to write Excel to. Defaults
        to "ingest/logs/".

    """
    fn_suffix: str = util.get_suffixed_fn("_ids", ".xlsx")
    n: int = len(item_ids)
    if n > 0:
        print(f"Getting Excel of {n} items")
        xlsx_bytes: bytes = schema.export(
            filters={"id": list(item_ids)},
        )["content"].read()
        with open(f"{path}{fn_prefix}{fn_suffix}", "wb") as f:
            f.write(xlsx_bytes)
