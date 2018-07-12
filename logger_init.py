#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
import logging
from logging.handlers import RotatingFileHandler
import sys
from os.path import abspath, join

FORMAT_FILE = "[{levelname:_^7.5}] - {asctime} -" + \
              " {name:^24.20} {lineno:6d} - {message}"
FORMAT_CONSOLE = "{message}"

fmter_file = logging.Formatter(FORMAT_FILE, style="{")
fmter_console = logging.Formatter(FORMAT_CONSOLE, style="{")

filehandler = RotatingFileHandler(join(abspath("logs"), "app_log.txt"),
                                  mode="a",
                                  maxBytes=1E32,
                                  backupCount=1000)
filehandler.setFormatter(fmter_file)
filehandler.setLevel(logging.DEBUG)

consolehandler = logging.StreamHandler(sys.stdout)
consolehandler.setFormatter(fmter_console)
consolehandler.setLevel(logging.INFO)

logging.basicConfig(level=logging.DEBUG,
                    handlers=[filehandler, consolehandler])

logging.info("Logging facility initialized.")
