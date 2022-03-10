from typing import List
from flask_restplus import Namespace


namespaces: List[Namespace] = [
    Namespace(
        "Item",
        description="Get data about Items in the HSN database.",
        path="/",
    ),
    Namespace(
        "Metadata",
        description="Get codelists for data attributes.",
        path="/",
    ),
    Namespace(
        "Search",
        description="Search Items, Authors, and Topics by text matching.",
        path="/",
    ),
    Namespace(
        "Downloads",
        description="Download data (.xlsx).",
        path="/",
    ),
    Namespace(
        "Deprecated",
        description="Deprecated methods.",
        path="/",
    ),
]

item, metadata, search, downloads, deprecated = namespaces
