"""Define data sources for ingesting data into databases"""
# 3rd party packages for AirtableSource
from airtable import Airtable
import pprint
import pandas as pd

# local modules
from .util import bcolors

# constants
pp = pprint.PrettyPrinter(indent=4)


class DataSource:
    def __init__(self, name: str):
        self.name = name


class AirtableSource(DataSource):
    def __init__(self, name: str, base_key: str, api_key: str):
        DataSource.__init__(self, name)
        self.base_key = base_key
        self.api_key = api_key

    def connect(self):
        return self

    def workbook(self, key: str):
        print("WARNING: `workbook` method not implemented for AirtableSource.")
        return self

    def worksheet(self, name: str):
        try:
            ws = Airtable(self.base_key, table_name=name, api_key=self.api_key)
            self.ws = ws
            self.ws_name = name
            return self

        except Exception as e:
            print(e)
            print("\nFailed to open worksheet with name " + str(name))

    def as_dataframe(
        self,
        header_row: int = 0,
        view: str = None,
        max_records: int = 10000000,
    ):
        try:
            records_tmp = (
                self.ws.get_all(max_records=max_records)
                if view is None
                else self.ws.get_all(view=view)
            )
            records = list()
            for r_tmp in records_tmp:
                r = r_tmp["fields"]
                r["source_id"] = r_tmp["id"]
                records.append(r)

            df = pd.DataFrame.from_records(records)

            print(
                f"""{bcolors.OKGREEN}Found {len(df)} records in worksheet "{self.ws_name}"{bcolors.ENDC}"""
            )

            # remove NaN values
            df = df.replace(pd.np.nan, "", regex=True)
            return df
        except Exception as e:
            print(e)
            print("\nFailed to open worksheet")
