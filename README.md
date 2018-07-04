# CALOA
CALOA project
Summary :

1. [Licence](README.md#licence)
2. [Installation](README.md#installation)
    1. Installing Python
    2. Installing PySerial
    3. Installing FTDI CDM drivers
    4. Installing CALOA
3. [Using CALOA](README.md#using-caloa)
    1. Starting CALOA
    2. Interface overview
    3. Starting an observation
    4. Using advanced mode
    5. Gathering saved datas


# Licence

CALOA is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CALOA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CALOA.  If not, see [here](http://www.gnu.org/licenses/gpl.html).

# Installation

Requires admin privileges.

Installation of CALOA is simple but there is some really important steps that
have to be carefully taken.
Installation is done by an installer which runs all third-party installers
useful to run CALOA.
If Python 3 is already installed on your computer, it is recommended to  
uninstall it to use Anaconda Python 3 instead. Anaconda provides a wide
selection of scientific python libraries. An uninstaller is provided with
CALOA Installer to allow you to easily uninstall Python 3.
Python 2 does not need to be uninstalled.
Installation can be split in 4 parts.

## Connect the spectrometer and the BNC via USB-to-Serial to the computer
to be used for installation and operating.

## Installing Python

Python 3.6 environment (env. 0.5 Gb disk space required) was used to write
the CALOA application, and is used during installation and execution.
During installation, an Python installer window will pop up.
Here is a really important step which have to be taken to use CALAO and
successfully run installation.
During Python installation, while encountering Advanced Installation Options,
select "Add Python to the PATH environment variable", if this step is not
taken, installation will not be complete and CALOA will not be usable.
Appearance of cmd.exe window is is normal, they will be closed afterwards.

In the end of installation, after VSCode installation is prompted, install it.
This will need an internet connection, if you do not have one, there is an installer
along with

## Installing libraries

Many libraries are used by CALOA to complete its role.
They will be be installed automatically, as long as, all previous steps has
been followed correctly.

## Installing FTDI CDM Drivers

FTDI CDM Drivers is needed for USB-to-Serial interfacing.
A new installation window will pop-up, simply follow the steps given by the
installer.

## Installing CALOA

This is the program that pilots communication with both BNC generator and
Avantes fiber spectrometers.
Installation will be done automatically.

If all went right, you can choose to start the application

# Using CALOA

## Starting CALOA

To start CALOA, simply double click on the CALOA short-cut.
Then a console will run, don't close this console manually, this will cause
CALOA to crash.
In this console, some information will be written, please DO NOT interact
with the console while it is starting, wait for GUI to appear.

## Interface overview

On the top of the frame, below menu bar, you can choose your "mode" between
"Normal" and "Advanced".

### Normal mode

Normal mode interface can be split in 3 parts :

#### BNC channel setter

This part of the interface is the lefter one.
Here we can divide interface in 8 similar labeled boxes. Each one of this boxes
corresponds to one of the BNC Channels (often named Pulse). A box contains many
informations :
- Pulse Label (text) : the name you want to give to the Pulse.
- Pulse state (check box) : whether you want the pulse to be active or not.
- Pulse width (floating point number) : width of the real TTL pulse in sec
- Pulse phase (floating point number) : delay between trigger and TTL pulse in
  sec
- Pulse phase variation (floating point number) : delay variation in sec

#### Observation management frame

Here again, interface can be split in three parts :

##### Experiment management

In this part, you can fix your experiment parameters :

* Total time : total time your observation will take (i.e. the time
  between two triggers).
* Observation time : integration time of the spectrometers.
* Averaging number : Averaging number of the spectrometers.
* Delay number : number of delays you want to do.

##### Interpolation management

In this part you can set you interpolation parameters.

* Starting wavelength : the wavelength you want the spectra to start with
* Ending wavelength : the wavelength you want the spectra to end with
* Points number : number of points you want between starting and ending
  wavelengths.
##### Reference channel selector
Here is the useful part to manage absorbance reference spectrum,
select here the AvaSpec channel used as reference.

#### Scope Display

Here you can select which scope you want to see, note that absorbance scope
will not be displayed before you've selected a reference channel.
It is composed of multiple panes clearly identified.

### Advanced mode

This is really not useful to interact with BNC using this mode.
But if you want some fine tunes of BNC, you should use this interface.
More informations about how to use and program BNC are given in his own documentation,
given along this file.

## Starting an observation

CALOA is used to perform spectrometry over time using a generator and Avantes
spectrometers.

### Enter experiment parameters

First of all you will have to enter your parameters in the application.
Enter the total observation time (this is the time between two triggers) in
the Entry labeled "Total time" in milliseconds.
Then enter the integration time of the spectrometers, be careful,
if you use multiple spectrometers, some tests showed that a minimum integration
time of 15 ms is needed.
Then enter the number of averages and number of delays.
Averaging number corresponds to the number of averages for a single delay
number.
Delay number corresponds to the number of times CALOA will delay all
instruments.

### Enter generator parameters

You now have to set all parameters for all 8 generator channels.
In each channel cell, as previously mentionned, you can set 5 parameters.
Label can be set to whatever value you want, it is used as a human readable
identification.
Channel parameters will be send to the generator only if State is enabled, if
not, for the sake of time saving other parameters will be skipped.

### Set black and white

#### By observation

You will now need to set Black and White. Your hardware setup needs to be
set for each of them, for example, after setting your hardware to a
"Black"-mode, hit "Set Black" button, this will set black spectra. Then
proceed in the same order to set white.

#### From a file

After observation of black (or white), you can save spectra in files.

To do this :

1. Select, in the menu, "Spectra"
2. Click on the button corresponding to the spectrum you want to save
3. Then click on "Save"

You will then be asked to selected a file to save selected spectra.

After that, you can load this files instead of observing.

If you already observed Black and White spectra and exited the application,
they will be saved and loaded automatically.

### Select the reference

Now, select a reference channel, it will be used to compute absorbance during
the experiment.

### Run experiment

After that you can hit "Start experiment" to run the observation. CALOA will
proceed as such :

1. Set width and delay for each channel
2. Prepare measures on spectrometers
3. Trigger generator (which trigger all instruments in the determined order)
4. Go to Step 3 for a total of <Averaging number> of times.
5. Recover spectra, store them, and display them
6. Increment delay of phase variation for each channel
7. Go to step 3 for a total of <Delay number> of time

### Save observed data

After that, you will be asked for a folder where you want to save datas.
Datas will be saved in a predetermined organization :
```
  selected_folder :
    save[TIMESTAMP]:
      raw:
        [A FILE FOR EACH CHANNEL]
      interp:
        [A FILE FOR EACH CHANNEL]
      cosmetic:
        [A FILE FOR EACH CHANNEL]
      config.txt
```
In each file (except config.txt), datas will be organized in lines as follows :

| LAMBDAS | BLACK | WHITE | Spectrum 1 | Spectrum 2 | ... |
| ------- | ----- | ----- | ---------- | ---------- | --- |

Folder raw will contain raw datas, interp interpolated datas, and cosmetic
smoothed datas.
