##
# # API schema
##

# Standard libraries
import functools
import pytz
import re
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# Third party libraries
import pprint
from pony.orm import select, db_session, raw_sql, distinct, count
from flask import send_file

# Local libraries
from .db_models import db
from .utils import passes_filters

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)


@db_session
def get_items(
    page=1,
    pagesize=1000000,
):
    q = select(
        i for i in db.Item
    )
    total = count(q)
    q_page = q.page(page, pagesize=pagesize)[:][:]
    only = ('id', 'title', 'description')
    data = [d.to_dict(only=only) for d in q_page]
    return {
        'data': data,
        'page': page,
        'pagesize': pagesize,
        'total': total,
        'num': len(data)
    }
# TODO functions
