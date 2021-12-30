# coding=utf-8

# This file contains the SerienRecoder Episodes Screen
import os, time

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from enigma import ePicLoad, eTimer, loadPNG, RT_HALIGN_LEFT, RT_VALIGN_CENTER, eListboxPythonMultiContent
from skin import parseColor, parseFont
from Tools.Directories import fileExists

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

from .SerienRecorder import serienRecDataBaseFilePath, getCover
from .SerienRecorderScreenHelpers import serienRecBaseScreen, skinFactor, updateMenuKeys, setSkinProperties, buttonText_na, setMenuTexts, InitSkin
from .SerienRecorderHelpers import isDreamOS, toStr
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderLogWriter import SRLogger

class serienRecEpisodes(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, seriesName, seriesWLID):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.serien_fsid = self.database.getMarkerFSID(seriesWLID)
		self.addedEpisodes = self.database.getTimerForSeries(self.serien_fsid)
		self.modus = "menu_list"
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = seriesName
		self.serien_wlid = seriesWLID
		self.episodes_list_cache = {}
		self.showEpisodes = True
		self.aStaffel = None
		self.aFromEpisode = None
		self.aToEpisode = None
		self.numberOfEpisodes = 0
		self.page = 1
		self.maxPages = 1
		self.loading = False
		self.changesMade = False

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Informationen zur ausgewählten Episode anzeigen"),
			"cancel": (self.keyCancel, "Zurück zur Serien-Marker-Ansicht"),
			"left"  : (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "Zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "Eine Zeile nach oben"),
			"down"  : (self.keyDown, "Eine Zeile nach unten"),
			"red"	: (self.keyRed, "Diese Folge (nicht mehr) timern"),
			"green"	: (self.keyGreen, "Zeige nur Einträge aus der Timer-Liste"),
			"yellow": (self.keyYellow, "Ausgewählte Folge auf den Merkzettel"),
			"blue"  : (self.keyBlue, "Neue Einträge manuell hinzufügen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"nextBouquet" : (self.nextPage, "Nächste Seite laden"),
			"prevBouquet" : (self.backPage, "Vorherige Seite laden"),
			"startTeletext"  : (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions", ], {
			"displayHelp"       : self.showHelp,
			"displayHelp_long"  : self.showManual,
		}, 0)

		self.setupSkin()
		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.loadEpisodes)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("(De)aktivieren")
		self['text_green'].setText("Zeige Timer")
		self['text_ok'].setText("Beschreibung")
		self['text_yellow'].setText("Auf den Merkzettel")
		self['text_blue'].setText("Manuell hinzufügen")

		self['headline'].instance.setForegroundColor(parseColor('red'))
		self['headline'].instance.setFont(parseFont("Regular;16", ((1,1),(1,1))))

		self.chooseMenuList.l.setItemHeight(int(28 * skinFactor))

		self.num_bt_text[2][2] = buttonText_na
		self.num_bt_text[3][2] = buttonText_na

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		super(self.__class__, self).setupSkin()
		self[self.modus].show()


		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_epg'].hide()
			self['bt_info'].hide()

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def wunschliste(self):
		super(self.__class__, self).wunschliste(self.serien_wlid)

	def resultsEpisodes(self, data):
		self.maxPages = 1
		self.episodes_list_cache[self.page] = []

		for episode in data["episodes"]:
			if "title" in episode:
				title = toStr(episode["title"])
			else:
				title = "-"

			activeTimer = self.isTimerAdded(episode["season"], episode["episode"], episode["title"])
			self.episodes_list_cache[self.page].append(
				[episode["season"], episode["episode"], episode["id"], title, activeTimer])

		self.chooseMenuList.setList(list(map(self.buildList_episodes, self.episodes_list_cache[self.page])))
		self.numberOfEpisodes = data["numEpisodes"]

		self.loading = False
		self.showPages()

	def loadEpisodes(self):
		getCover(self, self.serien_name, self.serien_wlid, self.serien_fsid)
		if self.page in self.episodes_list_cache:
			self.chooseMenuList.setList(list(map(self.buildList_episodes, self.episodes_list_cache[self.page])))
			self['title'].setText("%s Episoden für ' %s ' gefunden." % (self.numberOfEpisodes, self.serien_name))
		else:
			self.loading = True
			self['title'].setText("Lade Episodenliste...")
			def downloadEpisodes():
				print("[SerienRecorder] downloadEpisodes")
				return SeriesServer().doGetEpisodes(int(self.serien_wlid), int(self.page))

			def onDownloadEpisodesSuccessful(episodes):
				self.resultsEpisodes(episodes)
				self['title'].setText("%s Episoden für ' %s ' gefunden." % (self.numberOfEpisodes, self.serien_name))

			def onDownloadEpisodesFailed():
				print("[SerienRecorder]: Abfrage beim SerienServer doGetEpisodes() fehlgeschlagen")
				self['title'].setText("Fehler beim Abrufen der Episodenliste")
				self.loading = False

			import twisted.python.runtime
			if twisted.python.runtime.platform.supportsThreads():
				from twisted.internet.threads import deferToThread
				deferToThread(downloadEpisodes).addCallback(onDownloadEpisodesSuccessful).addErrback(onDownloadEpisodesFailed)
			else:
				try:
					result = downloadEpisodes()
					onDownloadEpisodesSuccessful(result)
				except:
					onDownloadEpisodesFailed()

		self['headline'].show()

	def buildList_episodes(self, entry):
		(season, episode, info_id, title, activeTimer) = entry

		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))

		serienRecMainPath = os.path.dirname(__file__)
		imageNone = "%s/images/black.png" % serienRecMainPath

		# imageMinus = "%s/images/red_dot.png" % serienRecMainPath
		# imagePlus = "%s/images/green_dot.png" % serienRecMainPath
		imageMinus = "%s/images/minus.png" % serienRecMainPath
		imagePlus = "%s/images/plus.png" % serienRecMainPath
		imageTimer = "%s/images/timer.png" % serienRecMainPath

		leftImage = (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 6 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(imageMinus))
		middleImage = imageNone

		# leftImage = imageMinus
		# if len(self.addedEpisodes) > 0 and self.isAlreadyAdded(season, episode, title):
		# 	leftImage = imagePlus
		#
		# color = parseColor('yellow').argb()
		# if not str(season).isdigit():
		# 	color = parseColor('red').argb()
		# if activeTimer:
		# 	leftImage = imageTimer

		color = parseColor('red').argb()
		if len(self.addedEpisodes) > 0 and self.isAlreadyAdded(season, episode, title):
			color = parseColor('green').argb()
			leftImage = (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 6 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(imagePlus))
		if activeTimer:
			color = parseColor('blue').argb()
			leftImage = (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 1, 3 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageTimer))
			#middleImage = imageTimer

		foregroundColor = parseColor('foreground').argb()

		return [entry,
			#(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 6 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(leftImage)),
		    leftImage,
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 140 * skinFactor, 22 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s" % seasonEpisodeString, color, color),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 165 * skinFactor, 3 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(middleImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 3, 550 * skinFactor, 22 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, foregroundColor, foregroundColor),
			#(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 29 * skinFactor, 550 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, otitle, parseColor('yellow').argb()),
			]

	def loadTimer(self):
		self.addedEpisodes = self.database.getTimerForSeries(self.serien_fsid)
		addedlist = []
		for timer in self.addedEpisodes:
			(Staffel, Episode, title, webChannel, start_time) = timer
			zeile = "%s - S%sE%s - %s" % (self.serien_name, str(Staffel).zfill(2), str(Episode).zfill(2), title)
			zeile = zeile.replace(" - dump", " - %s" % "(Manuell hinzugefügt !!)").replace(" - webdump", " - %s" % "(Manuell übers Webinterface hinzugefügt !!)")
			addedlist.append((zeile, self.serien_name, Staffel, Episode, title, start_time, webChannel))

		addedlist.sort(key=lambda x: (x[1].lower(), int(x[2]) if x[2].isdigit() else x[2].lower(), int(x[3]) if x[3].isdigit() else x[3].lower()))
		return addedlist[:]

	def buildList_timer(self, entry):
		(zeile, Serie, Staffel, Episode, title, start_time, webChannel) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
				(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile, foregroundColor)
				]

	def showPages(self):
		headline = "Diese Liste stammt von TheTVDB, daher kann die Nummerierung/Episodenbeschreibung abweichen."
		if self.maxPages > 1:
			headline += "          Seite %s/%s" % (str(self.page), str(self.maxPages))
		self['headline'].setText(headline)

	def isAlreadyAdded(self, season, episode, title=None):
		result = False
		#Title is only relevant if season and episode is 0
		#this happen when Wunschliste has no episode and season information
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		if not title:
			for addedEpisode in self.addedEpisodes[:]:
				if str(addedEpisode[0]).zfill(2) == str(season).zfill(2) and str(addedEpisode[1]).zfill(2) == str(episode).zfill(2):
					result = True
					#self.addedEpisodes.remove(addedEpisode)
					break
		else:
			for addedEpisode in self.addedEpisodes[:]:
				if (str(addedEpisode[0]).zfill(2) == str(season).zfill(2)) and (str(addedEpisode[1]).zfill(2) == str(episode).zfill(2)) and (addedEpisode[2] == title):
					result = True
					#self.addedEpisodes.remove(addedEpisode)
					break

		return result

	def isTimerAdded(self, season, episode, title=None):
		result = False
		current_time = int(time.time())

		#Title is only relevant if season and episode is 0
		#this happen when Wunschliste has no episode and season information
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		if not title:
			for addedEpisode in self.addedEpisodes[:]:
				if str(addedEpisode[0]).zfill(2) == str(season).zfill(2) and str(addedEpisode[1]).zfill(2) == str(episode).zfill(2) and addedEpisode[4] >= current_time:
					result = True
					#self.addedEpisodes.remove(addedEpisode)
					break
		else:
			for addedEpisode in self.addedEpisodes[:]:
				if (str(addedEpisode[0]).zfill(2) == str(season).zfill(2)) and (str(addedEpisode[1]).zfill(2) == str(episode).zfill(2)) and (addedEpisode[2] == title) and addedEpisode[4] >= current_time:
					result = True
					#self.addedEpisodes.remove(addedEpisode)
					break

		return result

	def removeFromDB(self, season, episode, title=None):
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		SRLogger.writeLogFilter("timerDebug", "Timer gelöscht: %s %s - %s" % (self.serien_name, seasonEpisodeString, title))

		self.database.removeTimer(self.serien_fsid, season, episode, title, None, None)

	def keyOK(self):
		if self.loading or not self.showEpisodes or self['menu_list'].getCurrent() is None:
			return

		sindex = self['menu_list'].getSelectedIndex()
		#if len(self.episodes_list_cache) >= self.page:
		if self.page in self.episodes_list_cache:
			if len(self.episodes_list_cache[self.page]) != 0:
				if self.episodes_list_cache[self.page][sindex][2]:
					self.session.open(serienRecShowEpisodeInfo, self.serien_name, self.serien_wlid, self.serien_fsid, self.episodes_list_cache[self.page][sindex][3], self.episodes_list_cache[self.page][sindex][2])
					#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!", MessageBox.TYPE_INFO, timeout=10)

	def keyRed(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		sindex = self['menu_list'].getSelectedIndex()
		if self.showEpisodes:
			if self.page in self.episodes_list_cache:
				current_episodes_list = self.episodes_list_cache[self.page]
				if len(current_episodes_list) != 0:
					isAlreadyAdded = self.isAlreadyAdded(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][3])

					if isAlreadyAdded:
						self.removeFromDB(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][3])
					else:
						self.database.addToTimerList(self.serien_name, self.serien_fsid, current_episodes_list[sindex][1], current_episodes_list[sindex][1], current_episodes_list[sindex][0], current_episodes_list[sindex][3], int(time.time()), "", "", 0, 1)

					self.addedEpisodes = self.database.getTimerForSeries(self.serien_fsid)
					self.chooseMenuList.setList(list(map(self.buildList_episodes, current_episodes_list)))
		else:
			(txt, serie, staffel, episode, title, start_time, webChannel) = self['menu_list'].getCurrent()[0]
			self.removeFromDB(staffel, episode, title)
			timerList = self.loadTimer()
			self.chooseMenuList.setList(list(map(self.buildList_timer, timerList)))
			self['title'].setText("%s Timer für ' %s ' gefunden." % (len(timerList), self.serien_name))

	def keyGreen(self):
		if self.loading:
			return

		if self.showEpisodes:
			# Show timer
			self.showEpisodes = False
			self['text_red'].setText("Eintrag löschen")
			self['text_green'].setText("Zeige Episoden")
			self['text_yellow'].hide()
			self['text_blue'].hide()
			self['text_ok'].hide()
			timerList = self.loadTimer()
			self.chooseMenuList.setList(list(map(self.buildList_timer, timerList)))
			self['menu_list'].moveToIndex(0)
			self['title'].setText("%s Timer für ' %s ' gefunden." % (len(timerList), self.serien_name))
			self['headline'].hide()
		else:
			# Show episodes
			self.showEpisodes = True
			self['text_red'].setText("(De)aktivieren")
			self['text_green'].setText("Zeige Timer")
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_ok'].show()
			self.loadEpisodes()
			self['menu_list'].moveToIndex(0)

	def keyYellow(self):
		if self.loading or not self.showEpisodes or self['menu_list'].getCurrent() is None:
			return

		sindex = self['menu_list'].getSelectedIndex()
		#if len(self.episodes_list_cache) >= self.page:
		if self.page in self.episodes_list_cache:
			if len(self.episodes_list_cache[self.page]) != 0:
				if self.database.addBookmark(self.serien_name, self.serien_fsid, self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][0], config.plugins.serienRec.NoOfRecords.value):
					self.session.open(MessageBox, "Die Episode wurde zum Merkzettel hinzugefügt", MessageBox.TYPE_INFO, timeout = 10)

	def nextPage(self):
		if self.loading or not self.showEpisodes:
			return

		if self.page <= self.maxPages:
			if self.page == self.maxPages:
				self.page = 1
			else:
				self.page += 1

			self.showPages()
			self.chooseMenuList.setList(list(map(self.buildList_episodes, [])))
			self.loadEpisodes()

	def backPage(self):
		if self.loading or not self.showEpisodes:
			return

		if self.page >= 1 and self.maxPages > 1:
			if self.page == 1:
				self.page = self.maxPages
			else:
				self.page -= 1

			self.showPages()
			self.chooseMenuList.setList(list(map(self.buildList_episodes, [])))
			self.loadEpisodes()

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel.strip()
		if not self.aStaffel or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, NTIVirtualKeyBoard, title = "von Episode:")

	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if not self.aFromEpisode or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, NTIVirtualKeyBoard, title = "bis Episode:")

	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		if self.aToEpisode == "":
			self.aToEpisode = self.aFromEpisode

		if not self.aToEpisode: # or self.aFromEpisode is None or self.aStaffel is None:
			return
		else:
			print("[SerienRecorder] Staffel: %s" % self.aStaffel)
			print("[SerienRecorder] von Episode: %s" % self.aFromEpisode)
			print("[SerienRecorder] bis Episode: %s" % self.aToEpisode)

			if self.aStaffel.startswith('0') and len(self.aStaffel) > 1:
				self.aStaffel = self.aStaffel[1:]

			if self.database.addToTimerList(self.serien_name, self.serien_fsid, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump", int(time.time()), "", "", 0, 1):
				self.chooseMenuList.setList(list(map(self.buildList_episodes, self.episodes_list_cache[self.page])))

	def keyBlue(self):
		if self.loading or not self.showEpisodes:
			return
		self.aStaffel = None
		self.aFromEpisode = None
		self.aToEpisode = None
		self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.serien_name)

	def __onClose(self):
		self.stopDisplayTimer()

