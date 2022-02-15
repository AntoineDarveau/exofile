from masterfile.archive import MasterFile

PATH_TO_FILE = "/home/vandal/composite.ecsv"
PATH_TO_FILE_CUSTOM = "/home/vandal/custom_composite.ecsv"

new = MasterFile.update()
new.write(PATH_TO_FILE, overwrite=True)
new_composite = MasterFile.update(use_composite_archive=False)
new_composite.write(PATH_TO_FILE_CUSTOM, overwrite=True)
