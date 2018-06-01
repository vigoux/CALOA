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

    def __init__(self, master=None, P_bnc=None):

        super().__init__(master)
        if P_bnc is None:
            P_bnc = BNC.BNC(P_dispUpdate=False)
        self.experiment_on = False
        self._bnc = P_bnc
        self.avh = spectro.AvaSpec_Handler()
        self.focus_set()
        self.pack()
        self.createScreen()
        self.initMenu()

    def createScreen(self, menu=True):
        self.mainOpt = ttk.Notebook(self)

        wind2 = self.createWidgetsSimple(self.mainOpt)
        self.mainOpt.add(wind2, text="Normal")

        wind = self.createWidgetsAdvanced(self.mainOpt)
        self.mainOpt.add(wind, text="Advanced")

        self.mainOpt.pack()

    def initMenu(self):
        menubar = tk.Menu(self.master)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open config", command=self.loadConfig)
        filemenu.add_command(label="Save current config",
                             command=self.saveConfig)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.master.config(menu=menubar)

    def updateScreen(self):
        self.mainOpt.update()

    def byeLiveUpdate(self):
        with main_lock:
            self.stop_live_display.set()
            del self.liveDisplay
            self.display_routine.join()

    def routine_data_sender(self):
        if not self.pause_live_display.wait(0):
            self.avh.acquire()
            self.avh.prepareAll(intTime=10)
            scopes = self.avh.startAllAndGetScopes()

            # list.copy() is realy important because of the
            # further modification of the list.
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
        else:
            self.after(1000, self.routine_data_sender)

    # Save and load

    # Useful constants

    BNC_ID, T_TOT_ID, T_ID, N_C_ID, N_D_ID, STARTLAM_ID, ENDLAM_ID, NRPTS_ID = \
        "BNC", "T_TOT", "T", "N_C", "N_D", "STARTLAM", "ENDLAM", "NRPTS"

    def loadConfig(self):
        with tkFileDialog.askopenfile(mode="rb",
                                      filetypes=[("CALOA Config file",
                                                  "*.cbc")]) as saveFile:
            unpick = Unpickler(saveFile)
            tp_config_dict = unpick.load()
            try:
                self._bnc.load_from_pick(tp_config_dict[self.BNC_ID])
                self.T_tot.set(tp_config_dict[self.T_TOT_ID])
                self.T.set(tp_config_dict[self.T_ID])
                self.N_c.set(tp_config_dict[self.N_C_ID])
                self.N_d.set(tp_config_dict[self.N_D_ID])
                self.startLambda.set(tp_config_dict[self.STARTLAM_ID])
                self.stopLambda.set(tp_config_dict[self.ENDLAM_ID])
                self.nrPoints.set(tp_config_dict[self.NRPTS_ID])
            except Exception as e:
                logger.critical("Error while loading file :", exc_info=e)
            finally:
                self.updateScreen()

    def get_saving_dict(self):
        return {self.BNC_ID: self._bnc.save_to_pickle(),
                self.T_TOT_ID: self.T_tot.get(),
                self.T_ID: self.T.get(),
                self.N_C_ID: self.N_c.get(),
                self.N_D_ID: self.N_d.get(),
                self.STARTLAM_ID: self.startLambda.get(),
                self.STOPLAM_ID: self.stopLambda.get(),
                self.NRPTS_ID: self.nrPoints.get()}

    def saveConfig(self):
        saveFileName = tkFileDialog.asksaveasfilename(
            defaultextension=".cbc",
            filetypes=[("CALOA Config file",
                        "*.cbc")])
        with open(saveFileName, "wb") as saveFile:
            pick = Pickler(saveFile)
            total_list = self.get_saving_dict()
            pick.dump(total_list)

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
        tk.Button(button_fen, text="Launch experiment",
                  command=self.experiment).grid(row=0, column=0)
        tk.Button(button_fen, text="Stop Experiment",
                  command=self.stop_experiment).grid(row=0, column=1)

        tk.Label(button_fen,
                 text="Total experiment time (in s)").grid(row=10, column=0,
                                                           sticky=tk.W)
        try:
            self.T_tot
        except AttributeError:
            self.T_tot = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.T_tot).grid(row=10, column=1)

        tk.Label(button_fen,
                 text="Integration time (in s)").grid(row=20, column=0,
                                                      sticky=tk.W)
        try:
            self.T
        except AttributeError:
            self.T = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.T).grid(row=20, column=1)

        tk.Label(button_fen,
                 text="Averaging Number (integer)").grid(row=30, column=0,
                                                         sticky=tk.W)
        try:
            self.N_c
        except AttributeError:
            self.N_c = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.N_c).grid(row=30, column=1)

        tk.Label(button_fen,
                 text="Delay Number (integer)").grid(row=40, column=0,
                                                     sticky=tk.W)
        try:
            self.N_d
        except AttributeError:
            self.N_d = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.N_d).grid(row=40, column=1)

        ttk.Separator(button_fen,
                      orient=tk.HORIZONTAL).grid(row=50,
                                                 columnspan=2,
                                                 sticky=tk.E+tk.W,
                                                 pady=5)

        tk.Label(button_fen,
                 text="Starting wavelenght (in nm)").grid(row=60,
                                                          column=0,
                                                          sticky=tk.W)
        try:
            self.startLambda
        except AttributeError:
            self.startLambda = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.startLambda).grid(row=60,
                                                                 column=1)

        tk.Label(button_fen,
                 text="Ending wavelenght (in nm)").grid(row=70,
                                                        column=0,
                                                        sticky=tk.W)
        try:
            self.stopLambda
        except AttributeError:
            self.stopLambda = tk.StringVar()
        tk.Entry(button_fen, textvariable=self.stopLambda).grid(row=70,
                                                                column=1)

        tk.Label(button_fen, text="Points # (integer)").grid(row=80, column=0,
                                                             sticky=tk.W)
        try:
            self.nrPoints
        except AttributeError:
            self.nrPoints = tk.StringVar()

        tk.Entry(button_fen, textvariable=self.nrPoints).grid(row=80, column=1)

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
                                         ["Scopes", "Absorbance"],
                                         self.stop_live_display)
        self.liveDisplay.pack(fill=tk.BOTH)
        self.after(0, self.routine_data_sender)
        scope_fen.pack(side=tk.RIGHT, padx=10, pady=10, fill=tk.BOTH)

        return frame

    def stop_experiment(self):

        self.experiment_on = False

    # TODO: there is some work here to make more event programming id:33
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/44
    # IDEA: N/B introduce possibility to im/export ascii from/to disk id:35
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/46
    # IDEA: In the end, write N/B as default, to be red at next start. id:34
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/45
    """
    def set_black(self):
        experiment_logger.info("Setting black.")
        self._bnc.run()
        self.avh.startAll(p_N_c)
        n_black = 0
        while n_black < p_N_c and self.experiment_on:

            self._bnc.sendtrig()
            time.sleep(p_T)
            self.update()


            n_black += 1
            experiment_logger.debug("Done black {}/{}".format(n_black,
                                                              p_N_c))
        self.avh.stopAll()
        self._bnc.stop()
        self.totalSpectras.append(self.avh.getScopes())
        experiment_logger.info("Black set.")
    """

    def experiment(self):
        experiment_logger.info("Starting experiment")
        self.experiment_on = True
        self.pause_live_display.set()
        self.avh.acquire()
        abort = False

        p_T_tot = float(self.T_tot.get())
        p_T = float(self.T.get())
        p_N_c = int(self.N_c.get())
        p_N_d = int(self.N_d.get())

        n_d = 1

        self._bnc.setmode("SINGLE")
        self._bnc.settrig("TRIG")

        for pulse in self._bnc:
            pulse[BNC.DELAY] = pulse.experimentTuple[BNC.DELAY].get()
            pulse[BNC.WIDTH] = pulse.experimentTuple[BNC.WIDTH].get()
            pulse[BNC.STATE] = pulse.experimentTuple[BNC.STATE].get()
            assert(p_N_d*float(pulse.experimentTuple[BNC.dPHASE].get()) < p_T)

        self.avh.prepareAll(p_T*(10**3), True, p_N_c)
        self.totalSpectras = []

        if not abort and tMsg.\
                askokcancel("Black", "Ready to set black ? (Cancel to exit)"):

            experiment_logger.info("Setting black.")
            self._bnc.run()
            self.avh.startAll(p_N_c)
            n_black = 0
            while n_black < p_N_c and self.experiment_on:

                self._bnc.sendtrig()
                self.after(int(p_T_tot*1E3))
                self.update()

                n_black += 1
                experiment_logger.debug("Done black {}/{}".format(n_black,
                                                                  p_N_c))
            self.avh.waitAll()
            self._bnc.stop()
            self.totalSpectras.append(self.avh.getScopes())
            experiment_logger.info("Black set.")
        else:
            experiment_logger.warning("Black not set, aborting.")
            abort = True
            self.experiment_on = False

        if not abort and tMsg.\
                askokcancel("White", "Ready to set white ? (Cancel to exit)"):
            experiment_logger.info("Setting white.")
            self._bnc.run()
            self.avh.startAll(p_N_c)
            n_white = 0
            while n_white < p_N_c and self.experiment_on:

                self._bnc.sendtrig()
                self.after(int(p_T_tot*1E3))
                self.update()

                n_white += 1
                experiment_logger.debug("Done black {}/{}".format(n_white,
                                                                  p_N_c))
            self.avh.waitAll()
            self._bnc.stop()
            self.totalSpectras.append(self.avh.getScopes())
            experiment_logger.info("White set.")
        else:
            experiment_logger.warning("White not set, aborting.")
            self.experiment_on = False
            abort = True

        experiment_logger.info("Starting observation.")
        if not abort and tMsg.\
                askokcancel("Ready", "Ready to start experiment ?"):

            pop_up = tk.TopLevel()
            pop_up.title("Processing...")
            pop_up["height"] = 100
            pop_up["width"] = 100

            message = tk.Message(pop_up)

            while n_d <= p_N_d and self.experiment_on:
                n_c = 1
                self._bnc.run()
                self.avh.startAll(p_N_c)

                while n_c <= p_N_c and self.experiment_on:
                    message["text"] = \
                        "Processing \n\tAvg : {}/{}".format(n_c, p_N_c)\
                         + "\n\tDelay : {}/{}".format(n_d, p_N_d)
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
                self.totalSpectras.append(tp_scopes)
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
        self.treatSpectras()
        self.avh.release()
        self.pause_live_display.clear()

    def treatSpectras(self):

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
            "{time.tm_day}_{time.tm_month}_{time.tm_hour}_{time.tm_min}".\
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
            to_save = [self.totalSpectras[0][0].lambdas]
            interp_lam_range = list(linspace(float(self.startLambda.get()),
                                             float(self.stopLambda.get()),
                                             int(self.nrPoints.get())))

            # Saving Raw datas
            for spectra in self.totalSpectras:
                to_save.append(spectra[i].values)  # Gathering Raw datas

            format_data(raw_path + os.sep
                        + "raw{}_chan{}.txt".format(timeStamp, i+1), to_save)

            # Saving Interpolated datas

            interpolated = [interp_lam_range]
            for spectra in self.totalSpectras:
                interpolated.append(spectra[i].getInterpolated(
                                    startingLamb=interp_lam_range[0],
                                    endingLamb=interp_lam_range[-1],
                                    nrPoints=len(interp_lam_range)).values)
            format_data(interp_path + os.sep
                        + "interp{}_chan{}.txt".format(timeStamp, i+1),
                        interpolated)

            # Saving Cosmetic datas

            cosmetic = [interp_lam_range]
            for spectrum in self.totalSpectras:
                cosmetic.append(spectra[i].getInterpolated(
                                startingLamb=interp_lam_range[0],
                                endingLamb=interp_lam_range[-1],
                                nrPoints=len(interp_lam_range),
                                smoothing=True).values)
            format_data(cosmetic_path + os.sep
                        + "cosm{}_chan{}.txt".format(timeStamp, i+1), cosmetic)

        config_list = self.get_saving_dict()
        with open(save_dir + os.sep + "config.txt", "w") as file:
            file.write("BNC parameters :\n")
            for i, pulse_dict in enumerate(config_list[0]):
                file.write("\tPulse {} :\n".format(i+1))
                for key, value in pulse_dict.items():
                    file.write("\t\t{} : {}\n".format(key, value))
            file.write("T : {}\n".format(config_list[1]))
            file.write("N_c : {}\n".format(config_list[2]))
            file.write("N_d : {}\n".format(config_list[3]))
            file.write("startLambda : {}\n".format(config_list[4]))
            file.write("stopLambda : {}\n".format(config_list[5]))
            file.write("nrPoints : {}\n".format(config_list[6]))
            file.close()

    def goodbye_app(self):
        self._bnc._bnc_handler._con.close()
        self.pause_live_display.is_set()
        self.experiment_on = True
        self.avh._done()
        self.destroy()


def report_callback_exception(self, *args):
    err = traceback.format_exception(*args)
    tMsg.showerror("Error", err)
    logger.critical("Error :", exc_info=err)


tk.Tk.report_callback_exception = report_callback_exception

print("CALOA Copyright (C) 2018 Thomas Vigouroux")
print("This program comes with ABSOLUTELY NO WARRANTY.")
print("This is a free software, and you are welcome to redistribute it")
print("under certain conditions.")


def root_goodbye():
    global root
    global app
    app.goodbye_app()
    root.destroy()


root = tk.Tk()
root.title("CALOA")
app = Application(master=root)
root.protocol("WM_DELETE_WINDOW", root_goodbye)
app.mainloop()


logger_init.filehandler.doRollover()
logging.shutdown()
