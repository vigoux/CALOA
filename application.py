#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (C) 2018  Thomas Vigouroux

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from threading import RLock, Event

import traceback

from queue import Queue

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as tMsg
import tkinter.filedialog as tkFileDialog

import BNC
import logging
import logger_init
import time
import spectro

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cmx
from numpy import linspace

from pickle import Pickler, Unpickler

import os

# Config file to manage functionnalities
import config

# Used to send automatic bug reports
import requests
import json
import platform

logger = logging.getLogger(__name__)
experiment_logger = logging.getLogger(__name__+".experiment")

main_lock = RLock()

# %% Scope_Display Object, useful to manage scope display


class Scope_Display(tk.Frame, Queue):

    SCOPE_UPDATE_SEQUENCE = "<<SCOPEUPDATE>>"
    PLOT_TYPE_2D = "2D"
    PLOT_TYPE_TIME = "Time"

    def __init__(self, master, nameList):
        """
        Initializes self.
        Display is a queue, in wich you put the scopes what you want to draw.
        To allow multi-threading, Scope_Display uses a bind to a special event.

        Parameters:
        - master -- The master widget where self needs to be drawn.
        - nameList -- A list of 2-tuples containing as follows
        (panel name, panel type id), it is used to initialize all panels
        """

        #

        Queue.__init__(self)

        # Setting up the GUI

        tk.Frame.__init__(self, master=master)

        # The global NoteBook wich contains all scopes
        self.globalPwnd = ttk.Notebook(master=self)

        # Create the panelsDict used to store all useful objects to display
        # spectrum. panelsDict is a dict containing as keys the names of all
        # panels, and as values a 3-tuple containing :
        #  (panel axes, panel canvas, panel type id)
        self.panelsDict = dict([])

        for name in nameList:
            figure = Figure(figsize=(6, 5.5), dpi=100)  # The scope figure

            plot = figure.add_subplot(111)

            frame = tk.Frame(self.globalPwnd)

            canvas = FigureCanvasTkAgg(figure,
                                       master=frame)  # Get the tkinter canvas

            # Add the canvas to global NoteBook
            self.globalPwnd.add(frame, text=name[0])

            canvas.get_tk_widget().pack(fill=tk.BOTH)  # Pack the canvas

            self.panelsDict[name[0]] = plot, canvas, name[1]
        self.bind(self.SCOPE_UPDATE_SEQUENCE, self.reactUpdate)

        self.globalPwnd.pack(fill=tk.BOTH)  # Pack the Global Notebook

    def putSpectrasAndUpdate(self, frame_id, spectras):
        """
        Use this method to update a live screen.
        This will send an instruction to the queue.
        Spectra must be :
        - if display is a 2D live display, the list of spectrum to display
          as given by Spectrum_Storage[folder_id, subfolder_id, :] :
            [(channel_id, spectrum), ...]
        - if display is a 3D live display, the list of spectra to display
          as given by Spectrum_Storage[folder_id, :, channel_id] :
            [(subfolder_id, spectrum), ...]
        """
        self.put((frame_id, spectras))
        self.event_generate(self.SCOPE_UPDATE_SEQUENCE)

    def reactUpdate(self, event):
        """
        This method is called whenever a new instruction is received.
        """

        try:

            tp_instruction = self.get()

        except Exception:
            pass
        else:

            # Extract useful objects
            plotting_area = self.panelsDict[tp_instruction[0]][0]
            canvas = self.panelsDict[tp_instruction[0]][1]
            plot_type = self.panelsDict[tp_instruction[0]][2]

            plotting_area.clear()
            plotting_area.grid()

            if plot_type == self.PLOT_TYPE_2D:

                # In this case we should have a list of spectrum as given
                # by Spectrum_Storage[folder_id, subfolder_id, :]:
                # {channel_id: spectrum, ...}

                for channel_name, spectrum in tp_instruction[1].items():
                    plotting_area.plot(
                        spectrum.lambdas, spectrum.values,
                        label=channel_name)
                plotting_area.legend()

            elif self.PLOT_TYPE_TIME:

                # In this case we should have a list of spectra as given by
                # Spectrum_Storage[folder_id, :, channel_id] :
                # {subfolder_id: spectrum, ...}

                # To find some other colormap ideas :
                # https://matplotlib.org/examples/color/colormaps_reference.html

                # This part of the work is based on an answers to a
                # StackOverflow question :
                # Using colomaps to set color of line in matplotlib

                values = list(tp_instruction[1].keys())

                # colormap = plt.get_cmap("plasma")
                colormap = plt.get_cmap("YlOrRd")

                cNorm = colors.Normalize(vmin=values[0], vmax=values[-1])

                scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=colormap)

                for val in values:
                    spectrum = tp_instruction[1][val]
                    colorVal = scalarMap.to_rgba(val)
                    plotting_area.plot(
                        spectrum.lambdas, spectrum.values,
                        color=colorVal
                        )
            canvas.draw()

