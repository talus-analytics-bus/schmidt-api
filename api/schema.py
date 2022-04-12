##
# API schema
##

# Standard libraries
import functools
import re
import math
import logging
from io import BytesIO
from typing import Any, Callable, Dict, List, Set, Tuple, Union

# Third party libraries
import boto3
import pprint
from pony.orm import select, db_session, raw_sql, count
from pony.orm.core import Query
from flask import Response

# Local libraries
from api.db_models.models import Item, Metadata, Glossary
from db.db import db
from . import search
from .export import SchmidtExportPlugin
from .utils import is_listlike, jsonify_response, DefaultOrderedDict
from api.metadatacounter.core import MetadataCounter

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)
s3 = boto3.client("s3")


def cached(func: Callable):
    """Decorator that returns function output if previously generated, as
    indexed by the concatenated kwargs; otherwise, runs the function and stores
    the output in the cache indexed by the concatenated kwargs.

    Args:
        func (Callable): Any function

    Returns:
        Any: The function result, possibly from the cache.
    """
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
def cached_items(func: Callable) -> Any:
    """Return cached Item instances or cache them.

    Args:
        func (Callable): Function, presumably one returning Item instances.

    Returns:
        Any: Function output, presumably Item instances.
    """
    cache: dict = {}

    @functools.wraps(func)
    def wrapper(*func_args, **kwargs) -> Any:
        """A wrapper for the function.

        Returns:
            Any: Cache results or function output.
        """
        key: str = str(kwargs)
        if key in cache:

            # get items by id
            res_tuple_tmp: Any = cache[key]
            item_ids: Set[int] = {i.id for i in res_tuple_tmp[0]}
            refreshed_items: List[Item] = select(i for i in Item if i.id in item_ids)[
                :
            ][:]
            return (refreshed_items, res_tuple_tmp[1], res_tuple_tmp[2])

        results: Any = func(*func_args, **kwargs)
        cache[key] = results
        return results

    return wrapper


@db_session
def get_items(
    page,
    pagesize,
    ids: list = [],
    is_desc: bool = True,
    order_by: str = "date",
):
    # get all items
    selected_items = select(i for i in db.Item if (len(ids) == 0 or i.id in ids))

    # order items
    ordered_items = apply_ordering_to_items(selected_items, order_by, is_desc)

    # get total num items, pages, etc. for response
    total = count(ordered_items)
    items = ordered_items.page(page, pagesize=pagesize)[:][:]
    num_pages = math.ceil(total / pagesize)

    return {
        "page": page,
        "num_pages": num_pages,
        "pagesize": pagesize,
        "total": total,
        "num": len(items),
        "data": items,
    }


@db_session
def get_metadata() -> List[dict]:
    res: List[Metadata] = select(i for i in Metadata)[:][:]
    return [d.to_dict() for d in res]


