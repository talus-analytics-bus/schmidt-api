"""Define project-specific methods for data ingestion."""
# standard modules
from pony.orm.core import Database
from api.db_models.models import (
    CovidTag,
    CovidTopic,
    FieldRelationship,
    File,
    GeoSpecificity,
    Item,
    KeyTopic,
    Metadata,
    Optionset,
    Tag,
)
import os
from io import BytesIO
from os import sys
from datetime import datetime
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Set, Type, Union

# 3rd party modules
import boto3
import pdfplumber
from alive_progress import alive_bar
from pony.orm import db_session, commit, select
import pprint

# local modules
from .sources import AirtableSource
from .util import (
    upsert,
    download_file,
    iterable,
    get_s3_bucket_keys,
    set_date_types,
    S3_BUCKET_NAME,
)
import pandas as pd

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)

# list tags that use the Tag entity
# TODO define tag fields dynamically in Metadata
OPTIONSET_CLASS_BY_FIELD: Dict[str, Any] = {
    "key_topics": KeyTopic,
    "tags": Tag,
    "covid_topics": CovidTopic,
    "covid_tags": CovidTag,
    "geo_specificity": GeoSpecificity,
    "field_relationship": FieldRelationship,
}

# define exported classes
__all__ = ["SchmidtPlugin"]


class IngestPlugin:
    """Basic data ingest plugin.

    Parameters
    ----------
    name : str
        Name of project.

    Attributes
    ----------
    name

    """

    def __init__(self, name: str):
        self.name = name


