#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module is used as a config file to enable/disable some functionnalities.

By modifying this file you can custom CALOA fundamental comportment.
Warning : each update will reset this file, and you will have to modified it
again.

All constants defined here shall be set either to True or to False.



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

# if AUTO_BUG_REPORT_ENABLED is set to True CALOA will send a bug report
# containing information about your platform, your python distribution and
# precise informations about the bug. Logs will not be sent for privacy reasons
# but for developers to have better informations about how bug happens
# you can send your log file to caloareportsender@gmail.com.
AUTO_BUG_REPORT_ENABLED = True

# if AUTO_UPDATE_ENABLED is set to True, CALOA will download the latest STABLE
# version. Update take some seconds but you will need an internet connection.
AUTO_UPDATE_ENABLED = True

# if DEVELOPER_MODE_ENABLED is set to True, CALOA will download the latest
# version and will enable AUTO_BUG_REPORT. Be carefull, by enabling this
# feature CALOA may be unstable, but by enabling this feature, each bug
# you collide with will give precious informations about the bug and will
# increase the patch rate.
# Furthermore, enabling this mode will give you an access to a new pane
# in scope display calle "Debug", enabling you to see all spectra sent to
# scope display.
DEVELOPER_MODE_ENABLED = True

# Enter here the name (between quotes) of the colormap you want to use
# To find some other colormap ideas :
# https://matplotlib.org/examples/color/colormaps_reference.html
COLORMAP_NAME = "Spectral"
