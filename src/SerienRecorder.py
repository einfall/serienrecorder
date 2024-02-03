# -*- coding: utf-8 -*-
from Components.AVSwitch import AVSwitch
from Components.config import config, configfile

from Tools.Directories import fileExists

from Screens.MessageBox import MessageBox
from Screens.EpgSelection import EPGSelection

from enigma import gPixmapPtr, eTimer

from Tools import Notifications

import os, time, shutil

try:
	import simplejson as json
except ImportError:
	import json

from .SerienRecorderHelpers import isDreamOS, toBinary, toStr
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderLogWriter import SRLogger

# check VPS availability
try:
	from Plugins.SystemPlugins.vps import Vps
except ImportError:
	VPSPluginAvailable = False
else:
	VPSPluginAvailable = True

def setDataBaseFilePath(path):
	global serienRecDataBaseFilePath
	serienRecDataBaseFilePath = path

def getDataBaseFilePath():
	return serienRecDataBaseFilePath

from .SerienRecorderSetupScreen import ReadConfigFile
ReadConfigFile()

serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

if config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
	config.plugins.serienRec.showAllButtons.value = False
else:
	config.plugins.serienRec.showAllButtons.value = True

coverToShow = None
startTimer = None
startTimerConnection = None

#---------------------------------- Common Functions ------------------------------------------

def getCover(self, serien_name, serien_fsid, auto_check=False, forceReload=False):
	if not config.plugins.serienRec.downloadCover.value:
		return

	from .SerienRecorderHelpers import doReplaces
	serien_name = doReplaces(toStr(serien_name))
	jpg_serien_cover_path = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)
	png_serien_cover_path = "%s%s.png" % (config.plugins.serienRec.coverPath.value, serien_name)
	fsid_serien_cover_path = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid)

	try:
		if self and config.plugins.serienRec.showCover.value:
			self['cover'].hide()
			global coverToShow
			coverToShow = fsid_serien_cover_path

		if not fileExists(config.plugins.serienRec.coverPath.value):
			try:
				os.mkdir(config.plugins.serienRec.coverPath.value)
			except:
				Notifications.AddPopup("Cover Pfad (%s) kann nicht angelegt werden.\n\nÜberprüfen Sie den Pfad und die Rechte!" % config.plugins.serienRec.coverPath.value, MessageBox.TYPE_INFO, timeout=10, id="checkFileAccess")
				return

		# Change PNG cover file extension to correct file extension JPG
		if fileExists(png_serien_cover_path):
			os.rename(png_serien_cover_path, jpg_serien_cover_path)

		# Change JPG serien name file name to correct Fernsehserie ID file name
		if not fileExists(fsid_serien_cover_path) and fileExists(jpg_serien_cover_path) and jpg_serien_cover_path != fsid_serien_cover_path:
			os.rename(jpg_serien_cover_path, fsid_serien_cover_path)

		if forceReload and fileExists(fsid_serien_cover_path):
			os.remove(fsid_serien_cover_path)

		if config.plugins.serienRec.refreshPlaceholderCover.value and fileExists(fsid_serien_cover_path) and os.path.getsize(fsid_serien_cover_path) == 0:
			statinfo = os.stat(fsid_serien_cover_path)
			print("[SerienRecorder] path = " + fsid_serien_cover_path + " / statinfo.st_mtime = " + str(statinfo.st_mtime) + " / current time = " + str(time.time()))
			if (statinfo.st_mtime + 5184000) <= time.time(): # Older than 60 days
				os.remove(fsid_serien_cover_path)

		if fileExists(fsid_serien_cover_path):
			if self and config.plugins.serienRec.showCover.value:
				showCover(None, self, fsid_serien_cover_path)
		elif serien_fsid and (config.plugins.serienRec.showCover.value or (config.plugins.serienRec.downloadCover.value and auto_check)):
			try:
				posterURL = SeriesServer().doGetCoverURL(0, serien_fsid)
				#SRLogger.writeLog("Cover URL [%s] (%s) => %s" % (serien_name, serien_fsid, posterURL), True)
				if posterURL:
					from twisted.web import client
					client.downloadPage(toBinary(posterURL), fsid_serien_cover_path).addCallback(showCover, self, fsid_serien_cover_path, False).addErrback(getCoverDataError, self, fsid_serien_cover_path)
				else:
					if config.plugins.serienRec.createPlaceholderCover.value:
						open(fsid_serien_cover_path, "a").close()
			except:
				if config.plugins.serienRec.createPlaceholderCover.value:
					open(fsid_serien_cover_path, "a").close()
				getCoverDataError("failed", self, fsid_serien_cover_path)
	except Exception as e:
		print("Exception loading cover: %s [%s]" % (fsid_serien_cover_path, str(e)))

