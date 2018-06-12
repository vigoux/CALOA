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
from numpy import linspace

from pickle import Pickler, Unpickler

import os

logger = logging.getLogger(__name__)
experiment_logger = logging.getLogger(__name__+".experiment")

main_lock = RLock()

# %% Scope_Display Object, useful to manage scope display


class Scope_Display(tk.Frame, Queue):

    SCOPE_UPDATE_SEQUENCE = "<<SCOPEUPDATE>>"

    def __init__(self, master, nameList, stop_event):

        # Display is a queue, in wich you put the scopes that you want to
        # draw. An embedded thread will look inside the queue to update
        # displays

        Queue.__init__(self)

        # Setting up the GUI

        tk.Frame.__init__(self, master=master)

        # The global NoteBook wich contains all scopes
        self.globalPwnd = ttk.Notebook(master=self)

        self.panelsList = []

        for name in nameList:
            figure = Figure(figsize=(6, 5.5), dpi=100)  # The scope figure

            plot = figure.add_subplot(111)  # Set-up axis and get plotting area

            frame = tk.Frame(self.globalPwnd)

            canvas = FigureCanvasTkAgg(figure,
                                       master=frame)  # Get the tkinter canvas

            # Add the canvas to global NoteBook
            self.globalPwnd.add(frame, text=name)

            canvas.get_tk_widget().pack(fill=tk.BOTH)  # Pack the canvas

            self.panelsList.append([plot, canvas])
        self.bind(self.SCOPE_UPDATE_SEQUENCE, self.reactUpdate)

        self.globalPwnd.pack(fill=tk.BOTH)  # Pack the Global Notebook

    def putSpectrasAndUpdate(self, frame_id, spectras):
        self.put((frame_id, spectras))
        self.event_generate(self.SCOPE_UPDATE_SEQUENCE)

    def reactUpdate(self, event):
        try:
            tp_instruction = self.get()
        except Exception:
            pass
        else:
            with main_lock:
                plotting_area = self.panelsList[tp_instruction[0]][0]
                canvas = self.panelsList[tp_instruction[0]][1]
                plotting_area.clear()
                plotting_area.grid()
                for spectrum in tp_instruction[1]:
                    plotting_area.plot(spectrum.lambdas, spectrum.values)
                canvas.draw()

# %% Application Object, true application is happening here


