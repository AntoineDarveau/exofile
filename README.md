# Exofile

Tools to generate and access the _exofile_, a customized exoplanet archive.

**IMPORTANT**: _exofile_ is the name of a file and the name of this code (sorry for that). To distinguish between the two in the following text, _exofile.ecsv_ will be used for the file and `exofile` will be used for the code.

_exofile.ecsv_ is based on the [NASA exoplanet archive](https://exoplanetarchive.ipac.caltech.edu/) tables, but allows users to include custom parameters in the final table. The _masterfile.ecsv_ available at http://www.astro.umontreal.ca/~adb/ is based entirely on the NASA Exoplanet Archive tables (the name will be changed to _exofile.ecsv_ for this file as well in a future release).

Thanks to for advices and corrections:
--------------
- Merrin Peterson
- Charles Cadieux
- Taylor Bell
- Anne Boucher

_Also thanks to my supervisors,_ David Lafrenière _and_ René Doyon!

Concept
-------
The idea is to make the most complete table as possible.
Here is a scheme of the concept:

![Concept_scheme](schema_exofile.png)

Explanations
Two files can be load using `ExoFile.load()`
- __Default__ The [Composite Planetary Systems Table](https://exoplanetarchive.ipac.caltech.edu/docs/pscp_about.html), directly taken from the archive with minor formating.
- __Alternative__ The [Planetary Systems Table](https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html) is used to build a _exofile_alt.ecsv_. The references are sorted according to the error on the ephemeride at the present date (this could be changed or improved). All the values from the best reference are used iteratively to fill missing values in the table for the sake of consistency.

The resulting file is called _exofile.ecsv_ or _exofile_alt.ecsv_ and can be used directly. It is also possible to complement this _exofile.ecsv_ with:

3. a crowdsourced [google sheet](https://docs.google.com/spreadsheets/d/1eAhWaff9mURg3TJ1Sp1VkAaMxeZEcKKs05w1kiGFVhs/edit?usp=sharing)
4. a local custom table (default is _exofile_custom.csv_).

To do so, simply use the following code:
``` python
from exofile.archive import ExoFile
data = ExoFile.load()  # or ExoFile.load(use_alt_file=True) for the alternative
```
`data` is an instance of `ExoFile` which is inheriting from [astropy.table.Table](https://docs.astropy.org/en/stable/table/access_table.html) class (so it has the same behaviour).

_NOTE: The Confirmed and Exteneded Planet Tables were retired from the archive
in August 2021. Versions of exofile using these tables are therefore out of
date._

Installation
-----

`exofile` is available on PyPI. You can install the latest release with
```unix
python -m pip install exofile
```

To install the master branch from GitHub, simply clone the repository and install the project locally with pip. 
```unix
git clone https://github.com/AntoineDarveau/exofile.git
cd exofile
python -m pip install -U pip
python -m pip install -U .
```

You can also install directly from github using `python -m pip install -U "git+https://github.com/AntoineDarveau/exofile.git#egg=exofile"`.

To install `exofile` for development, it is recommended to use an isolated environment with a tool like conda, virtualenv or venv. Inside your environment, you can install following the steps above, but replacing `python -m pip install -U .` by `python -m pip install -U -e ".[dev]"`. This will install `exofile` in editable mode (`-e`) and it will install the development dependencies.

You can then use `exofile` with `import exofile`. See the notebook for examples.

Customize
---------
You can change the default parameters file. Take a look at the notebook for examples.


What happened to masterfile ?
-----
This repository used to be named `masterfile` (and the associated database
_masterfile.ecsv_). It has been rename to avoid name conflicts with an existing
Python package called `masterfile`.

**If you have existing code that uses masterfile, these two commands should
help:**

`sed 's/masterfile/exofile/g' <FILES>`

`sed 's/MasterFile/ExoFile/g' <FILES>`

where files is a single file or a list of files. To edit the files directlly
(instead of just printing the result of the substitution), add the `-i` flag to
the `sed` command.

The default files have also be renamed to `exofile` (except the online one). This
can be changed by editing the parameters.
