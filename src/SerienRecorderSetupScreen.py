# coding=utf-8

# This file contains the SerienRecoder Season Begin Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config, ConfigInteger, getConfigListEntry, ConfigText, ConfigYesNo, configfile, ConfigSelection, ConfigSubsection, NoSave, ConfigClock, ConfigSelectionNumber
from Tools import Notifications
from Tools.Directories import fileExists

import time, shutil, os, re, random

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, setSkinProperties, SelectSkin
from .SerienRecorderHelpers import encrypt, STBHelpers, isDreamOS, SRVERSION, SRDBVERSION, SRAPIVERSION
from .SerienRecorder import setDataBaseFilePath, getDataBaseFilePath

def CheckChoices(choices, default):
	for choice in choices:
		if default == choice[0]:
			return default

	return choices[0][0]

def ReadConfigFile():
	try:
		default_before = int(config.recording.margin_before.value)
		default_after = int(config.recording.margin_after.value)
	except:
		default_before = 0
		default_after = 0

	from .SerienRecorderPatterns import readTimerPatterns
	timer_patterns = readTimerPatterns()
	pattern_title_choices = timer_patterns
	pattern_title_default = CheckChoices(pattern_title_choices, "{serie:s} - S{staffel:s}E{episode:s} - {titel:s}")
	pattern_description_choices = timer_patterns
	pattern_description_default = CheckChoices(pattern_description_choices, "S{staffel:s}E{episode:s} - {titel:s}")

	config.plugins.serienRec = ConfigSubsection()

	###############################################################################################################################
	# SYSTEM
	###############################################################################################################################
	config.plugins.serienRec.BoxID = ConfigSelectionNumber(1, 16, 1, default=1)
	config.plugins.serienRec.activateNewOnThisSTBOnly = ConfigYesNo(default=False)
	config.plugins.serienRec.savetopath = ConfigText(default="/media/hdd/movie/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.seriensubdir = ConfigYesNo(default=False)
	config.plugins.serienRec.seriensubdirwithyear = ConfigYesNo(default=True)
	config.plugins.serienRec.seasonsubdir = ConfigYesNo(default=False)
	config.plugins.serienRec.seasonsubdirnumerlength = ConfigInteger(1, (1, 4))
	config.plugins.serienRec.seasonsubdirfillchar = ConfigSelection(choices=[("0", "'0'"), ("<SPACE>", "<SPACE>")], default="0")
	config.plugins.serienRec.Autoupdate = ConfigYesNo(default=True)
	config.plugins.serienRec.databasePath = ConfigText(default="/etc/enigma2/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.AutoBackup = ConfigSelection(choices=[("0", "Nein"), ("before", "Vor dem Timer-Suchlauf"), ("after", "Nach dem Timer-Suchlauf")], default="before")
	config.plugins.serienRec.BackupPath = ConfigText(default="/media/hdd/SR_Backup/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.deleteBackupFilesOlderThan = ConfigInteger(5, (5, 999))

	###############################################################################################################################
	# TIMER-SUCHLAUF
	###############################################################################################################################
	try:
		# Remove EPGRefresh action for VU+ Boxes
		from Tools.HardwareInfoVu import HardwareInfoVu
		config.plugins.serienRec.autochecktype = ConfigSelection(choices=[("0", "Manuell"), ("1", "Zur gewählten Uhrzeit")], default="0")
	except:
		config.plugins.serienRec.autochecktype = ConfigSelection(choices=[("0", "Manuell"), ("1", "Zur gewählten Uhrzeit"), ("2", "Nach EPGRefresh")], default="0")
	config.plugins.serienRec.deltime = ConfigClock(default=(random.randint(1, 23) * 3600) + time.timezone)
	config.plugins.serienRec.maxDelayForAutocheck = ConfigInteger(15, (0, 60))
	config.plugins.serienRec.checkfordays = ConfigInteger(1, (1, 14))
	config.plugins.serienRec.globalFromTime = ConfigClock(default=0 + time.timezone)
	config.plugins.serienRec.globalToTime = ConfigClock(default=(((23 * 60) + 59) * 60) + time.timezone)
	config.plugins.serienRec.eventid = ConfigYesNo(default=True)
	config.plugins.serienRec.epgTimeSpan = ConfigInteger(10, (0, 30))
	config.plugins.serienRec.forceRecording = ConfigYesNo(default=False)
	config.plugins.serienRec.TimeSpanForRegularTimer = ConfigInteger(7, (int(config.plugins.serienRec.checkfordays.value), 999))
	config.plugins.serienRec.NoOfRecords = ConfigInteger(1, (1, 9))
	config.plugins.serienRec.selectNoOfTuners = ConfigYesNo(default=True)
	config.plugins.serienRec.tuner = ConfigInteger(4, (1, 8))
	config.plugins.serienRec.wakeUpDSB = ConfigYesNo(default=False)
	config.plugins.serienRec.afterAutocheck = ConfigSelection(choices=[("0", "Keine"), ("1", "In Standby gehen"), ("2", "In Deep-Standby gehen")], default="0")
	config.plugins.serienRec.DSBTimeout = ConfigInteger(20, (0, 999))

	###############################################################################################################################
	# E-MAIL
	###############################################################################################################################
	config.plugins.serienRec.tvplaner = ConfigYesNo(default=False)
	config.plugins.serienRec.imap_server = ConfigText(default="", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_server_ssl = ConfigYesNo(default=True)
	config.plugins.serienRec.imap_server_port = ConfigInteger(993, (1, 65535))
	config.plugins.serienRec.imap_login = ConfigText(default="", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_login_hidden = ConfigText(default="", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_password = ConfigText(default="", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_password_hidden = ConfigText(default="", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_mailbox = ConfigText(default="INBOX", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_test = NoSave(ConfigSelection(choices=[("", "OK zum Testen")], default=""))
	config.plugins.serienRec.imap_mail_subject = ConfigText(default="TV Wunschliste TV-Planer", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_mail_age = ConfigInteger(0, (0, 100))
	config.plugins.serienRec.tvplaner_full_check = ConfigYesNo(default=False)
	config.plugins.serienRec.tvplaner_skipSerienServer = ConfigYesNo(default=False)
	config.plugins.serienRec.tvplaner_series = ConfigYesNo(default=True)
	config.plugins.serienRec.tvplaner_series_activeSTB = ConfigYesNo(default=False)
	config.plugins.serienRec.tvplaner_movies = ConfigYesNo(default=True)
	config.plugins.serienRec.tvplaner_movies_activeSTB = ConfigYesNo(default=False)
	config.plugins.serienRec.tvplaner_movies_filepath = ConfigText(default="/media/hdd/movie/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.tvplaner_movies_createsubdir = ConfigYesNo(default=False)

	###############################################################################################################################
	# TIMER
	###############################################################################################################################
	config.plugins.serienRec.afterEvent = ConfigSelection(choices=[("0", "Nichts"), ("1", "In Standby gehen"), ("2", "In Deep-Standby gehen"), ("3", "Automatisch")], default="3")
	config.plugins.serienRec.margin_before = ConfigInteger(default_before, (0, 99))
	config.plugins.serienRec.margin_after = ConfigInteger(default_after, (0, 99))
	#config.plugins.serienRec.TimerName = ConfigSelection(choices=[("0", "<Serienname> - SnnEmm - <Episodentitel>"), ("1", "<Serienname>"), ("2", "SnnEmm - <Episodentitel>"), ("3", "<Serienname> - SnnEmm")], default="0")
	#config.plugins.serienRec.TimerDescription = ConfigSelection(choices=[("0", "SnnEmm - <Episodentitel>"), ("1", "<Episodentitel>")], default="0")
	config.plugins.serienRec.TimerName = ConfigSelection(choices=pattern_title_choices, default=pattern_title_default)
	config.plugins.serienRec.TimerDescription = ConfigSelection(choices=pattern_description_choices, default=pattern_description_default)
	config.plugins.serienRec.forceManualRecording = ConfigYesNo(default=False)
	config.plugins.serienRec.splitEventTimer = ConfigSelection(choices=[("0", "Nein"), ("1", "Timer anlegen"), ("2", "Einzelepisoden bevorzugen")], default="0")
	config.plugins.serienRec.addSingleTimersForEvent = ConfigSelection(choices=[("0", "Nein"), ("1", "Ja")], default="0")
	config.plugins.serienRec.selectBouquets = ConfigYesNo(default=False)

	boxBouquets = STBHelpers.getTVBouquets()
	# boxBouquets = [('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet', 'FTA TV D Astra'), ('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.dbe2.tv" ORDER BY bouquet', 'Sky Entertain'),...]
	# get name only
	choices = [(x[1], x[1]) for x in boxBouquets]
	if len(choices) > 0:
		config.plugins.serienRec.MainBouquet = ConfigSelection(choices=choices, default=choices[0][0])
	else:
		config.plugins.serienRec.MainBouquet = ConfigSelection(choices=choices)
	if len(choices) > 1:
		config.plugins.serienRec.AlternativeBouquet = ConfigSelection(choices=choices, default=choices[1][0])
	else:
		config.plugins.serienRec.AlternativeBouquet = ConfigSelection(choices=choices)
	config.plugins.serienRec.useAlternativeChannel = ConfigYesNo(default=False)
	config.plugins.serienRec.preferMainBouquet = ConfigYesNo(default=False)

	###############################################################################################################################
	# OPTIMIERUNGEN
	###############################################################################################################################
	config.plugins.serienRec.intensiveTimersuche = ConfigYesNo(default=True)
	config.plugins.serienRec.sucheAufnahme = ConfigYesNo(default=False)

	###############################################################################################################################
	# BENUTZEROBERFLÄCHE
	###############################################################################################################################
	skins = [("Skinpart", "Skinpart"), ("", "SerienRecorder 1"), ("Skin2", "SerienRecorder 2"),
	         ("AtileHD", "AtileHD"), ("StyleFHD", "StyleFHD"), ("Black Box", "Black Box")]
	try:
		t = list(os.walk("%s/skins" % os.path.dirname(__file__)))
		for x in t[0][1]:
			if x not in ("Skin2", "AtileHD", "StyleFHD", "Black Box"):
				skins.append((x, x))
	except:
		pass

	config.plugins.serienRec.SkinType = ConfigSelection(choices=skins, default="")
	config.plugins.serienRec.showAllButtons = ConfigYesNo(default=False)
	config.plugins.serienRec.DisplayRefreshRate = ConfigInteger(10, (1, 60))
	config.plugins.serienRec.firstscreen = ConfigSelection(choices=[("0", "SerienPlaner"), ("1", "SerienMarker")], default="0")
	config.plugins.serienRec.showPicons = ConfigSelection(choices=[("0", "Nein"), ("1", "Ja, über ServiceRef"), ("2", "Ja, über Name")], default="1")
	config.plugins.serienRec.piconPath = ConfigText(default="/usr/share/enigma2/picon/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.downloadCover = ConfigYesNo(default=False)
	config.plugins.serienRec.coverPath = ConfigText(default="/media/hdd/SR_Cover/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.showCover = ConfigYesNo(default=False)
	config.plugins.serienRec.createPlaceholderCover = ConfigYesNo(default=True)
	config.plugins.serienRec.refreshPlaceholderCover = ConfigYesNo(default=False)
	config.plugins.serienRec.copyCoverToFolder = ConfigSelection(choices=[("0", "Nein"), ("1", "folder.jpg"), ("2", "series.jpg")], default="1")
	config.plugins.serienRec.listFontsize = ConfigSelectionNumber(-5, 35, 1, default=0)
	config.plugins.serienRec.markerColumnWidth = ConfigSelectionNumber(-200, 200, 10, default=0)
	config.plugins.serienRec.markerNameInset = ConfigSelectionNumber(0, 80, 1, default=40)
	config.plugins.serienRec.seasonFilter = ConfigYesNo(default=False)
	config.plugins.serienRec.timerFilter = ConfigYesNo(default=False)
	config.plugins.serienRec.markerSort = ConfigSelection(choices=[("0", "Alphabetisch"), ("1", "Wunschliste")], default="0")
	config.plugins.serienRec.max_season = ConfigInteger(30, (1, 999))
	config.plugins.serienRec.openMarkerScreen = ConfigYesNo(default=True)
	config.plugins.serienRec.confirmOnDelete = ConfigYesNo(default=True)
	config.plugins.serienRec.enableWebinterface = ConfigYesNo(default=False)

	###############################################################################################################################
	# MELDUNGEN
	###############################################################################################################################
	config.plugins.serienRec.showNotification = ConfigSelection(choices=[("0", "Keine"), ("1", "Bei Suchlauf-Ende"), ("2", "Statistik bei Suchlauf-Ende")], default="1")
	config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default=True)
	config.plugins.serienRec.showMessageOnTVPlanerError = ConfigYesNo(default=True)
	config.plugins.serienRec.showMessageOnEventNotFound = ConfigYesNo(default=False)
	config.plugins.serienRec.showMessageTimeout = ConfigInteger(0, (0, 60))
	config.plugins.serienRec.channelUpdateNotification = ConfigSelection(choices=[("0", "Beim Start"), ("1", "Nach dem Timer-Suchlauf")], default="0")

	###############################################################################################################################
	# LOGGING
	###############################################################################################################################
	config.plugins.serienRec.LogFilePath = ConfigText(default=os.path.dirname(__file__), fixed_size=False, visible_width=80)
	config.plugins.serienRec.longLogFileName = ConfigYesNo(default=False)
	config.plugins.serienRec.deleteLogFilesOlderThan = ConfigInteger(14, (0, 999))
	config.plugins.serienRec.writeLog = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogVersion = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogChannels = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogAllowedEpisodes = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogAdded = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogDisk = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogTimeRange = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogTimeLimit = ConfigYesNo(default=True)
	config.plugins.serienRec.writeLogTimerDebug = ConfigYesNo(default=True)
	config.plugins.serienRec.tvplaner_backupHTML = ConfigYesNo(default=True)
	config.plugins.serienRec.logScrollLast = ConfigYesNo(default=False)
	config.plugins.serienRec.logWrapAround = ConfigYesNo(default=False)

	###############################################################################################################################

	config.plugins.serienRec.tvplaner_last_full_check = ConfigInteger(0)

	config.plugins.serienRec.justplay = ConfigYesNo(default=False)
	config.plugins.serienRec.justremind = ConfigYesNo(default=False)
	config.plugins.serienRec.zapbeforerecord = ConfigYesNo(default=False)
	config.plugins.serienRec.timeUpdate = ConfigYesNo(default=False)

	config.plugins.serienRec.showAdvice = ConfigYesNo(default=True)
	config.plugins.serienRec.showStartupInfoText = ConfigYesNo(default=True)

	# INTERNAL
	config.plugins.serienRec.showversion = NoSave(ConfigText(default=SRVERSION))
	config.plugins.serienRec.screenplaner = ConfigInteger(1, (1, 2))
	config.plugins.serienRec.recordListView = ConfigInteger(0, (0, 1))
	config.plugins.serienRec.addedListSorted = ConfigYesNo(default=False)
	config.plugins.serienRec.wishListSorted = ConfigYesNo(default=False)
	config.plugins.serienRec.serienRecShowSeasonBegins_filter = ConfigYesNo(default=False)

	# OBSOLETE
	config.plugins.serienRec.dbversion = NoSave(ConfigText(default=SRDBVERSION))
	config.plugins.serienRec.bouquetList = NoSave(ConfigText(default=""))
	config.plugins.serienRec.deleteOlderThan = NoSave(ConfigInteger(7, (1, 99)))
	config.plugins.serienRec.imap_check_interval = NoSave(ConfigInteger(30, (0, 10000)))
	config.plugins.serienRec.planerCacheEnabled = NoSave(ConfigYesNo(default=True))
	config.plugins.serienRec.planerCacheSize = NoSave(ConfigInteger(1, (1, 4)))
	config.plugins.serienRec.readdatafromfiles = NoSave(ConfigYesNo(default=False))
	config.plugins.serienRec.refreshViews = NoSave(ConfigYesNo(default=True))
	config.plugins.serienRec.setupType = NoSave(ConfigSelection(choices=[("0", "Einfach"), ("1", "Experte")], default="1"))
	config.plugins.serienRec.tvplaner_create_marker = NoSave(ConfigYesNo(default=True))
	config.plugins.serienRec.updateInterval = NoSave(ConfigInteger(24, (0, 24)))

	if config.plugins.serienRec.screenplaner.value > 2:
		config.plugins.serienRec.screenplaner.value = 1
	config.plugins.serienRec.screenplaner.save()

	if config.plugins.serienRec.showCover.value:
		config.plugins.serienRec.downloadCover.value = True
	config.plugins.serienRec.downloadCover.save()

	if config.plugins.serienRec.epgTimeSpan.value > 30:
		config.plugins.serienRec.epgTimeSpan.value = 30
	config.plugins.serienRec.epgTimeSpan.save()

	configfile.save()

	SelectSkin()


class ConfigListHC(ConfigList):
	def __init__(self, list, session=None):
		ConfigList.__init__(self, list, session=session)

	def jumpToPreviousSection(self):
		index = self.getCurrentIndex() - 1
		maxlen = len(self._ConfigList__list)
		while index >= 0 and maxlen > 0:
			index -= 1
			# fix jump to PreviousSection on empty lines in ConfigList
			if index in self._headers and self.list[index] != ("",):
				if index + 1 < maxlen:
					self.setCurrentIndex(index + 1)
					return
				else:
					self.setCurrentIndex(index - 1)
					return
		self.pageUp()

class serienRecSetup(serienRecBaseScreen, Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, readConfig=False):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.skin = None
		self.bouquetList = []
		self.session = session
		self.list = []
		self.HilfeTexte = {}
		self.num_bt_text = ()
		self.tvplaner_full_check = None
		self.checkfordays = None
		self.tvbouquets = STBHelpers.getTVBouquets()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"	: (self.keyOK, "Fenster für Verzeichnisauswahl öffnen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"red": (self.keyRed, "alle Einstellungen auf die Standardwerte zurücksetzen"),
			"green": (self.save, "Einstellungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "Einstellungen in Datei speichern"),
			"blue": (self.keyBlue, "Einstellungen aus Datei laden"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"startTeletext" : (self.showAbout, "Über dieses Plugin"),
			"menu"	: (self.openChannelSetup, "Sender zuordnen"),
			"nextBouquet":	(self.bouquetPlus, "zur vorherigen Seite blättern"),
			"prevBouquet":	(self.bouquetMinus, "zur nächsten Seite blättern"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		if readConfig:
			ReadConfigFile()

		self.setupSkin()

		self.setupModified = False
		self.SkinType = config.plugins.serienRec.SkinType.value

		self.__C_JUSTPLAY__ = 0
		self.__C_ZAPBEFORERECORD__ = 1
		self.__C_JUSTREMIND__ = 2

		kindOfTimer_default = 0
		if config.plugins.serienRec.zapbeforerecord.value:
			kindOfTimer_default |= (1 << self.__C_ZAPBEFORERECORD__)
			config.plugins.serienRec.justplay.value = False
			config.plugins.serienRec.justremind.value = False
		elif config.plugins.serienRec.justplay.value:
			kindOfTimer_default |= (1 << self.__C_JUSTPLAY__)
			config.plugins.serienRec.justremind.value = False
			config.plugins.serienRec.zapbeforerecord.value = False
		elif config.plugins.serienRec.justremind.value:
			kindOfTimer_default |= (1 << self.__C_JUSTREMIND__)
			config.plugins.serienRec.justplay.value = False
			config.plugins.serienRec.zapbeforerecord.value = False
		self.kindOfTimer = ConfigSelection(choices = [("1", "umschalten"), ("0", "aufnehmen"), ("2", "umschalten und aufnehmen"), ("4", "Erinnerung")], default=str(kindOfTimer_default))

		config.plugins.serienRec.AutoBackup.addNotifier(self.onChangeConfigSelection, initial_call=False)
		config.plugins.serienRec.autochecktype.addNotifier(self.onChangeConfigSelection, initial_call=False)
		config.plugins.serienRec.showPicons.addNotifier(self.onChangeConfigSelection, initial_call=False)
		config.plugins.serienRec.splitEventTimer.addNotifier(self.onChangeConfigSelection, initial_call=False)
		config.plugins.serienRec.SkinType.addNotifier(self.onChangeConfigSelection, initial_call=False)

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self['config'] = ConfigListHC(self.list, self.session)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[config.plugins.serienRec.BoxID])

		if config.plugins.serienRec.showAdvice.value:
			self.onShown.append(self.showAdvice)
		self.onLayoutFinish.append(self.setSkinProperties)

	def showAdvice(self):
		self.onShown.remove(self.showAdvice)
		self.session.openWithCallback(self.switchOffAdvice, MessageBox, ("Die 'HILFE' Taste lange drücken um die Bedienungsanleitung zu öffnen.\n"
		                                                                 "\n"
		                                                                 "Soll dieser Hinweis noch einmal angezeigt werden?\n"), MessageBox.TYPE_YESNO, default = False)

	@staticmethod
	def switchOffAdvice(answer=False):
		if not answer:
			config.plugins.serienRec.showAdvice.value = False
		config.plugins.serienRec.showAdvice.save()
		configfile.save()

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, "Hilfe"],
		                    [buttonText_na, buttonText_na, "Sender zuordnen"])

		self['text_red'].setText("Defaultwerte")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Ordner auswählen")
		self['text_yellow'].setText("in Datei speichern")
		self['text_blue'].setText("aus Datei laden")

		super(self.__class__, self).startDisplayTimer()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def setupSkin(self):
		InitSkin(self)

		self['config'].show()

		self['config_information'].show()
		self['config_information_text'].show()

		self['title'].setText("SerienRecorder - Einstellungen:")

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()
		else:
			self['text_0'].hide()
			self['text_1'].hide()
			self['text_2'].hide()
			self['text_3'].hide()
			self['text_4'].hide()
			self['text_5'].hide()
			self['text_6'].hide()
			self['text_7'].hide()
			self['text_8'].hide()
			self['text_9'].hide()

			self['bt_0'].hide()
			self['bt_1'].hide()
			self['bt_2'].hide()
			self['bt_3'].hide()
			self['bt_4'].hide()
			self['bt_5'].hide()
			self['bt_6'].hide()
			self['bt_7'].hide()
			self['bt_8'].hide()
			self['bt_9'].hide()

	def keyRed(self):
		self.session.openWithCallback(self.resetSettings, MessageBox, "Wollen Sie die Einstellungen wirklich zurücksetzen?", MessageBox.TYPE_YESNO, default = False)

	def resetSettings(self, answer=False):
		if answer:
			writeSettings = open("/etc/enigma2/settings_new", "w")
			readSettings = open("/etc/enigma2/settings", "r")
			for rawData in readSettings.readlines():
				data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
				if not data:
					writeSettings.write(rawData)
			writeSettings.close()
			readSettings.close()

			if fileExists("/etc/enigma2/settings_new"):
				shutil.move("/etc/enigma2/settings_new", "/etc/enigma2/settings")

			configfile.load()
			ReadConfigFile()
			self.changedEntry()
			self.setupModified = True

	# self.save()

	def keyYellow(self):
		config.plugins.serienRec.save()
		serienRecMainPath = os.path.dirname(__file__)
		STBHelpers.saveEnigmaSettingsToFile(serienRecMainPath)
		self.session.open(MessageBox, "Die aktuelle Konfiguration wurde in der Datei 'Config.backup' im Verzeichnis '%s' gespeichert." % serienRecMainPath, MessageBox.TYPE_INFO, timeout = 10)

	def keyBlue(self):
		serienRecMainPath = os.path.dirname(__file__)
		self.session.openWithCallback(self.importSettings, MessageBox, "Soll die Konfiguration aus der Datei 'Config.backup' im Verzeichnis '%s' geladen werden?" % serienRecMainPath, MessageBox.TYPE_YESNO, default = False)

	def importSettings(self, answer=False):
		if answer:
			writeSettings = open("/etc/enigma2/settings_new", "w")

			readSettings = open("/etc/enigma2/settings", "r")
			for rawData in readSettings.readlines():
				data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
				if not data:
					writeSettings.write(rawData)

			serienRecMainPath = os.path.dirname(__file__)

			if fileExists("%s/Config.backup" % serienRecMainPath):
				readConfFile = open("%s/Config.backup" % serienRecMainPath, "r")
				for rawData in readConfFile.readlines():
					writeSettings.write(rawData)

				writeSettings.close()
				readSettings.close()

				if fileExists("/etc/enigma2/settings_new"):
					shutil.move("/etc/enigma2/settings_new", "/etc/enigma2/settings")

				configfile.load()
				ReadConfigFile()
				self.changedEntry()
				self.setupModified = True
			else:
				self.session.open(MessageBox, "Die Datei 'Config.backup' wurde im Verzeichnis '%s' nicht gefunden." % serienRecMainPath, MessageBox.TYPE_INFO, timeout = 10)

	def updateTextAndButtons(self):
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] in \
		(config.plugins.serienRec.savetopath, config.plugins.serienRec.tvplaner_movies_filepath,
		config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath,
		config.plugins.serienRec.databasePath, config.plugins.serienRec.piconPath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def onChangeConfigSelection(self, selection):
		if selection is not None:
			self.changedEntry()

	def bouquetPlus(self):
		if isDreamOS():
			self["config"].jumpToPreviousSection()
		else:
			self['config'].instance.moveSelection(self['config'].instance.pageUp)
		self.updateTextAndButtons()

	def bouquetMinus(self):
		if isDreamOS():
			self["config"].jumpToNextSection()
		else:
			self['config'].instance.moveSelection(self['config'].instance.pageDown)
		self.updateTextAndButtons()

	def onKeyUpDown(self, moveUp):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.checkfordays:
			x = int(config.plugins.serienRec.TimeSpanForRegularTimer.value)
			if int(config.plugins.serienRec.checkfordays.value) > x:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = int(
					config.plugins.serienRec.checkfordays.value)
			else:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = x
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_mail_age:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_server_port:
			self.changedEntry()

		if moveUp:
			if self['config'].instance.getCurrentIndex() <= 1:
				self['config'].instance.moveSelectionTo(len(self.list) - 1)
			else:
				self['config'].instance.moveSelection(self['config'].instance.moveUp)
		else:
			if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
				self['config'].instance.moveSelectionTo(0)
			else:
				self['config'].instance.moveSelection(self['config'].instance.moveDown)
		self.updateTextAndButtons()


	def keyDown(self):
		self.onKeyUpDown(False)

	def keyUp(self):
		self.onKeyUpDown(True)


	def onKeyLeftRight(self):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.forceRecording:
			self.setInfoText()
		if self['config'].getCurrent()[1] not in (config.plugins.serienRec.savetopath,
		                                          config.plugins.serienRec.tvplaner_movies_filepath,
		                                          config.plugins.serienRec.seasonsubdirnumerlength,
		                                          config.plugins.serienRec.coverPath,
		                                          config.plugins.serienRec.BackupPath,
		                                          config.plugins.serienRec.deleteBackupFilesOlderThan,
		                                          config.plugins.serienRec.deltime,
		                                          config.plugins.serienRec.maxDelayForAutocheck,
		                                          config.plugins.serienRec.imap_server,
		                                          config.plugins.serienRec.imap_server_port,
		                                          config.plugins.serienRec.imap_login,
		                                          config.plugins.serienRec.imap_password,
		                                          config.plugins.serienRec.imap_mailbox,
		                                          config.plugins.serienRec.imap_mail_subject,
		                                          config.plugins.serienRec.checkfordays,
		                                          config.plugins.serienRec.globalFromTime,
		                                          config.plugins.serienRec.globalToTime,
		                                          config.plugins.serienRec.TimeSpanForRegularTimer,
		                                          config.plugins.serienRec.margin_before,
		                                          config.plugins.serienRec.margin_after,
		                                          config.plugins.serienRec.max_season,
		                                          config.plugins.serienRec.DSBTimeout,
		                                          config.plugins.serienRec.LogFilePath,
		                                          config.plugins.serienRec.deleteLogFilesOlderThan,
		                                          config.plugins.serienRec.NoOfRecords,
		                                          config.plugins.serienRec.tuner):
			self.changedEntry()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.onKeyLeftRight()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.onKeyLeftRight()

	def createConfigList(self):
		self.list = []

		def addSection(name, hasConfigDescription = False):
			if not hasConfigDescription:
				self.list.append(getConfigListEntry("", ))
			if not isDreamOS():
				self.list.append(getConfigListEntry(name, ))
				self.list.append(getConfigListEntry(400 * "¯", ))
			else:
				self.list.append(getConfigListEntry(name, ))

		###############################################################################################################################
		addSection("SYSTEM", True)
		self.list.append(getConfigListEntry("ID der Box:", config.plugins.serienRec.BoxID))
		self.list.append(getConfigListEntry("Neue Serien-Marker nur auf dieser Box aktivieren:", config.plugins.serienRec.activateNewOnThisSTBOnly))
		self.list.append(getConfigListEntry("Speicherort der Serienaufnahmen:", config.plugins.serienRec.savetopath))
		self.list.append(getConfigListEntry("Serien-Verzeichnis anlegen:", config.plugins.serienRec.seriensubdir))
		if config.plugins.serienRec.seriensubdir.value:
			self.list.append(getConfigListEntry("Verzeichnisname mit Produktionsjahr:", config.plugins.serienRec.seriensubdirwithyear))
			self.list.append(getConfigListEntry("Staffel-Verzeichnis anlegen:", config.plugins.serienRec.seasonsubdir))
			if config.plugins.serienRec.seasonsubdir.value:
				self.list.append(getConfigListEntry("    Mindestlänge der Staffelnummer im Verzeichnisnamen:", config.plugins.serienRec.seasonsubdirnumerlength))
				self.list.append(getConfigListEntry("    Füllzeichen für Staffelnummer im Verzeichnisnamen:", config.plugins.serienRec.seasonsubdirfillchar))
		self.list.append(getConfigListEntry("Automatisches Plugin-Update:", config.plugins.serienRec.Autoupdate))
		self.list.append(getConfigListEntry("Speicherort der Datenbank:", config.plugins.serienRec.databasePath))
		self.list.append(getConfigListEntry("Erstelle Backup:", config.plugins.serienRec.AutoBackup))
		if config.plugins.serienRec.AutoBackup.value != "0":
			self.list.append(getConfigListEntry("    Speicherort für Backup:", config.plugins.serienRec.BackupPath))
			self.list.append(getConfigListEntry("    Backup-Dateien löschen die älter als x Tage sind:", config.plugins.serienRec.deleteBackupFilesOlderThan))

		###############################################################################################################################
		addSection("TIMER-SUCHLAUF")
		self.list.append(getConfigListEntry("Automatischen Timer-Suchlauf ausführen:", config.plugins.serienRec.autochecktype))
		if config.plugins.serienRec.autochecktype.value == "1":
			self.list.append(getConfigListEntry("    Uhrzeit für automatischen Timer-Suchlauf:", config.plugins.serienRec.deltime))
			self.list.append(getConfigListEntry("    maximale Verzögerung für automatischen Timer-Suchlauf (Min.):", config.plugins.serienRec.maxDelayForAutocheck))
		self.list.append(getConfigListEntry("Timer für X Tage erstellen:", config.plugins.serienRec.checkfordays))
		self.checkfordays = config.plugins.serienRec.checkfordays.value
		self.list.append(getConfigListEntry("Früheste Zeit für Timer:", config.plugins.serienRec.globalFromTime))
		self.list.append(getConfigListEntry("Späteste Zeit für Timer:", config.plugins.serienRec.globalToTime))
		self.list.append(getConfigListEntry("Versuche Timer aus dem EPG zu aktualisieren:", config.plugins.serienRec.eventid))
		if config.plugins.serienRec.eventid.value:
			self.list.append(getConfigListEntry("    EPG Suchgrenzen in Minuten:", config.plugins.serienRec.epgTimeSpan))
		self.list.append(getConfigListEntry("Immer Timer anlegen, wenn keine Wiederholung gefunden wird:", config.plugins.serienRec.forceRecording))
		if config.plugins.serienRec.forceRecording.value:
			self.list.append(getConfigListEntry("    maximal X Tage auf Wiederholung warten:", config.plugins.serienRec.TimeSpanForRegularTimer))
		self.list.append(getConfigListEntry("Anzahl der Aufnahmen pro Episode:", config.plugins.serienRec.NoOfRecords))
		self.list.append(getConfigListEntry("Anzahl der Tuner für Aufnahmen einschränken:", config.plugins.serienRec.selectNoOfTuners))
		if config.plugins.serienRec.selectNoOfTuners.value:
			self.list.append(getConfigListEntry("    maximale Anzahl der zu benutzenden Tuner:", config.plugins.serienRec.tuner))
		if config.plugins.serienRec.autochecktype.value == "1":
			self.list.append(getConfigListEntry("Aus Deep-Standby aufwecken:", config.plugins.serienRec.wakeUpDSB))
		if config.plugins.serienRec.autochecktype.value in ("1", "2"):
			self.list.append(getConfigListEntry("Aktion nach dem automatischen Timer-Suchlauf:", config.plugins.serienRec.afterAutocheck))
			if int(config.plugins.serienRec.afterAutocheck.value):
				self.list.append(getConfigListEntry("    Timeout für (Deep-)Standby-Abfrage (in Sek.):", config.plugins.serienRec.DSBTimeout))

		###############################################################################################################################
		addSection("TV-PLANER E-MAIL")
		self.list.append(getConfigListEntry("Wunschliste TV-Planer E-Mails nutzen:", config.plugins.serienRec.tvplaner))
		if config.plugins.serienRec.tvplaner.value:
			self.list.append(getConfigListEntry("    IMAP Server:", config.plugins.serienRec.imap_server))
			self.list.append(getConfigListEntry("    IMAP Server SSL:", config.plugins.serienRec.imap_server_ssl))
			self.list.append(getConfigListEntry("    IMAP Server Port:", config.plugins.serienRec.imap_server_port))
			self.list.append(getConfigListEntry("    IMAP Login:", config.plugins.serienRec.imap_login))
			self.list.append(getConfigListEntry("    IMAP Passwort:", config.plugins.serienRec.imap_password))
			self.list.append(getConfigListEntry("    IMAP Mailbox:", config.plugins.serienRec.imap_mailbox))
			self.list.append(getConfigListEntry("    IMAP Einstellungen testen:", config.plugins.serienRec.imap_test))
			self.list.append(getConfigListEntry("    TV-Planer Subject:", config.plugins.serienRec.imap_mail_subject))
			self.list.append(getConfigListEntry("    maximales Alter der E-Mail (Tage):", config.plugins.serienRec.imap_mail_age))
			self.list.append(getConfigListEntry("    Voller Timer-Suchlauf mindestens einmal im Erstellungszeitraum:", config.plugins.serienRec.tvplaner_full_check))
			self.tvplaner_full_check = config.plugins.serienRec.tvplaner_full_check.value
			self.list.append(getConfigListEntry("    Timer nur aus der TV-Planer E-Mail anlegen:", config.plugins.serienRec.tvplaner_skipSerienServer))
			self.list.append(getConfigListEntry("    Timer für Serien anlegen:", config.plugins.serienRec.tvplaner_series))
			if config.plugins.serienRec.tvplaner_series.value:
				self.list.append(getConfigListEntry("        Neue TV-Planer Serien nur auf dieser Box aktivieren:", config.plugins.serienRec.tvplaner_series_activeSTB))
			self.list.append(getConfigListEntry("    Timer für Filme anlegen:", config.plugins.serienRec.tvplaner_movies))
			if config.plugins.serienRec.tvplaner_movies.value:
				self.list.append(getConfigListEntry("        Neue TV-Planer Filme nur auf dieser Box aktivieren:", config.plugins.serienRec.tvplaner_movies_activeSTB))
				self.list.append(getConfigListEntry("        Speicherort für Filme:", config.plugins.serienRec.tvplaner_movies_filepath))
				self.list.append(getConfigListEntry("        Unterverzeichnis für jeden Film:", config.plugins.serienRec.tvplaner_movies_createsubdir))

		###############################################################################################################################
		addSection("TIMER")
		self.list.append(getConfigListEntry("Timer-Art:", self.kindOfTimer))
		self.list.append(getConfigListEntry("Nach dem Event:", config.plugins.serienRec.afterEvent))
		self.list.append(getConfigListEntry("Timervorlauf (in Min.):", config.plugins.serienRec.margin_before))
		self.list.append(getConfigListEntry("Timernachlauf (in Min.):", config.plugins.serienRec.margin_after))
		self.list.append(getConfigListEntry("Timername:", config.plugins.serienRec.TimerName))
		self.list.append(getConfigListEntry("Timerbeschreibung:", config.plugins.serienRec.TimerDescription))
		self.list.append(getConfigListEntry("Manuelle Timer immer erstellen:", config.plugins.serienRec.forceManualRecording))
		self.list.append(getConfigListEntry("Event-Programmierungen behandeln:", config.plugins.serienRec.splitEventTimer))
		if config.plugins.serienRec.splitEventTimer.value == "2":
			self.list.append(getConfigListEntry("    Einzelepisoden als 'bereits getimert' markieren:", config.plugins.serienRec.addSingleTimersForEvent))

		print("[SerienRecorder] Number of TV bouquets = " + str(len(self.tvbouquets)))
		if len(self.tvbouquets) == 0:
			config.plugins.serienRec.selectBouquets.value = False
		else:
			for bouquet in self.tvbouquets:
				print(bouquet)
				self.bouquetList.append((bouquet[1], bouquet[1]))

			defaultAlternativeBouquetIndex = 1 if len(self.tvbouquets) > 1 else 0
			config.plugins.serienRec.MainBouquet.setChoices(choices=self.bouquetList, default=self.bouquetList[0][0])
			config.plugins.serienRec.AlternativeBouquet.setChoices(choices=self.bouquetList, default=self.bouquetList[defaultAlternativeBouquetIndex][0])

			self.list.append(getConfigListEntry("Bouquets auswählen:", config.plugins.serienRec.selectBouquets))
			if config.plugins.serienRec.selectBouquets.value:
				self.list.append(getConfigListEntry("    Standard Bouquet:", config.plugins.serienRec.MainBouquet))
				self.list.append(getConfigListEntry("    Alternatives Bouquet:", config.plugins.serienRec.AlternativeBouquet))
				self.list.append(getConfigListEntry("    Verwende alternative Sender bei Konflikten:", config.plugins.serienRec.useAlternativeChannel))
				self.list.append(getConfigListEntry("    Standard Bouquet bevorzugen:", config.plugins.serienRec.preferMainBouquet))

		###############################################################################################################################
		addSection("OPTIMIERUNGEN")
		self.list.append(getConfigListEntry("Intensive Suche nach angelegten Timern:", config.plugins.serienRec.intensiveTimersuche))
		self.list.append(getConfigListEntry("Sucht eine Episode als Aufnahme auf der HDD:", config.plugins.serienRec.sucheAufnahme))

		###############################################################################################################################
		addSection("BENUTZEROBERFLÄCHE")
		self.list.append(getConfigListEntry("Skin:", config.plugins.serienRec.SkinType))

		if config.plugins.serienRec.SkinType.value not in ("", "Skin2", "AtileHD", "StyleFHD", "Black Box"):
			self.list.append(getConfigListEntry("    werden bei diesem Skin immer ALLE Tasten angezeigt:", config.plugins.serienRec.showAllButtons))
		elif config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
			config.plugins.serienRec.showAllButtons.value = False
		else:
			config.plugins.serienRec.showAllButtons.value = True
		if not config.plugins.serienRec.showAllButtons.value:
			self.list.append(getConfigListEntry("    Wechselzeit der Tastenanzeige (Sek.):", config.plugins.serienRec.DisplayRefreshRate))
		self.list.append(getConfigListEntry("Starte Plugin mit:", config.plugins.serienRec.firstscreen))
		self.list.append(getConfigListEntry("Zeige Picons:", config.plugins.serienRec.showPicons))
		if config.plugins.serienRec.showPicons.value != "0":
			self.list.append(getConfigListEntry("    Verzeichnis mit Picons:", config.plugins.serienRec.piconPath))
		self.list.append(getConfigListEntry("Cover herunterladen:", config.plugins.serienRec.downloadCover))
		if config.plugins.serienRec.downloadCover.value:
			self.list.append(getConfigListEntry("    Speicherort der Cover:", config.plugins.serienRec.coverPath))
			self.list.append(getConfigListEntry("    Zeige Cover:", config.plugins.serienRec.showCover))
			self.list.append(getConfigListEntry("    Platzhalter anlegen wenn Cover nicht vorhanden:", config.plugins.serienRec.createPlaceholderCover))
			if config.plugins.serienRec.createPlaceholderCover.value:
				self.list.append(getConfigListEntry("        Platzhalter regelmäßig aktualisieren:", config.plugins.serienRec.refreshPlaceholderCover))
			if config.plugins.serienRec.seriensubdir.value:
				self.list.append(getConfigListEntry("    Cover in Serien-/Staffelordner kopieren:", config.plugins.serienRec.copyCoverToFolder))
		self.list.append(getConfigListEntry("Korrektur der Schriftgröße in Listen:", config.plugins.serienRec.listFontsize))
		self.list.append(getConfigListEntry("Korrektur der Spaltenbreite der Serien-Marker Ansicht:", config.plugins.serienRec.markerColumnWidth))
		self.list.append(getConfigListEntry("Einzug der Serien-Namen in der Serien-Marker Ansicht:", config.plugins.serienRec.markerNameInset))
		self.list.append(getConfigListEntry("Staffel-Filter in Sendetermine Ansicht:", config.plugins.serienRec.seasonFilter))
		self.list.append(getConfigListEntry("Timer-Filter in Sendetermine Ansicht:", config.plugins.serienRec.timerFilter))
		self.list.append(getConfigListEntry("Sortierung der Serien-Marker:", config.plugins.serienRec.markerSort))
		self.list.append(getConfigListEntry("Anzahl der wählbaren Staffeln im Menü Serien-Marker:", config.plugins.serienRec.max_season))
		self.list.append(getConfigListEntry("Öffne Marker-Ansicht nach Hinzufügen neuer Marker:", config.plugins.serienRec.openMarkerScreen))
		self.list.append(getConfigListEntry("Vor Löschen in Serien-Marker und Timer-Liste Benutzer fragen:", config.plugins.serienRec.confirmOnDelete))
		if os.path.isdir("%s/web-data" % os.path.dirname(__file__)):
			self.list.append(getConfigListEntry("SerienRecorder Webinterface aktivieren:", config.plugins.serienRec.enableWebinterface))

		###############################################################################################################################
		addSection("MELDUNGEN")
		self.list.append(getConfigListEntry("Meldung beim Timer-Suchlauf:", config.plugins.serienRec.showNotification))
		self.list.append(getConfigListEntry("Meldung bei Timerkonflikten:", config.plugins.serienRec.showMessageOnConflicts))
		if config.plugins.serienRec.tvplaner.value:
			self.list.append(getConfigListEntry("Meldung bei TV-Planer Fehlern:", config.plugins.serienRec.showMessageOnTVPlanerError))
		self.list.append(getConfigListEntry("Meldung wenn Sendung im EPG nicht gefunden wurde:", config.plugins.serienRec.showMessageOnEventNotFound))
		self.list.append(getConfigListEntry("Anzeigedauer für Meldungen:", config.plugins.serienRec.showMessageTimeout))
		self.list.append(getConfigListEntry("Meldung bei Senderaktualisierungen:", config.plugins.serienRec.channelUpdateNotification))

		###############################################################################################################################
		addSection("LOGGING")
		self.list.append(getConfigListEntry("Speicherort für Log-Datei:", config.plugins.serienRec.LogFilePath))
		self.list.append(getConfigListEntry("Log-Dateiname mit Datum/Uhrzeit:", config.plugins.serienRec.longLogFileName))
		if config.plugins.serienRec.longLogFileName.value:
			self.list.append(getConfigListEntry("    Log-Dateien löschen die älter als x Tage sind:", config.plugins.serienRec.deleteLogFilesOlderThan))
		self.list.append(getConfigListEntry("DEBUG LOG aktivieren:", config.plugins.serienRec.writeLog))
		self.list.append(getConfigListEntry("DEBUG LOG - Box Informationen:", config.plugins.serienRec.writeLogVersion))
		self.list.append(getConfigListEntry("DEBUG LOG - Senderliste:", config.plugins.serienRec.writeLogChannels))
		self.list.append(getConfigListEntry("DEBUG LOG - Episoden:", config.plugins.serienRec.writeLogAllowedEpisodes))
		self.list.append(getConfigListEntry("DEBUG LOG - Added:", config.plugins.serienRec.writeLogAdded))
		self.list.append(getConfigListEntry("DEBUG LOG - Festplatte:", config.plugins.serienRec.writeLogDisk))
		self.list.append(getConfigListEntry("DEBUG LOG - Tageszeit:", config.plugins.serienRec.writeLogTimeRange))
		self.list.append(getConfigListEntry("DEBUG LOG - Zeitbegrenzung:", config.plugins.serienRec.writeLogTimeLimit))
		self.list.append(getConfigListEntry("DEBUG LOG - Timer Debugging:", config.plugins.serienRec.writeLogTimerDebug))
		if config.plugins.serienRec.tvplaner.value:
			self.list.append(getConfigListEntry("Backup von TV-Planer E-Mail erstellen:", config.plugins.serienRec.tvplaner_backupHTML))
		self.list.append(getConfigListEntry("DEBUG LOG - Ans Ende springen:", config.plugins.serienRec.logScrollLast))
		self.list.append(getConfigListEntry("DEBUG LOG - Anzeige mit Zeilenumbruch:", config.plugins.serienRec.logWrapAround))

	def changedEntry(self, dummy=False):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyOK(self):
		from .SerienRecorderFileListScreen import serienRecFileListScreen
		current_selection = self['config'].getCurrent()[1]
		if current_selection == config.plugins.serienRec.imap_test:
			from .SerienRecorderTVPlaner import imaptest
			imaptest(self.session)
			# Do not call default OK action
		elif current_selection != config.plugins.serienRec.TimerName and current_selection != config.plugins.serienRec.TimerDescription:
			# Do not call default OK action for Timername and TimerDescription
			ConfigListScreen.keyOK(self)
			if current_selection == config.plugins.serienRec.savetopath:
				# start_dir = "/media/hdd/movie/"
				start_dir = config.plugins.serienRec.savetopath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Aufnahme Verzeichnis für Serien auswählen")
			if current_selection == config.plugins.serienRec.tvplaner_movies_filepath:
				# start_dir = "/media/hdd/movie/"
				start_dir = config.plugins.serienRec.tvplaner_movies_filepath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Aufnahme Verzeichnis für Filme auswählen")
			elif current_selection == config.plugins.serienRec.LogFilePath:
				start_dir = config.plugins.serienRec.LogFilePath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Log-Datei Verzeichnis auswählen")
			elif current_selection == config.plugins.serienRec.BackupPath:
				start_dir = config.plugins.serienRec.BackupPath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Backup Verzeichnis auswählen")
			elif current_selection == config.plugins.serienRec.databasePath:
				start_dir = config.plugins.serienRec.databasePath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Datenbank Verzeichnis auswählen")
			elif current_selection == config.plugins.serienRec.coverPath:
				start_dir = config.plugins.serienRec.coverPath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Cover Verzeichnis auswählen")
			elif current_selection == config.plugins.serienRec.piconPath:
				start_dir = config.plugins.serienRec.piconPath.value
				self.session.openWithCallback(self.selectedMediaFile, serienRecFileListScreen, start_dir,
				                              "Picon Verzeichnis auswählen")


	def selectedMediaFile(self, res):
		if res is not None:
			current_selection = self['config'].getCurrent()[1]
			if current_selection == config.plugins.serienRec.savetopath:
				#print(res)
				config.plugins.serienRec.savetopath.value = res
				self.changedEntry()
			if current_selection == config.plugins.serienRec.tvplaner_movies_filepath:
				#print(res)
				config.plugins.serienRec.tvplaner_movies_filepath.value = res
				self.changedEntry()
			elif current_selection == config.plugins.serienRec.LogFilePath:
				#print(res)
				config.plugins.serienRec.LogFilePath.value = res
				self.changedEntry()
			elif current_selection == config.plugins.serienRec.BackupPath:
				#print(res)
				config.plugins.serienRec.BackupPath.value = res
				self.changedEntry()
			elif current_selection == config.plugins.serienRec.databasePath:
				#print(res)
				config.plugins.serienRec.databasePath.value = res
				self.changedEntry()
			elif current_selection == config.plugins.serienRec.coverPath:
				#print(res)
				config.plugins.serienRec.coverPath.value = res
				self.changedEntry()
			elif current_selection == config.plugins.serienRec.piconPath:
				#print(res)
				config.plugins.serienRec.piconPath.value = res
				self.changedEntry()

	def setInfoText(self):
		from .SerienRecorderLogWriter import SERIENRECORDER_LONG_LOGFILENAME
		lt = time.localtime()
		self.HilfeTexte = {
			###############################################################################################################################
			# SYSTEM
			###############################################################################################################################
			config.plugins.serienRec.BoxID: (
				"Die ID (Nummer) der Box. Läuft der SerienRecorder auf mehreren Boxen, die alle auf die selbe Datenbank (im Netzwerk) zugreifen, "
				"können einzelne Marker über diese ID für jede Box einzeln aktiviert oder deaktiviert werden. Timer werden dann nur auf den Boxen erstellt, "
				"für die der Marker aktiviert ist."),
			config.plugins.serienRec.activateNewOnThisSTBOnly: (
				"Bei 'ja' werden neue Serien-Marker nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt."),
			config.plugins.serienRec.savetopath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von Serien gespeichert werden."),
			config.plugins.serienRec.seriensubdir: (
				"Bei 'ja' wird für jede Serie ein eigenes Unterverzeichnis für die Aufnahmen erstellt, Bei 'nein' wird kein Serienverzeichnis angelegt."),
			config.plugins.serienRec.seriensubdirwithyear: (
					"Bei 'ja' wird für das Unterverzeichnis mit dem Seriennamen und dem Produktionsjahr (z.B.\n'%sDie Simpsons (1989)/') erstellt, bei 'nein' wird nur der Serienname verwendet" % config.plugins.serienRec.savetopath.value),
			config.plugins.serienRec.seasonsubdir: (
					"Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis (z.B.\n"
					"'%s<Serien_Name>/Season %s') erstellt." % (config.plugins.serienRec.savetopath.value, str("1").zfill(
				config.plugins.serienRec.seasonsubdirnumerlength.value))),
			config.plugins.serienRec.seasonsubdirnumerlength: (
				"Die Anzahl der Stellen, auf die die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt wird."),
			config.plugins.serienRec.seasonsubdirfillchar: (
				"Auswahl, ob die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt werden."),
			config.plugins.serienRec.Autoupdate: (
				"Bei 'ja' wird bei jedem Start des SerienRecorders nach verfügbaren Updates gesucht."),
			config.plugins.serienRec.databasePath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Datenbank gespeichert wird."),
			config.plugins.serienRec.AutoBackup: (
					"Bei 'vor dem Timer-Suchlauf' werden vor jedem Timer-Suchlauf die Datenbank des SR, die 'alte' Log-Datei und die enigma2-Timer-Datei ('/etc/enigma2/timers.xml') in ein neues Verzeichnis kopiert, "
					"dessen Name sich aus dem aktuellen Datum und der aktuellen Uhrzeit zusammensetzt (z.B.\n'%s%s%s%s%s%s/').\n"
					"Bei 'nach dem Timer-Suchlauf' wird das Backup nach dem Timer-Suchlauf erstellt. Bei 'nein' wird kein Backup erstellt (nicht empfohlen)." % (
						config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2),
						str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))),
			config.plugins.serienRec.BackupPath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Backups gespeichert werden."),
			config.plugins.serienRec.deleteBackupFilesOlderThan: (
				"Backup-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht."),

			###############################################################################################################################
			# TIMER-SUCHLAUF
			###############################################################################################################################
			config.plugins.serienRec.autochecktype: (
				"Bei 'manuell' wird kein automatischer Timer-Suchlauf durchgeführt, die Suche muss manuell über die INFO/EPG Taste gestartet werden.\n\n"
				"Bei 'zur gewählten Uhrzeit' wird der automatische Timer-Suchlauf täglich zur eingestellten Uhrzeit ausgeführt.\n\n"
				"Bei 'nach EPGRefresh' wird der automatische Timer-Suchlauf ausgeführt, nachdem der EPGRefresh beendet ist (benötigt EPGRefresh v2.1.1 oder größer) - nicht verfügbar auf VU+ Boxen."),
			config.plugins.serienRec.deltime: (
					"Uhrzeit, zu der der automatische Timer-Suchlauf täglich ausgeführt wird (%s:%s Uhr)." % (
				str(config.plugins.serienRec.deltime.value[0]).zfill(2),
				str(config.plugins.serienRec.deltime.value[1]).zfill(2))),
			config.plugins.serienRec.maxDelayForAutocheck: (
				"Hier wird die Zeitspanne (in Minuten) eingestellt, innerhalb welcher der automatische Timer-Suchlauf ausgeführt wird. Diese Zeitspanne beginnt zu der oben eingestellten Uhrzeit."),
			config.plugins.serienRec.checkfordays: (
					"Es werden nur Timer für Folgen erstellt, die innerhalb der nächsten hier eingestellten Anzahl von Tagen ausgestrahlt werden \n"
					"(also bis %s)." % time.strftime("%d.%m.%Y - %H:%M", time.localtime(
				int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400)))),
			config.plugins.serienRec.globalFromTime: ("Die Uhrzeit, ab wann Aufnahmen erlaubt sind.\n"
			                                          "Die erlaubte Zeitspanne beginnt um %s:%s Uhr." % (
				                                          str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2),
				                                          str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2))
			                                          ),
			config.plugins.serienRec.globalToTime: ("Die Uhrzeit, bis wann Aufnahmen erlaubt sind.\n"
			                                        "Die erlaubte Zeitspanne endet um %s:%s Uhr." % (
				                                        str(config.plugins.serienRec.globalToTime.value[0]).zfill(2),
				                                        str(config.plugins.serienRec.globalToTime.value[1]).zfill(2))
			                                        ),
			config.plugins.serienRec.eventid: (
				"Bei 'ja' wird versucht die Sendung anhand der Anfangs- und Endzeiten im EPG zu finden. "
				"Außerdem erfolgt bei jedem Timer-Suchlauf ein Abgleich der Anfangs- und Endzeiten aller Timer mit den EPG-Daten.\n"
				"Diese Funktion muss aktiviert sein, wenn VPS benutzt werden soll."),
			config.plugins.serienRec.epgTimeSpan: (
				"Die Anzahl Minuten um die der EPG Suchzeitraum nach vorne und hinten vergrößert werden soll (Standard: 10 min).\n\n"
				"Beispiel: Eine Sendung soll laut Wunschliste um 3:20 Uhr starten, im EPG ist die Startzeit aber 3:28 Uhr, um die Sendung im EPG zu finden wird der Suchzeitraum um den eingestellten Wert "
				"vergrößert, im Standard wird also von 3:10 Uhr bis 3:30 Uhr gesucht um die Sendung im EPG zu finden."),
			config.plugins.serienRec.forceRecording: (
					"Bei 'ja' werden auch Timer für Folgen erstellt, die ausserhalb der erlaubten Zeitspanne (%s:%s - %s:%s) ausgestrahlt werden, "
					"falls KEINE Wiederholung innerhalb der erlaubten Zeitspanne gefunden wird.\n"
					"Bei 'nein' werden ausschließlich Timer für jene Folgen erstellt, die innerhalb der erlaubten Zeitspanne liegen." % (
						str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2),
						str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2),
						str(config.plugins.serienRec.globalToTime.value[0]).zfill(2),
						str(config.plugins.serienRec.globalToTime.value[1]).zfill(2))),
			config.plugins.serienRec.TimeSpanForRegularTimer: (
				"Die Anzahl der Tage, die maximal auf eine Wiederholung gewartet wird, die innerhalb der erlaubten Zeitspanne ausgestrahlt wird. "
				"Wird keine passende Wiederholung gefunden oder eine Wiederholung, die zu weit in der Zukunft liegt, "
				"wird ein Timer für den frühestmöglichen Termin, auch außerhalb der erlaubten Zeitspanne, erstellt."),
			config.plugins.serienRec.NoOfRecords: (
				"Die Anzahl der Aufnahmen, die von einer Folge gemacht werden sollen."),
			config.plugins.serienRec.selectNoOfTuners: (
				"Bei 'ja' wird die Anzahl der vom SR benutzten Tuner für gleichzeitige Aufnahmen begrenzt.\n"
				"Bei 'nein' werden alle verfügbaren Tuner für Timer benutzt, die Überprüfung ob noch ein weiterer Timer erzeugt werden kann, übernimmt enigma2."),
			config.plugins.serienRec.tuner: (
				"Die maximale Anzahl von Tunern für gleichzeitige (sich überschneidende) Timer. Überprüft werden dabei ALLE Timer, nicht nur die vom SerienRecorder erstellten."),
			config.plugins.serienRec.wakeUpDSB: (
				"Bei 'ja' wird die Box vor dem automatischen Timer-Suchlauf hochgefahren, falls sie sich im Deep-Standby befindet.\n"
				"Bei 'nein' wird der automatische Timer-Suchlauf NICHT ausgeführt, wenn sich die Box im Deep-Standby befindet."),
			config.plugins.serienRec.afterAutocheck: (
				"Hier kann ausgewählt werden, ob die Box nach dem automatischen Timer-Suchlauf in Standby oder Deep-Standby gehen soll."),
			config.plugins.serienRec.DSBTimeout: (
				"Bevor die Box in den Deep-Standby fährt, wird für die hier eingestellte Dauer (in Sekunden) eine entsprechende Nachricht auf dem Bildschirm angezeigt. "
				"Während dieser Zeitspanne hat der Benutzer die Möglichkeit, das Herunterfahren der Box abzubrechen. Nach Ablauf dieser Zeitspanne fährt die Box automatisch in den Deep-Stanby."),

			###############################################################################################################################
			# E-MAIL
			###############################################################################################################################
			config.plugins.serienRec.tvplaner: (
				"Um den SerienServer zu entlasten und nur die Serien abzurufen, die als nächstes ausgestrahlt werden, kann man die TV-Planer E-Mail von Wunschliste nutzen.\n"
				"Dazu muss der TV-Planer in 'Meine Wunschliste' auf der Wunschliste Webseite aktiviert sein.\n\n"
				"Bei 'ja' ruft der SerienRecorder beim Timer-Suchlauf, das in den nachfolgenden Optionen festgelegte E-Mail IMAP Konto ab und verarbeitet die Wunschliste TV-Planer E-Mail.\n\n"
				"Weitere Informationen zur Einrichtung finden sich auch im Handbuch (HELP lang)"),
			config.plugins.serienRec.imap_server: ("Name des IMAP Servers (z.B. imap.gmx.de)"),
			config.plugins.serienRec.imap_server_ssl: ("Zugriff über SSL (Port ohne SSL = 143, Port mit SSL = 993"),
			config.plugins.serienRec.imap_server_port: ("Portnummer für den Zugriff"),
			config.plugins.serienRec.imap_login: ("Benutzername des IMAP Accounts (z.B. abc@gmx.de)"),
			config.plugins.serienRec.imap_password: ("Passwort des IMAP Accounts"),
			config.plugins.serienRec.imap_mailbox: ("Name des Ordners in dem die E-Mails ankommen (z.B. INBOX)"),
			config.plugins.serienRec.imap_test: (
				"Mit der OK Taste können die IMAP Einstellungen getestet werden, dabei wird versucht eine Verbindung zum eingestellten E-Mail Server aufzubauen, außerdem werden noch die vorhandenen Postfächer abgerufen.\n\n"
				"Wenn die Zugangdaten geändert oder zum ersten Mal eingegeben wurden, bitte zuerst die Einstellungen speichern, bevor der Test ausgeführt wird.\n\n"
				"Die Ergebnisse werden im Log ausgegeben."),
			config.plugins.serienRec.imap_mail_subject: (
				"Betreff der TV-Planer E-Mails (Standard: TV Wunschliste TV-Planer)"),
			config.plugins.serienRec.imap_mail_age: ("Anzahl der Tage die beim Abrufen der E-Mails berücksichtigt werden, es wird aber immer nur die aktuellste Datei für die Timererstellung verwendet."),
			config.plugins.serienRec.tvplaner_full_check: (
				"Bei 'ja' wird vor dem Erreichen der eingestellten Zahl von Aufnahmetagen wieder ein voller Timer-Suchlauf gestartet"),
			config.plugins.serienRec.tvplaner_skipSerienServer: (
				"Bei 'ja' werden Timer nur aus der TV-Planer E-Mail angelegt, es werden keine Termine vom Serien-Server abgerufen."),
			config.plugins.serienRec.tvplaner_series: ("Bei 'ja' werden Timer für Serien angelegt"),
			config.plugins.serienRec.tvplaner_series_activeSTB: (
				"Bei 'ja' werden neue TV-Planer Serien nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt."),
			config.plugins.serienRec.tvplaner_movies: ("Bei 'ja' werden Timer für Filme angelegt"),
			config.plugins.serienRec.tvplaner_movies_activeSTB: (
				"Bei 'ja' werden neue TV-Planer Filme nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt."),
			config.plugins.serienRec.tvplaner_movies_filepath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von Filmen gespeichert werden."),
			config.plugins.serienRec.tvplaner_movies_createsubdir: (
				"Bei 'ja' wird für jeden Film ein eigenes Unterverzeichnis für die Aufnahmen erstellt. Bei 'nein' wird kein Filmordner angelegt."),

			###############################################################################################################################
			# TIMER
			###############################################################################################################################
			self.kindOfTimer: ("Es kann ausgewählt werden, wie Timer angelegt werden. Die Auswahlmöglichkeiten sind:\n"
			                   "  - 'aufnehmen': Ein 'normaler' Timer wird erstellt\n"
			                   "  - 'umschalten': Es wird ein Timer erstellt, bei dem nur auf den aufzunehmenden Sender umgeschaltet wird. Es erfolgt KEINE Aufnahme\n"
			                   "  - 'umschalten und aufnehmen': Es wird ein Timer erstellt, bei dem vor der Aufnahme auf den aufzunehmenden Sender umgeschaltet wird\n"
			                   "  - 'Erinnerung': Es wird ein Timer erstellt, bei dem lediglich eine Erinnerungs-Nachricht auf dem Bildschirm eingeblendet wird. Es wird weder umgeschaltet, noch erfolgt eine Aufnahme"),
			config.plugins.serienRec.afterEvent: (
				"Es kann ausgewählt werden, was nach dem Event passieren soll. Die Auswahlmöglichkeiten sind:\n"
				"  - 'nichts': Die Box bleibt im aktuellen Zustand.\n"
				"  - 'in Standby gehen': Die Box geht in den Standby\n"
				"  - 'in Deep-Standby gehen': Die Box geht in den Deep-Standby\n"
				"  - 'automatisch': Die Box entscheidet automatisch (Standardwert)"),
			config.plugins.serienRec.margin_before: ("Die Vorlaufzeit für Aufnahmen in Minuten.\n"
			                                         "Die Aufnahme startet um die hier eingestellte Anzahl von Minuten vor dem tatsächlichen Beginn der Sendung"),
			config.plugins.serienRec.margin_after: ("Die Nachlaufzeit für Aufnahmen in Minuten.\n"
			                                        "Die Aufnahme endet um die hier eingestellte Anzahl von Minuten noch dem tatsächlichen Ende der Sendung"),
			config.plugins.serienRec.TimerName: (
				"Es kann ausgewählt werden, wie der Timername gebildet werden soll, dieser Name bestimmt auch den Namen der Aufnahme.\n"
				"Falls das Plugin 'SerienFilm' verwendet wird, sollte man die Einstellung '<Serienname>' wählen, damit die Episoden korrekt in virtuellen Ordnern zusammengefasst werden."
				"In diesem Fall funktioniert aber die Funktion 'Zeige ob die Episode als Aufnahme auf der HDD ist' nicht, weil der Dateiname die nötigen Informationen nicht enthält."),
			config.plugins.serienRec.TimerDescription: (
				"Es kann ausgewählt werden, wie die Timerbeschreibung gebildet werden soll."),
			config.plugins.serienRec.forceManualRecording: (
				"Bei 'nein' erfolgt beim manuellen Anlegen von Timern in 'Sendetermine' eine Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen erreicht wurde. "
				"In diesem Fall wird der Timer NICHT angelegt, und es erfolgt ein entsprechender Eintrag im log.\n"
				"Bei 'ja' wird beim manuellen Anlegen von Timern in 'Sendetermine' die Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen vorhanden sind, "
				"ausgeschaltet. D.h. der Timer wird auf jeden Fall angelegt, sofern nicht ein Konflikt mit anderen Timern besteht."),
			config.plugins.serienRec.splitEventTimer: (
				"Bei 'nein' werden Event-Programmierungen (S01E01/1x02/1x03) als eigenständige Sendungen behandelt. "
				"Ansonsten wird versucht die einzelnen Episoden eines Events erkennen.\n\n"
				"Bei 'Timer anlegen' wird zwar weiterhin nur ein Timer angelegt, aber die Einzelepisoden werden in der Datenbank als 'bereits getimert' markiert."
				"Sollten bereits alle Einzelepisoden vorhanden sein, wird für das Event kein Timer angelegt.\n\n"
				"Bei 'Einzelepisoden bevorzugen' wird versucht Timer für die Einzelepisoden anzulegen. "
				"Falls das nicht möglich ist, wird ein Timer für das Event erstellt."),
			config.plugins.serienRec.addSingleTimersForEvent: (
				"Bei 'ja' werden die Einzelepisoden in der Datenbank als 'bereits getimert' markiert, falls ein Timer für das Event angelegt werden muss.\n"
				"Bei 'nein' werden, wenn ein Timer für das Event angelegt werden musste, ggf. später auch Timer für Einzelepisoden angelegt."),
			config.plugins.serienRec.selectBouquets: (
				"Bei 'ja' können 2 Bouquets (Standard und Alternativ) für die Sender-Zuordnung verwendet werden.\n"
				"Bei 'nein' werden alle Bouquets (in einer Liste zusammengefasst) für die Sender-Zuordnung benutzt."),
			config.plugins.serienRec.MainBouquet: (
				"Auswahl, welches Bouquet bei der Sender-Zuordnung als Standard verwendet werden soll."),
			config.plugins.serienRec.AlternativeBouquet: (
				"Auswahl, welches Bouquet bei der Sender-Zuordnung als Alternative verwendet werden soll."),
			config.plugins.serienRec.useAlternativeChannel: (
				"Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
				"falls der Timer auf dem bevorzugten Sender nicht angelegt werden kann."),
			config.plugins.serienRec.preferMainBouquet: (
				"Bei 'ja' werden Sender des Standard Bouquets bevorzugt, d.h. wurde für eine Episode auf einem Sender des alternativen Bouquets ein Timer angelegt, "
				"wird für diese Episode, falls sie danach auf einem Sender des Standard Bouquets ausgestrahlt wird, erneut ein Timer angelegt.\n\n"
				"So kann eine Sendung z.B. auf einem werbefreien Sender erneut getimert werden."),

			###############################################################################################################################
			# OPTIMIERUNGEN
			###############################################################################################################################
			config.plugins.serienRec.intensiveTimersuche: (
				"Bei 'ja' wird in der Hauptansicht intensiver nach vorhandenen Timern gesucht, d.h. es wird vor der Suche versucht die Anfangszeit aus dem EPGCACHE zu aktualisieren was aber zeitintensiv ist."),
			config.plugins.serienRec.sucheAufnahme: (
				"Bei 'ja' wird beim Timer-Suchlauf der Aufnahmeordner nach der Episode durchsucht, für die ein Timer angelegt werden soll. Wird eine entsprechende Aufnahme gefunden, wird kein Timer mehr angelegt.\n"
				"Zusätzlich sorgt diese Option dafür, dass ein Symbol für jede Episode angezeigt wird, die als Aufnahme auf der Festplatte gefunden wurde.\n\nDiese Suche kann u.U. zeitintensiv sein."),

			###############################################################################################################################
			# BENUTZEROBERFLÄCHE
			###############################################################################################################################
			config.plugins.serienRec.SkinType: (
				"Hier kann das Erscheinungsbild des SR ausgewählt werden."),
			config.plugins.serienRec.showAllButtons: (
				"Hier kann für eigene Skins angegeben werden, ob immer ALLE Options-Tasten angezeigt werden, oder ob die Anzeige wechselt."),
			config.plugins.serienRec.DisplayRefreshRate: (
				"Das Zeitintervall in Sekunden, in dem die Anzeige der Options-Tasten wechselt."),
			config.plugins.serienRec.firstscreen: (
				"Beim Start des SerienRecorder startet das Plugin mit dem ausgewählten Screen."),
			config.plugins.serienRec.showPicons: (
				"Gibt an ob und wie Sender-Logos z.B. in der Serien-Planer Ansichten angezeigt werden sollen."),
			config.plugins.serienRec.piconPath: (
				"Wählen Sie das Verzeichnis aus dem die Sender-Logos geladen werden sollen. Der SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird."),
			config.plugins.serienRec.downloadCover: ("Bei 'nein' werden keine Cover heruntergeladen und angezeigt.\n"
			                                         "Bei 'ja' werden Cover heruntergeladen.\n"
			                                         "  - Wenn 'Zeige Cover' auf 'ja' steht, werden alle Cover heruntergeladen.\n"
			                                         "  - Wenn 'Zeige Cover' auf 'nein' steht, werden beim Timer-Suchlauf nur Cover der Serien-Marker heruntergeladen."),
			config.plugins.serienRec.coverPath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Cover gespeichert werden."),
			config.plugins.serienRec.showCover: ("Bei 'nein' werden keine Cover angezeigt."),
			config.plugins.serienRec.createPlaceholderCover: (
				"Bei 'ja' werden Platzhalter Dateien erzeugt wenn kein Cover vorhanden ist - das hat den Vorteil, dass nicht immer wieder nach dem Cover gesucht wird."),
			config.plugins.serienRec.refreshPlaceholderCover: (
				"Bei 'ja' wird in regelmäßigen Abständen (alle 60 Tage) nach einem Cover für die Serie gesucht um die Platzhalter Datei zu ersetzen."),
			config.plugins.serienRec.copyCoverToFolder: (
				"Bei 'nein' wird das entsprechende Cover nicht in den Serien- und Staffelordner kopiert. Die anderen Optionen bestimmen den Namen der Datei im Staffelordner.\n"
				"Im Serienordner werden immer Cover mit dem Namen 'folder.jpg' angelegt. Für den Staffelordner kann der Name ausgewählt werden, da einige Movielist Plugins das Cover unter einem anderen Namen suchen."),
			config.plugins.serienRec.listFontsize: (
				"Damit kann bei zu großer oder zu kleiner Schrift eine individuelle Anpassung erfolgen. SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird."),
			config.plugins.serienRec.markerColumnWidth: (
				"Mit dieser Einstellung kann die Breite der ersten Spalte in der Serien-Marker Ansicht angepasst werden. Ausgehend von Standardbreite kann die Spalte schmaler bzw. breiter machen."),
			config.plugins.serienRec.markerNameInset: (
				"Mit dieser Einstellung kann der Einzug der Serien-Namen in der Serien-Marker Ansicht angepasst werden. Damit lässt sich eine deutlichere optische Abgrenzung der einzelnen Serien-Marker erreichen."),
			config.plugins.serienRec.seasonFilter: (
				"Bei 'ja' werden in der Sendetermine Ansicht nur Termine angezeigt, die der am Marker eingestellten Staffeln entsprechen."),
			config.plugins.serienRec.timerFilter: (
				"Bei 'ja' werden in der Sendetermine Ansicht nur Termine angezeigt, für die noch Timer angelegt werden müssen."),
			config.plugins.serienRec.markerSort: ("Bei 'Alphabetisch' werden die Serien-Marker alphabetisch sortiert.\n"
			                                      "Bei 'Wunschliste' werden die Serien-Marker so wie bei Wunschliste sortiert, d.h 'der, die, das und the' werden bei der Sortierung nicht berücksichtigt.\n"
			                                      "Dadurch werden z.B. 'Die Simpsons' unter 'S' einsortiert."),
			config.plugins.serienRec.max_season: (
				"Die höchste Staffelnummer, die für Serienmarker in der Staffel-Auswahl gewählt werden kann."),
			config.plugins.serienRec.openMarkerScreen: (
				"Bei 'ja' wird nach Anlegen eines neuen Markers die Marker-Anzeige geöffnet, um den neuen Marker bearbeiten zu können."),
			config.plugins.serienRec.confirmOnDelete: (
				"Bei 'ja' erfolgt eine Sicherheitsabfrage ('Soll ... wirklich entfernt werden?') vor dem endgültigen Löschen von Serienmarkern oder Timern."),
			config.plugins.serienRec.enableWebinterface: (
				"Bei 'ja' wird das Webinterface des SerienRecorder aktiviert, sodass über den Webbrowser von einem beliebigen Computer/Tablet/Smartphone auf den SerienRecorder zugegriffen werden kann.\n\n"
				"Die Box muss neu gestartet werden, damit diese Änderung wirksam wird.\n\n"
				"Schnittstellen Version: " + SRAPIVERSION),

			###############################################################################################################################
			# MELDUNGEN
			###############################################################################################################################
			config.plugins.serienRec.showNotification: (
				"Je nach Einstellung wird eine Nachricht auf dem Bildschirm eingeblendet, sobald der automatische Timer-Suchlauf endet."),
			config.plugins.serienRec.showMessageOnConflicts: (
				"Bei 'ja' wird für jeden Timer, der beim automatische Timer-Suchlauf wegen eines Konflikts nicht angelegt werden konnte, eine Nachricht auf dem Bildschirm eingeblendet.\n"
				"Diese Nachrichten bleiben solange auf dem Bildschirm, bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden."),
			config.plugins.serienRec.showMessageOnTVPlanerError: (
				"Bei 'ja' wird eine Nachricht auf dem Bildschirm eingeblendet, wenn beim Abrufen der TV-Planer E-Mail ein Fehler aufgetreten ist.\n"
				"Diese Nachrichten bleiben solange auf dem Bildschirm, bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden."),
			config.plugins.serienRec.showMessageOnEventNotFound: (
				"Bei 'ja' wird für jeden Timer dessen Sendung beim automatischen Timer-Suchlauf nicht mehr im EPG gefunden wurde, eine Nachricht auf dem Bildschirm eingeblendet.\n"
				"Das könnte darauf hindeuten, dass die Sendung evtl. kurzfristig aus dem Programm genommen wurde.\n"
				"Diese Nachrichten bleiben solange auf dem Bildschirm, bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden."),
			config.plugins.serienRec.showMessageTimeout: (
				"Gibt an wie lange die obigen Nachrichten (Timerkonflikte, TV-Planer Fehler und Sendung im EPG nicht gefunden) auf dem Bildschirm angezeigt werden.\n\n"
				"Bei '0' bleiben sie solange auf dem Bildschirm, bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden."),
			config.plugins.serienRec.channelUpdateNotification: (
				"Der SerienRecorder zeigt eine Nachricht, wenn sich die Sender bei Wunschliste ändern und die Senderliste im SerienRecorder aktualisiert werden muss.\n\n"
				"Bei 'Beim Starten' wird bei jedem Start des SerienRecorders nach Aktualisierungen der Sender gesucht und ggf. eine Nachricht angezeigt.\n"
				"Bei 'Nach dem Timer-Suchlauf' wird diese Prüfung nur nach dem Timer-Suchlauf ausgeführt und ggf. dann eine Nachricht gezeigt."),

			###############################################################################################################################
			# LOGGING
			###############################################################################################################################
			config.plugins.serienRec.LogFilePath: (
				"Das Verzeichnis auswählen und/oder erstellen, in dem die Log-Dateien gespeichert werden."),
			config.plugins.serienRec.longLogFileName: (
					"Bei 'nein' wird bei jedem Timer-Suchlauf die Log-Datei neu erzeugt.\n"
					"Bei 'ja' wird NACH jedem Timer-Suchlauf die soeben neu erzeugte Log-Datei in eine Datei kopiert, deren Name das aktuelle Datum und die aktuelle Uhrzeit beinhaltet.\n\n"
					"Beispiel:\n" + os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_LONG_LOGFILENAME % (str(lt.tm_year), str(lt.tm_mon).zfill(2),
						str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)))),
			config.plugins.serienRec.deleteLogFilesOlderThan: (
				"Log-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht."),
			config.plugins.serienRec.writeLog: (
				"Bei 'nein' erfolgen nur grundlegende Eintragungen in die Log-Datei, z.B. Datum/Uhrzeit des Timer-Suchlaufs, Beginn neuer Staffeln, Gesamtergebnis des Timer-Suchlaufs.\n"
				"Bei 'ja' erfolgen detaillierte Eintragungen, abhängig von den ausgewählten Filtern."),
			config.plugins.serienRec.writeLogVersion: (
				"Bei 'ja' erfolgen Einträge in die Log-Datei, die Informationen über die verwendete Box und das Image beinhalten."),
			config.plugins.serienRec.writeLogChannels: (
				"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn dem ausstrahlenden Sender in der Sender-Zuordnung kein Box-Sender zugeordnet ist, oder der Box-Sender deaktiviert ist."),
			config.plugins.serienRec.writeLogAllowedEpisodes: (
				"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn die zu timende Staffel oder Folge in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist."),
			config.plugins.serienRec.writeLogAdded: (
				"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Timern vorhanden ist."),
			config.plugins.serienRec.writeLogDisk: (
				"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Aufnahmen vorhanden ist."),
			config.plugins.serienRec.writeLogTimeRange: (
					"Bei 'ja' erfolgen Einträge in die Log-Datei, wenn die zu timende Folge nicht in der erlaubten Zeitspanne (%s:%s - %s:%s) liegt, "
					"sowie wenn gemäß der Einstellung 'Immer Timer anlegen, wenn keine Wiederholung gefunden wird' = 'ja' "
					"ein Timer ausserhalb der erlaubten Zeitspanne angelegt wird." % (
						str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2),
						str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2),
						str(config.plugins.serienRec.globalToTime.value[0]).zfill(2),
						str(config.plugins.serienRec.globalToTime.value[1]).zfill(2))),
			config.plugins.serienRec.writeLogTimeLimit: (
					"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn der Sendetermin für die zu timende Folge in der Verganhenheit, \n"
					"oder mehr als die in 'Timer für X Tage erstellen' eingestellte Anzahl von Tagen in der Zukunft liegt (jetzt also nach %s)." % time.strftime(
				"%d.%m.%Y - %H:%M",
				time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400)))),
			config.plugins.serienRec.writeLogTimerDebug: (
				"Bei 'ja' erfolgt ein Eintrag in die Log-Datei, wenn der zu erstellende Timer bereits vorhanden ist, oder der Timer erfolgreich angelegt wurde."),
			config.plugins.serienRec.tvplaner_backupHTML: (
				"Bei 'ja' wird die TV-Planer E-Mail als HTML im Logverzeichnis abgespeichert und ins Backup Verzeichnis kopiert, falls das SerienRecorder Backup aktiviert ist."),
			config.plugins.serienRec.logScrollLast: (
				"Bei 'ja' wird beim Anzeigen der Log-Datei ans Ende gesprungen, bei 'nein' auf den Anfang."),
			config.plugins.serienRec.logWrapAround: (
				"Bei 'ja' erfolgt die Anzeige der Log-Datei mit Zeilenumbruch, d.h. es werden drei Zeilen pro Eintrag angezeigt.\n"
				"Bei 'nein' erfolgt die Anzeige der Log-Datei mit einer Zeile pro Eintrag (Bei langen Zeilen sind dann die Enden nicht mehr sichbar!)"),
		}

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."

		self["config_information_text"].setText(text)

	def save(self):
		if config.plugins.serienRec.autochecktype.value == "0":
			config.plugins.serienRec.timeUpdate.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = True

		if not config.plugins.serienRec.selectBouquets.value:
			config.plugins.serienRec.MainBouquet.value = None
			config.plugins.serienRec.AlternativeBouquet.value = None
			config.plugins.serienRec.useAlternativeChannel.value = False

		if not config.plugins.serienRec.seriensubdir.value:
			config.plugins.serienRec.seasonsubdir.value = False

		if config.plugins.serienRec.autochecktype.value != "1":
			config.plugins.serienRec.wakeUpDSB.value = False

		if not config.plugins.serienRec.downloadCover.value:
			config.plugins.serienRec.showCover.value = False

		if config.plugins.serienRec.TimerName.value == "1":
			config.plugins.serienRec.sucheAufnahme.value = False

		if int(config.plugins.serienRec.checkfordays.value) > int(
				config.plugins.serienRec.TimeSpanForRegularTimer.value):
			config.plugins.serienRec.TimeSpanForRegularTimer.value = int(config.plugins.serienRec.checkfordays.value)

		if config.plugins.serienRec.preferMainBouquet.value:
			config.plugins.serienRec.sucheAufnahme.value = False

		config.plugins.serienRec.savetopath.value = os.path.join(str(config.plugins.serienRec.savetopath.value), '')
		config.plugins.serienRec.tvplaner_movies_filepath.value = os.path.join(str(config.plugins.serienRec.tvplaner_movies_filepath.value), '')
		config.plugins.serienRec.LogFilePath.value = os.path.join(str(config.plugins.serienRec.LogFilePath.value), '')
		config.plugins.serienRec.BackupPath.value = os.path.join(str(config.plugins.serienRec.BackupPath.value), '')
		config.plugins.serienRec.databasePath.value = os.path.join(str(config.plugins.serienRec.databasePath.value), '')
		config.plugins.serienRec.coverPath.value = os.path.join(str(config.plugins.serienRec.coverPath.value), '')
		config.plugins.serienRec.piconPath.value = os.path.join(str(config.plugins.serienRec.piconPath.value), '')


		###############################################################################################################################
		# SYSTEM
		###############################################################################################################################
		config.plugins.serienRec.BoxID.save()
		config.plugins.serienRec.activateNewOnThisSTBOnly.save()
		config.plugins.serienRec.savetopath.save()
		config.plugins.serienRec.seriensubdir.save()
		config.plugins.serienRec.seriensubdirwithyear.save()
		config.plugins.serienRec.seasonsubdir.save()
		config.plugins.serienRec.seasonsubdirnumerlength.save()
		config.plugins.serienRec.seasonsubdirfillchar.save()
		config.plugins.serienRec.Autoupdate.save()
		config.plugins.serienRec.databasePath.save()
		config.plugins.serienRec.AutoBackup.save()
		config.plugins.serienRec.BackupPath.save()
		config.plugins.serienRec.deleteBackupFilesOlderThan.save()

		###############################################################################################################################
		# TIMER-SUCHLAUF
		###############################################################################################################################
		config.plugins.serienRec.autochecktype.save()
		config.plugins.serienRec.deltime.save()
		config.plugins.serienRec.maxDelayForAutocheck.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.globalFromTime.save()
		config.plugins.serienRec.globalToTime.save()
		config.plugins.serienRec.eventid.save()
		config.plugins.serienRec.epgTimeSpan.save()
		config.plugins.serienRec.forceRecording.save()
		config.plugins.serienRec.TimeSpanForRegularTimer.save()
		config.plugins.serienRec.NoOfRecords.save()
		config.plugins.serienRec.selectNoOfTuners.save()
		config.plugins.serienRec.tuner.save()
		config.plugins.serienRec.wakeUpDSB.save()
		config.plugins.serienRec.afterAutocheck.save()
		config.plugins.serienRec.DSBTimeout.save()

		###############################################################################################################################
		# E-MAIL
		###############################################################################################################################
		config.plugins.serienRec.tvplaner.save()
		config.plugins.serienRec.imap_server.save()
		config.plugins.serienRec.imap_server_ssl.save()
		config.plugins.serienRec.imap_server_port.save()
		if config.plugins.serienRec.imap_login.value != "*":
			config.plugins.serienRec.imap_login_hidden.value = encrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_login.value)
			config.plugins.serienRec.imap_login.value = "*"
		config.plugins.serienRec.imap_login.save()
		config.plugins.serienRec.imap_login_hidden.save()
		if config.plugins.serienRec.imap_password.value != "*":
			config.plugins.serienRec.imap_password_hidden.value = encrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_password.value)
			config.plugins.serienRec.imap_password.value = "*"
		config.plugins.serienRec.imap_password.save()
		config.plugins.serienRec.imap_password_hidden.save()
		config.plugins.serienRec.imap_mailbox.save()
		config.plugins.serienRec.imap_mail_subject.save()
		config.plugins.serienRec.imap_mail_age.save()
		config.plugins.serienRec.tvplaner_full_check.save()
		if config.plugins.serienRec.tvplaner_full_check.value and (self.tvplaner_full_check != config.plugins.serienRec.tvplaner_full_check.value or self.checkfordays != config.plugins.serienRec.checkfordays.value):
			print("[SerienRecorder] TV-Planer last full check reseted")
			config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
			config.plugins.serienRec.tvplaner_last_full_check.save()
		config.plugins.serienRec.tvplaner_skipSerienServer.save()
		config.plugins.serienRec.tvplaner_series.save()
		config.plugins.serienRec.tvplaner_series_activeSTB.save()
		config.plugins.serienRec.tvplaner_movies.save()
		config.plugins.serienRec.tvplaner_movies_activeSTB.save()
		config.plugins.serienRec.tvplaner_movies_filepath.save()
		config.plugins.serienRec.tvplaner_movies_createsubdir.save()

		###############################################################################################################################
		# TIMER
		###############################################################################################################################
		config.plugins.serienRec.afterEvent.save()
		config.plugins.serienRec.margin_before.save()
		config.plugins.serienRec.margin_after.save()
		config.plugins.serienRec.TimerName.save()
		config.plugins.serienRec.TimerDescription.save()
		config.plugins.serienRec.forceManualRecording.save()
		config.plugins.serienRec.splitEventTimer.save()
		config.plugins.serienRec.addSingleTimersForEvent.save()
		config.plugins.serienRec.selectBouquets.save()
		# if config.plugins.serienRec.selectBouquets.value:
		# 	config.plugins.serienRec.bouquetList.value = str(list(zip(*self.bouquetList))[1])
		# else:
		# 	config.plugins.serienRec.bouquetList.value = ""
		#config.plugins.serienRec.bouquetList.save()
		config.plugins.serienRec.MainBouquet.save()
		config.plugins.serienRec.AlternativeBouquet.save()
		config.plugins.serienRec.useAlternativeChannel.save()
		config.plugins.serienRec.preferMainBouquet.save()

		###############################################################################################################################
		# OPTIMIERUNGEN
		###############################################################################################################################
		config.plugins.serienRec.intensiveTimersuche.save()
		config.plugins.serienRec.sucheAufnahme.save()

		###############################################################################################################################
		# BENUTZEROBERFLÄCHE
		###############################################################################################################################
		config.plugins.serienRec.SkinType.save()
		config.plugins.serienRec.showAllButtons.save()
		config.plugins.serienRec.DisplayRefreshRate.save()
		config.plugins.serienRec.firstscreen.save()
		config.plugins.serienRec.showPicons.save()
		config.plugins.serienRec.piconPath.save()
		config.plugins.serienRec.downloadCover.save()
		config.plugins.serienRec.coverPath.save()
		config.plugins.serienRec.showCover.save()
		config.plugins.serienRec.createPlaceholderCover.save()
		config.plugins.serienRec.refreshPlaceholderCover.save()
		config.plugins.serienRec.copyCoverToFolder.save()
		config.plugins.serienRec.listFontsize.save()
		config.plugins.serienRec.markerColumnWidth.save()
		config.plugins.serienRec.markerNameInset.save()
		config.plugins.serienRec.seasonFilter.save()
		config.plugins.serienRec.timerFilter.save()
		config.plugins.serienRec.markerSort.save()
		config.plugins.serienRec.max_season.save()
		config.plugins.serienRec.openMarkerScreen.save()
		config.plugins.serienRec.confirmOnDelete.save()
		config.plugins.serienRec.enableWebinterface.save()

		###############################################################################################################################
		# BENACHRICHTIGUNGEN
		###############################################################################################################################
		config.plugins.serienRec.showNotification.save()
		config.plugins.serienRec.showMessageOnConflicts.save()
		config.plugins.serienRec.showMessageOnTVPlanerError.save()
		config.plugins.serienRec.showMessageOnEventNotFound.save()
		config.plugins.serienRec.showMessageTimeout.save()
		config.plugins.serienRec.channelUpdateNotification.save()

		###############################################################################################################################
		# LOGGING
		###############################################################################################################################
		config.plugins.serienRec.LogFilePath.save()
		config.plugins.serienRec.longLogFileName.save()
		config.plugins.serienRec.deleteLogFilesOlderThan.save()
		config.plugins.serienRec.writeLog.save()
		config.plugins.serienRec.writeLogVersion.save()
		config.plugins.serienRec.writeLogChannels.save()
		config.plugins.serienRec.writeLogAllowedEpisodes.save()
		config.plugins.serienRec.writeLogAdded.save()
		config.plugins.serienRec.writeLogDisk.save()
		config.plugins.serienRec.writeLogTimeRange.save()
		config.plugins.serienRec.writeLogTimeLimit.save()
		config.plugins.serienRec.writeLogTimerDebug.save()
		config.plugins.serienRec.tvplaner_backupHTML.save()
		config.plugins.serienRec.logScrollLast.save()
		config.plugins.serienRec.logWrapAround.save()

		###############################################################################################################################

		config.plugins.serienRec.timeUpdate.save()
		config.plugins.serienRec.justplay.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTPLAY__))
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.justremind.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTREMIND__))
		config.plugins.serienRec.justremind.save()
		config.plugins.serienRec.zapbeforerecord.value = bool(
			int(self.kindOfTimer.value) & (1 << self.__C_ZAPBEFORERECORD__))
		config.plugins.serienRec.zapbeforerecord.save()

		# Save obsolete config setting here to remove it from file
		config.plugins.serienRec.dbversion.save()
		config.plugins.serienRec.bouquetList.save()
		config.plugins.serienRec.deleteOlderThan.save()
		config.plugins.serienRec.imap_check_interval.save()
		config.plugins.serienRec.planerCacheEnabled.save()
		config.plugins.serienRec.planerCacheSize.save()
		config.plugins.serienRec.readdatafromfiles.save()
		config.plugins.serienRec.refreshViews.save()
		config.plugins.serienRec.setupType.save()
		config.plugins.serienRec.tvplaner_create_marker.save()
		config.plugins.serienRec.updateInterval.save()

		configfile.save()

		if self.SkinType != config.plugins.serienRec.SkinType.value:
			SelectSkin()
			setSkinProperties(self)

		if getDataBaseFilePath() == "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			self.close((True, self.setupModified, True))
		else:
			self.session.openWithCallback(self.changeDBQuestion, MessageBox,
			                              "Das Datenbank Verzeichnis wurde geändert - die Box muss neu gestartet werden.\nSoll das Datenbank Verzeichnis wirklich geändert werden?",
			                              MessageBox.TYPE_YESNO, default=True)

	def changeDBQuestion(self, answer):
		if answer:
			defaultAnswer = False
			if not os.path.exists("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value):
				defaultAnswer = True

			self.session.openWithCallback(self.copyDBQuestion, MessageBox,
			                              "Soll die bestehende Datenbank in das neu ausgewählte Verzeichnis kopiert werden?",
			                              MessageBox.TYPE_YESNO, default=defaultAnswer)
		else:
			config.plugins.serienRec.databasePath.value = os.path.dirname(getDataBaseFilePath())
			config.plugins.serienRec.databasePath.save()
			configfile.save()
			self.close((True, True, True))

	def copyDBQuestion(self, answer):
		if answer:
			try:
				shutil.copyfile(getDataBaseFilePath(), "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)
				setDataBaseFilePath("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)
			except:
				from .SerienRecorderLogWriter import SRLogger
				SRLogger.writeLog("Fehler beim Kopieren der Datenbank")
				Notifications.AddPopup(
					"Die SerienRecorder Datenbank konnte nicht kopiert werden.\nDer alte Datenbankpfad wird wiederhergestellt!",
					MessageBox.TYPE_INFO, timeout=10)
				config.plugins.serienRec.databasePath.value = os.path.dirname(getDataBaseFilePath())
				config.plugins.serienRec.databasePath.save()
				configfile.save()
		else:
			setDataBaseFilePath("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)

		import Screens.Standby
		self.session.open(Screens.Standby.TryQuitMainloop, 3)

	def openChannelSetup(self):
		from .SerienRecorderChannelScreen import serienRecMainChannelEdit
		self.session.openWithCallback(self.changedEntry, serienRecMainChannelEdit)

	def keyCancel(self):
		if self.setupModified:
			self.save()
		else:
			configfile.load()
			ReadConfigFile()
			self.close((False, False, True))

	def __onClose(self):
		self.stopDisplayTimer()
