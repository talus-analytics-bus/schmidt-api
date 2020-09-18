##
# # API schema
##

# Standard libraries
import functools
import pytz
import re
import math
from datetime import datetime, timedelta, date
from io import BytesIO
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# Third party libraries
import boto3
import pprint
from pony.orm import select, db_session, raw_sql, distinct, count, StrArray
from flask import send_file

# Local libraries
from .db_models import db
from . import search

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)
s3 = boto3.client('s3')


@db_session
def get_items(
    page,
    pagesize,
):
    # get all items
    all_items = select(
        i for i in db.Item
    )

    # apply filters
    # TODO

    # apply ordering
    # TODO

    # filter items
    filtered_items = apply_filters_to_items(
        all_items,
    )

    # order items
    ordered_items = apply_ordering_to_items(filtered_items)

    # get total num items, pages, etc. for response
    total = count(ordered_items)
    items = ordered_items.page(page, pagesize=pagesize)[:][:]
    num_pages = math.ceil(total / pagesize)

    # convert to dict for response
    only = ('id', 'title', 'key_topics', 'files')
    data = [
        d.to_dict(
            only=only,
            with_collections=True,
            related_objects=True,
        ) for d in items
    ]
    return {
        'data': data,
        'page': page,
        'num_pages': num_pages,
        'pagesize': pagesize,
        'total': total,
        'num': len(data)
    }


@db_session
def get_file(id: int, get_thumb: bool):
    """Serves the file from S3 that corresponds to the File instances with
    the specified id.

    Parameters
    ----------
    id : int
        Unique ID of the File instance which corresponds to the S3 file to
        be served.

    """

    # define filename from File instance field
    file = db.File[id]
    key = file.s3_filename if not get_thumb else file.s3_filename + '_thumb'

    # retrieve file and write it to IO file object `data`
    # if the file is not found in S3, return a 404 error
    data = BytesIO()
    try:
        s3.download_fileobj('schmidt-storage', key, data)
    except Exception as e:
        print('e')
        print(e)
        return 'Document not found (404)'

    # return to start of IO stream
    data.seek(0)

    # return file with correct media type given its extension
    media_type = 'application'
    if key.endswith('.pdf'):
        media_type = 'application/pdf'

    attachment_filename = file.filename if not get_thumb else \
        file.s3_filename + '_thumb.png'
    return send_file(
        data,
        attachment_filename=attachment_filename,
        as_attachment=False
    )


@db_session
def get_search(
    page: int,
    pagesize: int,
    filters: dict = {},
    search_text: str = None,
    ordering: list = [],
    preview: bool = False,
    explain_results: bool = True,
):
    """.

    Parameters
    ----------
    id : int
        Description of parameter `id`.
    get_thumb : bool
        Description of parameter `get_thumb`.

    Returns
    -------
    type
        Description of returned object.

    """
    # get all items
    all_items = select(
        i for i in db.Item
    )

    # filter items
    filtered_items = apply_filters_to_items(
        all_items,
        filters
    )

    # order items
    ordered_items = apply_ordering_to_items(filtered_items)

    # paginate items
    items = ordered_items.page(page, pagesize=pagesize)

    # if search text not null and not preview: get matching instances by class
    other_instances = get_matching_instances(
        ordered_items,
        search_text,
        explain_results  # TODO dynamically
    )

    # if preview: return counts of items and matching instances
    data = None
    if preview:
        n_items = count(ordered_items)
        data = {
            'n_items': n_items,
            'other_instances': other_instances
        }
    else:
        # otherwise: return paginated items and details
        total = count(ordered_items)
        num_pages = math.ceil(total / pagesize)
        item_dicts = [
            d.to_dict(
                # only=only,
                with_collections=True,
                related_objects=True,
            )
            for d in items
        ]
        data = {
            'data': item_dicts,
            'page': page,
            'num_pages': num_pages,
            'pagesize': pagesize,
            'total': total,
            'num': len(item_dicts)
        }

    return data


def apply_filters_to_items(
    items,
    filters: dict = {},
    explain_results: bool = False
):
    """Given a set of filters, returns the items that match. If
    `explain_results` is True, return for each item the field(s) that matched
    and a highlighted text snippet (HTML) that shows what matched.

    Parameters
    ----------
    items : type
        Description of parameter `items`.
    filters : dict
        Description of parameter `filters`.
    explain_results : bool
        Description of parameter `explain_results`.

    Returns
    -------
    type
        Description of returned object.

    """
    tag_sets = ('key_topics',)
    for field in filters:
        allowed_values = filters[field]
        if field in tag_sets:
            items = select(
                i
                for i in items
                for j in i.key_topics
                if j.name in allowed_values
                and j.field == field
            )
        else:
            items = select(
                i
                for i in items
                if getattr(i, field) in allowed_values
            )

    return items


def apply_ordering_to_items(items, ordering: list = []):
    """Given an ordering, returns the items in that order.

    Parameters
    ----------
    items : type
        Description of parameter `items`.
    ordering : list(list)
        Description of parameter `list`.

    Returns
    -------
    type
        Description of returned object.

    """
    # TODO implement
    return items


def get_matching_instances(
    items,
    search_text: str = None,
    explain_results: bool = True
):
    """Given filters, return dict of lists of matching instances by class.

    Parameters
    ----------
    filters : dict
        Description of parameter `filters`.

    Returns
    -------
    type
        Description of returned object.

    """

    # if blank, return nothing
    if search_text is None:
        return {}
    else:
        matching_instances = {}
        # otherwise: check key fields for each entity class in turn for matches
        to_check = {
            'Author': {
                'fields': ['authoring_organization'],
                'match_type': 'exact-insensitive',  # TODO other types
                'snip_length': 1000000,
                'items_query': lambda x: lambda i: x in i.authors
            },
            'Funder': {
                'fields': ['name'],
                'match_type': 'exact-insensitive',
                'snip_length': 1000000,
                'items_query': lambda x: lambda i: x in i.funders
            },
            'Event': {
                'fields': ['name'],
                'match_type': 'exact-insensitive',
                'snip_length': 1000000,
                'items_query': lambda x: lambda i: x in i.events
            },
            'Key_Topic': {
                'match_type': 'exact-insensitive',
                'items_query': lambda x: lambda i: x in i.key_topics.name
            }
        }
        matching_instances = search.get_matching_instances(
            to_check,
            items,
            search_text,
            explain_results
        )

        # if match, return matching text and relevance score
        # collate and return all entity instances that matched in order of
        # relevance, truncating at a threshold number of them
        return matching_instances
