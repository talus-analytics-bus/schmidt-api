# Standard libraries

# Third party libraries
from flask import request, send_file, Response
from flask_restplus import Resource

# from flask_restplus.api import Api
from pony.orm import db_session

# Local libraries
from api import schema
from api.namespaces import item, metadata, search, downloads, deprecated
from api.main import app, api
from api.routing.models import ItemBody, SearchResponse
from api.utils import format_response
from api.metadatacounter.core import MetadataCounter


def add_search_args(parser):
    """Add search text arguments to `parser`.

    Parameters
    ----------
    parser : type
        Description of parameter `parser`.

    Returns
    -------
    type
        Description of returned object.

    """
    parser.add_argument(
        "search_text",
        type=str,
        required=False,
        help="""Search string to query matches with""",
    )
    parser.add_argument(
        "explain_results",
        type=bool,
        required=False,
        help="If True, will include which metadata fields matched the text",
    )


def add_pagination_args(parser):
    """Add pagination arguments to the provided `parser`.

    Parameters
    ----------
    parser : type
        Description of parameter `parser`.

    Returns
    -------
    type
        Description of returned object.

    """
    parser.add_argument(
        "page",
        type=int,
        required=False,
        help="""Optional: Page number. Defaults to null (no pagination).""",
    )
    parser.add_argument(
        "pagesize",
        type=int,
        required=False,
        help="""Optional: Page size. Defaults to null (no pagination).""",
    )


def add_ordering_args(parser):
    """Add ordering arguments to the provided `parser`.

    Parameters
    ----------
    parser : type
        Description of parameter `parser`.

    Returns
    -------
    type
        Description of returned object.

    """
    parser.add_argument(
        "order_by",
        type=str,
        required=False,
        default=None,
        choices=("date", "title", "relevance"),
        help="""Optional: Attribute to order by, currently one of date, title, or relevance. Defaults to null (no ordering).""",
    )
    parser.add_argument(
        "is_desc",
        type=bool,
        help="Optional: True if ordering should be descending order, false if ascending. Defaults to null (no ordering).",
    )


# define body model for search and item routes to allow filters
body_model = api.schema_model(
    "Body_Model",
    {
        "properties": {
            "filters": {
                "$id": "#/properties/filters",
                "type": "object",
                "title": "The filters schema",
                "description": "An explanation about the purpose of "
                "this instance.",
                "default": {"search_text": ["acad"]},
                "examples": [{"search_text": ["acad"]}],
                "required": [],
            },
        },
        "type": "object",
    },
)


def get_int_list(str_list):
    """Given list of strings, return integer representations as list.

    Parameters
    ----------
    str_list : type
        Description of parameter `str_list`.

    Returns
    -------
    type
        Description of returned object.

    """

    def to_int(x):
        return int(x)

    return list(map(to_int, str_list))


@deprecated.route(
    "/get/items",
    methods=["GET"],
)
@item.route(
    "/items",
    methods=["GET"],
)
class Items(Resource):
    # setup parser with pagination
    parser = api.parser()

    # add search text arg and pagination args
    add_pagination_args(parser)
    add_ordering_args(parser)

    @item.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        """Get lists of Items, optionally paginated."""
        ids = get_int_list(request.args.getlist("ids"))

        data = schema.get_items(
            page=int(request.args.get("page", 1)),
            pagesize=int(request.args.get("pagesize", 10000000)),
            order_by=request.args.get("order_by", None),
            is_desc=request.args.get("is_desc", "false") == "true",
            ids=ids,
        )
        return data


@item.route("/items/<id>", methods=["GET"])
class Item(Resource):
    # setup parser with pagination
    parser = api.parser()

    @api.doc(parser=parser, params={"id": "Unique ID of item to fetch."})
    @db_session
    @format_response
    def get(self, id: int):
        """Get detailed Item data by its ID."""
        data = schema.get_item(
            page=1,
            pagesize=10000000,
            id=id,
            include_related=False,
        )
        return data


@deprecated.route("/get/item", methods=["GET"])
class Item(Resource):
    # setup parser with pagination
    parser = api.parser()

    add_pagination_args(parser)
    parser.add_argument(
        "id", type=int, required=False, help="""Unique ID of item to fetch"""
    )
    parser.add_argument(
        "include_related",
        type=bool,
        required=False,
        help="""Include related item data in response?""",
    )

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        id_tmp: str = request.args.get("id")
        id: int = int(id_tmp) if id_tmp is not None else None
        data = schema.get_item(
            page=int(request.args.get("page", 1)),
            pagesize=int(request.args.get("pagesize", 10000000)),
            id=id,
            include_related=request.args.get("include_related", "false")
            == "true",
        )
        return data


