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
from pony.orm import select, db_session, raw_sql, distinct, count
from flask import send_file

# Local libraries
from .db_models import db
from .utils import passes_filters

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
        explain_results=False
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
            # with_collections=True,
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
        explain_results=True
    )

    # order items
    ordered_items = apply_ordering_to_items(filtered_items)

    # paginate items
    items = ordered_items.page(page, pagesize=pagesize)

    # if search text not null and not preview: get matching instances by class
    other_instances = get_matching_instances(ordered_items, search_text)

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
    # TODO implement
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


def get_matching_instances(items, search_text: str = None):
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
                'items_query': lambda x: lambda i: x in i.key_topics
            }
        }
        for class_name in to_check:
            match_type = to_check[class_name]['match_type']
            # special case: key topics
            if class_name != 'Key_Topic':
                matching_instances[class_name] = list()
                entity = getattr(db, class_name)
                matches = list()
                if match_type not in ('exact-insensitive',):
                    raise NotImplementedError(
                        'Unsupported match type: ' + match_type
                    )
                else:

                    # for each field to check, collect the matching entities into
                    # a single list
                    fields = to_check[class_name]['fields']
                    cur_search_text = search_text.lower()
                    all_matches_tmp = set()
                    for field in fields:
                        matches = select(
                            i for i in entity
                            if cur_search_text in getattr(i, field).lower()
                        )
                        all_matches_tmp = all_matches_tmp | set(matches[:][:])

                    # for each match in the list, count number of results (slow?)
                    # and get snippets showing why the instance matched
                    items_query = to_check[class_name]['items_query']
                    all_matches = list()
                    for match in all_matches_tmp:
                        # get number of results for this match
                        n_items = count(items.filter(items_query(match)))
                        d = match.to_dict(only=(['id'] + fields))
                        d['n_items'] = n_items

                        # exact-insensitive snippet
                        # TODO code for finding other types of snippets
                        # TODO score by relevance
                        # TODO add snippet length constraints
                        snippets = dict()
                        pattern = re.compile(cur_search_text, re.IGNORECASE)

                        def repl(x):
                            return '<highlight>' + x.group(0) + '</highlight>'
                        for field in fields:
                            snippets[field] = list()
                            if search_text in getattr(match, field).lower():
                                snippet = re.sub(
                                    pattern, repl, getattr(match, field))
                                snippets[field].append(snippet)
                        d['snippets'] = snippets
                        all_matches.append(d)
                    matching_instances[class_name] = all_matches
            else:
                # search through all used values for matches, then return
                all_vals_nested = select(i.key_topics for i in items)[:][:]
                all_vals = set([
                    item for sublist in all_vals_nested for item in sublist])
                if match_type not in ('exact-insensitive',):
                    raise NotImplementedError(
                        'Unsupported match type: ' + match_type
                    )
                else:
                    all_matches_tmp = [
                        i for i in all_vals if cur_search_text in i.lower()
                    ]
                    all_matches = list()
                    items_query = to_check[class_name]['items_query']
                    for match in all_matches_tmp:
                        # get number of results for this match
                        n_items = count(items.filter(items_query(match)))
                        d = {'name': match}
                        d['n_items'] = n_items

                        # exact-insensitive snippet
                        # TODO code for finding other types of snippets
                        # TODO score by relevance
                        # TODO add snippet length constraints
                        snippets = dict()
                        pattern = re.compile(cur_search_text, re.IGNORECASE)

                        def repl(x):
                            return '<highlight>' + x.group(0) + '</highlight>'
                        for field in fields:
                            snippets[field] = list()
                            if search_text in match.lower():
                                snippet = re.sub(
                                    pattern, repl, match)
                                snippets[field].append(snippet)
                        d['snippets'] = snippets
                        all_matches.append(d)
                    matching_instances[class_name] = all_matches

        # if match, return matching text and relevance score
        # collate and return all entity instances that matched in order of
        # relevance, truncating at a threshold number of them
        return matching_instances
