from re import search
from pony.orm import db_session

from api import schema
from .helpers import generate_mapping


@db_session
@generate_mapping
def test_sort():
    """Pages of items should be sorted by ascending date correctly"""
    filters = {"key_topics": ["Medical preparedness / emergency response"]}
    search_results_page_1 = schema.get_search(
        page=1,
        pagesize=5,
        order_by="date",
        is_desc=False,
        explain_results=False,
        filters=filters,
    )
    search_results_page_2 = schema.get_search(
        page=2,
        pagesize=5,
        order_by="date",
        is_desc=False,
        explain_results=False,
        filters=filters,
    )
    search_results_page_8 = schema.get_search(
        page=8,
        pagesize=5,
        order_by="date",
        is_desc=False,
        explain_results=False,
        filters=filters,
    )
    # print("search_results_page_1")
    # print(search_results_page_1)
    # print("search_results_page_2")
    # print(search_results_page_2)
    all_results = (
        search_results_page_1["data"]
        + search_results_page_2["data"]
        + search_results_page_8["data"]
    )
    prev_item = all_results[0]
    for item in all_results[1:]:
        print(f"""{prev_item["date"].year} vs. {item["date"].year}""")
        assert prev_item["date"].year <= item["date"].year
        prev_item = item
