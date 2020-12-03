"""Define project-specific methods for data ingestion."""
# standard modules
import os
import pytz
import time
from io import BytesIO
from os import sys
from datetime import date, datetime, timedelta
from collections import defaultdict

# 3rd party modules
import boto3
import pdfplumber
from progress.bar import Bar
from pony.orm import db_session, commit, get, select, delete, StrArray
from pony.orm.core import CacheIndexError, ObjectNotFound
import pprint

# local modules
from .sources import AirtableSource
from .util import upsert, download_file, bcolors, nyt_caseload_csv_to_dict, \
    jhu_caseload_csv_to_dict, find_all, iterable, get_s3_bucket_keys, \
    S3_BUCKET_NAME
import pandas as pd

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)

# define exported classes
__all__ = ['SchmidtPlugin']


class IngestPlugin():
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
    """Ingest Schmidt data and write to local database


    """

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
        api_key = os.environ.get('AIRTABLE_API_KEY')

        if api_key is None:
            print('\n\n[FATAL ERROR] No Airtable API key found. Please define it as an environment variable (e.g., `export AIRTABLE_API_KEY=[key]`)')
            sys.exit(1)

        # get Airtable client for specified base
        client = AirtableSource(
            name='Airtable',
            base_key=base_key,
            api_key=os.environ.get('AIRTABLE_API_KEY')
        )
        self.client = client
        return self

    @db_session
    def update_metadata(self, db):
        """Load data dictionaries from Airtable, and parse and write their
        contents to the database.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        # load data dictionaries from Airtable and store following the
        # pattern `self.dd_[entity_name]`
        print('Updating metadata...')
        self.dd_item = self.client \
            .worksheet(name='Field definitions') \
            .as_dataframe()

        # set entity type
        self.dd_item['Entity name'] = 'Item'

        # collate data dictionary dataframes into one
        self.dd_all = pd.concat(
            [
                self.dd_item
            ]
        )

        # process data dictionary dataframes into instances for database
        to_upsert = list()
        for d in self.dd_all.to_dict(orient='records'):
            upsert_set = {
                'order': d['Order'],
                'source_name': d['Field'],
                'display_name': d['Display name'],
                'colgroup': d['Category'],
                'definition': d['Definition'],
                'possible_values': d['Possible values'],
                'export': d['Export?'],
                'type': d['Type'],
                'notes': '',  # NOT IMPLEMENTED,
            }

            # define "get" field values for datum
            upsert_get = {
                'field': d['Database field name'],
                'entity_name': d['Entity name'],
                'linked_entity_name': d['Database entity'],
            }

            # write instances to database
            action, upserted = upsert(
                cls=db.Metadata,
                get=upsert_get,
                set=upsert_set
            )
        print('Metadata updated.')
        return self

    @db_session
    def update_items(self, db, delete_old=False):
        """Get Items instance data from Airtable, parse into database records,
        and write to database.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        print('\nUpdating items...')
        self.item = self.client \
            .worksheet(name='Schmidt dataset') \
            .as_dataframe()

        # list tags that use the Tag entity
        tag_fields = ('key_topics', 'tags')

        # list tags that are linked entities to be tagged after the fact
        linked_fields = ('funders',)

        # list tags that are for internal use only and should be skipped
        internal_fields = (
            'assigned_to_for_final_review',
            'assigned_to_initials',
            'reviewer_initials',
        )

        # get database fields for items to write
        field_data = select(
            i for i in db.Metadata
            if i.entity_name == 'Item'
            and i.field not in linked_fields
            and i.field not in internal_fields
        )

        # store link items
        linked_items_by_id = defaultdict(set)

        # store upserted items, and delete any in the db that aren't on the
        # list when ingest is complete
        all_upserted = set()

        # parse items into instances to write to database
        item_dicts = self.item.to_dict(orient="records")
        for d in self.item.to_dict(orient="records"):

            if d['Linked Record ID'] != '':
                for source_id in d['Linked Record ID']:
                    linked_items_by_id[
                        d['ID (automatically assigned)']
                    ].add(source_id)

            get_keys = ('id')
            upsert_get = dict()
            upsert_set = {'source_id': d['source_id']}
            upsert_tag = dict()

            for field_datum in field_data:
                is_linked = field_datum.linked_entity_name != field_datum.entity_name
                if is_linked:
                    continue
                else:
                    key = field_datum.field
                    name = field_datum.source_name
                    if name in d:
                        value = d[name]
                        # parse dates
                        if field_datum.type == 'date':
                            if value != '':
                                value = datetime.strptime(
                                    value, '%Y-%m-%d').date()
                            else:
                                value = None
                        elif field_datum.type == 'StrArray':
                            if value == '':
                                value = list()
                            elif type(value) == str:
                                value = value.replace('; and', ';')
                                value = value.replace('; ', ';')
                                value = value.split(';')
                        elif field_datum.type == 'bool':

                            if value in ('Yes', 'checked', True, 'True'):
                                value = True
                            elif value in ('No', '', None, False, 'False'):
                                value = False
                            else:
                                value = None
                        if key not in tag_fields:
                            if key in get_keys:
                                upsert_get[key] = value
                            else:
                                upsert_set[key] = value
                        else:
                            upsert_tag[key] = value
            action, upserted = upsert(
                db.Item,
                get=upsert_get,
                set=upsert_set,
            )

            # add upserted item to master set
            all_upserted.add(upserted)

            # clear tags
            upserted.tags = list()
            upserted.key_topics = list()

            # clear authors
            upserted.authors = list()
            commit()

            # assign all tag field keys here from upsert_set
            for field in upsert_tag:
                upsert_tag_field_vals = upsert_tag[field] if \
                    iterable(upsert_tag[field]) else [upsert_tag[field]]
                for tag_name in upsert_tag_field_vals:
                    action_tag, upserted_tag = upsert(
                        db.Tag,
                        get={
                            'name': tag_name,
                            'field': field
                        },
                        set=dict(),
                    )
                    getattr(upserted, field).add(upserted_tag)
                    commit()

        # Link related items
        for a_id, b_ids in linked_items_by_id.items():
            a = db.Item[a_id]
            for b_id in b_ids:
                b = db.Item.get(source_id=b_id)
                a.items.add(b)
            commit()

        # Delete old items from the db
        to_delete = select(i for i in db.Item if i not in all_upserted)
        to_delete.delete()
        commit()

        print('Items updated.')
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
        print('\nUpdating aggregated item search text...')
        fields_str = (
            'type_of_record',
            'title',
            'description',
            'link',
            'sub_organizations',
        )
        fields_tag = (
            'key_topics',
            'tags',
        )
        linked_fields_str = (
            'authors.authoring_organization',
            'funders.name',
            'events.name',
            'files.scraped_text',
            'authors.acronym',
        )
        all_items = select(i for i in db.Item)

        # add plain fields on the Item entity, like name and desc
        bar = Bar('Updating search text', max=all_items.count())
        for i in all_items:
            bar.next()
            search_text = ''
            file_search_text = ''
            for field in fields_str:
                value = getattr(i, field)
                if type(value) == list:
                    value = " ".join(value)
                search_text += value + ' '
            for field in fields_tag:
                tag_names = select(
                    tag.name
                    for tag in getattr(i, field)
                )[:][:]
                search_text += " - ".join(tag_names) + ' '

            # add linked fields from related entities like authors
            for field in linked_fields_str:
                arr = field.split('.')
                entity_name = arr[0]
                linked_field = arr[1]
                linked_values = select(
                    getattr(linked_entity, linked_field)
                    for linked_entity in getattr(i, entity_name)
                    if getattr(linked_entity, linked_field) is not None
                )[:][:]
                str_to_concat = " - ".join(linked_values) + ' '
                if linked_field == 'scraped_text':
                    str_to_concat = str_to_concat[0:100000]
                    file_search_text += str_to_concat
                else:
                    search_text += str_to_concat

            # update search text
            i.search_text = search_text.lower()
            i.file_search_text = file_search_text.lower()
            commit()
        bar.finish()
        print('Complete.')

    @db_session
    def clear_records(self, db):
        entity_classes = (
            db.Item,
            db.Funder,
            db.Author,
            db.Event,
        )
        print('\n\nDeleting existing records (except files)...')
        for entity_class in entity_classes:
            entity_class.select().delete()
            commit()
        print('Deleted.\n')

    @db_session
    def clean_tags(self, db):
        """Delete tag instances that aren't used

        """
        print('\nDeleting unused tags from database...')

        # delete tags that are not used by any items
        delete_tags = select(
            i for i in db.Tag
            if len(i._key_topics) == 0
            and len(i._tags) == 0
        )
        delete_tags.delete()
        commit()
        print('Tags cleaned.')

    @db_session
    def update_authors(self, db):
        """Update authors based on the lookup table There can be multiple
        authors for a single item.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        # update authors
        print('\nUpdating authors...')

        # get list of authors from lookup table
        self.author = self.client \
            .worksheet(name='Lookup: Publishing Org') \
            .as_dataframe()

        # define foreign key field
        fkey_field = 'Item IDs'

        # for each author
        for d in self.author.to_dict(orient='records'):
            # skip if no name
            if d['Publishing Organization Name'] is None or \
                    d['Publishing Organization Name'] == '':
                continue

            # get items this refers to
            for fkey in d[fkey_field]:
                item = db.Item.get(id=fkey)

                # upsert author instance
                upsert_get = {
                    'id': d['ID (automatically assigned)'],
                }
                upsert_set = {
                    'authoring_organization': d['Publishing Organization Name'],
                    'type_of_authoring_organization': d['Type of Publishing Organization'],
                    'international_national': d['Publishing Org- International/National'],
                    'acronym': d['Abbreviations lookup'],
                }
                if d['Country name'] != '':
                    upsert_set['if_national_country_of_authoring_org'] = d['Country name'][0]
                if d['ISO2'] != '':
                    upsert_set['if_national_iso2_of_authoring_org'] = d['ISO2'][0]

                # upsert implied author
                action, upserted = upsert(
                    db.Author,
                    get=upsert_get,
                    set=upsert_set
                )

                # add author to item's author list
                item.authors.add(upserted)
                commit()

        # Remove any authors that have no items
        to_delete = select(
            i for i in db.Author
            if len(i.items) == 0
        ).delete()
        commit()
        print('Authors updated.')
        return self

    @db_session
    def update_funders(self, db):
        """Update events based on the lookup table data.

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
        print('\nUpdating funders...')

        # get list of funders from lookup table
        self.funder = self.client \
            .worksheet(name='Lookup: Funder') \
            .as_dataframe()

        # define foreign key field
        fkey_field = 'Item IDs'

        # for each funder
        for d in self.funder.to_dict(orient='records'):

            # get items this refers to
            for fkey in d[fkey_field]:
                item = db.Item.get(id=fkey)

                # upsert funder instance
                upsert_get = {
                    'id': d['ID (automatically assigned)'],
                }
                upsert_set = {
                    'name': d['Funder']
                }

                # upsert implied funder
                action, upserted = upsert(
                    db.Funder,
                    get=upsert_get,
                    set=upsert_set
                )

                # add funder to item's funder list
                item.funders.add(upserted)
                commit()

        print('Funders updated.')
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
        if not hasattr(self, 'item'):
            print('[FATAL ERROR] Please `update_items` before other entities.')
            sys.exit(1)

        # update authors
        print('\nUpdating events...')

        # for each item
        for d in self.item.to_dict(orient='records'):
            event_defined = d['Event category'] != ''
            item = db.Item[int(d['ID (automatically assigned)'])]
            item_defined = item is not None
            if not event_defined or not item_defined:
                continue
            else:
                event_list = d['Event category']
                if not iterable(event_list):
                    event_list = list(set([event_list]))
                all_upserted = list()
                for event in event_list:
                    upsert_get = {
                        'name': event,
                    }
                    upsert_set = {
                        'master_id': event
                    }

                    # upsert implied author
                    action, upserted = upsert(
                        db.Event,
                        get=upsert_get,
                        set=upsert_set
                    )
                    all_upserted.append(upserted)

                # link item to author
                item.events = all_upserted

        print('Events updated.')
        return self

    @db_session
    def update_files(self, db, scrape_text=True):
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
        if not hasattr(self, 'item'):
            print('[FATAL ERROR] Please `update_items` before other entities.')
            sys.exit(1)

        # get all s3 bucket keys
        self.s3_bucket_keys = get_s3_bucket_keys(s3_bucket_name=S3_BUCKET_NAME)

        # define s3 client
        s3 = boto3.client('s3')

        item_dicts = self.item.to_dict(orient='records')
        n_item_dicts = len(item_dicts)
        cur_item_dict = 0

        # define progress bar for item update cycle
        print('')
        bar = Bar('Updating files', max=n_item_dicts)

        # for each item
        for d in item_dicts:
            cur_item_dict = cur_item_dict + 1

            bar.next()

            file_defined = d['PDF Attachments'] != ''
            item = db.Item[int(d['ID (automatically assigned)'])]
            item_defined = item is not None
            if not file_defined or not item_defined or \
                    item.exclude_pdf_from_site:
                continue
            else:
                file_list = d['PDF Attachments']
                if not iterable(file_list):
                    file_list = list(set([file_list]))
                all_upserted = list()
                for file in file_list:
                    upsert_get = {
                        's3_filename': file['id'],
                    }
                    has_thumbnails = 'thumbnails' in file
                    source_thumbnail_permalink = \
                        file['thumbnails']['large']['url'] if has_thumbnails \
                        else None
                    upsert_set = {
                        'source_permalink': file['url'],
                        'filename': file['filename'],
                        's3_permalink': None,
                        'exclude_from_site': item.exclude_pdf_from_site,
                        'mime_type': file['type'],
                        'source_thumbnail_permalink': source_thumbnail_permalink,
                        's3_thumbnail_permalink': None,
                        'num_bytes': file['size'],
                    }

                    files_to_check = [
                        {
                            'file_key': file['id'],
                            'file_url': file['url'],
                            'field': 's3_permalink',
                            'scrape': True,
                        },
                        {
                            'file_key': file['id'] + '_thumb',
                            'file_url': source_thumbnail_permalink,
                            'field': 's3_thumbnail_permalink',
                            'scrape': False,
                        }
                    ]

                    for file_to_check in files_to_check:
                        file_key = file_to_check['file_key']
                        file_url = file_to_check['file_url']
                        if file_url is None:
                            continue
                        else:
                            scrape = file_to_check['scrape']
                            file_already_in_s3 = file_key in self.s3_bucket_keys

                            if not file_already_in_s3:
                                # add file to S3 if not already there
                                file = download_file(
                                    file_url,
                                    file_key,
                                    None,
                                    as_object=True
                                )

                                if file is not None:

                                    # scrape PDF text unless file is not a PDF or
                                    # unless it is not flagged as `scrape`
                                    if scrape and scrape_text:
                                        try:
                                            pdf = pdfplumber.open(
                                                BytesIO(file))

                                            # # for debug: get first page only
                                            # # TODO revert
                                            # first_page = pdf.pages[0]
                                            # scraped_text = first_page.extract_text()

                                            scraped_text = ''
                                            for curpage in pdf.pages:
                                                page_scraped_text = curpage.extract_text()
                                                if page_scraped_text is not None:
                                                    scraped_text += page_scraped_text
                                            upsert_set['scraped_text'] = scraped_text.replace(
                                                '\x00', '')
                                        except Exception as e:
                                            pass
                                            # print(
                                            #     'File does not appear to be PDF, skipping scraping: ' + file['filename'])

                                    if not file_already_in_s3:
                                        # add file to s3
                                        response = s3.put_object(
                                            Body=file,
                                            Bucket=S3_BUCKET_NAME,
                                            Key=file_key,
                                        )

                                        # set to public
                                        response2 = s3.put_object_acl(
                                            ACL='public-read',
                                            Bucket=S3_BUCKET_NAME,
                                            Key=file_key,
                                        )

                                        field = file_to_check['field']
                                        upsert_set[field] = 'https://schmidt-storage.s3-us-west-1.amazonaws.com/' + file_key
                                        # print('Added file to s3: ' + file_key)

                    # upsert files
                    action, upserted = upsert(
                        db.File,
                        get=upsert_get,
                        set=upsert_set
                    )
                    commit()

                    # add to list of files for item
                    all_upserted.append(upserted)

                # link item to files
                item.files = all_upserted
        bar.finish()

        # assign s3 permalinks
        api_url = 'https://schmidt-api.talusanalytics.com/get/file/'
        for file in select(i for i in db.File):
            file.s3_permalink = \
                f'''{api_url}{file.filename.replace('?', '')}?id={file.id}'''
            commit()

        # delete file records and S3 files if they are not to be shown in
        # the site
        files_to_delete = \
            db.File.select().filter(lambda x: x.exclude_from_site)
        n_files_to_delete = files_to_delete.count()

        # define s3 resource client
        s3_resource = boto3.resource('s3')

        n_deleted = 0
        bar = Bar('Deleting files that have been marked "exclude" since last update',
                  max=n_files_to_delete)
        for file in files_to_delete:
            bar.next()
            # delete s3 file and thumb, if it exists
            s3_filename = file.s3_filename
            s3_resource.Object(S3_BUCKET_NAME, s3_filename).delete()
            if file.s3_thumbnail_permalink is not None:
                s3_resource.Object(
                    S3_BUCKET_NAME, s3_filename + '_thumb'
                ).delete()
            file.delete()
            commit()
            n_deleted += 1
        bar.finish()
        print('Deleted ' + str(n_deleted) + ' files (plus thumbnails) from database and S3.')
        print('Files updated.')
        return self

    def load_metadata(self):
        """Retrieve data dictionaries from data source and store in instance.

        Returns
        -------
        self

        """

        print('\n\n[0] Connecting to Airtable and fetching tables...')
        self.client.connect()

        # show every row of data dictionary preview in terminal
        pd.set_option("display.max_rows", None, "display.max_columns", None)

        # policy data dictionary
        self.data_dictionary = self.client \
            .worksheet(name='Appendix: Policy data dictionary') \
            .as_dataframe(view='API ingest')

        # court challenges data dictionary
        self.data_dictionary_court_challenges = self.client \
            .worksheet(name='Appendix: Court challenges data dictionary') \
            .as_dataframe()

        # plan data dictionary
        self.data_dictionary_plans = self.client \
            .worksheet(name='Appendix: Plan data dictionary') \
            .as_dataframe(view='API ingest')

        # glossary
        self.glossary = self.client \
            .worksheet(name='Appendix: glossary') \
            .as_dataframe(view='API ingest')

        return self

    @db_session
    def create_metadata(self, db, full_dd):
        """Create metadata instances if they do not exist. If they do exist,
        update them.

        Parameters
        ----------
        db : type
            Description of parameter `db`.

        Returns
        -------
        type
            Description of returned object.

        """
        print('\n\n[2] Ingesting metadata from data dictionary...')
        colgroup = ''
        upserted = set()
        n_inserted = 0
        n_updated = 0
        db.Metadata.select().delete()
        commit()

        for i, d in full_dd.iterrows():
            if d['Category'] != '':
                colgroup = d['Category']
            if d['Database entity'] == '' or d['Database field name'] == '':
                continue
            metadatum_attributes = {
                'ingest_field': d['Ingest field name'],
                'display_name': d['Field'],
                'colgroup': colgroup,
                'definition': d['Definition'],
                'possible_values': d['Possible values'],
                'notes': d['Notes'] if not pd.isna(d['Notes']) else '',
                'order': d['Order'],
                'export': d['Export?'] == True,
            }
            action, instance = upsert(db.Metadata, {
                'field': d['Database field name'],
                'entity_name': d['Database entity'],
                'class_name': d['Type']
            }, metadatum_attributes)
            if action == 'update':
                n_updated += 1
            elif action == 'insert':
                n_inserted += 1
            upserted.add(instance)

        # add extra metadata not in the data dictionary
        other_metadata = [
            ({
                'field': 'loc',
                'entity_name': 'Place',
                'class_name': 'Policy'
            }, {
                'ingest_field': 'loc',
                'display_name': 'Country / Specific location',
                'colgroup': '',
                'definition': 'The location affected by the policy',
                'possible_values': 'Any text',
                'notes': '',
                'order': 0,
                'export': False,
            }), ({
                'field': 'loc',
                'entity_name': 'Place',
                'class_name': 'Plan'
            }, {
                'ingest_field': 'loc',
                'display_name': 'Country / Specific location',
                'colgroup': '',
                'definition': 'The location affected by the plan',
                'possible_values': 'Any text',
                'notes': '',
                'order': 0,
                'export': False,
            }), ({
                'field': 'source_id',
                'entity_name': 'Policy',
                'class_name': 'Policy',
            }, {
                'ingest_field': 'source_id',
                'display_name': 'Source ID',
                'colgroup': '',
                'definition': 'The unique ID of the record in the original dataset',
                'possible_values': 'Any text',
                'order': 0,
                'notes': '',
                'export': False,
            }), ({
                'field': 'source_id',
                'entity_name': 'Plan',
                'class_name': 'Plan',
            }, {
                'ingest_field': 'source_id',
                'display_name': 'Source ID',
                'colgroup': '',
                'definition': 'The unique ID of the record in the original dataset',
                'possible_values': 'Any text',
                'order': 0,
                'notes': '',
                'export': False,
            }), ({
                'field': 'source_id',
                'entity_name': 'Court_Challenge',
                'class_name': 'Court_Challenge',
            }, {
                'ingest_field': 'source_id',
                'display_name': 'Source ID',
                'colgroup': '',
                'definition': 'The unique ID of the record in the original dataset',
                'possible_values': 'Any text',
                'order': 0,
                'notes': '',
                'export': False,
            }), ({
                'field': 'date_end_actual_or_anticipated',
                'entity_name': 'Policy',
                'class_name': 'Policy',
            }, {
                'ingest_field': '',
                'display_name': 'Policy end date',
                'colgroup': '',
                'definition': 'The date on which the policy or law will (or did) end',
                'possible_values': 'Any date',
                'order': 0,
                'notes': '',
                'export': False,
            })
        ]
        for get, d in other_metadata:
            action, instance = upsert(db.Metadata, get, d)
            if action == 'update':
                n_updated += 1
            elif action == 'insert':
                n_inserted += 1
            upserted.add(instance)

        # delete all records in table but not in ingest dataset
        n_deleted = db.Metadata.delete_2(upserted)
        commit()
        print('Inserted: ' + str(n_inserted))
        print('Updated: ' + str(n_updated))
        print('Deleted: ' + str(n_deleted))

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
        print('\n\n[1] Performing QA/QC on dataset...')

        valid = True

        # unique primary key `id`
        dupes = data.duplicated(['Unique ID'])
        if dupes.any():
            print('\nDetected duplicate unique IDs:')
            print(data[dupes == True].loc[:, 'Unique ID'])
            valid = False

        # dates formatted well
        # TODO

        return valid