@db_session
def get_item(
    page: int = 1,
    pagesize: int = 1000000,
    id: int = None,
    include_related: bool = False,
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
    # get item by id or first item if no id
    item: Item = None
    if id is not None:
        try:
            item = db.Item[id]
        except Exception as e:
            return Response(None, status=404)
    else:
        item = select(i for i in Item).first()

    # if include related, get those too
    # include all directly related items and, if that is fewer than 10,
    # as many items with a related topic as required to reach 10 total
    all_related = []
    related = []
    total = None
    related_by_topic = None
    related_directly = None
    if include_related:

        # get all items directly related
        related_directly = select(
            i for i in db.Item for tag in db.KeyTopic if i in item.items and i != item
        )

        # up to 10 items related by topic
        max_related_to_select = (
            0 if related_directly.count() >= 10 else 10 - related_directly.count()
        )
        related_by_topic = select(
            i
            for i in db.Item
            for tag in db.KeyTopic
            if tag in item.key_topics
            and tag in i.key_topics
            and i != item
            and i not in related_directly
        ).limit(max_related_to_select)

        # concatenate and sort directly related items to appear first
        all_related = select(
            i for i in db.Item if i in related_directly or i in related_by_topic
        ).order_by(lambda x: x not in item.items)

        # get grand total
        total = len(all_related)

        # get current page
        related = all_related.page(page, pagesize=pagesize)

    # return all data
    related_dicts = []
    already_added = set()

    # process each item, adding the reason why it is related
    for d in related:
        if d.id in already_added:
            continue
        else:
            why = list()
            if d in item.items:
                why.append("directly related")
            if d not in item.items:
                why.append("similar topic")

            already_added.add(d.id)
            datum = d.to_dict(
                exclude=["search_text"],
                with_collections=True,
                related_objects=True,
            )
            datum["why"] = why
            related_dicts.append(datum)

    # create response dict
    res = {
        "data": item.to_dict(
            exclude=["search_text"],
            with_collections=True,
            related_objects=True,
        ),
    }

    # add pagination data to response, if relevant
    if include_related:
        res["num_pages"] = math.ceil(total / pagesize)
        res["page"] = page
        res["pagesize"] = pagesize
        res["total"] = total
        res["num"] = len(related_dicts)
        res["related_items"] = related_dicts
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
    key = file.s3_filename if not get_thumb else file.s3_filename + "_thumb"

    # retrieve file and write it to IO file object `data`
    # if the file is not found in S3, return a 404 error
    data = BytesIO()
    try:
        s3.download_fileobj("schmidt-storage", key, data)
    except Exception as e:
        logging.exception(e)
        return "Document not found (404)"

    attachment_filename = (
        file.filename if not get_thumb else file.s3_filename + "_thumb.png"
    )
    return {
        "data": data,
        "attachment_filename": attachment_filename,
        "as_attachment": False,
    }


@db_session
@cached
def get_search(
    page: int,
    pagesize: int,
    filters: dict = {},
    search_text: str = None,
    order_by: str = "date",
    is_desc: bool = True,
    preview: bool = False,
    explain_results: bool = True,
) -> dict:
    """Get search results.

    Args:
        page (int): The current page.

        pagesize (int): The page size.

        filters (dict, optional): Filters to. Defaults to {}.

        search_text (str, optional): Text to search by. Defaults to None.

        order_by (str, optional): Field to order on. Defaults to "date".

        is_desc (bool, optional): Whether ordering is descending. Defaults
        to True.

        preview (bool, optional): True if search is only a preview, meaning
        that the number of results and not the results themselves is needed.
        Defaults to False.

        explain_results (bool, optional): True if information about why each
        search result matched should be returned. Defaults to True.

    Returns:
        dict: The search results data.
    """

    # get ordered items, from cache if available
    (
        ordered_items,
        filter_counts,
        other_instances,
    ) = get_ordered_items_and_filter_counts(
        filters=filters,
        search_text=search_text,
        order_by=order_by,
        is_desc=is_desc,
        preview=preview,
        explain_results=explain_results,
    )

    # paginate items
    # apply most efficient pagination method based on `items` type
    total: int = None
    if type(ordered_items) == list:
        start = 1 + pagesize * (page - 1) - 1
        end = pagesize * (page)
        total = len(ordered_items)
        items = ordered_items[start:end]
    else:
        total = ordered_items.count()
        items = ordered_items.page(page, pagesize=pagesize)

    # if applicable, get explanation for search results (snippets)
    data_snippets: list = list()
    if (
        not preview
        and explain_results
        and search_text is not None
        and search_text != ""
    ):
        cur_search_text = search_text.lower() if search_text is not None else ""

        # TODO reuse code in search.py
        pattern = re.compile(cur_search_text, re.IGNORECASE)

        def repl(x):
            return "<highlight>" + x.group(0) + "</highlight>"

        for d in items:
            snippets = dict()
            at_least_one = False
            # check basic string fields for exact-insensitive matches
            # TODO tag fields, linked fields
            fields_str = (
                "type_of_record",
                "title",
                "description",
                "link",
                "sub_organizations",
            )

            # basic fields
            for field in fields_str:
                if cur_search_text in getattr(d, field).lower():
                    at_least_one = True
                    snippets[field] = re.sub(pattern, repl, getattr(d, field))

            # tag fields
            # TODO
            fields_tag_str = (
                ("covid_tags", "name"),
                ("key_topics", "name"),
                ("events", "name"),
            )
            for field, linked_field in fields_tag_str:
                value = getattr(getattr(d, field), linked_field)
                if type(value) == str:
                    if cur_search_text in value.lower():
                        at_least_one = True
                        snippets[field] = re.sub(pattern, repl, getattr(d, field))
                else:
                    matches = list()
                    for v in value:
                        if cur_search_text in v.lower():
                            at_least_one = True
                            matches.append({"name": re.sub(pattern, repl, v), "id": v})
                    if len(matches) > 0:
                        snippets[field] = matches

            # linked fields
            linked_fields_str = (
                "authors.authoring_organization",
                "authors.acronym",
                "funders.name",
            )
            for field_tmp in linked_fields_str:
                arr_tmp = field_tmp.split(".")
                entity_name = arr_tmp[0]
                field = arr_tmp[1]
                for linked_instance in getattr(d, entity_name):
                    if cur_search_text in getattr(linked_instance, field).lower():
                        at_least_one = True

                        # if the field is the author's acronym, count this as
                        # a match with the entire author's name
                        count_as_entire_author_name = field_tmp == "authors.acronym"

                        # get value of match
                        value = (
                            getattr(linked_instance, field)
                            if not count_as_entire_author_name
                            else linked_instance.authoring_organization
                        )

                        if count_as_entire_author_name:
                            field = "authoring_organization"

                        if entity_name not in snippets:
                            snippets[entity_name] = []

                        # append matching text snippet
                        cur_snippet = dict()

                        # highlight relevant snippet, unless this is an acronym
                        # match, in which case highlight entire publisher name
                        if not count_as_entire_author_name:
                            cur_snippet[field] = re.sub(pattern, repl, value)
                        else:
                            cur_snippet[field] = f"""<highlight>{value}</highlight>"""

                        cur_snippet["id"] = linked_instance.id
                        snippets[entity_name].append(cur_snippet)

            # custom tags?
            if any(search_text in dd.lower() for dd in d.tags.name):
                at_least_one = True
                snippets["tags"] = "Search tags contain text match"

            # pdf?
            if d.file_search_text is not None and cur_search_text in d.file_search_text:
                at_least_one = True
                snippets["files"] = "PDF file contains text match"

            # append results
            data_snippets.append(snippets if at_least_one else dict())

    # if preview: return counts of items and matching instances
    data = None
    if preview:

        data = {
            "n_items": total,
            "other_instances": other_instances,
            "search_text": search_text,
        }
    else:
        # otherwise: return paginated items and details
        num_pages = math.ceil(total / pagesize)
        item_dicts = [
            d.to_dict(
                exclude=["search_text"],
                with_collections=True,
                related_objects=True,
            )
            for d in items
        ]
        data = {
            "page": page,
            "num_pages": num_pages,
            "pagesize": pagesize,
            "total": total,
            "num": len(item_dicts),
            "data": item_dicts,
        }
        if explain_results:
            data["data_snippets"] = data_snippets
            data["filter_counts"] = filter_counts

    return data


@db_session
def apply_filters_to_items(
    items: Query, filters: dict = {}, search_text: str = None
) -> Query:
    """Given a set of filters, returns the items that match. If
    `explain_results` is True, return for each item the field(s) that matched
    and a highlighted text snippet (HTML) that shows what matched.

    Args:
        items (Query): The query selecting items.
        filters (dict, optional): Filters to apply. Defaults to {}.
        search_text (str, optional): Text to search by. Defaults to None.

    Returns:
        Query: The filtered items query.
    """
    # tag_sets: tuple = ("key_topics", "covid_tags")
    field: str = None
    for field in filters:
        allowed_values: List[Any] = [str(v) for v in filters[field]]
        if len(allowed_values) == 0:
            continue

        # filters items by Tag attributes
        if field == "key_topics":
            items = select(
                i_key_topics
                for i_key_topics in items
                for key_topic in i_key_topics.key_topics
                if key_topic.name in allowed_values
            ).prefetch(
                db.Item.covid_tags,
                db.Item.key_topics,
                db.Item.funders,
                db.Item.authors,
                db.Item.tags,
                db.Item.files,
                db.Item.events,
                db.Item.items,
            )
        elif field == "covid_tags":
            items = select(
                i_covid_tags
                for i_covid_tags in items
                for j_covid_tag in i_covid_tags.covid_tags
                if j_covid_tag.name in allowed_values
            ).prefetch(
                db.Item.covid_tags,
                db.Item.key_topics,
                db.Item.funders,
                db.Item.authors,
                db.Item.tags,
                db.Item.files,
                db.Item.events,
                db.Item.items,
            )

        # filter items by linked attributes
        elif "." in field:
            field_arr = field.split(".")
            entity_name = field_arr[0]
            linked_field = field_arr[1]
            if entity_name == "author" and linked_field == "id":
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
                    db.Item.events,
                    db.Item.items,
                )
            elif (
                entity_name == "author"
                and linked_field == "type_of_authoring_organization"
            ):
                items = select(
                    i_linked_author_type
                    for i_linked_author_type in items
                    for j_linked_author_type in i_linked_author_type.authors
                    if str(j_linked_author_type.type_of_authoring_organization)
                    in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events,
                    db.Item.items,
                )
            elif entity_name == "funder" and linked_field == "name":
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
                    db.Item.events,
                    db.Item.items,
                )
            else:
                items = select(
                    i_linked
                    for i_linked in items
                    for j_linked in getattr(i_linked, entity_name + "s")
                    if str(getattr(j_linked, linked_field)) in allowed_values
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events,
                    db.Item.items,
                )
        # special: years
        elif field == "years":
            if not allowed_values[0].startswith("range"):
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
                    db.Item.events,
                    db.Item.items,
                )
            else:
                range = allowed_values[0].split("_")[1:3]
                start = int(range[0]) if range[0] != "null" else 0
                end = int(range[1]) if range[1] != "null" else 9999
                if start > end:
                    raise ValueError(
                        f"Start year ({start}) must be less than or equal to"
                        f" end year ({end})"
                    )
                items = select(
                    i_range
                    for i_range in items
                    if i_range.date.year >= start and i_range.date.year <= end
                ).prefetch(
                    db.Item.key_topics,
                    db.Item.funders,
                    db.Item.authors,
                    db.Item.tags,
                    db.Item.files,
                    db.Item.events,
                    db.Item.items,
                )
        else:
            items = select(
                i_standard
                for i_standard in items
                if str(getattr(i_standard, field)) in allowed_values
            ).prefetch(
                db.Item.key_topics,
                db.Item.funders,
                db.Item.authors,
                db.Item.covid_tags,
                db.Item.tags,
                db.Item.files,
                db.Item.events,
                db.Item.items,
            )

    # apply search text
    if search_text is not None and search_text != "":
        max_chars = 1000
        cur_search_text = search_text.lower()
        items = select(
            i
            for i in items
            if cur_search_text in i.search_text
            or cur_search_text in i.file_search_text[0:max_chars]
        ).prefetch(
            db.Item.key_topics,
            db.Item.funders,
            db.Item.authors,
            db.Item.tags,
            db.Item.files,
            db.Item.events,
            db.Item.items,
        )

    return items