class Application(tk.Frame):

    # Useful constants

    SEPARATOR_ID = "[SEPARATOR]"

    CONFIG_KEYS = (
        "T_TOT",
        "T",
        "N_C",
        "N_D",
        SEPARATOR_ID,
        "STARTLAM",
        "ENDLAM",
        "NRPTS",
        SEPARATOR_ID
        )

    (T_TOT_ID, T_ID, N_C_ID, N_D_ID, _1,
        STARTLAM_ID, ENDLAM_ID, NRPTS_ID, _2) = CONFIG_KEYS

    DISPLAY_TEXTS = {
        T_TOT_ID: "Total experiment time (in s)",
        T_ID: "Integration time (in s)",
        N_C_ID: "Averaging number (integer)",
        N_D_ID: "Delay Number (integer)",
        STARTLAM_ID: "Starting lambda (in nm)",
        ENDLAM_ID: "Ending lambda (in nm)",
        NRPTS_ID: "Points number (integer)"
        }

    BACKUP_CONFIG_FILE_NAME = "temporary_cfg.ctcf"

    def __init__(self, master=None, P_bnc=None):

        super().__init__(master)
        self.config_dict = dict([])
        if P_bnc is None:
            P_bnc = BNC.BNC(P_dispUpdate=False)

        self.experiment_on = False
        self._bnc = P_bnc
        self.avh = spectro.AvaSpec_Handler()
        self.focus_set()
        self.pack()
        self.createScreen()
        self.initMenu()

        try:  # to open preceding config file
            with open(self.BACKUP_CONFIG_FILE_NAME, "rb") as file:
                self._rawLoadConfig(file)
        except Exception as e:  # File not found
            logger.info("Impossible to open config file.", exc_info=e)

    def createScreen(self, menu=True):
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
        filemenu.add_command(label="Quit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)  # Add it to menubar

        menubar.add_command(label="Preferences...",
                            command=self.display_preference_menu)
        self.master.config(menu=menubar)

    def display_preference_menu(self):
        """Display the preference pane, for better parameter handling."""
        config_pane = tk.Toplevel()
        config_pane.title("Preferences")

    def updateScreen(self):
        """Easier way to update the screen."""
        self.mainOpt.update()

    def routine_data_sender(self):
        if not self.pause_live_display.wait(0):
            self.avh.acquire()
            self.avh.prepareAll(intTime=10)
            scopes = self.avh.startAllAndGetScopes()

            # list.copy() is realy important because of the
            # further modification of the list.
            # Send raw spectras.
            self.liveDisplay.putSpectrasAndUpdate(0, scopes.copy())

            if self.referenceChannel.get() != "":
                key_list = list(self.avh.devList.keys())
                chosen = key_list.index(int(self.referenceChannel.get()))

                # Modification that justifies above copy
                ref_spectrum = scopes.pop(chosen)
                to_plot_list = \
                    [spectro.Spectrum.absorbanceSpectrum(ref_spectrum, spec)
                     for spec in scopes]
                self.liveDisplay.putSpectrasAndUpdate(1, to_plot_list)

            self.avh.release()
            self.after(250, self.routine_data_sender)
        elif not self.stop_live_display.wait(0):
            self.after(1000, self.routine_data_sender)
        else:
            pass

    # Save and load

    def loadConfig(self):
        with tkFileDialog.askopenfile(mode="rb",
                                      filetypes=[("CALOA Config file",
                                                  "*.cbc")]) as saveFile:
            self._rawLoadConfig(saveFile)

    def _rawLoadConfig(self, file):
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
        tp_config_dict = dict([])
        for key in self.config_dict.keys():
            tp_config_dict[key] = self.config_dict[key].get()

        return self._bnc.save_to_pickle(), tp_config_dict

    def _rawSaveConfig(self, file):
        pick = Pickler(file)
        total_list = self.get_saving_dict()
        pick.dump(total_list)

    def saveConfig(self):
        saveFileName = tkFileDialog.asksaveasfilename(
            defaultextension=".cbc",
            filetypes=[("CALOA Config file",
                        "*.cbc")])
        with open(saveFileName, "wb") as saveFile:
            self._rawSaveConfig(saveFile)

    # TODO: Enhance advanced frame aspect id:32
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/43

    def createWidgetsAdvanced(self, master):

        wind = tk.PanedWindow(master, orient=tk.HORIZONTAL)
        self.Lframe = tk.Frame(wind)
        wind.add(self.Lframe)
        bnc_frame = self._bnc.drawComplete(self.Lframe)
        bnc_frame.pack(side=tk.LEFT)
        sep1 = ttk.Separator(wind, orient=tk.VERTICAL)
        wind.add(sep1)
        self.Mframe = tk.Frame(wind)
        wind.add(self.Mframe)
        tk.Button(self.Mframe, command=self._bnc.reset,
                  text="Reset BNC").pack(side=tk.RIGHT)
        wind.pack()

        return wind

    def createWidgetsSimple(self, master):
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
        sub_fen.grid(row=3, rowspan=len(self.CONFIG_KEYS), columnspan=2)
        for i, key in enumerate(self.CONFIG_KEYS):
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
            else:
                pass

        tk.Label(button_fen,
                 text="Reference channel").\
            grid(row=90, column=0, rowspan=self.avh._nr_spec_connected)

        self.referenceChannel = tk.StringVar()
        for i, avsHandle in enumerate(self.avh.devList):
            tk.Radiobutton(button_fen,
                           text=self.avh.devList[avsHandle][0],
                           variable=self.referenceChannel,
                           value=avsHandle).grid(row=90+i, column=1)
        button_fen.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        # Drawing Scope Frame

        scope_fen = tk.Frame(frame)

        self.pause_live_display = Event()
        self.stop_live_display = Event()
        self.liveDisplay = Scope_Display(scope_fen,
                                         ["Scopes", "Absorbance",
                                          "Black", "White"],
                                         self.stop_live_display)
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
        self.pause_live_display.set()
        self.avh.acquire()
        experiment_logger.info("Starting to set black")
        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.T].get())
        p_N_c = int(self.config_dict[self.N_c].get())

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        self.avh.prepareAll(p_T*(10**3), True, p_N_c)
        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()
        self._bnc.run()
        self.avh.startAll(p_N_c)
        n_black = 0

        while n_black < p_N_c:

            self._bnc.sendtrig()
            self.after(int(p_T_tot*1E3))
            self.update()

            n_black += 1
            experiment_logger.debug("Done black {}/{}".format(n_black,
                                                              p_N_c))
        self.avh.waitAll()
        self._bnc.stop()
        self.black_spectra = self.avh.getScopes()
        experiment_logger.info("Black set.")
        self.liveDisplay.putSpectrasAndUpdate(2, self.black_spectra)
        self.avh.stopAll()
        self.avh.release()
        self.pause_live_display.clear()

    def set_white(self):
        self.avh.acquire()
        self.pause_live_display.set()
        experiment_logger.info("Starting to set white")
        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.T].get())
        p_N_c = int(self.config_dict[self.N_c].get())

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        self.avh.prepareAll(p_T*(10**3), True, p_N_c)
        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()

        self._bnc.run()
        self.avh.startAll(p_N_c)
        n_white = 0

        while n_white < p_N_c:

            self._bnc.sendtrig()
            self.after(int(p_T_tot*1E3))
            self.update()

            n_white += 1
            experiment_logger.debug("Done white {}/{}".format(n_white,
                                                              p_N_c))
        self.avh.waitAll()
        self._bnc.stop()
        self.white_spectra = self.avh.getScopes()
        experiment_logger.info("White set.")
        self.liveDisplay.putSpectrasAndUpdate(3, self.white_spectra)
        self.avh.stopAll()
        self.avh.release()
        self.pause_live_display.clear()

    def experiment(self):
        experiment_logger.info("Starting experiment")
        self.experiment_on = True
        self.pause_live_display.set()
        self.avh.acquire()
        abort = False

        p_T_tot = float(self.config_dict[self.T_TOT_ID].get())
        p_T = float(self.config_dict[self.T].get())
        p_N_c = int(self.config_dict[self.N_c].get())
        p_N_d = int(self.config_dict[self.N_d].get())

        n_d = 1

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()
            assert(p_N_d*float(pulse.experimentTuple[BNC.dPHASE].get()) < p_T)

        self.avh.prepareAll(p_T*(10**3), True, p_N_c)
        totalSpectras = []

        try:
            self.black_spectra
        except Exception:
            experiment_logger.warning("Black not set, aborting.")
            abort = True
            self.experiment_on = False

        try:
            self.white_spectra
        except Exception:
            experiment_logger.warning("White not set, aborting.")
            self.experiment_on = False
            abort = True

        experiment_logger.info("Starting observation.")
        if not abort and tMsg.\
                askokcancel("Ready", "Ready to start experiment ?"):

            pop_up = tk.Toplevel()
            pop_up.title("Processing...")

            message = tk.Message(pop_up)
            message.pack()
            tk.Button(pop_up, text="Abort", command=self.stop_experiment).\
                pack(side=tk.BOTTOM)
            pop_up["height"] = 150
            pop_up["width"] = 150

            while n_d <= p_N_d and self.experiment_on:
                n_c = 1
                self._bnc.run()
                self.avh.startAll(p_N_c)

                while n_c <= p_N_c and self.experiment_on:
                    message["text"] = \
                        "Processing\n\tAvg : {}/{}".format(n_c, p_N_c)\
                        + "\n\tDel : {}/{}".format(n_d, p_N_d)
                    self._bnc.sendtrig()
                    self.after(int(p_T_tot*1E3))
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
                    pulse[BNC.DELAY] = \
                        float(pulse.experimentTuple[BNC.DELAY].get()) + n_d * \
                        float(pulse.experimentTuple[BNC.dPHASE].get())
                tp_scopes = self.avh.getScopes()
                self.avh.stopAll()
                totalSpectras.append(tp_scopes)
                self.liveDisplay.putSpectrasAndUpdate(0, tp_scopes)

            pop_up.destroy()

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
        self.treatSpectras([self.black_spectra, self.white_spectra]
                           + totalSpectras)
        self.avh.release()
        self.pause_live_display.clear()

    def treatSpectras(self, spectras):

        def format_data(filepath, datas):
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

        nr_chans = app.avh._nr_spec_connected

        for i in range(nr_chans):
            # This item is all the lambdas
            to_save = [spectras[0][0].lambdas]
            interp_lam_range = list(linspace(float(self.startLambda.get()),
                                             float(self.stopLambda.get()),
                                             int(self.nrPoints.get())))

            # Saving Raw datas
            for spectra in spectras:
                to_save.append(spectra[i].values)  # Gathering Raw datas

            format_data(raw_path + os.sep
                        + "raw{}_chan{}.txt".format(timeStamp, i+1), to_save)

            # Saving Interpolated datas

            interpolated = [interp_lam_range]
            for spectra in spectras:
                interpolated.append(spectra[i].getInterpolated(
                                    startingLamb=interp_lam_range[0],
                                    endingLamb=interp_lam_range[-1],
                                    nrPoints=len(interp_lam_range)).values)
            format_data(interp_path + os.sep
                        + "interp{}_chan{}.txt".format(timeStamp, i+1),
                        interpolated)

            # Saving Cosmetic datas

            cosmetic = [interp_lam_range]
            for spectrum in spectras:
                cosmetic.append(spectra[i].getInterpolated(
                                startingLamb=interp_lam_range[0],
                                endingLamb=interp_lam_range[-1],
                                nrPoints=len(interp_lam_range),
                                smoothing=True).values)
            format_data(cosmetic_path + os.sep
                        + "cosm{}_chan{}.txt".format(timeStamp, i+1), cosmetic)

        config_dict = self.get_saving_dict()

        # Here we write all informations about current configuration

        with open(save_dir + os.sep + "config.txt", "w") as file:
            file.write("BNC parameters :\n")
            for i, pulse_dict in enumerate(config_dict[0]):  # bnc
                file.write("\tPulse {} :\n".format(i+1))
                for key, value in pulse_dict.items():
                    file.write("\t\t{} : {}\n".format(key, value))
            for key in self.CONFIG_KEYS:
                if key != self.SEPARATOR_ID:
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
        self.destroy()


def report_callback_exception(self, *args):
    err = traceback.format_exception(*args)
    tMsg.showerror("Error", args[0])  # This is exception message
    logger.critical("Error :", exc_info=err)


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
