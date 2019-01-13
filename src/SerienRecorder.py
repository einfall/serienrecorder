# -*- coding: utf-8 -*-
from Components.AVSwitch import AVSwitch
from Components.config import config, configfile

from twisted.internet import reactor, defer

from Tools.Directories import fileExists

from Screens.MessageBox import MessageBox
from Screens.EpgSelection import EPGSelection
import Screens.Standby

from enigma import getDesktop, gPixmapPtr, eTimer

# Navigation (RecordTimer)
import NavigationInstance

from Tools import Notifications

import httplib, os, re, threading, Queue, time, shutil, datetime, random

try:
	import simplejson as json
except ImportError:
	import json

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"

from SerienRecorderHelpers import STBHelpers, TimeHelpers, doReplaces, isDreamOS, getSeriesIDByURL, createBackup, getDirname
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderDatabase import SRDatabase, SRTempDatabase
from SerienRecorderLogWriter import SRLogger

# check VPS availability
try:
	from Plugins.SystemPlugins.vps import Vps
except ImportError as ie:
	VPSPluginAvailable = False
else:
	VPSPluginAvailable = True

serienRecCoverPath = "/tmp/serienrecorder/"

from SerienRecorderSetupScreen import ReadConfigFile
ReadConfigFile()

if config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
	config.plugins.serienRec.showAllButtons.value = False
else:
	config.plugins.serienRec.showAllButtons.value = True

serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

autoCheckFinished = False
refreshTimer = None
refreshTimerConnection = None
coverToShow = None
runAutocheckAtExit = False
startTimer = None
startTimerConnection = None
transmissionFailed = False

#---------------------------------- Common Functions ------------------------------------------

def retry(times, func, *args, **kwargs):
	"""retry a defer function

	@param times: how many times to retry
	@param func: defer function
	"""
	errorList = []
	deferred = defer.Deferred()
	def run():
		d = func(*args, **kwargs)
		d.addCallbacks(deferred.callback, error)
	def error(retryError):
		errorList.append(retryError)
		# Retry
		if len(errorList) < times:
			SRLogger.writeLog("Fehler beim Abrufen von ' %s ', versuche es noch %d mal..." % (args[1], times - len(errorList)), True)
			run()
		# Fail
		else:
			SRLogger.writeLog("Abrufen von ' %s ' auch nach mehreren Versuchen nicht möglich!" % args[1], True)
			deferred.errback('retryError')
	run()
	return deferred

def getCover(self, serien_name, serien_id, auto_check = False):
	if not config.plugins.serienRec.downloadCover.value:
		return

	serien_name = doReplaces(serien_name.encode('utf-8'))
	serien_nameCover = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)
	png_serien_nameCover = "%s%s.png" % (config.plugins.serienRec.coverPath.value, serien_name)

	try:
		if self and config.plugins.serienRec.showCover.value:
			self['cover'].hide()
			global coverToShow
			coverToShow = serien_nameCover

		if not fileExists(config.plugins.serienRec.coverPath.value):
			try:
				os.mkdir(config.plugins.serienRec.coverPath.value)
			except:
				Notifications.AddPopup("Cover Pfad (%s) kann nicht angelegt werden.\n\nÜberprüfen Sie den Pfad und die Rechte!" % config.plugins.serienRec.coverPath.value, MessageBox.TYPE_INFO, timeout=10, id="checkFileAccess")

		# Change PNG cover file extension to correct file extension JPG
		if fileExists(png_serien_nameCover):
			os.rename(png_serien_nameCover, serien_nameCover)

		if fileExists(serien_nameCover):
			if self and config.plugins.serienRec.showCover.value:
				showCover(serien_nameCover, self, serien_nameCover)
		elif serien_id and (config.plugins.serienRec.showCover.value or (config.plugins.serienRec.downloadCover.value and auto_check)):
			try:
				posterURL = SeriesServer().doGetCoverURL(int(serien_id), serien_name)
				#writeLog("Cover URL [%s] => %s" % (serien_name, posterURL), True)
				if posterURL:
					from twisted.web.client import downloadPage
					downloadPage(posterURL, serien_nameCover).addCallback(showCover, self, serien_nameCover, False).addErrback(getCoverDataError, self, serien_nameCover)
				else:
					if config.plugins.serienRec.createPlaceholderCover.value:
						open(serien_nameCover, "a").close()
			except:
				if config.plugins.serienRec.createPlaceholderCover.value:
					open(serien_nameCover, "a").close()
				getCoverDataError("failed", self, serien_nameCover)
	except:
		SRLogger.writeLog("Fehler bei Laden des Covers: %s " % serien_nameCover, True)

def getCoverDataError(error, self, serien_nameCover):
	if self is not None and self.ErrorMsg:
		SRLogger.writeLog("Fehler bei: %s (%s)" % (self.ErrorMsg, serien_nameCover), True)
		print "[SerienRecorder] Fehler bei: %s" % self.ErrorMsg
	else:
		ErrorMsg = "Cover-Suche (%s) auf 'Wunschliste.de' erfolglos" % serien_nameCover
		SRLogger.writeLog("Fehler: %s" % ErrorMsg, True)
		print "[SerienRecorder] Fehler: %s" % ErrorMsg
		SRLogger.writeLog("      %s" % str(error), True)
	print error

def showCover(data, self, serien_nameCover, force_show=True):
	if self is not None and config.plugins.serienRec.showCover.value:
		if not force_show:
			global coverToShow
			if coverToShow == serien_nameCover:
				coverToShow = None
			else:
				return
			
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#00000000"))
			self.picLoaderResult = 1
			if isDreamOS():
				self.picLoaderResult = self.picload.startDecode(serien_nameCover, False)
			else:
				self.picLoaderResult = self.picload.startDecode(serien_nameCover, 0, 0, False)

			if self.picLoaderResult == 0:
				ptr = self.picload.getData()
				if ptr is not None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print "[SerienRecorder] Coverfile not found: %s" % serien_nameCover