def apply_ordering_to_items(
    items: Query,
    order_by: str = "date",
    is_desc: bool = True,
    search_text: str = None,
) -> Union[Query, List[Item]]:
    """Returns ordered list of items either as database query or, if ordering
    by item relevance, a list of Item instances.

    Args:
        items (Query): The query selecting items to be ordered.

        order_by (str, optional): The field ordered by. Defaults to "date".

        is_desc (bool, optional): Whether ordering is descending. Defaults
        to True.

        search_text (str, optional): Text to search by, used to determine
        item relevance if ordering by relevance. Defaults to None.

    Returns:
        Union[Query, List[Item]]: The item database query or, if ordering by
        relevance, the list of Item instances.
    """

    # TODO implement col ordering (relevance is done for now)
    by_relevance = order_by == "relevance"
    item_ids_by_relevance = list()
    if by_relevance and search_text is not None and search_text != "":

        cur_search_text = search_text.lower()
        for d in items:
            relevance = None
            if cur_search_text in d.title.lower():
                relevance = 3
            elif cur_search_text in d.description.lower():
                relevance = 2
            else:
                relevance = 0
            item_ids_by_relevance.append((d.id, relevance))
        item_ids_by_relevance.sort(key=lambda x: x[1])
        item_ids_by_relevance.reverse()
        items = [db.Item[i[0]] for i in item_ids_by_relevance]
        # if not sorting by relevance, handle other cases
    elif order_by == "date" or order_by == "title":
        desc_text = "DESC" if is_desc else ""

        # put nulls last always
        if order_by == "date":
            items = items.order_by(raw_sql(f"""i.date {desc_text} NULLS LAST"""))
        elif order_by == "title":
            items = items.order_by(raw_sql(f"""i.title {desc_text} NULLS LAST"""))

    return items


