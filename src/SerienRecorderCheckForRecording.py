# coding=utf-8

import os, time, threading, datetime, random
import Screens.Standby
# Navigation (RecordTimer)
import NavigationInstance

from Components.config import config, configfile
from Tools import Notifications
from enigma import getDesktop, eTimer
from Screens.MessageBox import MessageBox

from .SerienRecorderHelpers import SRAPIVERSION, STBHelpers, TimeHelpers, isDreamOS, createBackup, getDirname, toStr, PY2
from .SerienRecorder import serienRecDataBaseFilePath, getCover, initDB
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderDatabase import SRDatabase, SRTempDatabase
from .SerienRecorderLogWriter import SRLogger

#autoCheckFinished = False
refreshTimer = None
refreshTimerConnection = None
transmissionFailed = False

########################################################################################################################

class downloadTransmissionsThread(threading.Thread):
	def __init__(self, index, jobs, results):
		threading.Thread.__init__(self)
		self.index = index
		self.jobQueue = jobs
		self.resultQueue = results

	def run(self):
		while not self.jobQueue.empty():
			data = self.jobQueue.get()
			self.download(data)
			self.jobQueue.task_done()

	def download(self, data):
		(seriesID, fsID, timeSpan, markerChannels, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays, limitedChannels) = data
		try:
			isTransmissionFailed = False
			transmissions = SeriesServer().doGetTransmissions(seriesID, timeSpan, markerChannels)
		except:
			isTransmissionFailed = True
			transmissions = None
		self.resultQueue.put((isTransmissionFailed, transmissions, seriesID, fsID, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays, limitedChannels))

