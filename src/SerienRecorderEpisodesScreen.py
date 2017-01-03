# coding=utf-8

# This file contains the SerienRecoder Episodes Screen

from SerienRecorder import *

class serienRecEpisodes(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serien_name, serie_url, serien_cover):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.modus = "menu_list"
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serien_id = 0
		self.serien_cover = serien_cover
		self.addedEpisodes = SerienRecorder.getAlreadyAdded(self.serien_name)
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
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
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
		if isDreamboxOS:
			self.timer_default_conn = self.timer_default.timeout.connect(self.loadEpisodes)
		else:
			self.timer_default.callback.append(self.loadEpisodes)

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.searchEpisodes)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)
		self['text_red'].setText("Zurück")
		self['text_green'].setText("(De)aktivieren")
		self['text_ok'].setText("Beschreibung")
		self['text_yellow'].setText("Auf den Merkzettel")
		self['text_blue'].setText("Manuell hinzufügen")

		self['headline'].instance.setHAlign(2)
		self['headline'].instance.setForegroundColor(parseColor('foreground'))
		self['headline'].instance.setFont(parseFont("Regular;20", ((1,1),(1,1))))

		super(self.__class__, self).setSkinProperties()

	def setupSkin(self):
		super(self.__class__, self).setupSkin()
		self[self.modus].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()
		global showAllButtons
		if not showAllButtons:
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

	def youtubeSearch(self, searchWord):
		super(self.__class__, self).youtubeSearch(self.serien_name)

	def WikipediaSearch(self, searchWord):
		super(self.__class__, self).WikipediaSearch(self.serien_name)

	def searchEpisodes(self):
		super(self.__class__, self).getCover(self.serien_name)
		self['title'].setText("Suche Episoden ' %s '" % self.serien_name)
		self.loading = True
		self.timer_default.start(0)

	def resultsEpisodes(self, data):
		self.maxPages = data["numPages"]
		self.episodes_list_cache[self.page] = []
		for episode in data["episodes"]:
			if "title" in episode:
				title = episode["title"].encode("utf-8")
			else:
				title = "-"
			if "otitle" in episode:
				otitle = episode["otitle"].encode("utf-8")
			else:
				otitle = ("(%s)" % title)
			self.episodes_list_cache[self.page].append(
				[episode["season"], episode["episode"], episode["tv"], episode["url"], title, otitle])

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
			SerienRecorder.getCover(self, self.serien_name, self.serien_id)
			episodes = SeriesServer().doGetEpisodes(int(self.serien_id), int(self.page))
			self.resultsEpisodes(episodes)

	def buildList_episodes(self, entry):
		(season, episode, tv, info_url, title, otitle) = entry

		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))

		imageMinus = "%simages/red_dot.png" % serienRecMainPath
		imagePlus = "%simages/green_dot.png" % serienRecMainPath
		imageNone = "%simages/black.png" % serienRecMainPath
		imageTV = "%simages/tv.png" % serienRecMainPath

		middleImage = imageNone
		if tv:
			middleImage = imageTV

		leftImage = imageMinus
		if len(self.addedEpisodes) > 0 and self.isAlreadyAdded(season, episode, title):
			leftImage = imagePlus

		color = parseColor('yellow').argb()
		if not str(season).isdigit():
			color = parseColor('red').argb()

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 15 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(leftImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 140 * skinFactor, 48 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s" % seasonEpisodeString, color),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 150 * skinFactor, 17 * skinFactor, 48 * skinFactor, 48 * skinFactor, loadPNG(middleImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 3, 550 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title),
			(eListboxPythonMultiContent.TYPE_TEXT, 200 * skinFactor, 29 * skinFactor, 550 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, otitle, parseColor('yellow').argb()),
			]

	def showPages(self):
		if self.maxPages > 1:
			self['headline'].setText("Seite %s/%s" % (str(self.page), str(self.maxPages)))

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

		cCursor = SerienRecorder.dbSerRec.cursor()
		if not title:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (self.serien_name.lower(), season.lower(), str(episode).zfill(2).lower()))
		else:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND (LOWER(Titel)=? OR Titel=? OR Titel='')", (self.serien_name.lower(), season.lower(), str(episode).zfill(2).lower(), title.lower(), "dump"))

		SerienRecorder.dbSerRec.commit()
		cCursor.close()

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
				if self.episodes_list_cache[self.page][sindex][3]:
					self.session.open(SerienRecorder.serienRecShowEpisodeInfo, self.serien_name, self.episodes_list_cache[self.page][sindex][4], "http://www.wunschliste.de/%s" % self.episodes_list_cache[self.page][sindex][3])

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
				isAlreadyAdded = self.isAlreadyAdded(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][4])

				if isAlreadyAdded:
					self.removeFromDB(current_episodes_list[sindex][0], current_episodes_list[sindex][1], current_episodes_list[sindex][4])
				else:
					SerienRecorder.addToAddedList(self.serien_name, current_episodes_list[sindex][1], current_episodes_list[sindex][1], current_episodes_list[sindex][0], current_episodes_list[sindex][4])

				self.addedEpisodes = SerienRecorder.getAlreadyAdded(self.serien_name)
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
				if SerienRecorder.addToWishlist(self.serien_name, self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][1], self.episodes_list_cache[self.page][sindex][0]):
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
			if SerienRecorder.addToAddedList(self.serien_name, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump"):
				self.chooseMenuList.setList(map(self.buildList_episodes, self.episodes_list_cache[self.page]))

	def keyBlue(self):
		self.aStaffel = None
		self.aFromEpisode = None
		self.aToEpisode = None
		self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.serien_name)

	def __onClose(self):
		self.stopDisplayTimer()
