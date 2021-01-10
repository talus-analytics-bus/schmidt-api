# Standard libraries
import functools
import json
import pytz
import traceback
import logging
from collections import defaultdict, OrderedDict, Callable
from datetime import date

# Third party libraries
import pprint
import flask
from flask import Response
from pony.orm.core import QueryResult, Set
from werkzeug.exceptions import NotFound

# Local libraries
from .db_models import db


# pretty printing: for printing JSON objects legibly
pp = pprint.PrettyPrinter(indent=4)

only = {
    'Item': [
        'id',
        'title',
        'description',
        'type_of_record',
        'date',
        'funders',
        'authors',
        'events',
        'files',
        'key_topics',
        'authoring_organization_has_governance_authority',
        'link',
        'exclude_pdf_from_site'
    ],
    'File': [
        'id',
        'num_bytes',
        'filename',
        's3_filename',
        'has_thumb',
    ],
    'Author': [
        'id',
        'authoring_organization',
        'type_of_authoring_organization',
        'if_national_country_of_authoring_org',
        'if_national_iso2_of_authoring_org',
        'acronym',
    ],
    'Funder': [
        'id',
        'name',
    ],
    'Event': [
        'id',
        'name',
    ],
    'Tag': 'name'
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
    elif isinstance(obj, db.Tag):
        return getattr(obj, only['Tag'])
    elif isinstance(obj, db.Item):
        return obj.to_dict(
            only=only['Item'],
            with_collections=True,
            related_objects=True,
        )
    elif isinstance(obj, date):
        return str(obj)
    elif type(obj).__name__ == 'TagSet':
        return "; ".join([d.name for d in obj])
    else:
        print(obj)


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


def passes_filters(instance, filters):
    """Returns true if database entity class instance's attribute contains a
    value in the filter set, false otherwise.

    Parameters
    ----------
    instance : type
        Description of parameter `instance`.
    filters : type
        Description of parameter `filters`.

    Returns
    -------
    type
        Description of returned object.

    """
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


def is_error(d):
    # does this dict represent an error?
    return d.get('is_error', False)


def format_response(func):
    # A decorator to format API responses (Query objects) as
    # { data: [{...}, {...}] }
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Load unformatted data from prior function return statement.
        unformattedData = None
        status_code = None
        try:
            # get unformatted data
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
        except Exception as e:
            exc = traceback.format_exc()
            logging.error(exc)
            results = {
                "data": None, "error": True,
                "message": e.__class__.__name__ + ': ' + e.args[0],
                "traceback": exc
            }
            status_code = 500

        # Convert entire response to JSON and return it.
        json_response = json.loads(json.dumps(results, default=jsonify_custom))
        if status_code is not None:
            return json_response, status_code
        else:
            return json_response

    # Return the function wrapper (allows a succession of decorator functions to
    # be called)
    return wrapper


def jsonify_response(func):
    """Decorator to ensure all PonyORM entities in a schema function response
    are converted to dicts per the rules in `jsonify_custom` above.

    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Load unformatted data from prior function return statement.
        results = func(*args, **kwargs)

        # Convert entire response to JSON and return it.
        return json.loads(json.dumps(results, default=jsonify_custom))

    # Return the function wrapper (allows a succession of decorator functions to
    # be called)
    return wrapper


class DefaultOrderedDict(OrderedDict):
    # Source: http://stackoverflow.com/a/6190500/562769
    def __init__(self, default_factory=None, *a, **kw):
        if (default_factory is not None and
                not isinstance(default_factory, Callable)):
            raise TypeError('first argument must be callable')
        OrderedDict.__init__(self, *a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        if self.default_factory is None:
            args = tuple()
        else:
            args = self.default_factory,
        return type(self), args, None, None, self.items()

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)

    def __deepcopy__(self, memo):
        import copy
        return type(self)(self.default_factory,
                          copy.deepcopy(self.items()))

    def __repr__(self):
        return 'OrderedDefaultDict(%s, %s)' % (self.default_factory,
                                               OrderedDict.__repr__(self))
