# Tools to generate and access the masterfile
masterfile is based on the exoplanet archive tables.
The masterfile and the reference table are available at http://www.astro.umontreal.ca/~adb/

Contributors:
-------------
- Antoine Darveau-Bernier
- Merrin Peterson

Concept
-------
The idea is to make the most complete table as possible.
1. The [Confirmed Planet Table](https://exoplanetarchive.ipac.caltech.edu/docs/API_exoplanet_columns.html) is used to fill the masterfile. 
2. Then, the [Extended Planet Table](https://exoplanetarchive.ipac.caltech.edu/docs/API_exomultpars_columns.html) is used. The references are sorted according to the error on the orbital period (this could be changed). All the values from a particular reference are used to keep a minimum of consistency.

The resulting file can be used directly. It is also possible to complement this _masterfile_ with:

3. a google sheet (ask me if you want the link)
4. a local custom table (default is csv file).

To do so, simply use the following code:
```
python
from masterfile import MasterFile
data = MasterFile.load()
```

Setup
-----
Once the masterfile is cloned and properly referred to (like adding ` '/path/to/repository/masterfile/' ` to python's path or ` from sys import path; path.append('/path/to/repository/masterfile/')) `), the param file must be configurate. You can do so by simply running in python:
```python
from masterfile import edit_param
edit_param(sheet_key='key_of_the_google_sheet_for_custom_values',
           url='url_of_the_masterfile',
           url_ref='url_of_the_masterfile_references')
