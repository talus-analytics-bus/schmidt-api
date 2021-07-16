"""Helpers for test_items.py"""


from typing import List
from api.db_models.models import Item


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
