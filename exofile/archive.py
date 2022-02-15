import re
from warnings import warn
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import numpy as np
import requests
from astropy.time import Time
from astropy.units import Unit
from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
from pandas import read_csv, DataFrame

from .config import Param
from .exceptions import (ColUnitsWarning, GetLocalFileWarning, NoUnitsWarning,
                         QueryFileWarning)
from .table_custom import MaskedColumn, Table, difference


# Columns that are missing in archive even though listed in master CSV mappign
MISSING_COLS = [
    "raerr1",
    "raerr2",
    "decerr1",
    "decerr2",
    "glaterr1",
    "glaterr2",
    "glonerr1",
    "glonerr2",
    "elaterr1",
    "elaterr2",
    "elonerr1",
    "elonerr2",
]
PS_NAME = "Planetary Systems (PS)"
PC_NAME = "Planetary Systems Composite Parameters (PSCP)"
ARCHIVE_CSV_PATH = "https://exoplanetarchive.ipac.caltech.edu/docs/Exoplanet_Archive_Column_Mapping_CSV.csv"

def get_refname_from_link(link: str) -> str:
    """
    Get the text from a reflink
    """
    if link != "":
        res = re.search(">(.*)</a>", link)
        if res is not None:
            out = res.group(1)
        else:
            warn(f"Regex result for link {link} is None, returning input link")
            out = link
    else:
        out = link

    return out


def get_refname_from_links(links: List[str]) -> List[str]:
    """
    Get the text from multiple reflinks
    """
    return [get_refname_from_link(link) for link in links]


