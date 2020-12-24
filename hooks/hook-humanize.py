# this needs to be copied into C:\Users\user\AppData\Local\Programs\Python\Python37\Lib\site-packages\PyInstaller\hooks\hook-humanize.py
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('humanize')