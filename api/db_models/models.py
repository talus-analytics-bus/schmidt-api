##
# Database models.
##

# Standard libraries
from datetime import date

# Third party libraries
from pony.orm import PrimaryKey, Required, Optional, Set
from pony.orm.core import db_session, select
from pony.utils.utils import count
from api.db import db


class Item(db.Entity):
    """Reports, etc."""

    _table_ = "item"

    # Attributes
    id = PrimaryKey(int, auto=True)
    internal_date_of_initial_entry = Optional(date, nullable=True)
    date = Optional(date, nullable=True)
    date_type = Optional(int, nullable=True)
    type_of_record = Optional(str)
    key_topics = Set("KeyTopic")
    title = Optional(str, sql_default="'Untitled'", nullable=True)
    description = Optional(str)
    related_description = Optional(str)
    sub_organizations = Optional(str)
    link = Optional(str)
    internal_research_note = Optional(str)
    ra_coder_initials = Optional(str)
    final_review = Optional(bool, default=False)
    search_text = Optional(str)
    file_search_text = Optional(str)
    authoring_organization_has_governance_authority = Optional(
        bool, nullable=True
    )
    source_id = Optional(str)
    tags = Set("Tag")
    exclude_pdf_from_site = Required(bool, default=False)

    # COVID expansion data fields
    is_covid_commission_doc = Required(bool, default=False)
    field_relationship = Optional("FieldRelationship")
    geo_specificity = Optional("GeoSpecificity")
    covid_topics = Set("CovidTopic")
    covid_tags = Set("CovidTag")

    # Relationships
    authors = Set("Author", table="authors_to_items")
    funders = Set("Funder", table="funders_to_items")
    events = Set("Event", table="events_to_items")
    files = Set("File", table="files_to_items", reverse="items")
    related_files = Set(
        "File", table="related_files_to_items", reverse="related_items"
    )
    items = Set("Item", table="items_to_items", reverse="_items")
    _items = Set("Item", table="items_to_items")


class Author(db.Entity):
    """Authoring organizations who create items."""

    _table_ = "author"

    # Attributes
    id = PrimaryKey(int, auto=True)
    type_of_authoring_organization = Optional(str)
    authoring_organization = Required(str)
    international_national = Optional(str)
    if_national_country_of_authoring_org = Optional(str, nullable=True)
    if_national_iso2_of_authoring_org = Optional(str, nullable=True)
    acronym = Optional(str)

    # Relationships
    items = Set("Item", table="authors_to_items")


class Funder(db.Entity):
    """Funders who provide financial support for authoring organizations
    to create items.

    """

    _table_ = "funder"

    # Attributes
    id = PrimaryKey(int, auto=True)
    name = Required(str)

    # Relationships
    items = Set("Item", table="funders_to_items")


class Event(db.Entity):
    """Events (outbreaks) that may be tagged on items that discuss them."""

    _table_ = "event"

    # Attributes
    id = PrimaryKey(int, auto=True)
    master_id = Required(str)
    name = Required(str)

    # Relationships
    items = Set("Item", table="events_to_items")


class File(db.Entity):
    """Files (usually PDFs) with the content of items."""

    _table_ = "file"

    # Attributes
    id = PrimaryKey(int, auto=True)
    source_permalink = Required(str)
    s3_permalink = Optional(str, nullable=True)
    filename = Required(str)
    s3_filename = Required(str)
    mime_type = Required(str)
    source_thumbnail_permalink = Optional(str, nullable=True)
    s3_thumbnail_permalink = Optional(str, nullable=True)
    has_thumb = Required(bool)
    num_bytes = Optional(int)
    scraped_text = Optional(str, nullable=True)
    exclude_from_site = Required(bool, default=False)

    # Relationships
    items = Set("Item", table="files_to_items")
    related_items = Set("Item", table="related_files_to_items")


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


class Glossary(db.Entity):
    """Define definitions of terms for single- and multi-selects."""

    _table_ = "glossary"

    # Attributes
    id = PrimaryKey(int, auto=True)
    colname = Required(str)
    term = Required(str)
    definition = Required(str)


class Optionset(db.Entity):
    """Optionset values for tags, topics, etc."""

    _table_ = "optionset"
    id = PrimaryKey(int, auto=True)
    name = Required(str)

    # Helper methods
    @classmethod
    @db_session
    def delete_unused(self):
        print(f"""Deleting unused instances of {self.__name__}...""")
        select(i for i in self if count(i._items) == 0).delete()
        print("Deleted.")

    # Overrides
    def __str__(self):
        return self.name


class KeyTopic(Optionset):
    """Key topic optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="key_topics", table="key_topics_to_items")


class CovidTopic(Optionset):
    """COVID topic optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="covid_topics", table="covid_topics_to_items")


class Tag(Optionset):
    """Tag optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="tags", table="tags_to_items")


class CovidTag(Optionset):
    """COVID tag optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="covid_tags", table="covid_tags_to_items")


class GeoSpecificity(Optionset):
    """Geographic specificity optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="geo_specificity")


class FieldRelationship(Optionset):
    """Field relationship optionset values."""

    # Relationships: Items
    _items = Set("Item", reverse="field_relationship")
