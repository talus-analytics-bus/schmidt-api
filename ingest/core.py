import os
import sys
from typing import Set

from application import db
from api import schema
from . import SchmidtPlugin
from . import util
from cli.update import preview


def main(stop_if_no_new_or_del: bool = True):
    """Run main data ingest.

    Args:
        skip_if_no_new (bool, optional): Skip ingest if no new records
        detected. Defaults to True.

    """

    # constants
    # airtable base ID (non-sensitive)
    base_id = os.environ["AIRTABLE_BASE_ID"]

    # initialize db connection and plugin for ingest
    plugin = SchmidtPlugin()

    # update core policy data, if appropriate
    client = plugin.load_client(base_id)

    # update various entity instances
    new_item_ids: Set[int] = set()
    del_item_ids: Set[int] = set()
    new_item_ids, del_item_ids = client.get_new_and_del_item_ids()
    no_new_or_del: bool = (len(new_item_ids) + len(del_item_ids)) == 0
    if no_new_or_del and stop_if_no_new_or_del:
        print("No new items, halting ingest")
        sys.exit(0)
    else:
        print("Found new or deleted items, continuing ingest")

    # write Excel of deleted items if any
    if len(del_item_ids) > 0:
        write_items_xlsx(del_item_ids, "del")

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

    # write Excel of new items if any
    if len(new_item_ids) > 0:
        write_items_xlsx(new_item_ids, "new")

    # exit
    sys.exit(0)


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
