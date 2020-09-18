# Standard libraries
from datetime import datetime
from collections import defaultdict

# Third party libraries
from flask import request
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


# define body model for search and item routes to allow filters and ordering
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
        'ordering': {
            '$id': '#/properties/ordering',
            'type': 'array',
            'title': 'The ordering schema',
            'description': 'An explanation about the purpose of this instance.',
            'default': [['colname', 'dir']],
            'examples': [
                [
                    [
                        'colname',
                        'dir'
                    ]
                ]
            ],
            'additionalItems': True,
            'items': {
                '$id': '#/properties/ordering/items',
                'anyOf': [
                    {
                        '$id': '#/properties/ordering/items/anyOf/0',
                        'type': 'array',
                        'title': 'The first anyOf schema',
                        'description': 'An explanation about the purpose of this instance.',
                        'default': [],
                        'examples': [
                            [
                                'colname',
                                'dir'
                            ]
                        ],
                        'additionalItems': True,
                        'items': {
                            '$id': '#/properties/ordering/items/anyOf/0/items',
                            'anyOf': [
                                {
                                    '$id': '#/properties/ordering/items/anyOf/0/items/anyOf/0',
                                    'type': 'string',
                                    'title': 'The first anyOf schema',
                                    'description': 'An explanation about the purpose of this instance.',
                                    'default': '',
                                    'examples': [
                                        'colname',
                                        'dir'
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }
        }
    },
    'type': 'object'
})


@api.route("/get/items", methods=["POST"])
class Items(Resource):
    # setup parser with pagination
    parser = api.parser()
    # add search text arg and pagination args
    add_search_args(parser)
    add_pagination_args(parser)

    @api.doc(parser=parser, body=body_model)
    @db_session
    @format_response
    def post(self):
        data = schema.get_items(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000))
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


@api.route("/get/file", methods=["GET"])
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
    def get(self):
        data = schema.get_file(
            id=int(request.args.get('id', 1)),
            get_thumb=request.args.get('get_thumb', "false") == "true",
        )
        return data


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

    @api.doc(parser=parser, body=body_model)
    @db_session
    @format_response
    def post(self):
        # get request body containing filters, ordering, etc.
        body = request.get_json()
        filters = body['filters'] if 'filters' in body else {}

        return schema.get_search(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000)),
            filters=filters,
            search_text=request.args.get('search_text', None),
            preview=request.args.get('preview', 'false') == 'true',
            explain_results=request.args.get(
                'explain_results', 'false') == 'true',
        )


@api.route("/test", methods=["GET"])
class Test(Resource):
    """Test route."""
    parser = api.parser()
    parser.add_argument(
        'argument_name',
        type=str,
        required=False,
        help="""Description of argument"""
    )

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        return {'text': "Test successful"}
