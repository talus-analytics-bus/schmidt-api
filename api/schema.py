##
# # API schema
##

# Standard libraries
import functools
import pytz
import re
import math
from datetime import datetime, timedelta, date
from io import BytesIO
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# Third party libraries
import boto3
import pprint
from pony.orm import select, db_session, raw_sql, distinct, count
from flask import send_file

# Local libraries
from .db_models import db
from .utils import passes_filters

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)
s3 = boto3.client('s3')


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


@db_session
def get_file(id: int, get_thumb: bool):
    """Serves the file from S3 that corresponds to the File instances with
    the specified id.

    Parameters
    ----------
    id : int
        Unique ID of the File instance which corresponds to the S3 file to
        be served.

    """

    # define filename from File instance field
    file = db.File[id]
    key = file.s3_filename if not get_thumb else file.s3_filename + '_thumb'

    # retrieve file and write it to IO file object `data`
    # if the file is not found in S3, return a 404 error
    data = BytesIO()
    try:
        s3.download_fileobj('schmidt-storage', key, data)
    except Exception as e:
        print('e')
        print(e)
        return 'Document not found (404)'

    # return to start of IO stream
    data.seek(0)

    # return file with correct media type given its extension
    media_type = 'application'
    if key.endswith('.pdf'):
        media_type = 'application/pdf'

    attachment_filename = file.filename if not get_thumb else \
        file.s3_filename + '_thumb.png'
    return send_file(
        data,
        attachment_filename=attachment_filename,
        as_attachment=False
    )
