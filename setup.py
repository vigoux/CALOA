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
from cx_Freeze import setup, Executable
import os

os.environ['TCL_LIBRARY'] = "C:\\LOCAL_TO_PYTHON\\Python35-32\\tcl\\tcl8.6"
os.environ['TK_LIBRARY'] = "C:\\LOCAL_TO_PYTHON\\Python35-32\\tcl\\tk8.6"
setup(name="CALOA",
      version="0.0",
      options={'build_exe': {'include_files': ['app_log.txt', "as5216x64.dll"],
                             "packages": ["serial",
                                          "numpy",
                                          "scipy",
                                          "tkinter"]}},
      executables=[Executable("application.py")])
