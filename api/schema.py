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
from .export import SchmidtExportPlugin
from .utils import jsonify_response, DefaultOrderedDict

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)
s3 = boto3.client('s3')

def cached(func):
    """ Caching """
    cache = {}

    @functools.wraps(func)
    def wrapper(*func_args, **kwargs):

        key = str(kwargs)
        if key in cache:
            return cache[key]

        results = func(*func_args, **kwargs)
        cache[key] = results
        return results

    return wrapper

@db_session
def cached_items(func):
    """ Caching for PonyORM item instances """
    cache = {}

    @functools.wraps(func)
    def wrapper(*func_args, **kwargs):

        key = str(kwargs)
        if key in cache:

            # get items by id
            items = cache[key]
            return items

        results = func(*func_args, **kwargs)
        cache[key] = results
        return results

    return wrapper

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
                    # (
                    #     author in item.authors
                    #     and author in i.authors
                    # ),
                    (
                        tag in item.key_topics
                        and tag in i.key_topics
                    ),
                    i in item.items
                )
                for i in db.Item
                # for author in db.Author
                for tag in db.Tag
                if (
                #     (
                #     author in item.authors
                #     and author in i.authors
                # ) or
                    (
                    tag in item.key_topics
                    and tag in i.key_topics
                ) or (
                    i in item.items
                ))
                and i != item
            )
            related = all_related.order_by(lambda a, b, c: desc(c)).page(page, pagesize=pagesize)
            total = count(all_related)

        # return all data
        related_dicts = []
        already_added = set()
        for d in related:
            if d[0].id in already_added:
                continue
            else:
                already_added.add(d[0].id)
                datum = d[0].to_dict(
                    # only=only,
                    exclude=['search_text'],
                    with_collections=True,
                    related_objects=True,
                )
                why = list()
                if d[2]:
                    why.append('directly related')
                if not d[2]:
                    # if d[1]:
                    #     why.append('also by this authoring org.')
                    if d[1]:
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
# @cached
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

    # # return to start of IO stream
    # data.seek(0)

    # return file with correct media type given its extension
    media_type = 'application'
    if key.endswith('.pdf'):
        media_type = 'application/pdf'

    attachment_filename = file.filename if not get_thumb else \
        file.s3_filename + '_thumb.png'
    return {
        'data': data,
        'attachment_filename': attachment_filename,
        'as_attachment': False
    }


