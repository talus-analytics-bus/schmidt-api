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
from pony.orm import select, db_session, raw_sql, distinct, count, StrArray, desc
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
    ids: list = [],
    is_desc: bool = True,
    order_by: str = 'date'
):
    # get all items
    selected_items = select(
        i for i in db.Item
        if (
            len(ids) == 0
            or i.id in ids
        )
    )

    # order items
    ordered_items = apply_ordering_to_items(
        selected_items, order_by, is_desc
    )

    # get total num items, pages, etc. for response
    total = count(ordered_items)
    items = ordered_items.page(page, pagesize=pagesize)[:][:]
    num_pages = math.ceil(total / pagesize)

    return {
        'page': page,
        'num_pages': num_pages,
        'pagesize': pagesize,
        'total': total,
        'num': len(items),
        'data': items,
    }


@db_session
def get_item(
    page: int = 1,
    pagesize: int = 1000000,
    id: int = None,
    include_related: bool = False
):
    """Returns data about the item with the given ID.

    TODO add pagination?

    Parameters
    ----------
    id : int
        Description of parameter `id`.

    Returns
    -------
    type
        Description of returned object.

    """
    if id is None:
        return {}
    else:
        # get item
        item = db.Item[id]

        # define data output
        items = [item]

        # if include related, get those too
        all_related = []
        related = []
        total = None
        if include_related:
            all_related = select(
                (
                    i,
                    (
                        author in item.authors
                        and author in i.authors
                        and i != item
                    ),
                    (
                        tag in item.key_topics
                        and tag in i.key_topics
                    )
                )
                for i in db.Item
                for author in db.Author
                for tag in db.Tag
                if (
                    author in item.authors
                    and author in i.authors
                    and i != item
                ) or (
                    tag in item.key_topics
                    and tag in i.key_topics
                )
            )
            related = all_related.page(page, pagesize=pagesize)
            total = count(all_related)

        # return all data
        related_dicts = []
        for d in related:
            datum = d[0].to_dict(
                # only=only,
                exclude=['search_text'],
                with_collections=True,
                related_objects=True,
            )
            why = list()
            if d[1]:
                why.append('more by this authoring org.')
            if d[2]:
                why.append('similar topic')
            datum['why'] = why
            related_dicts.append(datum)

        res = {
            'data': item.to_dict(
                # only=only,
                exclude=['search_text'],
                with_collections=True,
                related_objects=True,
            ),
        }
        if include_related:
            res['num_pages'] = math.ceil(total / pagesize)
            res['page'] = page
            res['pagesize'] = pagesize
            res['total'] = total
            res['num'] = len(related_dicts)
            res['related_items'] = related_dicts
        return res


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
    order_by: str = 'date',
    is_desc: bool = True,
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
        filters,
        search_text
    )

    # if search text not null and not preview: get matching instances by class
    other_instances = get_matching_instances(
        filtered_items,
        search_text,
        explain_results  # TODO dynamically
    )

    # apply search text to items, if any
    searched_items = apply_search_to_items(
        filtered_items, search_text, explain_results, preview
    )

    # get filter value counts for current set
    filter_counts = get_metadata_value_counts(searched_items)

    # order items
    ordered_items = apply_ordering_to_items(
        searched_items, order_by, is_desc, search_text
    )

    # if applicable, get explanation for search results (snippets)
    if not preview and explain_results:
        search_items_with_snippets = list()
        cur_search_text = search_text.lower()
        data_snippets = list()

        # TODO reuse code in search.py
        pattern = re.compile(cur_search_text, re.IGNORECASE)

        def repl(x):
            return '<highlight>' + x.group(0) + '</highlight>'

        for d in ordered_items:
            snippets = dict()
            at_least_one = False
            # check basic string fields for exact-insensitive matches
            # TODO tag fields, linked fields
            fields_str = (
                'type_of_record',
                'title',
                'description',
                'link',
            )

            # basic fields
            for field in fields_str:
                if cur_search_text in getattr(d, field).lower():
                    at_least_one = True
                    snippets[field] = re.sub(
                        pattern, repl, getattr(d, field))

            # tag fields
            # TODO

            # linked fields
            # TODO

            # pdf?
            if any(cur_search_text in scraped_text for scraped_text in d.files.scraped_text):
                at_least_one = True
                snippets['files'] = 'PDF file contains text match'
            data_snippets.append(
                snippets if at_least_one else None
            )

    # paginate items
    start = 1 + pagesize * (page - 1) - 1
    end = pagesize * (page)
    items = ordered_items[start:end]
    # items = ordered_items.page(page, pagesize=pagesize)

    # if preview: return counts of items and matching instances
    data = None
    if preview:
        n_items = len(ordered_items)
        # n_items = count(ordered_items)
        data = {
            'n_items': n_items,
            'other_instances': other_instances
        }
    else:
        # otherwise: return paginated items and details
        total = len(ordered_items)
        # total = count(ordered_items)
        num_pages = math.ceil(total / pagesize)
        item_dicts = [
            d.to_dict(
                # only=only,
                exclude=['search_text'],
                with_collections=True,
                related_objects=True,
            )
            for d in items
        ]
        data = {
            'page': page,
            'num_pages': num_pages,
            'pagesize': pagesize,
            'total': total,
            'num': len(item_dicts),
            'data': item_dicts,
        }
        if explain_results:
            data['data_snippets'] = data_snippets
            data['filter_counts'] = filter_counts

    return data


