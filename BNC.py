#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module contains all classes used to handle BNC in a more "Python" way.

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

# %% Imports


import serial
import utils
import time
import re
import logger_init
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as tMsg

# %% BNC Exceptions


class BNC_exception(Exception):
    """Exceptions used by BNC"""

    BNC_EXCEPTION_CODE = {
        "?1": "Incorrect prefix, i.e. no colon or * to start command.",
        "?2": "Missing command keyword.",
        "?3": "Invalid command keyword.",
        "?4": "Missing parameter.",
        "?5": "Invalid parameter.",
        "?6": "Query only, command needs a question mark.",
        "?7": "Invalid query, command does not have a query form.",
        "?8": "Impossible to decode buffer, please verify baudrate."
        }

    def __init__(self, P_type):
        """Constructor of exception

        Named parameters :
            - P_type -- BNC Error Code of the
                        exception (see BNC 505 manual p39)
        """

        self._type = P_type
        tMsg.showerror("Error", str(self))

    def __str__(self):
        """Method used by Exception type to display the message."""
        return self.BNC_EXCEPTION_CODE[self._type]

# %% BNC HANDLER


logger_handler = logger_init.logging.getLogger(__name__+".handler")


class BNC_Handler():
    """Useful class to handle BNC."""

    def __init__(self, port=None, baud_rate=9600):
        """Class constructor.

        Named parameters :
            - port -- port where BNC is connected, if not known, constructor
                      will search it in open ports basing on the echo mode of
                      the BNC, you thus need to be sure that echo mode is
                      enabled on the BNC.
            - baud_rate -- baud rate of the connection, if not known, will be
                           set to 9600.
        """

        self._con = None

        if port is None:  # Port is not given

            portlist = utils.serial_ports()  # Search for usable ports

            for port in portlist:  # For each, try to connect with BNC

                logger_handler.debug("Trying to connect with {}".format(port))

                tp_con = serial.Serial(port, baud_rate, timeout=1)
                tp_con.write(b"*IDN?\r\n")

                time.sleep(0.1)  # Wait a little until answer.

                try:
                    a = bytes.decode(tp_con.read_all())
                except UnicodeDecodeError:

                    # If it is impossible to decode buffer, error can be that
                    # connection's baudrates are not the same and so decoding
                    # buffer is impossible.

                    raise BNC_exception("?8")

                if a.startswith("*IDN?"):  # We got an answer !

                    self._con = tp_con  # Keep this connection
                    logger_handler.debug(
                        "Connected with "
                        + "{} id {}".format(port,
                                            a.split("\r\n")[1]))  # Log it
                    break

                else:

                    logger_handler.debug(
                            "Unable to connect with {}".format(port))
                    tp_con.close()  # Really important step

            if self._con is None:  # If none of opened port can be used.

                logger_handler.critical("Impossible to find a connection.")
                raise RuntimeError("Impossible to find a connection.")

    def _read_buffer(self):
        """Reads the input buffer and split all lines.
        Thus, as ECHO is enabled, method returns :
                [ ECHO , ANSWER/ERROR_CODE , '' ]
        """
        cur_buffer = bytes.decode(self._con.read_all())
        tp_list = cur_buffer.split("\r\n")

        return tp_list

    def _raw_send_command(self, command):
        """Send a command (with correct format) to the connection"""
        self._con.write(str.encode(command+"\r\n"))

    def send_command(self, command, waiting_time=0.1):
        """Send a command to the connection and returns the answer.

        Warnings :
            - Always resets input buffer, thus all preceding informations
              stocked in the input buffer will be discarded.
            - It is based on the ECHO mode of BNC, to verify that command is
              correctly received.

        Named parameters :
            - command -- The command to give to the BNC
            - waiting_time -- Time to wait (s) between emmision and reception
                              of the command. Be careful, experiments showed
                              that with a waiting time < 0.1s, reception
                              problems may occurs.

        Raises :
            - A BNC_Exception if an error code is received.

        After observations, BNC answers a command (not a QUERY) by "ok",
        thus method returns True in this case to allow better handling.

        After observations, there is at least a 0.07s delay between emission
        and answering of a command or query by bnc, system sleeps after
        emission.
        """

        rexp = r"^[?][1-7]"  # This is the form of BNC erros codes.

        self._con.reset_input_buffer()  # Clear input buffer
        self._raw_send_command(command)  # Send desired command

        logger_handler.debug("Command {} sent.".format(command))  # Log it

        time.sleep(waiting_time)  # After observation we need to wait a little

        tp_ans = self._read_buffer()  # Read answer.

        assert(len(tp_ans) > 0)  # If tp_ans is empty, thus there is a problem

        if tp_ans[0] != command:  # Verifying echo

            logger_handler.error(
                    "Error in matching command echo : \n{} / {}".format(
                            command, tp_ans[0]))
            raise RuntimeWarning("Error in matching command echo, expected"
                                 + "{} but found {}.".format(command,
                                                             tp_ans[0]))

        if re.search(rexp, tp_ans[1]) is not None:  # Searching error codes

            e = BNC_exception(tp_ans[1])  # If found, raise it
            logger_handler.critical("An error happened :", exc_info=e)  # log

            raise e

        if tp_ans[1] == 'ok':  # If answer is ok, returning True

            return True

        return tp_ans[1]