class serienRecShowEpisodeInfo(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serieName, serienID, serienFSID, episodeTitle, episodeID):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.displayMode = 2
		self.session = session
		self.picload = ePicLoad()
		self.serien_wlid = serienID
		self.serien_name = serieName
		self.serien_fsid = serienFSID
		self.episodeID = episodeID
		self.episodeTitle = episodeTitle
		self.skin = None
		self.displayTimer_conn = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red"   : (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.pageUp, "zur vorherigen Seite blättern"),
			"right" : (self.pageDown, "zur nächsten Seite blättern"),
			"up"    : (self.pageUp, "zur vorherigen Seite blättern"),
			"down"  : (self.pageDown, "zur nächsten Seite blättern"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"  : (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.onLayoutFinish.append(self.getData)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Zurück")
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None

		if config.plugins.serienRec.showAllButtons.value:
			setMenuTexts(self)
		else:
			self.updateMenuKeys()

			self.displayTimer = eTimer()
			if isDreamOS():
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['info'].show()

		self['title'].setText("Episoden Beschreibung: %s" % self.episodeTitle)

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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

	def wunschliste(self):
		super(self.__class__, self).wunschliste(self.serien_wlid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.getData()

	def getData(self):
		getCover(self, self.serien_name, self.serien_wlid, self.serien_fsid)

		def downloadEpisodeInfo():
			print("[SerienRecorder] downloadEpisodeInfo")
			return SeriesServer().getEpisodeInfo(self.episodeID)

		def onDownloadEpisodeInfoSuccessful(result):
			self['info'].setText(result)

		def onDownloadEpisodeInfoFailed():
			self['info'].setText("Es ist ein Fehler beim Abrufen der Episoden-Informationen aufgetreten!")

		import twisted.python.runtime
		if twisted.python.runtime.platform.supportsThreads():
			from twisted.internet.threads import deferToThread
			deferToThread(downloadEpisodeInfo).addCallback(onDownloadEpisodeInfoSuccessful).addErrback(onDownloadEpisodeInfoFailed)
		else:
			try:
				result = downloadEpisodeInfo()
				onDownloadEpisodeInfoSuccessful(result)
			except:
				onDownloadEpisodeInfoFailed()

	def pageUp(self):
		self['info'].pageUp()

	def pageDown(self):
		self['info'].pageDown()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close()