def initDB():
	# type: () -> object
	global serienRecDataBaseFilePath

	# If database is at old default location (SerienRecorder plugin folder) we have to move the db to new default location
	if fileExists("%sSerienRecorder.db" % serienRecMainPath):
		shutil.move("%sSerienRecorder.db" % serienRecMainPath, serienRecDataBaseFilePath)

	if not fileExists(serienRecDataBaseFilePath):
		config.plugins.serienRec.databasePath.value = "/etc/enigma2/"
		config.plugins.serienRec.databasePath.save()
		configfile.save()
		SRLogger.writeLog("Datenbankpfad nicht gefunden, auf Standardpfad zurückgesetzt!")
		print "[SerienRecorder] Datenbankpfad nicht gefunden, auf Standardpfad zurückgesetzt!"
		Notifications.AddPopup(
			"SerienRecorder Datenbank wurde nicht gefunden.\nDer Standardpfad für die Datenbank wurde wiederhergestellt!",
			MessageBox.TYPE_INFO, timeout=10)
		serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

	try:
		database = SRDatabase(serienRecDataBaseFilePath)
	except:
		SRLogger.writeLog("Fehler beim Initialisieren der Datenbank")
		print "[SerienRecorder] Fehler beim Initialisieren der Datenbank"
		Notifications.AddPopup("SerienRecorder Datenbank kann nicht initialisiert werden.\nSerienRecorder wurde beendet!", MessageBox.TYPE_INFO, timeout=10)
		return False

	if os.path.getsize(serienRecDataBaseFilePath) == 0:
		database.initialize(config.plugins.serienRec.dbversion.value)
	else:
		dbVersionMatch = False
		dbIncompatible = False

		dbVersion = database.getVersion()
		if dbVersion:
			if dbVersion == config.plugins.serienRec.dbversion.value:
				dbVersionMatch = True
			elif dbVersion > config.plugins.serienRec.dbversion.value:
				SRLogger.writeLog("Datenbankversion nicht kompatibel: SerienRecorder Version muss mindestens %s sein." % dbVersion)
				Notifications.AddPopup("Die SerienRecorder Datenbank ist mit dieser Version nicht kompatibel.\nAktualisieren Sie mindestens auf Version %s!" % dbVersion, MessageBox.TYPE_INFO, timeout=10)
				dbIncompatible = True
		else:
			dbIncompatible = True

		# Database incompatible - do cleanup
		if dbIncompatible:
			SRLogger.writeLog("Database is incompatible", True)
			database.close()
			return False

		if not dbVersionMatch:
			SRLogger.writeLog("Database ist zu alt - sie muss aktualisiert werden...", True)
			database.close()
			backupSerienRecDataBaseFilePath = "%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value
			SRLogger.writeLog("Erstelle Datenbank Backup - es kann nach erfolgreichem Update gelöscht werden: %s" % backupSerienRecDataBaseFilePath, True)
			shutil.copy(serienRecDataBaseFilePath, backupSerienRecDataBaseFilePath)
			database = SRDatabase(serienRecDataBaseFilePath)
			database.update(config.plugins.serienRec.dbversion.value)
			SRLogger.writeLog("Datenbank von Version %s auf Version %s aktualisiert" % (dbVersion, config.plugins.serienRec.dbversion.value), True)

	# Analyze database for query optimizer
	database.optimize()
	database.close()
	return True

def testWebConnection():
	conn = httplib.HTTPConnection("www.google.com", timeout=10)
	try:
		conn.request("GET", "/")
		#data = conn.getresponse()
		#print "[SerienRecorder] Status: %s   and reason: %s" % (data.status, data.reason)
		conn.close()
		return True
	except:
		conn.close()
	return False



#----------------------------------------------------------------------------------------------

class serienRecEPGSelection(EPGSelection):
	def __init__(self, *args):
		EPGSelection.__init__(self, *args)
		self.skinName = "EPGSelection"

	def infoKeyPressed(self):
		self.timerAdd()

	def timerAdd(self):
		cur = self["list"].getCurrent()
		evt = cur[0]
		if not evt:
			return

		seriesName = evt and evt.getEventName() or ""
		if seriesName:
			from SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecSearchResultScreen, seriesName)

	def handleSeriesSearchEnd(self, seriesName=None):
		if seriesName:
			from SerienRecorderMarkerScreen import serienRecMarker
			self.session.open(serienRecMarker, seriesName)


class downloadTransmissionsThread(threading.Thread):

	def __init__(self, jobs, results):
		threading.Thread.__init__(self)
		self.jobQueue = jobs
		self.resultQueue = results

	def run(self):
		while True:
			data = self.jobQueue.get()
			self.download(data)
			self.jobQueue.task_done()

	def download(self, data):
		(seriesID, timeSpan, markerChannels, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays) = data
		try:
			isTransmissionFailed = False
			transmissions = SeriesServer().doGetTransmissions(seriesID, timeSpan, markerChannels)
		except:
			isTransmissionFailed = True
			transmissions = None
		self.resultQueue.put((isTransmissionFailed, transmissions, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays))

class backgroundThread(threading.Thread):
	def __init__(self, fnc):
		threading.Thread.__init__(self)
		self.result = None
		self.fnc = fnc
		self.setDaemon(True)

	def run(self):
		self.result = self.fnc()

########################################################################################################################

