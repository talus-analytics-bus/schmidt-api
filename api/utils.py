# Standard libraries
import functools
import json
import pytz
from collections import defaultdict
from datetime import date

# Third party libraries
import pprint
import flask
from flask import Response
from pony.orm.core import QueryResult
from werkzeug.exceptions import NotFound

# Local libraries
from .db_models import db

# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)

only = {
    'Item': [
        'id',
        'title',
        'type_of_record',
        'date',
        'authors',
        'files',
        'key_topics'
    ],
    'File': [
        'id',
        'num_bytes',
        'filename',
    ],
    'Author': [
        'id',
        'authoring_organization',
        'type_of_authoring_organization',
        'if_national_country_of_authoring_org',
        'authoring_organization_has_governance_authority',
    ],
    'Funder': [
        'id',
        'name',
    ],
    'Event': [
        'id',
        'name',
    ],
    'Tag': [
        'name',
    ],
}


def jsonify_custom(obj):
    """Define how related entities should be represented as JSON.

    Parameters
    ----------
    obj : type
        Description of parameter `obj`.

    Returns
    -------
    type
        Description of returned object.

    """
    if isinstance(obj, set):
        return list(obj)
        raise TypeError
    elif isinstance(obj, db.File):
        return obj.to_dict(only=only['File'])
    elif isinstance(obj, db.Author):
        return obj.to_dict(only=only['Author'])
    elif isinstance(obj, db.Funder):
        return obj.to_dict(only=only['Funder'])
    elif isinstance(obj, db.Event):
        return obj.to_dict(only=only['Event'])
    elif isinstance(obj, db.Item):
        return obj.to_dict(
            only=only['Item'],
            with_collections=True,
            related_objects=True,
        )
    elif isinstance(obj, db.Tag):
        return obj.name
    elif isinstance(obj, date):
        return str(obj)


def get_str_from_datetime(dt, t_res, strf_str):
    """Given dt `datetime` instance and temporal resolution return correct string
    representation of the instance.

    Parameters
    ----------
    dt : type
        Description of parameter `dt`.
    t_res : type
        Description of parameter `t_res`.
    strf_str : type
        Description of parameter `strf_str`.

    Returns
    -------
    type
        Description of returned object.

    """
    dt_utc = dt.astimezone(pytz.utc)
    if t_res == 'yearly':
        return str(dt_utc.year)
    else:
        return dt_utc.strftime(strf_str)

# Returns true if database entity class instance's attribute contains a value
# in the filter set, false otherwise.


def passes_filters(instance, filters):
    instancePasses = True
    for filterSetName in filters:

        # Get filter set
        filterSet = set(filters[filterSetName])

        # Get instance attribute values
        instanceSetTmp = getattr(instance, filterSetName)

        # If wrong type, cast to set
        instanceSet = None
        if type(instanceSetTmp) != set:
            instanceSet = set([instanceSetTmp])
        else:
            instanceSet = instanceSetTmp

        # If instance fails one filter, it fails completely.
        if len(instanceSet & filterSet) == 0:
            instancePasses = False
    return instancePasses

# A decorator to format API responses (Query objects) as
# { data: [{...}, {...}] }


def format_response(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # try:
        # Load unformatted data from prior function return statement.
        unformattedData = func(*args, **kwargs)

        # Init formatted data.
        formattedData = []

        # If the type of unformatted data was a query result, parse it as
        # items in a dictionary.
        if type(unformattedData) == QueryResult:
            formattedData = [r.to_dict() for r in unformattedData]

        # If dict, return as-is
        elif type(unformattedData) in (dict, defaultdict):
            formattedData = unformattedData

        elif type(unformattedData) == Response:
            formattedData = unformattedData

        # Otherwise, it is a tuple or list, and should be returned directly.
        else:
            formattedData = unformattedData[:]
        results = {
            "data": formattedData, "error": False, "message": "Success"
        }

        # # If there was an error, return it.
        # except NotFound:
        #     results = {
        #         "data": request.path, "error": True, "message": "404 - not found"
        #     }
        # except Exception as e:
        #     print(e)
        #     results = {
        #         "data": '',
        #         "error": True,
        #         "message": str(e),
        #     }

        # Convert entire response to JSON and return it.
        return json.loads(json.dumps(results, default=jsonify_custom))
        # return flask.jsonify(results)

    # Return the function wrapper (allows a succession of decorator functions to
    # be called)
    return wrapper