@metadata.route("/metadata", methods=["GET"])
@deprecated.route(
    "/get/metadata",
    methods=["GET"],
)
class Metadata(Resource):
    @db_session
    @format_response
    def get(self):
        """Get codelist possible values and their definitions."""
        return schema.get_metadata()


@downloads.route("/file/<title>", methods=["GET"])
@deprecated.route("/get/file/<title>", methods=["GET"])
class File(Resource):
    # setup parser
    parser = api.parser()
    parser.add_argument(
        "id", type=int, required=True, help="""Unique ID of file to fetch"""
    )

    @api.doc(
        parser=parser, params={"title": "The title to download the File with"}
    )
    @db_session
    def get(self, title: str):
        """Download the File with the given ID using the provided title"""
        try:
            details = schema.get_file(
                id=int(request.args.get("id", 1)),
                get_thumb=request.args.get("get_thumb", "false") == "true",
            )
        except Exception:
            return Response("No File found with that ID", status=404)
        data = details["data"]
        data.seek(0)
        return send_file(
            data,
            attachment_filename=details["attachment_filename"],
            as_attachment=details["as_attachment"],
        )


@search.route("/search", methods=["POST"])
@deprecated.route("/get/search", methods=["POST"])
class Search(Resource):

    parser = api.parser()
    parser.add_argument(
        "preview",
        type=bool,
        required=False,
        help="If True, preview of search results only, with counts of Items"
        " rather than Item data",
    )
    # add search text arg
    add_search_args(parser)

    # add pagination arguments to parser
    add_pagination_args(parser)

    # add ordering (sorting) arguments to parser
    add_ordering_args(parser)

    @api.doc(
        parser=parser,
        body=ItemBody,
        responses={
            "200": (
                "Pagination information and a list of Items will be returned.",
                SearchResponse,
            )
        },
    )
    @db_session
    @format_response
    def post(self):
        """Get search results or preview of them."""
        # get request body containing filters
        body = request.get_json()
        filters = body["filters"] if "filters" in body else {}

        # get search_text or set to None if blank
        search_text = request.args.get("search_text", None)
        if search_text == "":
            search_text = None

        return schema.get_search(
            page=int(request.args.get("page", 1)),
            pagesize=int(request.args.get("pagesize", 10000000)),
            filters=filters,
            search_text=search_text,
            order_by=request.args.get("order_by", None),
            is_desc=request.args.get("is_desc", "false") == "true",
            preview=request.args.get("preview", "false") == "true",
            explain_results=request.args.get("explain_results", "false")
            == "true",
        )


@search.route("/search/counts", methods=["GET"])
@deprecated.route("/get/filter_counts", methods=["GET"])
class Filter_Counts(Resource):

    parser = api.parser()

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        """Given search text, get count of results by filter attribute."""

        # get search text if any
        search_text = request.args.get("search_text", None)

        # get ids of items from URL params
        exclude = request.args.getlist("exclude")
        counter: MetadataCounter = MetadataCounter()
        return counter.get_metadata_value_counts(
            items=None, exclude=exclude, filters={}, search_text=search_text
        )


# XLSX download of items data
@downloads.route("/items/xlsx", methods=["GET"])
@deprecated.route("/get/export/excel", methods=["GET"])
class ExportExcelGet(Resource):

    parser = api.parser()

    @api.doc(parser=parser)
    @db_session
    def get(self):
        """Return XLSX file of data with specified filters applied."""

        params = request.args

        # get ids of items from URL params, if they exist
        ids = get_int_list(params.getlist("ids"))
        filters = {"id": ids} if len(ids) > 0 else dict()
        search_text = params.get("search_text", None)

        send_file_args = schema.export(
            filters=filters,
            search_text=search_text,
        )
        return send_file(
            send_file_args["content"],
            attachment_filename=send_file_args["attachment_filename"],
            as_attachment=True,
        )


@downloads.route("/items/xlsx", methods=["POST"])
@deprecated.route("/post/export/excel", methods=["POST"])
class ExportExcelPost(Resource):

    parser = api.parser()

    @api.doc(parser=parser)
    @db_session
    def post(self):
        """Return XLSX file of data with specified filters applied."""

        # get request body containing filters
        params = request.args
        body = request.get_json()
        filters = body["filters"] if "filters" in body else {}
        search_text = params.get("search_text", None)

        send_file_args = schema.export(
            filters=filters,
            search_text=search_text,
        )
        return send_file(
            send_file_args["content"],
            attachment_filename=send_file_args["attachment_filename"],
            as_attachment=True,
        )