class SchmidtPlugin(IngestPlugin):
    """Ingest Schmidt data and write to local database"""

    def __init__(self):
        return None

    def load_client(self, base_key):
        """Load client to access Airtable. NOTE: You must set environment
        variable `AIRTABLE_API_KEY` to use this.

        Returns
        -------
        self

        """

        # get API key from env var
        api_key = os.environ.get("AIRTABLE_API_KEY")

        if api_key is None:
            print(
                "\n\n[FATAL ERROR] No Airtable API key found. Please define it as an environment variable (e.g., `export AIRTABLE_API_KEY=[key]`)"
            )
            sys.exit(1)

        # get Airtable client for specified base
        client = AirtableSource(
            name="Airtable",
            base_key=base_key,
            api_key=os.environ.get("AIRTABLE_API_KEY"),
        )
        self.client = client
        return self

    @db_session
    def do_qaqc(self):
        # qa/qc authors
        self.__qaqc_authors()

    @db_session
    def update_metadata(self, db, delete_old: bool = False):
        """
        Load data dictionaries from Airtable, and parse and write their
        contents to the database.

        """
        # load data dictionaries from Airtable and store following the
        # pattern `self.dd_[entity_name]`
        print("Updating metadata...")
        self.dd_item = self.client.worksheet(
            name="Field definitions"
        ).as_dataframe()

        # set entity type
        self.dd_item["Entity name"] = "Item"

        # collate data dictionary dataframes into one
        self.dd_all = pd.concat([self.dd_item])

        # if requested, delete first
        if delete_old:
            db.Metadata.select().delete()
            commit()

        # process data dictionary dataframes into instances for database
        meta_row: dict = None
        for meta_row in self.dd_all.to_dict(orient="records"):
            # skip rows that lack a database field name
            db_field_name: str = meta_row.get("Database field name")
            if db_field_name in (
                None,
                "",
            ):
                continue

            # define "get" field values for datum
            upsert_get: dict = {
                "field": db_field_name,
                "entity_name": meta_row["Entity name"],
                "linked_entity_name": meta_row["Database entity"],
            }

            # define fields to set
            upsert_set: dict = {
                "order": meta_row["Order"],
                "source_name": meta_row["Field"],
                "display_name": meta_row["Display name"],
                "colgroup": meta_row["Category"],
                "definition": meta_row["Definition"],
                "possible_values": meta_row["Possible values"],
                "export": meta_row["Export?"],
                "type": meta_row["Type"],
                "notes": "",  # NOT IMPLEMENTED,
            }

            # upsert instances to database
            upsert(cls=db.Metadata, get=upsert_get, set=upsert_set)
        print("Metadata updated.")
        return self

    @db_session
    def update_items(self, db, delete_old=False):
        """Get Items instance data from Airtable, parse into database records,
        and write to database.

        """

        # limit number of items?
        MAX_ITEMS: int = os.environ.get("MAX_ITEMS")

        print("\nUpdating items...")
        self.items = self.client.worksheet(
            name="Schmidt dataset"
        ).as_dataframe(max_records=MAX_ITEMS)

        # list tags that are linked entities to be tagged after the fact
        linked_fields = ("funders",)

        # list tags that are for internal use only and should be skipped
        internal_fields = (
            "assigned_to_for_final_review",
            "assigned_to_initials",
            "reviewer_initials",
        )

        # get database fields for items to write
        metadata: List[Metadata] = select(
            i
            for i in Metadata
            if i.entity_name == "Item"
            and i.field not in linked_fields
            and i.field not in internal_fields
        )

        # define fields to skip over that are handled specially
        special_fields: Set[str] = {"items"}

        # store link items
        linked_items_by_id: DefaultDict[str, set] = defaultdict(set)

        # store upserted items, and delete any in the db that aren't on the
        # list when ingest is complete
        all_upserted = set()

        def reject(d: dict) -> bool:
            """Return True if the item datum is acceptable to add to the
            database and False otherwise.

            Args:
                d (dict): The item datum based on the Airtable record.

            Returns:
                bool: True if the item datum is acceptable to add to the
                database and False otherwise.
            """
            desc: str = d.get("Description", "").strip()
            no_desc: bool = desc == ""
            not_ready: bool = not d.get("Final review", False)
            if no_desc or not_ready:
                return True
            return False

        # parse items into instances to write to database
        raw_item_data: dict = None
        for raw_item_data in self.items.to_dict(orient="records"):

            # reject item data if not acceptable
            if reject(raw_item_data):
                continue

            if raw_item_data["Linked Record ID"] != "":
                for source_id in raw_item_data["Linked Record ID"]:
                    linked_items_by_id[
                        raw_item_data["ID (automatically assigned)"]
                    ].add(source_id)

            get_keys = "id"
            upsert_get = dict()
            upsert_set = {"source_id": raw_item_data["source_id"]}
            upsert_optionset: DefaultDict[str, Set[str]] = defaultdict(set)

            for field_datum in metadata:
                is_linked = (
                    field_datum.linked_entity_name != field_datum.entity_name
                    or field_datum.field in special_fields
                )
                if is_linked:
                    continue
                else:
                    key = field_datum.field
                    name = field_datum.source_name
                    if name in raw_item_data:
                        value = raw_item_data[name]
                        # parse dates
                        if field_datum.type == "date":
                            if value != "":
                                value = datetime.strptime(
                                    value, "%Y-%m-%d"
                                ).date()
                            else:
                                value = None
                        elif field_datum.type == "StrArray":
                            if value == "":
                                value = list()
                            elif type(value) == str:
                                value = value.replace("; and", ";")
                                value = value.replace("; ", ";")
                                value = value.split(";")
                        elif field_datum.type == "bool":

                            if value in ("Yes", "checked", True, "True"):
                                value = True
                            elif value in ("No", "", None, False, "False"):
                                value = False
                            else:
                                value = None
                        if key not in OPTIONSET_CLASS_BY_FIELD:
                            if key in get_keys:
                                upsert_get[key] = value
                            else:
                                upsert_set[key] = value
                        else:
                            v: str = None
                            for v in value:
                                upsert_optionset[key].add(v)

            _action, upserted = upsert(
                db.Item,
                get=upsert_get,
                set=upsert_set,
            )

            # add upserted item to master set
            all_upserted.add(upserted)

            # set item's optionset values
            optionset_field: str = None
            for optionset_field in upsert_optionset:
                OptionsetClass: Type[Optionset] = OPTIONSET_CLASS_BY_FIELD[
                    optionset_field
                ]
                upsert_optionset_field_vals = list(
                    upsert_optionset[optionset_field]
                )
                for optionset_name in upsert_optionset_field_vals:
                    _action_optionset, upserted_optionset = upsert(
                        OptionsetClass,
                        get={"name": optionset_name},
                        set=dict(),
                    )
                    commit()

                    getattr(upserted, optionset_field).add(upserted_optionset)
                    commit()

        # Link related items
        link_rel_items: bool = MAX_ITEMS is None
        if link_rel_items:
            for a_id, b_ids in linked_items_by_id.items():
                a = db.Item[a_id]
                for b_id in b_ids:
                    b = db.Item.get(source_id=b_id)
                    a.items.add(b)
                commit()

        # add date type
        define_date_types(db)

        # Delete old items from the db
        to_delete = select(i for i in db.Item if i not in all_upserted)
        to_delete.delete()
        commit()

        print("Items updated.")
        return self

    @db_session
    def update_item_search_text(self, db):
        """Set item `search_text` column to contain all attributes that
        should be searched.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        print("\nUpdating aggregated item search text...")
        fields_str = (
            "type_of_record",
            "title",
            "description",
            "link",
            "sub_organizations",
        )
        fields_optionset = (
            "key_topics",
            "tags",
            "covid_topics",
            "covid_tags",
            "field_relationship",
            "geo_specificity",
        )
        linked_fields_str = (
            "authors.authoring_organization",
            "funders.name",
            "events.name",
            "files.scraped_text",
            "related_files.scraped_text",
            "authors.acronym",
        )
        all_items = select(i for i in db.Item)

        # add plain fields on the Item entity, like name and desc
        with alive_bar(all_items.count(), title="Updating search text") as bar:
            for i in all_items:
                bar()
                search_text = ""
                file_search_text = ""
                for field in fields_str:
                    value = getattr(i, field)
                    if type(value) == list:
                        value = " ".join(value)
                    search_text += value + " "
                for field in fields_optionset:
                    optionset_values: List[Optionset] = getattr(i, field)
                    if optionset_values is not None:
                        optionset_names = select(
                            tag.name for tag in optionset_values
                        )[:][:]
                        search_text += " - ".join(optionset_names) + " "

                # add linked fields from related entities like authors
                for field in linked_fields_str:
                    arr = field.split(".")
                    entity_name = arr[0]
                    linked_field = arr[1]
                    linked_values = select(
                        getattr(linked_entity, linked_field)
                        for linked_entity in getattr(i, entity_name)
                        if getattr(linked_entity, linked_field) is not None
                    )[:][:]
                    str_to_concat = " - ".join(linked_values) + " "
                    if linked_field == "scraped_text":
                        str_to_concat = str_to_concat[0:100000]
                        file_search_text += str_to_concat
                    else:
                        search_text += str_to_concat

                # update search text
                i.search_text = search_text.lower()
                i.file_search_text = file_search_text.lower()
                commit()
        print("Complete.")

    @db_session
    def clear_records(self, db):
        entity_classes = (
            db.Item,
            db.Funder,
            db.Author,
            db.Event,
        )
        print("\n\nDeleting existing records (except files)...")
        for entity_class in entity_classes:
            entity_class.select().delete()
            commit()
        print("Deleted.\n")

    @db_session
    def clean_optionset_vals(self, db):
        """Delete optionset value instances that aren't used"""
        print("\nCleaning optionset values...")

        # delete tags that are not used by any items
        OptionsetClass: Type[Optionset] = None
        for OptionsetClass in OPTIONSET_CLASS_BY_FIELD.values():
            OptionsetClass.delete_unused()
            commit()
        print("Optionset values cleaned.")

    @db_session
    def update_authors(self, db):
        """
        Update authors based on the lookup table. There can be multiple
        authors for a single item.

        """
        # update authors
        print("\nUpdating authors...")

        # load list of authors from lookup table, if not yet loaded
        if not hasattr(self, "author"):
            self.__load_authors()

        # define foreign key field
        fkey_field = "Item IDs"

        # for each author
        for d in self.author.to_dict(orient="records"):
            # skip if no name
            if (
                d["Publishing Organization Name"] is None
                or d["Publishing Organization Name"] == ""
            ):
                continue

            # get items this refers to
            for fkey in d[fkey_field]:
                item = db.Item.get(id=fkey)
                if item is None:
                    continue

                # upsert author instance
                upsert_get = {
                    "id": d["ID (automatically assigned)"],
                }
                upsert_set = {
                    "authoring_organization": d[
                        "Publishing Organization Name"
                    ],
                    "type_of_authoring_organization": d[
                        "Type of Publishing Organization"
                    ],
                    "international_national": d[
                        "Publishing Org- International/National"
                    ],
                    "acronym": d["Abbreviations lookup"],
                }
                if d["Country name"] != "":
                    upsert_set["if_national_country_of_authoring_org"] = d[
                        "Country name"
                    ][0]
                if d["ISO2"] != "":
                    upsert_set["if_national_iso2_of_authoring_org"] = d[
                        "ISO2"
                    ][0]

                # upsert implied author
                action, upserted = upsert(
                    db.Author, get=upsert_get, set=upsert_set
                )

                # add author to item's author list
                item.authors.add(upserted)
                commit()

        # Remove any authors that have no items
        select(i for i in db.Author if len(i.items) == 0).delete()
        commit()
        print("Authors updated.")
        return self

    def __load_authors(self):
        """Load authors from Airtable."""
        self.author = self.client.worksheet(
            name="Lookup: Publishing Org"
        ).as_dataframe()

    @db_session
    def update_funders(self, db):
        """Update funders based on the lookup table data.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """

        # update funders
        print("\nUpdating funders...")

        # get list of funders from lookup table
        self.funder = self.client.worksheet(
            name="Lookup: Funder"
        ).as_dataframe()

        # define foreign key field
        fkey_field = "Item IDs"

        # for each funder
        for d in self.funder.to_dict(orient="records"):

            # get items this refers to
            for fkey in d[fkey_field]:
                item = db.Item.get(id=fkey)
                if item is None:
                    continue

                # upsert funder instance
                upsert_get = {
                    "id": d["ID (automatically assigned)"],
                }
                upsert_set = {"name": d["Funder"]}

                # upsert implied funder
                action, upserted = upsert(
                    db.Funder, get=upsert_get, set=upsert_set
                )

                # add funder to item's funder list
                item.funders.add(upserted)
                commit()

        print("Funders updated.")
        return self

    @db_session
    def update_events(self, db):
        """Update events based on the items data and write to database,
        linking to items as appropriate.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        # throw error if items data not loaded
        if not hasattr(self, "items"):
            print("[FATAL ERROR] Please `update_items` before other entities.")
            sys.exit(1)

        # update authors
        print("\nUpdating events...")

        # for each item
        for d in self.items.to_dict(orient="records"):
            event_defined = d.get("Event category") not in (None, "")
            item = db.Item.get(id=int(d["ID (automatically assigned)"]))
            if item is None:
                continue
            item_defined = item is not None
            if not event_defined or not item_defined:
                continue
            else:
                event_list = d["Event category"]
                if not iterable(event_list):
                    event_list = list(set([event_list]))
                all_upserted = list()
                for event in event_list:
                    upsert_get = {
                        "name": event,
                    }
                    upsert_set = {"master_id": event}

                    # upsert implied author
                    action, upserted = upsert(
                        db.Event, get=upsert_get, set=upsert_set
                    )
                    all_upserted.append(upserted)

                # link item to author
                item.events = all_upserted

        print("Events updated.")
        return self

    @db_session
    def update_files(self, db: Database, do_scrape_text: bool = True):
        """Update files based on the items data and write to database,
        linking to items as appropriate.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        # throw error if items data not loaded
        if not hasattr(self, "items"):
            print("[FATAL ERROR] Please `update_items` before other entities.")
            sys.exit(1)

        # get all s3 bucket keys
        self.s3_bucket_keys = get_s3_bucket_keys(s3_bucket_name=S3_BUCKET_NAME)

        self.__upsert_files_from_items(
            db, "PDF Attachments", "files", do_scrape_text
        )
        self.__upsert_files_from_items(
            db, "Related document(s)", "related_files", do_scrape_text
        )

        # assign s3 permalinks
        prod_api_url: str = "https://api.healthsecuritynet.org/get/file/"
        for file in select(i for i in db.File):
            file.s3_permalink = (
                f"""{prod_api_url}"""
                f"""{file.filename.replace('?', '')}?id={file.id}"""
            )
            commit()

        # delete file records and S3 files if they are not to be shown in
        # the site
        files_to_delete = db.File.select().filter(
            lambda x: x.exclude_from_site
        )
        n_files_to_delete = files_to_delete.count()

        # define s3 resource client
        s3_resource = boto3.resource("s3")

        n_deleted = 0
        with alive_bar(
            n_files_to_delete,
            title='Deleting files that have been marked "exclude" since '
            "last update",
        ) as bar:
            for file in files_to_delete:
                bar()
                # delete s3 file and thumb, if it exists
                s3_filename = file.s3_filename
                s3_resource.Object(S3_BUCKET_NAME, s3_filename).delete()
                if file.s3_thumbnail_permalink is not None:
                    s3_resource.Object(
                        S3_BUCKET_NAME, s3_filename + "_thumb"
                    ).delete()
                file.delete()
                commit()
                n_deleted += 1

        print(
            "Deleted "
            + str(n_deleted)
            + " files (plus thumbnails) from database and S3."
        )
        print("Files updated.")
        return self

    def __upsert_files_from_items(
        self,
        db: Database,
        airtable_pdf_field: str,
        db_item_field: str,
        do_scrape_text: bool,
    ):
        # define s3 client
        s3: Any = boto3.client("s3")

        item_dicts: List[dict] = self.items.to_dict(orient="records")
        n_item_dicts: int = len(item_dicts)
        cur_item_dict: int = 0

        # overwrite PDFs already in S3?
        OVERWRITE_PDFS: bool = (
            os.environ.get("OVERWRITE_PDFS", "false") == "true"
        )

        # define progress bar for item update cycle
        print("")
        with alive_bar(
            n_item_dicts,
            title="Updating files for field `" + db_item_field + "`",
        ) as bar:
            # for each item
            for d in item_dicts:
                bar()
                cur_item_dict += 1

                is_file_defined: bool = d[airtable_pdf_field] != ""
                item: Item = Item.get(id=int(d["ID (automatically assigned)"]))
                is_item_defined: bool = item is not None
                if (
                    not is_file_defined
                    or not is_item_defined
                    or item.exclude_pdf_from_site
                ):
                    continue

                file_list: List[str] = d[airtable_pdf_field]
                if not iterable(file_list):
                    file_list = list(set([file_list]))
                upserted_files: List[File] = list()
                for file in file_list:
                    upsert_get: dict = {
                        "s3_filename": file["id"],
                    }
                    has_thumbnails: bool = "thumbnails" in file
                    source_thumb_permalink: str = (
                        file["thumbnails"]["large"]["url"]
                        if has_thumbnails
                        else None
                    )
                    upsert_set: dict = {
                        "source_permalink": file["url"],
                        "filename": file["filename"],
                        "s3_permalink": None,
                        "exclude_from_site": item.exclude_pdf_from_site,
                        "mime_type": file["type"],
                        "source_thumbnail_permalink": source_thumb_permalink,
                        "s3_thumbnail_permalink": None,
                        "num_bytes": file["size"],
                    }

                    files_to_check: List[dict] = [
                        {
                            "file_key": file["id"],
                            "file_url": file["url"],
                            "field": "s3_permalink",
                            "scrape": True,
                        },
                        {
                            "file_key": file["id"] + "_thumb",
                            "file_url": source_thumb_permalink,
                            "field": "s3_thumbnail_permalink",
                            "scrape": False,
                        },
                    ]

                    file_to_check: dict = None
                    for file_to_check in files_to_check:
                        file_key: str = file_to_check["file_key"]
                        file_url: str = file_to_check["file_url"]
                        if file_url is None:
                            continue
                        file_should_be_scraped: bool = file_to_check["scrape"]
                        file_already_in_s3 = file_key in self.s3_bucket_keys

                        if (not file_already_in_s3) or OVERWRITE_PDFS:
                            # add file to S3 if not already there
                            file = download_file(
                                file_url,
                                file_key,
                                None,
                                as_object=True,
                            )

                            if file is None:
                                continue

                            # scrape PDF text unless file is not a PDF or
                            # unless it is not flagged as `scrape`
                            if file_should_be_scraped and do_scrape_text:
                                try:
                                    pdf = pdfplumber.open(BytesIO(file))

                                    # store scraped text
                                    scraped_text: str = ""

                                    # only scrape up to a set
                                    # limit of characters
                                    max_chars: int = 1000
                                    for curpage in pdf.pages:
                                        if len(scraped_text) < max_chars:
                                            page_scraped_text = (
                                                curpage.extract_text()
                                            )
                                            if page_scraped_text is not None:
                                                scraped_text += (
                                                    page_scraped_text
                                                )
                                    # trim string
                                    if len(scraped_text) > max_chars:
                                        scraped_text = scraped_text[
                                            0:max_chars
                                        ]

                                    upsert_set[
                                        "scraped_text"
                                    ] = scraped_text.replace("\x00", "")
                                except Exception:
                                    pass

                            if not file_already_in_s3:
                                # add file to s3
                                s3.put_object(
                                    Body=file,
                                    Bucket=S3_BUCKET_NAME,
                                    Key=file_key,
                                )

                                # set to public
                                s3.put_object_acl(
                                    ACL="public-read",
                                    Bucket=S3_BUCKET_NAME,
                                    Key=file_key,
                                )

                                field = file_to_check["field"]
                                upsert_set[field] = (
                                    "https://schmidt-storage"
                                    ".s3-us-west-1.amazonaws.com/" + file_key
                                )

                    # upsert files
                    upsert_set["has_thumb"] = (
                        upsert_set["source_thumbnail_permalink"] is not None
                    )
                    _action, upserted = upsert(
                        db.File, get=upsert_get, set=upsert_set
                    )
                    commit()

                    # add to list of files for item
                    upserted_files.append(upserted)

                # link item to files
                setattr(item, db_item_field, upserted_files)

    @db_session
    def update_glossary(self, db, delete_old):
        """Create glossary instances, deleting existing."""
        print("\n[2b] Ingesting glossary from Airtable...")
        self.glossary_dicts = (
            self.client.worksheet(name="Glossary (work in progress)")
            .as_dataframe()
            .to_dict(orient="records")
        )

        if delete_old:
            print("Deleting existing glossary records...")
            orig_records = db.Glossary.select()
            n_deleted = orig_records.count()
            orig_records.delete()
            commit()
            print("Deleted.")

        # get glossary terms from Airtable
        n_inserted = 0
        n_updated = 0
        with alive_bar(
            len(self.glossary_dicts), title="Ingesting glossary records"
        ) as bar:
            row: dict = None
            for row in self.glossary_dicts:
                bar()
                show: Union[str, bool] = row.get(
                    "Internal: Show in Excel download?"
                )
                if show is not True:
                    continue
                new_record = dict(
                    colname=row.get("Category"),
                    term=row.get("Name"),
                    definition=row.get("Definition (in progress)"),
                )
                action, instance = upsert(
                    db.Glossary,
                    new_record,
                    dict(),
                )

                if action == "update":
                    n_updated += 1
                elif action == "insert":
                    n_inserted += 1

        commit()
        print("Inserted: " + str(n_inserted))
        print("Updated: " + str(n_updated))
        print("Deleted: " + str(n_deleted))

    def check(self, data):
        """Perform QA/QC on the data and return a report.
        TODO

        Parameters
        ----------
        data : type
            Description of parameter `data`.

        Returns
        -------
        type
            Description of returned object.

        """
        print("\n\n[1] Performing QA/QC on dataset...")

        valid = True

        # unique primary key `id`
        dupes = data.duplicated(["Unique ID"])
        if dupes.any():
            print("\nDetected duplicate unique IDs:")
            print(data[dupes == True].loc[:, "Unique ID"])  # noqa: E712
            valid = False

        # dates formatted well
        # TODO

        return valid

    def __qaqc_authors(self) -> None:
        """Performs assertions for authors data frame.

        Args:
            author_df (pd.DataFrame): The authors data frame.
        """

        if not hasattr(self, "author"):
            self.__load_authors()

        # detect authors without links to items
        no_links_which_df: pd.Series = (
            self.author["Link to Schmidt dataset"] == ""
        )
        no_links_names_df: pd.Series = self.author.loc[
            no_links_which_df,
            "Publishing Organization Name",
        ]
        no_links_names: Set[str] = list(set(no_links_names_df.tolist()))
        if len(no_links_names) > 0:
            no_links_names.sort()
            print(
                "\nThe following publishing organizations have no items and "
                "will not be imported:"
            )
            name: str = None
            for name in no_links_names:
                print("    " + name)
            print("")

            # update df to remove no links rows
            self.author = self.author.loc[~no_links_which_df, :]

        # raise exception if authors have non-unique names
        dupes_which: pd.Series = self.author[
            "Publishing Organization Name"
        ].duplicated()
        dupe_names_df: pd.Series = self.author.loc[
            dupes_which, "Publishing Organization Name"
        ]
        dupe_names: List[str] = list(set(dupe_names_df.tolist()))
        if len(dupe_names) > 0:
            print(
                "\nThe following publishing organization names are used more "
                "than once. Please ensure all have unique names."
            )
            dupe_names_formatted: List[str] = [
                v if v != "" else "[blank]" for v in dupe_names
            ]
            name: str = None
            for name in dupe_names_formatted:
                print("\t" + name)
            raise ValueError("All publishing org. names must be unique.")
