# coding=utf-8

# This file contains the SerienRecoder Season Begin Screen

from SerienRecorder import *
from SerienRecorderHelpers import *
from SerienRecorderSeriesServer import *
import os, re, threading

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

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"yellow": (self.keyYellow, "Zeige nur Serien-Starts"),
			"startTeletext": (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long": (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
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

		self.changesMade = False
		self.proposalList = []
		self.transmissions = {}
		self.serviceRefs = getActiveServiceRefs()
		self.onLayoutFinish.append(self.__onLayoutFinish)
		self.onLayoutFinish.append(self.setSkinProperties)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_ok'].setText("Marker hinzufügen")
		self['text_yellow'].setText("Zeige Serienstarts")

		self.num_bt_text[3][0] = buttonText_na
		super(self.__class__, self).setSkinProperties()

	def setupSkin(self):
		super(self.__class__, self).setupSkin()
		self[self.modus].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()
		global showAllButtons
		if not showAllButtons:
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			#self['bt_info'].show()
			self['bt_menu'].show()

			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_0'].show()
			#self['text_1'].show()
			#self['text_2'].show()
			#self['text_3'].show()
			self['text_4'].show()
			self['text_6'].show()
			self['text_7'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def __onLayoutFinish(self):
		self['title'].setText("Lade neue Serien/Staffeln...")
		self.timer_default.start(0)

	def readProposal(self):
		self.timer_default.stop()

		webChannels = getWebSenderAktiv()
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
		markers = getAllMarkers()
		self.proposalList = []

		if self.filter:
			self['text_yellow'].setText("Serien-/Staffelstarts")
		else:
			self['text_yellow'].setText("Zeige Serienstarts")

		for event in self.transmissions['events']:
			if self.filter and str(event['season']).isdigit() and int(event['season']) > 1:
				continue

			seriesName = event['name'].encode('utf-8')
			lowerCaseSeriesName = seriesName.lower()

			# marker flags: 0 = no marker, 1 = active marker, 2 = inactive marker
			markerFlag = 0
			if lowerCaseSeriesName in markers:
				markerFlag = 1 if markers[lowerCaseSeriesName] else 2

			url = "http://www.wunschliste.de/epg_print.pl?s=%d" % event['id']
			self.proposalList.append([seriesName, event['season'], event['channel'].encode('utf-8'), event['start'], url, markerFlag])

		if self.filter:
			self['title'].setText("%d neue Serien gefunden:" % len(self.proposalList))
		else:
			self['title'].setText("%d neue Serien/Staffeln gefunden:" % len(self.proposalList))

		self.chooseMenuList.setList(map(self.buildList, self.proposalList))
		if self['menu_list'].getCurrent():
			serien_name = self[self.modus].getCurrent()[0][0]
			serien_url = self[self.modus].getCurrent()[0][4]
			self.getCover(serien_name, serien_url)

	def buildList(self, entry):
		(Serie, Staffel, Sender, UTCTime, Url, MarkerFlag) = entry

		icon = imageNone = "%simages/black.png" % serienRecMainPath
		imageNeu = "%simages/neu.png" % serienRecMainPath

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

		if config.plugins.serienRec.showPicons.value:
			picon = loadPNG(imageNone)
			if Sender:
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(Sender))
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
		url = self[self.modus].getCurrent()[0][4]
		serien_id = getSeriesIDByURL(url)
		if serien_id > 0:
			serien_name = self[self.modus].getCurrent()[0][0]
			self.session.open(serienRecShowInfo, serien_name, serien_id)
			#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
			#			  MessageBox.TYPE_INFO, timeout=10)

	def youtubeSearch(self, searchWord):
		serien_name = self[self.modus].getCurrent()[0][0]
		super(self.__class__, self).youtubeSearch(serien_name)

	def WikipediaSearch(self, searchWord):
		serien_name = self[self.modus].getCurrent()[0][0]
		super(self.__class__, self).WikipediaSearch(serien_name)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def keyOK(self):
		check = self[self.modus].getCurrent()
		if check is None:
			print "[SerienRecorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, UTCTime, Url, MarkerFlag) = self[self.modus].getCurrent()[0]
			(ID, AbStaffel, AlleSender) = self.checkMarker(Serie)
			if ID > 0:
				cCursor = SerienRecorder.dbSerRec.cursor()
				if str(Staffel).isdigit():
					if AbStaffel > Staffel:
						cCursor.execute("SELECT * FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel=?", (ID, Staffel))
						row = cCursor.fetchone()
						if not row:
							cCursor.execute(
								"INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, Staffel))
							cCursor.execute("SELECT * FROM StaffelAuswahl WHERE ID=? ORDER DESC BY ErlaubteStaffel", (ID,))
							staffel_Liste = cCursor.fetchall()
							for row in staffel_Liste:
								(ID, ErlaubteStaffel) = row
								if AbStaffel == (ErlaubteStaffel + 1):
									AbStaffel = ErlaubteStaffel
								else:
									break
							cCursor.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=? WHERE ID=?", (AbStaffel, ID))
							cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel>=?",	(ID, AbStaffel))
				else:
					cCursor.execute("UPDATE OR IGNORE SerienMarker SET TimerForSpecials=1 WHERE ID=?", (ID,))

				if not AlleSender:
					cCursor.execute("SELECT * FROM SenderAuswahl WHERE ID=? AND ErlaubterSender=?", (ID, Sender))
					row = cCursor.fetchone()
					if not row:
						cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))

				SerienRecorder.dbSerRec.commit()
				cCursor.close()
			else:
				cCursor = SerienRecorder.dbSerRec.cursor()
				if config.plugins.serienRec.defaultStaffel.value == "0":
					cCursor.execute(
						"INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, 0, 1, -1)", (Serie, Url))
					ID = cCursor.lastrowid
				else:
					if str(Staffel).isdigit():
						cCursor.execute(
							"INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, ?, -1)", (Serie, Url, AbStaffel, AlleSender))
						ID = cCursor.lastrowid
						cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, Staffel))
					else:
						cCursor.execute(
							"INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel, TimerForSpecials) VALUES (?, ?, ?, ?, -1, 1)", (Serie, Url, AbStaffel, AlleSender))
						ID = cCursor.lastrowid
					cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
				erlaubteSTB = 0xFFFF
				if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
					erlaubteSTB = 0
					erlaubteSTB |= (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
				cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, erlaubteSTB))
				SerienRecorder.dbSerRec.commit()
				cCursor.close()


			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			if config.plugins.serienRec.openMarkerScreen.value:
				self.session.open(serienRecMarker, Serie)

			self.buildProposalList()
			self.chooseMenuList.setList(map(self.buildList, self.proposalList))

	@staticmethod
	def checkMarker(mSerie):
		cCursor = SerienRecorder.dbSerRec.cursor()
		cCursor.execute("SELECT ID, AlleStaffelnAb, alleSender FROM SerienMarker WHERE LOWER(Serie)=?", (mSerie.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (0, 999999, 0)
		cCursor.close()
		return row

	def keyYellow(self):
		if self.filter:
			self.filter = False
		else:
			self.filter = True
		self.buildProposalList()

	def keyLeft(self):
		self[self.modus].pageUp()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_url = self[self.modus].getCurrent()[0][4]
		self.getCover(serien_name, serien_url)

	def keyRight(self):
		self[self.modus].pageDown()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_url = self[self.modus].getCurrent()[0][4]
		self.getCover(serien_name, serien_url)

	def keyDown(self):
		self[self.modus].down()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_url = self[self.modus].getCurrent()[0][4]
		self.getCover(serien_name, serien_url)

	def keyUp(self):
		self[self.modus].up()
		serien_name = self[self.modus].getCurrent()[0][0]
		serien_url = self[self.modus].getCurrent()[0][4]
		self.getCover(serien_name, serien_url)

	def getCover(self, serienName, url):
		serien_id = re.findall('epg_print.pl\?s=([0-9]+)', url)
		if serien_id:
			serien_id = serien_id[0]
		self.ErrorMsg = "'getCover()'"
		#SerienRecorder.writeLog("serienRecShowEpisodeInfo(): ID: %s  Serie: %s" % (str(serien_id), serienName))
		SerienRecorder.getCover(self, serienName, serien_id)

	def __onClose(self):
		self.stopDisplayTimer()
