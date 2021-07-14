"""Project-specific plugins for export module"""
# standard modules
from io import BytesIO
from datetime import date
from collections import defaultdict
import types

# 3rd party modules
from pony.orm import db_session, select, get, count
from openpyxl import load_workbook
from werkzeug import ImmutableMultiDict
import pandas as pd
import pprint

# local modules
from .formats import WorkbookFormats
from .export import ExcelExport, SheetSettings
from api import schema
from ..routing import routes

# constants
pp = pprint.PrettyPrinter(indent=4)


class SchmidtExportPlugin(ExcelExport):
    """Schmidt-specific ExcelExport-style class that writes data
    to an XLSX file when the instance method `build` is called.

    Parameters
    ----------
    db : type
        Description of parameter `db`.

    Attributes
    ----------
    data : type
        Description of attribute `data`.
    init_irow : type
        Description of attribute `init_irow`.
    sheet_settings : type
        Description of attribute `sheet_settings`.
    default_data_getter : type
        Description of attribute `default_data_getter`.
    db

    """

    def __init__(self, db, filters, search_text, class_name):
        self.db = db
        self.data = None
        self.init_irow = {
            "logo": 0,
            "title": 1,
            "subtitle": 2,
            "intro_text": 3,
            "gap": 4,
            "colgroups": 5,
            "colnames": 6,
            "data": 7,
        }
        self.filters = filters
        self.search_text = search_text

        # Bookmarks or filtered data or all data?
        def get_export_type(filters, search_text):
            """Get one-word description of the type of export, inferred from
            the filters provided.

            Parameters
            ----------
            filters : dict

            Returns
            -------
            str

            """
            if "id" in filters:
                return "bookmarks"
            elif len(filters.keys()) > 0 or search_text is not None:
                return "selected"
            else:
                return "all"

        def get_filter_prefix(key, search_text):
            """If funder or author filter applied, add prefix to sheet title
            saying which it was to reduce ambiguity.

            Parameters
            ----------
            key : str
                Name of filter field

            Returns
            -------
            str

            """
            if key == "funder.name":
                return "Funded by "
            elif key.startswith("author."):
                return "Published by "
            else:
                return ""

        def get_final_value(key, value_tmp):
            """Returns `value_tmp` unless it represents a unique ID of an
            author, in which case the author's name is returned instead.

            Parameters
            ----------
            key : str
                Name of filter
            value_tmp : any

            Returns
            -------
            any

            """
            if key == "author.id":
                return db.Author[value_tmp].authoring_organization
            else:
                return value_tmp

        def get_data_sheet_title(export_type):
            """Given the export type determined above returns the title of the
            sheet that should be used.

            Parameters
            ----------
            export_type : str

            Returns
            -------
            str

            """
            if export_type == "bookmarks":
                return "Bookmarked documents"

            # if selected items, show as descriptive a title as possible
            # without exceeding a reasonable number of characters
            elif export_type == "selected":
                search_text_defined = search_text is not None
                only_one_filter = (
                    len(filters.keys()) == 1 and not search_text_defined
                )
                any_filter_defined = len(filters.keys()) > 0
                suffix = ""
                if only_one_filter:
                    for key in filters:

                        # only describe what filter was applied if just one
                        # filter was applied, otherwise too many words
                        only_one_value = len(filters[key]) == 1

                        if only_one_value:

                            # if range of dates, format them
                            value = get_final_value(key, filters[key][0])

                            # format date ranges in plain English
                            if "range" in value:
                                value_list = value.split("_")
                                start = value_list[1]
                                end = value_list[2]
                                if end == "null":
                                    value = (
                                        f"""Year {value_list[1]} to present"""
                                    )
                                elif start == "null":
                                    value = f"""Through year {value_list[2]}"""
                                else:
                                    value = f"""Years {value_list[1]} to {value_list[2]}"""
                            elif key == "years":
                                value = f"""Year {value}"""

                            # get prefix with filter description (if avail.)
                            prefix = get_filter_prefix(key, search_text)
                            value = prefix + value

                            # add suffix explaining what filter was applied,
                            # if any shown
                            suffix = ": " + value
                elif search_text_defined and not any_filter_defined:
                    suffix = f''': Text matching "{search_text}"'''
                return "Selected documents" + suffix
            else:
                return "All documents in library"

        export_type = get_export_type(filters, search_text)
        data_sheet_title = get_data_sheet_title(export_type)

        self.sheet_settings = []
        tabs = (
            {
                "s": "Document",
                "p": data_sheet_title,
                "intro_text": f"""The table below lists data for {export_type} documents from Health Security Net\'s Global Health Security Library.""",
                "data": self.default_data_getter,
                "legend": self.default_data_getter_legend,
            },
            {
                "s": "Glossary",
                "p": "Glossary",
                "intro_text": f"""The table below lists definitions of terms used in Health Security Net\'s Global Health Security Library.""",
                "data": self.glossary_data_getter,
                "legend": None,
            },
        )
        for tab in tabs:
            sheet_settings = [
                SheetSettings(
                    name=tab["p"],
                    type="data",
                    intro_text=tab["intro_text"],
                    init_irow={
                        "logo": 0,
                        "title": 1,
                        "subtitle": 2,
                        "intro_text": 3,
                        "gap": 4,
                        "colgroups": 5,
                        "colnames": 6,
                        "data": 7,
                    },
                    data_getter=tab["data"],
                    class_name=tab["s"],
                )
            ]

            if tab["legend"] is not None:
                sheet_settings.append(
                    SheetSettings(
                        name="Column definitions",
                        # name='Legend - ' + tab['p'],
                        type="legend",
                        intro_text=f"""A description for each data column in the "{tab['p']}" tab and its possible values is provided below.""",
                        init_irow={
                            "logo": 0,
                            "title": 1,
                            "subtitle": 2,
                            "intro_text": 3,
                            "gap": 4,
                            "colgroups": 5,
                            "colnames": 6,
                            "data": 7,
                        },
                        data_getter=tab["legend"],
                        class_name=tab["s"],
                    )
                )

            self.sheet_settings += sheet_settings

    def add_content(self, workbook):
        """Add content, e.g., the tab containing the exported data.

        Parameters
        ----------
        workbook : type
            Description of parameter `workbook`.

        Returns
        -------
        type
            Description of returned object.

        """
        for settings in self.sheet_settings:
            # Truncate name if too many characters
            def truncate_name(name):
                max_tab_name_len = 31
                if len(name) > (max_tab_name_len - 2):
                    if ":" in name:
                        name = name.split(":")[0]
                    else:
                        name = name[0:max_tab_name_len]
                name = name.replace(":", " - ")
                return name

            tab_name = truncate_name(settings.name)
            worksheet = workbook.add_worksheet(tab_name)

            # hide gridlines
            worksheet.hide_gridlines(2)

            # define formats
            settings.formats = WorkbookFormats(workbook)
            settings.write_header(
                worksheet,
                logo_fn="./api/assets/images/logo.png",
                logo_offset={
                    "x_offset": 5,
                    "y_offset": 25,
                },
                # logo_stretch_correction=1,
                logo_stretch_correction=1 / 1.13,
                title=settings.name,
                intro_text=settings.intro_text,
            )

            data = settings.data
            settings.write_colgroups(worksheet, data)
            settings.write_colnames(worksheet, data)
            settings.write_rows(worksheet, data)

            if settings.type == "legend":
                settings.write_legend_labels(worksheet)
                worksheet.set_row(settings.init_irow["data"], 220)
                worksheet.set_column(0, 0, 50)
            elif settings.type == "data":
                worksheet.freeze_panes(settings.init_irow["data"], 0)
                worksheet.autofilter(
                    settings.init_irow["colnames"],
                    0,
                    settings.init_irow["colnames"],
                    settings.num_cols - 1,
                )

        return self

    def glossary_data_getter(
        self, class_name: str = "Glossary", filters: dict = None
    ):

        # get glossary term definitions
        data = schema.get_glossary()

        # init
        rows = list()

        # for each row
        for d in data:

            # create dict to store row information
            row = {
                "Term definitions": {
                    "Column name": d.colname,
                    "Term": d.term,
                    "Definition": d.definition,
                }
            }

            # append row data to overall row list
            rows.append(row)

        # return list of rows
        return rows

    def default_data_getter(
        self, class_name: str = "Policy", filters: dict = None
    ):
        # get items, applying filters (usually a list of IDs of items to return)
        return schema.get_export_data(
            filters=self.filters, search_text=self.search_text
        )

    def default_data_getter_legend(self, class_name: str = "Policy"):
        return schema.get_export_legend_data()
        # DEBUG
        return [
            {
                "Country": {
                    "Country": "The name of the country",
                },
                "Indicator and subindicator data": {
                    "Indicator or subindicator?": "Whether the data in this row describe an indicator or a subindicator (i.e., component of an indicator)",
                    "Indicator / Subindicator name": "The unique code and name of the indicator or subindicator",
                    "Year": "The year of data reported",
                    "Adoption level": 'Whether the country adopted, partially adopted, or did not adopt the indicator or subindicator in the year indicated. If no data are available, "No data" is listed.',
                },
            },
            {
                "Country": {
                    "Country": "Any country name",
                },
                "Indicator and subindicator data": {
                    "Indicator or subindicator?": "Indicator or subindicator",
                    "Indicator / Subindicator name": "Any unique indicator/subindicator code followed by a hyphen and its name",
                    "Year": "Any year (YYYY)",
                    "Adoption level": "Adopted, partially adopted, not adopted, or no data.",
                },
            },
        ]

        # get all metadata
        db = self.db
        metadata = select(
            i
            for i in db.Metadata
            if i.export == True and i.class_name == class_name
        ).order_by(db.Metadata.order)

        # init export data list
        rows = list()

        # for each metadatum
        for row_type in ("definition", "possible_values"):

            # append rows containing the field's definition and possible values
            row = defaultdict(dict)
            for d in metadata:
                if d.display_name == "Attachment for policy":
                    if row_type == "definition":
                        row[d.colgroup][
                            "Permalink for policy PDF(s)"
                        ] = "URL of permanently hosted PDF document(s) for the policy"
                    elif row_type == "possible_values":
                        row[d.colgroup][
                            "Permalink for policy PDF(s)"
                        ] = "Any URL(s)"
                else:
                    row[d.colgroup][d.display_name] = getattr(d, row_type)
            rows.append(row)
        return rows