class ExoFile(Table):

    main_col = "pl_name"

    def get_colnames_with_error(
            self, err_ext: List[str] = ["err1", "err2"]
        ) -> Tuple[str]:
        """
        Find all columns with an error column associate`.
        `err_ext` is the list of extensions for the name of the error columns.
        Returns a tuple of lists, each lists contain the name of a column
        and the names of its related errors.

        Example:
        colname = 'pl_tperi'
        errcols: 'pl_tperierr1' and 'pl_tperierr2'
        The output would be: (['pl_tperi', 'pl_tperierr1', 'pl_tperierr2'], )
        """

        colnames = ()
        for key in self.colnames:

            try:
                for err in err_ext:
                    self[key + err]
                colnames += ([key + err for err in ["", *err_ext]],)

            except KeyError:
                pass

        return colnames

    def mask_no_errors(self, **kwargs):
        """
        Mask columns where errors are not available
        """
        for cols in self.get_colnames_with_error(**kwargs):

            mask = self[cols].mask
            # Convert to regular array
            mask = np.array(mask.as_array().tolist())

            # Find where values, err1 or err2 are masked
            imask = np.where(mask.any(axis=-1))

            # Mask values, err1 and err2 at these rows
            for col in cols:
                self[col].mask[imask] = True

    def mask_zero_errors(self, **kwargs):
        """
        Mask columns where associated errors are equal to zero
        """
        for cols in self.get_colnames_with_error(**kwargs):

            # Put all errors in a 2d array (ex: err1, err2)
            errors = [self[col].data for col in cols[1:]]
            errors = np.ma.array(errors).T

            # Find where err1 or err2 are zero
            cond = errors == 0.0
            imask = np.where(cond.any(axis=-1))[0]

            # Mask value, err1 and err2 at these rows
            for col in cols:
                if imask.any():
                    self[col].mask[imask] = True

    def replace_with(self, other, main_col=None):
        """
        Use all non-masked values of `other` to replace values in `self`.
        `key` is the column use to identify corresponding rows.
        Default is other.main_col
        """

        # Take main_col if key is not given
        main_col = main_col or other.main_col

        # Make sure `other` is masked
        other = ExoFile(other, copy=True, masked=True)

        # Save units for conversion
        units = {}
        for key in other.keys():
            units[key] = self[key].unit
            # Check if they are the same
            if other[key].unit != units[key]:
                if other[key].unit is None:
                    other[key].unit = units[key]
                    warn(NoUnitsWarning(key, units[key]))
                else:
                    warn(ColUnitsWarning(key, [other[key].unit, units[key]]))

        # Get position in main table
        index = self.get_index(*other[main_col], name_key=main_col)
        index = np.array(index)

        # Add empty rows for objects not in `self`
        for name in other[index == -1]["pl_name"]:
            self.add_row({"pl_name": name})

        # Get position in main table again
        index = self.get_index(*other[main_col], name_key=main_col)
        index = np.array(index)

        # Replace values of objects in `self`
        for i_other, i_self in enumerate(index):
            # Position of keys that are not masked
            (i_keys,) = np.where(~np.array(list(other.mask[i_other])))

            # Keys not masked
            keys = [other.keys()[i_key] for i_key in i_keys]

            # Don't change values for main column
            keys.remove(main_col)

            # Assign new values
            for key in keys:
                # Don't convert units if unit is None. Else do so.
                if units[key] is None:
                    self[i_self][key] = other[i_other][key]
                else:
                    conversion = other[key].unit.to(units[key])
                    self[i_self][key] = other[i_other][key] * conversion

    @classmethod
    def query(cls, url_key="url", debug=False, exofile_kwargs=None, **kwargs):
        """
        Query the exofile and try to complement it with
        the custom table (google sheet).
        Returns the complemented exofile.
        Parameters:
        - url: string
            adress of the exofile
        - url_key: string
            key to get the url from param file. Default is 'url'.
        - sheet_key: string
            Identification key of the google sheet
        """
        # Get links to query the different database
        param = Param.load().value
        # Use input arguments if given
        param = {**param, **kwargs.pop("param", {})}

        try:
            # Get combined table
            master = requests.get(param[url_key])
            # Convert to table
            master = cls.read(master.text, format="ascii")
        except requests.exceptions.SSLError:
            # If SSLError, maybe just the exofile website is problem,
            # still try local file and then google sheet for custom
            try:
                master = cls.read(param["exofile"], **exofile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(GetLocalFileWarning(file="exofile", err=e))

        # Try to complement with custom values
        try:
            # Get custom values to be added to the exofile
            custom = GoogleSheet.query(param["sheet_key"], **kwargs)
            # Replace values in the exofile
            master.replace_with(custom)

        except Exception as e:
            if debug:
                raise e
            warn(QueryFileWarning(file="google sheet", err=e))

        return master

    @classmethod
    def load(
        cls,
        query=True,
        param=None,
        debug=None,
        query_kwargs=None,
        exofile_kwargs=None,
        **kwargs,
    ):
        """
        Returns the exofile complemented.
        Parameters
        - param: dict
            dictionnairy of the local files names. Default is param file.
            keys: 'exofile' and 'custom_file'
            `custom_file` will be use to replace values in the exofile.
            `exofile` is the local exofile.
        - query: bool
            query or not the exofile. If False, simply read `custom_file`
        - query_kwargs: None or dictionnary
            Passed to query() method
        - exofile_kwargs: None or dictionnary
            Passed to table.read() when reading the local exofile
            (see astropy.table.read)
        - kwargs
            Passed to table.read() when reading the custom table
            (see astropy.table.read)
        """
        # Assign default dictionnary values
        #  Never put {} in the function definition
        if param is None:
            param = {}
        if query_kwargs is None:
            query_kwargs = {}
        if exofile_kwargs is None:
            exofile_kwargs = {}

        # Use module parameters and complete with input parameters
        param = {**Param.load().value, **param}

        ###########################
        # Complement the exofile
        ###########################
        # Query online if True
        if query:
            # Try to query the complemented exofile.
            # If impossible, set query to False
            try:
                master = cls.query(**query_kwargs, exofile_kwargs=exofile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(QueryFileWarning(file="exofile", err=e))
                query = False

        # Read local exofile if query is False or query failed
        if not query:
            # Try to read locally
            try:
                master = cls.read(param["exofile"], **exofile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(GetLocalFileWarning(file="exofile", err=e))
                # Return custom_file as last ressort
                return cls.read(param["custom_file"], **kwargs)

        # Finally, complement with the local `custom_file`
        try:
            custom = cls.read(param["custom_file"], **kwargs)
            master.replace_with(custom)
        except Exception as e:
            if debug == "raise":
                raise e
            warn(GetLocalFileWarning(file="custom file", err=e))

        return master

    @classmethod
    def load_ref(cls, query=True, param=None, debug=None, **kwargs):
        """
        Returns the exofile reference table complemented.
        Parameters
        - param: dict
            dictionnairy of the local files names. Default is param file.
            keys: 'exofile' and 'custom_file'
            `custom_file` will be use to replace values in the exofile.
            `exofile` is the local exofile.
        - query: bool
            query or not the exofile. If False, simply read `custom_file`
        - kwargs are passed to query() method
        """
        # Assign default values
        if param is None:
            param = {}  # Never put {} in the function definition
        param = {**Param.load().value, **param}

        ###########################
        # Complement the exofile
        ###########################
        # Query online if True
        if query:
            # Try to query the complemented exofile.
            # If impossible, set query to False
            try:
                master = cls.query(
                    url_key="url_ref", sheet_name="Ref", keep_units=False
                )
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(QueryFileWarning(file="reference file", err=e))
                query = False

        # Read local exofile if query is False or query failed
        if not query:
            # Try to read locally
            try:
                master = cls.read(param["ref_file"])
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(GetLocalFileWarning(file="reference file", err=e))
                # Return 'custom ref' everywhere as last resort
                custom = cls.read(param["custom_file"])
                return custom.mk_unique_ref_table("custom ref")

        # Finally, complement with the local `custom_file`
        try:
            # Read the file
            custom = cls.read(param["custom_file"])
            # Convert in a reference table
            custom = custom.mk_unique_ref_table("custom ref")
            # Edit master ref table
            master.replace_with(custom)
        except Exception as e:
            if debug == "raise":
                raise e
            warn(GetLocalFileWarning(file="custom file", err=e))

        return master

    def write_to_custom(self, *args, **kwargs):

        file = Param.load().value["custom_file"]
        self.write(file, *args, **kwargs)

    def estim_ephemeride_err(
        self, ephemeride="pl_tranmid", err_ext="err1", orbper_ext=None
    ):
        """
        Compute error on the ephemeride time as of today.
        Create and add the column 'today_{ephemeride}{err_ext}'.
        Default will be: 'today_pl_tranmiderr1'
        """
        # Take same err_ext for
        if orbper_ext is None:
            orbper_ext = err_ext

        # Get transit mid time and period
        tranmid = self[ephemeride].to_array(units="d")
        orbper = self["pl_orbper"].to_array(units="d")

        # Compute number of period since transit mid time
        n_period = (Time.now().jd - tranmid) / orbper

        # Get corresponding errors
        orbper_err = self["pl_orbper" + orbper_ext].to_array(units="d")
        tranmid_err = self[ephemeride + err_ext].to_array(units="d")

        # Compute error as of today
        error_today = tranmid_err + n_period * orbper_err

        # Save as a column
        col = MaskedColumn(error_today, unit="d", name=f"today_{ephemeride}{err_ext}")
        self.add_column(col)

    @staticmethod
    def update(
            sort_keys: Optional[Union[str, List[str]]] = None,
            verbose: bool = True,
            use_composite_archive: bool = True,
            local_table: Optional[Union[str, Path]] = None,
        ):
        """
        Returns an updated masterfile built with the NasaExoplanetArchive.

        Parameters
        ----------
        sort_keys : str or list of str
            The key(s) to order the table by (passed to `astropy.table.sort`).
            If None, use the column 'today_tranmid_err'.
        """
        # Default sort keys
        if sort_keys is None:
            sort_keys = ["today_pl_tranmiderr1", "today_pl_orbtpererr1"]

        # Read new database from exoplanet archive
        if use_composite_archive:
            tbl_id = "pscomppars"
            tbl_name = PC_NAME
        else:
            tbl_id = "ps"
            tbl_name = PS_NAME

        if verbose:
            print(f"Querying {tbl_name}...", end="")

        # TODO: Make sure OK with composite tbl kwd if keep this
        if local_table is not None:
            new = ExoArchive.read(local_table)
            new = ExoArchive.format_table(new)
        else:
            new = ExoArchive.query(table=tbl_id)

        if not use_composite_archive:
            new = format_ps_table(new, verbose=verbose)
            new = compose_from_ps(new, sort_keys, verbose=verbose)

            # Get actual pc columns to compare with what's left.
            # Using CSV from Archive deletes too many columns
            pc_cols = ExoArchive.query(select="top 1 *").colnames

            # Now remove extra columns
            dlist = difference(new.colnames, pc_cols)
            del new[dlist]

            # Index with same order as pc_cols
            new = new[pc_cols]

            # Safety check
            if len(difference(new.colnames, pc_cols)) > 0 or len(difference(pc_cols, new.colnames)):
                raise RuntimeError(
                    f"The formatted {tbl_id} table is incompatible with the masterfile/composite table format"
                )

        if verbose:
            print("Done")

        ref_cols = [cn for cn in new.colnames if cn.endswith("reflink")]
        for cname in ref_cols:
            new[cname] = get_refname_from_links(new[cname])

        return new


class GoogleSheet(ExoFile):

    url_root = "https://docs.google.com/spreadsheets/d/{}/gviz/tq?tqx=out:csv&sheet={}"

    @classmethod
    def query(cls, key, sheet_name=0, check_units="silent", keep_units=True):

        url = cls.url_root.format(key, sheet_name)

        data = requests.get(url)

        # Convert to astropy table
        table = cls.read(data.text, format="ascii")

        # Remove units from the column name
        # The structure is: "name [units]"
        for key in table.keys():
            # Split name and units
            name, unit = key.split(" [")
            unit = unit.split("]")[0]

            # Rename and assign units
            table.rename_column(key, name)
            if unit != "None" and keep_units:
                table[name].unit = Unit(unit, parse_strict=check_units)
            else:
                table[name].unit = None

        return table


class ExoArchive(ExoFile):

    @classmethod
    def query(
            cls,
            table: str = "pscomppars",
            **criteria,
        ):
        """
        Query the NASA exoplanet using astroquery and return in a MasterFile object.
        Returns the full table by default
        Accepts the same criteria asu
        `astroquery.ipac.nexsci.nasa_exoplanet_archive.NasaExoplanetArchive.query_criteria()`
        """
        # Query and get astropy table
        data = NasaExoplanetArchive.query_criteria(table=table, **criteria)

        # Covnert to custom table
        data = cls(data, masked=True, copy=False)

        # sky_coord is duplicate of RA and DEC and causes problems with units and masking
        if "sky_coord" in data.colnames:
            del data["sky_coord"]

        # Correct units
        # ???: Is this still required now that we use astroquery ?
        data.correct_units(verbose=False)

        # Mask where errors are not available
        # NOTE: Calling separately because if the default (err1,err2) gives a KeyError,
        # we can try with err separately
        data.mask_no_errors()  # err1 and err2 cols
        data.mask_no_errors(err_ext=["err"])  # err cols

        # Mask where errors are set to zero
        data.mask_zero_errors()  # err1 and err2 cols
        data.mask_zero_errors(err_ext=["err"])  # err cols

        return data

    @classmethod
    def format_table(cls, data):

        # Covnert to custom table
        data = cls(data, masked=True, copy=False)

        # sky_coord is duplicate of RA and DEC and causes problems with units and masking
        if "sky_coord" in data.colnames:
            del data["sky_coord"]

        # Correct units
        # ???: Is this still required now that we use astroquery ?
        data.correct_units(verbose=False)

        # Mask where errors are not available
        # NOTE: Calling separately because if the default (err1,err2) gives a KeyError,
        # we can try with err separately
        data.mask_no_errors()  # err1 and err2 cols
        data.mask_no_errors(err_ext=["err"])  # err cols

        # Mask where errors are set to zero
        data.mask_zero_errors()  # err1 and err2 cols
        data.mask_zero_errors(err_ext=["err"])  # err cols

        return data


def load_exoplanet_archive_mappings(csv_path: Union[str, Path]) -> DataFrame:

    label_df = read_csv(
        csv_path,
        skiprows=[0, 2, 3],
        header=0,
        usecols=lambda x: not x.startswith("Unnamed: "),
    )

    return label_df


def format_ps_table(
        ps_tbl: Any,
        verbose: bool = False,
    ):
    # Map columns between PS and PS composite tables
    try:
        label_df = load_exoplanet_archive_mappings(ARCHIVE_CSV_PATH)
    except:
        param = {**Param.load().value, **{}}
        local_path = param["archive_mappings_csv"]
        label_df = load_exoplanet_archive_mappings(local_path)

    label_df_all = label_df.copy()
    label_df = label_df.dropna(subset=[PS_NAME, PC_NAME])
    label_df = label_df[~label_df[PS_NAME].str.contains("systemref")]
    label_ps = label_df[PS_NAME].str.strip()
    label_pc = label_df[PS_NAME].str.strip()

    for lps, lpc in zip(label_ps, label_pc):
        # Some columns are missing even if in CSV
        if lps not in MISSING_COLS:
            try:
                ps_tbl.rename_column(lps, lpc)
            except KeyError:
                warn(f"Column {lps} was not found in new table", RuntimeWarning)
    # Ref time keys are mismatched in CSV so one will be missing, need to update
    tper_ref = "pl_orbtper_systemref"
    tranmid_ref = "pl_tranmid_systemref"
    tsys_ref = "pl_tsystemref"
    ps_tbl[tranmid_ref] = ps_tbl[tsys_ref]
    ps_tbl[tper_ref] = ps_tbl[tsys_ref]

    # Format references to match composite table format (masterfile default)
    if verbose:
        print("Formatting references to match composite table format...", end="")

    reflink_labels = label_df_all.dropna(subset=PC_NAME)[PC_NAME]
    reflink_labels = reflink_labels.str.strip()
    reflink_labels= reflink_labels[reflink_labels.str.endswith("reflink")]
    for rlab in reflink_labels:

        plab = rlab.replace("_reflink", "")
        if isinstance(ps_tbl[plab][0], str) or ps_tbl[plab].dtype.kind in ["U", "S"]:
            nmask = ps_tbl[plab] == ""
        else:
            nmask = np.isnan(ps_tbl[plab])


        if rlab.startswith("st_"):
            new_refs = ps_tbl["st_refname"]
        elif rlab.startswith(("sy_", "ra_")):
            new_refs = ps_tbl["sy_refname"]
        elif rlab.startswith("pl_"):
            new_refs = ps_tbl["pl_refname"]
        else:
            warn(f"Reference {rlab} has no known match. Setting to ''.")
            new_refs = ""

        ps_tbl[rlab] = MaskedColumn(np.where(nmask, "", new_refs))

    if verbose:
        print("Done")

    return ps_tbl


def compose_from_ps(
        ps_tbl,
        sort_keys: Union[str, List[str]],
        verbose: bool = False,
    ):
    # This creates a composite table, but using full rows instead of using the most precise
    # for each parameter individually as (I think) done for NASA archive.

    default_mask = ps_tbl["default_flag"] == 1
    extended = ps_tbl[~default_mask]
    ps_tbl = ps_tbl[default_mask]

    # Add estimate of transit mid time error as of today
    extended.estim_ephemeride_err()

    # Add estimate of transit mid time error as of today
    extended.estim_ephemeride_err(ephemeride="pl_orbtper")

    # Sort to choose the reference accordingly
    extended.sort(sort_keys)

    # Separate bet
    # Group by planet's name
    grouped = extended.group_by(["pl_name"])

    # Complete new table with extended table
    if verbose:
        print(
            "Completing database with extended database (may take some time)...",
            end="",
        )

    # Fill all the values we can until nothing left or ps is completely filled
    i = 0
    while len(grouped) > 1 and ps_tbl.has_masked_values:

        print(f"Pass {i}")
        i+=1

        # Groupe by planet name
        grouped = grouped.group_by(["pl_name"])

        # "index" gives the first entry for each planet
        # (i.e. the star of each group where table is grouped by pl_name)
        index = grouped.groups.indices[:-1]

        # Add to master table
        # NOTE: This assumes that reflink will be masked if the value is masked.
        # Usually true, but would not hurt to check it somewhere
        ps_tbl = ps_tbl.complete(
            grouped[index], "pl_name", add_col=False, verbose=False
        )

        # Remove from the main table
        grouped.remove_rows(index)

    if verbose:
        print("Done")

    return ps_tbl