def getCoverDataError(error, self, serien_cover_path):
	#SRLogger.writeLog("Datenfehler beim Laden des Covers für ' %s ': %s" % (serien_cover_path, str(error)), True)
	print(error)

def showCover(data, self, serien_cover_path, force_show=True):
	if self is not None and config.plugins.serienRec.showCover.value:
		if not force_show:
			global coverToShow
			if coverToShow == serien_cover_path:
				coverToShow = None
			else:
				return
			
		if fileExists(serien_cover_path):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#00000000"))
			if isDreamOS():
				picLoaderResult = self.picload.startDecode(serien_cover_path, False)
			else:
				picLoaderResult = self.picload.startDecode(serien_cover_path, 0, 0, False)

			if picLoaderResult == 0:
				ptr = self.picload.getData()
				if ptr is not None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("[SerienRecorder] Coverfile not found: %s" % serien_cover_path)

def initDB():
	# type: () -> object
	global serienRecDataBaseFilePath
	print("[SerienRecorder] Initializing database...")

	# If database is at old default location (SerienRecorder plugin folder) we have to move the db to new default location
	serienRecMainPath = os.path.dirname(__file__)

	if fileExists("%s/SerienRecorder.db" % serienRecMainPath):
		shutil.move("%s/SerienRecorder.db" % serienRecMainPath, serienRecDataBaseFilePath)

	print("[SerienRecorder] Database file path: %s" % serienRecDataBaseFilePath)
	if not fileExists(serienRecDataBaseFilePath):
		config.plugins.serienRec.databasePath.value = "/etc/enigma2/"
		config.plugins.serienRec.databasePath.save()
		configfile.save()
		SRLogger.writeLog("Datenbankpfad nicht gefunden, auf Standardpfad zurückgesetzt!")
		print("[SerienRecorder] Database path not found, reset to default path")
		Notifications.AddPopup(
			"SerienRecorder Datenbank wurde nicht gefunden.\nDer Standardpfad für die Datenbank wurde wiederhergestellt!",
			MessageBox.TYPE_INFO, timeout=10)
		serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

	try:
		print("[SerienRecorder] Trying to instanciate SerienRecorder database at %s" % serienRecDataBaseFilePath)
		database = SRDatabase(serienRecDataBaseFilePath)
	except:
		print("[SerienRecorder] Database failed to initialize")
		SRLogger.writeLog("Fehler beim Initialisieren der Datenbank")
		Notifications.AddPopup("SerienRecorder Datenbank kann nicht initialisiert werden.\nSerienRecorder wurde beendet!", MessageBox.TYPE_INFO, timeout=10)
		return False

	if os.path.getsize(serienRecDataBaseFilePath) == 0:
		database.initialize(config.plugins.serienRec.dbversion.value)
	else:
		dbVersionMatch = False
		dbIncompatible = False

		isMalformed = database.isMalformed()
		if isMalformed:
			print("[SerienRecorder] Database is malformed")
			SRLogger.writeLog("Die SerienRecorder Datenbank ist beschädigt - der SerienRecorder kann nicht gestartet werden.")
			Notifications.AddPopup("Die SerienRecorder Datenbank ist beschädigt.\nDer SerienRecorder kann nicht gestartet werden!", MessageBox.TYPE_INFO, timeout=10)
			dbIncompatible = True

		dbVersion = database.getVersion()
		if dbVersion:
			if dbVersion == config.plugins.serienRec.dbversion.value:
				dbVersionMatch = True
			elif dbVersion > config.plugins.serienRec.dbversion.value:
				print("[SerienRecorder] Database version is incompatible, it has to be at least: %s" % dbVersion)
				SRLogger.writeLog("Datenbankversion nicht kompatibel: SerienRecorder Version muss mindestens %s sein." % dbVersion)
				Notifications.AddPopup("Die SerienRecorder Datenbank ist mit dieser Version nicht kompatibel.\nEs wird mindestens die SerienRecorder Version %s benötigt!" % dbVersion, MessageBox.TYPE_INFO, timeout=10)
				dbIncompatible = True
		else:
			dbIncompatible = True

		mode = os.R_OK | os.W_OK
		if not os.access(serienRecDataBaseFilePath, mode):
			print("[SerienRecorder] Database file has incorrect permissions!")
			SRLogger.writeLog("Datenbankdatei hat nicht die richtigen Berechtigungen - es müssen Lese- und Schreibrechte gesetzt sein.")
			Notifications.AddPopup("Datenbankdatei hat nicht die richtigen Berechtigungen - es müssen Lese- und Schreibrechte gesetzt sein.", MessageBox.TYPE_INFO, timeout=10)
			dbIncompatible = True

		# Database incompatible - do cleanup
		if dbIncompatible:
			database.close()
			print("[SerienRecorder] Database is incompatible")
			return False

		if not dbVersionMatch:
			print("[SerienRecorder] Database is too old!")
			SRLogger.writeLog("Datenbank ist zu alt - sie muss aktualisiert werden...", True)
			database.close()
			backupSerienRecDataBaseFilePath = "%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value
			SRLogger.writeLog("Erstelle Datenbank Backup - es kann nach erfolgreichem Update gelöscht werden: %s" % backupSerienRecDataBaseFilePath, True)
			shutil.copy(serienRecDataBaseFilePath, backupSerienRecDataBaseFilePath)
			database = SRDatabase(serienRecDataBaseFilePath)
			if database.update(config.plugins.serienRec.dbversion.value):
				print("[SerienRecorder] Database updated from %s to version %s" % (dbVersion, config.plugins.serienRec.dbversion.value))
				SRLogger.writeLog("Datenbank von Version %s auf Version %s aktualisiert" % (dbVersion, config.plugins.serienRec.dbversion.value), True)
			else:
				database.close()
				print("[SerienRecorder] Failed to update database")
				Notifications.AddPopup("SerienRecorder Datenbank konnte nicht aktualisiert werden. Fehler wurden in die Logdatei geschrieben.\nSerienRecorder wurde beendet!", MessageBox.TYPE_INFO, timeout=10)
				return False

	# Analyze database for query optimizer
	try:
		database.optimize()
	except Exception as e:
		database.close()
		print("[SerienRecorder] Failed to access database")
		SRLogger.writeLog("Fehler beim Zugriff auf die Datenbank [%s]" % str(e))
		Notifications.AddPopup("Fehler beim Zugriff auf die Datenbank!\n%s" % str(e), MessageBox.TYPE_INFO, timeout=10)
		return False

	database.close()
	return True

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
			from .SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecSearchResultScreen, seriesName)

	def handleSeriesSearchEnd(self, series_fsid=None):
		if series_fsid:
			from .SerienRecorderMarkerScreen import serienRecMarker
			self.session.open(serienRecMarker, series_fsid)

