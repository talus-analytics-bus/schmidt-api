##
# # API and database setup file.
##

# Standard libraries
from datetime import datetime, date

# Third party libraries
from pony.orm import PrimaryKey, Required, Optional, Set, StrArray
from . import db


class Item(db.Entity):
    """Reports, etc.."""
    _table_ = 'item'
    id = PrimaryKey(int, auto=True)
    date = Optional(date)
    type_of_record = Optional(str)
    key_topics = Optional(StrArray)
    title = Required(str)
    description = Optional(str)
    link = Optional(str)
    internal_research_note = Optional(str)
    ra_coder_initials = Optional(str)
    internal_date_of_initial_entry = Optional(datetime)
    final_review = Required(bool)


class Author(db.Entity):
    """Authoring organizations who create items."""
    _table_ = 'author'
    id = PrimaryKey(int, auto=True)
    type_of_authoring_organization = Optional(str)
    authoring_organization = Required(str)
    authoring_organization_sub_organization = Optional(str)
    international_national = Optional(str)
    if_national_country_of_authoring_org = Optional(str)
    authoring_organization_has_governance_authority = Optional(bool)


class Funder(db.Entity):
    """Funders who provide financial support for authoring organizations
    to create items.

    """
    _table_ = 'funder'
    id = PrimaryKey(int, auto=True)
    name = Required(str)


class Event(db.Entity):
    """Events (outbreaks) that may be tagged on items that discuss them."""
    _table_ = 'event'
    id = PrimaryKey(int, auto=True)
    name = Required(str)


class File(db.Entity):
    """Files (usually PDFs) with the content of items."""
    _table_ = 'file'
    id = PrimaryKey(int, auto=True)
    permalink = Required(str)
    filename = Required(str)
    extension = Required(str)
