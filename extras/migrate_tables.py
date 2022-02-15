"""
Helper to migrate the old masterfile format to the new one.
Most of this is taken from the MasterFile.update() and adapted to the old->new conversion
instead of PS -> PSCP.
"""
from warnings import warn

import numpy as np
from masterfile.archive import MasterFile, load_exoplanet_archive_mappings, ExoArchive, difference
from masterfile.table_custom import MaskedColumn

NEW_PATH = "exofile.ecsv"

old_tbl = MasterFile.read("old_masterfile.ecsv")
old_ref = MasterFile.read("reference_file.ecsv")

label_df = load_exoplanet_archive_mappings()
label_df_all = label_df.copy()
NEW_NAME = "Planetary Systems Composite Parameters (PSCP)"
OLD_NAME = "Confirmed Planets (retiring)"
label_df = label_df.dropna(subset=[NEW_NAME, OLD_NAME])
label_df = label_df[~label_df[NEW_NAME].str.contains("systemref")]
label_new = label_df[NEW_NAME].str.strip()
label_old = label_df[OLD_NAME].str.strip()

for lold, lnew in zip(label_old, label_new):
    # Some columns are missing even if in CSV, so will have a few warnings
    try:
        old_tbl.rename_column(lold, lnew)
        old_ref.rename_column(lold, lnew)
    except KeyError:
        warn(f"Column {lold} was not found in old table", RuntimeWarning)

pc_struct = ExoArchive.query(select="top 1 *")
pc_cols = pc_struct.colnames

# Now remove extra columns
dlist = difference(old_tbl.colnames, pc_cols)
del old_tbl[dlist]
del old_ref[dlist]

missing_cols = difference(pc_cols, old_tbl.colnames)

# Get ref an non-ref missing columns
reflink_labels = label_df_all.dropna(subset=NEW_NAME)[NEW_NAME]
reflink_labels = reflink_labels.str.strip()
reflink_labels = reflink_labels[reflink_labels.str.endswith("reflink")]
reflink_labels = reflink_labels[reflink_labels.isin(missing_cols)]
non_ref_cols = difference(missing_cols, reflink_labels.to_list())

# Add missing columns
for col in non_ref_cols:
    if pc_struct[col].dtype.kind in ["U", "S"]:
        old_tbl[col] = ""
    else:
        old_tbl[col] = MaskedColumn(
            np.full(len(old_tbl), np.nan), unit=pc_struct[col].unit
        )

for rlab in reflink_labels:

    plab = rlab.replace("_reflink", "")

    # If column was not in old file, it has no refs
    if plab in non_ref_cols:
        new_refs = ""
    else:
        new_refs = old_ref[plab]

    old_tbl[rlab] = MaskedColumn(new_refs)

new_tbl = old_tbl[pc_cols]

new_tbl.write(NEW_PATH)
