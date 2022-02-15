from pathlib import Path
from exofile.archive import ExoFile

PATH_TO_EXODIR = Path("/home/adb/www/")
PATH_TO_FILE = PATH_TO_EXODIR / "exofile.csv"
PATH_TO_FILE_ALT = PATH_TO_EXODIR / "exofile_alt.csv"

new = ExoFile.update()
new.write(PATH_TO_FILE, overwrite=True)
new_alt = ExoFile.update(use_composite_archive=False)
new_alt.write(PATH_TO_FILE_ALT, overwrite=True)
