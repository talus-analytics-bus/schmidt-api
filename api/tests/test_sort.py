from datetime import date
from re import search
from typing import Any, List
from typing_extensions import Unpack
from pony.orm import db_session

from api import schema
from .helpers import generate_mapping


@db_session
@generate_mapping
def test_sort_by_date():
    """Pages of items should be sorted by ascending date correctly"""
    validate_date_sorting(False)
    validate_date_sorting(True)


def validate_date_sorting(is_desc: bool):
    print("\n" + "-" * 88)
    print(f"""Testing {'descending' if is_desc else 'ascending'} date sort""")
    print("-" * 88)
    # setup tests
    kwargs: Any = dict(
        pagesize=5,
        order_by="date",
        is_desc=is_desc,
        explain_results=False,
        filters={"key_topics": ["Medical preparedness / emergency response"]},
    )
    search_results_page_1 = schema.get_search(page=1, **kwargs)
    search_results_page_2 = schema.get_search(page=2, **kwargs)
    search_results_page_8 = schema.get_search(page=8, **kwargs)
    all_search_results_items = (
        search_results_page_1["data"]
        + search_results_page_2["data"]
        + search_results_page_8["data"]
    )
    __check_items(all_search_results_items, is_desc=is_desc)


def __check_items(all_search_results_items: list, is_desc: bool):
    prev_item = all_search_results_items[0]
    for item in all_search_results_items[1:]:
        cur_item_date: date = item["date"]
        prev_item_date: date = prev_item["date"]
        print(f"""Year: {prev_item_date.year} vs. {cur_item_date.year}""")
        assert (not is_desc and (prev_item_date.year <= cur_item_date.year)) or (
            is_desc and (prev_item_date.year <= cur_item_date.year)
        )

        if prev_item_date.year == cur_item_date.year:
            print(f"""\tMonth: {prev_item_date:%b %Y} vs. {cur_item_date:%b %Y}""")
            assert (not is_desc and (prev_item_date.month <= cur_item_date.month)) or (
                is_desc and (prev_item_date.month >= cur_item_date.month)
            )

            if prev_item_date.month == cur_item_date.month:
                print(
                    f"""\t\tDate: {prev_item_date:%b %d, %Y} vs. {cur_item_date:%b %d, %Y}"""
                )
                assert (not is_desc and (prev_item_date.day <= cur_item_date.day)) or (
                    is_desc and (prev_item_date.day >= cur_item_date.day)
                )

        prev_item = item
