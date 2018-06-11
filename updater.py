#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module contains the auto-update processus.
Copyright (C) 2018  Thomas Vigouroux

This file is part of CALOA.

CALOA is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CALOA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CALOA.  If not, see <http://www.gnu.org/licenses/>.
"""
import logger_init

import requests
import os
from io import BytesIO
from zipfile import ZipFile
from ast import literal_eval
from re import search

update_logger = logger_init.logging.getLogger(__name__)

dont_take_unuseful = r"(logs|__pycache__|\.\w+)"

# Opening and getting current version number.
try:
    vers_file = open("VERSION_INFO", "r")
    vers_id = vers_file.readlines()[0]
except FileNotFoundError as err_file:
    update_logger.warning("VERSION_INFO file not found.", exc_info=err_file)
    vers_id = ""
except IndexError as ind_err:
    update_logger.warning("VERSION_INFO is empty.", exc_info=ind_err)
    vers_id = ""
    vers_file.close()
else:
    vers_file.close()

update_logger.debug("Current version : {}".format(vers_id))

# Getting latest release informations
try:
    latest_release_str = \
        requests.\
        get("https://api.github.com/repos/Mambu38/CALOA/releases/latest").\
        content.decode()
except Exception:
    raise RuntimeError("Unable to find a connection. Aborting update.")

dict_latest_release = \
    literal_eval(latest_release_str.
                 replace("true", "True").
                 replace("false", "False").
                 replace("null", "None"))

updated_version_nbr = dict_latest_release["tag_name"]

# Downloading and install

if updated_version_nbr > vers_id:

    update_logger.info("Software version is outdated, updating...")

    zipped = requests.get(dict_latest_release["zipball_url"])  # download zip
    update_logger.info("ZipFile downloaded.")

    unzipped = ZipFile(BytesIO(zipped.content))  # Unzip dowloaded file
    update_logger.info("ZipFile unzipped.")

    for file_name in unzipped.namelist():
        splitted_file_name = file_name.split("/")
        if not (search(dont_take_unuseful, file_name)
                or splitted_file_name[-1] == ""):  # Exclude unused files
            update_logger.debug("Updating file {}".format(file_name))

            # Open new and old files

            with unzipped.open(file_name, "r") as upd_file,\
                    open(splitted_file_name[-1], "wb") as old_file:

                for line in upd_file.readlines():
                    old_file.write(line)  # Write each new line  in old file
            update_logger.debug("{} updated.".format(file_name))

    with open("VERSION_INFO", "w") as vers_file:

        vers_file.write(updated_version_nbr)  # Update version number

    update_logger.info("Software updated to {}.".format(updated_version_nbr))
else:
    update_logger.info("Your software is up-to-date : {}.".format(vers_id))
