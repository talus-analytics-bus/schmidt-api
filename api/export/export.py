"""Write data to an XLSX file and download it."""
# standard modules
from io import BytesIO
from datetime import date
import types

# 3rd party modules
from pony.orm import db_session, select
from openpyxl import load_workbook
import pandas as pd

# local modules
from .formats import WorkbookFormats


class ExcelExport:
    """Parent class for project-specific Excel export."""

    def __init__(self):
        return None

    def build(self, **kwargs):
        # Create bytes output to return to client
        io = BytesIO()
        writer = pd.ExcelWriter("temp.xlsx", engine="xlsxwriter")
        writer.book.filename = io

        # add a worksheet
        workbook = writer.book
        workbook.set_size(3000, 3000)  # full screen

        # add content
        self.add_content(workbook, **kwargs)

        # close writer
        writer.close()

        # return to start of IO stream
        io.seek(0)

        # # return export file
        # content = io.read()

        return io

    def add_content(self):
        print("Not implemented")
        return False


class SheetSettings:
    """Define settings for a workbook sheet to be written to an XLSX file.

    Parameters
    ----------
    name : str
        Description of parameter `name`.
    type : str
        Description of parameter `type`.
    intro_text : str
        Description of parameter `intro_text`.
    init_irow : dict
        Description of parameter `init_irow`.
    data_getter : function
        Description of parameter `data_getter`.

    Attributes
    ----------
    data : type
        Description of attribute `data`.
    name
    type
    init_irow

    """

    def __init__(
        self,
        name: str,
        type: str,
        intro_text: str,
        init_irow: dict,
        data_getter: types.FunctionType,
        class_name: str,
    ):
        self.name = name
        self.type = type
        self.intro_text = intro_text
        self.init_irow = init_irow
        self.class_name = class_name
        self.data = data_getter(class_name=class_name)
        self.num_cols = 0

    def get_init_icol(self):
        """Get initial column for data-writing based on what type of sheet
        this is.

        Returns
        -------
        type
            Description of returned object.

        """
        if self.type == "data":
            return 0
        elif self.type == "legend":
            return 1

    def write_rows(self, worksheet, data):
        """Write the primary data rows of the sheet as table cells.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        data : type
            Description of parameter `data`.

        Returns
        -------
        type
            Description of returned object.

        """
        # if worksheet is legend, then always align text left
        is_legend = worksheet.name.startswith("Legend")
        init_irow = self.init_irow["data"]
        init_icol = self.get_init_icol()
        irow = init_irow
        icol = init_icol
        for row in data:
            for colgroup in row:
                for colname in row[colgroup]:
                    value = row[colgroup][colname]
                    # special formatting
                    if colname.endswith("date"):
                        if value is None:
                            value = "Unspecified"
                    elif value == "Unspecified":
                        value = ""
                    cell_format = (
                        self.formats.cell()
                        if is_legend
                        or colname not in ("HIV incidence", "ART coverage (%)")
                        else self.formats.comma_num()
                    )

                    if colname == "Year" and not is_legend:
                        cell_format = self.formats.num_right()

                    worksheet.write(irow, icol, value, cell_format)

                    icol = icol + 1
            worksheet.set_row(irow, 155)
            irow = irow + 1
            icol = init_icol

    def write_colnames(self, worksheet, data):
        """Write the column names as colorized headers for the sheet.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        data : type
            Description of parameter `data`.

        Returns
        -------
        type
            Description of returned object.

        """
        init_irow = self.init_irow["colnames"]
        init_icol = self.get_init_icol()
        irow = init_irow
        icol = init_icol
        bg_colors = ["#E9EFF1", "#cddbe1"]
        bg_color_idx = 0
        row = data[0]
        worksheet.set_row(irow, 40)
        for colgroup in row:
            # TODO fully customizable colors
            bg_color_idx = bg_color_idx + 1
            bg_color = bg_colors[bg_color_idx % 2]
            for colname in row[colgroup]:
                worksheet.write(irow, icol, colname, self.formats.colname(bg_color))
                if self.type == "legend" and colname in (
                    "Funders",
                    "Sub-organization",
                    "Authoring organization has governance authority?",
                ):
                    worksheet.set_column(icol, icol, 60)
                elif self.type == "legend" and colname == "Definition":
                    worksheet.set_column(icol, icol, 80)
                elif self.type != "legend" and colname == "Title":
                    worksheet.set_column(icol, icol, 25)
                elif self.type != "legend" and colname == "Description":
                    worksheet.set_column(icol, icol, 95)
                elif self.type != "legend" and colname in (
                    "Type of record",
                    "Date published",
                ):
                    worksheet.set_column(icol, icol, 25)
                elif self.type != "legend" and colname in ("Sortable date published"):
                    worksheet.set_column(icol, icol, 30)
                else:
                    worksheet.set_column(icol, icol, 50)

                icol = icol + 1
                self.num_cols = self.num_cols + 1

    def write_colgroups(self, worksheet, data):
        """Write the column groups as colorized, merged headers for the sheet.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        data : type
            Description of parameter `data`.

        Returns
        -------
        type
            Description of returned object.

        """
        init_irow = self.init_irow["colgroups"]
        init_icol = self.get_init_icol()
        irow = init_irow
        icol_end = init_icol
        row = data[0]
        worksheet.set_row(irow, 30)

        for colgroup in row:
            icol_start = icol_end
            for colname in row[colgroup]:
                icol_end = icol_end + 1
                if (icol_end - icol_start + 1) == len(row[colgroup]):
                    worksheet.merge_range(
                        irow,
                        icol_start,
                        irow,
                        icol_end,
                        colgroup,
                        self.formats.colgroup(),
                    )

    def write_legend_labels(self, worksheet):
        """For legend sheets: add the left-hand column defining what each of
        the rows is.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.

        Returns
        -------
        type
            Description of returned object.

        """
        init_irow = self.init_irow["colnames"]
        # worksheet.set_column(0, 0, 50)
        rows = [
            (init_irow, "Column name", self.formats.colname("#cddbe1")),
            (init_irow + 1, "Definition", self.formats.legend_cell()),
            (init_irow + 2, "Allowed values", self.formats.legend_cell()),
        ]
        for irow, text, cell_format in rows:
            worksheet.write(irow, 0, text, cell_format)
        worksheet.set_row(init_irow + 2, 360)

    def write_header(
        self,
        worksheet,
        logo_fn,
        logo_offset,
        logo_stretch_correction,
        title,
        intro_text,
    ):
        """Write the sheet header, including title, subtitle, logo, etc.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        logo_fn : type
            Description of parameter `logo_fn`.
        title : type
            Description of parameter `title`.
        intro_text : type
            Description of parameter `intro_text`.

        Returns
        -------
        type
            Description of returned object.

        """
        self.write_logo(worksheet, logo_fn, logo_offset, logo_stretch_correction, 115)
        self.write_title(worksheet, title)

        today = date.today()
        self.write_subtitle(worksheet, "Data as of " + str(today))
        self.write_intro_text(worksheet, intro_text)

    def write_logo(
        self,
        worksheet,
        logo_fn,
        logo_offset,
        logo_stretch_correction,
        row_height,
    ):
        """Add the logo at the specified filename path to the upper-left corner.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        logo_fn : type
            Description of parameter `logo_fn`.
        row_height : type
            Description of parameter `row_height`.

        Returns
        -------
        type
            Description of returned object.

        """
        worksheet.set_row(0, row_height)
        worksheet.insert_image(
            0,
            0,
            logo_fn,
            {
                "object_position": 3,
                "y_scale": 1.1,
                # 'x_scale': logo_stretch_correction,
                "x_offset": logo_offset["x_offset"],
                "y_offset": logo_offset["y_offset"],
            },
        )

    def write_title(self, worksheet, text):
        """Add title of sheet.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        text : type
            Description of parameter `text`.

        Returns
        -------
        type
            Description of returned object.

        """
        irow = self.init_irow["title"]
        worksheet.write(irow, 0, text, self.formats.title())

    def write_subtitle(self, worksheet, text):
        """Add subtitle of sheet, usually the download date.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        text : type
            Description of parameter `text`.

        Returns
        -------
        type
            Description of returned object.

        """
        irow = self.init_irow["subtitle"]
        worksheet.write(irow, 0, text, self.formats.subtitle())

    def write_intro_text(self, worksheet, text):
        """Add some intro text to the sheet beneath the subtitle.

        Parameters
        ----------
        worksheet : type
            Description of parameter `worksheet`.
        text : type
            Description of parameter `text`.

        Returns
        -------
        type
            Description of returned object.

        """
        irow = self.init_irow["intro_text"]
        icol_start = 0
        icol_end = 2
        worksheet.set_row(irow, 70)
        worksheet.merge_range(
            irow, icol_start, irow, icol_end, text, self.formats.intro_text()
        )


