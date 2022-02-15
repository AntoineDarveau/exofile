from masterfile.archive import GoogleSheet
from masterfile.config import Param
from masterfile.utils import migrate_table

param = Param.load().value

gs_tbl = GoogleSheet.query(param["sheet_key"])
gs_ref = GoogleSheet.query(param["sheet_key"], sheet_name="Ref")

new_gs = migrate_table(gs_tbl, gs_ref)
columns = new_gs.colnames

# Bring back to GS col names (units in bracket)
for col in columns:
    new_name = f'{new_gs[col].name} [{new_gs[col].unit or None}]'
    new_gs.rename_column(col, new_name)

# Write locally to CSV, then users can copy past with spreadsheet editor
new_gs.write("new_google_sheet.csv")
