"""
Create simple csv files to test joining tables.
"""
from astropy.table import Table
import numpy as np

# Table with single parameters and three references to test
names = ["pl_name", "mypar", "myparerr1", "myparerr2", "mypar_reflink", "default_flag"]
data1 = [["Cool-planet b", 0.5, 0.01, 0.01, "myref1", 1], ["Other-planet c", np.nan, np.nan, np.nan, "", 1]]
data2 = [["Cool-planet b", 0.8, 0.1, 0.1, "myref2", 0], ["Other-planet c", 0.2, 0.02, 0.02, "myref2", 0]]
data3 = [["Cool-planet b", 0.9, 0.2, 0.2, "myref3", 0], ["Other-planet c", 0.5, 0.2, 0.2, "myref3", 0]]

data_rows = [*data1, *data2, *data3]

tbl = Table(rows=data_rows, names=names)
tbl.write("tests/data/single_param.csv", overwrite=True)

# Add second parameter
tbl["otherpar"] = tbl["mypar"] * 4
tbl["otherparerr1"] = tbl["myparerr1"] * 4
tbl["otherparerr2"] = tbl["myparerr2"] * 4
tbl["otherpar_reflink"] = tbl["mypar_reflink"]

# Swap so that second parameters has NaN in different (non-default) refs
# Seems like need to look otherwise astropy gives copies of row sections
other_cols = ["otherpar", "otherparerr1", "otherparerr2", "otherpar_reflink"]
for oc in other_cols:
    r1_old = tbl[oc].copy()[1]
    r2_old = tbl[oc].copy()[3]
    tbl[oc][1] = r2_old
    tbl[oc][3] = r1_old
tbl["otherpar_reflink"][1] = "myref1"

tbl.write("tests/data/two_params.csv", overwrite=True)