@db_session
def get_matching_instances(
    items: Query, search_text: str = None, explain_results: bool = True
) -> dict:

    # if blank, return nothing
    if search_text is None or search_text == "":
        return {}
    else:
        matching_instances = {}
        # otherwise: check key fields for each entity class in turn for matches
        to_check = {
            "Author": {
                "fields": ["authoring_organization"],
                "match_type": "exact-insensitive",  # TODO other types
                "snip_length": 1000000,
                "items_query": lambda x: lambda i: x in i.authors,
            },
            # 'Funder': {
            #     'fields': ['name'],
            #     'match_type': 'exact-insensitive',
            #     'snip_length': 1000000,
            #     'items_query': lambda x: lambda i: x in i.funders
            # },
            "Event": {
                "fields": ["name"],
                "match_type": "exact-insensitive",
                "snip_length": 1000000,
                "items_query": lambda x: lambda i: x in i.events,
            },
            "Key_Topic": {
                "tag_field": "key_topics",
                "match_type": "exact-insensitive",
                "items_query": lambda x: lambda i: x in i.key_topics.name,
            },
            "Tag": {
                "tag_field": "covid_tags",
                "match_type": "exact-insensitive",
                "items_query": lambda x: lambda i: x in i.covid_tags.name,
            },
        }
        matching_instances = search.get_matching_instances(
            to_check, items, search_text, explain_results
        )

        # if match, return matching text and relevance score
        # collate and return all entity instances that matched in order of
        # relevance, truncating at a threshold number of them
        return matching_instances