# %% Application Object, true application is happening here


class Application(tk.Frame):

    # Useful constants

    SEPARATOR_ID = "[SEPARATOR]"

    DISPLAY_KEYS = (
        "T_TOT",
        "INT_T",
        "N_C",
        "N_D",
        SEPARATOR_ID,
        "STARTLAM",
        "ENDLAM",
        "NRPTS",
        SEPARATOR_ID
        )

    (T_TOT_ID, INT_T_ID, N_C_ID, N_D_ID, _1,
        STARTLAM_ID, ENDLAM_ID, NRPTS_ID, _2) = DISPLAY_KEYS

    DISPLAY_TEXTS = {
        T_TOT_ID: "Total experiment time (in ms)",
        INT_T_ID: "Integration time (in ms)",
        N_C_ID: "Averaging number (integer)",
        N_D_ID: "Delay Number (integer)",
        STARTLAM_ID: "Starting lambda (in nm)",
        ENDLAM_ID: "Ending lambda (in nm)",
        NRPTS_ID: "Points number (integer)"
        }

    PARAMETERS_KEYS = (
        "ROUTINE_DISPLAY_PERIOD",
        "ROUTINE_INT_TIME",
        "ROUTINE_INTERPOLATION",
        "ROUTINE_STARTING_LAMBDA",
        "ROUTINE_ENDING_LAMBDA",
        "ROUTINE_NR_POINTS"
        )

    (ROUT_PERIOD, ROUT_INT_TIME, ROUT_INTERP_INT,
        ROUT_START_LAM, ROUT_END_LAM, ROUT_NR_POINTS) = PARAMETERS_KEYS

    PARAMETERS_TEXTS = {
        ROUT_PERIOD: "Display's period (# of ms)",
        ROUT_INT_TIME: "Display's integration time (in ms)",
        ROUT_INTERP_INT: "Display's smoothing intensity (in %)",
        ROUT_START_LAM: "Display's starting wavelength (in nm)",
        ROUT_END_LAM: "Display's ending wavelength (in nm)",
        ROUT_NR_POINTS: "Display's # of points (integer)"
        }

    BACKUP_CONFIG_FILE_NAME = "temporary_cfg.ctcf"

    def __init__(self, master=None):
        """
        Inits self.

        Parameters:
        - master -- Master widget to draw application in.
        """

        super().__init__(master)

        self.config_dict = dict([])
        self.experiment_on = False

        # Initialize all data structures
        self.spectra_storage = spectro.Spectrum_Storage()
        self._bnc = BNC.BNC(P_dispUpdate=False)
        self.avh = spectro.AvaSpec_Handler()

        # Create screen and menu
        self.createScreen()
        self.initMenu()

        # Set focus and pack
        self.focus_set()
        self.pack()

        try:  # to open preceding config file
            with open(self.BACKUP_CONFIG_FILE_NAME, "rb") as file:
                self._rawLoadConfig(file)
        except Exception as e:  # File not found
            logger.info("Impossible to open config file.", exc_info=e)

    def createScreen(self):
        """Creates and draw main app screen."""

        self.mainOpt = ttk.Notebook(self)  # Main display

        # Normal mode
        wind2 = self.createWidgetsSimple(self.mainOpt)
        self.mainOpt.add(wind2, text="Normal")

        # Advanced mode
        wind = self.createWidgetsAdvanced(self.mainOpt)
        self.mainOpt.add(wind, text="Advanced")

        self.mainOpt.pack()

    def initMenu(self):
        """Inits and draw menubar."""

        menubar = tk.Menu(self.master)

        filemenu = tk.Menu(menubar, tearoff=0)  # Create the file menu scroll
        filemenu.add_command(label="Open config", command=self.loadConfig)
        filemenu.add_command(label="Save current config",
                             command=self.saveConfig)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.goodbye_app)
        menubar.add_cascade(label="File", menu=filemenu)  # Add it to menubar

        # Create the general spectra management menu
        spectra_menu = tk.Menu(menubar, tearoff=0)

        # Create the White menu
        white_menu = tk.Menu(spectra_menu, tearoff=0)

        # Technique using lambda functions to pass arguments to functions is
        # advised by answer to StackOverflow question :
        # https://stackoverflow.com/questions/6920302/how-to-pass-arguments-to-a-button-command-in-tkinter
        white_menu.add_command(
            label="Save White",
            command=lambda: self.saveSpectra("Basic", "White")
        )
        white_menu.add_command(
            label="Load White",
            command=lambda: self.loadSpectra("Basic", "White")
        )
        spectra_menu.add_cascade(
            label="White",
            menu=white_menu
        )

        black_menu = tk.Menu(spectra_menu, tearoff=0)
        black_menu.add_command(
            label="Save Black",
            command=lambda: self.saveSpectra("Basic", "Black")
        )
        black_menu.add_command(
            label="Load Black",
            command=lambda: self.loadSpectra("Basic", "Black")
        )
        spectra_menu.add_cascade(
            label="Black",
            menu=black_menu
        )

        menubar.add_cascade(
            label="Spectra",
            menu=spectra_menu
        )

        menubar.add_command(label="Preferences...",
                            command=self.display_preference_menu)
        self.master.config(menu=menubar)

    def display_preference_menu(self):
        """Display the preference pane, for better parameter handling."""

        config_pane = tk.Toplevel()
        config_pane.title("Preferences")
        for i, key in enumerate(self.PARAMETERS_KEYS):
            tk.Label(
                config_pane,
                text=self.PARAMETERS_TEXTS[key]
                ).grid(row=i, column=0, sticky=tk.W)
            tk.Entry(config_pane,
                     textvariable=self.config_dict[key]).grid(row=i, column=1)

    def updateScreen(self):
        """Easier way to update the screen."""

        self.mainOpt.update()

    def get_selected_absorbance(self, scopes):
        """
        This method returns the absorbance spectra using the channel
        selected in the GUI.

        Parameters :
            - scopes -- this is the spectra dict as given by
                Spectrum_Storage[folder_id, subfolder_id, :]
        """
        # As defined in createWidgetsSimple, referenceChannel is a textvariable
        # containing an int corresponding to an AvsHandle.
        # In AvaSpec_Handler.devList, keys are AvsHandles and items are
        # (m_aUserFriendlyId, Callbackfunc)
        # In Spectrum_Storage, spectra are indexed using m_aUserFriendlyId
        # thus the next line is used to get m_aUserFriendlyId of the choosen
        # channel as reference.
        chosen = self.avh.devList[int(self.referenceChannel.get())][0]

        ref_spectrum = scopes[chosen]  # This is the reference spectrum

        # We now generate absorbance spectra and format them in the correct way
        # as acceptable by Spectrum_Storage.putSpectra()
        # Naming convention for absorbance spectrum is as follows :
        #   "ABSORBANCE-{channel_id}"

        abs_spectras = dict([])

        for key in scopes:

            # This is not useful to compute the absorbanceSpectrum of the
            # referenceChannel, thus we don't do it.

            if key != chosen:
                abs_spectras["ABSORBANCE-{}".format(key)] = \
                    spectro.Spectrum.absorbanceSpectrum(
                        ref_spectrum, scopes[key])

        return abs_spectras

    def routine_data_sender(self):
        """
        This routine is meant to send data to scope display.
        This is a live-display-like feature.
        """

        if not self.pause_live_display.wait(0):

            self.avh.acquire()

            try:
                self.avh.prepareAll(
                    intTime=float(self.config_dict[self.ROUT_INT_TIME].get())
                )
            except Exception:
                self.avh.prepareAll()

            scopes = self.avh.startAllAndGetScopes()

            # list.copy() is realy important because of the
            # eventual further modification of the list.
            # Send raw spectras.
            self.liveDisplay.putSpectrasAndUpdate("Scopes", scopes.copy())
            self.avh.release()
            try:
                self.after(
                    int(self.config_dict[self.ROUT_PERIOD].get()),
                    self.routine_data_sender
                )
            except Exception:
                self.after(250, self.routine_data_sender)
        elif not self.stop_live_display.wait(0):
            self.after(1000, self.routine_data_sender)

    # Save and load

    def loadConfig(self):
        """Loads a config file selected by user."""

        with tkFileDialog.askopenfile(mode="rb",
                                      filetypes=[("CALOA Config file",
                                                  "*.cbc")]) as saveFile:
            self._rawLoadConfig(saveFile)

    def _rawLoadConfig(self, file):
        """Loads the file at file path given as parameter file."""

        unpick = Unpickler(file)
        tp_config_tup = unpick.load()
        try:
            self._bnc.load_from_pick(tp_config_tup[0])
            for key in tp_config_tup[1].keys():
                self.config_dict[key].set(tp_config_tup[1][key])
        except Exception as e:
            logger.critical("Error while loading file :", exc_info=e)
        finally:
            self.updateScreen()

    def get_saving_dict(self):
        """Gather all configuration information that needs to be saved"""

        tp_config_dict = dict([])
        for key in self.config_dict.keys():
            tp_config_dict[key] = self.config_dict[key].get()
        return self._bnc.save_to_pickle(), tp_config_dict

    def _rawSaveConfig(self, file):
        """Saves all config at file given as parameter file."""

        pick = Pickler(file)
        total_list = self.get_saving_dict()
        pick.dump(total_list)

    def saveConfig(self):
        """Saves config in a user selected location."""

        saveFileName = tkFileDialog.asksaveasfilename(
            defaultextension=".cbc",
            filetypes=[("CALOA Config file",
                        "*.cbc")])
        with open(saveFileName, "wb") as saveFile:
            self._rawSaveConfig(saveFile)

    def saveSpectra(self, folder_id, subfolder_id):
        """
        Saves spectra located at folder_id, subfolder_id
        """

        logger.debug("Starting to save {}-{}".format(folder_id, subfolder_id))

        save_path = tkFileDialog.asksaveasfilename(
            title="Saving spectra.",
            defaultextension=".css")

        if save_path is not None:
            with open(save_path, "wb") as save_file:
                pick = Pickler(save_file)
                pick.dump(
                    self.spectra_storage.  # NOT END OF LINE
                    _hidden_directory[folder_id][subfolder_id]
                )

        logger.debug("Saved {}-{}".format(folder_id, subfolder_id))

    def loadSpectra(self, folder_id, subfolder_id):
        """
        Loads spectra.
        """

        logger.debug("Starting to load {}-{}".format(folder_id, subfolder_id))

        load_path = tkFileDialog.askopenfile(
            title="Saving spectra.",
            defaultextension=".css")

        if load_path is not None:
            with open(load_path, "rb") as load_file:
                unpick = Unpickler(load_file)
                self.spectra_storage.\
                    _hidden_directory[folder_id][subfolder_id] = unpick.load()

        logger.debug("Loaded {}-{}".format(folder_id, subfolder_id))

    # TODO: Enhance advanced frame aspect id:32
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/43

    def createWidgetsAdvanced(self, master):
        """
        Creates the advanced pane.
        """

        wind = tk.PanedWindow(master, orient=tk.HORIZONTAL)

        self.Lframe = tk.Frame(wind)
        wind.add(self.Lframe)
        bnc_frame = self._bnc.drawComplete(self.Lframe)
        bnc_frame.pack(side=tk.LEFT)

        sep1 = ttk.Separator(wind, orient=tk.VERTICAL)
        wind.add(sep1)

        self.Mframe = tk.Frame(wind)
        wind.add(self.Mframe)
        tk.Button(
            self.Mframe, command=self._bnc.reset,
            text="Reset BNC"
        ).pack(side=tk.RIGHT)

        wind.pack()

        return wind

    def createWidgetsSimple(self, master):
        """
        Draw the simple pane.
        """
        frame = tk.Frame(master)

        #  Drawing BNC Frame

        bnc_fen = self._bnc.drawSimple(frame)
        bnc_fen.pack(side=tk.LEFT)

        #  Drawing Button Frame

        button_fen = tk.LabelFrame(frame, text="Experiment parameters")

        tk.Button(button_fen, text="Set Black",
                  command=self.set_black).grid(row=0, columnspan=2,
                                               sticky=tk.E+tk.W)

        tk.Button(button_fen, text="Set White",
                  command=self.set_white).grid(row=1, columnspan=2,
                                               sticky=tk.E+tk.W)

        tk.Button(button_fen, text="Launch experiment",
                  command=self.experiment).grid(row=2, columnspan=2,
                                                sticky=tk.E+tk.W)

        # Here we make all interactible for experiment configuration.
        sub_fen = tk.Frame(button_fen)
        for i, key in enumerate(self.DISPLAY_KEYS):
            if key == self.SEPARATOR_ID:
                ttk.Separator(sub_fen,
                              orient=tk.HORIZONTAL).grid(row=i,
                                                         columnspan=2,
                                                         sticky=tk.E+tk.W,
                                                         pady=5)
            elif key in self.DISPLAY_TEXTS:
                tk.Label(sub_fen,
                         text=self.DISPLAY_TEXTS[key]).grid(row=i, column=0,
                                                            sticky=tk.W)
                self.config_dict[key] = tk.StringVar()
                tk.Entry(sub_fen,
                         textvariable=self.config_dict[key]).\
                    grid(row=i, column=1)
        sub_fen.grid(row=3, rowspan=len(self.DISPLAY_KEYS), columnspan=2)

        for key in self.PARAMETERS_KEYS:
            self.config_dict[key] = tk.StringVar()

        tk.Label(button_fen,
                 text="Reference channel").\
            grid(row=90, column=0, rowspan=self.avh._nr_spec_connected)

        self.referenceChannel = tk.StringVar()
        for i, avsHandle in enumerate(self.avh.devList):
            tk.Radiobutton(button_fen,
                           text=self.avh.devList[avsHandle][0],
                           variable=self.referenceChannel,
                           value=avsHandle).grid(row=90+i, column=1)

        ttk.Separator(button_fen,
                      orient=tk.HORIZONTAL).grid(columnspan=2,
                                                 sticky=tk.E+tk.W,
                                                 pady=5)

        self.processing_text = tk.Label(
            button_fen, text="No running experiment...")

        self.processing_text.grid(columnspan=2)
        tk.Button(
            button_fen, text="Abort current observation.",
            command=self.stop_experiment
            ).grid(columnspan=2, sticky=tk.E+tk.W)
        button_fen.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Drawing Scope Frame

        scope_fen = tk.Frame(frame)

        self.pause_live_display = Event()
        self.stop_live_display = Event()
        self.liveDisplay = Scope_Display(
            scope_fen,
            [
                ("Scopes", Scope_Display.PLOT_TYPE_2D),
                ("Black", Scope_Display.PLOT_TYPE_2D),
                ("White", Scope_Display.PLOT_TYPE_2D),
                ("Experiment raw", Scope_Display.PLOT_TYPE_2D),
                ("Experiment abs.", Scope_Display.PLOT_TYPE_TIME)
            ]
        )
        self.liveDisplay.pack(fill=tk.BOTH)
        self.after(0, self.routine_data_sender)
        scope_fen.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.BOTH)

        return frame

    def stop_experiment(self):

        self.experiment_on = False

    # IDEA: N/B introduce possibility to im/export ascii from/to disk id:35
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/46

    # IDEA: In the end, write N/B as default, to be red at next start. id:34
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/45

    def set_black(self):
        self.processing_text["text"] = "Preparing black-setting..."
        self.pause_live_display.set()
        self.avh.acquire()
        experiment_logger.info("Starting to set black")
        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.INT_T_ID].get())
        p_N_c = int(self.config_dict[self.N_C_ID].get())

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        self.avh.prepareAll(p_T, True, p_N_c)
        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()
        self._bnc.run()
        self.avh.startAll(p_N_c)
        n_black = 0

        while n_black < p_N_c:
            self.processing_text["text"] = "Processing black :\n"\
                + "\tAverage : {}/{}".format(n_black, p_N_c)
            self.update()
            self._bnc.sendtrig()
            self.after(int(p_T_tot))
            self.update()

            n_black += 1
            experiment_logger.debug("Done black {}/{}".format(n_black,
                                                              p_N_c))
        self.avh.waitAll()
        self._bnc.stop()
        self.spectra_storage.putBlack(self.avh.getScopes())
        experiment_logger.info("Black set.")
        self.liveDisplay.putSpectrasAndUpdate(
            "Black", self.spectra_storage.latest_black)
        self.avh.stopAll()
        self.avh.release()
        self.pause_live_display.clear()
        self.processing_text["text"] = "No running experiment..."

    def set_white(self):
        self.processing_text["text"] = "Preparing white-setting..."
        self.pause_live_display.set()
        self.avh.acquire()
        experiment_logger.info("Starting to set white")
        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.INT_T_ID].get())
        p_N_c = int(self.config_dict[self.N_C_ID].get())

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        self.avh.prepareAll(p_T, True, p_N_c)
        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()

        self._bnc.run()
        self.avh.startAll(p_N_c)
        n_white = 0

        while n_white < p_N_c:

            self.processing_text["text"] = "Processing white :\n"\
                + "\tAverage : {}/{}".format(n_white, p_N_c)
            self.update()

            self._bnc.sendtrig()
            self.after(int(p_T_tot))
            self.update()

            n_white += 1
            experiment_logger.debug("Done white {}/{}".format(n_white,
                                                              p_N_c))
        self.avh.waitAll()
        self._bnc.stop()
        self.spectra_storage.putWhite(self.avh.getScopes())
        experiment_logger.info("White set.")
        self.liveDisplay.putSpectrasAndUpdate(
            "White", self.spectra_storage.latest_white)
        self.avh.stopAll()
        self.avh.release()
        self.pause_live_display.clear()
        self.processing_text["text"] = "No running experiment..."

    def get_timestamp(self):
        return \
            "{time.tm_mday}_{time.tm_mon}_{time.tm_hour}_{time.tm_min}".\
            format(time=time.localtime())

    def experiment(self):
        self.processing_text["text"] = "Preparing experiment..."
        raw_timestamp = self.spectra_storage.createStorageUnit(end="RAW")
        abs_timestamp = self.spectra_storage.createStorageUnit(end="ABS")
        experiment_logger.info("Starting experiment.")
        self.experiment_on = True
        self.pause_live_display.set()
        self.avh.acquire()
        abort = False

        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.INT_T_ID].get())
        p_N_c = int(self.config_dict[self.N_C_ID].get())
        p_N_d = int(self.config_dict[self.N_D_ID].get())

        n_d = 1

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        for pulse in self._bnc:
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()
            if pulse[BNC.STATE] == "1":
                pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
                pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
                total_time_used = p_N_d*float(
                    pulse.experimentTuple[BNC.dPHASE].get())
                if total_time_used >= p_T:
                    raise AssertionError(
                        "Experiment time to short. Pulse nr {}".
                        format(pulse.number)
                        + " uses {}ms but {}ms were allocated.".format(
                            total_time_used, p_T_tot))

        self.avh.prepareAll(p_T, True, p_N_c)

        if not self.spectra_storage.blackIsSet():
            experiment_logger.warning("Black not set, aborting.")
            abort = True
            self.experiment_on = False

        if not self.spectra_storage.whiteIsSet():
            experiment_logger.warning("White not set, aborting.")
            self.experiment_on = False
            abort = True

        if self.referenceChannel.get() != "":
            correction_spectrum = self.get_selected_absorbance(
                self.spectra_storage.latest_white)
        else:
            experiment_logger.warning(
                "No reference channel selected, aborting.")
            self.experiment_on = False
            abort = True

        experiment_logger.info("Starting observation.")
        if not abort:

            while n_d <= p_N_d and self.experiment_on:

                n_c = 1
                self._bnc.run()
                self.avh.startAll(p_N_c)

                while n_c <= p_N_c and self.experiment_on:

                    self.processing_text["text"] = "Processing experiment :\n"\
                        + "\tAverage : {}/{}\n".format(n_c, p_N_c)\
                        + "\tDelay : {}/{}".format(n_d, p_N_d)

                    self._bnc.sendtrig()
                    self.after(int(p_T_tot))
                    self.update()

                    n_c += 1

                    experiment_logger.\
                        debug("Done experiment {}/{}, {}/{}".format(n_c,
                                                                    p_N_c,
                                                                    n_d,
                                                                    p_N_d))
                self.avh.waitAll()
                self._bnc.stop()
                n_d += 1

                for pulse in self._bnc:
                        if pulse[BNC.STATE] == "1":
                            pulse[BNC.DELAY] = \
                                float(pulse.experimentTuple[BNC.DELAY].get()) \
                                + n_d * \
                                float(pulse.experimentTuple[BNC.dPHASE].get())
                tp_scopes = self.avh.getScopes()
                self.avh.stopAll()
                self.spectra_storage.putSpectra(raw_timestamp, n_d, tp_scopes)
                self.liveDisplay.putSpectrasAndUpdate(
                    "Experiment raw",
                    self.spectra_storage[raw_timestamp, n_d, :]
                )

                black_corrected_scopes = dict([])

                for id, spectrum in tp_scopes.items():
                    black_corrected_scopes[id] = \
                        spectrum - self.spectra_storage.latest_black[id]

                tp_absorbance = self.get_selected_absorbance(
                    black_corrected_scopes
                    )

                first_absorbance_spectrum_name = list(tp_absorbance.keys())[0]

                corrected_absorbance = dict([])

                for key in tp_absorbance:
                    corrected_absorbance[key] = \
                        tp_absorbance[key]-correction_spectrum[key]

                self.spectra_storage.putSpectra(
                    abs_timestamp, n_d, tp_absorbance
                )

                self.liveDisplay.putSpectrasAndUpdate(
                    "Experiment abs.",
                    self.spectra_storage[
                        abs_timestamp, :, first_absorbance_spectrum_name
                    ]
                )

            if not self.experiment_on:
                experiment_logger.info("Experiment stopped.")
                tMsg.showinfo("Experiment stopped",
                              "n_c = {} , n_d = {}".format(n_c, n_d))
            else:
                experiment_logger.info("Experiment finished.")

        else:
            experiment_logger.warning("Experiment aborted.")
            abort = True
            self.experiment_on = False
        self.treatSpectras(raw_timestamp)
        self.avh.release()
        self.pause_live_display.clear()
        self.processing_text["text"] = "No running experiment..."

    def treatSpectras(self, folder_id):
        """
        This method is used to export spectra contained in folder_id.
        This will proceed by getting all spectra corresponding to each channel
        contained in folder_id and gathering all data using
        Spectrum_Storage[folder_id, :, channel_id]
        Saving process will create 3 folders containing a file for each
        spectrometer containing : lambdas, black, ref, spectra, ...
        """

        def format_data(filepath, datas):
            """
            Parameters :
                - filepath -- filepath to file where datas need to be saved
                - datas -- data list organized as follows :
                    [lambdas, black, white, spectrum1, spectrum2, ...]
            """
            begin = " "
            for i, spect_tup in enumerate(datas):
                if i == 0:
                    begin_format_str = "LAMBDA"
                elif i == 1:
                    begin_format_str = "BLACK"
                elif i == 2:
                    begin_format_str = "REF"
                else:
                    begin_format_str = "SP{}"
                begin += "{: ^16s}".format(begin_format_str.format(i-2))
            format_str = "    "\
                + "    ".join(["{:=+012.5F}" for spect in datas])
            with open(filepath, "w") as file:
                file.write(begin+"\n")
                for tup in zip(*datas):
                    file.write(format_str.format(*tup)+"\n")
                file.close()
        timeStamp = \
            "{time.tm_mday}_{time.tm_mon}_{time.tm_hour}_{time.tm_min}".\
            format(time=time.localtime())

        dir_path = tkFileDialog.\
            askdirectory(title="Where do you want to save spectra ?")

        if dir_path is None:
            experiment_logger.\
                critical("No Dir Path gave, impossible to save spectra.")
            return None

        save_dir = dir_path + os.sep + "saves{}".format(timeStamp)
        os.mkdir(save_dir)

        raw_path = save_dir + os.sep + "raw"
        os.mkdir(raw_path)

        interp_path = save_dir + os.sep + "interpolated"
        os.mkdir(interp_path)

        cosmetic_path = save_dir + os.sep + "cosmetic"
        os.mkdir(cosmetic_path)

        channel_ids = [tup[0] for tup in self.avh.devList.values()]

        for id in channel_ids:

            # Quick reminder : Spectrum_Storage[folder_i, :, id] returns
            # a dict of the form :
            #   {subfolder_id: Spectrum, ...}

            to_save = self.spectra_storage[folder_id, :, id]
            interp_lam_range = list(linspace(
                float(self.config_dict[self.STARTLAM_ID].get()),
                float(self.config_dict[self.ENDLAM_ID].get()),
                int(self.config_dict[self.NRPTS_ID].get())))

            format_data(
                raw_path + os.sep + "raw{}_chan{}.txt".format(timeStamp, id),
                [
                    self.spectra_storage.latest_black[id].lambdas,  # LAMBDAS
                    self.spectra_storage.latest_black[id].values,  # BLACK
                    self.spectra_storage.latest_white[id].values  # WHITE
                ] + list(to_save.values())
            )

            # Saving Interpolated datas

            interpolated = [interp_lam_range]
            for _, spectrum in to_save:
                interpolated.append(spectrum.getInterpolated(
                                    startingLamb=interp_lam_range[0],
                                    endingLamb=interp_lam_range[-1],
                                    nrPoints=len(interp_lam_range)).values)
            format_data(interp_path + os.sep
                        + "interp{}_chan{}.txt".format(timeStamp, id),
                        interpolated)

            # Saving Cosmetic datas

            cosmetic = [interp_lam_range]
            for _, spectrum in to_save:
                cosmetic.append(spectrum.getInterpolated(
                                startingLamb=interp_lam_range[0],
                                endingLamb=interp_lam_range[-1],
                                nrPoints=len(interp_lam_range),
                                smoothing=True).values)
            format_data(cosmetic_path + os.sep
                        + "cosm{}_chan{}.txt".format(timeStamp, id), cosmetic)

        config_dict = self.get_saving_dict()

        # Here we write all informations about current configuration

        with open(save_dir + os.sep + "config.txt", "w") as file:
            file.write("BNC parameters :\n")
            for i, pulse_dict in enumerate(config_dict[0]):  # bnc
                file.write("\tPulse {} :\n".format(i+1))
                for key, value in pulse_dict.items():
                    file.write("\t\t{} : {}\n".format(key, value))
            for key in self.config_dict.keys():
                if key in self.DISPLAY_KEYS or key in self.PARAMETERS_KEYS:
                    file.write("{} : {}".format(key,
                                                self.config_dict[key].get()))
            file.close()

    def goodbye_app(self):
        with open(self.BACKUP_CONFIG_FILE_NAME, "wb") as saveFile:
            self._rawSaveConfig(saveFile)
        self._bnc._bnc_handler._con.close()
        self.pause_live_display.set()
        self.stop_live_display.set()
        self.experiment_on = True
        self.avh._done()
        self.quit()