class serienRecCheckForRecording:

	instance = None
	epgrefresh_instance = None

	def __init__(self, session, manuell, tvplaner_manuell=False):
		assert not serienRecCheckForRecording.instance, "Go is a singleton class!"
		serienRecCheckForRecording.instance = self
		self.session = session
		self.database = None
		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell
		print "[SerienRecorder] 1__init__ tvplaner_manuell: ", tvplaner_manuell
		self.newSeriesOrEpisodesFound = False
		self.senderListe = {}
		self.markers = []
		self.messageList = []
		self.speedStartTime = 0
		self.speedEndTime = 0
		self.konflikt = ""
		self.count_url = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.noOfRecords = int(config.plugins.serienRec.NoOfRecords.value)
		self.emailData = None

		SRLogger.checkFileAccess()

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		SRLogger.writeLog("\n---------' %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
		self.daypage = 0

		global refreshTimer
		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

		global refreshTimerConnection
		if refreshTimerConnection:
			refreshTimerConnection = None

		self.tempDB = None

		if config.plugins.serienRec.autochecktype.value == "0":
			SRLogger.writeLog("Auto-Check ist deaktiviert - nur manuelle Timersuche", True)
		elif config.plugins.serienRec.autochecktype.value == "1":
			SRLogger.writeLog("Auto-Check ist aktiviert - er wird zur gewählten Uhrzeit gestartet", True)
		elif config.plugins.serienRec.autochecktype.value == "2":
			SRLogger.writeLog("Auto-Check ist aktiviert - er wird nach dem EPGRefresh ausgeführt", True)

		if not self.manuell and config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value)*60)) * 1000, True)
			print "[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet."
			print "[SerienRecorder] Verbleibende Zeit: %s Stunden" % (TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))))
			SRLogger.writeLog("Verbleibende Zeit bis zum nächsten Auto-Check: %s Stunden\n" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if self.manuell:
			print "[SerienRecorder] checkRecTimer manuell."
			global runAutocheckAtExit
			runAutocheckAtExit = False
			self.startCheck()
			self.manuell = False
			self.tvplaner_manuell = False
		else:
			try:
				from Plugins.Extensions.EPGRefresh.EPGRefresh import epgrefresh
				self.epgrefresh_instance = epgrefresh
				config.plugins.serienRec.autochecktype.addNotifier(self.setEPGRefreshCallback)
			except Exception as e:
				SRLogger.writeLog("EPGRefresh plugin nicht installiert! " + str(e), True)

	@staticmethod
	def getNextAutoCheckTimer(lt):
		acttime = (lt.tm_hour * 60 + lt.tm_min)
		deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
		if acttime < deltime:
			deltatime = deltime - acttime
		else:
			deltatime = abs(1440 - acttime + deltime)
		return deltatime

	def setEPGRefreshCallback(self, configentry = None):
		try:
			if self.epgrefresh_instance:
				if config.plugins.serienRec.autochecktype.value == "2":
					self.epgrefresh_instance.addFinishNotifier(self.startCheck)
				else:
					self.epgrefresh_instance.removeFinishNotifier(self.startCheck)
		except Exception as e:
			try:
				from Tools.HardwareInfoVu import HardwareInfoVu
				pass
			except:
				SRLogger.writeLog("Um die EPGRefresh Optionen nutzen zu können, muss mindestens die EPGRefresh Version 2.1.1 installiert sein. " + str(e), True)

	def startCheck(self):
		self.database = SRDatabase(serienRecDataBaseFilePath)
		global autoCheckFinished
		autoCheckFinished = False

		print "[SerienRecorder] settings:"
		print "[SerienRecorder] manuell:", self.manuell
		print "[SerienRecorder] tvplaner_manuell:", self.tvplaner_manuell
		print "[SerienRecorder] uhrzeit check:", config.plugins.serienRec.timeUpdate.value

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		global refreshTimer
		global refreshTimerConnection

		SRLogger.checkFileAccess()

		SRLogger.writeLog("\n---------' %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)

		if not self.manuell and not initDB():
			self.askForDSB()
			return

		if not self.database.hasMarkers() and not config.plugins.serienRec.tvplaner and not config.plugins.serienRec.tvplaner_create_marker:
			SRLogger.writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle SerienMarker leer."
			SRLogger.writeLog("Es sind keine Serien-Marker vorhanden - Auto-Check kann nicht ausgeführt werden.", True)
			SRLogger.writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			self.askForDSB()
			return

		if not self.database.hasChannels():
			SRLogger.writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle Channels leer."
			SRLogger.writeLog("Es wurden keine Sender zugeordnet - Auto-Check kann nicht ausgeführt werden.", True)
			SRLogger.writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			self.askForDSB()
			return

		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

			if refreshTimerConnection:
				refreshTimerConnection = None

			print "[SerienRecorder] Auto-Check Timer stop."
			SRLogger.writeLog("Auto-Check stop.", True)

		if config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value)*60)) * 1000, True)

			print "[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet."
			print "[SerienRecorder] Verbleibende Zeit: %s Stunden" % (TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))))
			SRLogger.writeLog("Auto-Check Uhrzeit-Timer gestartet.", True)
			SRLogger.writeLog("Verbleibende Zeit: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if config.plugins.serienRec.AutoBackup.value == "before":
			createBackup()

		SRLogger.reset()
		self.database.removeExpiredTimerConflicts()

		if self.tvplaner_manuell and config.plugins.serienRec.tvplaner.value:
			print "\n---------' Starte Check um %s (TV-Planer manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			SRLogger.writeLog("\n---------' Starte Check um %s (TV-Planer manuell) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		elif self.manuell:
			print "\n---------' Starte Check um %s (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			SRLogger.writeLog("\n---------' Starte Check um %s (manuell) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		elif config.plugins.serienRec.tvplaner.value:
			print "\n---------' Starte Auto-Check um %s (TV-Planer auto) '-------------------------------------------------------------------------------" % self.uhrzeit
			SRLogger.writeLog("\n---------' Starte Auto-Check um %s (TV-Planer auto) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		else:
			print "\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------" % self.uhrzeit
			SRLogger.writeLog("\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
			if config.plugins.serienRec.showNotification.value in ("1", "3"):
				Notifications.AddPopup("SerienRecorder Suchlauf nach neuen Timern wurde gestartet.", MessageBox.TYPE_INFO, timeout=3, id="Suchlauf wurde gestartet")

		if config.plugins.serienRec.writeLogVersion.value:
			SRLogger.writeLog("STB Type: %s\nImage: %s" % (STBHelpers.getSTBType(), STBHelpers.getImageVersionString()), True)
			SRLogger.writeLog("SR Version: %s\nDatenbank Version: %s" % (config.plugins.serienRec.showversion.value, str(self.database.getVersion())), True)
			SRLogger.writeLog("Skin Auflösung: %s x %s" % (str(getDesktop(0).size().width()), str(getDesktop(0).size().height())), True)

		sMsg = "\nDEBUG Filter: "
		if config.plugins.serienRec.writeLogChannels.value:
			sMsg += "Senderliste "
		if config.plugins.serienRec.writeLogAllowedEpisodes.value:
			sMsg += "Episoden "
		if config.plugins.serienRec.writeLogAdded.value:
			sMsg += "Added "
		if config.plugins.serienRec.writeLogDisk.value:
			sMsg += "Disk "
		if config.plugins.serienRec.writeLogTimeRange.value:
			sMsg += "Tageszeit "
		if config.plugins.serienRec.writeLogTimeLimit.value:
			sMsg += "Zeitlimit "
		if config.plugins.serienRec.writeLogTimerDebug.value:
			sMsg += "Timer Debug "
			SRLogger.writeLog(sMsg, True)

		self.markers = []
		self.messageList = []
		self.speedStartTime = time.clock()

		# teste Verbindung ins Internet
		if not testWebConnection():
			SRLogger.writeLog("\nKeine Verbindung ins Internet. Check wurde abgebrochen!!\n", True)

			# Statistik
			self.speedEndTime = time.clock()
			speedTime = (self.speedEndTime - self.speedStartTime)
			SRLogger.writeLog("---------' Auto-Check beendet ( Ausführungsdauer: %3.2f Sek.)'-------------------------------------------------------------------------" % speedTime, True)
			print "[SerienRecorder] ---------' Auto-Check beendet ( Ausführungsdauer: %3.2f Sek.)'----------------------------------------------------------------------------" % speedTime

			SRLogger.backup()

			global autoCheckFinished
			autoCheckFinished = True

			if config.plugins.serienRec.AutoBackup.value == "after":
				createBackup()

			# in den deep-standby fahren.
			self.askForDSB()
			return

		# Versuche Verzeichnisse zu erreichen
		try:
			SRLogger.writeLog("\nPrüfe konfigurierte Aufnahmeverzeichnisse:", True)
			recordDirectories = self.database.getRecordDirectories(config.plugins.serienRec.savetopath.value)
			for directory in recordDirectories:
				SRLogger.writeLog("   %s" % directory, True)
				os.path.exists(directory)
		except:
			SRLogger.writeLog("Es konnten nicht alle Aufnahmeverzeichnisse gefunden werden", True)

		# suche nach neuen Serien, Covern und Planer-Cache
		from SerienRecorderSeriesPlanner import serienRecSeriesPlanner
		seriesPlanner = serienRecSeriesPlanner(self.manuell)
		seriesPlanner.updatePlanerData()

		self.startCheckTransmissions()

	def startCheckTransmissions(self):
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.tempDB = SRTempDatabase()
		self.tempDB.initialize()

		# read channels
		self.senderListe = {}
		for s in self.database.getChannels():
			self.senderListe[s[0].lower()] = s[:]

		webChannels = self.database.getActiveChannels()
		SRLogger.writeLog("\nAnzahl aktiver Websender: %d" % len(webChannels), True)
			
		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)
		search_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
		search_end = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(future_time)))
		search_rerun_end = time.strftime("%d.%m.%Y - %H:%M", time.localtime(future_time + (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400))
		SRLogger.writeLog("Berücksichtige Ausstrahlungstermine zwischen %s und %s" % (search_start, search_end), True)
		SRLogger.writeLog("Berücksichtige Wiederholungen zwischen %s und %s" % (search_start, search_rerun_end), True)
		
		# hier werden die wunschliste markers eingelesen
		self.emailData = None
		if config.plugins.serienRec.tvplaner.value and (not self.manuell or self.tvplaner_manuell):
			# When TV-Planer processing is enabled then regular autocheck
			# is only running for the transmissions received by email.
			try:
				from SerienRecorderTVPlaner import getEmailData
				emailParserThread = backgroundThread(getEmailData)
				emailParserThread.start()
				emailParserThread.join()
				self.emailData = emailParserThread.result
			except:
				SRLogger.writeLog("TV-Planer Verarbeitung fehlgeschlagen!", True)
				print "[SerienRecorder] TV-Planer exception!"
				self.emailData = None
		print "[SerienRecorder] lastFullCheckTime %s" % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(config.plugins.serienRec.tvplaner_last_full_check.value)))
		if self.emailData is None:
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value)
			config.plugins.serienRec.tvplaner_last_full_check.value = int(time.time())
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()
			if config.plugins.serienRec.tvplaner.value:
				fullCheck = "- keine TV-Planer Daten - voller Suchlauf '"
			else:
				fullCheck = "- voller Suchlauf '"
		elif config.plugins.serienRec.tvplaner_full_check.value and (int(config.plugins.serienRec.tvplaner_last_full_check.value) + (int(config.plugins.serienRec.checkfordays.value) - 1) * 86400) < int(time.time()):
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value)
			config.plugins.serienRec.tvplaner_last_full_check.value = int(time.time())
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()
			fullCheck = "- Zeit abgelaufen - voller Suchlauf '-------"
		else:
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, self.emailData.keys())
			fullCheck = "- nur Serien der TV-Planer E-Mail '---------"
		self.count_url = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.noOfRecords = int(config.plugins.serienRec.NoOfRecords.value)

		# regular processing through serienrecorder server
		# TODO: save all transmissions in files to protect from temporary SerienServer fails
		#       data will be read by the file reader below and used for timer programming
		if len(self.markers) > 0:
			while True:
				if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_skipSerienServer.value:
					# Skip serien server processing
					break

				global transmissionFailed
				transmissionFailed = False
				self.tempDB.cleanUp()
				SRLogger.writeLog("\n---------' Verarbeite Daten vom Server %s---------------------------\n" % fullCheck, True)

				# Create a job queue to keep the jobs processed by the threads
				# Create a result queue to keep the results of the job threads
				jobQueue = Queue.Queue()
				resultQueue = Queue.Queue()

				#SRLogger.writeLog("Active threads: %d" % threading.active_count(), True)
				# Create the threads
				for i in range(2):
					worker = downloadTransmissionsThread(jobQueue, resultQueue)
					worker.setDaemon(True)
					worker.start()

				for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,SerieEnabled,excludedWeekdays in self.markers:
					if SerieUrl.startswith('https://www.wunschliste.de/spielfilm'):
						# temporary marker for movie recording
						print "[SerienRecorder] ' %s - TV-Planer Film wird ignoriert '" % serienTitle
						continue
					self.countSerien += 1
					if SerieEnabled:
						# Download only if series is enabled
						if 'Alle' in SerieSender:
							markerChannels = webChannels
						else:
							markerChannels = SerieSender

						self.countActivatedSeries += 1
						seriesID = getSeriesIDByURL(SerieUrl)
						if seriesID is None or seriesID == 0:
							# This is a marker created by TV Planer function - fix url
							print "[SerienRecorder] fix seriesID for %r" % serienTitle
							try:
								seriesID = SeriesServer().getIDByFSID(SerieUrl[str.rindex(SerieUrl, '/')+1:])
							except:
								SRLogger.writeLog("' %s - Abfrage der Serien ID beim Serien-Server fehlgeschlagen - ignoriert '" % serienTitle, True)
								print "[SerienRecorder] ' %s - Abfrage der Serien ID beim Serien-Server fehlgeschlagen - ignoriert '" % serienTitle
								continue

							if seriesID is not None and seriesID != 0:
								try:
									getCover(None, serienTitle, seriesID, True)
								except:
									SRLogger.writeLog("' %s - Abruf des Covers fehlgeschlagen - ignoriert '" % serienTitle, True)
									print "[SerienRecorder] ' %s - Abruf des Covers fehlgeschlagen - ignoriert '" % serienTitle
								Url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(seriesID)
								# look if Series with this ID already exists
								if not self.database.markerExists(Url):
									print "[SerienRecorder] %r %r %r" % (serienTitle, str(seriesID), Url)
									try:
										self.database.updateMarkerURL(serienTitle, Url)
										SRLogger.writeLog("' %s - TV-Planer Marker -> URL %s - Korrektur erfolgreich '" % (serienTitle, Url), True)
										print "[SerienRecorder] ' %s - TV-Planer Marker -> URL %s - Korrektur erfolgreich '" % (serienTitle, Url)
									except:
										SRLogger.writeLog("' %s - TV-Planer Marker -> URL %s - Korrektur fehlgeschlagen ' " % (serienTitle, Url), True)
										print "[SerienRecorder] ' %s - TV-Planer Marker -> URL %s - Korrektur fehlgeschlagen '" % (serienTitle, Url)
							else:
								SRLogger.writeLog("' %s - TV-Planer Marker ohne Serien ID -> ignoriert '" % (serienTitle,), True)
								print "[SerienRecorder] ' %s - TV-Planer Marker ohne Serien ID -> ignoriert '" % (serienTitle,)
								continue

						jobQueue.put((seriesID, (int(config.plugins.serienRec.TimeSpanForRegularTimer.value)), markerChannels, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays))

				jobQueue.join()
				while not resultQueue.empty():
					(transmissionFailed, transmissions, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays) = resultQueue.get()
					self.processTransmission(transmissions, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays)
					resultQueue.task_done()

				self.createTimer()
				break
		# 
		# In order to provide an emergency recording service when serien server is down or
		# because Wunschliste isn't accessable, it is now possible to use the TV Wunschliste
		# TV-Planer Infomails.
		# 
		# With an account at www.wunschliste.de it is possible to mark series to appear at
		# "TV-Planer" screen. This screen shows the transmissions of up to a week in advance.
		# In "Einstellungen" it is possible to enable Infomails about TV-Planer. This Infomails
		# can now be used by SerienRecorder to create timers without any further access to
		# Wunschliste, and therefore avoids hitting Wunschliste with the enormous
		# internet traffic that was caused by the many boxes with SerienRecorder.
		#
		# Wunschliste Settings:
		# - put your favourite series on TV-Planer
		# - enable TV-Planer Infomails in "Einstellungen"
		# - set Vorlauf (i.e. 1 day)
		# - set Programmtag-Beginn (i.e. 5.00 Uhr)
		# - set MailFormat to HTML+Text (currently only HTML emails are recognized)
		#
		# When this has been finished the first TV-Planer email will be received next day.
		# 
		# SerienRecorder Settings:
		# - enable TVPlaner feature
		# - set email server, login, password and possibly modify the other parameters
		# - set the autocheck time to about 1 h after the time you receive the TV-planer emails
		#
		# Now every time the regular SerienRecorder autocheck runs, received 
		# TV-Planer emails will be used to program timers, even no marker 
		# has been created by SerienMarker before. The marker is created automatically, 
		# except for the correct url.  
		#
		if config.plugins.serienRec.tvplaner.value and self.emailData is not None:
			# check mailbox for TV-Planer EMail and create timer
			downloads = []
			self.tempDB.cleanUp()
			SRLogger.writeLog("\n---------' Verarbeite TV-Planer E-Mail '-----------------------------------------------------------\n", True)
			download = None
			ds = defer.DeferredSemaphore(tokens=1)
			for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,SerieEnabled,excludedWeekdays in self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, self.emailData.keys()):
				self.countSerien += 1
				print serienTitle
				if SerieEnabled:
					# Download only if series is enabled
					if 'Alle' in SerieSender:
						markerChannels = { x : x for x in webChannels }
					else:
						markerChannels = { x : x for x in SerieSender }
					# markerChannels contains dictionary of all allowed senders
					self.countActivatedSeries += 1
					download = retry(0, ds.run, self.downloadEmail, serienTitle, markerChannels)
					download.addErrback(self.dataError, SerieUrl)
					download.addCallback(self.processTransmission, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays)
					download.addErrback(self.dataError, SerieUrl)
					downloads.append(download)

			if download:
				download.addCallbacks(self.createTimer, self.dataError)
		
		# this is only for experts that have data files available in a directory
		# TODO: use saved transmissions for programming timer
		if config.plugins.serienRec.readdatafromfiles.value and len(self.markers) > 0:
			# use this only when WL is down and you have copies of the webpages on disk in serienrecorder/data
			##('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
			downloads = []
			SRLogger.writeLog("\n---------' Verarbeite Daten von Dateien '---------------------------------------------------------------\n", True)
			c1 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>(?:\((.*?)x(.*?)\).)*<span class="titel">(.*?)</span></td></tr>')
			c2 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(\S+x\S+))(.*?)\).<span class="titel">(.*?)</span></td></tr>')
			ds = defer.DeferredSemaphore(tokens=1)
			for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,SerieEnabled,excludedWeekdays in self.markers:
				self.countSerien += 1
				if SerieEnabled:
					# Download only if series is enabled
					self.countActivatedSeries += 1
					download = retry(1, ds.run, self.downloadFile, SerieUrl)
					download.addCallback(self.parseWebpage,c1,c2,serienTitle,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,current_time,future_time,excludedWeekdays)
					download.addErrback(self.dataError,SerieUrl)
					downloads.append(download)
				
			# run file data check
			finished = defer.DeferredList(downloads).addCallback(self.createTimer).addErrback(self.dataError)
		
		self.checkFinal()

	def createTimer(self, result=True):
		from SerienRecorderTimer import serienRecTimer
		timer = serienRecTimer()
		timer.setTempDB(self.tempDB)

		# versuche deaktivierte Timer zu erstellen
		timer.activate()

		# jetzt die Timer erstellen
		for x in range(self.noOfRecords):
			timer.search(x)

		# gleiche alte Timer mit EPG ab
		current_time = int(time.time())
		timer.adjustEPGtimes(current_time)
		SRLogger.writeLog("\n", True)

		# Datenbank aufräumen
		self.database.rebuild()
		self.tempDB.rebuild()

		global autoCheckFinished
		autoCheckFinished = True

		(countTimer, countTimerUpdate, countNotActiveTimer, countTimerFromWishlist, self.messageList) = timer.getCounts()

		# Statistik
		self.speedEndTime = time.clock()
		speedTime = (self.speedEndTime - self.speedStartTime)
		if config.plugins.serienRec.eventid.value:
			SRLogger.writeLog("%s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate)), True)
			print "[SerienRecorder] %s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate))
		else:
			SRLogger.writeLog("%s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer)), True)
			print "[SerienRecorder] %s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer))
		if countNotActiveTimer > 0:
			SRLogger.writeLog("%s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(countNotActiveTimer), True)
			print "[SerienRecorder] %s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(countNotActiveTimer)
		if countTimerFromWishlist > 0:
			SRLogger.writeLog("%s Timer vom Merkzettel wurde(n) erstellt!" % str(countTimerFromWishlist), True)
			print "[SerienRecorder] %s Timer vom Merkzettel wurde(n) erstellt!" % str(countTimerFromWishlist)
		SRLogger.writeLog("---------' Auto-Check beendet (Ausführungsdauer: %3.2f Sek.)'---------------------------------------------------------------------------" % speedTime, True)
		print "[SerienRecorder] ---------' Auto-Check beendet (Ausführungsdauer: %3.2f Sek.)'-------------------------------------------------------------------------------" % speedTime
		if (config.plugins.serienRec.showNotification.value in ("2", "3")) and (not self.manuell):
			statisticMessage = "Serien vorgemerkt: %s/%s\nTimer erstellt: %s\nTimer aktualisiert: %s\nTimer mit Konflikten: %s\nTimer vom Merkzettel: %s" % (
			str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate),
			str(countNotActiveTimer), str(countTimerFromWishlist))
			newSeasonOrEpisodeMessage = ""
			if self.newSeriesOrEpisodesFound:
				newSeasonOrEpisodeMessage = "\n\nNeuer Serien- oder Staffelbeginn gefunden"

			Notifications.AddPopup("SerienRecorder Suchlauf für neue Timer wurde beendet.\n\n%s%s" % (
			statisticMessage, newSeasonOrEpisodeMessage), MessageBox.TYPE_INFO, timeout=10, id="Suchlauf wurde beendet")

		return result

	def checkFinal(self):
		print "[SerienRecorder] checkFinal"
		# final processing
		if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_movies.value:
			# remove all serien markers created for movies
			try:
				self.database.removeMovieMarkers()
				print "[SerienRecorder] ' TV-Planer FilmMarker gelöscht '"
			except:
				SRLogger.writeLog("' TV-Planer FilmMarker löschen fehlgeschlagen '", True)
				print "[SerienRecorder] ' TV-Planer FilmMarker löschen fehlgeschlagen '"
			global transmissionFailed
			if transmissionFailed: 
				# always do fullcheck after transmission error
				config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
				config.plugins.serienRec.tvplaner_last_full_check.save()
				configfile.save()

		if config.plugins.serienRec.AutoBackup.value == "after":
			createBackup()

		SRLogger.backup()

		# trigger read of log file
		global autoCheckFinished
		autoCheckFinished = True
		print "[SerienRecorder] checkFinal: autoCheckFinished"
		if config.plugins.serienRec.autochecktype.value == "1":
			lt = time.localtime()
			deltatime = self.getNextAutoCheckTimer(lt)
			SRLogger.writeLog("\nVerbleibende Zeit bis zum nächsten Auto-Check: %s Stunden\n" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)
			if config.plugins.serienRec.tvplaner_full_check.value:
				autoCheckDays = ((int(config.plugins.serienRec.tvplaner_last_full_check.value) + (int(config.plugins.serienRec.checkfordays.value) - 1) * 86400) - int(time.time())) / 86400
				if autoCheckDays < 0:
					autoCheckDays = 0
				SRLogger.writeLog("Verbleibende Zeit bis zum nächsten vollen Auto-Check: %d Tage" % autoCheckDays, True)

		self.tempDB = None
		self.database = None

		# in den deep-standby fahren.
		self.askForDSB()

	def processTransmission(self, data, serien_name, staffeln, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays=None):

		print "[SerienRecorder] processTransmissions: %r" % serien_name
		self.count_url += 1

		if data is None:
			SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der Ausstrahlungstermine [%s]" % serien_name, True)
			#print "[SerienRecorder] processTransmissions: no Data"
			return

		(fromTime, toTime) = self.database.getTimeSpan(serien_name, config.plugins.serienRec.globalFromTime.value, config.plugins.serienRec.globalToTime.value)
		if self.noOfRecords < AnzahlAufnahmen:
			self.noOfRecords = AnzahlAufnahmen

		TimeSpan_time = int(future_time)
		if config.plugins.serienRec.forceRecording.value:
			TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400

		# loop over all transmissions
		self.tempDB.beginTransaction()
		for current_serien_name, sender, startzeit, endzeit, staffel, episode, title, status in data:
			start_unixtime = startzeit
			end_unixtime = endzeit

			# install missing covers
			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			STBHelpers.createDirectory(current_serien_name, dirname, dirname_serie, True)

			# setze die vorlauf/nachlauf-zeit
			(margin_before, margin_after) = self.database.getMargins(serien_name, sender, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			if not config.plugins.serienRec.forceRecording.value:
				if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						print "[SerienRecorder] processTransmissions time range ignore: %r" % serien_name
						continue

			# if there is no season or episode number it can be a special
			# but if we have more than one special and wunschliste.de does not
			# give us an episode number we are unable to differentiate between these specials
			if not staffel and not episode:
				staffel = "S"
				episode = "00"

			# initialize strings
			seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
			label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)

			# Process channel relevant data

			##############################
			#
			# CHECK
			#
			# ueberprueft welche sender aktiviert und eingestellt sind.
			#
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(sender)
			if stbChannel == "":
				SRLogger.writeLogFilter("channels", "' %s ' - STB-Sender nicht gefunden ' -> ' %s '" % (label_serie, webChannel))
				continue

			if int(status) == 0:
				SRLogger.writeLogFilter("channels", "' %s ' - STB-Sender deaktiviert -> ' %s '" % (label_serie, webChannel))
				continue

			##############################
			#
			# CHECK
			#
			# ueberprueft welche staffel(n) erlaubt sind
			#
			serieAllowed = False
			if -2 in staffeln:                          	# 'Manuell'
				serieAllowed = False
			elif (-1 in staffeln) and (0 in staffeln):		# 'Alle'
				serieAllowed = True
			elif str(staffel).isdigit():
				if int(staffel) == 0:
					if str(episode).isdigit():
						if int(episode) < int(AbEpisode):
							if config.plugins.serienRec.writeLogAllowedEpisodes.value:
								liste = staffeln[:]
								liste.sort()
								liste.reverse()
								if -1 in staffeln:
									liste.remove(-1)
									liste[0] = "ab %s" % liste[0]
								liste.reverse()
								liste.insert(0, "0 ab E%s" % str(AbEpisode).zfill(2))
								SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Episode nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
							continue
						else:
							serieAllowed = True
				elif int(staffel) in staffeln:
					serieAllowed = True
				elif -1 in staffeln:		# 'folgende'
					if int(staffel) >= max(staffeln):
						serieAllowed = True
			elif self.database.getSpecialsAllowed(serien_name):
				serieAllowed = True

			vomMerkzettel = False
			if not serieAllowed:
				if self.database.hasBookmark(serien_name, staffel, episode):
					SRLogger.writeLog("' %s ' - Timer vom Merkzettel wird angelegt @ %s" % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True

			if not serieAllowed:
				if config.plugins.serienRec.writeLogAllowedEpisodes.value:
					liste = staffeln[:]
					liste.sort()
					liste.reverse()
					if -1 in staffeln:
						liste.remove(-1)
						liste[0] = "ab %s" % liste[0]
					liste.reverse()
					if str(episode).isdigit():
						if int(episode) < int(AbEpisode):
							liste.insert(0, "0 ab E%s" % str(AbEpisode).zfill(2))
					if -2 in staffeln:
						liste.remove(-2)
						liste.insert(0, "Manuell")
						SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Staffel nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
				continue


			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit, new_end_unixtime, new_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, stbRef)
			alt_eit = 0
			alt_end_unixtime = end_unixtime
			alt_start_unixtime = start_unixtime
			if altstbRef:
				alt_eit, alt_end_unixtime, alt_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, altstbRef)

			updateFromEPG = self.database.getUpdateFromEPG(serien_name)
			if updateFromEPG is False:
				new_start_unixtime = start_unixtime
				new_end_unixtime = end_unixtime
				alt_end_unixtime = end_unixtime
				alt_start_unixtime = start_unixtime

			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			self.tempDB.addTransmission([(current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays, updateFromEPG)])
		self.tempDB.commitTransaction()

	# This has been included again to allow direct parsing of stored data files
	# when serienserver is down.
	# 
	# TODO: remove timer programming and return same data as downloadTransmissions()
	# 
	def parseWebpage(self, data, c1, c2, serien_name, staffeln, allowedSender, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays=None):
		#data = processDownloadedData(data)
		self.count_url += 1
		raw = c1.findall(data)
		raw2 = c2.findall(data)
		raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])

		def y(l):
			(day, month) = l[1].split('.')
			(start_hour, start_min) = l[2].split('.')
			now = datetime.datetime.now()
			if int(month) < now.month:
				return time.mktime((int(now.year) + 1, int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))
			else:
				return time.mktime((int(now.year), int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
		raw.sort(key=y)
		
		# check for parsing error
		if not raw:
			# parsing error -> nothing to do
			return
		
		(fromTime, toTime) = self.database.getTimeSpan(serien_name, config.plugins.serienRec.globalFromTime.value, config.plugins.serienRec.globalToTime.value)
		if self.noOfRecords < AnzahlAufnahmen:
			self.noOfRecords = AnzahlAufnahmen
		
		TimeSpan_time = int(future_time)
		if config.plugins.serienRec.forceRecording.value:
			TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400
		
		# loop over all transmissions
		self.tempDB.beginTransaction()
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')

			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = startzeit.split('.')
			(end_hour, end_min) = endzeit.split('.')
			
			start_unixtime = TimeHelpers.getUnixTimeAll(start_min, start_hour, day, month)
			
			if int(start_hour) > int(end_hour):
				end_unixtime = TimeHelpers.getNextDayUnixtime(end_min, end_hour, day, month)
			else:
				end_unixtime = TimeHelpers.getUnixTimeAll(end_min, end_hour, day, month)
			
			# setze die vorlauf/nachlauf-zeit
			(margin_before, margin_after) = self.database.getMargins(serien_name, sender, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			# The transmission list is sorted by date, so it is save to break if we reach the time span for regular timers
			#if config.plugins.serienRec.breakTimersuche.value and (int(start_unixtime) > int(TimeSpan_time)):
			#		# We reached the maximal time range to look for transmissions, so we can break here
			#		break
			
			if not config.plugins.serienRec.forceRecording.value:
				if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						continue

			if not staffel and not episode:
				staffel = "0"
				episode = "00"
			
			# initialize strings
			seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
			label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)
			
			# Process channel relevant data
			
			##############################
			#
			# CHECK
			#
			# ueberprueft welche sender aktiviert und eingestellt sind.
			#
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(sender)
			if stbChannel == "":
				SRLogger.writeLogFilter("channels", "' %s ' - STB-Sender nicht gefunden ' -> ' %s '" % (label_serie, webChannel))
				continue
			
			if int(status) == 0:
				SRLogger.writeLogFilter("channels", "' %s ' - STB-Sender deaktiviert -> ' %s '" % (label_serie, webChannel))
				continue
			
			##############################
			#
			# CHECK
			#
			# ueberprueft ob der sender zum sender von der Serie aus dem serien marker passt.
			#
			serieAllowed = False
			if 'Alle' in allowedSender:
				serieAllowed = True
			elif sender in allowedSender:
				serieAllowed = True
			
			if not serieAllowed:
				SRLogger.writeLogFilter("channels", "' %s ' - Sender nicht erlaubt -> %s -> %s" % (label_serie, sender, allowedSender))
				continue
			
			##############################
			#
			# CHECK
			#
			# ueberprueft welche staffel(n) erlaubt sind
			#
			serieAllowed = False
			if -2 in staffeln:                          	# 'Manuell'
				serieAllowed = False
			elif (-1 in staffeln) and (0 in staffeln):		# 'Alle'
				serieAllowed = True
			elif str(staffel).isdigit():
				if int(staffel) == 0:
					if str(episode).isdigit():
						if int(episode) < int(AbEpisode):
							if config.plugins.serienRec.writeLogAllowedEpisodes.value:
								liste = staffeln[:]
								liste.sort()
								liste.reverse()
								if -1 in staffeln:
									liste.remove(-1)
									liste[0] = "ab %s" % liste[0]
								liste.reverse()
								liste.insert(0, "0 ab E%s" % str(AbEpisode).zfill(2))
								SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Episode nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
							continue
						else:
							serieAllowed = True
				elif int(staffel) in staffeln:
					serieAllowed = True
				elif -1 in staffeln:		# 'folgende'
					if int(staffel) >= max(staffeln):
						serieAllowed = True
			elif self.database.getSpecialsAllowed(serien_name):
				serieAllowed = True
			
			vomMerkzettel = False
			if not serieAllowed:
				if self.database.hasBookmark(serien_name, staffel, episode):
					SRLogger.writeLog("' %s ' - Timer vom Merkzettel wird angelegt @ %s" % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True

			if not serieAllowed:
				if config.plugins.serienRec.writeLogAllowedEpisodes.value:
					liste = staffeln[:]
					liste.sort()
					liste.reverse()
					if -1 in staffeln:
						liste.remove(-1)
						liste[0] = "ab %s" % liste[0]
					liste.reverse()
					if str(episode).isdigit():
						if int(episode) < int(AbEpisode):
							liste.insert(0, "0 ab E%s" % str(AbEpisode).zfill(2))
					if -2 in staffeln:
						liste.remove(-2)
						liste.insert(0, "Manuell")
					SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Staffel nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
				continue
			
			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit, new_end_unixtime, new_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, stbRef)
			alt_eit = 0
			alt_end_unixtime = end_unixtime
			alt_start_unixtime = start_unixtime
			if altstbRef:
				alt_eit, alt_end_unixtime, alt_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, altstbRef)
			
			updateFromEPG = self.database.getUpdateFromEPG(serien_name)
			if updateFromEPG is False:
				new_start_unixtime = start_unixtime
				new_end_unixtime = end_unixtime
				alt_end_unixtime = end_unixtime
				alt_start_unixtime = start_unixtime

			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			self.tempDB.addTransmission([(current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays, updateFromEPG)])
		self.tempDB.commitTransaction()

	@staticmethod
	def downloadFile(url):
		#print "[Serien Recorder] call %s" % url
		try:
			pageFile = open("%sdata/" % serienRecMainPath + url.split("=")[1], "r")
			text = pageFile.read()
			pageFile.close()
		except:
			text = None
		return text

	def downloadEmail(self, seriesName, markerChannels):
		transmissions = []
		for key in self.emailData.keys():
			if self.emailData[key][0][0] == seriesName:
				seriesName = key
				break
		for transmission in self.emailData[seriesName]:
			if transmission[1] in markerChannels:
				transmissions.append(transmission[0:-1])
		return transmissions

	def askForDSB(self):
		if not self.manuell:
			if config.plugins.serienRec.afterAutocheck.value != "0":
				if config.plugins.serienRec.DSBTimeout.value > 0 and not Screens.Standby.inStandby:
					print "[SerienRecorder] Try to display shutdown notification..."
					try:
						notificationText = "Soll der SerienRecorder die Box in den Ruhemodus (Standby) schalten?"
						if config.plugins.serienRec.afterAutocheck.value == "2":
							notificationText = "Soll der SerienRecorder die Box ausschalten (Deep-Standby)?"
						Notifications.AddNotificationWithCallback(self.gotoDeepStandby, MessageBox, text=notificationText, type=MessageBox.TYPE_YESNO, timeout=config.plugins.serienRec.DSBTimeout.value, default=True)
					except Exception as e:
						print "[SerienRecorder] Could not display shutdown notification - shutdown box without notification... (%s)" % str(e)
						self.gotoDeepStandby(True)
				else:
					self.gotoDeepStandby(True)

	def gotoDeepStandby(self, answer):
		if answer:
			if config.plugins.serienRec.afterAutocheck.value == "2":
				if not NavigationInstance.instance.RecordTimer.isRecording():
					for each in self.messageList:
						Notifications.RemovePopup(each[3])

					print "[SerienRecorder] gehe in Deep-Standby"
					SRLogger.writeLog("gehe in Deep-Standby")
					if Screens.Standby.inStandby:
						from RecordTimer import RecordTimerEntry
						RecordTimerEntry.TryQuitMainloop()
					else:
						Notifications.AddNotificationWithID("Shutdown", Screens.Standby.TryQuitMainloop, 1)
				else:
					print "[SerienRecorder] Eine laufende Aufnahme verhindert den Deep-Standby"
					SRLogger.writeLog("Eine laufende Aufnahme verhindert den Deep-Standby")
			else:
				print "[SerienRecorder] gehe in Standby"
				SRLogger.writeLog("gehe in Standby")
				Notifications.AddNotification(Screens.Standby.Standby)

	def checkSender(self, channel):
		if channel.lower() in self.senderListe:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.senderListe[channel.lower()]
		else:
			webChannel = channel
			stbChannel = ""
			stbRef = ""
			altstbChannel = ""
			altstbRef = ""
			status = "0"
		return webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status

	@staticmethod
	def dataError(error):
		print "[SerienRecorder] Es ist ein Fehler aufgetreten - die Daten konnten nicht abgerufen/verarbeitet werden: (%s)" % error

# ---------------------------------- Main Functions ------------------------------------------

def getNextWakeup():
	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value and config.plugins.serienRec.autochecktype.value == "1":
		print "[SerienRecorder] Deep-Standby WakeUp: AN"
		now = time.localtime()
		current_time = int(time.time())

		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0],
		                         config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			print "[SerienRecorder] WakeUp-Timer + 1 day."
			begin += 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin -= 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		print "[SerienRecorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit

		return begin
	else:
		print "[SerienRecorder] Deep-Standby WakeUp: AUS"


def autostart(reason, **kwargs):
	if reason == 0 and "session" in kwargs:
		session = kwargs["session"]

		global startTimer
		global startTimerConnection
		lt = time.localtime()
		uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		SRLogger.writeLog("\nSerienRecorder Start: %s" % uhrzeit, True)

		def startAutoCheckTimer():
			serienRecCheckForRecording(session, False, False)

		if config.plugins.serienRec.autochecktype.value in ("1", "2") and config.plugins.serienRec.timeUpdate.value:
			print "[SerienRecorder] Auto-Check: AN"
			startTimer = eTimer()
			if isDreamOS():
				startTimerConnection = startTimer.timeout.connect(startAutoCheckTimer)
			else:
				startTimer.callback.append(startAutoCheckTimer)
			startTimer.start(60 * 1000, True)
		else:
			print "[SerienRecorder] Auto-Check: AUS"

# API
# from SerienRecorderResource import addWebInterfaceForDreamMultimedia
# addWebInterfaceForDreamMultimedia(session)



