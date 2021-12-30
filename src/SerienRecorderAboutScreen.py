# coding=utf-8

# This file contains the SerienRecoder About Screen
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import config

from enigma import getDesktop

class serienRecAboutScreen(Screen, ConfigListScreen):
	DESKTOP_WIDTH       = getDesktop(0).size().width()
	DESKTOP_HEIGHT      = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderAbout" position="%d,%d" size="650,400" title="%s" >
			<widget name="pluginInfo" position="5,5" size="640,390" valign="center" halign="center" zPosition="5" transparent="1" foregroundColor="#FFFFFF" font="Regular;18"/>
		</screen>""" % ((DESKTOP_WIDTH - 650) / 2, (DESKTOP_HEIGHT - 400) / 2, ("Über SerienRecorder"))

	def __init__(self,session):
		self.session = session
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions"], dict(cancel=self.exit, ok=self.exit), -1)

		self.info =("SerienRecorder für enigma2 (Version %s)\n"
		            "(c) 2014-2022 by einfall, w22754, egn und MacDisein\n"
					"\n"
					"For more info:\n"
					"https://tinyurl.com/yblfjmhr\n"
					"\n"
					"Wenn das Plugin gefällt, würden wir uns über eine Spende freuen:\n"
					"@einfall: Ein PN schicken für den Amazon Wunschzettel,\n"
		            "@MacDisein: PayPal an macdisein@gmx.de\n\n"
		            "Mit Unterstützung und Genehmigung zur Verwendung der Daten von\n"
		            "Wunschliste.de - http://www.wunschliste.de") % config.plugins.serienRec.showversion.value

		self["pluginInfo"] = Label(self.info)

	def exit(self):
		self.close()
