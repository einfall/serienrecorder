# coding=utf-8

# This file contains the SerienRecoder Season Begin Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config

from enigma import ePicLoad, eTimer, loadPNG, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor

import SerienRecorder
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, skinFactor
from SerienRecorderHelpers import PiconLoader, isDreamOS, PicLoader
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderDatabase import SRDatabase
import threading, time

class downloadSeasonBegins(threading.Thread):
	def __init__ (self, webChannels):
		threading.Thread.__init__(self)
		self.webChannels = webChannels
		self.transmissions = None
	def run(self):
		try:
			self.transmissions = SeriesServer().doGetSeasonBegins(self.webChannels)
		except:
			self.transmissions = None

	def getData(self):
		return self.transmissions

class serienRecShowSeasonBegins(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.modus = "menu_list"
		self.session = session
		self.picload = ePicLoad()
		self.ErrorMsg = "unbekannt"
		self.piconLoader = PiconLoader()
		self.picloader = None
		self.filter = False
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		self.changesMade = False

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"yellow": (self.keyYellow, "Zeige nur Serien-Starts"),
			"startTeletext": (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.timer_default = eTimer()
		if isDreamOS():
			self.timer_default_conn = self.timer_default.timeout.connect(self.readProposal)
		else:
			self.timer_default.callback.append(self.readProposal)

		self.proposalList = []
		self.transmissions = {}
		self.serviceRefs = self.database.getActiveServiceRefs()
		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.__onLayoutFinish)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_ok'].setText("Marker hinzufügen")
		self['text_yellow'].setText("Zeige Serienstarts")

		self.num_bt_text[3][0] = buttonText_na
		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		super(self.__class__, self).setupSkin()
		self[self.modus].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()
			self['text_6'].show()
			self['text_7'].show()
			self['text_8'].show()
			self['text_9'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def __onLayoutFinish(self):
		self['title'].setText("Lade neue Serien/Staffeln...")
		self.timer_default.start(0)

	def readProposal(self):
		self.timer_default.stop()

		webChannels = self.database.getActiveChannels()
		self.proposalList = []

		transmissionResults = downloadSeasonBegins(webChannels)
		transmissionResults.start()
		transmissionResults.join()

		if not transmissionResults.getData():
			print "[SerienRecorder]: Abfrage beim SerienServer doGetSeasonBegins() fehlgeschlagen"
		else:
			self.transmissions = transmissionResults.getData()
			self.buildProposalList()

	def buildProposalList(self):
		markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)

		self.proposalList = []

		if self.filter:
			self['text_yellow'].setText("Serien-/Staffelstarts")
		else:
			self['text_yellow'].setText("Zeige Serienstarts")

		for event in self.transmissions['events']:
			if self.filter and str(event['season']).isdigit() and int(event['season']) > 1:
				continue

			seriesName = event['name'].encode('utf-8')
			seriesID = int(event['id'])

			# marker flags: 0 = no marker, 1 = active marker, 2 = inactive marker
			markerFlag = 0
			if seriesID in markers:
				markerFlag = 1 if markers[seriesID] else 2

			self.proposalList.append([seriesName, event['season'], event['channel'].encode('utf-8'), event['start'], event['id'], markerFlag])

		if self.filter:
			self['title'].setText("%d neue Serien gefunden:" % len(self.proposalList))
		else:
			self['title'].setText("%d neue Serien/Staffeln gefunden:" % len(self.proposalList))

		self.chooseMenuList.setList(map(self.buildList, self.proposalList))
		if self['menu_list'].getCurrent():
			serien_name = self[self.modus].getCurrent()[0][0]
			serien_id = self[self.modus].getCurrent()[0][4]
			SerienRecorder.getCover(self, serien_name, serien_id)

	def buildList(self, entry):
		(Serie, Staffel, Sender, UTCTime, ID, MarkerFlag) = entry

		icon = imageNone = "%simages/black.png" % SerienRecorder.serienRecMainPath
		imageNeu = "%simages/neu.png" % SerienRecorder.serienRecMainPath

		if MarkerFlag == 1:
			setFarbe = parseColor('green').argb()
		elif MarkerFlag == 2:
			setFarbe = parseColor('red').argb()
		else:
			setFarbe = parseColor('foreground').argb()

		if str(Staffel).isdigit() and int(Staffel) == 1:
			icon = imageNeu

		foregroundColor = parseColor('foreground').argb()

		Staffel = "Staffel %s" % str(Staffel)
		WochenTag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		xtime = time.strftime(WochenTag[time.localtime(int(UTCTime)).tm_wday]+ ", %d.%m.%Y", time.localtime(int(UTCTime)))

		if config.plugins.serienRec.showPicons.value != "0":
			picon = loadPNG(imageNone)
			if Sender and self.serviceRefs.get(Sender):
				# Get picon by reference or by name
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(Sender)[0] if config.plugins.serienRec.showPicons.value == "1" else self.serviceRefs.get(Sender)[1])
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 5, 80 * skinFactor, 40 * skinFactor, picon),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340 * skinFactor, 15 * skinFactor, 30
					 * skinFactor, 30 * skinFactor, loadPNG(icon)),
					(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender, foregroundColor, foregroundColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime),
					(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
					(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel)
					]
		else:
			return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 15 * skinFactor, 30 * skinFactor, 30
					 * skinFactor, loadPNG(icon)),
					(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender, foregroundColor, foregroundColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime),
					(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
					(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel)
					]

	def serieInfo(self):
		check = self[self.modus].getCurrent()
		if check is None:
			return
		serien_id = self[self.modus].getCurrent()[0][4]
		if serien_id > 0:
			serien_name = self[self.modus].getCurrent()[0][0]
			from SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_id)

	def wunschliste(self):
		serien_id = self[self.modus].getCurrent()[0][4]
		super(self.__class__, self).wunschliste(serien_id)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def keyOK(self):
		check = self[self.modus].getCurrent()
		if check is None:
			print "[SerienRecorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, UTCTime, ID, MarkerFlag) = self[self.modus].getCurrent()[0]
			(existingID, AbStaffel, AlleSender) = self.database.getMarkerSeasonAndChannelSettings(Serie)
			if existingID > 0:
				# Add season and channel of selected series to marker
				self.database.updateMarkerSeasonAndChannelSettings(existingID, AbStaffel, Staffel, AlleSender, Sender)
				# Activate marker
				self.database.setMarkerStatus(Serie, config.plugins.serienRec.BoxID.value, True)
			else:
				if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
					boxID = config.plugins.serienRec.BoxID.value
				else:
					boxID = None
				self.database.addMarker(str(ID), Serie, "", boxID, 0)

			if config.plugins.serienRec.openMarkerScreen.value:
				from SerienRecorderMarkerScreen import serienRecMarker
				self.session.open(serienRecMarker, Serie)

			self.changesMade = True
			self.buildProposalList()
			self.chooseMenuList.setList(map(self.buildList, self.proposalList))

	def keyYellow(self):
		if self.filter:
			self.filter = False
		else:
			self.filter = True
		self.buildProposalList()

	def keyLeft(self):
		self[self.modus].pageUp()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_id = self[self.modus].getCurrent()[0][4]
		SerienRecorder.getCover(self, serien_name, serien_id)

	def keyRight(self):
		self[self.modus].pageDown()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_id = self[self.modus].getCurrent()[0][4]
		SerienRecorder.getCover(self, serien_name, serien_id)

	def keyDown(self):
		self[self.modus].down()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_id = self[self.modus].getCurrent()[0][4]
		SerienRecorder.getCover(self, serien_name, serien_id)

	def keyUp(self):
		self[self.modus].up()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_id = self[self.modus].getCurrent()[0][4]
		SerienRecorder.getCover(self, serien_name, serien_id)

	def __onClose(self):
		self.stopDisplayTimer()
