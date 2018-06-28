#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This module is basically the .dll wrapper, used to handle spectrometers.

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
import ctypes
import os
import enum
import logger_init
from scipy import linspace
from scipy.interpolate import CubicSpline
from scipy.signal import savgol_filter
import math
from threading import Event, Lock
import time

abp = os.path.abspath("as5216x64.dll")
AVS_DLL = ctypes.WinDLL(abp)


# %% DLL Wrapper part

#####
# Constants
#####

AVS_SERIAL_LEN = 10
AVS_SATURATION_VALUE = 65535

#####
# Exception
#####


class c_AVA_Exceptions(Exception):

    AVA_EXCEPTION_CODES = {
            -1: ("ERR_INVALID_PARAMETER",
                 "Function called with invalid parameter value"),
            -2: ("ERR_OPERATION_NOT_SUPPORTED",
                 ""),
            -3: ("ERR_DEVICE_NOT_FOUND",
                 "Opening communication failed or time-out occurs."),
            -4: ("ERR_INVALID_DEVICE_ID",
                 "AvsHandle is unknown in the DLL."),
            -5: ("ERR_OPERATION_PENDING",
                 "Function is called while result of previous call to"
                 " AVS_Measure is not received yet."),
            -6: ("ERR_TIMEOUT",
                 "No anwer received from device."),
            -7: ("Reserved", ""),
            -8: ("ERR_INVALID_MEAS_DATA",
                 "Not measure data is received at the point AVS_GetScopeData"
                 " is called."),
            -9: ("ERR_INVALID_SIZE",
                 "Allocated buffer size is too small."),
            -10: ("ERR_INVALID_PIXEL_RANGE",
                  "Measurement preparation failed because pixel range"
                  " is invalid."),
            -11: ("ERR_INVALID_INT_TIME",
                  "Measurement preparation failed because integration time"
                  " is invalid."),
            -12: ("ERR_INVALID_COMBINATION",
                  "Measurement preparation failed because of an invalid"
                  " combination of parameters."),
            -13: ("Reserved", ""),
            -14: ("ERR_NO_MEAS_BUFFER_AVAIL",
                  "Measurement preparation failed because no measurement"
                  " buffers available."),
            -15: ("ERR_UNKNOWN",
                  "Unknown error reason received from spectrometer."),
            -16: ("ERR_COMMUNICATION",
                  "Error in communication occurred."),
            -17: ("ERR_NO_SPECTRA_IN_RAM",
                  "No more spectra available in RAM, all read or measurement"
                  " not started yet."),
            -18: ("ERR_INVALID_DLL_VERSION",
                  "DLL version information could mot be retrieved."),
            -19: ("ERR_NO_MEMORY",
                  "Memory allocation error in the DLL."),
            -20: ("ERR_DLL_INITIALISATION",
                  "Function called before AVS_Init is called."),
            -21: ("ERR_INVALID_STATE",
                  "Function failed because AvaSpec is in wrong state."),
            -22: ("ERR_INVALID_REPLY",
                  "Reply is not a recognized protocol message."),
            -100: ("ERR_INVALID_PARAMETER_NR_PIXEL",
                   "NrOfPixel in Device data incorrect."),
            -101: ("ERR_INVALID_PARAMETER_ADC_GAIN",
                   "Gain Setting Out of Range."),
            -102: ("ERR_INVALID_PARAMETER_ADC_OFFSET",
                   "OffSet Setting Out of Range."),
            -110: ("ERR_INVALID_MEASPARAM_AVG_SAT2",
                   "Use of saturation detection level 2 is not compatible"
                   " with the averaging function."),
            -111: ("ERR_INVALID_MEASPARAM_AVD_RAM",
                   "Use of Averaging is not compatible with StoreToRAM"
                   " function."),
            -112: ("ERR_INVALID_MEASPARAM_SYNC_RAM",
                   "Use of Synchronize setting is not compatible with"
                   " StoreToRAM function"),
            -113: ("ERR_INVALID_MEASPARAM_LEVEL_RAM",
                   "Use of Level Triggering is not compatible with"
                   " StoreToRAM function."),
            -114: ("ERR_INVALID_MASPARAM_SAT2_RAM",
                   "Use of Saturation Detection Level 2 is not compatible"
                   " with the StoreToRAM function."),
            -115: ("ERR_INVALID_MEASPARAM_FWVER_RAM",
                   "The StoreToRAM function is only supported with firmware"
                   " version 0.20.0.0 or later."),
            -116: ("ERR_INVALID_MEASPARAM_DYNDARK",
                   "Dynamic Dark Correction not supported."),
            -120: ("ERR_NOT_SUPPORTED_BY_SENSOR_TYPE",
                   "Use of AVS_SetSensitivityMode not supported by"
                   " detector type."),
            -121: ("ERR_NOT_SUPPORTED_BY_FW_VER",
                   "Use of AVS_SetSensitivityMode not supported by"
                   " firmware version."),
            -122: ("ERR_NOT_SUPPORTED_BY_FPGA_VER",
                   "use of AVS_SetSensitivityMode not supported by"
                   " FPGA version."),
            -140: ("ERR_SL_CALIBRATION_NOT_IN_RANGE",
                   "Spectrometer was not calibrated for stray light"
                   " correction."),
            -141: ("ERR_SL_STARTPIXEL_NOT_IN_RANGE",
                   "Incorrect start pixel found in EEProm."),
            -142: ("ERR_SL_ENDPIXEL_OUT_OF_RANGE",
                   "Incorrect end pixel found in EEProm."),
            -143: ("ERR_SL_STARTPIX_GT_ENDPIX",
                   "Incorrect start or end pixel found in EEProm."),
            -144: ("ERR_SL_MFACTOR_OUT_OF_RANGE",
                   "Factor should be in range 0.0 - 4.0.")
            }

    def __init__(self, P_codeNbr):

        self.code_nbr = P_codeNbr

    def __str__(self):

        return "\n".join(self.AVA_EXCEPTION_CODES[self.code_nbr])