class GenericExcelExport(ExcelExport):
    """Demo ExcelExport-style class that writes data to an XLSX file when the
    instance method `build` is called.

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

    def __init__(self, db):
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

        # Define a sheet settings instance for each tab of the XLSX
        self.sheet_settings = [
            SheetSettings(
                name="Exported data",
                type="data",
                intro_text="This is placeholder intro text for the main data sheet of the workbook. It can be edited by changing the `text` argument to the function `write_intro_text` in module `~/py/api/excel.py`.",
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
                data_getter=self.default_data_getter,
            ),
            SheetSettings(
                name="Legend",
                type="legend",
                intro_text="This is a placeholder for a legend sheet.",
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
                data_getter=self.default_data_getter_legend,
            ),
        ]

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
            worksheet = workbook.add_worksheet(settings.name)

            # hide gridlines
            worksheet.hide_gridlines(2)

            # define formats
            settings.formats = WorkbookFormats(workbook)

            settings.write_header(
                worksheet,
                logo_fn="./api/assets/images/logo-talus.png",
                title=settings.name,
                intro_text=settings.intro_text,
            )

            data = settings.data
            settings.write_colgroups(worksheet, data)
            settings.write_colnames(worksheet, data)
            settings.write_rows(worksheet, data)

            if settings.type == "legend":
                settings.write_legend_labels(worksheet)
            elif settings.type == "data":
                worksheet.freeze_panes(settings.init_irow["colnames"], 0)
                worksheet.autofilter(
                    settings.init_irow["colnames"],
                    0,
                    settings.init_irow["colnames"],
                    settings.num_cols - 1,
                )

        return self

    def default_data_getter(self):
        # Test data
        # Name, email
        # Hobbies, Favorite color
        # Dict of column groups, which are a list of columns, which are
        # dictionaries with key = colname, value = data to show
        return [
            {
                "Basic information": {
                    "Name": "Test",
                    "E-mail": "Test",
                },
                "Additional details": {
                    "Hobbies": "Test",
                    "Favorite color": "Test",
                },
            },
            {
                "Basic information": {
                    "Name": "Test",
                    "E-mail": "Test",
                },
                "Additional details": {
                    "Hobbies": "Test",
                    "Favorite color": "Test",
                },
            },
        ]

    def default_data_getter_legend(self):
        # Test data
        # Name, email
        # Hobbies, Favorite color
        # Dict of column groups, which are a list of columns, which are
        # dictionaries with key = colname, value = data to show
        return [
            {
                "Basic information": {
                    "Name": "Test",
                    "E-mail": "Test",
                },
                "Additional details": {
                    "Hobbies": "Test",
                    "Favorite color": "Test",
                },
            },
            {
                "Basic information": {
                    "Name": "Test",
                    "E-mail": "Test",
                },
                "Additional details": {
                    "Hobbies": "Test",
                    "Favorite color": "Test",
                },
            },
        ]
