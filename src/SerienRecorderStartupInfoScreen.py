# coding=utf-8

# This file contains the SerienRecoder Startup Info Screen
# showing the release notes of the latest version
from Screens.Screen import Screen
from Tools.Directories import fileExists
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.config import config, configfile

from enigma import getDesktop

class ShowStartupInfo(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	BUTTON_X = DESKTOP_WIDTH / 2
	BUTTON_Y = DESKTOP_HEIGHT - 50

	skin = """
		<screen name="SerienRecorderHints" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
			<widget name="srlog" position="5,5" size="%d,%d" font="Regular;21" valign="left" halign="top" foregroundColor="#FFFFFF" transparent="1" zPosition="5"/>
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/SerienRecorder/images/key_ok.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_ok" position="%d,%d" size="%d,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/SerienRecorder/images/key_exit.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_exit" position="%d,%d" size="%d,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>""" % (10, 10, DESKTOP_WIDTH - 20, DESKTOP_HEIGHT - 20, ("SerienRecorder InfoText"),
		                DESKTOP_WIDTH - 30, DESKTOP_HEIGHT - 80,
						BUTTON_X + 50, BUTTON_Y,
						BUTTON_X + 100, BUTTON_Y, BUTTON_X - 100,
						50, BUTTON_Y,
						100, BUTTON_Y, BUTTON_X - 100,
						)

	def __init__(self, session):
		self.session = session
		self.serienRecInfoFilePath = "/usr/lib/enigma2/python/Plugins/Extensions/SerienRecorder/StartupInfoText"

		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
		}, -1)

		self['srlog'] = ScrollLabel()
		self['text_ok'] = Label(("Exit und nicht mehr anzeigen"))
		self['text_exit'] = Label(("Exit"))

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		sl = self['srlog']
		sl.instance.setZPosition(5)

		text = ""
		if fileExists(self.serienRecInfoFilePath):
			readFile = open(self.serienRecInfoFilePath, "r")
			text = readFile.read()
			readFile.close()
		self['srlog'].setText(text)

	def keyLeft(self):
		self['srlog'].pageUp()

	def keyRight(self):
		self['srlog'].pageDown()

	def keyDown(self):
		self['srlog'].pageDown()

	def keyUp(self):
		self['srlog'].pageUp()

	def keyOK(self):
		config.plugins.serienRec.showStartupInfoText.value = False
		config.plugins.serienRec.showStartupInfoText.save()
		configfile.save()
		self.close()

	def keyCancel(self):
		self.close()