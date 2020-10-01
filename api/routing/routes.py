# Standard libraries
from datetime import datetime
from collections import defaultdict

# Third party libraries
from flask import request, send_file
from flask_restplus import Resource, fields
from pony.orm import db_session
import pytz

# Local libraries
from ..db_models import db
from ..db import api
from .. import schema
from ..utils import format_response


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
        'search_text',
        type=str,
        required=False,
        help="""Search string to query matches with"""
    )
    parser.add_argument(
        'explain_results',
        type=bool,
        required=False,
        help="""If True, will include which metadata fields matched the text"""
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
        'page',
        type=int,
        required=False,
        help="""Page number"""
    )
    parser.add_argument(
        'pagesize',
        type=int,
        required=False,
        help="""Page size"""
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
        'order_by',
        type=str,
        required=False,
        help="""Attribute to order by, currently date, title, or relevance"""
    )
    parser.add_argument(
        'is_desc',
        type=bool,
        help="""True if ordering should be descending order, false if ascending"""
    )


# define body model for search and item routes to allow filters
body_model = api.schema_model('Body_Model', {
    'properties': {
        'filters': {
            '$id': '#/properties/filters',
            'type': 'object',
            'title': 'The filters schema',
            'description': 'An explanation about the purpose of this instance.',
            'default': {"search_text": ["acad"]},
            'examples': [
                {"search_text": ["acad"]}
            ],
            'required': [],
        },
    },
    'type': 'object'
})

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


@api.route("/get/items", methods=["GET"])
class Items(Resource):
    # setup parser with pagination
    parser = api.parser()

    # add search text arg and pagination args
    add_pagination_args(parser)
    add_ordering_args(parser)

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        # get ids of items from URL params
        ids = get_int_list(request.args.getlist('ids'))

        data = schema.get_items(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000)),
            order_by=request.args.get('order_by', None),
            is_desc=request.args.get('is_desc', 'false') == 'true',
            ids=ids,
        )
        return data


@api.route("/get/item", methods=["GET"])
class Item(Resource):
    # setup parser with pagination
    parser = api.parser()

    add_pagination_args(parser)
    parser.add_argument(
        'id',
        type=int,
        required=False,
        help="""Unique ID of item to fetch"""
    )
    parser.add_argument(
        'include_related',
        type=bool,
        required=False,
        help="""Include related item data in response?"""
    )

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        data = schema.get_item(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000)),
            id=int(request.args.get('id', 1)),
            include_related=request.args.get(
                'include_related', 'false') == 'true'
        )
        return data


@api.route("/get/file/<title>", methods=["GET"])
class File(Resource):
    # setup parser
    parser = api.parser()
    parser.add_argument(
        'id',
        type=int,
        required=False,
        help="""Unique ID of file to fetch"""
    )

    @api.doc(parser=parser)
    @db_session
    def get(self, title: str):
        details = schema.get_file(
            id=int(request.args.get('id', 1)),
            get_thumb=request.args.get('get_thumb', "false") == "true",
        )
        data = details['data']
        data.seek(0)
        return send_file(
            data,
            attachment_filename=details['attachment_filename'],
            as_attachment=details['as_attachment']
        )


@api.route("/get/search", methods=["POST"])
class Search(Resource):
    """Get search results or preview of them."""
    parser = api.parser()
    parser.add_argument(
        'preview',
        type=bool,
        required=False,
        help="""If True, preview of search results only, with counts of items"""
    )
    # add search text arg
    add_search_args(parser)

    # add pagination arguments to parser
    add_pagination_args(parser)

    # add ordering (sorting) arguments to parser
    add_ordering_args(parser)

    @api.doc(parser=parser, body=body_model)
    @db_session
    @format_response
    def post(self):
        # get request body containing filters
        body = request.get_json()
        filters = body['filters'] if 'filters' in body else {}

        # get search_text or set to None if blank
        search_text = request.args.get('search_text', None)
        if search_text == '':
            search_text = None

        return schema.get_search(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000)),
            filters=filters,
            search_text=search_text,
            order_by=request.args.get('order_by', None),
            is_desc=request.args.get('is_desc', 'false') == 'true',
            preview=request.args.get('preview', 'false') == 'true',
            explain_results=request.args.get(
                'explain_results', 'false') == 'true',
        )


@api.route("/get/filter_counts", methods=["GET"])
class Filter_Counts(Resource):
    """Get possible filter values and baseline number of each in dataset."""
    parser = api.parser()

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        return schema.get_metadata_value_counts(None)


# XLSX download of items data
@api.route("/export/excel", methods=["GET"])
class Export(Resource):
    """Return XLSX file of data with specified filters applied."""
    parser = api.parser()

    @api.doc(parser=parser)
    @db_session
    def get(self):
        params = request.args

        # get ids of items from URL params
        ids = get_int_list(params.getlist('ids'))

        filters = {'id': ids}
        # filters = request.json.get('filters')

        send_file_args = schema.export(
            filters=filters,
        )
        return send_file(
            send_file_args['content'],
            attachment_filename=send_file_args['attachment_filename'],
            as_attachment=True
        )
