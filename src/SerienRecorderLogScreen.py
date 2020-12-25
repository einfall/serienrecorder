# coding=utf-8

# This file contains the SerienRecoder Log Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config
from Tools.Directories import fileExists

from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_WRAP, RT_VALIGN_CENTER

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderLogWriter import SRLogger
import os

class serienRecReadLog(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)

		self.displayTimer = None
		self.displayTimer_conn = None
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"3"	: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"red"   : (self.keyRed, "zurück zur vorherigen Ansicht"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		self.onLayoutFinish.append(self.readLog)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Schließen")
		self.num_bt_text[0][0] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		if config.plugins.serienRec.logWrapAround.value:
			self.chooseMenuList.l.setItemHeight(int(70 *skinFactor))
		else:
			self.chooseMenuList.l.setItemHeight(int(25 *skinFactor))
		self['log'] = self.chooseMenuList
		self['log'].show()
		self['video'].hide()
		self['cover'].hide()

		self['title'].setText("Lese LogFile: (%s)" % SRLogger.getLogFilePath())

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_exit'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def readLog(self):
		logFilePath = SRLogger.getLogFilePath()
		if not fileExists(logFilePath):
			open(logFilePath, 'w').close()

		logFileSize = os.path.getsize(logFilePath)
		if not logFileSize == 0:
			readLog = open(logFilePath, "r")
			logliste = []
			for zeile in readLog.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					logliste.append(zeile)
			readLog.close()
			self['title'].hide()
			self['path'].setText("LogFile:\n(%s)" % logFilePath)
			self['path'].show()
			self.chooseMenuList.setList(list(map(self.buildList, logliste)))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(logliste)
				if count != 0:
					self['log'].moveToIndex(int(count -1))

	@staticmethod
	def buildList(entry):
		(zeile) = entry
		width = 850
		if config.plugins.serienRec.SkinType.value == "":
			width = 1240

		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, width * skinFactor, 65 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 00, 2 * skinFactor, width * skinFactor, 20 * skinFactor, 0,
			RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]

	def keyLeft(self):
		self['log'].pageUp()

	def keyRight(self):
		self['log'].pageDown()

	def keyDown(self):
		self['log'].down()

	def keyUp(self):
		self['log'].up()

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		self.close()

	def keyRed(self):
		self.close()
