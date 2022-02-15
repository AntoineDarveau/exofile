from collections import OrderedDict
from warnings import warn

from astropy.table import join
import astropy.table as table
from astropy.table.operations import _join, _merge_table_meta
from astropy.units import Unit
import numpy as np
from astropy.coordinates import SkyCoord


class MaskedColumn(table.MaskedColumn):

    def find(self, sub, start=0, end=None):
        if isinstance(self, (MaskedColumn)):
            str_array = np.array(self, dtype=str)
            index = np.core.defchararray.find(str_array, sub, start=start, end=end) != -1
            return np.where(index)[0], str_array[index]

        else:
            return NotImplemented

    def to_array(self, units=None):
        """
        Returns the columns as a MaskedArray.
        If units are specified, convert to good units
        before returning the array.
        """
        if units is None:
            return self.data.copy()
        else:
            # Convert to quantity array
            data = self.quantity
            # Need to stored masked values
            # (quantity arrays don't deal with masks)
            mask = self.mask

            # Make sure it has the good units
            data = data.to(units)

            # Convert to masked array
            return np.ma.array(data.value, mask=mask)


class Column(table.Column):

    def find(self, sub, start=0, end=None):
        if isinstance(self, (Column)):
            str_array = np.array(self, dtype=str)
            index = np.core.defchararray.find(str_array, sub, start=start, end=end) != -1
            return np.where(index)[0], str_array[index]

        else:
            return NotImplemented

    def to_array(self, units=None):
        """
        Returns the columns as an array.
        If units are specified, convert to good units
        before returning the array.
        """
        if units is None:
            return self.data.copy()
        else:
            # Convert to quantity array
            data = self.quantity

            # Make sure it has the good units
            data = data.to(units)

            # Convert to array
            return np.array(data.value)


