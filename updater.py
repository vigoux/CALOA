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

# Getting latest release informations
try:
    latest_release_str = \
        requests.\
        get("https://api.github.com/repos/Mambu38/CALOA/releases/latest").\
        decode()
except Exception:
    raise RuntimeError("Unable to find a connection. Aborting update.")

dict_latest_release = \
    literal_eval(latest_release_str.
                 replace("true", "True").replace("false", "False"))

updated_version_nbr = dict_latest_release["tag_name"]

# TODO: Finish updater, left while getting zipped update.

if updated_version_nbr > vers_id:
    zipped = requests.get(dict_latest_release["zipball_url"])
