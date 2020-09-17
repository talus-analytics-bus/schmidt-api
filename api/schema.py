##
# # API schema
##

# Standard libraries
import functools
import pytz
import re
import math
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
    page,
    pagesize,
):
    # get all items
    q = select(
        i for i in db.Item
    )

    # apply filters
    # TODO

    # apply text search with relevance scoring
    # TODO

    # apply ordering
    # TODO

    # get total num items, pages, etc. for response
    total = count(q)
    q_page = q.page(page, pagesize=pagesize)[:][:]
    num_pages = math.ceil(total / pagesize)

    # convert to dict for response
    only = ('id', 'title', 'key_topics')
    data = [
        d.to_dict(
            only=only,
            # with_collections=True,
            # related_objects=True,
        ) for d in q_page
    ]
    return {
        'data': data,
        'page': page,
        'num_pages': num_pages,
        'pagesize': pagesize,
        'total': total,
        'num': len(data)
    }