class processEMailDataThread(threading.Thread):
	def __init__(self, index, emailData, jobs, results):
		threading.Thread.__init__(self)
		self.index = index
		self.jobQueue = jobs
		self.resultQueue = results
		self.emailData = emailData

	def run(self):
		while not self.jobQueue.empty():
			data = self.jobQueue.get()
			self.process(data)
			self.jobQueue.task_done()

	def process(self, data):
		(markerChannels, seriesID, fsID, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays, markerType, limitedChannels) = data
		transmissions = []
		for key in list(self.emailData.keys()):
			if self.emailData[key][0][0] == seriesTitle:
				fsID = key
				break
		for transmission in self.emailData[fsID]:
			if transmission[1] in markerChannels:
				transmissions.append(transmission[0:-1])

		self.resultQueue.put((transmissions, seriesID, fsID, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays, markerType, limitedChannels))

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
	epgrefresh_instance = None
	__instance = None

	def __init__(self):
		assert not serienRecCheckForRecording.__instance, "serienRecCheckForRecording is a singleton class!"
		serienRecCheckForRecording.__instance = self
		self.session = None
		self.database = None
		self.manuell = False
		self.tvplaner_manuell = False
		self.newSeriesOrEpisodesFound = False
		self.senderListe = {}
		self.markers = []
		self.messageList = []
		self.speedStartTime = 0
		self.speedEndTime = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.noOfRecords = 0
		self.emailData = None
		self.uhrzeit = None
		self.daypage = 0
		self.tempDB = None
		self.autoCheckFinished = False

	def initialize(self, session, manuell, tvplaner_manuell=False):
		self.session = session
		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell

		self.database = None
		self.newSeriesOrEpisodesFound = False
		self.senderListe = {}
		self.markers = []
		self.messageList = []
		self.speedStartTime = 0
		self.speedEndTime = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.noOfRecords = int(config.plugins.serienRec.NoOfRecords.value)
		self.emailData = None
		self.daypage = 0
		self.tempDB = None
		self.autoCheckFinished = False

		print("[SerienRecorder] Initialize checkForRecording manual: %s (with TV-Planer: %s)" % (str(manuell), str(tvplaner_manuell)))

		SRLogger.checkFileAccess()

		lt = time.localtime()
		self.uhrzeit = time.strftime("%a, %d.%m.%Y - %H:%M:%S", lt)
		SRLogger.writeLog("\n---------' %s '---------" % self.uhrzeit, True)

		global refreshTimer
		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

		global refreshTimerConnection
		if refreshTimerConnection:
			refreshTimerConnection = None

		if config.plugins.serienRec.autochecktype.value == "0":
			SRLogger.writeLog("Automatischer Timer-Suchlauf ist deaktiviert - nur manuelle Timersuche", True)
		elif config.plugins.serienRec.autochecktype.value == "1":
			SRLogger.writeLog("Automatischer Timer-Suchlauf ist aktiviert - er wird zur gewählten Uhrzeit gestartet", True)
		elif config.plugins.serienRec.autochecktype.value == "2":
			SRLogger.writeLog("Automatischer Timer-Suchlauf ist aktiviert - er wird nach dem EPGRefresh ausgeführt", True)

		if not self.manuell and config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value) * 60)) * 1000, True)
			print("[SerienRecorder] Timer-Suchlauf Uhrzeit-Timer gestartet.")
			print("[SerienRecorder] Verbleibende Zeit: %s Stunden" % (TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime + int(config.plugins.serienRec.maxDelayForAutocheck.value)))))
			SRLogger.writeLog("Verbleibende Zeit bis zum nächsten automatischen Timer-Suchlauf: %s Stunden\n" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime + int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if self.manuell:
			print("[SerienRecorder] checkRecTimer manuell.")
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

	def isAutoCheckFinished(self):
		return self.autoCheckFinished

	def setAutoCheckFinished(self, finished):
		self.autoCheckFinished = finished

	@staticmethod
	def getNextAutoCheckTimer(lt):
		acttime = (lt.tm_hour * 60 + lt.tm_min)
		deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
		if acttime < deltime:
			deltatime = deltime - acttime
		else:
			deltatime = abs(1440 - acttime + deltime)
		return deltatime

	def setEPGRefreshCallback(self, configentry=None):
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

	def getMarkerCover(self):
		self.database = SRDatabase(serienRecDataBaseFilePath)
		markers = self.database.getAllMarkers(False)
		for marker in markers:
			(ID, Serie, Info, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, ErlaubteStaffelCount, fsID) = marker
			getCover(None, Serie, ID, fsID, True)

	def startCheck(self):
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.autoCheckFinished = False

		print("[SerienRecorder] Starting check")

		lt = time.localtime()
		self.uhrzeit = time.strftime("%a, %d.%m.%Y - %H:%M:%S", lt)

		global refreshTimer
		global refreshTimerConnection

		print("[SerienRecorder] Check file access for log file and backup folder")
		SRLogger.checkFileAccess()
		if config.plugins.serienRec.AutoBackup.value != "0":
			# Try to access the backup directory to wake up the disks
			os.path.exists(config.plugins.serienRec.BackupPath.value)

		SRLogger.writeLog("\n---------' %s '---------" % self.uhrzeit, True)

		if not self.manuell and not initDB():
			self.askForDSB()
			return

		if not self.database.hasMarkers() and not config.plugins.serienRec.tvplaner.value:
			SRLogger.writeLog("\n---------' Timer-Suchlauf gestartet am %s '---------" % self.uhrzeit, True)
			print("[SerienRecorder] check: Tabelle Serien-Marker leer.")
			SRLogger.writeLog("Es sind keine Serien-Marker vorhanden - Timer-Suchlauf kann nicht ausgeführt werden.", True)
			SRLogger.writeLog("---------' Timer-Suchlauf beendet '---------", True)
			self.askForDSB()
			return

		if not self.database.hasChannels():
			SRLogger.writeLog("\n---------' Timer-Suchlauf gestartet am %s '---------" % self.uhrzeit, True)
			print("[SerienRecorder] check: Tabelle Channels leer.")
			SRLogger.writeLog("Es wurden keine Sender zugeordnet - Timer-Suchlauf kann nicht ausgeführt werden.", True)
			SRLogger.writeLog("---------' Timer-Suchlauf beendet '---------", True)
			self.askForDSB()
			return

		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

			if refreshTimerConnection:
				refreshTimerConnection = None

			print("[SerienRecorder] Auto-Check Timer stop.")
			SRLogger.writeLog("Automatischer Timer-Suchlauf Uhrzeit-Timer angehalten.", True)

		self.speedStartTime = time.time()
		print("[SerienRecorder] Stopwatch Start: " + str(self.speedStartTime))
		if config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value) * 60)) * 1000, True)

			print("[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet.")
			print("[SerienRecorder] Verbleibende Zeit: %s Stunden" % (TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime + int(config.plugins.serienRec.maxDelayForAutocheck.value)))))
			SRLogger.writeLog("Automatischer Timer-Suchlauf Uhrzeit-Timer gestartet.", True)
			SRLogger.writeLog("Verbleibende Zeit: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime + int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if config.plugins.serienRec.AutoBackup.value == "before":
			createBackup(self.manuell)

		SRLogger.reset()
		from .SerienRecorderTVPlaner import resetTVPlanerHTMLBackup
		resetTVPlanerHTMLBackup()
		self.database.removeExpiredTimerConflicts()

		# HEADER ###########################################################################################################
		check_type = ""
		if config.plugins.serienRec.tvplaner.value:
			check_type += "TV-Planer "
		elif config.plugins.serienRec.autochecktype == '2':
			check_type += "EPG-Refresh "

		if self.manuell:
			check_type += "manuell"
		else:
			check_type += "auto"

		print("---------' Timer-Suchlauf gestartet am %s (%s) '---------" % (self.uhrzeit, check_type))
		SRLogger.writeLog("\n---------' Timer-Suchlauf gestartet am %s (%s) '---------\n" % (self.uhrzeit, check_type), True)

		# BOX-INFO ###########################################################################################################
		if config.plugins.serienRec.writeLogVersion.value:
			SRLogger.writeLog("Box-Typ: %s" % STBHelpers.getSTBType(), True)
			SRLogger.writeLog("Image: %s" % STBHelpers.getImageVersionString(), True)
			pos = config.skin.primary_skin.value.rfind('/')
			if pos != -1:
				skin = config.skin.primary_skin.value[:pos]
			else:
				skin = "Default Skin"
			SRLogger.writeLog("Box-Skin: %s (%s x %s)\n" % (skin, str(getDesktop(0).size().width()), str(getDesktop(0).size().height())), True)

			SRLogger.writeLog("SerienRecorder Version: %s" % config.plugins.serienRec.showversion.value, True)
			SRLogger.writeLog("Datenbank Schema Version: %s" % str(self.database.getVersion()), True)
			if config.plugins.serienRec.enableWebinterface.value:
				SRLogger.writeLog("Schnittstellen Version: %s" % SRAPIVERSION, True)
			SRLogger.writeLog("SerienRecorder Box ID: %s" % str(config.plugins.serienRec.BoxID.value), True)

		# LOG-SETTINGS ###########################################################################################################
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
			sMsg += "Timer "
			SRLogger.writeLog(sMsg, True)

		self.markers = []
		self.messageList = []

		# teste Verbindung ins Internet
		print("[SerienRecorder] Check internet connection")
		from .SerienRecorderHelpers import testWebConnection
		if not testWebConnection():
			SRLogger.writeLog("\nKeine Verbindung ins Internet. Suchlauf wurde abgebrochen!!\n", True)

			# Statistik
			self.speedEndTime = time.time()
			speedTime = (self.speedEndTime - self.speedStartTime)
			SRLogger.writeLog("---------' Timer-Suchlauf beendet ( Ausführungsdauer: %3.2f Sek.) '---------" % speedTime, True)
			print("[SerienRecorder] ---------' Timer-Suchlauf beendet ( Ausführungsdauer: %3.2f Sek.) '---------" % speedTime)

			SRLogger.backup()
			from .SerienRecorderTVPlaner import backupTVPlanerHTML
			backupTVPlanerHTML()

			self.autoCheckFinished = True

			if config.plugins.serienRec.AutoBackup.value == "after":
				createBackup(self.manuell)

			# in den deep-standby fahren.
			self.askForDSB()
			return

		# Versuche Verzeichnisse zu erreichen
		print("[SerienRecorder] Check configured recording directories")
		try:
			SRLogger.writeLog("\nPrüfe konfigurierte Aufnahmeverzeichnisse:", True)
			recordDirectories = self.database.getRecordDirectories(config.plugins.serienRec.savetopath.value)
			for directory in recordDirectories:
				SRLogger.writeLog("   %s" % directory, True)
				os.path.exists(directory)
		except:
			SRLogger.writeLog("Es konnten nicht alle Aufnahmeverzeichnisse gefunden werden", True)

		if not self.manuell and config.plugins.serienRec.firstscreen.value == "0":
			# Refresh Planer-Cache if not called manually and first screen is Planer
			print("[SerienRecorder] Update series planer data")
			from twisted.internet import reactor
			from .SerienRecorderSeriesPlanner import serienRecSeriesPlanner
			seriesPlanner = serienRecSeriesPlanner()
			reactor.callFromThread(seriesPlanner.updatePlannerData)

		# if config.plugins.serienRec.downloadCover.value:
		#	reactor.callFromThread(self.getMarkerCover())

		self.startCheckTransmissions()

	def startCheckTransmissions(self):
		print("[SerienRecorder] Start check transmissions")

		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.tempDB = SRTempDatabase()
		self.tempDB.initialize()

		# read channels
		self.senderListe = {}
		for s in self.database.getChannels():
			self.senderListe[s[0].lower()] = s[:]

		webChannels = self.database.getActiveChannels()
		SRLogger.writeLog("\nAnzahl aktiver Websender: %d" % len(webChannels), True)
		epgTimeSpan = "Deaktiviert"
		if config.plugins.serienRec.eventid.value:
			epgTimeSpan = "± %d Minuten" % config.plugins.serienRec.epgTimeSpan.value
		SRLogger.writeLog("Eingestellte EPG Suchgrenzen: %s" % epgTimeSpan, True)

		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)
		search_start = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(current_time)))
		search_end = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(future_time)))
		search_rerun_end = time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(future_time + (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400))
		SRLogger.writeLog("Berücksichtige Ausstrahlungstermine zwischen %s und %s" % (search_start, search_end), True)
		SRLogger.writeLog("Berücksichtige Wiederholungen zwischen %s und %s" % (search_start, search_rerun_end), True)

		# hier werden die wunschliste markers eingelesen
		self.emailData = None
		if config.plugins.serienRec.tvplaner.value and (not self.manuell or self.tvplaner_manuell):
			print("[SerienRecorder] Parsing TV-Planer e-mail")
			# When TV-Planer processing is enabled then regular autocheck
			# is only running for the transmissions received by email.
			try:
				from .SerienRecorderTVPlaner import getEmailData
				emailParserThread = backgroundThread(getEmailData)
				emailParserThread.start()
				emailParserThread.join()
				self.emailData = emailParserThread.result
				del emailParserThread
			except:
				SRLogger.writeLog("TV-Planer Verarbeitung fehlgeschlagen!", True)
				print("[SerienRecorder] TV-Planer exception!")
				self.emailData = None
		print("[SerienRecorder] lastFullCheckTime %s" % time.strftime("%a, %d.%m.%Y - %H:%M", time.localtime(int(config.plugins.serienRec.tvplaner_last_full_check.value))))
		if self.emailData is None:
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value)
			config.plugins.serienRec.tvplaner_last_full_check.value = int(time.time())
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()
			if config.plugins.serienRec.tvplaner.value and (not self.manuell and self.tvplaner_manuell):
				if config.plugins.serienRec.showMessageOnTVPlanerError.value:
					timeout = config.plugins.serienRec.showMessageTimeout.value
					if config.plugins.serienRec.showMessageTimeout.value == 0:
						timeout = -1
					self.messageList.append(("Beim Abrufen der TV-Planer E-Mail ist ein Fehler aufgetreten - es wurde ein voller Suchlauf durchgeführt.\nWeitere Informationen wurden ins Log geschrieben.",
					                         MessageBox.TYPE_INFO, timeout, "tvplaner-error"))
					Notifications.AddPopup("Beim Abrufen der TV-Planer E-Mail ist ein Fehler aufgetreten - es wurde ein voller Suchlauf durchgeführt.\nWeitere Informationen wurden ins Log geschrieben.",
					                       MessageBox.TYPE_INFO, timeout=timeout, id="tvplaner-error")
				fullCheck = "- keine TV-Planer Daten - voller Suchlauf"
			else:
				fullCheck = "- voller Suchlauf"
		elif config.plugins.serienRec.tvplaner_full_check.value and (int(config.plugins.serienRec.tvplaner_last_full_check.value) + (int(config.plugins.serienRec.checkfordays.value) - 1) * 86400) < int(time.time()):
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value)
			config.plugins.serienRec.tvplaner_last_full_check.value = int(time.time())
			config.plugins.serienRec.tvplaner_last_full_check.save()
			configfile.save()
			fullCheck = "- Zeit abgelaufen - voller Suchlauf"
		else:
			self.markers = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, list(self.emailData.keys()))
			fullCheck = "- nur Serien der TV-Planer E-Mail"

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
					SRLogger.writeLog("\nGemäß den globalen Einstellungen werden Timer nur aus den Terminen der TV-Planer E-Mail angelegt.\n", True)

				global transmissionFailed
				transmissionFailed = False
				self.tempDB.cleanUp()
				if not (config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_skipSerienServer.value):
					SRLogger.writeLog("\n---------' Verarbeite Daten vom Server %s '---------\n" % fullCheck, True)
					print("[SerienRecorder] Processing data from Serien-Server")

				# Create a job queue to keep the jobs processed by the threads
				# Create a result queue to keep the results of the job threads
				if PY2:
					import Queue
				else:
					import queue as Queue

				jobQueue = Queue.Queue()
				resultQueue = Queue.Queue()

				for serienTitle, SerieUrl, SerieStaffel, SerieSender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays, skipSeriesServer, markerType, fsID in self.markers:
					if config.plugins.serienRec.tvplaner.value:
						if skipSeriesServer is None:
							# No overwrite for this marker - use global setting
							if config.plugins.serienRec.tvplaner_skipSerienServer.value:
								continue
						else:
							# Setting overwritten for this marker
							if skipSeriesServer:
								SRLogger.writeLog("' %s ' - Für diesen Serien-Marker sollen Timer nur aus den Terminen der TV-Planer E-Mail angelegt werden." % serienTitle, True)
								continue
							else:
								SRLogger.writeLog("' %s ' - Für diesen Serien-Marker sollen Timer aus den Terminen des Serien-Servers angelegt werden." % serienTitle, True)

					if markerType == 1:
						# temporary marker for movie recording
						print("[SerienRecorder] ' %s - TV-Planer Film wird ignoriert '" % serienTitle)
						continue

					self.countSerien += 1

					if SerieEnabled:
						# Process only if series is enabled
						limitedChannels = False

						if 'Alle' in SerieSender:
							markerChannels = webChannels
						else:
							markerChannels = SerieSender
							limitedChannels = True

						self.countActivatedSeries += 1
						seriesID = SerieUrl

						jobQueue.put((seriesID, fsID, (int(config.plugins.serienRec.TimeSpanForRegularTimer.value)), markerChannels, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays, limitedChannels))
					else:
						SRLogger.writeLog("' %s ' - Dieser Serien-Marker ist deaktiviert - es werden keine Timer angelegt." % serienTitle, True)

					if -2 in SerieStaffel:
						SRLogger.writeLog("' %s ' - Dieser Serien-Marker steht auf manuell - es werden keine Timer automatisch angelegt." % serienTitle, True)

				# Create the threads
				for i in range(4):
					worker = downloadTransmissionsThread(i, jobQueue, resultQueue)
					worker.setDaemon(True)
					worker.start()

				jobQueue.join()
				while not resultQueue.empty():
					(transmissionFailed, transmissions, seriesID, fsID, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays, limitedChannels) = resultQueue.get()
					self.processTransmission(transmissions, seriesID, fsID, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, limitedChannels, excludedWeekdays, 0)
					resultQueue.task_done()

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
		# has been created by Serien-Marker before. The marker is created automatically,
		# except for the correct url.
		#
		if config.plugins.serienRec.tvplaner.value and self.emailData is not None:
			# check mailbox for TV-Planer EMail and create timer
			SRLogger.writeLog("\n---------' Verarbeite Daten aus TV-Planer E-Mail '---------\n", True)
			print("[SerienRecorder] Processing data from TV-Planer e-mail")

			if PY2:
				import Queue
			else:
				import queue as Queue

			jobQueue = Queue.Queue()
			resultQueue = Queue.Queue()

			for serienTitle, SerieUrl, SerieStaffel, SerieSender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays, skipSeriesServer, markerType, fsID in self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, list(self.emailData.keys())):
				if SerieEnabled:
					# Process only if series is enabled
					limitedChannels = False

					if 'Alle' in SerieSender:
						markerChannels = {x: x for x in webChannels}
					else:
						markerChannels = {x: x for x in SerieSender}
						limitedChannels = True

					jobQueue.put((markerChannels, SerieUrl, fsID, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays, markerType, limitedChannels))
				else:
					SRLogger.writeLog("' %s ' - Dieser Serien-Marker ist deaktiviert - es werden keine Timer angelegt." % serienTitle, True)

				if -2 in SerieStaffel:
					SRLogger.writeLog("' %s ' - Für diesen Serien-Marker sind die Staffeln auf 'manuell' gestellt - es werden keine Timer automatisch angelegt." % serienTitle, True)

			# Create the threads
			for i in range(4):
				worker = processEMailDataThread(i, self.emailData, jobQueue, resultQueue)
				worker.setDaemon(True)
				worker.start()

			jobQueue.join()
			while not resultQueue.empty():
				(transmissions, seriesID, fsID, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays, markerType, limitedChannels) = resultQueue.get()
				self.processTransmission(transmissions, seriesID, fsID, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, limitedChannels, excludedWeekdays, markerType)
				resultQueue.task_done()

		self.createTimer()
		self.checkFinal()

	def createTimer(self, result=True):
		from .SerienRecorderTimer import serienRecTimer
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

		self.autoCheckFinished = True

		(countTimer, countTimerUpdate, countNotActiveTimer, countTimerFromWishlist, self.messageList) = timer.getCounts()

		# Statistik
		self.speedEndTime = time.time()
		print("[SerienRecorder] Stopwatch End: " + str(self.speedEndTime))
		speedTime = (self.speedEndTime - self.speedStartTime)
		if config.plugins.serienRec.eventid.value:
			SRLogger.writeLog("%s/%s Serie(n) sind vorgemerkt dafür wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate)), True)
			print("[SerienRecorder] %s/%s Serie(n) sind vorgemerkt dafür wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate)))
		else:
			SRLogger.writeLog("%s/%s Serie(n) sind vorgemerkt dafür wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer)), True)
			print("[SerienRecorder] %s/%s Serie(n) sind vorgemerkt dafür wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(countTimer)))
		if countNotActiveTimer > 0:
			SRLogger.writeLog("%s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(countNotActiveTimer), True)
			print("[SerienRecorder] %s Timer wurde(n) wegen Konflikten deaktiviert erstellt!" % str(countNotActiveTimer))
		if countTimerFromWishlist > 0:
			SRLogger.writeLog("%s Timer vom Merkzettel wurde(n) erstellt!" % str(countTimerFromWishlist), True)
			print("[SerienRecorder] %s Timer vom Merkzettel wurde(n) erstellt!" % str(countTimerFromWishlist))
		SRLogger.writeLog("---------' Timer-Suchlauf beendet (Ausführungsdauer: %3.2f Sek.) '---------" % speedTime, True)
		print("[SerienRecorder] ---------' Timer-Suchlauf beendet (Ausführungsdauer: %3.2f Sek.) '---------" % speedTime)

		if not self.manuell:
			if config.plugins.serienRec.showNotification.value == "1":
				Notifications.AddPopup("SerienRecorder Suchlauf für neue Timer wurde beendet.", MessageBox.TYPE_INFO, timeout=3, id="Suchlauf wurde beendet")
			elif config.plugins.serienRec.showNotification.value == "2":
				statisticMessage = "Serien vorgemerkt: %s/%s\nTimer erstellt: %s\nTimer aktualisiert: %s\nTimer mit Konflikten: %s\nTimer vom Merkzettel: %s" % (
					str(self.countActivatedSeries), str(self.countSerien), str(countTimer), str(countTimerUpdate),
					str(countNotActiveTimer), str(countTimerFromWishlist))
				newSeasonOrEpisodeMessage = ""
				if self.newSeriesOrEpisodesFound:
					newSeasonOrEpisodeMessage = "\n\nNeuer Serien- oder Staffelbeginn gefunden."

				Notifications.AddPopup("SerienRecorder Suchlauf für neue Timer wurde beendet.\n\n%s%s" % (
					statisticMessage, newSeasonOrEpisodeMessage), MessageBox.TYPE_INFO, timeout=10, id="Suchlauf wurde beendet")

			if config.plugins.serienRec.channelUpdateNotification.value == '1':
				from .SerienRecorderChannelScreen import checkChannelListTimelineness
				channelListUpToDate = checkChannelListTimelineness(self.database)
				if not channelListUpToDate:
					Notifications.AddPopup("Die Senderliste wurde auf dem Serien-Server aktualisiert.\nSie muss auch im SerienRecorder aktualisiert werden.", MessageBox.TYPE_INFO, timeout=0, id="Senderliste aktualisieren")

		return result

	def checkFinal(self):
		print("[SerienRecorder] checkFinal")
		# final processing
		if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_movies.value:
			# remove all serien markers created for movies
			try:
				self.database.removeMovieMarkers()
				print("[SerienRecorder] ' TV-Planer FilmMarker gelöscht '")
			except:
				SRLogger.writeLog("' TV-Planer FilmMarker löschen fehlgeschlagen '", True)
				print("[SerienRecorder] ' TV-Planer FilmMarker löschen fehlgeschlagen '")
			global transmissionFailed
			if transmissionFailed:
				# always do fullcheck after transmission error
				config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
				config.plugins.serienRec.tvplaner_last_full_check.save()
				configfile.save()

		if config.plugins.serienRec.AutoBackup.value == "after":
			createBackup(self.manuell)

		SRLogger.backup()
		from .SerienRecorderTVPlaner import backupTVPlanerHTML
		backupTVPlanerHTML()

		# trigger read of log file
		self.autoCheckFinished = True
		print("[SerienRecorder] checkFinal: autoCheckFinished")
		if config.plugins.serienRec.autochecktype.value == "1":
			lt = time.localtime()
			deltatime = self.getNextAutoCheckTimer(lt)
			SRLogger.writeLog("\nVerbleibende Zeit bis zum nächsten automatischen Timer-Suchlauf: %s Stunden\n" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime + int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)
			if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_full_check.value:
				autoCheckDays = ((int(config.plugins.serienRec.tvplaner_last_full_check.value) + (int(config.plugins.serienRec.checkfordays.value) - 1) * 86400) - int(time.time())) / 86400
				if autoCheckDays < 0:
					autoCheckDays = 0
				SRLogger.writeLog("Verbleibende Zeit bis zum nächsten vollen Timer-Suchlauf: %d Tage" % autoCheckDays, True)

		self.tempDB = None
		self.database = None

		# in den deep-standby fahren.
		self.askForDSB()

	def processTransmission(self, data, serien_wlid, serien_fsid, serien_name, staffeln, AbEpisode, AnzahlAufnahmen, current_time, future_time, limitedChannels, excludedWeekdays=None, markerType=0):
		if data is None:
			SRLogger.writeLog("Fehler beim Abrufen und Verarbeiten der Ausstrahlungstermine [%s]" % serien_name, True)
			# print("[SerienRecorder] processTransmissions: no Data")
			return

		print("[SerienRecorder] processTransmissions: %r [%d]" % (toStr(serien_name), len(data)))

		if len(data) == 0 and limitedChannels:
			SRLogger.writeLogFilter("channels", "' %s ' Es wurden keine Ausstrahlungstermine gefunden, die Sender sind am Marker eingeschränkt." % serien_name)

		(fromTime, toTime) = self.database.getTimeSpan(serien_wlid, config.plugins.serienRec.globalFromTime.value, config.plugins.serienRec.globalToTime.value)
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

			# if there is no season or episode number it can be a special
			# but if we have more than one special and wunschliste.de does not
			# give us an episode number we are unable to differentiate between these specials
			if not staffel and not episode:
				staffel = "S"
				episode = "00"

			# initialize strings
			seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
			label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)

			if not config.plugins.serienRec.forceRecording.value:
				if (int(fromTime) > 0) or (int(toTime) < (23 * 60) + 59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						print("[SerienRecorder] processTransmissions time range ignore: %r" % serien_name)
						timeRangeConfigured = "%s:%s - %s:%s" % (str(int(fromTime) // 60).zfill(2), str(int(fromTime) % 60).zfill(2), str(int(toTime) // 60).zfill(2), str(int(toTime) % 60).zfill(2))
						timeRangeTransmission = "%s:%s - %s:%s" % (str(int(start_time) // 60).zfill(2), str(int(start_time) % 60).zfill(2), str(int(end_time) // 60).zfill(2), str(int(end_time) % 60).zfill(2))
						SRLogger.writeLogFilter("timeRange", "' %s ' - Sendung (%s) nicht in Zeitspanne (%s)" % (label_serie, timeRangeTransmission, timeRangeConfigured))
						continue

			# Process channel relevant data

			##############################
			#
			# CHECK
			#
			# ueberprueft welche sender aktiviert und eingestellt sind.
			#
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(sender)
			if stbChannel == "" and altstbChannel == "":
				SRLogger.writeLogFilter("channels", "' %s ' - Box-Sender nicht gefunden ' → ' %s '" % (label_serie, webChannel))
				continue

			if int(status) == 0:
				SRLogger.writeLogFilter("channels", "' %s ' - Box-Sender deaktiviert → ' %s '" % (label_serie, webChannel))
				continue

			##############################
			#
			# CHECK
			#
			# ueberprueft welche staffel(n) erlaubt sind
			#
			serieAllowed = False
			if -2 in staffeln:  # 'Manuell'
				serieAllowed = False
			elif (-1 in staffeln) and (0 in staffeln):  # 'Alle'
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
								SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Episode nicht erlaubt → ' %s ' → ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
							continue
						else:
							serieAllowed = True
				elif int(staffel) in staffeln:
					serieAllowed = True
				elif -1 in staffeln:  # 'folgende'
					if int(staffel) >= max(staffeln):
						serieAllowed = True
			elif self.database.getSpecialsAllowed(serien_wlid):
				serieAllowed = True

			vomMerkzettel = False
			if not serieAllowed:
				if self.database.hasBookmark(serien_fsid, staffel, episode):
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
						SRLogger.writeLogFilter("allowedEpisodes", "' %s ' - Staffel nicht erlaubt → ' %s ' → ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
				continue

			updateFromEPG = self.database.getUpdateFromEPG(serien_fsid, config.plugins.serienRec.eventid.value)

			(dirname, dirname_serie) = getDirname(self.database, serien_name, serien_fsid, staffel)
			self.tempDB.addTransmission([(current_time, future_time, serien_name, serien_wlid, serien_fsid, markerType, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, altstbChannel, altstbRef, dirname, AnzahlAufnahmen,
			                              fromTime, toTime, int(vomMerkzettel), excludedWeekdays, updateFromEPG)])
		self.tempDB.commitTransaction()

	def askForDSB(self):
		if not self.manuell:
			if config.plugins.serienRec.afterAutocheck.value != "0":
				if config.plugins.serienRec.DSBTimeout.value > 0 and not Screens.Standby.inStandby:
					print("[SerienRecorder] Try to display shutdown notification...")
					try:
						notificationText = "Soll der SerienRecorder die Box in den Ruhemodus (Standby) schalten?"
						if config.plugins.serienRec.afterAutocheck.value == "2":
							notificationText = "Soll der SerienRecorder die Box ausschalten (Deep-Standby)?"
						Notifications.AddNotificationWithCallback(self.gotoDeepStandby, MessageBox, text=notificationText, type=MessageBox.TYPE_YESNO, timeout=config.plugins.serienRec.DSBTimeout.value, default=True)
					except Exception as e:
						print("[SerienRecorder] Could not display shutdown notification - shutdown box without notification... (%s)" % str(e))
						self.gotoDeepStandby(True)
				else:
					self.gotoDeepStandby(True)

	def gotoDeepStandby(self, answer):
		if answer:
			if config.plugins.serienRec.afterAutocheck.value == "2":
				if not NavigationInstance.instance.RecordTimer.isRecording():
					for each in self.messageList:
						Notifications.RemovePopup(each[3])

					print("[SerienRecorder] Going into Deep-Standby")
					SRLogger.writeLog("Gehe in den Deep-Standby")
					if Screens.Standby.inStandby:
						# from RecordTimer import RecordTimerEntry
						# RecordTimerEntry.TryQuitMainloop()
						self.session.open(Screens.Standby.TryQuitMainloop, 1)
					else:
						Notifications.AddNotificationWithID("Shutdown", Screens.Standby.TryQuitMainloop, 1)
				else:
					print("[SerienRecorder] A running recording prevents Deep-Standby")
					SRLogger.writeLog("Eine laufende Aufnahme verhindert den Deep-Standby")
			else:
				if not Screens.Standby.inStandby:
					print("[SerienRecorder] Going into standby")
					SRLogger.writeLog("Gehe in den Standby")
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
		print("[SerienRecorder] Es ist ein Fehler aufgetreten - die Daten konnten nicht abgerufen/verarbeitet werden: (%s)" % error)


# Create class instance as singleton
checkForRecordingInstance = serienRecCheckForRecording()