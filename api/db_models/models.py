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

    # Attributes
    id = PrimaryKey(int, auto=True)
    internal_date_of_initial_entry = Optional(date, nullable=True)
    date = Optional(date, nullable=True)
    type_of_record = Optional(str)
    key_topics = Set('Tag')
    title = Optional(str, sql_default="'Untitled'", nullable=True)
    description = Optional(str)
    link = Optional(str)
    internal_research_note = Optional(str)
    ra_coder_initials = Optional(str)
    final_review = Required(bool, default=False)
    search_text = Optional(str)
    authoring_organization_has_governance_authority = Optional(bool, nullable=True)

    # Relationships
    authors = Set('Author', table='authors_to_items')
    funders = Set('Funder', table='funders_to_items')
    events = Set('Event', table='events_to_items')
    files = Set('File', table='files_to_items')


class Author(db.Entity):
    """Authoring organizations who create items."""
    _table_ = 'author'

    # Attributes
    id = PrimaryKey(int, auto=True)
    type_of_authoring_organization = Optional(str)
    authoring_organization = Required(str)
    authoring_organization_sub_organization = Optional(str) # TODO
    international_national = Optional(str)
    if_national_country_of_authoring_org = Optional(str, nullable=True)  
    if_national_iso2_of_authoring_org = Optional(str, nullable=True)

    # Relationships
    items = Set('Item', table='authors_to_items')


class Funder(db.Entity):
    """Funders who provide financial support for authoring organizations
    to create items.

    """
    _table_ = 'funder'

    # Attributes
    id = PrimaryKey(int, auto=True)
    name = Required(str)

    # Relationships
    items = Set('Item', table='funders_to_items')


class Event(db.Entity):
    """Events (outbreaks) that may be tagged on items that discuss them."""
    _table_ = 'event'

    # Attributes
    id = PrimaryKey(int, auto=True)
    master_id = Required(str)
    name = Required(str)

    # Relationships
    items = Set('Item', table='events_to_items')


class File(db.Entity):
    """Files (usually PDFs) with the content of items."""
    _table_ = 'file'

    # Attributes
    id = PrimaryKey(int, auto=True)
    source_permalink = Required(str)
    s3_permalink = Optional(str, nullable=True)
    filename = Required(str)
    s3_filename = Required(str)
    mime_type = Required(str)
    source_thumbnail_permalink = Optional(str, nullable=True)
    s3_thumbnail_permalink = Optional(str, nullable=True)
    num_bytes = Optional(int)
    scraped_text = Optional(str, nullable=True)

    # Relationships
    items = Set('Item', table='files_to_items')


class Metadata(db.Entity):
    """Display names, definitions, etc. for fields."""
    _table_ = "metadata"

    # Attributes
    field = Required(str)
    source_name = Required(str)
    order = Required(float)
    display_name = Optional(str)
    colgroup = Optional(str)
    definition = Optional(str)
    possible_values = Optional(str)
    notes = Optional(str)
    export = Required(bool)
    entity_name = Required(str)
    linked_entity_name = Required(str)
    type = Required(str)
    PrimaryKey(entity_name, linked_entity_name, field)


class Tag(db.Entity):
    """Tags for single and multiselects."""
    _table_ = "tag"

    # Attributes
    id = PrimaryKey(int, auto=True)
    name = Required(str)
    field = Required(str)

    # Relationships
    _key_topics = Set('Item')
