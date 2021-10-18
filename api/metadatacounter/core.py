# standard packages
from api import schema
from typing import List

# 3rd party packages
from pony.orm.core import Query, db_session, desc, coalesce, count, select


# local modules
from api.db_models.models import Item


class MetadataCounter:
    """Count number of items with each value of a metadata field."""

    def __init__(self):
        """Create new metadata counter."""
        return None

    @db_session
    def get_metadata_value_counts(
        self,
        items: Query = None,
        all_items: Query = None,
        exclude: List[str] = [],
        filters: dict = None,
        search_text: str = None,
    ):
        """Given a set of items, returns the possible filter values in them and
        the number of items for each.

        TODO optimize by reducing db queries

        """

        # set items to all items if they are not assigned
        if items is None:
            items = Item

        if all_items is None:
            all_items = Item

        # exclude None-values if those are in the `exclude` list as 'null'
        allow_none = "null" not in exclude

        # define
        to_check = [
            {
                "key": "years",
                "field": "date",
                "filter_field": "years",
                "is_date_part": True,
                "link_field": "year",
            },
            {
                "field": "events",
                "link_field": "name",
                "filter_field": "event.name",
            },
            {
                "field": "key_topics",
                "link_field": "name",  # if present, will link from item
            },
            {
                "field": "covid_tags",
                "link_field": "name",  # if present, will link from item
            },
            {
                "field": "authors",
                "filter_field": "author.id",
                "link_field": "authoring_organization",
                "include_id_and_acronym": True,
            },
            {
                "key": "author_types",
                "field": "authors",
                "link_field": "type_of_authoring_organization",
                "filter_field": "author.type_of_authoring_organization",
            },
            {
                "field": "funders",
                "link_field": "name",
                "filter_field": "funder.name",
            },
            {
                "key": "types_of_record",
                "field": "type_of_record",
            },
        ]

        # return the correct lambda func for sorting "by value" query results
        # based on the whether a third element in the array list is included
        def get_order_by_func(include_id_and_acronym):
            if include_id_and_acronym:
                return lambda w, x, y, z: desc(x)
            else:
                return lambda x, y: desc(y)

        # return the appropriate "by value" query given whether to include the
        # ID field or not
        def get_query_body(include_id_and_acronym, link_field, field_items):
            order_by_func = get_order_by_func(include_id_and_acronym)
            if include_id_and_acronym:
                return select(
                    (
                        getattr(j, link_field),
                        coalesce(j.acronym, ""),
                        count(i),
                        j.id,
                    )
                    for i in field_items
                    for j in getattr(i, field)
                    if getattr(j, link_field) not in exclude
                    and (getattr(j, link_field) is not None or allow_none)
                ).order_by(order_by_func)[:][:]
            else:
                return select(
                    (getattr(j, link_field), count(i))
                    for i in field_items
                    for j in getattr(i, field)
                    if getattr(j, link_field) not in exclude
                    and (getattr(j, link_field) is not None or allow_none)
                ).order_by(order_by_func)[:][:]

        # init output dict
        output = dict()

        # iterate on each filter category and define the number of unique items
        # in it overall and by value, except those in `exclude`
        for d in to_check:
            # init key params
            field = d["field"]
            filter_field = d.get("filter_field", field)
            key = d.get("key", d["field"])
            is_linked = "link_field" in d
            is_date_part = d.get("is_date_part", False)

            # get `items` to use for this category
            field_items = self.__get_items_without_filter(
                items=all_items,
                filters=filters,
                filter_to_skip=filter_field,
                search_text=search_text,
            )

            # init output dict section
            output[key] = dict()

            if is_date_part:
                # error handling
                if "link_field" not in d:
                    raise KeyError(
                        "Must define a `link_field` value for date"
                        " parts, e.g., 'year'"
                    )

                link_field = d["link_field"]  # the date part, e.g., `year`

                # get unique count of items that meet exclusion criteria
                unique_count = select(
                    i
                    for i in field_items
                    if str(getattr(getattr(i, field), link_field))
                    not in exclude
                    and (
                        str(getattr(getattr(i, field), link_field)) is not None
                        or allow_none
                    )
                ).count()
                output[key]["unique"] = unique_count

                by_value_counts = select(
                    (getattr(getattr(i, field), link_field), count(i))
                    for i in field_items
                    if str(getattr(getattr(i, field), link_field))
                    not in exclude
                    and (
                        str(getattr(getattr(i, field), link_field)) is not None
                        or allow_none
                    )
                ).order_by(get_order_by_func(False))[:][:]
                output[key]["by_value"] = by_value_counts

            # count linked fields specially
            elif is_linked:
                link_field = d["link_field"]
                include_id_and_acronym = d.get("include_id_and_acronym", False)

                # get unique count of items that meet exclusion criteria
                unique_count = select(
                    i.id
                    for i in field_items
                    for j in getattr(i, field)
                    if getattr(j, link_field) not in exclude
                    and (getattr(j, link_field) is not None or allow_none)
                ).count()
                output[key]["unique"] = unique_count

                by_value_counts = get_query_body(
                    include_id_and_acronym, link_field, field_items
                )
                output[key]["by_value"] = by_value_counts

            # count standard fields
            else:
                # get unique count of items that meet exclusion criteria
                unique_count = select(
                    i.id
                    for i in field_items
                    if getattr(i, field) not in exclude
                    and (getattr(i, field) is not None or allow_none)
                ).count()
                output[key]["unique"] = unique_count

                by_value_counts = select(
                    (getattr(i, field), count(i))
                    for i in field_items
                    if getattr(i, field) not in exclude
                    and (getattr(i, field) is not None or allow_none)
                ).order_by(get_order_by_func(False))[:][:]
                output[key]["by_value"] = by_value_counts

        return output

    @db_session
    def __get_items_without_filter(
        self,
        items: Query = None,
        filters: dict = {},
        filter_to_skip: str = None,
        search_text: str = None,
    ) -> Query:
        """Return item query using all filters in all fields except for one.

        Args:
            items (Query, optional): The items query. Defaults to None.

            filters (dict, optional): Filters to apply. Defaults to {}.

            filter_to_skip (str, optional): The filter field for which counts
            are needed. Defaults to None.

            search_text (str, optional): Text to search by. Defaults to None.

        Returns:
            Query: Item query without filters in the defined field.
        """

        filters_without_skipped: dict = {
            k: v for (k, v) in filters.items() if k != filter_to_skip
        }

        filtered_items: Query = schema.apply_filters_to_items(
            items=items,
            filters=filters_without_skipped,
            search_text=search_text,
        )
        return filtered_items
