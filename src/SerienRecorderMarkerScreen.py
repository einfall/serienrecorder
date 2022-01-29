# coding=utf-8

# This file contains the SerienRecoder Marker Screen
import os
import time

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Components.MenuList import MenuList

from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox

from Tools.Directories import fileExists

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, loadPNG
from skin import parseColor

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

from .SerienRecorderScreenHelpers import serienRecBaseScreen, InitSkin, skinFactor
from .SerienRecorder import serienRecDataBaseFilePath

from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderEpisodesScreen import serienRecEpisodes
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderMarkerSetupScreen import serienRecMarkerSetup

class serienRecMarker(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, toBeSelect=None):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.skin = None
		self.displayMode = 0
		self.displayTimer = None
		self.displayTimer_conn = None
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.staffel_liste = []
		self.sender_liste = []
		self.AbEpisode = 0
		self.columnWidth = int(config.plugins.serienRec.markerColumnWidth.value)

		if config.plugins.serienRec.firstscreen.value == "0":
			self.showMainScreen = True
		else:
			self.showMainScreen = False

		actions = {
			"ok"            : (self.keyOK, "Zur Staffelauswahl"),
			"cancel"        : (self.keyCancel, "Zurück zur Serienplaner-Ansicht"),
			"red"	        : (self.keyRed, "Ausgewählten Serien-Marker aktivieren/deaktivieren"),
			"red_long"      : (self.keyRedLong, "Ausgewählten Serien-Marker löschen"),
			"green"         : (self.keyGreen, "Zur Senderauswahl"),
			"yellow"        : (self.keyYellow, "Sendetermine für ausgewählte Serie anzeigen"),
			"yellow_long"   : (self.resetTransmissions, "Sendetermine für ausgewählte Serie zurücksetzen"),
			"blue"	        : (self.keyBlue, "Ansicht Timer-Liste öffnen"),
			"info"	        : (self.keyCheck, "Suchlauf für Timer starten"),
			"left"          : (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right"         : (self.keyRight, "Zur nächsten Seite blättern"),
			"up"            : (self.keyUp, "Eine Zeile nach oben"),
			"down"          : (self.keyDown, "Eine Zeile nach unten"),
			"menu"          : (self.markerSetup, "Menü für Serien-Einstellungen öffnen"),
			"menu_long"     : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext" : (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"		        : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"1"		        : (self.searchSeries, "Serie manuell suchen"),
			"2"		        : (self.changeTVDBID, "TVDB-ID ändern"),
			"3"		        : (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		        : (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"5"		        : (self.episodeList, "Episoden der ausgewählten Serie anzeigen"),
			"6"		        : (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		        : (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"8"		        : (self.updateMarkers, "Serien-Marker aktualisieren"),
			"9"		        : (self.disableAll, "Alle Serien-Marker für diese Box-ID deaktivieren"),
		}

		if not self.showMainScreen:
			actions["cancel_long"] = (self.keyExit, "zurück zur Serienplaner-Ansicht")

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", actions, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.modus = "menu_list"
		self.changesMade = False
		self.loading = True
		self.selected_serien_wlid = toBeSelect

		self.onShow.append(self.checkLastMarkerUpdate)

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.readSerienMarker)

		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_green'].setText("Sender auswählen")
		self['text_ok'].setText("Staffel(n) auswählen")
		self['text_yellow'].setText("Sendetermine")
		self.num_bt_text[1][0] = "Serie suchen"
		self.num_bt_text[2][0] = "TVDB-ID ändern"
		self.num_bt_text[0][1] = "Episoden-Liste"
		self.num_bt_text[2][2] = "Timer suchen"
		self.num_bt_text[3][1] = "Marker aktualisieren"
		self.num_bt_text[4][1] = "Alle deaktivieren"
		self.num_bt_text[4][2] = "Setup Serie/global"
		self['text_red'].setText("Ein/Löschen")
		self['text_blue'].setText("Timer-Liste")
		if not self.showMainScreen:
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

	def markerSetup(self):
		if self['menu_list'].getCurrent() is None:
			return
		serien_id = self['menu_list'].getCurrent()[0][0]
		serien_name = self['menu_list'].getCurrent()[0][1]
		self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]
		serien_fsid = self['menu_list'].getCurrent()[0][13]
		self.session.openWithCallback(self.setupFinished, serienRecMarkerSetup, serien_name, self.selected_serien_wlid, serien_id, serien_fsid)

	def setupFinished(self, result):
		if result:
			self.changesMade = True
		self.readSerienMarker(self.selected_serien_wlid)
		return

	def getCurrentSelection(self):
		serien_name = self['menu_list'].getCurrent()[0][1]
		serien_wlid = self['menu_list'].getCurrent()[0][2]
		serien_fsid = self['menu_list'].getCurrent()[0][13]
		return serien_name, serien_wlid, serien_fsid

	def checkLastMarkerUpdate(self):
		markerLastUpdate = self.database.getMarkerLastUpdate()
		if (markerLastUpdate + 30 * 24 * 60 * 60) < int(time.time()):
			self.onShow.remove(self.checkLastMarkerUpdate)
			self.session.openWithCallback(self.executeUpdateMarkers, MessageBox, "Die Namen der Serien-Marker wurden vor mehr als 30 Tagen das letzte Mal aktualisiert, sollen sie jetzt aktualisiert werden?", MessageBox.TYPE_YESNO)

	def updateMarkers(self):
		self.session.openWithCallback(self.executeUpdateMarkers, MessageBox, "Sollen die Namen der Serien-Marker aktualisiert werden?", MessageBox.TYPE_YESNO)

	def executeUpdateMarkers(self, execute):
		if execute:
			updatedMarkers = self.database.updateSeriesMarker(True)
			self.readSerienMarker()
			message = "Es musste kein Serien-Marker aktualisiert werden."
			if len(updatedMarkers) > 0:
				message = "Es wurden %d Serien-Marker aktualisiert.\n\nEine Liste der geänderten Marker wurde ins Log geschrieben." % len(updatedMarkers)

			self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=10)
		else:
			self.database.setMarkerLastUpdate()

	def changeTVDBID(self):
		if self.loading:
			return

		from .SerienRecorderScreenHelpers import EditTVDBID
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		editTVDBID = EditTVDBID(self, self.session, serien_name, None, serien_wlid, serien_fsid)
		editTVDBID.changeTVDBID()

	def serieInfo(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_wlid:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, serien_name, serien_wlid, serien_fsid)
			#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
			#				  MessageBox.TYPE_INFO, timeout=10)

	def episodeList(self):
		if self.modus == "menu_list" and self['menu_list'].getCurrent():
			(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
			if serien_wlid:
				self.session.open(serienRecEpisodes, serien_name, serien_wlid)

	def wunschliste(self):
		if self['menu_list'].getCurrent() is None:
			return
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		super(self.__class__, self).wunschliste(serien_wlid)

	def resetTransmissions(self):
		if self['menu_list'].getCurrent() is None:
			return
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_wlid:
			if SeriesServer().resetLastEPGUpdate(serien_wlid):
				self.session.open(MessageBox, "Die Sendetermine für ' %s ' wurden zurückgesetzt." % serien_name, MessageBox.TYPE_INFO, timeout=5)
			else:
				self.session.open(MessageBox, "Fehler beim Zurücksetzen der Sendetermine für ' %s '." % serien_name, MessageBox.TYPE_ERROR, timeout=5)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

		if result[1]:
			self.readSerienMarker()

	def getCover(self):
		if self.loading or self.modus == "popup_list" or self['menu_list'].getCurrent() is None:
			return

		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		from .SerienRecorder import getCover
		getCover(self, serien_name, serien_wlid, serien_fsid)

	def readSerienMarker(self, selectedSeriesWLID=None):
		if selectedSeriesWLID:
			self.selected_serien_wlid = selectedSeriesWLID

		numberOfDeactivatedSeries, markerList = self.getMarkerList(self.database)
		self['title'].setText("Serien-Marker - %d/%d Serien vorgemerkt." % (len(markerList)-numberOfDeactivatedSeries, len(markerList)))
		if len(markerList) != 0:
			self.chooseMenuList.setList(list(map(self.buildList, markerList)))
			if self.selected_serien_wlid:
				try:
					idx = list(zip(*markerList))[2].index(str(self.selected_serien_wlid))
					self['menu_list'].moveToIndex(idx)
				except Exception:
					pass
			self.loading = False
			self.setMenuKeyText()
			self.getCover()

	@staticmethod
	def getMarkerList(database):
		markerList = []
		numberOfDeactivatedSeries = 0
		
		markers = database.getAllMarkers(True if config.plugins.serienRec.markerSort.value == '1' else False)		
		for marker in markers:
			(ID, Serie, Info, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, ErlaubteStaffelCount, fsID) = marker
			if alleSender:
				sender = ['Alle',]
			else:
				sender = database.getMarkerChannels(Url, False)

			if AlleStaffelnAb == -2: 		# 'Manuell'
				staffeln = ['Manuell',]
			elif AlleStaffelnAb == 0:		# 'Alle'
				staffeln = ['Alle',]
			else:
				staffeln = []
				if ErlaubteStaffelCount > 0:
					staffeln = database.getAllowedSeasons(ID, AlleStaffelnAb)
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

			staffeln = ', '.join(str(staffel) for staffel in staffeln)
			sender = ', '.join(sender)

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

			markerList.append((ID, Serie, Url, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, bool(useAlternativeChannel), SerieAktiviert, Info, fsID))

		return numberOfDeactivatedSeries, markerList
	
	
	def buildList(self, entry):
		(ID, serie, url, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel, SerieAktiviert, info, fsID) = entry

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

		senderText = "Sender (%s): %s" % (senderText, sender)
		staffelText = "Staffel: %s" % staffeln
		infoText = "Wdh./Vorl./Nachl.: %s / %s / %s" % (int(AnzahlAufnahmen) - 1, int(Vorlaufzeit), int(Nachlaufzeit))
		folderText = "Dir: %s" % AufnahmeVerzeichnis

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, int(config.plugins.serienRec.markerNameInset.value), 3, (410 + self.columnWidth) * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, serieColor, serieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, (470 + self.columnWidth) * skinFactor, 3, (380 + self.columnWidth) * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, info, serieColor, serieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29 * skinFactor, (410 + self.columnWidth) * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffelText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, (470 + self.columnWidth) * skinFactor, 29 * skinFactor, (380 + self.columnWidth) * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, senderText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 49 * skinFactor, (410 + self.columnWidth) * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, infoText, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, (470 + self.columnWidth) * skinFactor, 49 * skinFactor, (380 + self.columnWidth) * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, folderText, foregroundColor, foregroundColor)
			]

	def keyCheck(self):
		if self['menu_list'].getCurrent() is None:
			print("[SerienRecorder] Serien-Marker Tabelle leer.")
			return
		if self.modus == "menu_list":
			from .SerienRecorderAutoCheckScreen import serienRecRunAutoCheckScreen
			self.session.openWithCallback(self.readSerienMarker, serienRecRunAutoCheckScreen, False)

	def keyOK(self):
		if self.modus == "popup_list":	# Staffel
			self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]
			select_staffel = self['popup_list'].getCurrent()[0][0]
			select_mode = self['popup_list'].getCurrent()[0][1]
			select_index = self['popup_list'].getCurrent()[0][2]
			print(select_staffel, select_mode)
			if select_mode == 0:
				select_mode = 1
			else:
				select_mode = 0

			self.staffel_liste[select_index] = list(self.staffel_liste[select_index])
			self.staffel_liste[select_index][1] = select_mode

			if select_mode == 1:
				deselectRange = None
				if select_index == 0:	# 'Manuell'
					# Disable all other special rows
					deselectRange = list(range(1, 3))
				if select_index == 1:	# Alle
					# Disable 'Manuell' and 'folgende'
					deselectRange = [0, 3]
				if select_index == 2:  # Specials
					# Disable 'Manuell' and 'Alle'
					deselectRange = [0, 1]
				if select_index == 4:  # 0
					# Disable 'Manuell', 'Alle' and 'folgende'
					deselectRange = [0, 1, 3]

				if deselectRange:
					for index in deselectRange:
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0

				if select_index == 0 or select_index == 1 or select_index == 4:  # 'Manuell', 'Alle' or '0'
					for index in range((5 if select_index == 4 else 4), len(self.staffel_liste)):
						# Disable all other season rows
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0

				if select_index >= 3:	# Any season
					for index in [0, 1]:
						# Disable 'Manuell' and 'Alle'
						self.staffel_liste[index] = list(self.staffel_liste[index])
						self.staffel_liste[index][1] = 0

			self.chooseMenuList_popup.setList(list(map(self.buildList2, self.staffel_liste)))
		elif self.modus == "popup_list2":	# Sender
			self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]
			select_sender = self['popup_list'].getCurrent()[0][0]
			select_mode = self['popup_list'].getCurrent()[0][1]
			select_index = self['popup_list'].getCurrent()[0][2]
			print(select_sender, select_mode)
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
			self.chooseMenuList_popup.setList(list(map(self.buildList2, self.sender_liste)))
		else:
			self.staffelSelect()

	def staffelSelect(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				print("[SerienRecorder] Serien-Marker Tabelle leer.")
				return

			self.modus = "popup_list"
			self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]
			self['popup_list'].show()
			self['popup_bg'].show()
			
			staffeln = ["Manuell", "Alle (inkl. Specials)", "Specials", "Staffeln ab"]
			staffeln.extend(list(range(config.plugins.serienRec.max_season.value+1)))
			mode_list = [0,]*len(staffeln)
			index_list = list(range(len(staffeln)))
			(ID, AlleStaffelnAb, self.AbEpisode, TimerForSpecials) = self.database.getMarkerSeasonSettings(self.selected_serien_wlid)

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
			self.staffel_liste = list(zip(staffeln, mode_list, index_list))
			self.chooseMenuList_popup.setList(list(map(self.buildList2, self.staffel_liste)))

	@staticmethod
	def buildList2(entry):
		(staffel, mode, index) = entry
		serienRecMainPath = os.path.dirname(__file__)
		if int(mode) == 0:
			imageMode = "%s/images/minus.png" % serienRecMainPath
		else:
			imageMode = "%s/images/plus.png" % serienRecMainPath

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 7 * skinFactor, 30 * skinFactor, 17 * skinFactor, loadPNG(imageMode)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 0, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(staffel).zfill(2))
			]

	def keyGreen(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				print("[SerienRecorder] Serien-Marker Tabelle leer.")
				return

			activeChannels = self.database.getActiveChannels()
			if len(activeChannels) != 0:
				self.modus = "popup_list2"
				self['popup_list'].show()
				self['popup_bg'].show()
				self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]

				activeChannels.insert(0, 'Alle')
				mode_list = [0,]*len(activeChannels)
				index_list = list(range(len(activeChannels)))
				channels = self.database.getMarkerChannels(self.selected_serien_wlid, False)
				if len(channels) > 0:
					for channel in channels:
						if channel in activeChannels:
							idx = activeChannels.index(channel)
							mode_list[idx] = 1
				else:
					# No channels assigned to marker => Alle
					mode_list[0] = 1

				self.sender_liste = list(zip(activeChannels, mode_list, index_list))
				self.chooseMenuList_popup.setList(list(map(self.buildList2, self.sender_liste)))

	def callTimerAdded(self, answer):
		if answer:
			self.changesMade = True
			
	def keyYellow(self):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		if serien_name and serien_wlid:
			from .SerienRecorderTransmissionsScreen import serienRecSendeTermine
			self.session.openWithCallback(self.callTimerAdded, serienRecSendeTermine, serien_name, serien_wlid, serien_fsid)

	def callDisableAll(self, answer):
		if answer:
			self.database.disableAllMarkers(config.plugins.serienRec.BoxID.value)
			self.readSerienMarker()
		else:
			return

	def callSaveMsg(self, answer):
		if answer:
			(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
			serien_info = self['menu_list'].getCurrent()[0][12]
			self.session.openWithCallback(self.callDelMsg, MessageBox, "Die Timer Einträge für '%s (%s)' auch aus der Datenbank löschen?" % (serien_name, serien_info), MessageBox.TYPE_YESNO, default = False)
		else:
			return

	def callDelMsg(self, answer):
		(serien_name, serien_wlid, serien_fsid) = self.getCurrentSelection()
		self.removeSerienMarker(serien_fsid, serien_name, answer)
		
	def removeSerienMarker(self, serien_fsid, serien_name, answer):
		serien_info = self['menu_list'].getCurrent()[0][12]
		serienRecMarker.doRemoveSerienMarker(serien_fsid, serien_name, serien_info, answer)
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Marker für '%s (%s)' wurde gelöscht." % (serien_name, serien_info))
		self.readSerienMarker()	

	@staticmethod
	def doRemoveSerienMarker(serien_fsid, serien_name, serien_info, withTimer):
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		database.removeMarker(serien_fsid, withTimer)
		from .SerienRecorderLogWriter import SRLogger
		SRLogger.writeLog("Der Serien-Marker für '%s (%s)' wurde gelöscht" % (serien_name, serien_info), True)

	def keyRed(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				print("[SerienRecorder] Serien-Marker Tabelle leer.")
				return
			else:
				self.selected_serien_wlid = self['menu_list'].getCurrent()[0][2]
				self.database.changeMarkerStatus(self.selected_serien_wlid, config.plugins.serienRec.BoxID.value)
				self.readSerienMarker(self.selected_serien_wlid)
					
	def keyRedLong(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				print("[SerienRecorder] Serien-Marker Tabelle leer.")
				return
			else:
				self.selected_serien_wlid = None
				serien_name = self['menu_list'].getCurrent()[0][1]
				serien_info = self['menu_list'].getCurrent()[0][12]
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.callSaveMsg, MessageBox, "Den Serien-Marker für '%s (%s)' wirklich löschen?" % (serien_name, serien_info), MessageBox.TYPE_YESNO, default = False)
				else:
					self.session.openWithCallback(self.callDelMsg, MessageBox, "Die Timer Einträge für '%s (%s)' auch aus der Datenbank löschen?" % (serien_name, serien_info), MessageBox.TYPE_YESNO, default = False)

	def disableAll(self):
		if self.modus == "menu_list":
			if self['menu_list'].getCurrent() is None:
				print("[SerienRecorder] Serien-Marker Tabelle leer.")
				return
			else:
				self.session.openWithCallback(self.callDisableAll, MessageBox, "Alle Serien-Marker für diese Box deaktivieren?", MessageBox.TYPE_YESNO, default = False)

	def insertStaffelMarker(self):
		(ID, AlleStaffelnAb, AbEpisode, TimerForSpecials) = self.database.getMarkerSeasonSettings(self.selected_serien_wlid)
		if ID:
			self.database.removeAllMarkerSeasons(self.selected_serien_wlid)
			liste = self.staffel_liste[1:]
			print("[SerienRecorder] insertStaffelMarker")
			#print(liste)
			liste = list(zip(*liste))
			#print(liste)
			if 1 in liste[1]:
				TimerForSpecials = 0
				AlleStaffelnAb = 999999
				#staffel_liste = ['Manuell','Alle','Specials','folgende',...]
				for row in self.staffel_liste:
					(staffel, mode, index) = row
					if mode == 1:
						if index == 0:	# 'Manuell'
							AlleStaffelnAb = -2
							AbEpisode = 0
							TimerForSpecials = 0
							break
						if index == 1:		# 'Alle'
							AlleStaffelnAb = 0
							AbEpisode = 0
							TimerForSpecials = 0
							break
						if index == 2:		#'Specials'
							TimerForSpecials = 1
						if index == 3:		#'folgende'
							liste = self.staffel_liste[5:]
							liste.reverse()
							liste = list(zip(*liste))
							if 1 in liste[1]:
								idx = liste[1].index(1)
								AlleStaffelnAb = liste[0][idx]
						if index > 4:
							if staffel != AlleStaffelnAb:
								self.database.setMarkerSeason(ID, staffel)
					else:
						if index == 4:
							AbEpisode = 0

			else:
				AlleStaffelnAb = -2
				AbEpisode = 0

			if AlleStaffelnAb == -2: # 'Manuell'
				self.session.open(MessageBox, "Mit dieser Einstellung ('Manuell') werden für diesen\nSerien-Marker keine Timer mehr automatisch angelegt!", MessageBox.TYPE_INFO, timeout=10)

		self.database.updateMarkerSeasonsSettings(self.selected_serien_wlid, AlleStaffelnAb, AbEpisode, TimerForSpecials)

		self.changesMade = True
		self.readSerienMarker()

	def insertMarkerChannels(self):
		alleSender = 0
		self.database.removeAllMarkerChannels(self.selected_serien_wlid)
		markerID = self.database.getMarkerID(self.selected_serien_wlid)
		liste = self.sender_liste[1:]
		liste = list(zip(*liste))
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

		self.database.setAllChannelsToMarker(self.selected_serien_wlid, alleSender)

		self.changesMade = True
		self.readSerienMarker()

	def keyBlue(self):
		if self.modus == "menu_list":
			from .SerienRecorderTimerListScreen import serienRecTimerListScreen
			self.session.openWithCallback(self.readSerienMarker, serienRecTimerListScreen)

	def searchSeries(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			#print serien_name
			self.changesMade = True
			from .SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			self.session.openWithCallback(self.readSerienMarker, serienRecSearchResultScreen, serien_name)

	def setMenuKeyText(self):
		active = self['menu_list'].getCurrent()[0][11]
		if active:
			self['text_red'].setText("Aus/Löschen")
		else:
			self['text_red'].setText("Ein/Löschen")

	def keyLeft(self):
		if self.modus == "popup_list2":
			self["popup_list"].pageUp()
		else:
			self[self.modus].pageUp()
			self.getCover()
			self.setMenuKeyText()

	def keyRight(self):
		if self.modus == "popup_list2":
			self["popup_list"].pageDown()
		else:
			self[self.modus].pageDown()
			self.getCover()
			self.setMenuKeyText()

	def keyDown(self):
		if self.modus == "popup_list2":
			self["popup_list"].down()
		else:
			self[self.modus].down()
			self.getCover()
			self.setMenuKeyText()

	def keyUp(self):
		if self.modus == "popup_list2":
			self["popup_list"].up()
		else:
			self[self.modus].up()
			self.getCover()
			self.setMenuKeyText()

	def selectEpisode(self, episode):
		if str(episode).isdigit():
			self.database.setMarkerEpisode(self.selected_serien_wlid, episode)
		self.insertStaffelMarker()
			
	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyExit(self):
		if self.modus == "popup_list" or self.modus == "popup_list2":
			self.keyCancel()
		else:
			print("[SerienRecorder] MarkerScreen exit")
			from . import SerienRecorderMainScreen
			SerienRecorderMainScreen.showMainScreen = True
			self.close(self.changesMade)

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "menu_list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			if (self.staffel_liste[0][1] == 0) and (self.staffel_liste[1][1] == 0) and (self.staffel_liste[4][1] == 1):		# nicht ('Manuell' oder 'Alle') und '00'
				self.session.openWithCallback(self.selectEpisode, NTIVirtualKeyBoard, title = "Die Episode eingeben ab der Timer erstellt werden sollen:", text = str(self.AbEpisode))
			else:
				self.insertStaffelMarker()
		elif self.modus == "popup_list2":
			self.modus = "menu_list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.insertMarkerChannels()
		else:
			self.close(self.changesMade)