#####
# Struct definition
#####

class c_AvsIdentityType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_aSerialId", ctypes.c_char * 10),  # NOT SURE
                ("m_aUserFriendlyId", ctypes.c_char * 64),
                ("m_Status", ctypes.c_int)]  # c_DeviceStatus


class c_BroadcastAnswerType(ctypes.Structure):  # VERIFIED

    _fields_ = [("InterfaceType", ctypes.c_ubyte),
                ("serial", ctypes.c_ubyte * AVS_SERIAL_LEN),
                ("port", ctypes.c_ushort),
                ("status", ctypes.c_ubyte),
                ("RemoteHostIp", ctypes.c_uint),
                ("LocalIp", ctypes.c_uint),  # NOT SURE
                ("reserved", ctypes.c_ubyte * 4)]


class c_ControlSettingsType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_StrobeControl", ctypes.c_ushort),
                ("m_LaserDelay", ctypes.c_uint),
                ("m_LaserWidth", ctypes.c_uint),
                ("m_LaserWaveLength", ctypes.c_float),
                ("m_StoreToRam", ctypes.c_ushort)]


class c_DarkCorrectionType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Enable", ctypes.c_ubyte),
                ("m_ForgetPercentage", ctypes.c_ubyte)]


class c_DeviceStatus(enum.Enum):  # VERIFIED
    UNKNOWN = 0
    USB_AVAILABLE = 1
    USB_IN_USE_BY_APPLICATION = 2
    USB_IN_USE_BY_OTHER = 3
    ETH_AVAILABLE = 4
    ETH_IN_USE_BY_APPLICATION = 5
    ETH_IN_USE_BY_OTHER = 6
    ETH_ALREADY_IN_USE_USB = 7


class c_DetectorType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_SensorType", ctypes.c_ubyte),  # SensorType
                ("m_NrPixels", ctypes.c_ushort),
                ("m_aFit", ctypes.c_float * 5),
                ("m_NLEnable", ctypes.c_bool),
                ("m_aNLCorrect", ctypes.c_double * 8),
                ("m_aLowNLCounts", ctypes.c_double),
                ("m_aHighNLCounts", ctypes.c_double),
                ("m_Gain", ctypes.c_float * 2),
                ("m_Reserved", ctypes.c_float),
                ("m_Offset", ctypes.c_float * 2),
                ("m_ExtOffset", ctypes.c_float),
                ("m_DefectivePixels", ctypes.c_ushort * 30)]


class c_DynamicStorageType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Nmsr", ctypes.c_int32),
                ("m_Reserved", ctypes.c_uint8 * 8)]


