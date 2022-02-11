from collections import OrderedDict
from os import remove
from os.path import abspath, dirname
from warnings import warn

import yaml


# --------------------------------
# Usefull functions
# --------------------------------

def get_module_path(file):

    dir_path = abspath(file)
    dir_path = dirname(dir_path) + '/'

    return dir_path

# ----------------------------------
# Functions for param
# ----------------------------------
class Param():

    default_file = get_module_path(__file__) + 'param.yaml'

    def __init__(self, value, description=None):

        # Make sure they are OrderedDict
        value = OrderedDict(value)

        if description is None:
            self.value = OrderedDict()
            self.description = OrderedDict()
            for key in value:
                try:
                    self[key] = value[key]
                except TypeError:
                    raise
        else:
            description = OrderedDict(description)

            self.value = value
            self.description = description

    @classmethod
    def load(cls, filename=None, raise_err=False, **kwargs):

        kwargs = {'Loader':yaml.Loader, **kwargs}

        if filename is None:
            output = cls._load_default(raise_err, **kwargs)
            return cls(output)

        try:
            with open(filename) as f:
                output = yaml.load(f, **kwargs)
        except FileNotFoundError as e:
            message = str(e) + '. Taking default param instead.'
            warn(message)
            output = cls._load_default(raise_err, **kwargs)

        return cls(output)

    @classmethod
    def _load_default(cls, raise_err, **kwargs):

        try:
            with open(cls.default_file) as f:
                    output = yaml.load(f, **kwargs)
        except FileNotFoundError as e:
            if raise_err:
                message = str(e) \
                   + ". You need to configurate the exofile. \n"  \
                   + "Example:  \n"  \
                   + ">>> from exofile.config import edit_param  \n" \
                   + ">>> edit_param(sheet_key='the_key_to_the_google_sheet',) \n"  \
                   + ">>> edit_param(url='url_to_exofile',"  \
                   + " url_ref='url_to_exofile_references')"
                raise FileNotFoundError(message)
            else:
                configurate()
                with open(cls.default_file) as f:
                        output = yaml.load(f, **kwargs)
        return output

    def dump(self, filename=None, **kwargs):

        if filename is None:
            filename = self.default_file

        with open(filename, 'w') as f:
            yaml.dump(self.to_dict(), f, **kwargs)


    def to_dict(self):

        out = OrderedDict()
        for key in self.value:
            out[key] = {'Value':self.value[key],
                        'Description':self.description[key]}
        return out

    def __repr__(self):

        return yaml.dump(self.to_dict())

    def __eq__(self, other):

        return self.value == other.value


    def __getitem__(self, key):

        return {'Value':self.value[key], 'Description':self.description[key]}

    def __setitem__(self, key, value):

        if isinstance(value, dict):
            self.value[key] = value['Value']
            self.description[key] = value['Description']
        elif isinstance(value, list):
            self.value[key] = value[0]
            self.description[key] = value[1]
        else:
            self.value[key] = value
            self.description[key] = None

    def keys(self):

        return self.value.keys()

    def __iter__(self):

        yield from self.keys()



def edit_param(**param_kwargs):

    # Load param default file (param.yaml in module)
    param = Param.load()

    # Convert into Param object
    param_kwargs = Param(param_kwargs)

    # Take default description if not given
    for key in param_kwargs:
        desc = param_kwargs.description
        if desc[key] is None:
            try:
                desc[key] = param.description[key]
            except KeyError as _:
                message = "No description found for '{}'"
                warn(message.format(key))

    # Combine Param objects
    param = Param({**param, **param_kwargs})

    # Save to param.yaml in module directory
    param.dump()


def configurate():
    '''
    Copy default_param to param
    '''

    # Get librairy dir
    dir_path = get_module_path(__file__)

    param = Param.load(dir_path + 'default_param.yaml')

    with open(dir_path + 'default_param.yaml', 'r') as f:
            param = f.readlines()

    try:
        with open(dir_path + 'param.yaml', 'x') as f:
            f.writelines(param)
    except FileExistsError as e:
        message = str(e) + '. Run exofile.config.reset_param() to delete the file.'
        raise FileExistsError(message)

def reset_param():
    '''
    Delete param.yaml (located in the librairy dir)
    '''

    # Get librairy dir
    dir_path = get_module_path(__file__)

    # Remove the file
    remove(dir_path + 'param.yaml')