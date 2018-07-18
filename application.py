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

# Used to open caloa documentation
import webbrowser

logger = logging.getLogger(__name__)
experiment_logger = logging.getLogger(__name__+".experiment")

main_lock = RLock()

# %% Scope_Display Object, useful to manage scope display


class Scope_Display(tk.Frame, Queue):
    """
    Live scope display (right panel in normal mode)
    """

    SCOPE_UPDATE_SEQUENCE = "<<SCOPEUPDATE>>"
    PLOT_TYPE_2D = "2D"
    PLOT_TYPE_TIME = "Time"

    DEBUG_DISPLAY = "DEBUG"

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

        # If developer mode is enabled, we create the debug display
        # to allow us to display all spectra sent to the scope display
        if config.DEVELOPER_MODE_ENABLED:
                figure = Figure(figsize=(6, 5.5), dpi=100)  # The scope figure

                plot = figure.add_subplot(111)

                frame = tk.Frame(self.globalPwnd)

                # Get the tkinter canvas
                canvas = FigureCanvasTkAgg(figure,
                                           master=frame)

                # Add the canvas to global NoteBook
                self.globalPwnd.add(frame, text=self.DEBUG_DISPLAY)

                canvas.get_tk_widget().pack(fill=tk.BOTH)  # Pack the canvas

                self.panelsDict[self.DEBUG_DISPLAY] =\
                    plot, canvas, self.PLOT_TYPE_2D

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

        If developer mode is enabled and a spectrum is sent to scope display
        with a frame id not equal to self.DEBUG_DISPLAY, this spectrum will be
        sent to debug display too.
        """
        self.put((frame_id, spectras))

        # If developer mode is enabled, we push the new spectrum to
        # debug display.
        # if config.DEVELOPER_MODE_ENABLED and frame_id != self.DEBUG_DISPLAY:
        #     self.put((self.DEBUG_DISPLAY, spectras))

        self.event_generate(self.SCOPE_UPDATE_SEQUENCE)

    def reactUpdate(self, event):
        """
        This method is called whenever a new instruction is received.
        """

        try:  # This block asserts that we don't get too far in Queue

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

                colormap = plt.get_cmap(config.COLORMAP_NAME)

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
    """
    GUI and pilot of the application.
    """

    #####
    # Useful constants
    ####

    # Parameters and entries
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
        ROUT_PERIOD: "Live display's period (>500 ms)",
        ROUT_INT_TIME: "Live display's integration time (in ms)",
        ROUT_INTERP_INT:
            "Live display's smoothing window width (7 - 51 data pts)",
        ROUT_START_LAM: "Live display's starting wavelength (in nm)",
        ROUT_END_LAM: "Live display's ending wavelength (in nm)",
        ROUT_NR_POINTS: "Live display's # of points (integer)"
        }

    # Files
    BACKUP_CONFIG_FILE_NAME = "temporary_cfg.ctcf"
    BACKUP_BLACK_FILE_NAME = "backup_black.crs"
    BACKUP_WHITE_FILE_NAME = "backup_white.crs"

    # Live Display Key names
    LIVE_SCOPE = "Live scope"
    LIVE_ABS = "Live abs."
    BLACK_PANE = "Black"
    WHITE_PANE = "White"
    HARD_ABS_PANE = "Machine abs."
    EXP_SCOPE = "Exp. scope"
    EXP_ABS = "Exp. abs."

    def __init__(self, master=None):
        """
        Inits self.

        Parameters:
        - master -- Master widget to draw application in.
        """

        super().__init__(master)

        logger.debug("Initializing data structures.")
        self.spectra_storage = spectro.Spectrum_Storage()
        self.config_dict = dict([])
        self.experiment_on = False

        logger.debug("Opening connections.")
        self._bnc = BNC.BNC(P_dispUpdate=False)
        self.avh = spectro.AvaSpec_Handler()

        logger.debug("Creating screen.")
        self.createScreen()
        self.initMenu()

        # Set focus and pack
        self.focus_set()
        self.pack()

        if os.path.exists("VERSION_INFO"):
            with open("VERSION_INFO", "r") as file:
                self._version = " ".join(
                    (
                        file.read().strip("\n"),
                        "(DEV)" if config.DEVELOPER_MODE_ENABLED else ""
                    )
                )

        logger.debug("Loading config file.")
        try:  # to open preceding config file
            with open(self.BACKUP_CONFIG_FILE_NAME, "rb") as file:
                self._rawLoadConfig(file)
        except Exception as e:  # File not found
            logger.info("Impossible to open config file.", exc_info=e)

        logger.debug("Loading B/W files.")
        if os.path.exists(self.BACKUP_BLACK_FILE_NAME):
            self.loadSpectra(
                "Basic",
                "Black",
                path=self.BACKUP_BLACK_FILE_NAME,
                display_screen=self.BLACK_PANE
            )
        else:
            logger.info("No black spectra found.")

        if os.path.exists(self.BACKUP_WHITE_FILE_NAME):
            self.loadSpectra(
                "Basic",
                "White",
                path=self.BACKUP_WHITE_FILE_NAME,
                display_screen=self.WHITE_PANE
            )
        else:
            logger.info("No white spectra found.")

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
            command=lambda: self.loadSpectra(
                "Basic", "White", display_screen=self.WHITE_PANE
            )
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
            command=lambda: self.loadSpectra(
                "Basic", "Black", display_screen=self.BLACK_PANE
            )
        )
        spectra_menu.add_cascade(
            label="Black",
            menu=black_menu
        )

        spectra_menu.add_command(
            label="Save all spectra",
            command=self.saveSpectrumStorage
        )

        menubar.add_cascade(
            label="Spectra",
            menu=spectra_menu
        )

        menubar.add_command(label="Preferences...",
                            command=self.display_preference_menu)

        menubar.add_command(
            label="?",
            command=self.displayHelp
        )
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

    def displayHelp(self):
        """
        Open a popup showing a help frame.
        """
        help_frame = tk.Toplevel()
        help_frame.title("Help")

        # CALOA version
        tk.Label(
            help_frame, text="CALOA {}".format(self._version)
        ).grid(row=0)

        # Copyright
        tk.Label(
            help_frame,
            text="Copyright (C) 2018  Thomas Vigouroux"
        ).grid(row=10)

        # Open documentation button.
        # the <commmand> part of this button is the combination of two
        # StackOverflow questions :
        # https://stackoverflow.com/questions/6920302/how-to-pass-arguments-to-a-button-command-in-tkinter
        # https://stackoverflow.com/questions/4302027/how-to-open-a-url-in-python
        tk.Button(
            help_frame,
            text="Open documentation.",
            command=lambda: webbrowser.open(
                "https://github.com/Mambu38/CALOA/blob/master/README.md"
            )
        ).grid(row=20, sticky=tk.W+tk.E)

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
                    intTime=float(self.config_dict[self.ROUT_INT_TIME].get()),
                    triggerred=False,
                    nrAverages=1
                )

            except Exception:

                self.avh.prepareAll(
                    triggerred=False,
                    nrAverages=1
                )

            scopes = self.avh.startAllAndGetScopes()

            # list.copy() is realy important because of the
            # eventual further modification of the list.
            # Send raw spectras.

            interpolated_scopes = dict([])
            for key in scopes:
                interpolated_scopes[key] =\
                    scopes[key].getInterpolated(
                        startingLamb=float(self.config_dict[
                            self.ROUT_START_LAM
                        ].get()),
                        endingLamb=float(self.config_dict[
                            self.ROUT_END_LAM
                        ].get()),
                        nrPoints=int(self.config_dict[
                            self.ROUT_NR_POINTS
                        ].get()),
                        smoothing=True,
                        windowSize=int(self.config_dict[
                            self.ROUT_INTERP_INT
                        ].get()),
                        polDegree=5
                    )

            self.liveDisplay.putSpectrasAndUpdate(
                self.LIVE_SCOPE, interpolated_scopes.copy()
            )

            if self.referenceChannel.get() != "":

                # Compute absorbance (live)
                try:
                    absorbanceSpectrum = self.get_selected_absorbance(
                        scopes
                    )
                    # Display absorbance
                    to_disp_abs = dict([])
                    for key in absorbanceSpectrum:
                        to_disp_abs[key] =\
                            absorbanceSpectrum[key].getInterpolated(
                                startingLamb=float(self.config_dict[
                                    self.ROUT_START_LAM
                                ].get()),
                                endingLamb=float(self.config_dict[
                                    self.ROUT_END_LAM
                                ].get()),
                                nrPoints=int(self.config_dict[
                                    self.ROUT_NR_POINTS
                                ].get()),
                                smoothing=True,
                                windowSize=int(self.config_dict[
                                    self.ROUT_INTERP_INT
                                ].get()),
                                polDegree=5
                            )
                    self.liveDisplay.putSpectrasAndUpdate(
                        self.LIVE_ABS, to_disp_abs
                    )
                except Exception:
                    pass

            self.avh.release()

            try:
                assert(int(self.config_dict[self.ROUT_PERIOD].get()) > 10)
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

    def saveSpectra(self, folder_id, subfolder_id, path=None):
        """
        Saves spectra located at folder_id, subfolder_id

        Parameters :
        - folder_id -- A folder id contained in Spectrum_Storage
        - subfolder_id -- A subfolder_id contained in folder_id
        """

        logger.debug("Starting to save {}-{}".format(folder_id, subfolder_id))

        if path is None:
            # Ask to select a save file
            path = tkFileDialog.asksaveasfilename(
                title="Saving spectra.",
                defaultextension=".crs")

        if path is not None:  # if selected
            with open(path, "wb") as save_file:  # open it
                pick = Pickler(save_file)  # Create a Pickler
                pick.dump(
                    self.spectra_storage.  # NOT END OF LINE
                    _hidden_directory[folder_id][subfolder_id]
                )  # Save spectra

        logger.debug("Saved {}-{}".format(folder_id, subfolder_id))

    def loadSpectra(self, folder_id, subfolder_id, path=None,
                    display_screen=None):
        """
        Loads spectra.

        Parameters :
        - folder_id/subfolder_id -- see Application.saveSpectra
        - display_screen -- If set to a value (str), will display loaded
        spectra in the live display using
        Scope_Display.putSpectrasAndUpdate(display_screen, loaded data)
        """

        logger.debug("Starting to load {}-{}".format(folder_id, subfolder_id))

        if path is None:
            # Ask to select a file
            path = tkFileDialog.askopenfilename(
                title="Saving spectra.",
                defaultextension=".crs")

        tp_spectra = None

        if path is not None:  # if selected

            with open(path, "rb") as load_file:  # open it
                unpick = Unpickler(load_file)  # crete an Unpickler
                tp_spectra = unpick.load()  # Load data
                self.spectra_storage.\
                    _hidden_directory[folder_id][subfolder_id] = tp_spectra
        else:
            logger.critical("No file selected.")
            return None

        if display_screen is not None:  # if a display_screen is set
            # Display loaded spectra
            self.liveDisplay.putSpectrasAndUpdate(
                display_screen,
                tp_spectra
            )

        logger.debug("Loaded {}-{}".format(folder_id, subfolder_id))

    def saveSpectrumStorage(self):
        """
        Saves spectrum storage into a selected file.
        """

        # Select a file name
        save_path = tkFileDialog.asksaveasfilename(
            title="Save all spectra.",
            defaultextension=".csf"
        )

        if save_path != "":  # If selected
            with open(save_path, "wb") as save_file:
                pick = Pickler(save_file)  # Create a Pickler
                pick.dump(self.spectra_storage)  # Dump spectra_storage
                save_file.close()  # For safety reasons, close file
        else:  # If not selected raise a warning to the user
            raise UserWarning(
                "Invalid file path."
            )
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

        tk.Button(button_fen, text="Start experiment",
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
                self.config_dict[key] = tk.StringVar(value="0")
                tk.Entry(sub_fen,
                         textvariable=self.config_dict[key]).\
                    grid(row=i, column=1)
        sub_fen.grid(row=3, rowspan=len(self.DISPLAY_KEYS), columnspan=2)

        for key in self.PARAMETERS_KEYS:
            self.config_dict[key] = tk.StringVar(value="0")

        tk.Label(button_fen,
                 text="Reference channel").\
            grid(row=90, column=0, rowspan=self.avh._nr_spec_connected)

        self.referenceChannel = tk.StringVar(value="0")
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
                (self.LIVE_SCOPE, Scope_Display.PLOT_TYPE_2D),
                (self.LIVE_ABS, Scope_Display.PLOT_TYPE_2D),
                (self.BLACK_PANE, Scope_Display.PLOT_TYPE_2D),
                (self.WHITE_PANE, Scope_Display.PLOT_TYPE_2D),
                (self.HARD_ABS_PANE, Scope_Display.PLOT_TYPE_2D),
                (self.EXP_SCOPE, Scope_Display.PLOT_TYPE_2D),
                (self.EXP_ABS, Scope_Display.PLOT_TYPE_TIME)
            ]
        )
        self.liveDisplay.pack(fill=tk.BOTH)
        self.after(0, self.routine_data_sender)
        scope_fen.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.BOTH)

        return frame

    def stop_experiment(self):

        self.experiment_on = False

    def set_black(self):

        # Inform user that blakc is going to be set
        self.processing_text["text"] = "Preparing black-setting..."
        self.pause_live_display.set()
        experiment_logger.info("Starting to set black")

        # Gather informations about experiment parameters
        try:

            p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
            p_T = float(self.config_dict[self.INT_T_ID].get())
            p_N_c = int(self.config_dict[self.N_C_ID].get())
        except ValueError as e:

            raise UserWarning(e.args[0])  # e.args[0] is the message

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        self.avh.acquire()
        self.avh.prepareAll(p_T, True)

        for pulse in self._bnc:

            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()

        self._bnc.run()
        n_black = 0

        tp_scopes = None

        while n_black < p_N_c:

            # Inform user
            self.processing_text["text"] = "Processing experiment :\n"\
                + "\tAverage : {}/{}\n".format(n_black, p_N_c)
            self.update()

            # Get current time in milliseconds and compute estimated
            # end time for experiment
            start_time_in_ms = int(time.time()*1E3)
            estimated_end_time_in_ms = start_time_in_ms + p_T_tot

            self.avh.startAll(1)  # Start avaspec
            self._bnc.sendtrig()  # Send trigger to BNC

            # Wait appropriate time
            self.after(
                int(estimated_end_time_in_ms - int(time.time()*1E3))
            )

            n_black += 1

            self.avh.waitAll()
            spectra = self.avh.getScopes()

            # If one spectrum is saturated, we inform user of it
            # Feature asked in #81
            for key in spectra:
                if spectra[key].isSaturated():
                    self.processing_text["text"] += (
                        "\nWarning, {} is saturated.".format(key)
                    )
                    self.update()

            if config.DEVELOPER_MODE_ENABLED:

                self.liveDisplay.putSpectrasAndUpdate(
                    Scope_Display.DEBUG_DISPLAY, spectra
                )

            # if this is the first observation, tp_scopes is None
            # and thus we initialize it, else, we increment each spectrum
            if tp_scopes:
                for key in tp_scopes:
                    tp_scopes[key] += spectra[key]
            else:
                tp_scopes = spectra

        self._bnc.stop()

        for key in tp_scopes:
            tp_scopes[key] = tp_scopes[key] / p_N_c  # Correct averaging

        self.spectra_storage.putBlack(tp_scopes)  # Put in spectrum storage
        experiment_logger.info("Black set.")

        self.liveDisplay.putSpectrasAndUpdate(
            self.BLACK_PANE, self.spectra_storage.latest_black
        )
        self.avh.release()
        self.pause_live_display.clear()
        self.processing_text["text"] = "No running experiment..."

    def set_white(self):
        self.processing_text["text"] = "Preparing white-setting..."
        self.pause_live_display.set()
        experiment_logger.info("Starting to set white")
        try:
            p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
            p_T = float(self.config_dict[self.INT_T_ID].get())
            p_N_c = int(self.config_dict[self.N_C_ID].get())
        except ValueError as e:
            raise UserWarning(e.args[0])  # e.args[0] is the message

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")
        self.avh.acquire()
        self.avh.prepareAll(p_T, True)
        for pulse in self._bnc:
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()

        self._bnc.run()
        n_white = 0

        tp_scopes = None

        while n_white < p_N_c:

            # Inform user
            self.processing_text["text"] = "Processing white :\n"\
                + "\tAverage : {}/{}\n".format(n_white, p_N_c)
            self.update()

            # Get current time in milliseconds and compute estimated
            # end time for experiment
            start_time_in_ms = int(time.time()*1E3)
            estimated_end_time_in_ms = start_time_in_ms + p_T_tot

            self.avh.startAll(1)  # Start avaspec
            self._bnc.sendtrig()  # Send trigger to BNC

            # Wait appropriate time
            self.after(
                int(estimated_end_time_in_ms - int(time.time()*1E3))
            )

            n_white += 1

            self.avh.waitAll()
            spectra = self.avh.getScopes()

            # If one spectrum is saturated, we inform user of it
            # Feature asked in #81
            for key in spectra:
                if spectra[key].isSaturated():
                    self.processing_text["text"] += (
                        "\nWarning, {} is saturated.".format(key)
                    )
                    self.update()

            if config.DEVELOPER_MODE_ENABLED:

                self.liveDisplay.putSpectrasAndUpdate(
                    Scope_Display.DEBUG_DISPLAY, spectra
                )

            # if this is the first observation, tp_scopes is None
            # and thus we initialize it, else, we increment each spectrum
            if tp_scopes:
                for key in tp_scopes:
                    tp_scopes[key] += spectra[key]
            else:
                tp_scopes = spectra

        for key in tp_scopes:
            tp_scopes[key] = tp_scopes[key] / p_N_c

        self._bnc.stop()
        self.spectra_storage.putWhite(tp_scopes)
        experiment_logger.info("White set.")
        self.liveDisplay.putSpectrasAndUpdate(
            self.WHITE_PANE, self.spectra_storage.latest_white
        )
        self.avh.stopAll()
        self.avh.release()
        self.pause_live_display.clear()
        self.processing_text["text"] = "No running experiment..."

    def get_timestamp(self):
        return \
            "{time.tm_mday}_{time.tm_mon}_{time.tm_hour}_{time.tm_min}".\
            format(time=time.localtime())

    def experiment(self):

        #####
        # PREPARATION PART
        #####

        # Prepare and inform user that experiment is Running
        self.processing_text["text"] = "Preparing experiment..."
        experiment_logger.info("Preparint experiment.")

        # Prepare data-structures
        raw_timestamp = self.spectra_storage.createStorageUnit(end="RAW")
        abs_timestamp = self.spectra_storage.createStorageUnit(end="ABS")
        interp_timestamp = self.spectra_storage.createStorageUnit(end="INT")

        # Stop pending operations
        self.experiment_on = True
        self.pause_live_display.set()

        # ASSERTION PART

        # Chek if parameters are set
        try:

            p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
            p_T = float(self.config_dict[self.INT_T_ID].get())
            p_N_c = int(self.config_dict[self.N_C_ID].get())
            p_N_d = int(self.config_dict[self.N_D_ID].get())

        except ValueError as e:

            raise UserWarning(e.args[0])  # e.args[0] is the error message

        # Check if black is set
        if not self.spectra_storage.blackIsSet():

            raise UserWarning("Black not set, aborting.")

        # Check is white is set
        if not self.spectra_storage.whiteIsSet():

            raise UserWarning("White not set, aborting.")

        # Here we correct black from reference spectra.
        tp_reference = dict([])
        for key in self.spectra_storage.latest_white:
            tp_reference[key] = \
                self.spectra_storage.latest_white[key]\
                - self.spectra_storage.latest_black[key]

        # Check is a reference channel is set, if not, raise a Warning
        # else, compute the machine absorbance for further spectrum correction
        if self.referenceChannel.get() != "":
            correction_spectrum = self.get_selected_absorbance(
                tp_reference
            )
            self.liveDisplay.putSpectrasAndUpdate(
                self.HARD_ABS_PANE,
                correction_spectrum
            )
        else:

            raise UserWarning(
                "No reference channel selected, aborting."
            )
        # PREPARE BNC
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
                    raise UserWarning(
                        "Experiment time to short. Pulse nr {}".
                        format(pulse.number)
                        + " uses {}ms but {}ms were allocated.".format(
                            total_time_used, p_T_tot)
                    )

        # PREPARE AVASPEC
        self.avh.acquire()  # Acquire to prevent thread overlap on Avaspec
        self.avh.prepareAll(
            intTime=p_T,
            triggerred=True,
        )

        #####
        # OBSERVATION PART
        #####

        experiment_logger.info("Starting observation.")

        # START OF BOXCAR METHOD - DELAY LOOP

        n_d = 1

        while n_d <= p_N_d and self.experiment_on:

            self._bnc.run()
            tp_scopes = None

            # AVERAGING LOOP

            n_c = 1

            while n_c <= p_N_c and self.experiment_on:

                # Inform user
                self.processing_text["text"] = "Processing experiment :\n"\
                    + "\tAverage : {}/{}\n".format(n_c, p_N_c)\
                    + "\tDelay : {}/{}".format(n_d, p_N_d)
                self.update()
                experiment_logger.debug(
                    "Done experiment {}/{}, {}/{}".format(
                            n_c, p_N_c, n_d, p_N_d
                        )
                    )

                # Get current time in milliseconds and compute estimated
                # end time for experiment
                start_time_in_ms = int(time.time()*1E3)
                estimated_end_time_in_ms = start_time_in_ms + p_T_tot

                self.avh.startAll(1)  # Start avaspec
                self._bnc.sendtrig()  # Send trigger to BNC

                # Wait appropriate time
                self.after(
                    int(estimated_end_time_in_ms - int(time.time()*1E3))
                )

                n_c += 1

                self.avh.waitAll()
                spectra = self.avh.getScopes()

                # If one spectrum is saturated, we inform user of it
                # Feature asked in #81
                for key in spectra:
                    if spectra[key].isSaturated():
                        self.processing_text["text"] += (
                            "\nWarning, {} is saturated.".format(key)
                        )
                        self.update()

                if config.DEVELOPER_MODE_ENABLED:

                    self.liveDisplay.putSpectrasAndUpdate(
                        Scope_Display.DEBUG_DISPLAY, spectra
                    )

                # if this is the first observation, tp_scopes is None
                # and thus we initialize it, else, we increment each spectrum
                if tp_scopes:
                    for key in tp_scopes:
                        tp_scopes[key] += spectra[key]
                else:
                    tp_scopes = spectra

            # END OF AVERAGING LOOP

            self._bnc.stop()
            self.avh.stopAll()
            n_d += 1

            # Correct error caused by adding spectra
            for key in tp_scopes:
                tp_scopes[key] = tp_scopes[key] / p_N_c

            # Store Spectrum, and display it
            self.spectra_storage.putSpectra(raw_timestamp, n_d, tp_scopes)
            self.liveDisplay.putSpectrasAndUpdate(
                self.EXP_SCOPE,
                self.spectra_storage[raw_timestamp, n_d, :]
            )

            black_corrected_scopes = dict([])

            # Correct raw spectra, ie substract black
            for id, spectrum in tp_scopes.items():
                black_corrected_scopes[id] = \
                    spectrum - self.spectra_storage.latest_black[id]

            # Compute absorbance
            tp_absorbance = self.get_selected_absorbance(
                black_corrected_scopes
            )

            # Exctract the first one (actually, only the first is used)
            first_absorbance_spectrum_name = list(tp_absorbance.keys())[0]

            corrected_absorbance = dict([])
            absorbance_to_display = dict([])
            try:

                for key in tp_absorbance:
                    corrected_absorbance[key] = (
                            tp_absorbance[key]
                            - correction_spectrum[key]
                        )
                    absorbance_to_display[key] =\
                        corrected_absorbance[key].getInterpolated(
                            startingLamb=float(
                                self.config_dict[self.STARTLAM_ID].get()
                            ),
                            endingLamb=float(
                                self.config_dict[self.ENDLAM_ID].get()
                            ),
                            nrPoints=int(
                                self.config_dict[self.NRPTS_ID].get()
                            )
                        )
            except Exception:

                for key in tp_absorbance:
                    corrected_absorbance[key] = \
                        tp_absorbance[key]-correction_spectrum[key]

            # Store corrected absorbance spectra and display them
            self.spectra_storage.putSpectra(
                abs_timestamp, n_d, corrected_absorbance
            )

            self.spectra_storage.putSpectra(
                interp_timestamp, n_d, absorbance_to_display
            )

            self.liveDisplay.putSpectrasAndUpdate(
                self.EXP_ABS,
                self.spectra_storage[
                    interp_timestamp, :, first_absorbance_spectrum_name
                ]
            )

            # Delay instruments
            for pulse in self._bnc:
                    if pulse[BNC.STATE] == "1":
                        if pulse.experimentTuple[BNC.PHASE_BASE].get() == "1":
                            pulse[BNC.DELAY] = \
                                float(pulse.experimentTuple[BNC.DELAY].get()) \
                                + n_d * \
                                float(pulse.experimentTuple[BNC.dPHASE].get())
                        else:
                            pulse[BNC.DELAY] = \
                                float(pulse.experimentTuple[BNC.DELAY].get()) \
                                + (float(
                                    pulse.experimentTuple[BNC.PHASE_BASE].get()
                                ) ** n_d) * \
                                float(pulse.experimentTuple[BNC.dPHASE].get())
            del tp_scopes

        # END OF DELAY LOOP
        if not self.experiment_on:
            experiment_logger.info("Experiment stopped.")
            tMsg.showinfo("Experiment stopped",
                          "n_c = {} , n_d = {}".format(n_c, n_d))
        else:
            experiment_logger.info("Experiment finished.")

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
        timeStamp = folder_id[:-3]

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
                ] + [spectrum.values for spectrum in to_save.values()]
            )

            # Saving Interpolated datas

            interpolated = [interp_lam_range]
            for spectrum in to_save.values():
                interpolated.append(spectrum.getInterpolated(
                                    startingLamb=interp_lam_range[0],
                                    endingLamb=interp_lam_range[-1],
                                    nrPoints=len(interp_lam_range)).values)
            format_data(interp_path + os.sep
                        + "interp{}_chan{}.txt".format(timeStamp, id),
                        interpolated)

            # Saving Cosmetic datas

            cosmetic = [interp_lam_range]
            for spectrum in to_save.values():
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
                    file.write("{} : {}\n".format(
                        key,
                        self.config_dict[key].get())
                    )
            file.close()

        with open(save_dir + os.sep + "time_table.txt", "w") as file:
            heading = ""
            for pulse in self._bnc:
                heading += "{: ^25s}".format(
                    "{} : {}".format(
                        str(pulse),
                        pulse.experimentTuple[BNC.LABEL].get()
                    )
                )
            file.write(heading + "\n")
            for i in range(len(self.spectra_storage[folder_id, :, :])):
                tp_line = ""
                for pulse in self._bnc:
                    if pulse.experimentTuple[BNC.PHASE_BASE].get() == "1":
                        tp_line += "             {:=+012.5F}".format(
                            float(pulse.experimentTuple[BNC.DELAY].get())
                            + i *
                            float(pulse.experimentTuple[BNC.dPHASE].get())
                        )
                    else:
                        tp_line += "             {:=+012.5F}".format(
                            float(pulse.experimentTuple[BNC.DELAY].get())
                            + (float(
                                pulse.experimentTuple[BNC.PHASE_BASE].get()
                            ) ** i) *
                            float(pulse.experimentTuple[BNC.dPHASE].get())
                        )
                file.write(tp_line + "\n")
            file.close()

    def goodbye_app(self):
        logger.info("Exiting CALOA.")

        logger.debug("Saving config.")
        with open(self.BACKUP_CONFIG_FILE_NAME, "wb") as configFile:

            self._rawSaveConfig(configFile)

        logger.debug("Saving B/W spectra.")
        if self.spectra_storage.blackIsSet():
            self.saveSpectra(
                "Basic", "Black", path=self.BACKUP_BLACK_FILE_NAME
            )
        if self.spectra_storage.whiteIsSet():
            self.saveSpectra(
                "Basic", "White", path=self.BACKUP_WHITE_FILE_NAME
            )

        logger.debug("Stopping live display.")
        self.pause_live_display.set()
        self.stop_live_display.set()
        self.experiment_on = True

        logger.debug("Closing connections.")
        self._bnc._bnc_handler._con.close()
        self.avh._done()

        logger.debug("Exit")
        self.quit()


def report_callback_exception(self, exc, val, tb):
    err = traceback.format_exception(exc, val, tb)
    tMsg.showerror(
        "An error happened",
        val
    )  # This is exception message
    logger.critical("Error :", exc_info=err)
    if (config.AUTO_BUG_REPORT_ENABLED or config.DEVELOPER_MODE_ENABLED)\
            and not issubclass(exc, Warning):
        url = "https://api.github.com/repos/Mambu38/CALOA/issues"

        # open template
        file = open("AUTO_BUG_REPORT_TEMPLATE", "r")
        template = ''.join(file.readlines())
        file.close()

        # complete template
        formatted = template.format(
            platform_id=platform.platform(),
            pyimpl=platform.python_implementation(),
            pyvers=platform.python_version(),
            err="\n".join(err)
        )

        # Create payload to post
        payload = {
            # see traceback for further informations
            "title": "AUTO BUG REPORT: {}".format(val),
            "body": formatted,
            "labels": ["bug", ]
        }
        r = requests.post(
            url,
            data=json.dumps(payload),
            auth=(
                "caloareportsender@gmail.com",
                "!T&XfDOLONZ3W@5lbC*k"
            )
        )
        logger.info("Bug report sent, received {}".format(r.headers["Status"]))

    # Reset App, to be used further.
    app.stop_experiment()
    app.pause_live_display.clear()
    app.stop_live_display.clear()
    # app.avh.release()


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