class c_EthernetSettingsType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_IpAddr", ctypes.c_uint),
                ("m_NetMask", ctypes.c_uint),
                ("m_Gateway", ctypes.c_uint),
                ("m_DhcpEnabled", ctypes.c_ubyte),
                ("m_TcpPort", ctypes.c_ushort),
                ("m_LinkStatus", ctypes.c_ubyte)]


class c_InterfaceType(enum.Enum):  # VERIFIED
    RS232 = 0
    USB5216 = 1
    USBMINI = 2
    USB7010 = 3
    ETH7010 = 4


class c_ProcessControlType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_AnalogLow", ctypes.c_float * 2),
                ("m_AnalogHigh", ctypes.c_float * 2),
                ("m_DigitalLow", ctypes.c_float * 10),
                ("m_DigitalHigh", ctypes.c_float * 10)]


# SensorType

class c_SmoothingType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_SmoothPix", ctypes.c_ushort),
                ("m_SmoothModel", ctypes.c_ubyte)]


class c_SpectrumCalibrationType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Smoothing", c_SmoothingType),
                ("m_CalInttime", ctypes.c_float),  # NOT SURE
                ("m_aCalibConvers", ctypes.c_float * 4096)]


class c_SpectrumCorrectionType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_aSpectrumCorrect", ctypes.c_float * 4096)]


class c_IrradianceType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_IntensityCalib", c_SpectrumCalibrationType),
                ("m_CalibrationType", ctypes.c_ubyte),
                ("m_FiberDiameter", ctypes.c_uint)]


class c_TecControlType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Enable", ctypes.c_bool),
                ("m_Setpoint", ctypes.c_float),
                ("m_aFit", ctypes.c_float * 2)]


class c_TempSensorType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_aFit", ctypes.c_float * 5)]


class c_TimeStampType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Date", ctypes.c_ushort),
                ("m_Time", ctypes.c_ushort)]


class c_TriggerType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Mode", ctypes.c_ubyte),
                ("m_Source", ctypes.c_ubyte),
                ("m_SourceType", ctypes.c_ubyte)]


class c_MeasConfigType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_StartPixel", ctypes.c_ushort),
                ("m_StopPixel", ctypes.c_ushort),
                ("m_IntegrationTime", ctypes.c_float),
                ("m_IntegrationDelay", ctypes.c_uint),
                ("m_NrAverages", ctypes.c_uint),
                ("m_CorDynDark", c_DarkCorrectionType),
                ("m_Smoothing", c_SmoothingType),
                ("m_SaturationDetection", ctypes.c_ubyte),
                ("m_Trigger", c_TriggerType),
                ("m_Control", c_ControlSettingsType)]


class c_StandaloneType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Enable", ctypes.c_bool),
                ("m_Meas", c_MeasConfigType),
                ("m_Nmsr", ctypes.c_short)]


class c_DeviceConfigType(ctypes.Structure):  # VERIFIED

    _fields_ = [("m_Len", ctypes.c_ushort),
                ("m_ConfigVersion", ctypes.c_ushort),
                ("m_aUserFriendlyId", ctypes.c_char * 64),
                ("m_Detector", c_DetectorType),
                ("m_Irradiance", c_IrradianceType),
                ("m_Reflectance", c_SpectrumCalibrationType),
                ("m_SpectrumCorrect", c_SpectrumCorrectionType),
                ("m_StandAlone", c_StandaloneType),
                ("m_DynamicStorage", c_DynamicStorageType),
                ("m_Temperature", c_TempSensorType * 3),
                ("m_TecControl", c_TecControlType),
                ("m_ProcessControl", c_ProcessControlType),
                ("m_EthernetSettings", c_EthernetSettingsType),
                ("m_aReserved", ctypes.c_ubyte * 13816)]

# %% CallBack Function Object for a better handling of measurments


class Callback_Measurment(Event):

    def __init__(self):
        Event.__init__(self)
        self.c_callback = \
            ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                               ctypes.POINTER(ctypes.c_int))(self.Callbackfunc)

    def Callbackfunc(self, Avh_Pointer, int_pointer):
        int_val = int_pointer.contents.value
        Avh_val = Avh_Pointer.contents.value
        if int_val >= 0:
            logger_ASH.debug("{} measurments Ready.".format(Avh_val))
            self.set()
        else:
            raise c_AVA_Exceptions(int_val)

# %% Avantes Spectrometer Handler


logger_ASH = logger_init.logging.getLogger(__name__+".AvaSpec_Handler")


