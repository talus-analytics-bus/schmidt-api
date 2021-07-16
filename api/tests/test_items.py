"""Test items for validity"""


# 3rd party modules
from api.tests.helpers import InvalidItemsError
import functools
from typing import Any, Callable, List, Union
from pony.orm import db_session, select
from pony.orm.core import count

# local modules
from api.db_models.models import Item
from api.db import db


def generate_mapping(func: Callable) -> Callable:
    """Decorator func that ensures PonyORM database mapping is generated.

    Args:
        func (Callable): The function decorated.

    Returns:
        Callable: The wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Union[Any, None]:
        try:
            db.generate_mapping()
        except Exception:
            print("Mapping already generated, continuing.")
        return func(*args, **kwargs)

    return wrapper


@db_session
@generate_mapping
def test_final_review():
    """Only allow items that have passed final review."""
    invalid_items: List[Item] = (
        select(i for i in Item if not i.final_review)
    )[:][:]
    try:
        assert len(invalid_items) == 0, (
            str(len(invalid_items)) + " item(s) have not cleared "
            "final review"
        )
    except AssertionError:
        raise InvalidItemsError(
            invalid_items,
            "The following items have not cleared final review. Please "
            "delete them from the database:",
        )


@db_session
@generate_mapping
def test_title_and_desc():
    """Only allow items that have titles and descriptions."""
    invalid_items: List[Item] = (
        select(
            i
            for i in Item
            if i.title.strip() == "" or i.description.strip() == ""
        )
    )[:][:]
    try:
        assert len(invalid_items) == 0, (
            str(len(invalid_items)) + " item(s) lack title(s) and/or desc(s)"
        )
    except AssertionError:
        raise InvalidItemsError(
            invalid_items,
            "The following items lack titles and/or descriptions:",
        )


@db_session
@generate_mapping
def test_pdf_exclusion():
    """Ensures PDFs are excluded from items where appropriate."""
    invalid_items: List[Item] = select(
        i
        for i in Item
        if (count(i.files) > 0 or count(i.related_files) > 0)
        and i.exclude_pdf_from_site
    )[:][:]
    try:
        assert len(invalid_items) == 0, (
            str(len(invalid_items)) + " item(s) include PDFs which should not"
        )
    except AssertionError:
        raise InvalidItemsError(
            invalid_items,
            "The following items include PDFs but are marked as not "
            "being allowed to include them. Please delete the PDFs:",
        )


@db_session
@generate_mapping
def test_covid_expansion():
    """
    Ensures COVID-19 expansion-specific items have appropriate data.

    """

    # items with COVID-specific data should be marked as COVID items
    invalid_items: List[Item] = select(
        i
        for i in Item
        if (count(i.covid_tags) > 0 or count(i.covid_topics) > 0)
        and not i.is_covid_commission_doc
    )[:][:]
    try:
        assert len(invalid_items) == 0, (
            str(len(invalid_items)) + " item(s) include COVID tags which "
            "should not"
        )
    except AssertionError:
        raise InvalidItemsError(
            invalid_items,
            "The following items include COVID tags but are not marked as "
            "COVID Commission documents. Please remove the tags or mark them "
            "as such:",
        )