@db_session
def export(filters: dict = None, search_text: str = None):
    """Return XLSX data export for data with the given filters applied.

    Parameters
    ----------
    filters : dict
        The filters to apply.

    """

    # Create Excel export file
    export_instance = SchmidtExportPlugin(
        db, filters, search_text=search_text, class_name="Item"
    )
    content = export_instance.build()

    # return the file
    attachment_filename = f"""Health Security Net - Data Download.xlsx"""

    return {
        "content": content,
        "attachment_filename": attachment_filename,
        "as_attachment": True,
    }


def write_field_val_to_excel_row(
    excel_row: DefaultOrderedDict,
    item: Item,
    meta: Metadata,
) -> None:
    """Given the row dict and the `field` info, assigns the value to the row,
    accounting for linked entities, etc., from the item

    Args:
        row (DefaultOrderedDict): The row dictionary
        which stores values to be written in the Excel export.

        item (Item): The item from which formatted values are needed.

        field (Metadata): Information about the field corresponding to the
        Excel column that is being assigned to.
    """

    def get_formatted_val(item: Item, meta: Metadata) -> Any:
        """
        Get formatted value of field based on type for writing to an
        Excel file.

        Args:
            item (Item): The item from which a formatted val. is needed
            meta (Metadata): Info about the column to be assign to.

        Returns:
            Any: A formatted value of any type to be written to the Excel file.
        """
        val_tmp: Any = getattr(item, meta.field, None)

        # parse boolean values as yes/no
        if meta.type == "bool":
            if val_tmp is None:
                return ""
            elif val_tmp is True:
                return "Yes"
            else:
                return "No"

        # parse dates based on how precise they are and whether they are
        # intended to be sortable.
        elif meta.type == "date":
            # sortable date published, with varying degrees of precision
            if meta.field == "date_sortable":
                val_tmp = item.date
                if item.date_type == 1:
                    month = str(val_tmp.month)
                    if len(month) == 1:
                        month = "0" + month
                    return f"""{str(val_tmp.year)}-{month}-XX"""
                elif item.date_type == 2:
                    return f"""{str(val_tmp.year)}-XX-XX"""
                elif item.date_type == 0:
                    return str(val_tmp)
            # date published, with varying degrees of precision
            elif meta.field == "date":
                if item.date_type == 1:
                    return val_tmp.strftime("%b %Y")
                elif item.date_type == 2:
                    return val_tmp.strftime("%Y")
                elif item.date_type == 0:
                    return val_tmp.strftime("%b %d, %Y")

        # write listlike vals. as semicolon-delimited lists
        elif is_listlike(val_tmp):
            return "; ".join([str(v) for v in val_tmp])
        else:
            return val_tmp if val_tmp is not None else ""

    is_linked: bool = meta.linked_entity_name != meta.entity_name

    # non-linked fields: format as needed
    if not is_linked:
        excel_row[meta.colgroup][meta.display_name] = get_formatted_val(item, meta)

    # special case: related files URLs
    elif meta.field == "related_s3_permalink":
        excel_row[meta.colgroup][meta.display_name] = "\n".join(
            [f.s3_permalink for f in item.related_files]
        )

    # linked fields: get values and represent as list of strings (one per line)
    else:
        linked_field_name = meta.linked_entity_name.lower() + "s"
        linked_instances = getattr(item, linked_field_name)
        strs = list()
        for dd in linked_instances:
            strs.append(get_formatted_val(dd, meta))
        excel_row[meta.colgroup][meta.display_name] = "\n".join(strs)