# %% Pulse Object


logger_pulse = logger_init.logging.getLogger(__name__+".pulse")

# COMMAND_DICT is used to match parameter name and corresponding command.

COMMAND_DICT = {"STATE": (":STAT", "bool"),
                "WIDTH": (":WIDT", float),
                "DELAY": (":DEL", float),
                "SYNC": (":SYNC", "pulse"),
                "POL": (":POL", ["Normal", "Single", "Inverted"]),
                "AMP": (":OUTP:AMPL", float),
                "MODE": (":CMOD", ["Normal", "Single", "Burst", "DCycle"]),
                "BC": (":BCO", int),
                "PC": (":PCO", int),
                "OC": (":OCO", int),
                "WC": (":WCO", int),
                "GATE": (":CGAT", ["Disable", "Low", "High"])}

# This the list off all parameters for an easier handling.

STATE, WIDTH, DELAY, SYNC, POL, AMP, MODE, BC, PC, OC, WC, GATE =\
     tuple(COMMAND_DICT)

LABEL, dPHASE = "LABEL", "dPHASE"


class Pulse():
    """Useful class to manage BNC's channels."""

    def __init__(self, P_bnc_handler, P_number, P_dispUpdate):
        """
        Constructor of the Pulse class.

        Named parameters :
            - P_bnc_handler -- A BNC handler, used to send commands to BNC.
            - P_number -- Pulse's pin number, if not in
                          [0 ; nbr of connected BNC channels] this might raise
                          BNC_Exceptions of type 3.
        """
        logger_pulse.info("Initializing P{}...".format(P_number))

        assert(P_number > 0)

        self._bnc_handler = P_bnc_handler
        self.number = P_number
        # If we want to update display after sending a command
        self._dispUpdate = P_dispUpdate
        self._state = dict([])  # State of the pulse, represented by a dict
        self._refresh_state()
        self.experimentTuple = {LABEL: None,
                                STATE: None,
                                WIDTH: None,
                                DELAY: None,
                                dPHASE: None}

        logger_pulse.info("P{} initialized.".format(P_number))

    def __str__(self):
        return "Channel {}".format(self.number)

    def __repr__(self):
        rep_str = str(self) + " :\n"
        for paramid in COMMAND_DICT:
            rep_str += "\t- " + paramid + " : " + self[paramid] + "\n"

    def __getitem__(self, P_id):
        """Useful method to get efficiently an information about channel"""
        return self._state[P_id]

    def __setitem__(self, P_id, P_newval):
        """Useful method to modify channel's parameters.

        Named parameters :
            P_id -- Parameter id, has to be in COMMAND_DICT keys.

        Always asserts that the modification is valid.
        The modification will never be applied without a BNC's confirmation.
        Updates BNC's diplay to directly see modification.
        There is some work to do here because of the great inefficiency in
        the management of numerous cases, and lack of clearness.
        """
        assert(P_id in COMMAND_DICT)  # assert that the parameter is supported

        possible = False  # Useful afterwards

        if P_id != SYNC:

            # Establish the list of all possible commands

            possible_commands = ("NORM", "COMP", "INV", "SING",
                                 "BURS", "DCYCLE", "DISABLE",
                                 "LOW", "HIGH")

            if str(P_newval) in ("0", "1"):
                possible = True
            elif str(P_newval) in possible_commands:
                possible = True
            elif str(P_newval).isnumeric():
                possible = True
            else:
                try:
                    P_newval = "{:012.8f}".format(float(P_newval))
                except Exception:
                    pass  # If P_newval isn't a float
                else:
                    possible = True

            assert(possible)  # If nothing works, exit.
        else:  # Sync case is quit diffcult to handle.
            if isinstance(P_newval, Pulse):
                P_newval = "T{}".format(P_newval.number)
            elif str(P_newval) == "0":
                P_newval = "T0"
            elif P_newval == "T0":
                pass
            else:
                raise RuntimeError("Sync parameter has to be a pulse object "
                                   + "or T0.")

        # If command is approuved by BNC, we change state parameter in python
        # elsem, we raise a error.
        if self._bnc_handler.send_command(":PULS{}".format(self.number)
                                          + COMMAND_DICT[P_id][0]
                                          + " {}".format(P_newval)):
            self._state[P_id] = str(P_newval)
        else:
            logger_pulse.error("An unknown error happened.")
            raise RuntimeError()

        if self._dispUpdate:  # Updates BNC screen, if needed.
            self._bnc_handler.send_command(":DISP:UPDATE?")

    def _refresh_state(self):
        """Gather informations about the channel at BNC_Handler"""

        tp_dict_state = dict([])

        for key in COMMAND_DICT:
            tp_dict_state[key] = self._bnc_handler.send_command(
                    ":PULS{}".format(self.number)
                    + COMMAND_DICT[key][0] + "?")
            logger_pulse.debug("{} done".format(key))
        self._state = tp_dict_state

    def _get_state(self):
        """state getter."""
        return self._state

    state = property(_get_state, doc="Dict corresponding to Pulse state")

    def pushParamsDict(self, paramsDict):
        """
        Uses each paramsDict entry to set the corresponding Pulse parameter.
        """
        logger_pulse.debug("Receiving new parameters : {}".format(paramsDict))
        for param_id in paramsDict:
            if str(self[param_id]) != str(paramsDict[param_id]):
                self[param_id] = paramsDict[param_id]

    # These methods shall not be used.

    def _drawAParam(self, master, param_id):
        """
        Useful method to draw a parameter of Pulse.
        There is still some work here, it seems not very efficient and easy
        to handle actually because of absence of convention
        """
        p_frame = tk.Frame(master)
        p_label = tk.Label(p_frame, text=param_id.capitalize())
        p_stringvar = tk.StringVar()
        p_stringvar.set(str(self[param_id]))
        p_champ = tk.Entry(p_frame, textvariable=p_stringvar)
        p_label.pack(side=tk.LEFT)
        p_champ.pack(side=tk.RIGHT)
        return p_frame, p_stringvar

    def drawParams(self, master):
        """
        Useful method to draw pulse state.
        There is still some work to do here.
        Names need to be changed for a better understanding.
        """
        logger_pulse.debug("Drawing Pulse {}".format(self.number))
        m_frame = tk.Frame(master)
        string_vars = dict([])
        for i, param_id in enumerate(COMMAND_DICT):
            p_frame, string_var = self._drawAParam(m_frame, param_id)
            string_vars[param_id] = string_var
            p_frame.pack(fill="both")
        return m_frame, string_vars

    # Experiment Management

    def drawSimple(self, master):
        """Method used to draw in a simple way the pulse."""
        master_frame = tk.LabelFrame(master, text=str(self))
        if self.experimentTuple[LABEL] is None:
            self.experimentTuple[LABEL] = tk.StringVar()
        tk.Entry(master_frame,
                 textvariable=self.experimentTuple[LABEL]).grid(row=0,
                                                                column=0)

        tk.Label(master_frame, text="Activate : ").grid(row=1, column=0,
                                                        sticky=tk.W)
        if self.experimentTuple[STATE] is None:
            self.experimentTuple[STATE] = tk.StringVar()
            self.experimentTuple[STATE].set(int(self[STATE]))
        tk.Checkbutton(master_frame,
                       variable=self.experimentTuple[STATE]).grid(row=1,
                                                                  column=1,
                                                                  sticky=tk.W)

        tk.Label(master_frame, text="Width (in s) : ").grid(row=2, column=0,
                                                            sticky=tk.W)
        if self.experimentTuple[WIDTH] is None:
            self.experimentTuple[WIDTH] = tk.StringVar()
            self.experimentTuple[WIDTH].set(self[WIDTH])
        tk.Entry(master_frame,
                 textvariable=self.experimentTuple[WIDTH]).grid(row=2,
                                                                column=1,
                                                                sticky=tk.W)

        tk.Label(master_frame, text="Phase (in s) : ").grid(row=3, column=0,
                                                            sticky=tk.W)
        if self.experimentTuple[DELAY] is None:
            self.experimentTuple[DELAY] = tk.StringVar()
            self.experimentTuple[DELAY].set(self[DELAY])
        tk.Entry(master_frame,
                 textvariable=self.experimentTuple[DELAY]).grid(row=3,
                                                                column=1,
                                                                sticky=tk.W)

        tk.Label(master_frame,
                 text="Phase Variation (in s) : ").grid(row=4, column=0,
                                                        sticky=tk.W)
        if self.experimentTuple[dPHASE] is None:
            self.experimentTuple[dPHASE] = tk.StringVar()
            self.experimentTuple[dPHASE].set("0")
        tk.Entry(master_frame,
                 textvariable=self.experimentTuple[dPHASE]).grid(row=4,
                                                                 column=1,
                                                                 sticky=tk.W)

        return master_frame

    # Loading and saving

    def save_to_pickle(self):
        state_dict = dict([])
        for key, val in list(self.experimentTuple.items()):
            state_dict[key] = val.get()
        return state_dict

    def load_from_pick(self, loaded):
        for key, val in list(loaded.items()):
            self.experimentTuple[key].set(val)


