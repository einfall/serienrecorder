# coding=utf-8

# This file contains the SerienRecoder Splash Screen
# which is appreciation of Wunschliste (http://www.wunschliste.de)
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label

from enigma import getDesktop

class ShowSplashScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderSplash" position="%d,%d" size="416,250" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
			<widget name="srlog" position="135,50" size="250,30" font="Regular;18" valign="center" halign="left" foregroundColor="#FFFFFF" transparent="1" zPosition="5"/>
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/splashscreen.png" position="5,5" zPosition="1" size="406,240" alphatest="on" />
		</screen>""" % ((DESKTOP_WIDTH - 416) / 2, (DESKTOP_HEIGHT - 250) / 2, ("SerienRecorder Splashscreen"))

	def __init__(self, session, version):
		self.session = session
		self.version = version
		Screen.__init__(self, session)

		self['srlog'] = Label()

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyExit,
			"cancel": self.keyExit,
		}, -1)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		sl = self['srlog']
		sl.instance.setZPosition(5)

		text = "Version %s" % self.version
		self['srlog'].setText(text)

	def keyExit(self):
		self.close()