@db_session
@cached
@jsonify_response
def get_export_data(filters: dict = None, search_text: str = None) -> List[dict]:
    """Returns items that match the filters for export.

    Args:
        filters (dict, optional): Filters to apply. Defaults to None.
        search_text (str, optional): Text to search for. Defaults to None.

    Returns:
        List[dict]: Rows for Excel export.
    """

    # get data fields to be exported
    export_metas: Query = select(
        i for i in db.Metadata if i.entity_name == "Item" and i.export
    ).order_by(db.Metadata.order)

    # get items to be exported
    order_field: str = "date"
    items: Query = select(i for i in db.Item).order_by(
        raw_sql(f"""i.{order_field} DESC NULLS LAST""")
    )
    filtered_items: Query = apply_filters_to_items(items, filters, search_text)

    # get rows to write to Excel file
    rows: List[dict] = list()

    # format data for export
    item: Item = None
    for item in filtered_items:
        excel_row: DefaultOrderedDict = DefaultOrderedDict(DefaultOrderedDict)
        meta: Metadata = None
        for meta in export_metas:
            write_field_val_to_excel_row(excel_row, item, meta)
        rows.append(excel_row)

    return rows


@db_session
@jsonify_response
def get_export_legend_data() -> List[DefaultOrderedDict]:
    """Returns legend entry data for all fields exported in Excel, to be
    written to the Excel's legend sheet.

    Returns:
        List[DefaultOrderedDict]: The definition row
        and the possible values row data to write to the Excel legend sheet.
    """
    # get data fields to be exported
    export_metas: Query = select(
        i for i in db.Metadata if i.entity_name == "Item" and i.export
    ).order_by(db.Metadata.order)

    # format data for export
    defs_row_text = DefaultOrderedDict(DefaultOrderedDict)
    poss_vals_row_text = DefaultOrderedDict(DefaultOrderedDict)
    meta: Metadata = None
    for meta in export_metas:
        # definition
        defs_row_text[meta.colgroup][meta.display_name] = meta.definition

        # possible values
        poss_vals_row_text[meta.colgroup][meta.display_name] = meta.possible_values

    return [defs_row_text, poss_vals_row_text]


