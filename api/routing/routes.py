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
from ..utils import format_response, get_str_from_datetime

strf_str = '%Y-%m-%d %H:%M:%S %Z'

# Initialize metric catalog or specifics endpoint
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
        return {data: "Test successful", success: True}
