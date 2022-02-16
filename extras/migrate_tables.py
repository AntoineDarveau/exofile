"""
Helper to migrate the old exofile format to the new one.
Most of this is taken from the ExoFile.update() and adapted to the old->new conversion
instead of PS -> PSCP.
"""

from exofile.archive import ExoFile
from exofile.utils import migrate_table

NEW_PATH = "exofile.ecsv"

old_tbl = ExoFile.read("old_exofile.ecsv")
old_ref = ExoFile.read("reference_file.ecsv")

new_tbl = migrate_table(old_tbl, old_ref)

new_tbl.write(NEW_PATH)
