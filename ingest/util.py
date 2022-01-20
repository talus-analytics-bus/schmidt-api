"""Ingest utility methods"""
# standard packages
from datetime import date
import urllib3
import certifi

# 3rd party modules
import boto3
import pprint
from pony.orm import db_session, commit, select
from pony.orm.core import EntityMeta
from alive_progress import alive_bar

# constants
pp = pprint.PrettyPrinter(indent=4)

# define S3 client used for adding / checking for files in the S3
# storage bucket
S3_BUCKET_NAME = "schmidt-storage"

# define colors for printing colorized terminal text


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


special_fields = ("home_rule", "dillons_rule")


def find_all(i, filter_func):
    """Finds all instances in iterable `i` for which func `filter_func`
    returns True, returns emptylist otherwise.

    Parameters
    ----------
    i : type
        Description of parameter `i`.
    filter_func : type
        Description of parameter `filter_func`.

    Returns
    -------
    type
        Description of returned object.

    """
    return list(filter(filter_func, i))


@db_session
def upsert(cls, get: dict, set: dict = None, skip: list = []):
    """Insert or update record into specified class based on checking for
    existence with dictionary data field map `get`, and creating with
    data based on values in dictionaries `get` and `set`, skipping any
    data fields defined in `skip`.

    Parameters
    ----------
    cls : type
        Description of parameter `cls`.
    get : dict
        Description of parameter `get`.
    set : dict
        Description of parameter `set`.
    skip : list
        Description of parameter `skip`.

    Returns
    -------
    type
        Description of returned object.

    """

    def conv(value, x):
        """Convert value to string, parsing bools specially.

        Parameters
        ----------
        value : type
            Description of parameter `value`.
        x : type
            Description of parameter `x`.

        Returns
        -------
        type
            Description of returned object.

        """
        if type(value) == bool:
            if x is True or x is False:
                return x
            if x == "":
                return False
            else:
                return None
        elif iterable(value):
            if not iterable(x):
                return x
            else:
                return "; ".join(x)
        else:
            return x

    # does the object exist
    assert isinstance(
        cls, EntityMeta
    ), "{cls} is not a database entity".format(cls=cls)

    # if no set dictionary has been specified
    set = set or {}

    if not cls.exists(**get):
        # make new object
        return ("insert", cls(**set, **get))
    else:
        # get the existing object
        obj = cls.get(**get)
        action = "none"
        for key, value in set.items():
            if key in skip:
                continue

            # Determine whether an update or an insert occurred
            db_value = getattr(obj, key)
            db_value_str = str(conv(db_value, db_value)).strip()
            upsert_value = value
            upsert_value_str = str(conv(db_value, upsert_value)).strip()
            true_update = (
                upsert_value_str != db_value_str and upsert_value != db_value
            )

            if true_update:
                action = "update"

            # special cases
            if key in special_fields:
                cur_val = getattr(obj, key)
                if cur_val != "" and cur_val is not None:
                    continue
            obj.__setattr__(key, value)

        commit()
        return (action, obj)


def download_file(
    download_url: str,
    fn: str = None,
    write_path: str = None,
    as_object: bool = True,
):
    """Download the PDF at the specified URL and either save it to disk or
    return it as a byte stream.

    Parameters
    ----------
    download_url : type
        Description of parameter `download_url`.
    fn : type
        Description of parameter `fn`.
    write_path : type
        Description of parameter `write_path`.
    as_object : type
        Description of parameter `as_object`.

    Returns
    -------
    type
        Description of returned object.

    """
    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED", ca_certs=certifi.where()
    )
    user_agent = "Mozilla/5.0"
    try:
        response = http.request(
            "GET", download_url, headers={"User-Agent": user_agent}
        )
        if response is not None and response.data is not None:
            if as_object:
                return response.data
            else:
                with open(write_path + fn, "wb") as out:
                    out.write(response.data)
                return True
    except Exception:
        return None
    else:
        print("Error when downloading PDF (404)")
        return False


def iterable(obj):
    """Return True if `obj` is iterable, like a string, set, or list,
    False otherwise.

    """
    try:
        iter(obj)  # TODO optimize since this is likely slow
    except Exception:
        return False
    else:
        return type(obj) != str


def str_to_bool(x):
    """Convert yes/no val `x` to True/False, or None otherwise."""
    if x == "Yes":
        return True
    elif x == "No":
        return False
    else:
        return None


def get_s3_bucket_keys(s3_bucket_name: str):
    """For the given S3 bucket, return all file keys, i.e., filenames.

    Parameters
    ----------
    s3_bucket_name : str
        Name of S3 bucket.

    Returns
    -------
    type
        Description of returned object.

    """
    s3 = boto3.client("s3")

    nextContinuationToken = None
    keys = list()
    more_keys = True

    # while there are still more keys to retrieve from the bucket
    while more_keys:

        # use continuation token if it is defined
        response = None
        if nextContinuationToken is not None:
            response = s3.list_objects_v2(
                Bucket=S3_BUCKET_NAME,
                ContinuationToken=nextContinuationToken,
            )

        # otherwise it is the first request for keys, so do not include it
        else:
            response = s3.list_objects_v2(
                Bucket=S3_BUCKET_NAME,
            )

        # set continuation key if it is provided in the response,
        # otherwise do not since it means all keys have been returned
        if "NextContinuationToken" in response:
            nextContinuationToken = response["NextContinuationToken"]
        else:
            nextContinuationToken = None

        # for each response object, extract the key and add it to the
        # full list
        if "KeyCount" in response and response["KeyCount"] == 0:
            return list()
        else:
            for d in response["Contents"]:
                keys.append(d["Key"])

            # are there more keys to pull from the bucket?
            more_keys = nextContinuationToken is not None

    # return master list of all bucket keys
    return keys


# define date type data field in model `Item` based on internal
# research notes about date precision


@db_session
def set_date_types(db):
    items_by_date_type = select(
        (
            i,
            "MONTH" in i.internal_research_note,
            "YEAR" in i.internal_research_note,
        )
        for i in db.Item
    )

    with alive_bar(
        len(items_by_date_type), title="Assigning date types"
    ) as bar:
        for item, month_only, year_only in items_by_date_type:
            bar()
            if item.date is None:
                item.date_type = -1
            elif month_only:
                item.date_type = 1
            elif year_only:
                item.date_type = 2
            else:
                item.date_type = 0


def get_suffixed_fn(prefix: str, ext: str = "") -> str:
    """Return filename consisting of prefix suffixed with today's date

    Args:
        prefix (str): The prefix

    Returns:
        str: The filename
    """
    today_date: str = str(date.today())
    fn_suffix: str = prefix + "_" + today_date + ext
    return fn_suffix
