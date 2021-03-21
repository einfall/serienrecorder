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

	screenWidth = 416
	screenHeight = 250
	imageWidth = 406
	imageHeigt = 240
	imagePath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/splashscreen.png"
	versionPosX = 130
	versionPosY = 55
	versionHeight = 30
	versionFontSize = 18
	copyrightPosX = 10
	copyrightPosY = 95
	copyrightHeight = 30
	copyrightFontSize = 14
	if DESKTOP_WIDTH > 1280:
		factor = 1.5
		screenWidth *= factor
		screenHeight *= factor
		imageWidth *= factor
		imageHeigt *= factor
		imagePath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/splashscreen_x15.png"
		versionPosX *= factor
		versionPosY *= factor
		versionHeight *= factor
		versionFontSize *= factor
		copyrightPosX *= factor
		copyrightPosY *= factor
		copyrightHeight *= factor
		copyrightFontSize *= factor

	skin = """
		<screen name="SerienRecorderSplash" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
			<widget name="version" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" halign="left" foregroundColor="#FFFFFF" transparent="1" zPosition="5"/>
			<widget name="copyright" position="%d,%d" size="%d,%d" font="Regular;%d" valign="center" halign="left" foregroundColor="#FFFFFF" transparent="1" zPosition="5"/>
			<ePixmap pixmap="%s" position="5,5" zPosition="1" size="%d,%d" alphatest="on" />
		</screen>""" % ((DESKTOP_WIDTH - screenWidth) / 2, (DESKTOP_HEIGHT - screenHeight) / 2, screenWidth, screenHeight, "SerienRecorder Splashscreen",
	                    versionPosX, versionPosY, screenWidth, versionHeight, versionFontSize,
	                    copyrightPosX, copyrightPosY, screenWidth, copyrightHeight, copyrightFontSize,
	                    imagePath, imageWidth, imageHeigt)

	def __init__(self, session):
		self.session = session
		Screen.__init__(self, session)

		self['version'] = Label()
		self['copyright'] = Label()

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyExit,
			"cancel": self.keyExit,
		}, -1)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		self['version'].instance.setZPosition(5)
		self['copyright'].instance.setZPosition(5)

		from .SerienRecorderHelpers import SRVERSION
		self['version'].setText("Version %s" % SRVERSION)
		self['copyright'].setText("©2014-21 einfall, w22754, egn und MacDisein")

	def keyExit(self):
		self.close()
