"""
Helper to migrate the old masterfile format to the new one.
Most of this is taken from the MasterFile.update() and adapted to the old->new conversion
instead of PS -> PSCP.
"""

from masterfile.archive import MasterFile
from masterfile.utils import migrate_table

NEW_PATH = "exofile.ecsv"

old_tbl = MasterFile.read("old_masterfile.ecsv")
old_ref = MasterFile.read("reference_file.ecsv")

new_tbl = migrate_table(old_tbl, old_ref)

new_tbl.write(NEW_PATH)