def report_callback_exception(self, *args):
    err = traceback.format_exception(*args)
    tMsg.showerror("Error", args[1])  # This is exception message
    logger.critical("Error :", exc_info=err)
    if config.AUTO_BUG_REPORT_ENABLED:
        url = "https://api.github.com/repos/Mambu38/CALOA/issues"
        err_str = platform.platform()+"\n"
        err_str += \
            platform.python_implementation() + "-" + platform.python_version()\
            + "\n"
        for line in err:
            err_str += line
        payload = {
            "title": "AUTO BUG REPORT: {}".format(args[1]),
            "body": "```\n" + err_str + "```",
            "labels": ["bug", ]
        }
        r = requests.post(
            url,
            data=json.dumps(payload),
            auth=("caloareportsender@gmail.com", "!T&XfDOLONZ3W@5lbC*k")
        )
        logger.info("Bug report sent, received {}".format(r.headers["Status"]))


def root_goodbye():
    global root
    global app
    app.goodbye_app()
    root.destroy()


tk.Tk.report_callback_exception = report_callback_exception

print("CALOA Copyright (C) 2018 Thomas Vigouroux")
print("This program comes with ABSOLUTELY NO WARRANTY.")
print("This is a free software, and you are welcome to redistribute it")
print("under certain conditions.")

root = tk.Tk()
root.title("CALOA")
app = Application(master=root)
root.protocol("WM_DELETE_WINDOW", root_goodbye)  # If window is closed
app.mainloop()

logger_init.filehandler.doRollover()
logging.shutdown()
