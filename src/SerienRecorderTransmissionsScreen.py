# coding=utf-8

# This file contains the SerienRecoder Transmissions Screen
import time, os

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Components.MenuList import MenuList

from Screens.HelpMenu import HelpableScreen
from Screens.Screen import Screen

from enigma import ePicLoad, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, loadPNG
from skin import parseColor

from .SerienRecorderScreenHelpers import serienRecBaseScreen, InitSkin, skinFactor
from .SerienRecorder import serienRecDataBaseFilePath

from .SerienRecorderHelpers import STBHelpers, getDirname
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderLogWriter import SRLogger


class serienRecSendeTermine(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, seriesName, seriesWLID, seriesFSID):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.session = session
		self.picload = ePicLoad()
		self.seriesName = seriesName
		self.addedEpisodes = self.database.getTimerForSeries(seriesFSID, False)
		self.seriesWLID = seriesWLID
		self.seriesFSID = seriesFSID
		self.skin = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok": (self.keyOK, "umschalten ausgewählter Sendetermin aktiviert/deaktiviert"),
			"cancel": (self.keyCancel, "zurück zur Serien-Marker-Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"red": (self.keyRed, "zurück zur Serien-Marker-Ansicht"),
			"green": (self.keyGreen, "Timer für aktivierte Sendetermine erstellen"),
			"yellow": (self.keyYellow, "umschalten Filter (aktive Sender) aktiviert/deaktiviert"),
			"blue": (self.keyBlue, "Ansicht Timer-Liste öffnen"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext": (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.filterMode = 1
		self.title_txt = "aktive Sender"

		self.changesMade = False

		self.setupSkin()

		self.sendetermine_list = []
		self.loading = True

		self.onLayoutFinish.append(self.searchEvents)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Abbrechen")
		self['text_ok'].setText("Auswahl")
		if self.filterMode == 1:
			self['text_yellow'].setText("Filter umschalten")
			self.title_txt = "aktive Sender"
		elif self.filterMode == 2:
			self['text_yellow'].setText("Filter ausschalten")
			self.title_txt = "Marker Sender"
		else:
			self['text_yellow'].setText("Filter einschalten")
			self.title_txt = "alle"
		self['text_blue'].setText("Timer-Liste")

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		self['title'].setText("Lade Web-Sender / Box-Sender...")

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

	def serieInfo(self):
		if self.loading:
			return

		if self.seriesWLID:
			from .SerienRecorderSeriesInfoScreen import serienRecShowInfo
			self.session.open(serienRecShowInfo, self.seriesName, self.seriesWLID, self.seriesFSID)

	# self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
		#				  MessageBox.TYPE_INFO, timeout=10)

	def wunschliste(self):
		serien_id = self.seriesWLID
		super(self.__class__, self).wunschliste(serien_id)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					from .SerienRecorderCheckForRecording import checkForRecordingInstance
					checkForRecordingInstance.initialize(self.session, False, False)

			if result[1]:
				self.searchEvents()

	def searchEvents(self, result=None):
		self['title'].setText("Suche ' %s '" % self.seriesName)
		print("[SerienRecorder] suche ' %s '" % self.seriesName)
		print(self.seriesWLID)

		transmissions = None
		if self.seriesWLID:

			if self.seriesWLID != 0:
				print(self.seriesWLID)
				from .SerienRecorder import getCover
				getCover(self, self.seriesName, self.seriesWLID, self.seriesFSID)

				if self.filterMode == 0:
					webChannels = []
				elif self.filterMode == 1:
					webChannels = self.database.getActiveChannels()
				else:
					webChannels = self.database.getMarkerChannels(self.seriesWLID)

				try:
					transmissions = SeriesServer().doGetTransmissions(self.seriesWLID, 0, webChannels)
				except:
					transmissions = None
			else:
				transmissions = None

		self.resultsEvents(transmissions)

	def resultsEvents(self, transmissions):
		if transmissions is None:
			self['title'].setText("Fehler beim Abrufen der Termine für ' %s '" % self.seriesName)
			return
		self.sendetermine_list = []

		# Update added list in case of made changes
		if self.changesMade:
			self.addedEpisodes = self.database.getTimerForSeries(self.seriesFSID, False)

		# build unique dir list by season
		dirList = {}
		# build unique margins
		marginList = {}

		SerieStaffel = None
		AbEpisode = None
		try:
			(serienTitle, SerieUrl, SerieStaffel, SerieSender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays, skipSeriesServer, markerType, fsID) = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, [self.seriesFSID])[0]
		except:
			SRLogger.writeLog("Fehler beim Filtern nach Staffel", True)

		for serien_name, sender, startzeit, endzeit, staffel, episode, title, status in transmissions:
			seasonAllowed = True
			if config.plugins.serienRec.seasonFilter.value:
				seasonAllowed = self.isSeasonAllowed(staffel, episode, SerieStaffel, AbEpisode)

			if seasonAllowed:
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					if not staffel in dirList:
						dirList[staffel] = getDirname(self.database, serien_name, self.seriesFSID, staffel)

					(dirname, dirname_serie) = dirList[staffel]
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, True, title) and True or False
						else:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, True) and True or False
					else:
						bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, True) and True or False

				if bereits_vorhanden:
					addedType = 1
				else:
					if not sender in marginList:
						marginList[sender] = self.database.getMargins(self.seriesFSID, sender, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)

					(margin_before, margin_after) = marginList[sender]

					# check 2 (im timer file)
					start_unixtime = startzeit - (int(margin_before) * 60)

					if self.isTimerAdded(self.addedEpisodes, sender, staffel, episode, int(start_unixtime), title):
						addedType = 2
					elif self.isAlreadyAdded(self.addedEpisodes, staffel, episode, title):
						addedType = 3
					else:
						addedType = 0

				if not config.plugins.serienRec.timerFilter.value or config.plugins.serienRec.timerFilter.value and addedType == 0:
					self.sendetermine_list.append([serien_name, sender, startzeit, endzeit, staffel, episode, title, status, addedType])

		if len(self.sendetermine_list):
			self['text_green'].setText("Timer erstellen")

		self.chooseMenuList.setList(list(map(self.buildList_termine, self.sendetermine_list)))
		self.loading = False
		self['title'].setText("%s Sendetermine für ' %s ' gefunden. (%s)" %
		                      (str(len(self.sendetermine_list)), self.seriesName, self.title_txt))

	@staticmethod
	def buildList_termine(entry):
		(serien_name, sender, start, end, staffel, episode, title, status, addedType) = entry

		# addedType: 0 = None, 1 = on HDD, 2 = Timer available, 3 = in DB
		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

		weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		transmissionTime = time.localtime(start)
		datum = time.strftime(weekdays[transmissionTime.tm_wday] + ", %d.%m.%Y", transmissionTime)
		startTime = time.strftime("%H:%M", transmissionTime)

		serienRecMainPath = os.path.dirname(__file__)

		imageMinus = "%s/images/minus.png" % serienRecMainPath
		imagePlus = "%s/images/plus.png" % serienRecMainPath
		imageNone = "%s/images/black.png" % serienRecMainPath

		if int(status) == 0:
			leftImage = imageMinus
		else:
			leftImage = imagePlus

		imageHDD = imageNone
		imageTimer = imageNone
		if addedType == 1:
			titleColor = None
			imageHDD = "%simages/hdd_icon.png" % serienRecMainPath
		elif addedType == 2:
			titleColor = parseColor('blue').argb()
			imageTimer = "%simages/timer.png" % serienRecMainPath
		elif addedType == 3:
			titleColor = parseColor('green').argb()
		else:
			titleColor = parseColor('red').argb()

		foregroundColor = parseColor('foreground').argb()

		return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 15 * skinFactor, 16 * skinFactor, 16 * skinFactor,
				 loadPNG(leftImage)),
				(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 240 * skinFactor, 26 * skinFactor, 0,
				 RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender, foregroundColor, foregroundColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 29 * skinFactor, 230 * skinFactor,
				 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s - %s" % (datum, startTime)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 265 * skinFactor, 7 * skinFactor, 30 * skinFactor,
				 22 * skinFactor, loadPNG(imageTimer)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 265 * skinFactor, 30 * skinFactor, 30 * skinFactor,
				 22 * skinFactor, loadPNG(imageHDD)),
				(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0,
				 RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, foregroundColor, foregroundColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 498 * skinFactor,
				 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s - %s" % (seasonEpisodeString, title),
				 titleColor, titleColor)
				]

	@staticmethod
	def isAlreadyAdded(addedEpisodes, season, episode, title=None):
		result = False
		# Title is only relevant if season and episode is 0
		# this happen when Wunschliste has no episode and season information
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		if not title:
			for addedEpisode in addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode:
					result = True
					break
		else:
			for addedEpisode in addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode and addedEpisode[2] == title:
					result = True
					break

		return result

	@staticmethod
	def isTimerAdded(addedEpisodes, sender, season, episode, start_unixtime, title=None):
		result = False
		if not title:
			for addedEpisode in addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode and addedEpisode[
					3] == sender.lower() and int(start_unixtime) - (int(STBHelpers.getEPGTimeSpan()) * 60) <= \
						addedEpisode[4] <= int(start_unixtime) + (int(STBHelpers.getEPGTimeSpan()) * 60):
					result = True
					break
		else:
			for addedEpisode in addedEpisodes:
				if ((addedEpisode[0] == season and addedEpisode[1] == episode) or addedEpisode[2] == title) and \
						addedEpisode[3] == sender.lower() and int(start_unixtime) - (
						int(STBHelpers.getEPGTimeSpan()) * 60) <= addedEpisode[4] <= int(start_unixtime) + (
						int(STBHelpers.getEPGTimeSpan()) * 60):
					result = True
					break

		return result

	def countSelectedTransmissionForTimerCreation(self):
		result = 0
		for serien_name, sender, start_unixtime, end_unixtime, staffel, episode, title, status, addedType in self.sendetermine_list:
			if int(status) == 1:
				result += 1

		return result

	def getTimes(self):
		changesMade = False
		if len(self.sendetermine_list) != 0 and self.countSelectedTransmissionForTimerCreation() != 0:
			(activatedTimer, deactivatedTimer) = serienRecSendeTermine.prepareTimer(self.database, self.filterMode, self.seriesWLID, self.seriesFSID, self.sendetermine_list)

			# self.session.open(serienRecRunAutoCheck, False)
			from .SerienRecorderLogScreen import serienRecReadLog
			self.session.open(serienRecReadLog)
			if activatedTimer > 0 or deactivatedTimer > 0:
				changesMade = True

		else:
			self['title'].setText("Keine Sendetermine ausgewählt.")
			print("[SerienRecorder] keine Sendetermine ausgewählt.")

		return changesMade

	@staticmethod
	def createTimer(database, filterMode, wlid, fsid, params, force=True):
		activatedTimer = 0
		deactivatedTimer = 0

		if not force:
			return False, activatedTimer, deactivatedTimer
		else:
			(serien_name, sender, start_unixtime, margin_before, margin_after, end_unixtime, label_serie,
			 staffel, episode, title, dirname, preferredChannel, useAlternativeChannel, vpsSettings, tags,
			 addToDatabase, autoAdjust, epgSeriesName) = params
			# check sender
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = database.getChannelInfo(sender, wlid, filterMode)

			TimerOK = False
			if stbChannel == "":
				SRLogger.writeLog("' %s ' - Kein Box-Sender gefunden → ' %s '" % (serien_name, webChannel))
			elif int(status) == 0:
				SRLogger.writeLog("' %s ' - Box-Sender deaktiviert → ' %s '" % (serien_name, webChannel))
			else:
				from .SerienRecorderTimer import serienRecTimer, serienRecBoxTimer
				timer = serienRecTimer()
				timer_name = serienRecTimer.getTimerName(serien_name, staffel, episode, title, 0)
				timer_description = serienRecTimer.getTimerDescription(serien_name, staffel, episode, title)

				if preferredChannel == 1:
					timer_stbRef = stbRef
					timer_altstbRef = altstbRef
				else:
					timer_stbRef = altstbRef
					timer_altstbRef = stbRef

				# try to get eventID (eit) from epgCache
				if len(epgSeriesName) == 0 or epgSeriesName == serien_name:
					epgSeriesName = ""

				if database.getUpdateFromEPG(fsid, config.plugins.serienRec.eventid.value):

					eit, start_unixtime_eit, end_unixtime_eit = STBHelpers.getStartEndTimeFromEPG(start_unixtime,
					                                                                              end_unixtime,
					                                                                              margin_before,
					                                                                              serien_name, epgSeriesName,
					                                                                              timer_stbRef)
					if eit > 0:
						# Adjust the EPG start/end time with margins
						start_unixtime_eit = int(start_unixtime_eit) - (int(margin_before) * 60)
						end_unixtime_eit = int(end_unixtime_eit) + (int(margin_after) * 60)
				else:
					eit = 0
					start_unixtime_eit = start_unixtime
					end_unixtime_eit = end_unixtime

				konflikt = ""

				# versuche timer anzulegen
				result = serienRecBoxTimer.addTimer(timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit),
				                                    timer_name, timer_description, eit,
				                                    False, dirname, vpsSettings, tags, autoAdjust, None)
				if result["result"]:
					timer.addTimerToDB(serien_name, wlid, fsid, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit, addToDatabase)
					activatedTimer += 1
					TimerOK = True
				else:
					konflikt = result["message"]

				if not TimerOK and useAlternativeChannel:
					# try to get eventID (eit) from epgCache
					if len(epgSeriesName) == 0 or epgSeriesName == serien_name:
						epgSeriesName = ""

					if database.getUpdateFromEPG(fsid, config.plugins.serienRec.eventid.value):
						alt_eit, alt_start_unixtime_eit, alt_end_unixtime_eit = STBHelpers.getStartEndTimeFromEPG(
							start_unixtime, end_unixtime, margin_before, serien_name, epgSeriesName, timer_altstbRef)
					else:
						alt_eit = 0
						alt_start_unixtime_eit = start_unixtime
						alt_end_unixtime_eit = end_unixtime

					alt_start_unixtime_eit = int(alt_start_unixtime_eit) - (int(margin_before) * 60)
					alt_end_unixtime_eit = int(alt_end_unixtime_eit) + (int(margin_after) * 60)

					# versuche timer anzulegen
					result = serienRecBoxTimer.addTimer(timer_altstbRef, str(alt_start_unixtime_eit),
					                                    str(alt_end_unixtime_eit), timer_name,
					                                    timer_description, alt_eit, False,
					                                    dirname, vpsSettings, tags, autoAdjust, None)
					if result["result"]:
						konflikt = None
						timer.addTimerToDB(serien_name, wlid, fsid, staffel, episode, title, str(alt_start_unixtime_eit), timer_altstbRef, webChannel, alt_eit, addToDatabase)
						activatedTimer += 1
						TimerOK = True
					else:
						konflikt = result["message"]

				if (not TimerOK) and konflikt:
					SRLogger.writeLog("' %s ' - ACHTUNG! → %s" % (label_serie, konflikt), True)
					dbMessage = result["message"].replace("In Konflikt stehende Timer vorhanden!", "").strip()

					result = serienRecBoxTimer.addTimer(timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit),
					                                    timer_name, timer_description, eit, True,
					                                    dirname, vpsSettings, tags, autoAdjust, None)
					if result["result"]:
						timer.addTimerToDB(serien_name, wlid, fsid, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit, addToDatabase, False)
						deactivatedTimer += 1
						TimerOK = True
						database.addTimerConflict(dbMessage, start_unixtime_eit, webChannel)

			return TimerOK, activatedTimer, deactivatedTimer

	@staticmethod
	def prepareTimer(database, filterMode, wlid, fsid, sendetermine):

		activatedTimer = 0
		deactivatedTimer = 0

		lt = time.localtime()
		uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		print("---------' Manuelle Timererstellung aus Sendeterminen um %s '---------" % uhrzeit)
		SRLogger.writeLog("\n---------' Manuelle Timererstellung aus Sendeterminen um %s '---------" % uhrzeit, True)
		for serien_name, sender, start_unixtime, end_unixtime, staffel, episode, title, status, addedType in sendetermine:
			if int(status) == 1:
				# initialize strings
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
				label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)

				# setze die vorlauf/nachlauf-zeit
				(margin_before, margin_after) = database.getMargins(fsid, sender,
				                                                         config.plugins.serienRec.margin_before.value,
				                                                         config.plugins.serienRec.margin_after.value)
				start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
				end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

				# get VPS settings for channel
				vpsSettings = database.getVPS(fsid, sender)

				# get tags from marker
				tags = database.getTags(wlid)

				# get addToDatabase for marker
				addToDatabase = database.getAddToDatabase(wlid)

				# get autoAdjust for marker
				autoAdjust = database.getAutoAdjust(wlid, sender)

				# get alternative epg series name
				epgSeriesName = database.getMarkerEPGName(fsid)

				(dirname, dirname_serie) = getDirname(database, serien_name, fsid, staffel)

				(NoOfRecords, preferredChannel, useAlternativeChannel) = database.getPreferredMarkerChannels(
					wlid, config.plugins.serienRec.useAlternativeChannel.value,
					config.plugins.serienRec.NoOfRecords.value)

				params = (serien_name, sender, start_unixtime, margin_before, margin_after, end_unixtime,
				          label_serie, staffel, episode, title, dirname, preferredChannel,
				          bool(useAlternativeChannel), vpsSettings, tags, addToDatabase, autoAdjust, epgSeriesName)

				timerExists = False
				if config.plugins.serienRec.selectBouquets.value and config.plugins.serienRec.preferMainBouquet.value:
					(primary_bouquet_active, secondary_bouquet_active) = database.isBouquetActive(sender)
					if str(episode).isdigit():
						if int(episode) == 0:
							(count_manually, count_primary_bouquet, count_secondary_bouquet) = database.getNumberOfTimersByBouquet(fsid, str(staffel), str(episode), title)
						else:
							(count_manually, count_primary_bouquet, count_secondary_bouquet) = database.getNumberOfTimersByBouquet(fsid, str(staffel), str(episode))
					else:
						(count_manually, count_primary_bouquet, count_secondary_bouquet) = database.getNumberOfTimersByBouquet(fsid, str(staffel), str(episode))
					if count_manually >= NoOfRecords or (count_primary_bouquet >= NoOfRecords or (secondary_bouquet_active and count_secondary_bouquet >= NoOfRecords) or (primary_bouquet_active and count_primary_bouquet >= NoOfRecords)):
						timerExists = True
				else:
					# überprüft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = database.getNumberOfTimers(fsid, str(staffel), str(episode), title, searchOnlyActiveTimers=True)
							bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False, title)
						else:
							bereits_vorhanden = database.getNumberOfTimers(fsid, str(staffel), str(episode), searchOnlyActiveTimers=True)
							bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False)
					else:
						bereits_vorhanden = database.getNumberOfTimers(fsid, str(staffel), str(episode), searchOnlyActiveTimers=True)
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False)

					if (bereits_vorhanden >= NoOfRecords) or (bereits_vorhanden_HDD >= NoOfRecords):
						timerExists = True

				if not timerExists:
					(TimerDone, onTimer, offTimer) = serienRecSendeTermine.createTimer(database, filterMode, wlid, fsid, params)
				else:
					SRLogger.writeLog("' %s ' → Staffel/Episode bereits vorhanden ' %s '" % (
						serien_name, seasonEpisodeString))
					(TimerDone, onTimer, offTimer) = serienRecSendeTermine.createTimer(database, filterMode, wlid, fsid, params, config.plugins.serienRec.forceManualRecording.value)

				activatedTimer += onTimer
				deactivatedTimer += offTimer
				if TimerDone:
					# erstellt das serien verzeichnis und kopiert das Cover in das Verzeichnis
					STBHelpers.createDirectory(fsid, 0, dirname, dirname_serie)

		SRLogger.writeLog("Es wurde(n) %s Timer erstellt." % str(activatedTimer), True)
		print("[SerienRecorder] Es wurde(n) %s Timer erstellt." % str(activatedTimer))
		if deactivatedTimer > 0:
			SRLogger.writeLog("%s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(deactivatedTimer), True)
			print("[SerienRecorder] %s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(deactivatedTimer))
		SRLogger.writeLog("---------' Manuelle Timererstellung aus Sendeterminen beendet '---------", True)
		print("---------' Manuelle Timererstellung aus Sendeterminen beendet '---------")

		return activatedTimer, deactivatedTimer

	def isSeasonAllowed(self, season, episode, markerSeasons, fromEpisode):
		if not markerSeasons and not fromEpisode:
			return True

		allowed = False
		if -2 in markerSeasons:  # 'Manuell'
			allowed = False
		elif (-1 in markerSeasons) and (0 in markerSeasons):  # 'Alle'
			allowed = True
		elif str(season).isdigit():
			if int(season) == 0:
				if str(episode).isdigit():
					if int(episode) < int(fromEpisode):
						allowed = False
					else:
						allowed = True
			elif int(season) in markerSeasons:
				allowed = True
			elif -1 in markerSeasons:  # 'folgende'
				if int(season) >= max(markerSeasons):
					allowed = True
		elif self.database.getSpecialsAllowed(self.seriesWLID):
			allowed = True

		return allowed

	def keyOK(self):
		if self.loading or self['menu_list'].getCurrent() is None:
			return

		sindex = self['menu_list'].getSelectedIndex()
		if len(self.sendetermine_list) != 0:
			if int(self.sendetermine_list[sindex][7]) == 0:
				self.sendetermine_list[sindex][7] = "1"
			else:
				self.sendetermine_list[sindex][7] = "0"
			self.chooseMenuList.setList(list(map(self.buildList_termine, self.sendetermine_list)))

	def keyLeft(self):
		self['menu_list'].pageUp()

	def keyRight(self):
		self['menu_list'].pageDown()

	def keyDown(self):
		self['menu_list'].down()

	def keyUp(self):
		self['menu_list'].up()

	def keyRed(self):
		self.close(self.changesMade)

	def keyGreen(self):
		self.changesMade = self.getTimes()
		if self.changesMade:
			self.searchEvents()

	def keyYellow(self):
		self.sendetermine_list = []
		self.loading = True
		self.chooseMenuList.setList(list(map(self.buildList_termine, self.sendetermine_list)))

		if self.filterMode == 0:
			self.filterMode = 1
			self['text_yellow'].setText("Filter umschalten")
			self.title_txt = "aktive Sender"
		elif self.filterMode == 1:
			self.filterMode = 2
			self['text_yellow'].setText("Filter ausschalten")
			self.title_txt = "Marker Sender"
		else:
			self.filterMode = 0
			self['text_yellow'].setText("Filter einschalten")
			self.title_txt = "alle"

		print("[SerienRecorder] suche ' %s '" % self.seriesName)
		self['title'].setText("Suche ' %s '" % self.seriesName)
		print(self.seriesWLID)

		if self.filterMode == 0:
			webChannels = []
		elif self.filterMode == 1:
			webChannels = self.database.getActiveChannels()
		else:
			webChannels = self.database.getMarkerChannels(self.seriesWLID)

		try:
			transmissions = SeriesServer().doGetTransmissions(self.seriesWLID, 0, webChannels)
		except:
			transmissions = None
		self.resultsEvents(transmissions)

	def keyBlue(self):
		from .SerienRecorderTimerListScreen import serienRecTimerListScreen
		self.session.openWithCallback(self.searchEvents, serienRecTimerListScreen)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close(self.changesMade)