class Table(table.Table):

    # Redefine class attributes (if not, the originals would be taken)
    Column = Column
    MaskedColumn = MaskedColumn

    # Set attributes
    main_col = None  # Default column used to order
    log = []  # Save output when using insert_value method

    # New methods
    def rename_columns(self, old, new):

        for ko, kn in zip(old, new):
            self.rename_column(ko, kn)

    def nan_to_mask(self):
        """
        Replace nan by masked array
        """
        if self.masked:
            for k in self.keys():
                if self[k].dtype == float:
                    self[k].mask = np.isnan(self[k])
        else:
            raise TypeError("Input must be a Masked Table." +
                            "\n \t Set its mask to True before calling" +
                            " (example: t = Table(t,masked=True)).")

    def by_pl_name(self, *plName, name_key=None, remove=False):
        """
        Return the complete line of a given planet name (plName)
        """
        position = self.get_index(*plName, name_key=name_key)

        out = self[position]

        if remove and len(position) == 1:
            print(str(*plName) + ' has been removed')
            self.remove_row(int(position[0]))

        return out

    def by_plName(self, *args, **kwargs):
        """
        Old name of by_pl_name. Just an alias
        """

        return self.by_pl_name(*args, **kwargs)

    def get_index(self, *plName, name_key=None):
        '''
        Return the lines index where plName are located for the column given by name_key
        name_key default is given by main_col attribute of the object
        '''
        name_key = name_key or self.main_col

        position = []
        for pl in plName:
            try:
                position.append(int(self[name_key].find(pl)[0]))

            except TypeError:
                values = ', '.join(self[name_key].find(pl)[1])
                if values:
                    raise ValueError(
                        'Incomplete name. Possible values: '
                        + values
                    )
                else:
                    raise ValueError(
                        f"Unkonwn planet '{pl}'."
                    )
        
        return position

    def set_main_col(self, colname=None, extension='_temp'):
        '''
        Set self.main_col and assign it to the first column.
        If colname is None, simply assign self.main_col to the
        first column.
        '''
        if self.main_col is None:
            self.main_col = colname
        elif colname is None:
            colname = self.main_col

        colname_temp = colname+extension
        self.rename_column(colname, colname_temp)
        self.add_column(self[colname_temp], name=colname, index=0)
        self.remove_column(colname_temp)

    def correct_units(self, badunits=['degrees', 'days', 'hours','jovMass', 'mags'],
                     gunits=['degree', 'day', 'hour','jupiterMass', 'mag'], verbose=True,
                     debug=False):
        '''
        Correct columns units for astropy units
        '''
        text_frame = "Column {} corrected for '{}' unit (previous was '{}')"

        for col in self.colnames:
            if debug:
                print(col, self[col].unit)

            # Skip skycoord: no unit attribute
            if isinstance(self[col], SkyCoord):
                continue

            # Search for bad units
            # TODO: check if unit is in list instead of loop and use dict
            # to replace
            for bunit, gunit in zip(badunits, gunits):
                if self[col].unit == bunit:
                    self[col].unit = gunit

                    # Message and log it
                    self.log.append(
                        text_frame.format(col, self[col].unit, bunit))
                    if verbose:
                        print(self.log[-1])
                    print(self.log[-1])

    def cols_2_qarr(self, *keys):
        '''
        Returns columns given in input as astropy q_arrays
        '''

        warn(DeprecationWarning(
            "This method will be removed in future versions. Do not use it."))

        out = []
        for k in keys:
            try:
                out.append(np.ma.array(self[k].data) * self[k].unit)
            except TypeError:
                out.append(np.ma.array(self[k].data))

        return tuple(out)

    def set_units(self, units, cols=None):
        '''
        Assign units to columns.
        units:
          list of units (str or astropy units) to be assign
        cols:
          list of columns names (str).
          If None is given, it takes all the keys, so Table.keys() as default
        '''

        if not cols:
            cols = self.keys()

        for col, u in zip(cols, units):
            self[col].unit = u

    def new_value(self, plName, col, value):

        names = np.array(self[self.main_col], dtype=str)
        position = np.where(names == plName)[0]

        self[col][position] = value

    def complete(self, right, key=None, join_type='left',
                 add_col=True, metadata_conflicts='warn',
                 verbose=True, debug=False, **kwargs):
        """
        Add every missing data in self if present in right.

        join_type : 'inner': do not add new rows
                    'outer': add new rows if not present in self
        add_col: add new colums from right
        """

        key = key or self.main_col

        # Try converting inputs to Table as needed
        if not isinstance(right, Table):
            right = Table(right)

        try:
            out = self._complete(right, key=key, join_type=join_type,
                                 add_col=add_col, verbose=verbose, debug=debug)
        except:
            warn("Custom table completion failed, trying default astropy join.")
            # NOTE: This seemd to break when I tested it quickly,
            # but I needed masking anyway so I did not get to the bottom of the problem.
            # - Thomas
            col_name_map = OrderedDict()
            out = _join(
                self,
                right,
                join_type=join_type,
                col_name_map=col_name_map,
                keys=key,
                **kwargs
            )

        # Merge the column and table meta data. Table subclasses might override
        # these methods for custom merge behavior.
        _merge_table_meta(out, [self, right], metadata_conflicts=metadata_conflicts)

        return out

    def _complete(self, right, key=None, join_type='left', add_col=True,
                  verbose=True, debug=False):

        if not key:
            raise ValueError('key is empty')

        # Save shared columns without "key"
        cols = intersection(self.keys(), right.keys())
        cols.remove(key)

        # Join tables
        join_t = join(self, right, join_type=join_type, keys=key)

        # Complete masked values of "self" if available in "right"
        for col in cols:

            # Add eventually a condition to check units!

            # Names of joined columns (default from join())
            col1, col2 = col + '_1', col + '_2'

            # Index of masked in "self" and not masked in "right"
            index = join_t[col1].mask & ~join_t[col2].mask

            # Reassign value
            join_t[col1].unshare_mask()
            join_t[col1][index] = join_t[col2][index]

            # Remove 2nd column and rename to original
            join_t[col1].name = col
            del join_t[col2]

        # Remove added columns from "right" if not wanted
        supp_cols = difference(right.keys(), self.keys())
        if debug: print(supp_cols)

        if not add_col and supp_cols:
            if verbose:
                print('remove non shared columns from second table')
            join_t.remove_columns(supp_cols)

        return join_t

    def complete_cols(self, col_in, col_out, name_key=None):
        '''
        Use a column from table to complete another column.
        Input:
            col_in: list of names of columns to use (list of str)
            col_out: list of names of columns to complete (list of str)
        '''
        # Take default col if none is given
        name_key = name_key or self.main_col

        # Def table with cols to use and rename it to cols to complete
        temp_table = Table(self[[name_key] + col_in], masked=True)
        temp_table.nan_to_mask()
        temp_table.rename_columns(col_in, col_out)

        # Complete with the temp_table
        return self.complete(temp_table, key=name_key)

    def add_calc_col(self, fct, *args, f_args=(), f_kwargs={}, col_keys=[], **kwargs):
        '''
        Add new column wich is the result of fct(table[col_keys], *f_args, **f_kwargs)

        args and kwargs are passed to MaskedColumn instantiation

        '''

        # Build tuple of columns inputs to fct and add to f_args
        cols = ()
        for key in col_keys:
            cols += (self[key],)
        f_args = cols + f_args

        # Define column and add it
        col = MaskedColumn(*args, data=fct(*f_args, **f_kwargs), **kwargs)
        self.add_column(col)

    def check_col_units(self, colname):

        col_units = self[colname].unit
        try:  # Check if col_units valid
            1. * Unit(col_units)
        except TypeError:
            print('Column has no units (unit = None)')
        except:  # Enter valid unit and refresh all table
            print("Column units '{}' are not".format(col_units) +
                          ' recognized by astropy.\n')
            print("Error message from astropy:")
            print_unit_error(str(col_units))
            print("-------------------------")
            gunit = input('***** Please enter the corresponding unit'
                          + ' recognized by astropy unit: ')
            self.correct_units(badunits=[str(col_units)], gunits=[gunit])


def difference(left, right):
    if isinstance(left, list) and isinstance(right, list):
        return list(set(left) - set(right))
    else:
        return NotImplemented


def intersection(tbl, other):
    if isinstance(tbl, list):
        return list(set(tbl).intersection(other))
    else:
        return NotImplemented


def print_unit_error(str_unit):

    try:
        Unit(str_unit)
    except ValueError as e:
        print(e)