# %% BNC


logger_main = logger_init.logging.getLogger(__name__+".BNC")


class BNC():

    """Usefull class to handle and manage BNC, in the highest level."""

    def __init__(self, P_bnc_handler=None, P_channelnumber=8,
                 P_dispUpdate=True):
        """Initialize self.

        Named Parameters :
            - P_bnc_handler -- A BNC handler, used to send commands, and to
                               initialize all Pulses
            - P_channelnumber -- Number of channels of connected BNC.
        """
        logger_main.info("Initializing BNC...")
        if P_bnc_handler is None:
            self._bnc_handler = BNC_Handler()
        else:
            self._bnc_handler = P_bnc_handler

        self._pulse_list = []
        self._stringListeners = []
        self.main_fen = None
        for i in range(1, P_channelnumber+1):
            self._pulse_list.append(Pulse(self._bnc_handler, i, P_dispUpdate))
        logger_main.info("BNC initialized.")

    # Pulses Management.

    def __getitem__(self, P_nbr):
        """Useful method to access to one of BNC's Pulse."""
        if P_nbr <= 0:
            raise IndexError("Invalid index, to set BNC period or global "
                             + "parameters, use methods instead.")
        return self._pulse_list[P_nbr-1]

    def __iter__(self):
        return iter(self._pulse_list)

    def reset(self):
        """Resets BNC."""
        logger_main.info("Reseting BNC...")
        self._bnc_handler.send_command("*RST", 1)
        self._bnc_handler.send_command(":DISP:UPDATE?")
        for i, p in enumerate(self._pulse_list):
            logger_main.info("Reseting P{}".format(i))
            p._refresh_state()
        logger_main.info("BNC reseted.")
        if self.main_fen is not None:
            self._update_frame()

    # T0 Management.

    def get_id(self):
        """Returns BNC's ID."""
        return self._bnc_handler.send_command("*IDN?")

    def run(self):
        """Runs BNC."""
        logger_main.debug("BNC runs...")
        self._bnc_handler.send_command(":PULS0:STAT 1")

    def stop(self):
        """Stops BNC."""
        self._bnc_handler.send_command(":PULS0:STAT 0")
        logger_main.debug("BNC stopped.")

    def _set_period(self, P_period):
        """Sets T0's period to P_period."""
        self._bnc_handler.send_command(":PULS0:PER {}".format(P_period))
        logger_main.debug("BNC period changed to {}".format(P_period))

    def _get_period(self):
        """Returns T0 period."""
        return float(self._bnc_handler.send_command(":PULS0:PER?"))

    period = property(_get_period, _set_period,
                      doc="Period of BNC's T0.\n"
                      + "Warning : period is never stocked in a proper \n"
                      + "attribute but is only a property (ie a couple of \n"
                      + "methods).")

    def setmode(self, newMode):
        return self._bnc_handler.send_command(":PULS0:MOD {}".format(newMode))

    def settrig(self, newMode):
        return self._bnc_handler.\
            send_command(":PULS0:EXT:MOD {}".format(newMode))

    def sendtrig(self):
        return self._bnc_handler.send_command("*TRG")

    # Drawing methods.

    def drawComplete(self, master):
        """Method called to draw BNC.
        There is some work to do here, mainly because of the great lack of
        clarity and inefficiency of the code."""
        logger_main.debug("Starting to draw BNC.")
        self.main_fen = tk.Frame(master)
        self.panes = ttk.Notebook(self.main_fen)
        for i, pulse in enumerate(self._pulse_list):
            f, chanStrings = pulse.drawParams(self.panes)
            self._stringListeners.append(chanStrings)
            self.panes.add(f, text=str(pulse))
        self.panes.pack(side=tk.LEFT)
        self.Lfen = tk.Frame(self.main_fen)
        update_button = tk.Button(self.Lfen, text="Update Display",
                                  command=self._update_frame)
        update_button.pack()
        push_params_button = tk.Button(self.Lfen, text="Push Parameters",
                                       command=self._push_parameters)
        push_params_button.pack()
        self.Lfen.pack(side=tk.RIGHT)
        return self.main_fen

    def _update_frame(self):
        """Internal method called to update """
        self.panes.destroy()
        self.panes = ttk.Notebook(self.main_fen)
        for i, pulse in enumerate(self._pulse_list):
            f, chanStrings = pulse.drawParams(self.panes)
            self._stringListeners[i] = chanStrings
            self.panes.add(f, text=str(pulse))
        self.panes.pack()

    def _push_parameters(self):
        """Method used to push all parameters gathered by the interface."""
        logger_main.debug("Pushing new parameters.")
        for i in range(1, len(self._pulse_list)+1):
            tp_dict = dict([])
            for paramid in COMMAND_DICT:
                tp_dict[paramid] = self._stringListeners[i][paramid].get()
            self[i].pushParamsDict(tp_dict)
        self._update_frame()

    def drawSimple(self, master):
        master_fen = tk.Frame(master)
        for i, pulse in enumerate(self):
                pulse.drawSimple(master_fen).grid(row=i % 4,
                                                  column=i // 4,
                                                  padx=10,
                                                  pady=10)
        return master_fen

    # Save and load

    def save_to_pickle(self):
        pulse_pick_list = []

        for pulse in self:
            pulse_pick_list.append(pulse.save_to_pickle())

        return pulse_pick_list

    def load_from_pick(self, loaded):

        for i, dic in enumerate(loaded):
            self[i+1].load_from_pick(dic)