@db_session
@cached
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
    # get ordered items, from cache if available
    [ordered_items, filter_counts, other_instances] = \
        get_ordered_items_and_filter_counts(
            filters=filters,
            search_text=search_text,
            order_by=order_by,
            is_desc=is_desc,
            preview=preview,
            explain_results=explain_results,
        )

    # paginate items
    start = 1 + pagesize * (page - 1) - 1
    end = pagesize * (page)
    items = ordered_items[start:end]

    # if applicable, get explanation for search results (snippets)
    data_snippets = list()
    if not preview and explain_results and search_text is not None and search_text != '':
        search_items_with_snippets = list()
        cur_search_text = search_text.lower() if search_text is not None \
            else ''

        # TODO reuse code in search.py
        pattern = re.compile(cur_search_text, re.IGNORECASE)

        def repl(x):
            return '<highlight>' + x.group(0) + '</highlight>'

        for d in items:
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
            # fields_tag_str = (
            #     ('key_topics', 'name'),
            # )
            # for field, linked_field in fields_tag_str:
            #     tags = getattr(getattr(d, field), linked_field)
            #
            #     if cur_search_text in getattr(getattr(d, field), linked_field).lower():
            #         at_least_one = True
            #         snippets[field] = re.sub(
            #             pattern, repl, getattr(d, field))


            # linked fields
            linked_fields_str = (
                'authors.authoring_organization',
                'funders.name',
            )
            for field_tmp in linked_fields_str:
                arr_tmp = field_tmp.split('.')
                entity_name = arr_tmp[0]
                field = arr_tmp[1]
                for linked_instance in getattr(d, entity_name):
                    if cur_search_text in getattr(linked_instance, field).lower():
                        at_least_one = True
                        if entity_name not in snippets:
                            snippets[entity_name] = []
                        cur_snippet = dict()
                        cur_snippet[field] = re.sub(
                            pattern, repl, getattr(linked_instance, field)
                            )
                        cur_snippet['id'] = linked_instance.id
                        snippets[entity_name].append(
                            cur_snippet
                        )

            # custom tags?
            if any(search_text in dd.lower() for dd in d.tags.name):
                at_least_one = True
                snippets['tags'] = 'Search tags contain text match'

            # pdf?
            for file in d.files:
                if file.scraped_text is not None and \
                        cur_search_text in file.scraped_text:
                    at_least_one = True
                    snippets['files'] = 'PDF file contains text match'
                break

            # append results
            data_snippets.append(
                snippets if at_least_one else dict()
            )

    # if preview: return counts of items and matching instances
    data = None
    if preview:
        n_items = len(ordered_items)
        # n_items = count(ordered_items)
        data = {
            'n_items': n_items,
            'other_instances': other_instances,
            'search_text': search_text
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

@db_session
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
                i_filtered
                for i_filtered in items
                for j_topic in i_filtered.key_topics
                if j_topic.name in allowed_values
                and j_topic.field == field
            ).prefetch(
                db.Item.key_topics,
                db.Item.funders,
                db.Item.authors,
                db.Item.tags,
                db.Item.files,
                db.Item.events
            )

        # filter items by linked attributes
        elif '.' in field:
            field_arr = field.split('.')
            entity_name = field_arr[0]
            linked_field = field_arr[1]
            entity = getattr(db, entity_name.capitalize())
            if entity_name == 'author' and linked_field == 'id':
                items = select(
                    i_linked_author
                    for i_linked_author in items
                    for j_linked_author in i_linked_author.authors
                    if str(j_linked_author.id) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
            elif entity_name == 'author' and linked_field == 'type_of_authoring_organization':
                items = select(
                    i_linked_author_type
                    for i_linked_author_type in items
                    for j_linked_author_type in i_linked_author_type.authors
                    if str(j_linked_author_type.type_of_authoring_organization) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
            elif entity_name == 'funder' and linked_field == 'name':
                items = select(
                    i_linked_funder
                    for i_linked_funder in items
                    for j_linked_funder in i_linked_funder.funders
                    if str(j_linked_funder.name) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
            else:
                items = select(
                    i_linked
                    for i_linked in items
                    for j_linked in getattr(i_linked, entity_name + 's')
                    if str(getattr(j_linked, linked_field)) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
        # special: years
        elif field == 'years':
            if 'range' not in allowed_values[0]:
                items = select(
                    i_years
                    for i_years in items
                    if str(i_years.date.year) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
            else:
                range = allowed_values[0].split('_')[1:3]
                start = int(range[0]) if range[0] != 'null' else 0
                end = int(range[1]) if range[1] != 'null' else 9999
                items = select(
                    i_range
                    for i_range in items
                    if i_range.date.year >= start
                    and i_range.date.year <= end
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events
                )
        else:
            items = select(
                i_standard
                for i_standard in items
                if getattr(i_standard, field) in allowed_values
            ).prefetch(
                db.Item.key_topics,
                db.Item.funders,
                db.Item.authors,
                db.Item.tags,
                db.Item.files,
                db.Item.events
            )

    # apply search text
    if search_text is not None and search_text != '':
        items = select(
            i
            for i in items
            if search_text.lower() in i.search_text
            # if search_text.lower() in i.search_text.lower()
        ).prefetch(
            db.Item.key_topics,
            db.Item.funders,
            db.Item.authors,
            db.Item.tags,
            db.Item.files,
            db.Item.events
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
    if search_text is not None and search_text != '':
        cur_search_text = search_text.lower()
        search_items = select(
            search_item
            for search_item in search_items
            if cur_search_text in search_item.search_text
            # if cur_search_text in search_item.search_text.lower()
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
    if by_relevance and search_text is not None and search_text != '':
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
        desc_text = 'DESC' if is_desc else ''

        # put nulls last always
        if order_by == 'date':
            items = items.order_by(raw_sql(f'''i.date {desc_text} NULLS LAST'''))
        elif order_by == 'title':
            items = items.order_by(raw_sql(f'''i.title {desc_text} NULLS LAST'''))
    return items

@db_session
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
    if search_text is None or search_text == '':
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
# @cached
def get_metadata_value_counts(items):
    """Given a set of items, returns the possible filter values in them and
    the number of items for each.

    TODO optimize by reducing db queries

    Parameters
    ----------
    items : type
        Description of parameter `items`.

    Returns
    -------
    type
        Description of returned object.

    """
    # print(items)
    if items is None:
        items = db.Item

    # Key topics
    key_topics = select(
        (
            i.key_topics.name,
            count(i),
        )
        for i in items
    ).order_by(lambda x, y: desc(y))[:][:]

    # Authors
    authors = select(
        (author.authoring_organization, count(i), author.id)
        for i in items
        for author in i.authors
    ).order_by(lambda x, y, z: desc(y))[:][:]


    # Author types
    author_types = select(
        (author.type_of_authoring_organization, count(i))
        for i in items
        for author in i.authors
    ).order_by(lambda x, y: desc(y))[:][:]

    # Funder names
    funders = select(
        (funder.name, count(i))
        for i in items
        for funder in i.funders
    ).order_by(lambda x, y: desc(y))[:][:]

    # Years
    years = select(
        (i.date.year, count(i))
        for i in items
    ).order_by(lambda x, y: desc(y))[:][:]

    # Events
    events = select(
        (event.name, count(i))
        for i in items
        for event in i.events
    ).order_by(lambda x, y: desc(y))[:][:]

    # Item type
    types_of_record = select(
        (i.type_of_record, count(i))
        for i in items
    ).order_by(lambda x, y: desc(y))[:][:]


    output = {
        'key_topics': key_topics,
        'authors': authors,
        'author_types': author_types,
        'funders': funders,
        'years': years,
        'types_of_record': types_of_record,
        'events': events,
    }

    return output


@db_session
def export(filters: dict = None):
    """Return XLSX data export for data with the given filters applied.

    Parameters
    ----------
    filters : dict
        The filters to apply.

    """
    media_type = 'application/' + \
        'vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    # Create Excel export file
    export_instance = SchmidtExportPlugin(db, filters, class_name='Item')
    content = export_instance.build()

    # return the file
    today = date.today()
    attachment_filename = f'''Health Security Net - Data Export.xlsx'''

    return {
        'content': content,
        'attachment_filename': attachment_filename,
        'as_attachment': True
    }

def assign_field_value_to_export_row(row, d, field):
    """Given the row dict and the `field` info, assigns the value to the row,
    accounting for linked entities, etc., from the datum `d`

    Parameters
    ----------
    row : type
        Description of parameter `row`.
    field : type
        Description of parameter `field`.

    Returns
    -------
    type
        Description of returned object.

    """
    def get_val(d, field):
        """Get formatted value of field based on type.

        Parameters
        ----------
        d : type
            Description of parameter `d`.
        field : type
            Description of parameter `field`.

        Returns
        -------
        type
            Description of returned object.

        """
        val_tmp = getattr(d, field.field)

        # parse bool as yes/no
        if field.type == 'bool':
            if val_tmp is None:
                return ''
            elif val_tmp == True:
                return 'Yes'
            else:
                return 'No'
        else:
            return val_tmp if val_tmp is not None else ''

    linked = field.linked_entity_name != field.entity_name
    if not linked:
        row[field.colgroup][field.display_name] = get_val(d, field)
    else:
        linked_field_name = field.linked_entity_name.lower() + 's'
        linked_instances = getattr(d, linked_field_name)
        strs = list()
        for dd in linked_instances:
            strs.append(get_val(dd, field))
        row[field.colgroup][field.display_name] = "\n".join(strs)


@db_session
@cached
@jsonify_response
def get_export_data(filters: dict = None):
    """Returns items that match the filters for export.

    Parameters
    ----------
    filters : dict
        Description of parameter `filters`.

    Returns
    -------
    type
        Description of returned object.

    """

    # get data fields to be exported
    export_fields = select(
        i for i in db.Metadata
        if i.entity_name == 'Item'
        and i.export
    ).order_by(db.Metadata.order)

    # get items to be exported
    ids = [] if 'id' not in filters else filters['id']
    items = select(
        i for i in db.Item
        if i.id in ids or len(ids) == 0
    ).order_by(raw_sql(f'''i.date DESC NULLS LAST'''))

    # get rows
    rows = list()

    # format data for export
    for d in items:
        row = DefaultOrderedDict(DefaultOrderedDict)
        for field in export_fields:
            assign_field_value_to_export_row(row, d, field)

        rows.append(row)

    return rows

@db_session
@jsonify_response
def get_export_legend_data():
    """Returns legend entry data for all fields exported in XLSX file.

    """
    # get data fields to be exported
    export_fields = select(
        i for i in db.Metadata
        if i.entity_name == 'Item'
        and i.export
    ).order_by(db.Metadata.order)

    # format data for export
    def_row = DefaultOrderedDict(DefaultOrderedDict)
    val_row = DefaultOrderedDict(DefaultOrderedDict)
    for field in export_fields:
        # definition
        def_row[field.colgroup][field.display_name] = \
            field.definition

        # possible values
        val_row[field.colgroup][field.display_name] = \
            field.possible_values

    return [def_row, val_row]

@db_session
@cached_items
def get_ordered_items_and_filter_counts(
    filters: dict = {},
    search_text: str = None,
    order_by: str = 'date',
    is_desc: bool = True,
    preview: bool = False,
    explain_results: bool = True,
):
    # get all items
    all_items = get_all_items()

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
    ) if preview else []

    # get filter value counts for current set
    filter_counts = get_metadata_value_counts(items=filtered_items)

    # order items
    return [
        apply_ordering_to_items(
            filtered_items, order_by, is_desc, search_text
        )[:][:],
        filter_counts,
        other_instances
    ]

@cached_items
def get_all_items():
    return select(
        i for i in db.Item
    ).prefetch(
        db.Item.key_topics,
        db.Item.funders,
        db.Item.authors,
        db.Item.tags,
        db.Item.files,
        db.Item.events
    )
