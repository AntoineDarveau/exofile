# Librairy imports
import re
# from numpy import where, array
from warnings import warn

import numpy as np
import requests
from astropy.time import Time
from astropy.units import Unit

from .config import Param
from .exceptions import (ColUnitsWarning, GetLocalFileWarning, NoUnitsWarning,
                         QueryFileWarning)
# Local imports
from .table_custom import MaskedColumn, Table


def get_refname_from_link(link):
    """
    Get the text from a reflink
    """
    out = re.search(">(.*)</a>", link).group(1)

    return out.strip()


def get_refname_from_links(links):
    """
    Get the text from multiple reflinks
    """
    return [get_refname_from_link(link) for link in links]


class MasterFile(Table):

    main_col = "pl_name"

    def mk_ref_table(self, ref_link=True, ref_col="mpl_reflink"):
        """
        Return a table with the same structure as self, but with the
        name of the reference at each position.

        Parameters:
        - ref_link: bool
            Extract the reference name from a url link using
            the function get_refname_from_links
        - ref_col: string
            Which column to use as the reference
        """

        # Initiate table with the same structure
        keys = self.keys()
        out = MasterFile(
            names=keys,
            dtype=["bytes" for k in keys],
            masked=True,
            data=self.mask.copy(),
        )
        # Remove units from column definition
        for key in out.keys():
            out[key].unit = None

        # Get all references
        if ref_link:
            refs = get_refname_from_links(self[ref_col])
        else:
            refs = MaskedColumn(self[ref_col], dtype="bytes")

        # Put the ref in each columns
        for key in keys:
            out[key] = refs

        out["pl_name"] = self["pl_name"]  # Keep the planet name
        out.mask = self.mask  # Keep mask

        return out

    def mk_unique_ref_table(self, ref="No Ref"):
        """
        Return a table with the same structure as self, but with the
        name of the reference at each position.

        Parameters:
        - ref_link: bool
            Extract the reference name from a url link using
            the function get_refname_from_links
        - ref_col: string
            Which column to use as the reference
        """

        # Initiate table with the same structure
        keys = self.keys()
        mask = Table(self, copy=True, masked=True).mask
        out = MasterFile(
            names=keys, dtype=["bytes" for k in keys], masked=True, data=mask
        )
        # Remove units from column definition
        for key in out.keys():
            out[key].unit = None

        refs = MaskedColumn([ref for lines in self], dtype="bytes")

        # Put the ref in each columns
        for key in keys:
            out[key] = refs

        out["pl_name"] = self["pl_name"]  # Keep the planet name
        out.mask = mask  # Keep mask

        return out

    def get_colnames_with_error(self, err_ext=["err1", "err2"]):
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

    @staticmethod
    def update(sort_keys=None, verbose=True):
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
        if verbose:
            print("Query Confirmed Planet Table...", end="")

        new = PlanetArchive.query()

        if verbose:
            print("Done")

        # Read new extended database from exoplanet archive to complete it
        if verbose:
            print("Query extended database....", end="")

        extended = ExtendedArchive.query()

        if verbose:
            print("Done")

        # Change columns names to match confirmed planet table
        extended.ch_col_names()

        # Remove used reference (already in Planet table)
        (index,) = np.where(extended["mpl_def"])
        extended.remove_rows(index)

        # Add estimate of transit mid time error as of today
        extended.estim_ephemeride_err()

        # Add estimate of transit mid time error as of today
        extended.estim_ephemeride_err(ephemeride="pl_orbtper")

        # Sort to choose the reference accordingly
        extended.sort(sort_keys)

        # Group by planet's name
        grouped = extended.group_by(["pl_name"])

        # Define a separate reference table
        if verbose:
            print("Building new reference table...", end="")

        keys = extended.keys()
        ref_table = new.mk_ref_table(ref_link=False, ref_col="pl_def_refname")

        if verbose:
            print("Done")

        # Convert to the same class
        # (astropy.table.join doesn't like to join different classes)
        grouped = PlanetArchive(grouped)

        # Complete new table with extended table
        if verbose:
            print(
                "Completing database with extended database (may take some time)...",
                end="",
            )

        while len(grouped) > 1:

            # Groupe by planet name
            grouped = grouped.group_by(["pl_name"])
            index = grouped.groups.indices[:-1]

            # Add to master table
            new = new.complete(grouped[index], "pl_name", add_col=False, verbose=False)

            # Add ref to ref_table
            ref = grouped[index].mk_ref_table()
            ref_table = ref_table.complete(ref, "pl_name", add_col=False, verbose=False)

            # Remove from the main table
            grouped.remove_rows(index)

        if verbose:
            print("Done")

        return new, ref_table

    def replace_with(self, other, main_col=None):
        """
        Use all non-masked values of `other` to replace values in `self`.
        `key` is the column use to identify corresponding rows.
        Default is other.main_col
        """

        # Take main_col if key is not given
        main_col = main_col or other.main_col

        # Make sure `other` is masked
        other = MasterFile(other, copy=True, masked=True)

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
    def query(cls, url_key="url", debug=False, masterfile_kwargs=None, **kwargs):
        """
        Query the masterfile and try to complement it with
        the custom table (google sheet).
        Returns the complemented masterfile.
        Parameters:
        - url: string
            adress of the masterfile
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
            # If SSLError, maybe just the masterfile website is problem,
            # still try local file and then google sheet for custom
            try:
                master = cls.read(param["masterfile"], **masterfile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(GetLocalFileWarning(file="masterfile", err=e))

        # Try to complement with custom values
        try:
            # Get custom values to be added to the masterfile
            custom = GoogleSheet.query(param["sheet_key"], **kwargs)
            # Replace values in the masterfile
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
        masterfile_kwargs=None,
        **kwargs,
    ):
        """
        Returns the masterfile complemented.
        Parameters
        - param: dict
            dictionnairy of the local files names. Default is param file.
            keys: 'masterfile' and 'custom_file'
            `custom_file` will be use to replace values in the masterfile.
            `masterfile` is the local masterfile.
        - query: bool
            query or not the masterfile. If False, simply read `custom_file`
        - query_kwargs: None or dictionnary
            Passed to query() method
        - masterfile_kwargs: None or dictionnary
            Passed to table.read() when reading the local masterfile
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
        if masterfile_kwargs is None:
            masterfile_kwargs = {}

        # Use module parameters and complete with input parameters
        param = {**Param.load().value, **param}

        ###########################
        # Complement the masterfile
        ###########################
        # Query online if True
        if query:
            # Try to query the complemented masterfile.
            # If impossible, set query to False
            try:
                master = cls.query(**query_kwargs, masterfile_kwargs=masterfile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(QueryFileWarning(file="masterfile", err=e))
                query = False

        # Read local masterfile if query is False or query failed
        if not query:
            # Try to read locally
            try:
                master = cls.read(param["masterfile"], **masterfile_kwargs)
            except Exception as e:
                if debug == "raise":
                    raise e
                warn(GetLocalFileWarning(file="masterfile", err=e))
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
        Returns the masterfile reference table complemented.
        Parameters
        - param: dict
            dictionnairy of the local files names. Default is param file.
            keys: 'masterfile' and 'custom_file'
            `custom_file` will be use to replace values in the masterfile.
            `masterfile` is the local masterfile.
        - query: bool
            query or not the masterfile. If False, simply read `custom_file`
        - kwargs are passed to query() method
        """
        # Assign default values
        if param is None:
            param = {}  # Never put {} in the function definition
        param = {**Param.load().value, **param}

        ###########################
        # Complement the masterfile
        ###########################
        # Query online if True
        if query:
            # Try to query the complemented masterfile.
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

        # Read local masterfile if query is False or query failed
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


class GoogleSheet(MasterFile):

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


class BaseArchive(MasterFile):

    url_root = "http://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?"

    @classmethod
    def _query(cls, url_tail):
        """
        Get the extended planet table from exoplanet archive
        """
        # Query
        data = requests.get(cls.url_root + url_tail)

        # Convert to an astropy Table
        data = cls.read(data.text, format="ascii")

        # Correct
        data.correct_units(verbose=False)

        # Mask where errors are not available
        data.mask_no_errors()  # err1 and err2 cols
        data.mask_no_errors(err_ext=["err"])  # err cols

        # Mask where errors are set to zero
        data.mask_zero_errors()  # err1 and err2 cols
        data.mask_zero_errors(err_ext=["err"])  # err cols

        return data


class PlanetArchive(BaseArchive):

    main_col = "pl_name"

    @classmethod
    def query(cls, url_tail="table=exoplanets&select=*&format=ascii"):
        """
        Get the extended planet table from exoplanet archive
        """
        return cls._query(url_tail)


class ExtendedArchive(BaseArchive):
    @classmethod
    def query(cls, url_tail="table=exomultpars&select=*&format=ascii"):
        """
        Get the extended planet table from exoplanet archive
        """
        return cls._query(url_tail)

    def ch_col_names(self):
        """
        Give the same name as the Confirmed Planet table.
        """

        self.rename_columns(
            [
                "mpl_hostname",
                "mpl_letter",
                "mpl_discmethod",
                "mpl_pnum",
                "mpl_orbper",
                "mpl_orbpererr1",
                "mpl_orbpererr2",
                "mpl_orbperlim",
                "mpl_orbsmax",
                "mpl_orbsmaxerr1",
                "mpl_orbsmaxerr2",
                "mpl_orbsmaxlim",
                "mpl_orbeccen",
                "mpl_orbeccenerr1",
                "mpl_orbeccenerr2",
                "mpl_orbeccenlim",
                "mpl_orbincl",
                "mpl_orbinclerr1",
                "mpl_orbinclerr2",
                "mpl_orbincllim",
                "mpl_bmassj",
                "mpl_bmassjerr1",
                "mpl_bmassjerr2",
                "mpl_bmassjlim",
                "mpl_bmassprov",
                "mpl_radj",
                "mpl_radjerr1",
                "mpl_radjerr2",
                "mpl_radjlim",
                "mpl_dens",
                "mpl_denserr1",
                "mpl_denserr2",
                "mpl_denslim",
                "ra_str",
                "dec_str",
                "ra",
                "dec",
                "mst_teff",
                "mst_tefferr1",
                "mst_tefferr2",
                "mst_tefflim",
                "mst_mass",
                "mst_masserr1",
                "mst_masserr2",
                "mst_masslim",
                "mst_rad",
                "mst_raderr1",
                "mst_raderr2",
                "mst_radlim",
                "rowupdate",
                "mpl_name",
                "mpl_tranflag",
                "mpl_rvflag",
                "mpl_ttvflag",
                "mpl_orbtper",
                "mpl_orbtpererr1",
                "mpl_orbtpererr2",
                "mpl_orbtperlim",
                "mpl_orblper",
                "mpl_orblpererr1",
                "mpl_orblpererr2",
                "mpl_orblperlim",
                "mpl_rvamp",
                "mpl_rvamperr1",
                "mpl_rvamperr2",
                "mpl_rvamplim",
                "mpl_eqt",
                "mpl_eqterr1",
                "mpl_eqterr2",
                "mpl_eqtlim",
                "mpl_insol",
                "mpl_insolerr1",
                "mpl_insolerr2",
                "mpl_insollim",
                "mpl_massj",
                "mpl_massjerr1",
                "mpl_massjerr2",
                "mpl_massjlim",
                "mpl_msinij",
                "mpl_msinijerr1",
                "mpl_msinijerr2",
                "mpl_msinijlim",
                "mpl_masse",
                "mpl_masseerr1",
                "mpl_masseerr2",
                "mpl_masselim",
                "mpl_msinie",
                "mpl_msinieerr1",
                "mpl_msinieerr2",
                "mpl_msinielim",
                "mpl_bmasse",
                "mpl_bmasseerr1",
                "mpl_bmasseerr2",
                "mpl_bmasselim",
                "mpl_rade",
                "mpl_radeerr1",
                "mpl_radeerr2",
                "mpl_radelim",
                "mpl_rads",
                "mpl_radserr1",
                "mpl_radserr2",
                "mpl_trandep",
                "mpl_trandeperr1",
                "mpl_trandeperr2",
                "mpl_trandeplim",
                "mpl_trandur",
                "mpl_trandurerr1",
                "mpl_trandurerr2",
                "mpl_trandurlim",
                "mpl_tranmid",
                "mpl_tranmiderr1",
                "mpl_tranmiderr2",
                "mpl_tranmidlim",
                "mpl_tsystemref",
                "mpl_imppar",
                "mpl_impparerr1",
                "mpl_impparerr2",
                "mpl_impparlim",
                "mpl_occdep",
                "mpl_occdeperr1",
                "mpl_occdeperr2",
                "mpl_occdeplim",
                "mpl_ratdor",
                "mpl_ratdorerr1",
                "mpl_ratdorerr2",
                "mpl_ratdorlim",
                "mpl_ratror",
                "mpl_ratrorerr1",
                "mpl_ratrorerr2",
                "mpl_ratrorlim",
                "mpl_disc",
                "mpl_status",
                "mpl_mnum",
                "mpl_publ_date",
                "hd_name",
                "hip_name",
                "mst_logg",
                "mst_loggerr1",
                "mst_loggerr2",
                "mst_logglim",
                "mst_lum",
                "mst_lumerr1",
                "mst_lumerr2",
                "mst_lumlim",
                "mst_dens",
                "mst_denserr1",
                "mst_denserr2",
                "mst_denslim",
                "mst_metfe",
                "mst_metfeerr1",
                "mst_metfeerr2",
                "mst_metfelim",
                "mst_metratio",
                "mst_age",
                "mst_ageerr1",
                "mst_ageerr2",
                "mst_agelim",
                "swasp_id",
            ],
            [
                "pl_hostname",
                "pl_letter",
                "pl_discmethod",
                "pl_pnum",
                "pl_orbper",
                "pl_orbpererr1",
                "pl_orbpererr2",
                "pl_orbperlim",
                "pl_orbsmax",
                "pl_orbsmaxerr1",
                "pl_orbsmaxerr2",
                "pl_orbsmaxlim",
                "pl_orbeccen",
                "pl_orbeccenerr1",
                "pl_orbeccenerr2",
                "pl_orbeccenlim",
                "pl_orbincl",
                "pl_orbinclerr1",
                "pl_orbinclerr2",
                "pl_orbincllim",
                "pl_bmassj",
                "pl_bmassjerr1",
                "pl_bmassjerr2",
                "pl_bmassjlim",
                "pl_bmassprov",
                "pl_radj",
                "pl_radjerr1",
                "pl_radjerr2",
                "pl_radjlim",
                "pl_dens",
                "pl_denserr1",
                "pl_denserr2",
                "pl_denslim",
                "ra_str",
                "dec_str",
                "ra",
                "dec",
                "st_teff",
                "st_tefferr1",
                "st_tefferr2",
                "st_tefflim",
                "st_mass",
                "st_masserr1",
                "st_masserr2",
                "st_masslim",
                "st_rad",
                "st_raderr1",
                "st_raderr2",
                "st_radlim",
                "rowupdate",
                "pl_name",
                "pl_tranflag",
                "pl_rvflag",
                "pl_ttvflag",
                "pl_orbtper",
                "pl_orbtpererr1",
                "pl_orbtpererr2",
                "pl_orbtperlim",
                "pl_orblper",
                "pl_orblpererr1",
                "pl_orblpererr2",
                "pl_orblperlim",
                "pl_rvamp",
                "pl_rvamperr1",
                "pl_rvamperr2",
                "pl_rvamplim",
                "pl_eqt",
                "pl_eqterr1",
                "pl_eqterr2",
                "pl_eqtlim",
                "pl_insol",
                "pl_insolerr1",
                "pl_insolerr2",
                "pl_insollim",
                "pl_massj",
                "pl_massjerr1",
                "pl_massjerr2",
                "pl_massjlim",
                "pl_msinij",
                "pl_msinijerr1",
                "pl_msinijerr2",
                "pl_msinijlim",
                "pl_masse",
                "pl_masseerr1",
                "pl_masseerr2",
                "pl_masselim",
                "pl_msinie",
                "pl_msinieerr1",
                "pl_msinieerr2",
                "pl_msinielim",
                "pl_bmasse",
                "pl_bmasseerr1",
                "pl_bmasseerr2",
                "pl_bmasselim",
                "pl_rade",
                "pl_radeerr1",
                "pl_radeerr2",
                "pl_radelim",
                "pl_rads",
                "pl_radserr1",
                "pl_radserr2",
                "pl_trandep",
                "pl_trandeperr1",
                "pl_trandeperr2",
                "pl_trandeplim",
                "pl_trandur",
                "pl_trandurerr1",
                "pl_trandurerr2",
                "pl_trandurlim",
                "pl_tranmid",
                "pl_tranmiderr1",
                "pl_tranmiderr2",
                "pl_tranmidlim",
                "pl_tsystemref",
                "pl_imppar",
                "pl_impparerr1",
                "pl_impparerr2",
                "pl_impparlim",
                "pl_occdep",
                "pl_occdeperr1",
                "pl_occdeperr2",
                "pl_occdeplim",
                "pl_ratdor",
                "pl_ratdorerr1",
                "pl_ratdorerr2",
                "pl_ratdorlim",
                "pl_ratror",
                "pl_ratrorerr1",
                "pl_ratrorerr2",
                "pl_ratrorlim",
                "pl_disc",
                "pl_status",
                "pl_mnum",
                "pl_publ_date",
                "hd_name",
                "hip_name",
                "st_logg",
                "st_loggerr1",
                "st_loggerr2",
                "st_logglim",
                "st_lum",
                "st_lumerr1",
                "st_lumerr2",
                "st_lumlim",
                "st_dens",
                "st_denserr1",
                "st_denserr2",
                "st_denslim",
                "st_metfe",
                "st_metfeerr1",
                "st_metfeerr2",
                "st_metfelim",
                "st_metratio",
                "st_age",
                "st_ageerr1",
                "st_ageerr2",
                "st_agelim",
                "swasp_id",
            ],
        )