class AvaSpec_Handler:

    def __init__(self, mode=0):
        Lock.__init__(self)

        logger_ASH.info("Initializing AvaSpec_Handler...")

        self._nr_spec_connected = self._init(mode)
        self.devList = self._getDeviceList()
        self.lock = Lock()
        logger_ASH.info("AvaSpec_Handler initialized.")

    def __del__(self):

        logger_ASH.info("Deleting AvaSpec_Handler...")

        logger_ASH.debug("Closing communications...")

        self._done()

    def _check_error(self, result, func, arguments):
        if result < 0:
            raise c_AVA_Exceptions(result)
        return arguments

    def _init(self, mode):

        if AVS_DLL.AVS_Init.argtypes is None:
            logger_ASH.debug("Defining AVS_Init function information...")

            AVS_DLL.AVS_Init.argtypes = [ctypes.c_short]
            AVS_DLL.AVS_Init.restype = ctypes.c_int
            AVS_DLL.AVS_Init.errcheck = self._check_error

        logger_ASH.debug("Calling AVS_Init.")
        return AVS_DLL.AVS_Init(mode)

    def _done(self):

        if AVS_DLL.AVS_Done.argtypes is None:
            logger_ASH.debug("Defining AVS_Done function information...")

            AVS_DLL.AVS_Done.argtypes = []
            AVS_DLL.AVS_Done.restype = ctypes.c_int
            AVS_DLL.AVS_Done.errcheck = self._check_error

        logger_ASH.debug("Calling AVS_Done.")
        return AVS_DLL.AVS_Done()

    def _getDeviceList(self):
        nrDev = AVS_DLL.AVS_GetNrOfDevices()
        ReqSize = ctypes.c_uint(nrDev * ctypes.sizeof(c_AvsIdentityType))
        AvsDevList = (c_AvsIdentityType * nrDev)()
        AVS_DLL.AVS_GetList.errcheck = self._check_error
        self.raw = AvsDevList
        nrDev = AVS_DLL.AVS_GetList(ReqSize,
                                    ctypes.byref(ReqSize),
                                    ctypes.byref(AvsDevList))
        devDict = dict([])
        AVS_DLL.AVS_Activate.errcheck = self._check_error
        AVS_DLL.AVS_Activate.restype = ctypes.c_uint
        for i, dev in enumerate(AvsDevList):
            if i != 0:
                begin = AvsDevList[0].m_aSerialId[:-4]
                dev.m_aSerialId = begin + dev.m_aSerialId
                dev.m_aUserFriendlyId = begin + dev.m_aUserFriendlyId
            devDict[AVS_DLL.AVS_Activate(ctypes.byref(dev))] = \
                (bytes.decode(dev.m_aUserFriendlyId), Callback_Measurment())
        return devDict

    def acquire(self):
        self.lock.acquire()

    def release(self):
        self.lock.release()

    def prepareMeasure(self, device, intTime=10, triggerred=False,
                       nrAverages=1):

        logger_ASH.debug("Preparing measurments on {}.".format(device))
        numPix = ctypes.c_short()
        AVS_DLL.AVS_GetNumPixels(device, ctypes.byref(numPix))
        Meas = c_MeasConfigType()
        Meas.m_StartPixel = 0
        Meas.m_StopPixel = numPix.value - 1
        Meas.m_IntegrationTime = intTime
        Meas.m_NrAverages = nrAverages
        Meas.m_Trigger.m_Mode = int(triggerred)
        Meas.m_Trigger.m_Source = 0
        Meas.m_Trigger.m_SourceType = 0

        AVS_DLL.AVS_PrepareMeasure(device, ctypes.byref(Meas))

    def startMeasure(self, device, nmsr):

        logger_ASH.debug("Sarting measurment on {}.".format(device))
        calback_event = self.devList[device][1]
        calback_event.clear()
        AVS_DLL.AVS_MeasureCallback(device, calback_event.c_callback, nmsr)

    def waitMeasurmentReady(self, device):
        while not self.devList[device][1].wait(0.1):
            pass

    def getScope(self, device):
        logger_ASH.debug("Gathering {} scopes.".format(device))
        timeStamp = ctypes.c_uint()
        numPix = ctypes.c_short()
        AVS_DLL.AVS_GetNumPixels(device, ctypes.byref(numPix))
        spect = (ctypes.c_double * numPix.value)()
        AVS_DLL.AVS_GetScopeData(device,
                                 ctypes.byref(timeStamp),
                                 ctypes.byref(spect))
        lambdaList = (ctypes.c_double * numPix.value)()
        AVS_DLL.AVS_GetLambda(device, ctypes.byref(lambdaList))
        logger_ASH.debug("{} scopes gathered.".format(device))
        return self.devList[device][0], Spectrum(list(lambdaList), list(spect))

    def stopMeasure(self, device):
        AVS_DLL.AVS_StopMeasure(device)

    def prepareAll(self, intTime=10, triggered=False, nrAverages=1):
        assert(intTime >= 1.1)
        for device in self.devList:
            self.prepareMeasure(device, intTime, triggered, nrAverages)

    def startAll(self, nmsr):
        for device in self.devList:
            self.startMeasure(device, nmsr)

    def waitAll(self):
        for device in self.devList:
            self.waitMeasurmentReady(device)

    def getScopes(self):
        return [self.getScope(device) for device in self.devList]

    def stopAll(self):
        for device in self.devList:
            self.stopMeasure(device)

    def getParameters(self, device):

        Device_Config = c_DeviceConfigType()
        ReqSize = ctypes.c_uint(ctypes.sizeof(Device_Config))
        AVS_DLL.AVS_GetParameter.errcheck = self._check_error
        AVS_DLL.AVS_GetParameter(device, ReqSize, ctypes.byref(ReqSize),
                                 ctypes.byref(Device_Config))

        return Device_Config

    def startAllAndGetScopes(self, nmsr=1):
        self.startAll(nmsr)
        self.waitAll()
        return self.getScopes()

