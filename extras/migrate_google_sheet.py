from exofile.archive import GoogleSheet
from exofile.utils import migrate_table

old_key = "14Trm-AQ2eOphfwqJYrevnDrNVk56E-aH8yvRHQLjzWg"
gs_tbl = GoogleSheet.query(old_key)
gs_ref = GoogleSheet.query(old_key, sheet_name="Ref")

for rc in gs_ref.colnames:
    gs_ref[rc] = gs_ref[rc].astype("str")
    gs_ref[rc].unit = None

new_gs = migrate_table(gs_tbl, gs_ref)
columns = new_gs.colnames

# Bring back to GS col names (units in bracket)
for col in columns:
    new_name = f'{new_gs[col].name} [{new_gs[col].unit or None}]'
    new_gs.rename_column(col, new_name)

new_gs = GoogleSheet(new_gs, copy=False, masked=True)
new_gs.nan_to_mask()
# Write locally to CSV, then users can copy past with spreadsheet editor
new_gs.write("new_google_sheet.csv")
