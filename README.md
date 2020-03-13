# Tools to generate and access the masterfile

__IMPORTANT__: _masterfile_ is the name of a file and the name of this code (sorry for that). To distinguish between the two in the following text, _masterfile.ecsv_ will be used for the file and ` masterfile ` will be used for the code.

_masterfile.ecsv_ is based on the exoplanet archive tables.
The masterfile and the reference table are available at http://www.astro.umontreal.ca/~adb/

Contributors:
-------------
- Antoine Darveau-Bernier
- Merrin Peterson
- Charles Cadieux
- Taylor Bell?

Concept
-------
The idea is to make the most complete table as possible.
1. The [Confirmed Planet Table](https://exoplanetarchive.ipac.caltech.edu/docs/API_exoplanet_columns.html) is used to fill the masterfile. 
2. Then, the [Extended Planet Table](https://exoplanetarchive.ipac.caltech.edu/docs/API_exomultpars_columns.html) is used to fill the missing values. The references are sorted according to the error on the orbital period (this could be changed). All the values from a particular reference are used to keep a minimum of consistency.

The resulting file is called _masterfile.ecsv_ and can be used directly. It is also possible to complement this _masterfile.ecsv_ with:

3. a [google sheet](https://docs.google.com/spreadsheets/d/14Trm-AQ2eOphfwqJYrevnDrNVk56E-aH8yvRHQLjzWg/edit?usp=sharing)
4. a local custom table (default is _masterfile_custom.csv_).

To do so, simply use the following code:
``` python
from masterfile.archive import MasterFile
data = MasterFile.load()
```
`data`is an instance of MasterFile which is inheriting from [astropy.table.Table](https://docs.astropy.org/en/stable/table/access_table.html) class (so it has the same behaviour).

Setup
-----
Simply clone `masterfile` by running the following line in a terminal (you need to be in the directory where you want to copy `masterfile`).
```unix
git clone git@github.com:AntoineDarveau/masterfile.git
```
Then, there are many ways to refer to the code, but one could be to add the ` '/path/to/repository/masterfile/' ` to your `PYTHONPATH`. See this [link](https://stackoverflow.com/questions/3402168/permanently-add-a-directory-to-pythonpath) for more information on how to do that. This will ensure that you can import `masterfile` from anywhere in your computer. Another way is to add ` from sys import path; path.append('/path/to/repository/masterfile/')) ` at the beggining of each code and then you will be able to import `masterfile`


You can also change the default parameters file. Take a look at the notebook for examples.
