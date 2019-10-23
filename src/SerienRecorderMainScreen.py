# coding=utf-8

# This file contains the SerienRecoder Main Screen
import os, datetime, time


from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Tools.Directories import fileExists

from enigma import eTimer, ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, loadPNG
from skin import parseColor

import SerienRecorder
from SerienRecorderScreenHelpers import serienRecBaseScreen, updateMenuKeys, InitSkin, skinFactor
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderHelpers import isDreamOS, PiconLoader, TimeHelpers, STBHelpers, PicLoader, getDirname
from SerienRecorderDatabase import SRDatabase
from SerienRecorderLogWriter import SRLogger
from SerienRecorderSeriesPlanner import serienRecSeriesPlanner

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

showMainScreen = False

class serienRecMainScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.picloader = None
		self.ErrorMsg = "unbekannt"
		self.skin = None
		self.chooseMenuList = None
		self.chooseMenuList_popup = None
		self.popup_list = []
		self.piconLoader = PiconLoader()
		self.database = None
		self.singleTimer_conn = None
		self.displayTimer_conn = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "SerienRecorder beenden"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "Anzeige-Modus auswählen"),
			"green"	: (self.keyGreen, "Ansicht Sender-Zuordnung öffnen"),
			"yellow": (self.keyYellow, "Ansicht Serien-Marker öffnen"),
			"blue"	: (self.keyBlue, "Ansicht Timer-Liste öffnen"),
			"info" 	: (self.keyCheck, "Suchlauf für Timer starten"),
			"menu"	: (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"nextBouquet" : (self.nextPage, "Serienplaner des nächsten Tages laden"),
			"prevBouquet" : (self.backPage, "Serienplaner des vorherigen Tages laden"),
			"startTeletext"  : (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"1"		: (self.searchSeries, "Serie manuell suchen"),
			"2"	    : (self.changeTVDBID, "TVDB-ID ändern"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"5"		: (self.imapTest, "IMAP Test"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"8"		: (self.reloadSerienplaner, "Serienplaner neu laden"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		SerienRecorder.ReadConfigFile()

		if not os.path.exists(config.plugins.serienRec.piconPath.value):
			config.plugins.serienRec.showPicons.value = False

		self.setupSkin()

		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
		elif config.plugins.serienRec.updateInterval.value == 0:
			config.plugins.serienRec.timeUpdate.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False

		global showMainScreen
		if config.plugins.serienRec.firstscreen.value == "0":
			showMainScreen = True
		else:
			showMainScreen = False

		self.pRegional = 0
		self.pPaytv = 1
		self.pPrime = 1
		self.page = 0
		self.modus = "list"
		self.loading = True
		self.daylist = [[]]
		self.displayTimer = None
		self.displayMode = 1
		self.serviceRefs = None

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onClose.append(self.__onClose)

		self.onFirstExecBegin.append(self.showSplashScreen)
		self.onFirstExecBegin.append(self.checkForUpdate)

		if config.plugins.serienRec.showStartupInfoText.value:
			if fileExists("%sStartupInfoText" % SerienRecorder.serienRecMainPath):
				self.onFirstExecBegin.append(self.showInfoText)
			else:
				self.onFirstExecBegin.append(self.startScreen)
		else:
			self.onFirstExecBegin.append(self.startScreen)

	def imapTest(self):
		from SerienRecorderTVPlaner import imaptest
		imaptest(self.session)

	def showInfoText(self):
		from SerienRecorderStartupInfoScreen import ShowStartupInfo
		self.session.openWithCallback(self.startScreen, ShowStartupInfo)

	def showSplashScreen(self):
		from SerienRecorderSplashScreen import ShowSplashScreen
		self.session.openWithCallback(self.checkForUpdate, ShowSplashScreen, config.plugins.serienRec.showversion.value)

	def checkForUpdate(self):
		if config.plugins.serienRec.Autoupdate.value:
			from SerienRecorderUpdateScreen import checkGitHubUpdate
			checkGitHubUpdate(self.session).checkForUpdate()

		self.startScreen()

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Anzeige-Modus")
		self['text_green'].setText("Sender zuordnen")
		self['text_ok'].setText("Marker hinzufügen")
		self['text_yellow'].setText("Serien Marker")
		self['text_blue'].setText("Timer-Liste")
		self.num_bt_text[0][1] = "IMAP-Test"
		self.num_bt_text[1][0] = "Serie suchen"
		self.num_bt_text[2][0] = "TVDB-ID ändern"
		self.num_bt_text[2][2] = "Timer suchen"
		self.num_bt_text[3][1] = "Neu laden"

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50 * skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(30 * skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['title'].setText("Lade infos from Web...")

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_epg'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def test(self):
		i = 0

	def changeTVDBID(self):
		from SerienRecorderScreenHelpers import EditTVDBID
		(serien_name, serien_id) = self.getSeriesNameID()
		editTVDBID = EditTVDBID(self, self.session, serien_name, serien_id)
		editTVDBID.changeTVDBID()

	def reloadSerienplaner(self):
		# lt = datetime.datetime.now()
		# lt += datetime.timedelta(days=self.page)
		# key = time.strftime('%d.%m.%Y', lt.timetuple())
		# cache = serienRecMainScreen.loadPlanerData(config.plugins.serienRec.screenplaner.value)
		# if key in cache:
		# 	del cache[key]
		self.readPlanerData(True)

	def readLogFile(self):
		from SerienRecorderLogScreen import serienRecReadLog
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		from SerienRecorderSeasonBeginsScreen import serienRecShowSeasonBegins
		self.session.openWithCallback(self.readPlanerData, serienRecShowSeasonBegins)

	def searchSeries(self):
		if self.modus == "list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			from SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecSearchResultScreen, serien_name)

	def handleSeriesSearchEnd(self, serien_name=None):
		if serien_name:
			from SerienRecorderMarkerScreen import serienRecMarker
			self.session.openWithCallback(self.readPlanerData, serienRecMarker, serien_name)
		else:
			self.readPlanerData(False)

	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		(serien_name, serien_id) = self.getSeriesNameID()
		from SerienRecorderSeriesInfoScreen import serienRecShowInfo
		self.session.open(serienRecShowInfo, serien_name, serien_id)

	def wunschliste(self):
		(serien_name, serien_id) = self.getSeriesNameID()
		super(self.__class__, self).wunschliste(serien_id)

	def setHeadline(self):
		if int(config.plugins.serienRec.screenplaner.value) == 1:
			self['headline'].setText("Serien-Planer (Serien Tagesübersicht)")
			self['text_red'].setText("Top 30")
		elif int(config.plugins.serienRec.screenplaner.value) == 2:
			self['headline'].setText("Top 30 SerienRecorder Serien")
			self['text_red'].setText("Tagesübersicht")

		self['headline'].instance.setForegroundColor(parseColor("red"))

	def recSetup(self):
		from SerienRecorderSetupScreen import serienRecSetup
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readPlanerData()

	def startScreen(self):
		print "[SerienRecorder] version %s is running..." % config.plugins.serienRec.showversion.value

		if not SerienRecorder.refreshTimer:
			if config.plugins.serienRec.timeUpdate.value:
				SerienRecorder.serienRecCheckForRecording(self.session, False, False)

		if not SerienRecorder.initDB():
			print "[SerienRecorder] initDB failed"
			super(self.__class__, self).close()

		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		if not self.database.hasChannels():
			print "[SerienRecorder] Channellist is empty !"
			from SerienRecorderChannelScreen import serienRecMainChannelEdit
			self.session.openWithCallback(self.readPlanerData, serienRecMainChannelEdit)
		else:
			self.serviceRefs = self.database.getActiveServiceRefs()
			remoteChannelListLastUpdated = SeriesServer.getChannelListLastUpdate()
			channelListUpToDate = True
			if remoteChannelListLastUpdated:
				localChannelListLastUpdated = self.database.getChannelListLastUpdate()
				if 0 < localChannelListLastUpdated < remoteChannelListLastUpdated:
					SRLogger.writeLog("Auf dem Serien-Server wurde die Senderliste aktualisiert - bitte führen Sie auch eine Aktualisierung in der Senderzuordnung aus.", True)
					channelListUpToDate = False

			if channelListUpToDate:
				self.switchStartScreen()
			else:
				self.session.openWithCallback(self.handleChannelListUpdate, MessageBox, "Die Senderliste wurde auf dem Server aktualisiert.\nSie muss auch im SerienRecorder aktualisiert werden.\nWechseln Sie zur Senderzuordnung und aktualisieren Sie die Senderliste mit der grünen Taste.\n\nZur Senderzuordnung wechseln?", MessageBox.TYPE_YESNO)

	def handleChannelListUpdate(self, showChannelEdit=False):
		if showChannelEdit:
			from SerienRecorderChannelScreen import serienRecMainChannelEdit
			self.session.openWithCallback(self.switchStartScreen, serienRecMainChannelEdit)
		else:
			self.switchStartScreen()

	def switchStartScreen(self, unused=None):
		if not showMainScreen:
			from SerienRecorderMarkerScreen import serienRecMarker
			self.session.openWithCallback(self.readPlanerData, serienRecMarker)
		else:
			self.readPlanerData(False)

	def readPlanerData(self, answer=True):
		print "[SerienRecorder] readPlanerData"
		if not showMainScreen:
			self.keyCancel()
			self.close()
			return

		self.loading = True
		cache = serienRecSeriesPlanner.loadPlanerData(config.plugins.serienRec.screenplaner.value)

		if answer:
			cache.clear()

		self.setHeadline()
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		lt = datetime.datetime.now()
		if config.plugins.serienRec.screenplaner.value == 1:
			lt += datetime.timedelta(days=self.page)
		key = time.strftime('%d.%m.%Y', lt.timetuple())
		if key in cache:
			try:
				self['title'].setText("Lade Infos vom Speicher...")
				if config.plugins.serienRec.screenplaner.value == 1:
					self.processPlanerData(cache[key], True)
				else:
					self.processTopThirty(cache[key], True)
			except:
				SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der Daten\n", True)
		else:
			self['title'].setText("Lade Infos vom Web...")
			webChannels = self.database.getActiveChannels()
			try:
				if config.plugins.serienRec.screenplaner.value == 1:
					planerData = SeriesServer().doGetPlanerData(int(self.page), webChannels)
					self.processPlanerData(planerData, False)
				else:
					topThirtyData = SeriesServer().doGetTopThirty()
					self.processTopThirty(topThirtyData, False)
			except:
				SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der Daten\n", True)

	def processPlanerData(self, data, useCache=False):
		if not data or len(data) == 0:
			self['title'].setText("Fehler beim Abrufen der SerienPlaner-Daten")
			return
		if useCache:
			(headDate, self.daylist) = data
		else:
			self.daylist = [[]]
			headDate = [data["date"]]


			markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)
			timers = self.database.getTimer(self.page)

			for event in data["events"]:
				aufnahme = False
				serieAdded = 0
				start_h = event["time"][:+2]
				start_m = event["time"][+3:]
				start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, self.page)

				serien_name = event["name"].encode("utf-8")
				serien_name_lower = serien_name.lower()
				serien_id = int(event["id"])
				sender = event["channel"]
				title = event["title"].encode("utf-8")
				staffel = event["season"]
				episode = event["episode"]
				self.ErrorMsg = "%s - S%sE%s - %s (%s)" % \
				(serien_name, str(staffel).zfill(2), str(episode).zfill(2), title, sender)

				serienTimers = [timer for timer in timers if timer[0] == serien_name_lower]
				serienTimersOnChannel = [serienTimer for serienTimer in serienTimers if
				                         serienTimer[2] == sender.lower()]
				for serienTimerOnChannel in serienTimersOnChannel:
					if (int(serienTimerOnChannel[1]) >= (int(start_time) - 300)) and (
							int(serienTimerOnChannel[1]) < (int(start_time) + 300)):
						aufnahme = True

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				if serien_id in markers:
					serieAdded = 1 if markers[serien_id] else 2

				staffel = str(staffel).zfill(2)
				episode = str(episode).zfill(2)

				##############################
				#
				# CHECK
				#
				# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
				#
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name,
							                                                 False, title) > 0 and True or False
						else:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name,
							                                                 False) > 0 and True or False
					else:
						bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name,
						                                                 False) > 0 and True or False

				title = "%s - %s" % (seasonEpisodeString, title)
				regional = False
				paytv = False
				neu = event["new"]
				prime = False
				transmissionTime = event["time"]
				url = ''
				self.daylist[0].append((
				                       regional, paytv, neu, prime, transmissionTime, url, serien_name, sender, staffel,
				                       episode, title, aufnahme, serieAdded, bereits_vorhanden, serien_id))

			print "[SerienRecorder] Es wurden %s Serie(n) gefunden" % len(self.daylist[0])

			if headDate:
				d = headDate[0].split(',')
				d.reverse()
				key = d[0].strip()
				cache = serienRecSeriesPlanner.loadPlanerData(1)
				cache.update({key: (headDate, self.daylist)})
				if config.plugins.serienRec.planerCacheEnabled.value:
					serienRecSeriesPlanner.writePlanerData(1, cache)

		self.loading = False

		if len(self.daylist[0]) != 0:
			if headDate:
				self['title'].setText(
					"Es wurden für - %s - %s Serie(n) gefunden." % (headDate[0], len(self.daylist[0])))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			else:
				self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[0]))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.chooseMenuList.setList(map(self.buildPlanerList, self.daylist[0]))
			self.ErrorMsg = "'getCover()'"
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[0]))
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			print "[SerienRecorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
			self.chooseMenuList.setList(map(self.buildPlanerList, self.daylist[0]))

	def processTopThirty(self, data, useCache=False):
		if not data or len(data) == 0:
			self['title'].setText("Fehler beim Abrufen der SerienPlaner-Daten")
			return
		if useCache:
			(headDate, self.daylist) = data
		else:
			self.daylist = [[]]
			headDate = [data["date"]]

			markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)

			rank = 0
			for serie in data["series"]:
				serien_name = serie["name"].encode("utf-8")
				serien_id = int(serie["id"])
				average = serie["average"]

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				serieAdded = 0
				if serien_id in markers:
					serieAdded = 1 if markers[serien_id] else 2

				rank += 1
				self.daylist[0].append((serien_name, average, serien_id, serieAdded, rank))

			if headDate:
				d = headDate[0].split(',')
				d.reverse()
				key = d[0].strip()
				cache = serienRecSeriesPlanner.loadPlanerData(2)
				cache.update({key: (headDate, self.daylist)})
				if config.plugins.serienRec.planerCacheEnabled.value:
					serienRecSeriesPlanner.writePlanerData(2, cache)

		self.loading = False
		self['title'].setText("")
		self.chooseMenuList.setList(map(self.buildTopThirtyList, self.daylist[0]))
		self.ErrorMsg = "'getCover()'"
		self.getCover()

	def buildPlanerList(self, entry):
		(regional, paytv, neu, prime, transmissionTime, url, serien_name, sender, staffel, episode, title, aufnahme,
		 serieAdded, bereits_vorhanden, serien_id) = entry

		imageNone = "%simages/black.png" % SerienRecorder.serienRecMainPath
		imageNeu = "%simages/neu.png" % SerienRecorder.serienRecMainPath
		imageTimer = "%simages/timer.png" % SerienRecorder.serienRecMainPath
		imageHDD = "%simages/hdd_icon.png" % SerienRecorder.serienRecMainPath

		if serieAdded == 1:
			seriesColor = parseColor('green').argb()
		elif serieAdded == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None
		if aufnahme:
			seriesColor = parseColor('blue').argb()

		titleColor = timeColor = parseColor('foreground').argb()

		if int(neu) == 0:
			imageNeu = imageNone

		if bereits_vorhanden:
			imageHDDTimer = imageHDD
		elif aufnahme:
			imageHDDTimer = imageTimer
		else:
			imageHDDTimer = imageNone

		if config.plugins.serienRec.showPicons.value != "0":
			picon = loadPNG(imageNone)
			if sender and self.serviceRefs.get(sender):
				# Get picon by reference or name
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(sender)[0] if config.plugins.serienRec.showPicons.value == "1" else self.serviceRefs.get(sender)[1])
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
			        (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 5 * skinFactor, 80 * skinFactor,
			         40 * skinFactor, picon),
			        (
			        eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330 * skinFactor, 7 * skinFactor, 30 * skinFactor,
			        22 * skinFactor, loadPNG(imageNeu)),
			        (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330 * skinFactor, 30 * skinFactor,
			         30 * skinFactor, 22 * skinFactor, loadPNG(imageHDDTimer)),
			        (eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0,
			         RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
			        (eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 29 * skinFactor, 150 * skinFactor,
			         18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, transmissionTime, timeColor, timeColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 365 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
			         RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 365 * skinFactor, 29 * skinFactor, 500 * skinFactor,
			         18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
			        ]
		else:
			return [entry,
			        (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 7, 30 * skinFactor, 22 * skinFactor,
			         loadPNG(imageNeu)),
			        (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 30 * skinFactor, 30 * skinFactor,
			         22 * skinFactor, loadPNG(imageHDDTimer)),
			        (eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 280 * skinFactor, 26 * skinFactor, 0,
			         RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
			        (eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 29 * skinFactor, 150 * skinFactor,
			         18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, transmissionTime, timeColor, timeColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 340 * skinFactor, 3, 520 * skinFactor, 26 * skinFactor, 0,
			         RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
			        (eListboxPythonMultiContent.TYPE_TEXT, 340 * skinFactor, 29 * skinFactor, 520 * skinFactor,
			         18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
			        ]

	@staticmethod
	def buildTopThirtyList(entry):
		(serien_name, average, serien_id, serieAdded, rank) = entry

		if serieAdded == 1:
			seriesColor = parseColor('green').argb()
		elif serieAdded == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None

		title = "%d Abrufe/Tag" % average
		titleColor = parseColor('foreground').argb()

		rank = "%d." % rank

		return [entry,
		        (eListboxPythonMultiContent.TYPE_TEXT, 5 * skinFactor, 3, 40 * skinFactor, 26 * skinFactor, 0,
		         RT_HALIGN_RIGHT | RT_VALIGN_CENTER, rank, titleColor, titleColor),
		        (eListboxPythonMultiContent.TYPE_TEXT, 70 * skinFactor, 3, 520 * skinFactor, 26 * skinFactor, 0,
		         RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
		        (eListboxPythonMultiContent.TYPE_TEXT, 70 * skinFactor, 29 * skinFactor, 520 * skinFactor,
		         18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
		        ]

	def keyOK(self):
		if self.modus == "list":
			if self.loading:
				return

			check = self['menu_list'].getCurrent()
			if check is None:
				return

			(serien_name, serien_id) = self.getSeriesNameID()
			if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
				boxID = None
			else:
				boxID = config.plugins.serienRec.BoxID.value

			if self.database.addMarker(str(serien_id), serien_name, '', boxID, 0):
				SRLogger.writeLog("\nSerien Marker für ' %s ' wurde angelegt" % serien_name, True)
				self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
				if config.plugins.serienRec.tvplaner_full_check.value:
					config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
					config.plugins.serienRec.tvplaner_last_full_check.save()
					SerienRecorder.configfile.save()
				if config.plugins.serienRec.openMarkerScreen.value:
					from SerienRecorderMarkerScreen import serienRecMarker
					self.session.open(serienRecMarker, serien_name)
			else:
				self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))

	def getCover(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		(serien_name, serien_id) = self.getSeriesNameID()
		self.ErrorMsg = "'getCover()'"
		SerienRecorder.getCover(self, serien_name, serien_id)

	def keyRed(self):
		if self.modus == "list":
			if config.plugins.serienRec.screenplaner.value == 1:
				config.plugins.serienRec.screenplaner.value = 2
			else:
				config.plugins.serienRec.screenplaner.value = 1
			config.plugins.serienRec.screenplaner.save()
			SerienRecorder.configfile.save()
			self.readPlanerData(False)

	def getSeriesNameID(self):
		if config.plugins.serienRec.screenplaner.value == 1:
			serien_name = self['menu_list'].getCurrent()[0][6]
			serien_id = self['menu_list'].getCurrent()[0][14]
		else:
			serien_name = self['menu_list'].getCurrent()[0][0]
			serien_id = self['menu_list'].getCurrent()[0][2]

		return serien_name, serien_id

	def keyGreen(self):
		from SerienRecorderChannelScreen import serienRecMainChannelEdit
		self.session.openWithCallback(self.readPlanerData, serienRecMainChannelEdit)

	def keyYellow(self):
		from SerienRecorderMarkerScreen import serienRecMarker
		self.session.openWithCallback(self.readPlanerData, serienRecMarker)

	def keyBlue(self):
		from SerienRecorderTimerListScreen import serienRecTimerListScreen
		self.session.openWithCallback(self.readPlanerData, serienRecTimerListScreen)

	def keyCheck(self):
		if config.plugins.serienRec.tvplaner.value:
			self.session.openWithCallback(self.executeAutoCheck, MessageBox, "Bei 'ja' wird der Suchlauf für TV-Planer Timer gestartet, bei 'nein' wird ein voller Suchlauf durchgeführt.", MessageBox.TYPE_YESNO)
		else:
			self.executeAutoCheck(False)

	def executeAutoCheck(self, withTVPlaner):
		from SerienRecorderAutoCheckScreen import serienRecRunAutoCheckScreen
		self.session.openWithCallback(self.readPlanerData, serienRecRunAutoCheckScreen, withTVPlaner)


	def keyLeft(self):
		if self.modus == "list":
			self['menu_list'].pageUp()
			self.getCover()

	def keyRight(self):
		if self.modus == "list":
			self['menu_list'].pageDown()
			self.getCover()

	def keyDown(self):
		if self.modus == "list":
			self['menu_list'].down()
			self.getCover()

	def keyUp(self):
		if self.modus == "list":
			self['menu_list'].up()
			self.getCover()

	def nextPage(self):
		if config.plugins.serienRec.screenplaner.value == 1 and self.page < 4:
			self.page += 1
			self.chooseMenuList.setList(map(self.buildPlanerList, []))
			self.readPlanerData(False)

	def backPage(self):
		if config.plugins.serienRec.screenplaner.value == 1 and not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildPlanerList, []))
		self.readPlanerData(False)

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		if self.modus == "list":
			self.stopDisplayTimer()
			self.close()


