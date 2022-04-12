"""Helpers for test_items.py"""


import functools
from typing import Union, List, Callable, Any

from api.db_models.models import Item
from db.db import db


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


class InvalidItemsError(AssertionError):
    """
    Throw exception if items are invalid and print their IDs and titles.

    """

    def __init__(
        self, invalid_items: List[Item], message: str = "Invalid items found:"
    ):
        """Create new invalid items exception.

        Args:
            invalid_items (List[Item]): The list of invalid items.

            message (str, optional): The message to show before listing
            invalid items. Defaults to "Invalid items found:".
        """
        item: Item = None
        for item in invalid_items:
            message += f"\n    [id = {item.id}]: {item.title}"
        super().__init__(message)
