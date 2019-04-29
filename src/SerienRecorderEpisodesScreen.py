# coding=utf-8

# This file contains the SerienRecoder Episodes Screen
import re, time

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

from SerienRecorder import serienRecDataBaseFilePath, getCover, serienRecMainPath
from SerienRecorderScreenHelpers import serienRecBaseScreen, skinFactor, updateMenuKeys, setSkinProperties, buttonText_na, setMenuTexts, InitSkin
from SerienRecorderHelpers import isDreamOS
from SerienRecorderDatabase import SRDatabase
from SerienRecorderSeriesServer import SeriesServer

class serienRecEpisodes(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serien_name, serie_url, serien_cover):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.ErrorMsg = ''
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.modus = "menu_list"
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serien_id = 0
		self.serien_cover = serien_cover
		self.addedEpisodes = self.database.getTimerForSeries(self.serien_name)
		self.episodes_list_cache = {}
		self.aStaffel = None
		self.aFromEpisode = None
		self.aToEpisode = None
		#self.pages = []
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
			"red"	: (self.keyRed, "Zurück zur Serien-Marker-Ansicht"),
			"green"	: (self.keyGreen, "Diese Folge (nicht mehr) aufnehmen"),
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

		raw = re.findall(".*?(\d+)", serie_url)
		self.serien_id = raw[0]

		self.timer_default = eTimer()
		if isDreamOS():
			self.timer_default_conn = self.timer_default.timeout.connect(self.loadEpisodes)
		else:
			self.timer_default.callback.append(self.loadEpisodes)

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.searchEpisodes)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Zurück")
		self['text_green'].setText("(De)aktivieren")
		self['text_ok'].setText("Beschreibung")
		self['text_yellow'].setText("Auf den Merkzettel")
		self['text_blue'].setText("Manuell hinzufügen")

		#self['headline'].instance.setHAlign(2)
		self['headline'].instance.setForegroundColor(parseColor('red'))
		self['headline'].instance.setFont(parseFont("Regular;16", ((1,1),(1,1))))

		self.chooseMenuList.l.setItemHeight(int(28 * skinFactor))

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		super(self.__class__, self).setupSkin()
		self[self.modus].show()

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

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def wunschliste(self):
		super(self.__class__, self).wunschliste(self.serien_id)

	def searchEpisodes(self):
		super(self.__class__, self).getCover(self.serien_name)
		self['title'].setText("Suche Episoden ' %s '" % self.serien_name)
		self.loading = True
		self.timer_default.start(0)

	def resultsEpisodes(self, data):
		self.maxPages = 1
		self.episodes_list_cache[self.page] = []
		for episode in data["episodes"]:
			if "title" in episode:
				title = episode["title"].encode("utf-8")
			else:
				title = "-"
			self.episodes_list_cache[self.page].append(
				[episode["season"], episode["episode"], episode["id"], title])

		self.chooseMenuList.setList(map(self.buildList_episodes, self.episodes_list_cache[self.page]))
		numberOfEpisodes = data["numEpisodes"]

		self.loading = False
		self['title'].setText("%s Episoden für ' %s ' gefunden." % (numberOfEpisodes, self.serien_name))
		self.showPages()

	def loadEpisodes(self):
		self.timer_default.stop()
		if self.page in self.episodes_list_cache:
			self.chooseMenuList.setList(map(self.buildList_episodes, self.episodes_list_cache[self.page]))
		else:
			getCover(self, self.serien_name, self.serien_id)
			try:
				episodes = SeriesServer().doGetEpisodes(int(self.serien_id), int(self.page))
				self.resultsEpisodes(episodes)
			except:
				self['title'].setText("Fehler beim Abrufen der Episodenliste")

	def buildList_episodes(self, entry):
		(season, episode, info_id, title) = entry

		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))

		imageMinus = "%simages/red_dot.png" % serienRecMainPath
		imagePlus = "%simages/green_dot.png" % serienRecMainPath
		imageNone = "%simages/black.png" % serienRecMainPath

		middleImage = imageNone

		leftImage = imageMinus
		if len(self.addedEpisodes) > 0 and self.isAlreadyAdded(season, episode, title):
			leftImage = imagePlus

		color = parseColor('yellow').argb()
		if not str(season).isdigit():
			color = parseColor('red').argb()

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 8 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(leftImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 140 * skinFactor, 22 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s" % seasonEpisodeString, color),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 150 * skinFactor, 17 * skinFactor, 22 * skinFactor, 48 * skinFactor, loadPNG(middleImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 3, 550 * skinFactor, 22 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title),
			#(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 29 * skinFactor, 550 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, otitle, parseColor('yellow').argb()),
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

	def removeFromDB(self, season, episode, title=None):
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		self.database.removeTimer(self.serien_name, season, episode, title, None, None, None)

	def keyOK(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if not check:
			return

		sindex = self['menu_list'].getSelectedIndex()
		#if len(self.episodes_list_cache) >= self.page:
		if self.page in self.episodes_list_cache:
			if len(self.episodes_list_cache[self.page]) != 0:
				if self.episodes_list_cache[self.page][sindex][2]:
					self.session.open(serienRecShowEpisodeInfo, self.serien_name, self.serien_id, self.episodes_list_cache[self.page][sindex][3], self.episodes_list_cache[self.page][sindex][2])
					#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!", MessageBox.TYPE_INFO, timeout=10)

	def keyGreen(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if not check:
			return

		sindex = self['menu_list'].getSelectedIndex()
		#if len(self.episodes_list_cache) >= self.page:
		if self.page in self.episodes_list_cache:
			current_episodes_list = self.episodes_list_cache[self.page]
			if len(current_episodes_list) != 0:
				isAlreadyAdded = self.isAlreadyAdded(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][3])

				if isAlreadyAdded:
					self.removeFromDB(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][3])
				else:
					self.database.addToTimerList(self.serien_name, current_episodes_list[sindex][1], current_episodes_list[sindex][1], current_episodes_list[sindex][0], current_episodes_list[sindex][3], int(time.time()), "", "", 0, 1)

				self.addedEpisodes = self.database.getTimerForSeries(self.serien_name)
				self.chooseMenuList.setList(map(self.buildList_episodes, current_episodes_list))

	def keyYellow(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if not check:
			return

		sindex = self['menu_list'].getSelectedIndex()
		#if len(self.episodes_list_cache) >= self.page:
		if self.page in self.episodes_list_cache:
			if len(self.episodes_list_cache[self.page]) != 0:
				if self.database.addBookmark(self.serien_name, self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][0], config.plugins.serienRec.NoOfRecords.value):
					self.session.open(MessageBox, "Die Episode wurde zum Merkzettel hinzugefügt", MessageBox.TYPE_INFO, timeout = 10)

	def nextPage(self):
		if self.loading:
			return

		if self.page <= self.maxPages:
			if self.page == self.maxPages:
				self.page = 1
			else:
				self.page += 1

			self.showPages()
			self.chooseMenuList.setList(map(self.buildList_episodes, []))
			self.searchEpisodes()

	def backPage(self):
		if self.loading:
			return

		if self.page >= 1 and self.maxPages > 1:
			if self.page == 1:
				self.page = self.maxPages
			else:
				self.page -= 1

			self.showPages()
			self.chooseMenuList.setList(map(self.buildList_episodes, []))
			self.searchEpisodes()

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
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
			print "[SerienRecorder] Staffel: %s" % self.aStaffel
			print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
			print "[SerienRecorder] bis Episode: %s" % self.aToEpisode
			if self.database.addToTimerList(self.serien_name, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump", int(time.time()), "", "", 0, 1):
				self.chooseMenuList.setList(map(self.buildList_episodes, self.episodes_list_cache[self.page]))

	def keyBlue(self):
		self.aStaffel = None
		self.aFromEpisode = None
		self.aToEpisode = None
		self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.serien_name)

	def __onClose(self):
		self.stopDisplayTimer()

class serienRecShowEpisodeInfo(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serieName, serienID, episodeTitle, episodeID):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.displayMode = 2
		self.session = session
		self.picload = ePicLoad()
		self.serienID = serienID
		self.serien_name = serieName
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
		super(self.__class__, self).wunschliste(self.serienID)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.getData()

	def getData(self):
		try:
			infoText = SeriesServer().getEpisodeInfo(self.episodeID)
		except:
			infoText = 'Es ist ein Fehler beim Abrufen der Episoden-Informationen aufgetreten!'
		self['info'].setText(infoText)
		super(self.__class__, self).getCover(self.serien_name)

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