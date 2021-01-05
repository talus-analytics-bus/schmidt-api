"""Define formats for use in ExcelExport class."""
# 3rd party modules
import pandas
import pandas.io.formats.excel

# settings
pandas.io.formats.excel.header_style = None


class WorkbookFormats():
    """Define various workbook formats to be used in Excel export.

    Parameters
    ----------
    workbook : type
        Description of parameter `workbook`.

    Attributes
    ----------
    title_format : type
        Description of attribute `title_format`.
    subtitle_format : type
        Description of attribute `subtitle_format`.
    intro_text_format : type
        Description of attribute `intro_text_format`.
    cell_format : type
        Description of attribute `cell_format`.
    legend_cell_format : type
        Description of attribute `legend_cell_format`.
    workbook

    """

    def __init__(self, workbook):
        self.workbook = workbook

        self.title_format = workbook.add_format(
            {
                'font_size': 26,
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'bold': True,
                'text_wrap': False
            }
        )

        self.subtitle_format = workbook.add_format(
            {
                'font_size': 18,
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'italic': True,
                'text_wrap': False
            }
        )

        self.intro_text_format = workbook.add_format(
            {
                'font_size': 16,
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'text_wrap': True
            }
        )

        self.cell_format = workbook.add_format(
            {
                'font_size': 14,
                'bg_color': '#ffffff',
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'align': 'left',
                'border': 2,
                'border_color': '#CCCDCB',
                'text_wrap': True,
                # 'num_format': '_(* ###0_);_(* (#,##0);_(* "-"??_);_(@_)'
            }
        )

        self.legend_cell_format = workbook.add_format(
            {
                'font_size': 14,
                'bg_color': '#ffffff',
                # 'bg_color': '#DEDEDE',
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'bold': True,
                'border': 2,
                'border_color': '#CCCDCB',
                'text_wrap': True
            }
        )

        self.comma_num_format = workbook.add_format(
            {
                'font_size': 14,
                'bg_color': '#ffffff',
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'align': 'right',
                'border': 2,
                'border_color': '#CCCDCB',
                'text_wrap': True,
                'num_format': '_(* #,##0_);_(* (#,##0);_(* "-"??_);_(@_)'
            }
        )
        self.num_right_format = workbook.add_format(
            {
                'font_size': 14,
                'bg_color': '#ffffff',
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'align': 'right',
                'border': 2,
                'border_color': '#CCCDCB',
                'text_wrap': True,
                'num_format': '_(* ###0_);_(* (#,##0);_(* "-"??_);_(@_)'
            }
        )

    def title(self):
        return self.title_format

    def subtitle(self):
        return self.subtitle_format

    def intro_text(self):
        return self.intro_text_format

    def cell(self):
        return self.cell_format

    def comma_num(self):
        return self.comma_num_format

    def num_right(self):
        return self.num_right_format

    def legend_cell(self):
        return self.legend_cell_format

    def colgroup(self):
        """Creates a header format from the given color hex value.

        Parameters
        ----------
        color_hex : type
            Description of parameter `color_hex`.

        Returns
        -------
        type
            Description of returned object.

        """
        return self.workbook.add_format(
            {
                # Specific header styling:
                'bg_color': '#be0e23',
                # 'bg_color': '#DEDEDE',
                'font_color': '#ffffff',
                # 'font_color': '#000000',

                # All header styling:
                'bold': True,
                'font_size': 22,
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'align': 'left',
                'border': 2,
                'border_color': '#CCCDCB',
            }
        )

    def colname(self, color_hex):
        """Creates a header format from the given color hex value.

        Parameters
        ----------
        color_hex : type
            Description of parameter `color_hex`.

        Returns
        -------
        type
            Description of returned object.

        """
        return self.workbook.add_format(
            {
                # Specific header styling:
                'bg_color': color_hex,
                'font_color': '#333333',
                # 'font_color': '#ffffff',

                # All header styling:
                'bold': True,
                'font_size': 14,
                'font_name': 'Calibri (Body)',
                'valign': 'vcenter',
                'border': 2,
                'border_color': '#CCCDCB',
                'text_wrap': True,
            }
        )
