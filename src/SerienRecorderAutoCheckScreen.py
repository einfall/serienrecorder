# coding=utf-8

# This file contains the SerienRecoder AutoCheck Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config

from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_WRAP

import SerienRecorder
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from SerienRecorderHelpers import isDreamOS

class serienRecRunAutoCheckScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, withTVPlanner=False):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.withTVPlanner = withTVPlanner
		print "[SerienRecorder] 0__init__ withTVPlanner:", withTVPlanner
		self.autoCheckRunning = False

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"3"	: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		self.logliste = []
		self.points = ""

		self.readLogTimer = eTimer()
		self.readLogTimer_conn = None

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.startCheck)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Abbrechen")
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

		self['title'].setText("Suche nach neuen Timern läuft.")
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

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.startCheck()

	def startCheck(self):
		# Log Reload Timer
		print "[SerienRecorder] startCheck timer"
		SerienRecorder.autoCheckFinished = False
		self.autoCheckRunning = False
		if isDreamOS():
			self.readLogTimer_conn = self.readLogTimer.timeout.connect(self.readLog)
		else:
			self.readLogTimer.callback.append(self.readLog)
		self.readLogTimer.start(2500)

	def executeAutoCheck(self):
		if not self.autoCheckRunning:
			self.autoCheckRunning = True
			SerienRecorder.serienRecCheckForRecording(self.session, True, self.withTVPlanner)

	def readLog(self):
		print "[SerienRecorder] readLog called"
		if SerienRecorder.autoCheckFinished:
			if self.readLogTimer:
				self.readLogTimer.stop()
				self.readLogTimer = None
			print "[SerienRecorder] update log reader stopped."
			self['title'].setText("Auto-Check fertig !")

			from SerienRecorderLogWriter import SRLogger
			logFileHandle = open(SRLogger.getLogFilePath(), "r")
			for zeile in logFileHandle.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					self.logliste.append(zeile)
			logFileHandle.close()
			self.chooseMenuList.setList(map(self.buildList, self.logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self['log'].moveToIndex(int(count - 1))
			SerienRecorder.autoCheckRunning = False
		else:
			print "[SerienRecorder] waiting"
			self.points += " ."
			self['title'].setText("Suche nach neuen Timern läuft.%s" % self.points)
			self.executeAutoCheck()

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

	def pageUp(self):
		self['log'].pageUp()

	def pageDown(self):
		self['log'].pageDown()

	def __onClose(self):
		if self.readLogTimer:
			self.readLogTimer.stop()
			self.readLogTimer = None
			self.readLogTimer_conn = None

		self.stopDisplayTimer()

	def keyCancel(self):
		if SerienRecorder.autoCheckFinished:
			self.close(config.plugins.serienRec.refreshViews.value)