# ---------------------------------- Main Functions ------------------------------------------

def getNextWakeup():
	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value and config.plugins.serienRec.autochecktype.value == "1":
		print("[SerienRecorder] Deep-Standby WakeUp: AN")
		now = time.localtime()
		current_time = int(time.time())

		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0],
								 config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			print("[SerienRecorder] WakeUp-Timer + 1 day.")
			begin += 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin -= 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		print("[SerienRecorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit)

		return begin
	else:
		print("[SerienRecorder] Deep-Standby WakeUp: AUS")


def autostart(reason, **kwargs):
	if reason == 0 and "session" in kwargs:
		# Boot
		session = kwargs["session"]

		global startTimer
		global startTimerConnection

		lt = time.localtime()
		uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		SRLogger.writeLog("\nBox wurde gestartet - SerienRecorder wurde geladen: %s" % uhrzeit, True)
		print("[SerienRecorder] Start: %s" % uhrzeit)

		def startAutoCheckTimer():
			from .SerienRecorderCheckForRecording import checkForRecordingInstance
			checkForRecordingInstance.initialize(session, False, False)

		if config.plugins.serienRec.autochecktype.value in ("1", "2") and config.plugins.serienRec.timeUpdate.value:
			print("[SerienRecorder] Auto-Check: ON")
			startTimer = eTimer()
			if isDreamOS():
				startTimerConnection = startTimer.timeout.connect(startAutoCheckTimer)
			else:
				startTimer.callback.append(startAutoCheckTimer)
			startTimer.start(60 * 1000, True)
		else:
			print("[SerienRecorder] Auto-Check: OFF")

		# API
		if config.plugins.serienRec.enableWebinterface.value:
			from .SerienRecorderResource import addWebInterface
			addWebInterface(session)

	elif reason == 1:
		# Shutdown
		lt = time.localtime()
		uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		SRLogger.writeLog("\nBox wird heruntergefahren - SerienRecorder wird beendet: %s" % uhrzeit, True)