def apply_filters_to_items(
    items,
    filters: dict = {},
    search_text: str = None
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

        # filters items by Tag attributes
        if field in tag_sets:
            items = select(
                i
                for i in items
                for j in i.key_topics
                if j.name in allowed_values
                and j.field == field
            )

        # filter items by linked attributes
        elif '.' in field:
            field_arr = field.split('.')
            entity_name = field_arr[0]
            linked_field = field_arr[1]
            entity = getattr(db, entity_name.capitalize())
            items = select(
                i
                for i in items
                for j in getattr(i, entity_name + 's')
                if getattr(j, linked_field) in allowed_values
            )

        else:
            items = select(
                i
                for i in items
                if getattr(i, field) in allowed_values
            )

    # apply search text
    if search_text is not None:
        items = select(
            i
            for i in items
            for file in i.files
            if file.scraped_text is not None
            and search_text.lower() in i.search_text.lower()
        )

    return items


def apply_search_to_items(
    search_items,
    search_text: str = None,
    explain_results: bool = False,
    preview: bool = True
):
    """Given a search string, applies exact-insensitive search to item
    metadata to find matches.

    TODO other search approaches like fuzzy

    Parameters
    ----------
    items : type
        Description of parameter `items`.
    search_text : str
        Description of parameter `search_text`.

    Returns
    -------
    type
        Description of returned object.

    """

    # apply search text
    if search_text is not None:
        cur_search_text = search_text.lower()
        search_items = select(
            search_item
            for search_item in search_items
            if cur_search_text in search_item.search_text.lower()
        )

    return search_items


def apply_ordering_to_items(
    items,
    order_by: str = 'date',
    is_desc: bool = True,
    search_text=None
):
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
    # TODO implement col ordering (relevance is done for now)
    by_relevance = order_by == 'relevance'
    item_ids_by_relevance = list()
    if by_relevance and search_text is not None:
        cur_search_text = search_text.lower()
        for d in items:
            relevance = None
            if cur_search_text in d.title.lower():
                relevance = 3
            elif cur_search_text in d.description.lower():
                relevance = 2
            else:
                relevance = 0
            item_ids_by_relevance.append(
                (
                    d.id,
                    relevance
                )
            )
        item_ids_by_relevance.sort(key=lambda x: x[1])
        item_ids_by_relevance.reverse()
        item_ids = [i[0] for i in item_ids_by_relevance]
        items = [db.Item[i[0]] for i in item_ids_by_relevance]
        # if not sorting by relevance, handle other cases
    elif order_by == 'date' or order_by == 'title':
        # date or title
        # `items` is PonyORM query object, so apply ordering using methods
        if is_desc:
            items = items.order_by(desc(getattr(db.Item, order_by)))
        else:
            items = items.order_by(getattr(db.Item, order_by))
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
            # 'Funder': {
            #     'fields': ['name'],
            #     'match_type': 'exact-insensitive',
            #     'snip_length': 1000000,
            #     'items_query': lambda x: lambda i: x in i.funders
            # },
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


@db_session
def get_metadata_value_counts(items):
    """Given a set of items, returns the possible filter values in them and
    the number of items for each.

    Parameters
    ----------
    items : type
        Description of parameter `items`.

    Returns
    -------
    type
        Description of returned object.

    """

    # Key topics
    key_topics = select(
        (tag.name, count(i))
        for i in items
        for tag in i.key_topics
    )[:][:]

    # Authors
    authors = select(
        (author.authoring_organization, count(i))
        for i in items
        for author in i.authors
    )[:][:]

    # Author types
    author_types = select(
        (author.type_of_authoring_organization, count(i))
        for i in items
        for author in i.authors
    )[:][:]

    # Funder names
    funders = select(
        (funder.name, count(i))
        for i in items
        for funder in i.funders
    )[:][:]

    # Years
    years = select(
        (i.date.year, count(i))
        for i in items
    )[:][:]

    # Item type
    types_of_record = select(
        (i.type_of_record, count(i))
        for i in items
    )[:][:]
    return {
        'key_topics': key_topics,
        'authors': authors,
        'author_types': author_types,
        'funders': funders,
        'years': years,
        'types_of_record': types_of_record,
    }