# @cached_items
@db_session
def get_ordered_items_and_filter_counts(
    filters: dict = {},
    search_text: str = None,
    order_by: str = "date",
    is_desc: bool = True,
    preview: bool = False,
    explain_results: bool = True,
) -> Tuple[Query, dict, Dict[str, list]]:
    """Returns ordered items matching filters and the number of results with
    each filter value.

    Args:
        filters (dict, optional): Filters to apply. Defaults to {}.

        search_text (str, optional): Text to search by. Defaults to None.

        order_by (str, optional): Field to order on. Defaults to "date".

        is_desc (bool, optional): Whether ordering is descending. Defaults
        to True.

        preview (bool, optional): True if search is only a preview, meaning
        that the number of results and not the results themselves is needed.
        Defaults to False.

        explain_results (bool, optional): True if information about why each
        search result matched should be returned. Defaults to True.

    Returns:
        Tuple[Query, dict, Dict[str, list]]: The query containing matching item
        instances; a dictionary counting instances; and, if preview only, the
        number of matches for each instance by filter value.
    """

    # get all items
    all_items: Query = get_all_items()

    # filter items
    filtered_items: Query = apply_filters_to_items(all_items, filters, search_text)

    # if search text not null and not preview: get matching instances by class
    other_instances: Dict[str, list] = (
        get_matching_instances(
            filtered_items, search_text, explain_results  # TODO dynamically
        )
        if preview
        else dict()
    )

    # get filter value counts for current set
    counter: MetadataCounter = MetadataCounter()
    filter_counts: dict = counter.get_metadata_value_counts(
        items=filtered_items,
        all_items=all_items,
        filters=filters,
        search_text=search_text,
    )

    # get ordered items
    ordered_items: Query = apply_ordering_to_items(
        filtered_items, order_by, is_desc, search_text
    )

    # get results
    results: Tuple[Query, dict, Dict[str, list]] = (
        ordered_items,
        filter_counts,
        other_instances,
    )

    # order items
    return results


# @cached_items
def get_all_items() -> Query:
    """Get all items as query with most fields prefetched.

    Returns:
        Query: Query presenting all items.
    """
    return select(i for i in db.Item).prefetch(
        db.Item.key_topics,
        db.Item.funders,
        db.Item.authors,
        db.Item.tags,
        db.Item.files,
        db.Item.events,
        db.Item.items,
    )


@db_session
def get_glossary() -> List[Glossary]:
    """Get all glossary instances.

    Returns:
        List[Glossary]: List of glossary instances.
    """
    return db.Glossary.select().order_by(db.Glossary.colname, db.Glossary.term)[:][:]
