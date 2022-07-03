# coding=utf-8

# This file contains the SerienRecoder Season Begin Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config

from enigma import ePicLoad, eTimer, loadPNG, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, skinFactor
from .SerienRecorderHelpers import PiconLoader, isDreamOS, PicLoader, toStr
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorder import getDataBaseFilePath, getCover
import time, os

class serienRecShowSeasonBegins(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.modus = "menu_list"
		self.session = session
		self.picload = ePicLoad()
		self.piconLoader = PiconLoader()
		self.picloader = None
		self.filter = False
		self.channelFilter = True
		self.database = SRDatabase(getDataBaseFilePath())
		self.changesMade = False

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "Zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"yellow": (self.keyYellow, "Umschalten zwischen 'Nur Serienstarts' und 'Serien- und Staffelstarts'"),
			"blue": (self.keyBlue, "Umschalten zwischen 'Alle Sender' und 'Zugewiesene Sender'"),
			"startTeletext": (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"	    : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"2"		: (self.changeTVDBID, "TVDB-ID ändern"),
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

		self.proposalList = []
		self.transmissions = {}
		self.serviceRefs = self.database.getActiveServiceRefs()
		self.webChannels = self.database.getActiveChannels()
		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.readProposal)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_ok'].setText("Marker hinzufügen")
		self['text_yellow'].setText("Zeige Serienstarts")
		self['text_blue'].setText("Alle Sender")

		self.num_bt_text[2][0] = "TVDB-ID ändern"
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
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
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

	def getCurrentSelection(self):
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_alias = self[self.modus].getCurrent()[0][8]
		serien_wlid = self[self.modus].getCurrent()[0][4]
		serien_fsid = self[self.modus].getCurrent()[0][6]
		return serien_name, serien_alias, serien_wlid, serien_fsid

	def changeTVDBID(self):
		from .SerienRecorderScreenHelpers import EditTVDBID
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		editTVDBID = EditTVDBID(self, self.session, serien_name, serien_alias, serien_wlid, serien_fsid)
		editTVDBID.changeTVDBID()

	def readProposal(self):
		self['title'].setText("Lade neue Serien/Staffeln...")
		self.transmissions = {}

		def downloadSeasonBegins():
			print("[SerienRecorder] downloadSeasonBegins")
			channels = self.webChannels
			if not self.channelFilter:
				channels = []

			return SeriesServer().doGetSeasonBegins(channels)

		def onDownloadSeasonBeginsSuccessful(result):
			print("[SerienRecorder] onDownloadSeasonBeginsSuccessful")
			if result:
				self.transmissions = result
				self.buildProposalList()

		def onDownloadSeasonBeginsFailed():
			print("[SerienRecorder]: Abfrage beim SerienServer doGetSeasonBegins() fehlgeschlagen")

		import twisted.python.runtime
		if twisted.python.runtime.platform.supportsThreads():
			from twisted.internet.threads import deferToThread
			deferToThread(downloadSeasonBegins).addCallback(onDownloadSeasonBeginsSuccessful).addErrback(onDownloadSeasonBeginsFailed)
		else:
			try:
				result = downloadSeasonBegins()
				onDownloadSeasonBeginsSuccessful(result)
			except:
				onDownloadSeasonBeginsFailed()

	def buildProposalList(self):
		markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)
		self.proposalList = []

		if self.filter:
			self['text_yellow'].setText("Serien-/Staffelstarts")
		else:
			self['text_yellow'].setText("Zeige Serienstarts")

		if self.channelFilter:
			self['text_blue'].setText("Alle Sender")
		else:
			self['text_blue'].setText("Zugewiesene Sender")

		for event in self.transmissions['events']:
			if self.filter and str(event['season']).isdigit() and int(event['season']) > 1:
				continue

			series_name = toStr(event['name'])
			series_fsid = event['fs_id']

			# marker flags: 0 = no marker, 1 = active marker, 2 = inactive marker
			marker_flag = 0
			if series_fsid in markers:
				marker_flag = 1 if markers[series_fsid] else 2

			self.proposalList.append([series_name, event['season'], toStr(event['channel']), event['start'], event['id'], marker_flag, series_fsid, toStr(event['info']), toStr(event['subtitle'])])

		if self.filter:
			self['title'].setText("%d neue Serien gefunden:" % len(self.proposalList))
		else:
			self['title'].setText("%d neue Serien/Staffeln gefunden:" % len(self.proposalList))

		self.chooseMenuList.setList(list(map(self.buildList, self.proposalList)))
		self['menu_list'].moveToIndex(0)
		if self['menu_list'].getCurrent():
			(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
			getCover(self, serien_name, serien_fsid)

	def buildList(self, entry):
		(series, season, channel, utc_time, ID, marker_flag, fs_id, info, alias) = entry

		serienRecMainPath = os.path.dirname(__file__)
		icon = imageNone = "%s/images/black.png" % serienRecMainPath
		imageNeu = "%s/images/neu.png" % serienRecMainPath

		if marker_flag == 1:
			seriesColor = parseColor('green').argb()
		elif marker_flag == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None

		if str(season).isdigit() and int(season) == 1:
			icon = imageNeu

		foregroundColor = parseColor('foreground').argb()

		season = "Staffel %s" % str(season)
		weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		xtime = time.strftime(weekdays[time.localtime(int(utc_time)).tm_wday]+ ", %d.%m.%Y", time.localtime(int(utc_time)))

		if config.plugins.serienRec.showPicons.value != "0":
			picon = loadPNG(imageNone)
			if channel and self.serviceRefs.get(channel):
				# Get picon by reference or by name
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(channel)[0] if config.plugins.serienRec.showPicons.value == "1" else self.serviceRefs.get(channel)[1])
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10 * skinFactor, 5 * skinFactor, 80 * skinFactor, 40 * skinFactor, picon),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340 * skinFactor, 15 * skinFactor, 30
					 * skinFactor, 30 * skinFactor, loadPNG(icon)),
					(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 3, 230 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, channel),
					(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, series, seriesColor, seriesColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, season, foregroundColor, foregroundColor)
					]
		else:
			return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15 * skinFactor, 15 * skinFactor, 27 * skinFactor, 17
					 * skinFactor, loadPNG(icon)),
					(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 3, 230 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, channel),
					(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
					 RT_HALIGN_LEFT | RT_VALIGN_CENTER, series, seriesColor, seriesColor),
					(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18
					 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, season, foregroundColor, foregroundColor)
					]

	def serieInfo(self):
		if self[self.modus].getCurrent() is None:
			return
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_wlid > 0:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_wlid, serien_fsid)

	def wunschliste(self):
		if self[self.modus].getCurrent() is None:
			return
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		super(self.__class__, self).wunschliste(serien_fsid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def keyOK(self):
		if self[self.modus].getCurrent() is None:
			return
		else:
			(serien_name, serien_staffel, serien_sender, serien_startzeit, serien_wlid, serien_markerFlag, serien_fsid, serien_info, serien_alias) = self[self.modus].getCurrent()[0]
			(existingID, from_season, all_channels) = self.database.getMarkerSeasonAndChannelSettings(serien_fsid)
			if existingID > 0:
				# Add season and channel of selected series to marker
				self.database.updateMarkerSeasonAndChannelSettings(existingID, from_season, serien_staffel, all_channels, serien_sender)
				# Activate marker
				self.database.setMarkerStatus(existingID, config.plugins.serienRec.BoxID.value, True)
			else:
				if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
					boxID = config.plugins.serienRec.BoxID.value
				else:
					boxID = None
				self.database.addMarker(str(serien_wlid), serien_name, serien_info, serien_fsid, boxID, 0)

				from .SerienRecorderLogWriter import SRLogger
				SRLogger.writeLog("Ein Serien-Marker für '%s (%s)' wurde angelegt" % (serien_name, serien_info), True)
				self['title'].setText("Marker '%s (%s)' wurde angelegt." % (serien_name, serien_info))

				from .SerienRecorder import getCover
				getCover(self, serien_name, serien_fsid, False, True)

			if config.plugins.serienRec.openMarkerScreen.value:
				from .SerienRecorderMarkerScreen import serienRecMarker
				self.session.open(serienRecMarker, serien_fsid)

			selectedIndex = self[self.modus].getSelectedIndex()
			self.changesMade = True
			self.buildProposalList()
			self.chooseMenuList.setList(list(map(self.buildList, self.proposalList)))
			self[self.modus].moveToIndex(selectedIndex)

	def keyYellow(self):
		if self.filter:
			self.filter = False
		else:
			self.filter = True
		self.buildProposalList()

	def keyBlue(self):
		self.proposalList = []
		self.chooseMenuList.setList(list(map(self.buildList, self.proposalList)))

		if self.channelFilter:
			self.channelFilter = False
		else:
			self.channelFilter = True
		self.readProposal()

	def keyLeft(self):
		self[self.modus].pageUp()
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		getCover(self, serien_name, serien_fsid)

	def keyRight(self):
		self[self.modus].pageDown()
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		getCover(self, serien_name, serien_fsid)

	def keyDown(self):
		self[self.modus].down()
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		getCover(self, serien_name, serien_fsid)

	def keyUp(self):
		self[self.modus].up()
		(serien_name, serien_alias, serien_wlid, serien_fsid) = self.getCurrentSelection()
		getCover(self, serien_name, serien_fsid)

	def __onClose(self):
		self.stopDisplayTimer()
