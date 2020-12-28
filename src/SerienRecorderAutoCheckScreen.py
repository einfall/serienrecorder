# coding=utf-8

# This file contains the SerienRecoder AutoCheck Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Components.Label import Label
from Components.ProgressBar import ProgressBar

from enigma import eTimer, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, RT_WRAP, getDesktop

from .SerienRecorderCheckForRecording import checkForRecordingInstance
from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderHelpers import isDreamOS

class serienRecNewRunAutoCheckScreen(Screen):
	DESKTOP_WIDTH = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	screenWidth = 600
	screenHeight = 120
	if DESKTOP_WIDTH > 1280:
		factor = 1.5
		screenWidth *= factor
		screenHeight *= factor

	skin = """
			<screen name="SerienRecorderAutoCheck" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
				<widget name="headline" position="10,20" size="%d,40" foregroundColor="#00ff4a3c" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
				<widget name="progressslider" position="10,75" size="%d,25" borderWidth="1" zPosition="1" backgroundColor="#00242424"/>
			</screen>""" % ((DESKTOP_WIDTH - screenWidth) / 2, (DESKTOP_HEIGHT - screenHeight) / 2, screenWidth, screenHeight, "SerienRecorder Timer-Suchlauf", screenWidth - 20, screenWidth - 20)

	def __init__(self, session, version):
		self.session = session
		self.version = version
		Screen.__init__(self, session)

		self['headline'] = Label("")
		self['progressslider'] = ProgressBar()

		self["actions"] = ActionMap(["SerienRecorderActions", ], {
			"ok": self.keyExit,
			"cancel": self.keyExit,
		}, -1)

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		self['headline'].setText("Timer-Suchlauf wird ausgeführt - bitte warten...")
		self['progressslider'].setValue(-1)


	def keyExit(self):
		self.close()


class serienRecRunAutoCheckScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, withTVPlanner=False):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.withTVPlanner = withTVPlanner
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
		self.onFirstExecBegin.append(self.askForExecute)
		#self.onLayoutFinish.append(self.startCheck)
		#self.onLayoutFinish.append(self.readLog)
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

		self['title'].setText("Suche nach neuen Timern läuft...")
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
		# if result[1]:
		# 	self.startCheck()

	def askForExecute(self):
		if config.plugins.serienRec.tvplaner.value:
			self.session.openWithCallback(self.executeAutoCheck, MessageBox, "Bei 'ja' wird der Suchlauf für TV-Planer Timer gestartet, bei 'nein' wird ein voller Suchlauf durchgeführt.", MessageBox.TYPE_YESNO)
		else:
			self.session.openWithCallback(self.executeFullAutoCheck, MessageBox, "Soll ein Suchlauf für Timer gestartet werden?", MessageBox.TYPE_YESNO)

	def executeAutoCheck(self, withTVPlaner):
		print("[SerienRecorder] ExecuteAutocCheck: %s" % str(withTVPlaner))
		self.withTVPlanner = withTVPlaner
		self.startCheck()

	def executeFullAutoCheck(self, execute):
		print("[SerienRecorder] ExecuteFullAutoCheck: %s" % str(execute))
		if execute:
			self.withTVPlanner = False
			self.startCheck()
		else:
			self.close()

	def startCheck(self):
		# Log Reload Timer
		print("[SerienRecorder] startCheck timer")
		checkForRecordingInstance.setAutoCheckFinished(False)
		self.autoCheckRunning = False
		if isDreamOS():
			self.readLogTimer_conn = self.readLogTimer.timeout.connect(self.readLog)
		else:
			self.readLogTimer.callback.append(self.readLog)
		self.readLogTimer.start(2000)

	def runAutoCheck(self):
		if not self.autoCheckRunning:
			self.autoCheckRunning = True
			checkForRecordingInstance.initialize(self.session, True, self.withTVPlanner)

	def readLog(self):
		print("[SerienRecorder] readLog called")
		if checkForRecordingInstance.isAutoCheckFinished():
			if self.readLogTimer:
				self.readLogTimer.stop()
				self.readLogTimer = None
			print("[SerienRecorder] update log reader stopped.")
			self['title'].setText("Timer-Suchlauf abgeschlossen")

			from .SerienRecorderLogWriter import SRLogger
			logFileHandle = open(SRLogger.getLogFilePath(), "r")
			for zeile in logFileHandle.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					self.logliste.append(zeile)
			logFileHandle.close()
			self.chooseMenuList.setList(list(map(self.buildList, self.logliste)))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self['log'].moveToIndex(int(count - 1))
			self.autoCheckRunning = False
		else:
			print("[SerienRecorder] waiting")
			self.points += " ."
			self['title'].setText("Suche nach neuen Timern läuft.%s" % self.points)
			self.runAutoCheck()

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
		self.close(True)