# %% Spectrum Object used for an easier handling of spectras


class Spectrum:

    def __init__(self, P_lambdas, P_values, P_smoothed=False):
        self._lambdas = list(P_lambdas)
        self._values = list(P_values)
        self._smoothed = bool(P_smoothed)
        self._interpolator = CubicSpline(self._lambdas, self._values)

    def _get_lambdas(self):
        return self._lambdas.copy()

    lambdas = property(_get_lambdas)

    def _get_values(self):
        return self._values.copy()

    values = property(_get_values)

    def __iter__(self):
        return iter(zip(self.lambdas, self.values))

    def __call__(self, P_lambda):
        if P_lambda < self.lambdas[0] or P_lambda > self.lambdas[-1]:
                raise RuntimeError("{} is not ".format(P_lambda)
                                   + "contained in spectrum range (wich is"
                                   + " {} - {})".format(self.lambdas[0],
                                                        self.lambdas[-1]))
        return self._interpolator(P_lambda)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, tp_dict):
        self.__dict__ = tp_dict

    def getInterpolated(self, startingLamb=None, endingLamb=None,
                        nrPoints=None,
                        smoothing=False, windowSize=51, polDegree=5):
        if startingLamb is None or endingLamb is None or nrPoints is None:
            startingLamb = self.lambdas[0]
            endingLamb = self.lambdas[-1]
            nrPoints = len(self.lambdas)
        if startingLamb < self.lambdas[0] or endingLamb > self.lambdas[-1]:
            raise RuntimeError("{} - {} is not ".format(startingLamb,
                                                        endingLamb)
                               + "contained in spectrum range "
                               + "(wich is {} - {})".format(self.lambdas[0],
                                                            self.lambdas[-1]))
        lamb_space = linspace(startingLamb, endingLamb, nrPoints)
        if smoothing:
            if self._smoothed:
                raise RuntimeError("This spectrum has already been smoothed.")
            to_interpolate = savgol_filter(self.values, windowSize, polDegree)
            interp = CubicSpline(self.lambdas, to_interpolate)
        else:
            interp = self._interpolator

        return Spectrum(lamb_space,
                        [interp(lam) for lam in lamb_space],
                        P_smoothed=True)

    def isSaturated(self):
        return max(self.values) >= AVS_SATURATION_VALUE - 1

    # FIXME: Lambdas values may not match, interpolation ? id:30
    # Mambu38
    # 39092278+Mambu38@users.noreply.github.com
    # https://github.com/Mambu38/CALOA/issues/40
    def __add__(self, spectrum):
        l_lambdas = []
        l_values = []
        smoothed = self._smoothed or spectrum._smoothed
        for tup1, tup2 in zip(self, spectrum):
            if tup1[0] == tup2[0]:
                l_lambdas.append(tup1[0])
            else:
                raise RuntimeError("Value seems not to match.")
            l_values.append(tup1[1] + tup2[1])
        return Spectrum(l_lambdas, l_values, P_smoothed=smoothed)

    def __sub__(self, spectrum):
        l_lambdas = []
        l_values = []
        smoothed = self._smoothed or spectrum._smoothed
        for tup1, tup2 in zip(self, spectrum):
            l_lambdas.append(tup1[0])
            l_values.append(tup1[1] - tup2[1])
        return Spectrum(l_lambdas, l_values, P_smoothed=smoothed)

    def __truediv__(self, spectrum):
        l_lambdas = []
        l_values = []
        smoothed = self._smoothed or spectrum._smoothed
        for tup1, tup2 in zip(self, spectrum):
            l_lambdas.append(tup1[0])
            if tup2[1] <= 0:
                l_values.append(0)
            else:
                l_values.append(tup1[1]/tup2[1])
        return Spectrum(l_lambdas, l_values, P_smoothed=smoothed)

    def __mul__(self, spectrum):
        l_lambdas = []
        l_values = []
        smoothed = self._smoothed or spectrum._smoothed
        for tup1, tup2 in zip(self, spectrum):
            l_lambdas.append(tup1[0])
            if tup2[1] <= 0:
                l_values.append(0)
            else:
                l_values.append(tup1[1]*tup2[1])
        return Spectrum(l_lambdas, l_values, P_smoothed=smoothed)

    def __imul__(self, spectrum):
        return self * spectrum

    def absorbanceSpectrum(reference, spectrum):
        opacity_spectrum = reference/spectrum

        l_lambdas = opacity_spectrum.lambdas
        l_values = [math.log10(val) if val > 0 else 0
                    for val in opacity_spectrum.values]

        return Spectrum(l_lambdas, l_values)

