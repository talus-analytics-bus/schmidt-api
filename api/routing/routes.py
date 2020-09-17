# Standard libraries
from datetime import datetime
from collections import defaultdict

# Third party libraries
from flask import request
from flask_restplus import Resource
from pony.orm import db_session
import pytz

# Local libraries
from ..db_models import db
from ..db import api
from .. import schema
from ..utils import format_response


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


@api.route("/get/items", methods=["GET"])
class Items(Resource):
    # setup parser with pagination
    parser = api.parser()
    add_pagination_args(parser)

    @api.doc(parser=parser)
    @db_session
    @format_response
    def get(self):
        data = schema.get_items(
            page=int(request.args.get('page', 1)),
            pagesize=int(request.args.get('pagesize', 10000000))
        )
        return data


@api.route("/test", methods=["GET"])
class Test(Resource):
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
