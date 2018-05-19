# coding=utf-8

# This file contains the SerienRecoder Marker Screen
from Components.ConfigList import ConfigListScreen
from Components.config import getConfigListEntry
from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from SerienRecorderScreenHelpers import *
from SerienRecorder import *
from SerienRecorderHelpers import *
from SerienRecorderDatabase import *

# Tageditor
from Screens.MovieSelection import getPreferredTagEditor

class serienRecMarker(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, SelectSerie=None):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.SelectSerie = SelectSerie
		self.ErrorMsg = "unbekannt"
		self.skin = None
		self.displayMode = 0
		self.displayTimer = None
		self.displayTimer_conn = None
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)

		if not SerienRecorder.showMainScreen:
			self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
				"ok"       : (self.keyOK, "zur Staffelauswahl"),
				"cancel"   : (self.keyCancel, "SerienRecorder beenden"),
				"red"	   : (self.keyRed, "umschalten ausgewählter Serien-Marker aktiviert/deaktiviert"),
				"red_long" : (self.keyRedLong, "ausgewählten Serien-Marker löschen"),
				"green"    : (self.keyGreen, "zur Senderauswahl"),
				"yellow"   : (self.keyYellow, "Sendetermine für ausgewählte Serien anzeigen"),
				"blue"	   : (self.keyBlue, "Ansicht Timer-Liste öffnen"),
				"info"	   : (self.keyCheck, "Suchlauf für Timer mit TV-Planer starten"),
				"info_long": (self.keyCheckLong, "Suchlauf für Timer starten"),
				"left"     : (self.keyLeft, "zur vorherigen Seite blättern"),
				"right"    : (self.keyRight, "zur nächsten Seite blättern"),
				"up"       : (self.keyUp, "eine Zeile nach oben"),
				"down"     : (self.keyDown, "eine Zeile nach unten"),
				"menu"     : (self.markerSetup, "Menü für Serien-Einstellungen öffnen"),
				"menu_long": (self.recSetup, "Menü für globale Einstellungen öffnen"),
				"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
				"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
				"cancel_long" : (self.keyExit, "zurück zur Serienplaner-Ansicht"),
				"0"		   : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
				"1"		   : (self.searchSeries, "Serie manuell suchen"),
				"3"		   : (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
				"4"		   : (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			    "5"		   : (self.episodeList, "Episoden der ausgewählten Serie anzeigen"),
				"6"		   : (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
				"7"		   : (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
				"9"		   : (self.disableAll, "Alle Serien-Marker für diese Box-ID deaktivieren"),
			}, -1)
		else:
			self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
				"ok"       : (self.keyOK, "zur Staffelauswahl"),
				"cancel"   : (self.keyCancel, "zurück zur Serienplaner-Ansicht"),
				"red"	   : (self.keyRed, "umschalten ausgewählter Serien-Marker aktiviert/deaktiviert"),
				"red_long" : (self.keyRedLong, "ausgewählten Serien-Marker löschen"),
				"green"    : (self.keyGreen, "zur Senderauswahl"),
				"yellow"   : (self.keyYellow, "Sendetermine für ausgewählte Serien anzeigen"),
				"blue"	   : (self.keyBlue, "Ansicht Timer-Liste öffnen"),
				"info"	   : (self.keyCheck, "Suchlauf für Timer starten"),
				"info_long": (self.keyCheckLong, "Suchlauf für TV-Planer Timer starten"),
				"left"     : (self.keyLeft, "zur vorherigen Seite blättern"),
				"right"    : (self.keyRight, "zur nächsten Seite blättern"),
				"up"       : (self.keyUp, "eine Zeile nach oben"),
				"down"     : (self.keyDown, "eine Zeile nach unten"),
				"menu"     : (self.markerSetup, "Menü für Serien-Einstellungen öffnen"),
				"menu_long": (self.recSetup, "Menü für globale Einstellungen öffnen"),
				"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
				"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
				"cancel_long" : (self.keyExit, "zurück zur Serienplaner-Ansicht"),
				"0"		   : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
				"1"		   : (self.searchSeries, "Serie manuell suchen"),
				"3"		   : (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
				"4"		   : (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			    "5"		   : (self.episodeList, "Episoden der ausgewählten Serie anzeigen"),
				"6"		   : (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
				"7"		   : (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
				"9"		   : (self.disableAll, "Alle Serien-Marker für diese Box-ID deaktivieren"),
			}, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.modus = "menu_list"
		self.changesMade = False
		self.serien_nameCover = "nix"
		self.loading = True
		self.selected_serien_name = None
		
		self.onLayoutFinish.append(self.readSerienMarker)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_green'].setText("Sender auswählen")
		self['text_ok'].setText("Staffel(n) auswählen")
		self['text_yellow'].setText("Sendetermine")
		self.num_bt_text[1][0] = "Serie suchen"
		self.num_bt_text[0][1] = "Episoden-Liste"
		self.num_bt_text[2][2] = "Timer suchen"
		self.num_bt_text[4][1] = "Alle deaktivieren"

		if longButtonText:
			self.num_bt_text[4][2] = "Setup Serie (lang: global)"
			self['text_red'].setText("An/Aus (lang: Löschen)")
			self['text_blue'].setText("Timer-Liste")
			if not SerienRecorder.showMainScreen:
				self.num_bt_text[0][2] = "Exit (lang: Serienplaner)"
		else:
			self.num_bt_text[4][2] = "Setup Serie/global"
			self['text_red'].setText("(De)aktivieren/Löschen")
			self['text_blue'].setText("Timer-Liste")
			if not SerienRecorder.showMainScreen:
				self.num_bt_text[0][2] = "Exit/Serienplaner"

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)
		
		#normal
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(70*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(25*skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

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

	def markerSetup(self):
		if self['menu_list'].getCurrent() is None:
			return
		serien_name = self['menu_list'].getCurrent()[0][1]
		self.session.openWithCallback(self.SetupFinished, serienRecMarkerSetup, serien_name)

	def SetupFinished(self, result):
		if result:
			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			if config.plugins.serienRec.tvplaner_full_check.value:
				config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
				config.plugins.serienRec.tvplaner_last_full_check.save()
				configfile.save()
			self.readSerienMarker()
		return
		
	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][1]
		serien_url = self['menu_list'].getCurrent()[0][2]
		serien_id = getSeriesIDByURL(serien_url)
		if serien_id:
			self.session.open(SerienRecorder.serienRecShowInfo, serien_name, serien_id)
			#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
			#				  MessageBox.TYPE_INFO, timeout=10)

	def episodeList(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][1]
			serien_url = self['menu_list'].getCurrent()[0][2]
			serien_id = getSeriesIDByURL(serien_url)
			if serien_id:
				self.session.open(serienRecEpisodes, serien_name, "http://www.wunschliste.de/%s" % serien_id, self.serien_nameCover)
				#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
				#				  MessageBox.TYPE_INFO, timeout=10)

	def youtubeSearch(self):
		serien_name = self['menu_list'].getCurrent()[0][1]
		super(self.__class__, self).youtubeSearch(serien_name)

	def WikipediaSearch(self):
		serien_name = self['menu_list'].getCurrent()[0][1]
		super(self.__class__, self).WikipediaSearch(serien_name)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

		if result[1]:
			self.readSerienMarker()

	def getCover(self):
		if self.loading:
			return
		
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][1]
		self.serien_nameCover = "%s%s.png" % (config.plugins.serienRec.coverPath.value, serien_name)
		serien_id = getSeriesIDByURL(self['menu_list'].getCurrent()[0][2])
		self.ErrorMsg = "'getCover()'"
		SerienRecorder.getCover(self, serien_name, serien_id)

	def readSerienMarker(self, SelectSerie=None):
		if SelectSerie:
			self.SelectSerie = SelectSerie
		markerList = []
		numberOfDeactivatedSeries = 0

		markers = self.database.getAllMarkers(True if config.plugins.serienRec.markerSort.value == '1' else False)
		for marker in markers:
			(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, ErlaubteStaffelCount) = marker
			if alleSender:
				sender = ['Alle',]
			else:
				sender = self.database.getMarkerChannels(Serie, False)

			if AlleStaffelnAb == -2: 		# 'Manuell'
				staffeln = ['Manuell',]
			elif AlleStaffelnAb == 0:		# 'Alle'
				staffeln = ['Alle',]
			else:
				staffeln = []
				if ErlaubteStaffelCount > 0:
					staffeln = self.database.getAllowedSeasons(ID, AlleStaffelnAb)
					staffeln.sort()
				if AlleStaffelnAb < 999999:
					staffeln.append('ab %s' % AlleStaffelnAb)
				if AbEpisode > 0:
					staffeln.insert(0, '0 ab E%s' % AbEpisode)
				if bool(TimerForSpecials):
					staffeln.insert(0, 'Specials')

			if useAlternativeChannel == -1:
				useAlternativeChannel = config.plugins.serienRec.useAlternativeChannel.value
			
			SerieAktiviert = True
			if ErlaubteSTB is not None and not (ErlaubteSTB & (1 << (int(config.plugins.serienRec.BoxID.value) - 1))):
				numberOfDeactivatedSeries += 1
				SerieAktiviert = False

			staffeln = str(staffeln).replace("[","").replace("]","").replace("'","").replace('"',"")
			sender = str(sender).replace("[","").replace("]","").replace("'","").replace('"',"")

			if not AufnahmeVerzeichnis:
				AufnahmeVerzeichnis = config.plugins.serienRec.savetopath.value

			if not AnzahlAufnahmen:
				AnzahlAufnahmen = config.plugins.serienRec.NoOfRecords.value
			elif AnzahlAufnahmen < 1:
				AnzahlAufnahmen = 1

			if Vorlaufzeit is None:
				Vorlaufzeit = config.plugins.serienRec.margin_before.value
			elif Vorlaufzeit < 0:
				Vorlaufzeit = 0

			if Nachlaufzeit is None:
				Nachlaufzeit = config.plugins.serienRec.margin_after.value
			elif Nachlaufzeit < 0:
				Nachlaufzeit = 0

			markerList.append((ID, Serie, Url, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, bool(useAlternativeChannel), SerieAktiviert))

		self['title'].setText("Serien Marker - %d/%d Serien vorgemerkt." % (len(markerList)-numberOfDeactivatedSeries, len(markerList)))
		if len(markerList) != 0:
			self.chooseMenuList.setList(map(self.buildList, markerList))
			if self.SelectSerie:
				try:
					idx = zip(*markerList)[1].index(self.SelectSerie)
					self['menu_list'].moveToIndex(idx)
				except Exception, e:
					pass
			self.loading = False
			self.getCover()

	@staticmethod
	def buildList(entry):
		(ID, serie, url, staffeln, sendern, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel, SerieAktiviert) = entry

		if preferredChannel == 1:
			senderText = "Std."
			if useAlternativeChannel:
				senderText = "%s, Alt." % senderText
		else:
			senderText = "Alt."
			if useAlternativeChannel:
				senderText = "%s, Std." % senderText

		if SerieAktiviert:
			serieColor = None
		else:
			serieColor = parseColor('red').argb()

		foregroundColor = parseColor('foreground').argb()

		senderText = "Sender (%s): %s" % (senderText, sendern)
		staffelText = "Staffel: %s" % staffeln
		infoText = "Wdh./Vorl./Nachl.: %s / %s / %s" % (int(AnzahlAufnahmen) - 1, int(Vorlaufzeit), int(Nachlaufzeit))
		folderText = "Dir: %s" % AufnahmeVerzeichnis

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 750 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, serieColor, serieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29 * skinFactor, 350 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffelText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 400 * skinFactor, 29 * skinFactor, 450 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, senderText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 49 * skinFactor, 350 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, infoText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 400 * skinFactor, 49 * skinFactor, 450 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, folderText, foregroundColor, foregroundColor)
			]

	def keyCheckLong(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return
		if self.modus == "menu_list":
			self.session.openWithCallback(self.readSerienMarker, SerienRecorder.serienRecRunAutoCheck, True)
		self.readSerienMarker()

	def keyCheck(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return
		if self.modus == "menu_list":
			self.session.openWithCallback(self.readSerienMarker, SerienRecorder.serienRecRunAutoCheck, True, config.plugins.serienRec.tvplaner.value)

	def keyOK(self):
		if self.modus == "popup_list":	# Staffel
			self.select_serie = self['menu_list'].getCurrent()[0][1]
			select_staffel = self['popup_list'].getCurrent()[0][0]
			select_mode = self['popup_list'].getCurrent()[0][1]
			select_index = self['popup_list'].getCurrent()[0][2]
			print select_staffel, select_mode
			if select_mode == 0:
				select_mode = 1
			else:
				select_mode = 0

			self.staffel_liste[select_index] = list(self.staffel_liste[select_index])
			self.staffel_liste[select_index][1] = select_mode

			if select_mode == 1:
				if select_index == 0:	# 'Manuell'
					for index in range(1, 3):
						# Disable all other special rows
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0
				if select_index == 1:	# Alle
					for index in [0, 3]:
						# Disable 'Manuell' and 'folgende'
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0
				if select_index == 0 or select_index == 1:  # 'Manuell' oder 'Alle'
					for index in range(4, len(self.staffel_liste)):
						# Disable all other season rows
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0

				if select_index >= 3:	# Any season
					for index in [0, 1]:
						# Disable 'Manuell' and 'Alle'
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0

			self.chooseMenuList_popup.setList(map(self.buildList2, self.staffel_liste))
		elif self.modus == "popup_list2":	# Sender
			self.select_serie = self['menu_list'].getCurrent()[0][1]
			select_sender = self['popup_list'].getCurrent()[0][0]
			select_mode = self['popup_list'].getCurrent()[0][1]
			select_index = self['popup_list'].getCurrent()[0][2]
			print select_sender, select_mode
			if select_mode == 0:
				select_mode = 1
			else:
				select_mode = 0
			self.sender_liste[select_index] = list(self.sender_liste[select_index])
			self.sender_liste[select_index][1] = select_mode
			if select_mode == 1:
				if select_index == 0:	# 'Alle'
					# Disable any other channels
					for index in range(1, len(self.sender_liste)):
						# Disable all other season rows
						self.sender_liste[index] = list(self.sender_liste[index])
						self.sender_liste[index][1] = 0
				if select_index >= 1:  	# Any channel
					# Disable 'Alle'
					self.sender_liste[0] = list(self.sender_liste[0])
					self.sender_liste[0][1] = 0
			self.chooseMenuList_popup.setList(map(self.buildList2, self.sender_liste))
		else:
			self.staffelSelect()

	def staffelSelect(self):		
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return

			self.modus = "popup_list"
			self.select_serie = self['menu_list'].getCurrent()[0][1]
			self['popup_list'].show()
			self['popup_bg'].show()
			
			staffeln = ["Manuell", "Alle", "Specials", "Staffeln ab"]
			staffeln.extend(range(config.plugins.serienRec.max_season.value+1))
			mode_list = [0,]*len(staffeln)
			index_list = range(len(staffeln))
			(ID, AlleStaffelnAb, self.AbEpisode, TimerForSpecials) = self.database.getMarkerSeasonSettings(self.select_serie)

			if AlleStaffelnAb == -2:		# 'Manuell'
				mode_list[0] = 1
			else:
				if AlleStaffelnAb == 0:		# 'Alle'
					mode_list[1] = 1
				else:
					if bool(TimerForSpecials):
						mode_list[2] = 1
					cStaffelList = self.database.getAllowedSeasons(ID, AlleStaffelnAb)
					if AlleStaffelnAb >= 999999:
						for staffel in cStaffelList:
							mode_list[staffel + 4] = 1
					elif (AlleStaffelnAb > 0) and (AlleStaffelnAb <= (len(staffeln)-4)):
						mode_list[AlleStaffelnAb + 4] = 1
						mode_list[3] = 1
						for staffel in cStaffelList:
							mode_list[staffel + 4] = 1
							if (staffel + 1) == AlleStaffelnAb:
								mode_list[AlleStaffelnAb + 4] = 0
								AlleStaffelnAb = staffel

					if self.AbEpisode > 0:
						mode_list[4] = 1

			if mode_list.count(1) == 0:
				mode_list[0] = 1
			self.staffel_liste = zip(staffeln, mode_list, index_list)
			self.chooseMenuList_popup.setList(map(self.buildList2, self.staffel_liste))

	def buildList2(self, entry):
		(staffel, mode, index) = entry
		if int(mode) == 0:
			imageMode = "%simages/minus.png" % serienRecMainPath
		else:
			imageMode = "%simages/plus.png" % serienRecMainPath

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 7 * skinFactor, 30 * skinFactor, 17 * skinFactor, loadPNG(imageMode)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 0, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(staffel).zfill(2))
			]

	def keyGreen(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return

			getSender = self.database.getActiveChannels()
			if len(getSender) != 0:
				self.modus = "popup_list2"
				self['popup_list'].show()
				self['popup_bg'].show()
				self.select_serie = self['menu_list'].getCurrent()[0][1]

				getSender.insert(0, 'Alle')
				mode_list = [0,]*len(getSender)
				index_list = range(len(getSender))
				channels = self.database.getMarkerChannels(self.select_serie, False)
				if len(channels) > 0:
					for channel in channels:
						if channel in getSender:
							idx = getSender.index(channel)
							mode_list[idx] = 1
				else:
					# No channels assigned to marker => Alle
					mode_list[0] = 1

				self.sender_liste = zip(getSender, mode_list, index_list)
				self.chooseMenuList_popup.setList(map(self.buildList2, self.sender_liste))

	def callTimerAdded(self, answer):
		if answer:
			self.changesMade = True
			
	def keyYellow(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_id = self['menu_list'].getCurrent()[0][0]
			serien_name = self['menu_list'].getCurrent()[0][1]
			serien_url = self['menu_list'].getCurrent()[0][2]
			
			print serien_url
			self.session.openWithCallback(self.callTimerAdded, SerienRecorder.serienRecSendeTermine, serien_id, serien_name, serien_url, self.serien_nameCover)

	def callDisableAll(self, answer):
		if answer:
			self.selected_serien_name = self['menu_list'].getCurrent()[0][1]
			self.database.disableAllMarkers(config.plugins.serienRec.BoxID.value)
			self.readSerienMarker()
		else:
			return

	def callSaveMsg(self, answer):
		if answer:
			self.session.openWithCallback(self.callDelMsg, MessageBox, "Sollen die Einträge für '%s' auch aus der Timer-Liste entfernt werden?" % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
		else:
			return

	def callDelMsg(self, answer):
		print self.selected_serien_name, answer
		self.removeSerienMarker(self.selected_serien_name, answer)
		
	def removeSerienMarker(self, serien_name, answer):
		self.database.removeMarker(serien_name, answer)
		self.changesMade = True
		SerienRecorder.writeLog("\nSerien Marker für ' %s ' wurde entfernt" % serien_name, True)
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Serie '- %s -' entfernt." % serien_name)
		self.readSerienMarker()	
			
	def keyRed(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['menu_list'].getCurrent()[0][1]
				self.database.changeMarkerStatus(self.selected_serien_name, config.plugins.serienRec.BoxID.value)
				self.readSerienMarker(self.selected_serien_name)
					
	def keyRedLong(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['menu_list'].getCurrent()[0][1]
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.callSaveMsg, MessageBox, "Soll '%s' wirklich entfernt werden?" % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
				else:
					self.session.openWithCallback(self.callDelMsg, MessageBox, "Sollen die Einträge für '%s' auch aus der Timer-Liste entfernt werden?" % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)

	def disableAll(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return
			else:
				self.session.openWithCallback(self.callDisableAll, MessageBox, "Wollen Sie alle Serien-Marker für diese Box deaktivieren?", MessageBox.TYPE_YESNO, default = False)

	def insertStaffelMarker(self):
		(ID, AlleStaffelnAb, AbEpisode, TimerForSpecials) = self.database.getMarkerSeasonSettings(self.select_serie)
		if ID:
			self.database.removeAllMarkerSeasons(self.select_serie)
			liste = self.staffel_liste[1:]
			liste = zip(*liste)
			if 1 in liste[1]:
				#staffel_liste = ['Manuell','Alle','Specials','folgende',...]
				for row in self.staffel_liste:
					(staffel, mode, index) = row
					if mode == 1:
						if index == 0:	# 'Manuell'
							AlleStaffelnAb = -2
							AbEpisode = 0
							TimerForSpecials = 0
							break
						elif index == 1:		# 'Alle'
							AlleStaffelnAb = 0
							AbEpisode = 0
							TimerForSpecials = 0
							break
						elif index == 2:		#'Specials'
							TimerForSpecials = 1
						elif index == 3:		#'folgende'
							liste = self.staffel_liste[5:]
							liste.reverse()
							liste = zip(*liste)
							if 1 in liste[1]:
								idx = liste[1].index(1)
								AlleStaffelnAb = liste[0][idx]
								break
						elif index > 4:
								AlleStaffelnAb = 999999
								AbEpisode = 0
								self.database.setMarkerSeason(ID, staffel)
					else:
						if index == 4:
							AbEpisode = 0

			else:
				AlleStaffelnAb = -2
				AbEpisode = 0

		self.database.updateMarkerSeasonsSettings(self.select_serie, AlleStaffelnAb, AbEpisode, TimerForSpecials)

		if config.plugins.serienRec.tvplaner_full_check.value:
			config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()

		self.changesMade = True
		global runAutocheckAtExit
		runAutocheckAtExit = True
		self.readSerienMarker()

	def insertSenderMarker(self):
		alleSender = 0
		self.database.removeAllMarkerChannels(self.select_serie)
		markerID = self.database.getMarkerID(self.select_serie)
		liste = self.sender_liste[1:]
		liste = zip(*liste)
		data = []
		if 1 in liste[1]:
			for row in self.sender_liste:
				(sender, mode, index) = row
				if (index == 0) and (mode == 1):		# 'Alle'
					alleSender = 1
					break
				elif mode == 1:		# Sender erlaubt
					data.append((markerID, sender))
			self.database.setMarkerChannels(data)
		else:
			alleSender = 1

		self.database.setAllChannelsToMarker(self.select_serie, alleSender)

		self.changesMade = True
		global runAutocheckAtExit
		runAutocheckAtExit = True
		if config.plugins.serienRec.tvplaner_full_check.value:
			config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()

		self.readSerienMarker()

	def keyBlue(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.readSerienMarker, SerienRecorder.serienRecTimer)

	def searchSeries(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			if config.plugins.serienRec.tvplaner_full_check.value:
				config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
				config.plugins.serienRec.tvplaner_last_full_check.save()
				configfile.save()
			self.session.openWithCallback(self.readSerienMarker, SerienRecorder.serienRecAddSerie, serien_name)

	def keyLeft(self):
		if self.modus == "popup_list2":
			self["popup_list"].pageUp()
		else:
			self[self.modus].pageUp()
			self.getCover()

	def keyRight(self):
		if self.modus == "popup_list2":
			self["popup_list"].pageDown()
		else:
			self[self.modus].pageDown()
			self.getCover()

	def keyDown(self):
		if self.modus == "popup_list2":
			self["popup_list"].down()
		else:
			self[self.modus].down()
			self.getCover()

	def keyUp(self):
		if self.modus == "popup_list2":
			self["popup_list"].up()
		else:
			self[self.modus].up()
			self.getCover()

	def selectEpisode(self, episode):
		if str(episode).isdigit():
			self.database.setMarkerEpisode(self.select_serie, episode)
		self.insertStaffelMarker()
			
	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyExit(self):
		if self.modus == "popup_list" or self.modus == "popup_list2":
			self.keyCancel()
		else:
			SerienRecorder.showMainScreen = True
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)
	
	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "menu_list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			if (self.staffel_liste[0][1] == 0) and (self.staffel_liste[1][1] == 0) and (self.staffel_liste[4][1] == 1):		# nicht ('Manuell' oder 'Alle') und '00'
				self.session.openWithCallback(self.selectEpisode, NTIVirtualKeyBoard, title = "Episode eingeben ab der Timer erstellt werden sollen:", text = str(self.AbEpisode))
			else:
				self.insertStaffelMarker()
		elif self.modus == "popup_list2":
			self.modus = "menu_list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.insertSenderMarker()
		else:
			#if not SerienRecorder.showMainScreen:
				#self.hide()
				#self.session.openWithCallback(self.readSerienMarker, ShowSplashScreen, config.plugins.serienRec.showversion.value)
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)


class serienRecMarkerSetup(serienRecBaseScreen, Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, Serie):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.Serie = Serie
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red": (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"green": (self.save, "Einstellungen speichern und zurück zur Serien-Marker-Ansicht"),
			"cancel": (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"ok": (self.ok, "Fenster für Verzeichnisauswahl öffnen"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"startTeletext": (self.showAbout, "Über dieses Plugin"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions", ], {
			"displayHelp": self.showHelp,
			"displayHelp_long": self.showManual,
		}, 0)

		self.setupSkin()
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)

		(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon,
		 AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase) = self.database.getMarkerSettings(self.Serie)

		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = ""
		self.savetopath = ConfigText(default=AufnahmeVerzeichnis, fixed_size=False, visible_width=50)
		self.seasonsubdir = ConfigSelection(choices=[("-1", "gemäß Setup (dzt. %s)" % str(
			config.plugins.serienRec.seasonsubdir.value).replace("True", "ja").replace("False", "nein")), ("0", "nein"),
													 ("1", "ja")], default=str(Staffelverzeichnis))

		if str(Vorlaufzeit).isdigit():
			self.margin_before = ConfigInteger(Vorlaufzeit, (0, 999))
			self.enable_margin_before = ConfigYesNo(default=True)
		else:
			self.margin_before = ConfigInteger(config.plugins.serienRec.margin_before.value, (0, 999))
			self.enable_margin_before = ConfigYesNo(default=False)

		if str(Nachlaufzeit).isdigit():
			self.margin_after = ConfigInteger(Nachlaufzeit, (0, 999))
			self.enable_margin_after = ConfigYesNo(default=True)
		else:
			self.margin_after = ConfigInteger(config.plugins.serienRec.margin_after.value, (0, 999))
			self.enable_margin_after = ConfigYesNo(default=False)

		if str(AnzahlWiederholungen).isdigit():
			self.NoOfRecords = ConfigInteger(AnzahlWiederholungen, (1, 9))
			self.enable_NoOfRecords = ConfigYesNo(default=True)
		else:
			self.NoOfRecords = ConfigInteger(config.plugins.serienRec.NoOfRecords.value, (1, 9))
			self.enable_NoOfRecords = ConfigYesNo(default=False)

		if str(AufnahmezeitVon).isdigit():
			self.fromTime = ConfigClock(default=int(AufnahmezeitVon) * 60 + time.timezone)
			self.enable_fromTime = ConfigYesNo(default=True)
		else:
			self.fromTime = ConfigClock(default=((config.plugins.serienRec.globalFromTime.value[0] * 60) +
												 config.plugins.serienRec.globalFromTime.value[1]) * 60 + time.timezone)
			self.enable_fromTime = ConfigYesNo(default=False)

		if str(AufnahmezeitBis).isdigit():
			self.toTime = ConfigClock(default=int(AufnahmezeitBis) * 60 + time.timezone)
			self.enable_toTime = ConfigYesNo(default=True)
		else:
			self.toTime = ConfigClock(default=((config.plugins.serienRec.globalToTime.value[0] * 60) +
											   config.plugins.serienRec.globalToTime.value[1]) * 60 + time.timezone)
			self.enable_toTime = ConfigYesNo(default=False)

		if str(vps).isdigit():
			self.override_vps = ConfigYesNo(default=True)
			self.enable_vps = ConfigYesNo(default=bool(vps & 0x1))
			self.enable_vps_savemode = ConfigYesNo(default=bool(vps & 0x2))
		else:
			self.override_vps = ConfigYesNo(default=False)
			self.enable_vps = ConfigYesNo(default=False)
			self.enable_vps_savemode = ConfigYesNo(default=False)

		if str(addToDatabase).isdigit():
			self.addToDatabase = ConfigYesNo(default=bool(addToDatabase))
		else:
			self.addToDatabase = ConfigYesNo(default=True)

		self.preferredChannel = ConfigSelection(choices=[("1", "Standard"), ("0", "Alternativ")],
												default=str(preferredChannel))
		self.useAlternativeChannel = ConfigSelection(choices=[("-1", "gemäß Setup (dzt. %s)" % str(
			config.plugins.serienRec.useAlternativeChannel.value).replace("True", "ja").replace("False", "nein")),
															  ("0", "nein"), ("1", "ja")],
													 default=str(useAlternativeChannel))

		# excluded weekdays
		# each weekday is represented by a bit in the database field
		# 0 = Monday to 6 = Sunday, so if all weekdays are excluded we got 1111111 = 127
		if str(excludedWeekdays).isdigit():
			self.enable_excludedWeekdays = ConfigYesNo(default=True)
			self.excludeMonday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 0)))
			self.excludeTuesday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 1)))
			self.excludeWednesday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 2)))
			self.excludeThursday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 3)))
			self.excludeFriday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 4)))
			self.excludeSaturday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 5)))
			self.excludeSunday = ConfigYesNo(default=bool(excludedWeekdays & (1 << 6)))
		else:
			self.enable_excludedWeekdays = ConfigYesNo(default=False)
			self.excludeMonday = ConfigYesNo(default=False)
			self.excludeTuesday = ConfigYesNo(default=False)
			self.excludeWednesday = ConfigYesNo(default=False)
			self.excludeThursday = ConfigYesNo(default=False)
			self.excludeFriday = ConfigYesNo(default=False)
			self.excludeSaturday = ConfigYesNo(default=False)
			self.excludeSunday = ConfigYesNo(default=False)

		# tags
		if tags is None or len(tags) == 0:
			self.serienmarker_tags = []
		else:
			self.serienmarker_tags = pickle.loads(tags)
		self.tags = NoSave(
			ConfigSelection(choices=[len(self.serienmarker_tags) == 0 and "Keine" or ' '.join(self.serienmarker_tags)]))

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[self.savetopath])
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['config'] = ConfigList([])
		self['config'].show()

		self['config_information'].show()
		self['config_information_text'].show()

		self['title'].setText("SerienRecorder - Einstellungen für '%s':" % self.Serie)
		self['text_red'].setText("Abbrechen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Ordner auswählen")
		global showAllButtons
		if not showAllButtons:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, "Hilfe"],
								[buttonText_na, buttonText_na, buttonText_na])

	def createConfigList(self):
		self.margin_before_index = 1
		self.list = []
		self.list.append(
			getConfigListEntry("vom globalen Setup abweichender Speicherort der Aufnahmen:", self.savetopath))
		if self.savetopath.value:
			self.list.append(getConfigListEntry("Staffel-Verzeichnis anlegen:", self.seasonsubdir))
			self.margin_before_index += 1

		self.margin_after_index = self.margin_before_index + 1

		self.list.append(
			getConfigListEntry("vom globalen Setup abweichenden Timervorlauf aktivieren:", self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry("      Timervorlauf (in Min.):", self.margin_before))
			self.margin_after_index += 1

		self.NoOfRecords_index = self.margin_after_index + 1

		self.list.append(
			getConfigListEntry("vom globalen Setup abweichenden Timernachlauf aktivieren:", self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry("      Timernachlauf (in Min.):", self.margin_after))
			self.NoOfRecords_index += 1

		self.fromTime_index = self.NoOfRecords_index + 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichende Anzahl der Aufnahmen aktivieren:",
											self.enable_NoOfRecords))
		if self.enable_NoOfRecords.value:
			self.list.append(getConfigListEntry("      Anzahl der Aufnahmen:", self.NoOfRecords))
			self.fromTime_index += 1

		self.toTime_index = self.fromTime_index + 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichende Früheste Zeit für Timer aktivieren:",
											self.enable_fromTime))
		if self.enable_fromTime.value:
			self.list.append(getConfigListEntry("      Früheste Zeit für Timer:", self.fromTime))
			self.toTime_index += 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichende Späteste Zeit für Timer aktivieren:",
											self.enable_toTime))
		if self.enable_toTime.value:
			self.list.append(getConfigListEntry("      Späteste Zeit für Timer:", self.toTime))

		if SerienRecorder.VPSPluginAvailable:
			self.list.append(getConfigListEntry("vom Sender Setup abweichende VPS Einstellungen:", self.override_vps))
			if self.override_vps.value:
				self.list.append(getConfigListEntry("      VPS für diesen Serien-Marker aktivieren:", self.enable_vps))
				if self.enable_vps.value:
					self.list.append(
						getConfigListEntry("            Sicherheitsmodus aktivieren:", self.enable_vps_savemode))

		self.list.append(getConfigListEntry("Timer in Timer-Liste speichern:", self.addToDatabase))
		self.list.append(getConfigListEntry("Bevorzugte Sender-Liste:", self.preferredChannel))
		self.list.append(getConfigListEntry("Verwende alternative Sender bei Konflikten:", self.useAlternativeChannel))

		self.list.append(
			getConfigListEntry("Wochentage von der Timer-Erstellung ausschließen:", self.enable_excludedWeekdays))
		if self.enable_excludedWeekdays.value:
			self.list.append(getConfigListEntry("      Montag:", self.excludeMonday))
			self.list.append(getConfigListEntry("      Dienstag:", self.excludeTuesday))
			self.list.append(getConfigListEntry("      Mittwoch:", self.excludeWednesday))
			self.list.append(getConfigListEntry("      Donnerstag:", self.excludeThursday))
			self.list.append(getConfigListEntry("      Freitag:", self.excludeFriday))
			self.list.append(getConfigListEntry("      Samstag:", self.excludeSaturday))
			self.list.append(getConfigListEntry("      Sonntag:", self.excludeSunday))

		self.list.append(getConfigListEntry("Tags:", self.tags))

	def UpdateMenuValues(self):
		if self['config'].instance.getCurrentIndex() == self.margin_before_index:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self['config'].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		elif self['config'].instance.getCurrentIndex() == self.NoOfRecords_index:
			if self.enable_NoOfRecords.value and not self.NoOfRecords.value:
				self.NoOfRecords.value = config.plugins.serienRec.NoOfRecords.value
		elif self['config'].instance.getCurrentIndex() == self.fromTime_index:
			if self.enable_fromTime.value and not self.fromTime.value:
				self.fromTime.value = config.plugins.serienRec.globalFromTime.value
		elif self['config'].instance.getCurrentIndex() == self.toTime_index:
			if self.enable_toTime.value and not self.toTime.value:
				self.toTime.value = config.plugins.serienRec.globalToTime.value
		self.changedEntry()

	def changedEntry(self):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyLeft(self):
		if self['config'].getCurrent()[1] == self.tags:
			self.chooseTags()
		else:
			ConfigListScreen.keyLeft(self)
			self.UpdateMenuValues()

	def keyRight(self):
		if self['config'].getCurrent()[1] == self.tags:
			self.chooseTags()
		else:
			ConfigListScreen.keyRight(self)
			self.UpdateMenuValues()

	def keyDown(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyUp(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() < 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def ok(self):
		if self["config"].getCurrent()[1] == self.tags:
			self.chooseTags()
		else:
			ConfigListScreen.keyOK(self)
			if self['config'].instance.getCurrentIndex() == 0:
				if config.plugins.serienRec.seriensubdir.value:
					self.session.openWithCallback(self.openFileSelector, MessageBox,
												  "Hier wird das direkte Aufnahme-Verzeichnis für die Serie ausgewählt, es wird nicht automatisch ein Serien-Ordner angelegt.\n\nMit der blauen Taste kann ein Serien-Ordner manuell angelegt werden.",
												  MessageBox.TYPE_INFO, timeout=15)
				else:
					self.openFileSelector(True)

	def openFileSelector(self, answer):
		if not self.savetopath.value:
			start_dir = config.plugins.serienRec.savetopath.value
		else:
			start_dir = self.savetopath.value

		self.session.openWithCallback(self.selectedMediaFile, SerienRecorder.serienRecFileList, start_dir,
									  "Aufnahme-Verzeichnis auswählen", self.Serie)

	def selectedMediaFile(self, res):
		if res is not None:
			if self['config'].instance.getCurrentIndex() == 0:
				print res
				self.savetopath.value = res
				if self.savetopath.value == "":
					self.savetopath.value = None
				self.changedEntry()

	def tagEditFinished(self, res):
		if res is not None:
			self.serienmarker_tags = res
			self.tags.setChoices([len(res) == 0 and "Keine" or ' '.join(res)])

	def chooseTags(self):
		SerienRecorder.writeLog("Choose tags was called.", True)
		preferredTagEditor = getPreferredTagEditor()
		if preferredTagEditor:
			SerienRecorder.writeLog("Has preferred tageditor.", True)
			self.session.openWithCallback(
				self.tagEditFinished,
				preferredTagEditor,
				self.serienmarker_tags
			)

	def setInfoText(self):
		self.HilfeTexte = {
			self.savetopath: "Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von '%s' gespeichert werden." % self.Serie,
			self.seasonsubdir: "Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis für '%s' (z.B.\n'%sSeason 001') erstellt." % (
			self.Serie, self.savetopath.value),
			self.enable_margin_before: ("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
										"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
										"Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
										"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.margin_before: ("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
								 "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.Serie,
			self.enable_margin_after: ("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
									   "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
									   "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
									   "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.margin_after: ("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
								"Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.Serie,
			self.enable_NoOfRecords: (
									 "Bei 'ja' kann die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen, eingestellt werden.\n"
									 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.\n"
									 "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.NoOfRecords: ("Die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen.\n"
							   "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.") % self.Serie,
			self.enable_fromTime: (
								  "Bei 'ja' kann die erlaubte Zeitspanne (ab Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.\n"
								  "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.fromTime: ("Die Uhrzeit, ab wann Aufnahmen von '%s' erlaubt sind.\n"
							"Die erlaubte Zeitspanne beginnt um %s:%s Uhr.\n"
							"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.") % (
						   self.Serie, str(self.fromTime.value[0]).zfill(2), str(self.fromTime.value[1]).zfill(2)),
			self.enable_toTime: (
								"Bei 'ja' kann die erlaubte Zeitspanne (bis Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.\n"
								"Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.toTime: ("Die Uhrzeit, bis wann Aufnahmen von '%s' erlaubt sind.\n"
						  "Die erlaubte Zeitspanne endet um %s:%s Uhr.\n"
						  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.") % (
						 self.Serie, str(self.toTime.value[0]).zfill(2), str(self.toTime.value[1]).zfill(2)),
			self.override_vps: ("Bei 'ja' kann VPS für Aufnahmen von '%s' eingestellt werden.\n"
								"Diese Einstellung hat Vorrang gegenüber der Einstellung des Senders für VPS.\n"
								"Bei 'nein' gilt die Einstellung vom Sender.") % self.Serie,
			self.enable_vps: (
							 "Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
							 "und endet, wenn der Sender das Ende der Ausstrahlung angibt.\n"
							 "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.Serie,
			self.enable_vps_savemode: (
									  "Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet. Die programmierten Start- und Endzeiten werden eingehalten.\n"
									  "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.\n"
									  "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.Serie,
			self.addToDatabase: "Bei 'nein' werden für die Aufnahmen von '%s' keine Einträge in die Timer-Liste gemacht, sodass die Episoden beliebig oft aufgenommen werden können." % self.Serie,
			self.preferredChannel: "Auswahl, ob die Standard-Sender oder die alternativen Sender für die Aufnahmen von '%s' verwendet werden sollen." % self.Serie,
			self.useAlternativeChannel: (
										"Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
										"falls der Timer für '%s' auf dem bevorzugten Sender nicht angelegt werden kann.\n"
										"Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Verwendung von alternativen Sendern.\n"
										"Bei 'gemäß Setup' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.enable_excludedWeekdays: (
										  "Bei 'ja' können bestimmte Wochentage für die Erstellung von Timern für '%s' ausgenommen werden.\n"
										  "Es werden also an diesen Wochentage für diese Serie keine Timer erstellt.\n"
										  "Bei 'nein' werden alle Wochentage berücksichtigt.") % self.Serie,
			self.tags: ("Verwaltet die Tags für die Timer, die für %s angelegt werden.\n\n"
						"Um diese Option nutzen zu können, muss das Tageditor Plugin installiert sein.") % self.Serie
		}

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."

		self["config_information_text"].setText(text)

	def save(self):
		if not self.enable_margin_before.value:
			Vorlaufzeit = None
		else:
			Vorlaufzeit = self.margin_before.value

		if not self.enable_margin_after.value:
			Nachlaufzeit = None
		else:
			Nachlaufzeit = self.margin_after.value

		if not self.enable_NoOfRecords.value:
			AnzahlWiederholungen = None
		else:
			AnzahlWiederholungen = self.NoOfRecords.value

		if not self.enable_fromTime.value:
			AufnahmezeitVon = None
		else:
			AufnahmezeitVon = (self.fromTime.value[0] * 60) + self.fromTime.value[1]

		if not self.enable_toTime.value:
			AufnahmezeitBis = None
		else:
			AufnahmezeitBis = (self.toTime.value[0] * 60) + self.toTime.value[1]

		if not self.override_vps.value:
			vpsSettings = None
		else:
			vpsSettings = (int(self.enable_vps_savemode.value) << 1) + int(self.enable_vps.value)

		if (not self.savetopath.value) or (self.savetopath.value == ""):
			Staffelverzeichnis = -1
		else:
			Staffelverzeichnis = self.seasonsubdir.value

		if not self.enable_excludedWeekdays.value:
			excludedWeekdays = None
		else:
			excludedWeekdays = 0
			excludedWeekdays |= (self.excludeMonday.value << 0)
			excludedWeekdays |= (self.excludeTuesday.value << 1)
			excludedWeekdays |= (self.excludeWednesday.value << 2)
			excludedWeekdays |= (self.excludeThursday.value << 3)
			excludedWeekdays |= (self.excludeFriday.value << 4)
			excludedWeekdays |= (self.excludeSaturday.value << 5)
			excludedWeekdays |= (self.excludeSunday.value << 6)

		if len(self.serienmarker_tags) == 0:
			tags = ""
		else:
			tags = pickle.dumps(self.serienmarker_tags)

		self.database.setMarkerSettings(self.Serie, (self.savetopath.value, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen,
		AufnahmezeitVon, AufnahmezeitBis, int(self.preferredChannel.value), int(self.useAlternativeChannel.value),
		vpsSettings, excludedWeekdays, tags, int(self.addToDatabase.value)))

		self.close(True)

	def cancel(self):
		self.close(False)