# %% Spectrum_Storage class, useful for further improvements on
# spectrum handling


class Spectrum_Storage:

    """
    This class is meant to be used as a storage for spectra.
    It may be useful for further improvements of application.
    It will store all desired spectra in a folder-like way.

    Some basic "folders" are pre-built for a better handling.

    "folder" arborescence is as follows :

    Spectrum_Storage
    |- Basic
    |  |- Black
    |  |  |- [CHAN ID] : Spectrum
    |  |  |- [OTHER CHAN ID] : Spectrum
    |  |  :
    |  |- White
    |  |  :
    |- [TIMESTAMP]
    |  |- 1
    |  |  |- [CHAN ID] : Spectrum ...
    |  |  :
    |  |- 2
    |  |  :
    |  :
    |- [OTHER TIMESTAMP]
    |  :
    :
    """

    def get_timestamp(self):
        """Creates the time current time stamp as follows :
        DD:MM:YYYY_HH:MM:SS
        Where in the same order :
            D = a day number digit
            M = a month number digit
            Y = a year number digit
            H = an hour number digit
            M = a minute number digit
            S = a second number digit
        """
        return \
            "{time.tm_mday}:{time.tm_mon}:{time.tm_year}_{time.tm_hour}:{time.tm_min}:{time.tm_sec}".\
            format(time=time.localtime())

    def createStorageUnit(self):
        """
        Inits a storage unit in the storage space, time_stamp itm and returns
        his identifier (timestamp).
        """
        cur_timestamp = self.get_timestamp()
        self._hidden_directory[cur_timestamp] = []
        return cur_timestamp

    def __init__(self):
        """Inits self and creates basic storage space."""
        self._hidden_directory = {"Basic": dict([])}

    def __getitem__(self, indicator_tuple):
        """
        Get a spectrum or a list of spectra depending on
        the given indicator_tuple.
        The first index of indicator_tuple must be a Spectrum-folder identifier
            (a timestamp given by createStorageUnit method) or a slice of
            Spectrum-folder identifiers wich don't includes "Basic"
        The second can be an integer or slice of integers.
        The third and last must be an integer or slice of integers.
        """

        if len(indicator_tuple) != 3:
            raise ValueError("Argument don't have correct length.")

        if not isinstance(indicator_tuple[0], (str, slice)):
            raise ValueError("Argument nr 1 is not of the correct type."
                             + " Expected one of : str, slice.")

        if not isinstance(indicator_tuple[1], (int, slice)):
            raise ValueError("Argument nr 2 is not of the correct type."
                             + " Expected one of : int, slice.")

        if not isinstance(indicator_tuple[2], (str, slice)):
            raise ValueError("Argument nr 3 is not of the correct type."
                             + " Expected one of : str, slice.")

        class_types = tuple(map(type, indicator_tuple))

        for i in range(3):
            if class_types[i] == slice:
                if indicator_tuple[i] != slice(None, None, None):
                    raise ValueError("Use slices only with \":\"")

        if class_types == (str, int, str):

            # Her the user wants to see only one spectrum

            choosen_folder = self._hidden_directory[indicator_tuple[0]]
            choosen_subfolder = choosen_folder[indicator_tuple[1]]
            return choosen_subfolder[indicator_tuple[2]]

        elif class_types == (slice, int, str):

            # In this case the user wants to see all spectra corresponding
            # to one delay and one spectrometer.

            tp_dict_to_return = dict([])

            for key in self._hidden_directory.keys():
                if key != "Basic":
                    tp_dict_to_return[key] =\
                        self._hidden_directory[key][
                        indicator_tuple[1]][
                        indicator_tuple[2]]
            return tp_dict_to_return

        elif class_types == (str, slice, str):

            # Here we need to return a dict containing all spectra that come
            # from the same spectrometer and from the same folder

            tp_dict_to_return = dict([])

            folder = self._hidden_directory[indicator_tuple[0]]
            for key in folder.keys():
                tp_dict_to_return[key] = folder[key][indicator_tuple[2]]

        elif class_types == (str, int, slice):

            # Here we want all spectra corresponding to one delay and from
            # the same folder

            return self._hidden_directory[indicator_tuple[0]][
                indicator_tuple[1]]

        elif class_types == (slice, slice, str):

            # This corresponds to all spectra coming from the same spectrometer

            tp_dict_to_return = dict([])

            for folder_id in self._hidden_directory.keys():
                tp_dict_to_append = dict([])

                for subfolder_id in self._hidden_directory[folder_id].keys():
                    tp_dict_to_append[subfolder_id] =\
                        self._hidden_directory[folder_id][subfolder_id][
                        indicator_tuple[2]]

        elif class_types == (slice, int, slice):

            # This is all spectra with the same delay number (subfolder_id)

            tp_dict_to_return = dict([])

            for folder_id in self._hidden_directory.keys():
                tp_dict_to_return[folder_id] =\
                    self._hidden_directory[folder_id][indicator_tuple[1]]

        elif class_types == (str, slice, slice):

            # This is all spectra in the same folder

            return self._hidden_directory[indicator_tuple[0]]

        else:
            return self._hidden_directory

    def putSpectra(self, folder_id, subfolder_id, spectra):
        """
        Put given spectra in the selected folder.
        First we create a new subfolder (append it in the folder)
        Then we create a subfolder.
        Then we associate channel id to the corresponding Spectrum.
        We base this method on AvaSpec_Handler.getScopes, which returns a list
        of tuple like so :

            [(channel_id, spectrum), ...]
        """

        if folder_id not in self._hidden_directory:
            raise IndexError(
                "{} is not a correct folder id.".format(folder_id)
            )

        if subfolder_id in self._hidden_directory[folder_id]:
            raise IndexError(
                "{} is already in folder {}.".format(subfolder_id, folder_id)
            )

        if isinstance(subfolder_id, int) and folder_id != "Basic":
            raise TypeError(
                "subfolder_id must be an integer."
            )

        tp_spectrum_dict = dict({})

        for channel_id, spectrum in spectra:
            tp_spectrum_dict[channel_id] = spectrum

        self._hidden_directory[folder_id][subfolder_id] = tp_spectrum_dict

    def putBlack(self, new_spectra):

        self.putSpectra("Basic", "Black", new_spectra)

    def getBlack(self):

        return self._hidden_directory["Basic"]["Black"]

    latest_black = property(getBlack, putBlack)

    def putWhite(self, new_spectra):

        self.putSpectra("Basic", "White", new_spectra)

    def getWhite(self):

        return self._hidden_directory["Basic"]["White"]

    latest_white = property(getWhite, putWhite)

    def blackIsSet(self):

        return "Black" in self._hidden_directory["Basic"]

    def whiteIsSet(self):

        return "White" in self._hidden_directory["Basic"]

    def isExperimentReady(self):

        return self.blackIsSet() and self.whiteIsSet()
