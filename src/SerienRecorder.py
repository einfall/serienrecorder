# -*- coding: utf-8 -*-
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaTest
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Components.PluginComponent import plugins
from Components.Button import Button
from Components.VideoWindow import VideoWindow
from Components.ServicePosition import ServicePositionGauge
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config, ConfigInteger, ConfigSelection, getConfigListEntry, ConfigText, ConfigDirectory, ConfigYesNo, configfile, ConfigSelection, ConfigSubsection, ConfigPIN, NoSave, ConfigNothing, ConfigClock, ConfigSelectionNumber
from Components.ScrollLabel import ScrollLabel
from Components.FileList import FileList
from Components.Sources.StaticText import StaticText

from Plugins.Plugin import PluginDescriptor

from twisted.web.client import getPage
from twisted.web.client import downloadPage
from twisted.web import client, error as weberror
from twisted.internet import reactor, defer

from HTMLParser import HTMLParser

from Tools.NumericalTextInput import NumericalTextInput
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import pathExists, fileExists, SCOPE_SKIN_IMAGE, resolveFilename

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.InputBox import InputBox
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.EpgSelection import EPGSelection
from Screens.InfoBar import MoviePlayer
import Screens.Standby

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, eServiceReference, getDesktop, loadJPG, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM, gPixmapPtr, ePicLoad, eTimer, eServiceCenter
import sys, os, base64, re, time, shutil, datetime, codecs, urllib, urllib2, random, itertools, traceback
from skin import parseColor, loadSkin, parseFont
import imaplib
import email
import quopri

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

from ServiceReference import ServiceReference

from Components.UsageConfig import preferredTimerPath, preferredInstantRecordPath

# Navigation (RecordTimer)
import NavigationInstance

# Timer
from RecordTimer import RecordTimerEntry, RecordTimer, parseEvent, AFTEREVENT
from Components.TimerSanityCheck import TimerSanityCheck

# EPGCache & Event
from enigma import eEPGCache, iServiceInformation

from Tools import Notifications

import sqlite3, httplib
import cPickle as pickle
import xmlrpclib

try:
	import simplejson as json
except ImportError:
	import json

import SerienRecorderHelpers
from SerienRecorderSplashScreen import *
from SerienRecorderStartupInfoScreen import *
from SerienRecorderUpdateScreen import *
from SerienRecorderAboutScreen import *
from SerienRecorderSeriesServer import *
from SerienRecorderChannelScreen import *
from SerienRecorderScreenHelpers import *
from SerienRecorderEpisodesScreen import *
from SerienRecorderMarkerScreen import *
from SerienRecorderShowSeasonBeginsScreen import *
from SerienRecorderDatabase import *

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"
serienRecCoverPath = "/tmp/serienrecorder/"
InfoFile = "%sStartupInfoText" % serienRecMainPath

try:
	default_before = int(config.recording.margin_before.value)
	default_after = int(config.recording.margin_after.value)
except:
	default_before = 0
	default_after = 0

def ReadConfigFile():
	config.plugins.serienRec = ConfigSubsection()
	config.plugins.serienRec.savetopath = ConfigText(default = "/media/hdd/movie/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.databasePath = ConfigText(default = "/etc/enigma2/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.coverPath = ConfigText(default = serienRecCoverPath, fixed_size=False, visible_width=80)
	
	choices = [("Skinpart", "Skinpart"), ("", "SerienRecorder 1"), ("Skin2", "SerienRecorder 2"), ("AtileHD", "AtileHD"), ("StyleFHD", "StyleFHD"), ("Black Box", "Black Box")]
	try:
		t = list(os.walk("%sskins" % serienRecMainPath))
		for x in t[0][1]:
			if x not in ("Skin2", "AtileHD", "StyleFHD", "Black Box"):
				choices.append((x, x))
	except:
		pass
	config.plugins.serienRec.SkinType = ConfigSelection(choices = choices, default="") 
	config.plugins.serienRec.showAllButtons = ConfigYesNo(default = False)
	config.plugins.serienRec.DisplayRefreshRate = ConfigInteger(10, (1,60))

	config.plugins.serienRec.piconPath = ConfigText(default="/usr/share/enigma2/picon/", fixed_size=False, visible_width=80)
	
	#config.plugins.serienRec.fake_entry = NoSave(ConfigNothing())
	config.plugins.serienRec.BoxID = ConfigSelectionNumber(1, 16, 1, default = 1)
	config.plugins.serienRec.activateNewOnThisSTBOnly = ConfigYesNo(default = False)
	config.plugins.serienRec.setupType = ConfigSelection(choices = [("0", "einfach"), ("1", "Experte")], default = "1")
	config.plugins.serienRec.seriensubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdirnumerlength = ConfigInteger(1, (1,4))
	config.plugins.serienRec.seasonsubdirfillchar = ConfigSelection(choices = [("0","'0'"), ("<SPACE>", "<SPACE>")], default="0")
	config.plugins.serienRec.justplay = ConfigYesNo(default = False)
	config.plugins.serienRec.justremind = ConfigYesNo(default = False)
	config.plugins.serienRec.zapbeforerecord = ConfigYesNo(default = False)
	config.plugins.serienRec.afterEvent = ConfigSelection(choices = [("0", "nichts"), ("1", "in Standby gehen"), ("2", "in Deep-Standby gehen"), ("3", "automatisch")], default="3")
	config.plugins.serienRec.AutoBackup = ConfigSelection(choices = [("0", "nein"), ("before", "vor dem Suchlauf"), ("after", "nach dem Suchlauf")], default="before")
	config.plugins.serienRec.BackupPath = ConfigText(default = "/media/hdd/SR_Backup/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.deleteBackupFilesOlderThan = ConfigInteger(0, (0,999))
	config.plugins.serienRec.eventid = ConfigYesNo(default = True)
	config.plugins.serienRec.epgTimeSpan = ConfigInteger(10, (0, 30))
	# Remove EPGRefresh action for VU+ Boxes
	try:
		from Tools.HardwareInfoVu import HardwareInfoVu
		config.plugins.serienRec.autochecktype = ConfigSelection(choices = [("0", "Manuell"), ("1", "zur gewählten Uhrzeit")], default = "0")
	except:
		config.plugins.serienRec.autochecktype = ConfigSelection(choices = [("0", "Manuell"), ("1", "zur gewählten Uhrzeit"), ("2", "nach EPGRefresh")], default = "0")
	config.plugins.serienRec.readdatafromfiles = ConfigYesNo(default = False)
	config.plugins.serienRec.updateInterval = ConfigInteger(24, (0,24))
	config.plugins.serienRec.timeUpdate = ConfigYesNo(default = False)
	config.plugins.serienRec.deltime = ConfigClock(default = (random.randint(1, 23)*3600)+time.timezone)
	config.plugins.serienRec.maxDelayForAutocheck = ConfigInteger(15, (0,60))
	config.plugins.serienRec.maxWebRequests = ConfigInteger(1, (1,99))
	config.plugins.serienRec.tvplaner = ConfigYesNo(default = False)
	config.plugins.serienRec.imap_server = ConfigText(default = "", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_server_ssl = ConfigYesNo(default = True)
	config.plugins.serienRec.imap_server_port = ConfigInteger(993, (1,65535))
	config.plugins.serienRec.imap_login = ConfigText(default = "", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_login_hidden = ConfigText(default = "", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_password = ConfigText(default = "", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_password_hidden = ConfigText(default = "", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_mailbox = ConfigText(default = "INBOX", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_mail_subject = ConfigText(default = "TV Wunschliste TV-Planer", fixed_size=False, visible_width=80)
	config.plugins.serienRec.imap_mail_age = ConfigInteger(0, (0, 100))
	config.plugins.serienRec.imap_check_interval = ConfigInteger(30, (0, 10000))
	config.plugins.serienRec.tvplaner_create_marker = ConfigYesNo(default = True)
	config.plugins.serienRec.tvplaner_series = ConfigYesNo(default = True)
	config.plugins.serienRec.tvplaner_series_activeSTB = ConfigYesNo(default = False)
	config.plugins.serienRec.tvplaner_movies = ConfigYesNo(default = True)
	config.plugins.serienRec.tvplaner_movies_filepath = ConfigText(default = "/media/hdd/movie/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.tvplaner_movies_createsubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.tvplaner_movies_activeSTB = ConfigYesNo(default = False)
	config.plugins.serienRec.tvplaner_full_check = ConfigYesNo(default = False)
	config.plugins.serienRec.tvplaner_last_full_check = ConfigInteger(0)
	config.plugins.serienRec.tvplaner_skipSerienServer = ConfigYesNo(default = False)
	config.plugins.serienRec.checkfordays = ConfigInteger(1, (1,14))
	config.plugins.serienRec.globalFromTime = ConfigClock(default = 0+time.timezone)
	config.plugins.serienRec.globalToTime = ConfigClock(default = (((23*60)+59)*60)+time.timezone)
	config.plugins.serienRec.forceRecording = ConfigYesNo(default = False)
	config.plugins.serienRec.TimerForSpecials = ConfigYesNo(default = False)
	config.plugins.serienRec.TimeSpanForRegularTimer = ConfigInteger(7, (int(config.plugins.serienRec.checkfordays.value),999))
	config.plugins.serienRec.forceManualRecording = ConfigYesNo(default = False)
	config.plugins.serienRec.margin_before = ConfigInteger(default_before, (0,99))
	config.plugins.serienRec.margin_after = ConfigInteger(default_after, (0,99))
	config.plugins.serienRec.max_season = ConfigInteger(30, (1,999))
	config.plugins.serienRec.Autoupdate = ConfigYesNo(default = True)
	config.plugins.serienRec.wakeUpDSB = ConfigYesNo(default = False)
	config.plugins.serienRec.afterAutocheck = ConfigSelection(choices = [("0", "keine"), ("1", "in Standby gehen"), ("2", "in Deep-Standby gehen")], default = "0")
	config.plugins.serienRec.DSBTimeout = ConfigInteger(20, (0,999))
	config.plugins.serienRec.showNotification = ConfigSelection(choices = [("0", "keine"), ("1", "bei Suchlauf-Start"), ("2", "bei Suchlauf-Ende"), ("3", "bei Suchlauf-Start und Ende")], default = "1")
	config.plugins.serienRec.LogFilePath = ConfigText(default = serienRecMainPath, fixed_size=False, visible_width=80)
	config.plugins.serienRec.longLogFileName = ConfigYesNo(default = False)
	config.plugins.serienRec.deleteLogFilesOlderThan = ConfigInteger(14, (0,999))
	config.plugins.serienRec.writeLog = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogChannels = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogAllowedEpisodes = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogAdded = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogDisk = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimeRange = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimeLimit = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimerDebug = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogVersion = ConfigYesNo(default = True)
	config.plugins.serienRec.confirmOnDelete = ConfigYesNo(default = True)
	config.plugins.serienRec.deleteOlderThan = ConfigInteger(7, (1,99))
	config.plugins.serienRec.planerCacheEnabled = ConfigYesNo(default = True)
	config.plugins.serienRec.planerCacheSize = ConfigInteger((int(config.plugins.serienRec.checkfordays.value)), (1,4))
	config.plugins.serienRec.NoOfRecords = ConfigInteger(1, (1,9))
	config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default = True)
	config.plugins.serienRec.showPicons = ConfigYesNo(default = True)
	config.plugins.serienRec.listFontsize = ConfigSelectionNumber(-5, 35, 1, default = 0)
	config.plugins.serienRec.markerSort = ConfigSelection(choices=[("0", "Alphabetisch"), ("1", "Wunschliste")], default="0")
	config.plugins.serienRec.intensiveTimersuche = ConfigYesNo(default = True)
	config.plugins.serienRec.sucheAufnahme = ConfigYesNo(default = True)
	config.plugins.serienRec.selectNoOfTuners = ConfigYesNo(default = True)
	config.plugins.serienRec.tuner = ConfigInteger(4, (1,8))
	config.plugins.serienRec.seasonFilter = ConfigYesNo(default = False)
	config.plugins.serienRec.timerFilter = ConfigYesNo(default = False)
	config.plugins.serienRec.logScrollLast = ConfigYesNo(default = False)
	config.plugins.serienRec.logWrapAround = ConfigYesNo(default = False)
	config.plugins.serienRec.TimerName = ConfigSelection(choices = [("0", "<Serienname> - SnnEmm - <Episodentitel>"), ("1", "<Serienname>"), ("2", "SnnEmm - <Episodentitel>")], default="0")
	config.plugins.serienRec.refreshViews = ConfigYesNo(default = True)
	config.plugins.serienRec.openMarkerScreen = ConfigYesNo(default = True)
	config.plugins.serienRec.runAutocheckAtExit = ConfigYesNo(default = False)
	config.plugins.serienRec.downloadCover = ConfigYesNo(default = False)
	config.plugins.serienRec.showCover = ConfigYesNo(default = False)
	config.plugins.serienRec.createPlaceholderCover = ConfigYesNo(default = True)
	config.plugins.serienRec.showAdvice = ConfigYesNo(default = True)
	config.plugins.serienRec.showStartupInfoText = ConfigYesNo(default = True)

	config.plugins.serienRec.selectBouquets = ConfigYesNo(default = False)
	config.plugins.serienRec.bouquetList = ConfigText(default = "")
	choices = [(x.strip(),x.strip()) for x in config.plugins.serienRec.bouquetList.value.replace('"','').replace("'",'').replace('[','').replace(']','').split(',')]
	if len(choices) > 0:
		config.plugins.serienRec.MainBouquet = ConfigSelection(choices = choices, default = choices[0][0])
	else:
		config.plugins.serienRec.MainBouquet = ConfigSelection(choices = choices)
	if len(choices) > 1:
		config.plugins.serienRec.AlternativeBouquet = ConfigSelection(choices = choices, default = choices[1][0])
	else:
		config.plugins.serienRec.AlternativeBouquet = ConfigSelection(choices = choices)
	config.plugins.serienRec.useAlternativeChannel = ConfigYesNo(default = False)
	config.plugins.serienRec.splitEventTimer = ConfigSelection(choices = [("0", "nein"), ("1", "Timer anlegen"), ("2", "Einzelepisoden bevorzugen")], default = "0")

	config.plugins.serienRec.firstscreen = ConfigSelection(choices = [("0","SerienPlaner"), ("1", "SerienMarker")], default="0")
	
	# interne
	config.plugins.serienRec.version = NoSave(ConfigText(default="037"))
	config.plugins.serienRec.showversion = NoSave(ConfigText(default=SerienRecorderHelpers.SRVERSION))
	config.plugins.serienRec.screenplaner = ConfigInteger(1, (1,2))
	config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))
	config.plugins.serienRec.addedListSorted = ConfigYesNo(default = False)
	config.plugins.serienRec.wishListSorted = ConfigYesNo(default = False)
	config.plugins.serienRec.serienRecShowSeasonBegins_filter = ConfigYesNo(default = False)
	config.plugins.serienRec.dbversion = NoSave(ConfigText(default="3.8"))

	# Override settings for maxWebRequests, AutoCheckInterval and due to restrictions of Wunschliste.de
	config.plugins.serienRec.maxWebRequests.setValue(1)
	config.plugins.serienRec.maxWebRequests.save()
	if config.plugins.serienRec.autochecktype.value == "0":
		config.plugins.serienRec.updateInterval.setValue(0)
	else:
		if int(config.plugins.serienRec.updateInterval.value) != 0:
			config.plugins.serienRec.updateInterval.setValue(24)
	config.plugins.serienRec.updateInterval.save()
	if config.plugins.serienRec.planerCacheSize.value > 4:
		config.plugins.serienRec.planerCacheSize.value = 4
	config.plugins.serienRec.planerCacheSize.save()
	if config.plugins.serienRec.screenplaner.value > 2:
		config.plugins.serienRec.screenplaner.value = 1
	config.plugins.serienRec.screenplaner.save()

	if config.plugins.serienRec.showCover.value:
		config.plugins.serienRec.downloadCover.value = True
	config.plugins.serienRec.downloadCover.save()

	configfile.save()
	
	SelectSkin()
ReadConfigFile()

if config.plugins.serienRec.firstscreen.value == "0":
	showMainScreen = True
else:
	showMainScreen = False
	
if config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
	showAllButtons = False
else:
	showAllButtons = True	

#logFile = "%slog" % serienRecMainPath
SERIENRECORDER_LOGFILENAME = "%sSerienRecorder.log"
SERIENRECORDER_LONG_LOGFILENAME = "%sSerienRecorder_%s%s%s%s%s.log"
logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

#dbTmp = sqlite3.connect("%sSR_Tmp.db" % config.plugins.serienRec.databasePath.value)
#dbTmp = sqlite3.connect(":memory:")
#dbTmp.text_factory = lambda x: str(x.decode("utf-8"))
#dbSerRec = None
#dbSerRec = sqlite3.connect(serienRecDataBaseFilePath)
# dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))

autoCheckFinished = False
refreshTimer = None
refreshTimerConnection = None
coverToShow = None
runAutocheckAtExit = False
startTimer = None
startTimerConnection = None
transmissionFailed = False

dayCache = {}

# init EPGTranslator
if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/EPGTranslator/plugin.pyo"):
	from Plugins.Extensions.EPGTranslator.plugin import searchYouTube
	epgTranslatorInstalled = True
else:
	epgTranslatorInstalled = False

	
# check VPS availability
try:
	from Plugins.SystemPlugins.vps import Vps
except ImportError as ie:
	VPSPluginAvailable = False
else:
	VPSPluginAvailable = True


SR_OperatingManual = "http://einfall.github.io/serienrecorder/"

# init Opera Webbrowser
if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/HbbTV/browser.pyo"):
	from Plugins.Extensions.HbbTV.browser import Browser
	OperaBrowserInstalled = True
else:
	OperaBrowserInstalled = False

# init DMM Webbrowser
if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/Browser/Browser.pyo"):
	from Plugins.Extensions.Browser.Browser import Browser
	DMMBrowserInstalled = True
else:
	DMMBrowserInstalled = False
	
	
# init Wikipedia
if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/Wikipedia/plugin.pyo"):
	from Plugins.Extensions.Wikipedia.plugin import wikiSearch
	WikipediaInstalled = True
else:
	WikipediaInstalled = False


import keymapparser
try:
	keymapparser.removeKeymap("%skeymap.xml" % serienRecMainPath)
except:
	pass
try:
	keymapparser.readKeymap("%skeymap.xml" % serienRecMainPath)
except:
	pass
	
	
	
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
			writeLog("Fehler beim Abrufen von ' %s ', versuche es noch %d mal..." % (args[1], times - len(errorList)), True)
			run()
		# Fail
		else:
			writeLog("Abrufen von ' %s ' auch nach mehreren Versuchen nicht möglich!" % args[1], True)
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
				shutil.os.mkdir(config.plugins.serienRec.coverPath.value)
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
					downloadPage(posterURL, serien_nameCover).addCallback(showCover, self, serien_nameCover, False).addErrback(getCoverDataError, self, serien_nameCover)
				else:
					if config.plugins.serienRec.createPlaceholderCover.value:
						open(serien_nameCover, "a").close()
			except:
				if config.plugins.serienRec.createPlaceholderCover.value:
					open(serien_nameCover, "a").close()
				getCoverDataError("failed", self, serien_nameCover)
	except:
		writeLog("Fehler bei Laden des Covers: %s " % serien_nameCover, True)

def getCoverDataError(error, self, serien_nameCover):
	if self is not None and self.ErrorMsg: 
		writeLog("Fehler bei: %s (%s)" % (self.ErrorMsg, serien_nameCover), True)
		print "[SerienRecorder] Fehler bei: %s" % self.ErrorMsg
	else:
		ErrorMsg = "Cover-Suche (%s) auf 'Wunschliste.de' erfolglos" % serien_nameCover
		writeLog("Fehler: %s" % ErrorMsg, True)
		print "[SerienRecorder] Fehler: %s" % ErrorMsg
	writeLog("      %s" % str(error), True)
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
			print "Coverfile not found: %s" % serien_nameCover


def writeLog(text, forceWrite=False):
	global logFile
	if config.plugins.serienRec.writeLog.value or forceWrite:
		try:
			open(logFile, 'a').close()
		except (IOError, OSError) as e:
			logFile = SERIENRECORDER_LOGFILENAME % serienRecMainPath
			open(logFile, 'a').close()

		writeLogFile = open(logFile, 'a')
		writeLogFile.write('%s\n' % (text))
		writeLogFile.close()

def writeLogFilter(logtype, text, forceWrite=False):
	global logFile
	if config.plugins.serienRec.writeLog.value or forceWrite:
		try:
			open(logFile, 'a').close()
		except (IOError, OSError) as e:
			logFile = SERIENRECORDER_LOGFILENAME % serienRecMainPath
			open(logFile, 'a').close()

		writeLogFile = open(logFile, 'a')
		if (logtype is "channels" and config.plugins.serienRec.writeLogChannels.value) or \
		   (logtype is "allowedEpisodes" and config.plugins.serienRec.writeLogAllowedEpisodes.value) or \
		   (logtype is "added" and config.plugins.serienRec.writeLogAdded.value) or \
		   (logtype is "disk" and config.plugins.serienRec.writeLogDisk.value) or \
		   (logtype is "timeRange" and config.plugins.serienRec.writeLogTimeRange.value) or \
		   (logtype is "timeLimit" and config.plugins.serienRec.writeLogTimeLimit.value) or \
		   (logtype is "timerDebug" and config.plugins.serienRec.writeLogTimerDebug.value):
			# write log
			writeLogFile.write('%s\n' % text)
		
		writeLogFile.close()

def checkTuner(check_start, check_end, check_stbRef):
	if not config.plugins.serienRec.selectNoOfTuners.value:
		return True

	cRecords = 1
	lTuner = []
	lTimerStart = {}
	lTimerEnd = {}

	# Aufnahme Tuner braucht CI -1 -> nein, 1 - ja
	provider_ref = ServiceReference(check_stbRef)
	new_needs_ci_0 = checkCI(provider_ref.ref, 0)
	new_needs_ci_1 = checkCI(provider_ref.ref, 1)

	check_stbRef = check_stbRef.split(":")[4:7]

	timers = serienRecAddTimer.getTimersTime()
	for name, begin, end, service_ref in timers:
		#print name, begin, end, service_ref
		if not ((int(check_end) < int(begin)) or (int(check_start) > int(end))):
			#print "between"
			cRecords += 1

			# vorhandener Timer braucht CI -1 -> nein, 1 - ja
			# provider_ref = ServiceReference(service_ref)
			timer_needs_ci_0 = checkCI(service_ref.ref, 0)
			timer_needs_ci_1 = checkCI(service_ref.ref, 1)

			service_ref = str(service_ref).split(":")[4:7]
			#gleicher service
			if str(check_stbRef).lower() == str(service_ref).lower():
				if int(check_start) > int(begin): begin = check_start
				if int(check_end) < int(end): end = check_end
				lTimerStart.update({int(begin) : int(end)})
				lTimerEnd.update({int(end) : int(begin)})
			else:
				# vorhandener und neuer Timer benötigt ein CI
				if ((timer_needs_ci_0 is not -1) or (timer_needs_ci_1 is not -1)) and ((new_needs_ci_0 is not -1) or (new_needs_ci_1 is not -1)):
					return False
				# Anzahl der verwendeten Tuner um 1 erhöhen
				if not lTuner.count(service_ref):
					lTuner.append(service_ref)

	if int(check_start) in lTimerStart:
		l = lTimerStart.items()
		l.sort(key=lambda x: x[0])
		for each in l:
			if (each[0] <= lTimerStart[int(check_start)]) and (each[1] > lTimerStart[int(check_start)]):
				lTimerStart.update({int(check_start) : each[1]})

		if int(check_end) in lTimerEnd:
			l = lTimerEnd.items()
			l.sort(key=lambda x: x[0], reverse=True)
			for each in l:
				if (each[0] >= lTimerEnd[int(check_end)]) and (each[1] < lTimerEnd[int(check_end)]):
					lTimerEnd.update({int(check_end) : each[1]})

			if lTimerStart[int(check_start)] >= lTimerEnd[int(check_end)]:
				lTuner.append(check_stbRef)

	if lTuner.count(check_stbRef):
		return True
	else:
		return len(lTuner) < int(config.plugins.serienRec.tuner.value)

def checkFileAccess():
	# überprüfe ob logFile als Datei erzeigt werden kann
	global logFile
	logFileValid = True

	if not os.path.exists(config.plugins.serienRec.LogFilePath.value):
		try:
			os.makedirs(config.plugins.serienRec.LogFilePath.value)
		except:
			logFileValid = False

	if not logFileValid:
		try:
			open(logFile, 'a').close()
		except:
			logFileValid = False

	if not logFileValid:
		logFile = SERIENRECORDER_LOGFILENAME % serienRecMainPath
		Notifications.AddPopup("Log-Datei kann nicht im angegebenen Pfad (%s) erzeugt werden.\n\nEs wird '%s' verwendet!" % (config.plugins.serienRec.LogFilePath.value, logFile), MessageBox.TYPE_INFO, timeout=10, id="checkFileAccess")

def getDirname(database, serien_name, staffel):
	if config.plugins.serienRec.seasonsubdirfillchar.value == '<SPACE>':
		seasonsubdirfillchar = ' '
	else:
		seasonsubdirfillchar = config.plugins.serienRec.seasonsubdirfillchar.value
	# This is to let the user configure the name of the Sesaon subfolder
	# If a file called 'Staffel' exists in SerienRecorder folder the folder will be created as "Staffel" instead of "Season"
	germanSeasonNameConfig = "%sStaffel" % serienRecMainPath
	seasonDirName = "Season"
	if fileExists(germanSeasonNameConfig):
		seasonDirName = "Staffel"

	dirname = None
	seasonsubdir = -1
	isMovie = False
	row = database.getDirNames(serien_name)
	if not row:
		# It is a movie (because there is no marker)
		isMovie = True
	else:
		(dirname, seasonsubdir, url) = row
		if url.startswith('https://www.wunschliste.de/spielfilm'):
			isMovie = True

	if isMovie:
		path = config.plugins.serienRec.tvplaner_movies_filepath.value
		isCreateSerienSubDir = config.plugins.serienRec.tvplaner_movies_createsubdir.value
		isCreateSeasonSubDir = False
	else:
		path = config.plugins.serienRec.savetopath.value
		isCreateSerienSubDir = config.plugins.serienRec.seriensubdir.value
		isCreateSeasonSubDir = config.plugins.serienRec.seasonsubdir.value

	if dirname:
		if not re.search('.*?/\Z', dirname):
			dirname = "%s/" % dirname
		dirname_serie = dirname
		if (seasonsubdir == -1) and isCreateSeasonSubDir or (seasonsubdir == 1):
			dirname = "%s%s %s/" % (dirname, seasonDirName, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
	else:
		dirname = path
		dirname_serie = dirname
		if isCreateSerienSubDir:
			dirname = "%s%s/" % (dirname, "".join(i for i in serien_name if i not in "\/:*?<>|."))
			dirname_serie = dirname
			if isCreateSeasonSubDir:
				dirname = "%s%s %s/" % (dirname, seasonDirName, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))

	return dirname, dirname_serie

def CreateDirectory(serien_name, dirname, dirname_serie, cover_only = False):
	serien_name = doReplaces(serien_name)
	#dirname = doReplaces(dirname)
	#dirname_serie = doReplaces(dirname_serie)
	if not fileExists(dirname) and not cover_only:
		print "[SerienRecorder] Erstelle Verzeichnis %s" % dirname
		writeLog("Erstelle Verzeichnis: ' %s '" % dirname)
		try:
			os.makedirs(dirname)
		except OSError as e:
			writeLog("Fehler beim Erstellen des Verzeichnisses: %s" % e.strerror)
			#if e.errno != 17:
			#	raise

	# Copy cover only if path exists and series sub dir is activated
	if fileExists(dirname) and config.plugins.serienRec.seriensubdir.value:
		if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)) and not fileExists("%sfolder.jpg" % dirname_serie):
			shutil.copy("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name), "%sfolder.jpg" % dirname_serie)
		if config.plugins.serienRec.seasonsubdir.value:
			if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)) and not fileExists("%sfolder.jpg" % dirname):
				shutil.copy("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name), "%sfolder.jpg" % dirname)
	
def getEmailData():
	# extract all html parts
	def get_html(email_message_instance):
		maintype = email_message_instance.get_content_maintype()
		if maintype == 'multipart':
			for part in email_message_instance.get_payload():
				if part.get_content_type() == 'text/html':
					return part.get_payload()

	writeLog("\n---------' Lade TV-Planer E-Mail '---------------------------------------------------------------\n", True)
	
	# get emails
	if len(config.plugins.serienRec.imap_server.value) == 0:
		writeLog("TV-Planer: imap_server nicht gesetzt", True)
		return None
	
	if len(config.plugins.serienRec.imap_login_hidden.value) == 0:
		writeLog("TV-Planer: imap_login nicht gesetzt", True)
		return None
	
	if len(config.plugins.serienRec.imap_password_hidden.value) == 0:
		writeLog("TV-Planer: imap_password nicht gesetzt", True)
		return None
	
	if len(config.plugins.serienRec.imap_mailbox.value) == 0:
		writeLog("TV-Planer: imap_mailbox nicht gesetzt", True)
		return None
	
	if len(config.plugins.serienRec.imap_mail_subject.value)  == 0:
		writeLog("TV-Planer: imap_mail_subject nicht gesetzt", True)
		return None
	
	if 1 > config.plugins.serienRec.imap_mail_age.value > 100:
		config.plugins.serienRec.imap_mail_age.value = 1
	
	try:
		if config.plugins.serienRec.imap_server_ssl.value:
			mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)
		else:
			mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)
	
	except imaplib.IMAP4.abort:
		writeLog("TV-Planer: Verbindung zum Server fehlgeschlagen", True)
		return None
	
	except imaplib.IMAP4.error:
		writeLog("TV-Planer: Verbindung zum Server fehlgeschlagen", True)
		return None
	
	try:
		mail.login(SerienRecorderHelpers.decrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
				   SerienRecorderHelpers.decrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))
		print "[serienrecorder]: imap login ok"
	
	except imaplib.IMAP4.error:
		writeLog("TV-Planer: Anmeldung auf Server fehlgeschlagen", True)
		print "[serienrecorder]: imap login failed"
		return None

	try:
		mail.select(config.plugins.serienRec.imap_mailbox.value)
	
	except imaplib.IMAP4.error:
		writeLog("TV-Planer: Mailbox %r nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, True)
		return None
	
	searchstr = TimeHelpers.getMailSearchString()
	try:
		result, data = mail.uid('search', None, searchstr)
		if result != 'OK':
			writeLog("TV-Planer: Fehler bei der Suche nach TV-Planer E-Mails", True)
			writeLog("TV-Planer: %s" % data, True)
			return None

	except imaplib.IMAP4.error:
		writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen" % str(config.plugins.serienRec.imap_mail_age.value), True)
		writeLog("TV-Planer: %s" % searchstr, True)
		return None
	
	if len(data[0]) == 0:
		writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen" % str(config.plugins.serienRec.imap_mail_age.value), True)
		writeLog("TV-Planer: %s" % searchstr, True)
		return None
	
	# get the latest email
	latest_email_uid = data[0].split()[-1] 
	# fetch the email body (RFC822) for the given UID
	try:
		result, data = mail.uid('fetch', latest_email_uid, '(RFC822)')
	except:
		writeLog("TV-Planer: Laden der E-Mail fehlgeschlagen", True)
		return None
	
	mail.logout()
	# extract email message including headers and alternate payloads
	email_message = email.message_from_string(data[0][1])
	if len(email_message) == 0:
		writeLog("TV-Planer: leere E-Mail", True)
		return None
	
	# get html of wunschliste
	html = get_html(email_message)
	if html is None or len(html) == 0:
		writeLog("TV-Planer: leeres HTML", True)
		return None

	# class used for parsing TV-Planer html
	# States and Changes
	# ------------------
	# [error] || [finished] -> [state]
	# [start]: data && '.*TV-Planer.*?den (.*?)' -> <date> -> [time]
	# [time]: data && '\(ab (.*?) Uhr' -> <time> -> [transmission_table]
	# [time]: </div> -> 0:00 -> [transmission_table]
	# [transmission_table]: <table> -> [transmission]
	# [transmission]: <tr> -> [transmission_start]
	# [transmission]: </table> -> [finished]
	# [transmission_start]: >starttime< -> [transmission_url] | [error]
	# [transmission_url]: <a> -> url = href -> [transmission_serie]
	# [transmission_serie]: <strong> -> serie = ''
	# [transmission_serie]: serie += >serie<
	# [transmission_serie]: </strong> -> serie -> [transmission_serie_end]
	# [transmission_serie_end]: <span> -> title == 'Staffel' -> [transmission_season]
	# [transmission_serie_end]: <span> -> title == 'Episode' -> [transmission_episode]
	# [transmission_serie_end]: <span> -> title == 'xxx' -> [transmission_transmission_serie_end]
	# [transmission_serie_end]: <span> -> title != 'Staffel' and title != 'Episode' ->
	#                          save transmission, Staffel = Episode = '0' -> [transmission_title]
	# [transmission_title_end]: <span> -> title == 'Staffel' -> recover transmission, [transmission_season]
	# [transmission_title_end]: <span> -> title == 'Episode' -> recover transmission, [transmission_episode]
	# [transmission_title_end]: <span> -> title == 'xxx' -> -> recover transmission, [transmission_serie_end]
	# [transmission_season]: >season< -> [transmission_serie_end]
	# [transmission_episode]: >episode< -> [transmission_serie_end]
	# [transmission_title]: <span> -> title = ''
	# [transmission_title]: title += >title<
	# [transmission_title]: </span> -> [transmission_title_end]
	# [transmission_title_end]: </div> -> title -> [transmission_desc]
	# [transmission_desc]: <div> -> desc = ''
	# [transmission_desc]: >data< -> data == "bis ..." -> endtime = data -> [transmission_sender] | [error]
	# [transmission_desc]: >data< -> data == 'FREE-TV NEU' or data == 'NEU'
	# [transmission_desc]: desc += >desc<
	# [transmission_desc]: </div> -> desc -> [transmission_endtime]
	# [transmission_endtime]: >endtime< -> [transmission_sender] | [error]
	# [transmission_sender]: <img> sender = title -> [transmission_end]
	# [transmission_end]: </tr> -> [transmission]
	# 
	class TVPlaner_HTMLParser(HTMLParser):
		def __init__(self):
			HTMLParser.__init__(self)
			self.state = 'start'
			self.date = ()
			self.transmission = []
			self.transmission_save = []
			self.transmissions = []
			self.season = '0'
			self.episode = '00'
		def handle_starttag(self, tag, attrs):
			# print "Encountered a start tag:", tag, attrs
			if self.state == 'time' and tag == 'table':
				# no time - starting at 00:00 Uhr
				self.date = ( self.date, '00:00' )
				self.state = "transmission"
			elif self.state == 'transmission_table' and tag == 'table':
				self.state = 'transmission'
			elif self.state == 'transmission' and tag == 'tr':
				self.state = 'transmission_start'
			elif self.state == 'transmission_start' and tag == 'strong':
				# next day - reset
				self.state = 'transmission'
			elif self.state == 'transmission_url' and tag == 'a':
				url = ''
				for name, value in attrs:
					if name == 'href':
						url = value
						break
				self.transmission.append(url)
				self.state = 'transmission_serie'
			elif self.state == 'transmission_serie' and tag == 'strong':
				self.data = ''
			elif self.state == 'transmission_title' and tag == 'span':
				self.data = ''
			elif self.state == 'transmission_desc' and tag == 'div':
				self.data = ''
			elif self.state == 'transmission_serie_end' and tag == 'span' :
				found = False
				for name, value in attrs:
					if name == 'title' and value == 'Staffel':
						found = True
						self.state = 'transmission_season'
						break
					elif name == 'title' and value == 'Episode':
						found = True
						self.state = 'transmission_episode'
						break
					elif name == 'title':
						found = True
						break
				if not found:
					# do copy by creating new object for later recovery
					self.transmission_save = self.transmission + []
					self.transmission.append(self.season)
					self.transmission.append(self.episode)
					self.season = '0'
					self.episode = '00'
					self.state = 'transmission_title'
			elif self.state == 'transmission_title_end' and tag == 'span' :
				found = False
				for name, value in attrs:
					if name == 'title' and value == 'Staffel':
						found = True
						self.state = 'transmission_season'
						break
					elif name == 'title' and value == 'Episode':
						found = True
						self.state = 'transmission_episode'
						break
					elif name == 'title':
						found = True
						break
				if found:
					# do copy by creating new object for recovery
					self.transmission = self.transmission_save + []
					self.transmission_save = []
			elif self.state == 'transmission_sender' and tag == 'img':
				# match sender
				for name, value in attrs:
					if name == 'title':
						self.transmission.append(value)
						break
				self.state = 'transmission_end'
		
		def handle_endtag(self, tag):
			# print "Encountered an end tag :", tag
			if self.state == 'transmission_end' and tag == 'tr':
				print self.transmission
				self.transmissions.append(tuple(self.transmission))
				self.transmission = []
				self.state = 'transmission'
			elif self.state == 'transmission_serie' and tag == 'strong':
				# append collected data
				self.transmission.append(self.data)
				self.data = ''
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_title' and tag == 'span':
				# append collected data
				self.transmission.append(self.data)
				self.data = ''
				self.state = 'transmission_title_end'
			elif self.state == 'transmission_title_end' and tag == 'div':
				# consume closing div
				self.state = 'transmission_desc'
			elif self.state == 'transmission_desc' and tag == 'div':
				# append collected data
				self.transmission.append(self.data)
				self.data = ''
				self.state = 'transmission_endtime'
			elif self.state == 'transmission' and tag == 'table':
				# processing finished without error
				self.state = 'finished'

		def handle_data(self, data):
			# print "Encountered some data  : %r" % data
			if self.state == 'finished' or self.state == 'error':
				# do nothing
				self.state = self.state
			elif self.state == 'start':
				# match date
				# 'TV-Planer f=C3=BCr Donnerstag, den 22.12.2016'
				date_regexp=re.compile('.*TV-Planer.*?den ([0-3][0-9]\.[0-1][0-9]\.20[0-9][0-9])')
				result = date_regexp.findall(data)
				if result:
					self.date = result[0]
					self.state = 'time'
			elif self.state == 'time':
				# match time
				# '(ab 05:00 Uhr)'
				time_regexp=re.compile('ab (.*?) Uhr')
				result = time_regexp.findall(data)
				if result:
					self.date = ( self.date, result[0] )
					self.state = 'transmission_table'
			elif self.state == 'transmission_start':
				# match start time
				time_regexp=re.compile('(.*?) Uhr')
				time = time_regexp.findall(data)
				if len(time) > 0:
					self.transmission.append(time[0])
					self.state = 'transmission_url'
				else:
					self.state = 'error'
			elif self.state == 'transmission_serie':
				# match serie
				self.data += data
			elif self.state == 'transmission_season':
				# match season
				self.season = data
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_episode':
				# match episode
				self.episode = data
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_title':
				# match title
				self.data += data
			elif self.state == 'transmission_desc':
				# match description
				if data.startswith('bis:'):
					# may be empty description
					time_regexp=re.compile('bis: (.*?) Uhr.*')
					time = time_regexp.findall(data)
					if len(time) > 0:
						self.transmission.append('')
						self.transmission.append(time[0])
						self.state = 'transmission_sender'
					else:
						self.state = 'error'
				elif data != 'FREE-TV NEU' and data != "NEU":
					self.data += data
			elif self.state == 'transmission_endtime':
				# match end time
				time_regexp=re.compile('bis: (.*?) Uhr.*')
				time = time_regexp.findall(data)
				if len(time) > 0:
					self.transmission.append(time[0])
					self.state = 'transmission_sender'
				else:
					self.state = 'error'
			elif self.state == 'transmission_sender':
				# match sender
				self.transmission.append(data)
				self.state = 'transmission_end'
	
	# make one line and convert characters
	html = html.replace('=\r\n', '').replace('=\n','').replace('=\r', '').replace('\n', '').replace('\r', '')
	html = html.replace('=3D', '=')
	
	parser = TVPlaner_HTMLParser()
	html = parser.unescape(html).encode('utf-8')
	if html is None or len(html) == 0:
		writeLog("TV-Planer: leeres HTML nach HTMLParser", True)
		return None
	try:
		parser.feed(html)
#		print parser.date
#		print parser.transmissions
	except:
		writeLog("TV-Planer: HTML Parsing abgebrochen", True)
		return None
	
	if parser.state != "finished":
		writeLog("TV-Planer: HTML Parsing mit Fehler beendet", True)
		return None
		
	# prepare transmissions
	# [ ( seriesName, channel, start, end, season, episode, title, '0' ) ]
	# calculate start time and end time of list in E-Mail
	if len(parser.date) != 2:
		writeLog("TV-Planer: falsches Datumsformat", True)
		return None
	(day, month, year) = parser.date[0].split('.')
	(hour, minute) = parser.date[1].split(':')
	liststarttime_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
	# generate dictionary with final transmissions
	writeLog("Ab dem %s %s Uhr wurden die folgenden Sendungen gefunden:\n" % (parser.date[0], parser.date[1]))
	print "[SerienRecorder] Ab dem %s %s Uhr wurden die folgenden Sendungen gefunden:" % (parser.date[0], parser.date[1])
	transmissiondict = dict()
	for starttime, url, seriesname, season, episode, titel, description, endtime, channel in parser.transmissions:
		if url.startswith('https://www.wunschliste.de/spielfilm'):
			if not config.plugins.serienRec.tvplaner_movies.value:
				writeLog("' %s - Filmaufzeichnung ist deaktiviert '" % (seriesname), True)
				print "' %s - Filmaufzeichnung ist deaktiviert '" % (seriesname)
				continue
			type = '[ Film ]'
		elif url.startswith('https://www.wunschliste.de/serie'):
			if not config.plugins.serienRec.tvplaner_series.value:
				writeLog("' %s - Serienaufzeichnung ist deaktiviert '" % (seriesname), True)
				print "' %s - Serienaufzeichnung ist deaktiviert '" % (seriesname)
				continue
			type = '[ Serie ]'
		else:
			writeLog("' %s - Ungültige URL %r '" % (seriesname, url), True)
			print "' %s - Serienaufzeichnung ist deaktiviert '" % (seriesname)
			continue
		
		# series
		transmission = [ seriesname ]
		# channel
		channel = channel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').strip()
		transmission += [ channel ]
		# start time
		(hour, minute) = starttime.split(':')
		transmissionstart_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionstart_unix < liststarttime_unix:
			transmissionstart_unix = TimeHelpers.getRealUnixTimeWithDayOffset(minute, hour, day, month, year, 1)
		transmission += [ transmissionstart_unix ]
		# end time
		(hour, minute) = endtime.split('.')
		transmissionend_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionend_unix < transmissionstart_unix:
			transmissionend_unix = TimeHelpers.getRealUnixTimeWithDayOffset(minute, hour, day, month, year, 1)
		transmission += [ transmissionend_unix ]
		# season
		if season == '':
			season = '0'
		transmission += [ season ]
		# episode
		if episode == '':
			episode = '00'
		transmission += [ episode ]
		# title
		transmission += [ quopri.decodestring(titel) ]
		# last
		transmission += [ '0' ]
		# url
		transmission += [ url ]
		# store in dictionary transmissiondict[seriesname] = [ seriesname: [ transmission 0 ], [ transmission 1], .... ]
		if seriesname in transmissiondict:
			transmissiondict[seriesname] += [ transmission ]
		else:
			transmissiondict[seriesname] = [ transmission ]
		writeLog("' %s - S%sE%s - %s - %s - %s - %s - %s '" % (transmission[0], str(transmission[4]).zfill(2), str(transmission[5]).zfill(2), transmission[6], transmission[1], time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionstart_unix))), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionend_unix))), type), True)
		print "[SerienRecorder] ' %s - S%sE%s - %s - %s - %s - %s - %s'" % (transmission[0], str(transmission[4]).zfill(2), str(transmission[5]).zfill(2), transmission[6], transmission[1], time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionstart_unix))), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionend_unix))), type)
	
	if config.plugins.serienRec.tvplaner_create_marker.value:
		database = SRDatabase(serienRecDataBaseFilePath)
		for seriesname in transmissiondict.keys():
			# marker isn't in database, create new marker
			# url stored in marker isn't the final one, it is corrected later
			url = transmissiondict[seriesname][0][-1]
			try:
				boxID = None
				if url.startswith('https://www.wunschliste.de/serie'):
					seriesID = SeriesServer().getIDByFSID(url[str.rindex(url, '/') + 1:])
					if seriesID > 0:
						url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(seriesID)
					else:
						url = None
					if config.plugins.serienRec.tvplaner_series_activeSTB.value:
						boxID = config.plugins.serienRec.BoxID.value

				if url.startswith('https://www.wunschliste.de/spielfilm') and config.plugins.serienRec.tvplaner_movies_activeSTB.value:
					boxID = config.plugins.serienRec.BoxID.value

				if url and not database.markerExists(url):
					if database.addMarker(url, seriesname, boxID):
						writeLog("\nSerien Marker für ' %s ' wurde angelegt" % seriesname, True)
						print "[SerienRecorder] ' %s - Serien Marker erzeugt '" % seriesname
					else:
						writeLog("Serien Marker für ' %s ' konnte nicht angelegt werden" % seriesname, True)
						print "[SerienRecorder] ' %s - Serien Marker konnte nicht angelegt werden '" % seriesname
			except:
				writeLog("Serien Marker für ' %s ' konnte nicht angelegt werden" % seriesname, True)
				print "[SerienRecorder] ' %s - Serien Marker konnte nicht angelegt werden '" % seriesname

	return transmissiondict

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
		writeLog("Datenbankpfad nicht gefunden, auf Standardpfad zurückgesetzt!")
		print "Datenbankpfad nicht gefunden, auf Standardpfad zurückgesetzt!"
		Notifications.AddPopup(
			"SerienRecorder Datenbank wurde nicht gefunden.\nDer Standardpfad für die Datenbank wurde wiederhergestellt!",
			MessageBox.TYPE_INFO, timeout=10)
		serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

	try:
		database = SRDatabase(serienRecDataBaseFilePath)
		#dbSerRec = sqlite3.connect(serienRecDataBaseFilePath)
		#dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	except:
		writeLog("Fehler beim Initialisieren der Datenbank")
		print "Fehler beim Initialisieren der Datenbank"
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
				writeLog("Datenbankversion nicht kompatibel: SerienRecorder Version muss mindestens %s sein." % dbVersion)
				Notifications.AddPopup("Die SerienRecorder Datenbank ist mit dieser Version nicht kompatibel.\nAktualisieren Sie mindestens auf Version %s!" % dbVersion, MessageBox.TYPE_INFO, timeout=10)
				dbIncompatible = True
		else:
			dbIncompatible = True

		# Database incompatible - do cleanup
		if dbIncompatible:
			writeLog("Database is incompatible", True)
			database.close()
			return False

		if not dbVersionMatch:
			writeLog("Database ist zu alt - sie muss aktualisiert werden...", True)
			database.close()
			backupSerienRecDataBaseFilePath = "%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value
			writeLog("Erstelle Datenbank Backup - es kann nach erfolgreichem Update gelöscht werden: %s" % backupSerienRecDataBaseFilePath, True)
			shutil.copy(serienRecDataBaseFilePath, backupSerienRecDataBaseFilePath)
			database = SRDatabase(serienRecDataBaseFilePath)
			database.update(config.plugins.serienRec.dbversion.value)
			writeLog("Datenbank von Version %s auf Version %s aktualisiert" % (dbVersion, config.plugins.serienRec.dbversion.value), True)

	# Analyze database for query optimizer
	database.optimize()
	database.close()

	#dbSerRec.close()
	#dbSerRec = sqlite3.connect(serienRecDataBaseFilePath)
	#dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	return True

def writePlanerData(planerType):
	if not os.path.exists("%stmp/" % serienRecMainPath):
		try:
			os.makedirs("%stmp/" % serienRecMainPath)
		except:
			pass
	if os.path.isdir("%stmp/" % serienRecMainPath):
		try:
			os.chmod("%stmp/planer_%s" % (serienRecMainPath, str(planerType)), 0o666)
		except:
			pass

		f = open("%stmp/planer_%s" % (serienRecMainPath, str(planerType)), "wb")
		try:
			p = pickle.Pickler(f, 2)
			global dayCache
			p.dump(dayCache)
		except:
			pass
		f.close()

		try:
			os.chmod("%stmp/planer_%s" % (serienRecMainPath, str(planerType)), 0o666)
		except:
			pass

def loadPlanerData(planerType):
	global dayCache
	dayCache.clear()
	
	planerFile = "%stmp/planer_%s" % (serienRecMainPath, str(planerType))
	if fileExists(planerFile):
		f = open(planerFile, "rb")
		try:
			u = pickle.Unpickler(f)
			dayCache = u.load()
		except:
			pass
		f.close()

		try:
			heute = time.strptime(time.strftime('%d.%m.%Y', datetime.datetime.now().timetuple()), '%d.%m.%Y')
			l = []
			for key in dayCache:
				if time.strptime(key, '%d.%m.%Y') < heute: l.append(key)
			for key in l:
				del dayCache[key]
		except:
			pass

		if planerType == 1:
			optimizePlanerData()
		
def optimizePlanerData():
	if time.strftime('%H.%M', datetime.datetime.now().timetuple()) < '01.00':
		t_jetzt = datetime.datetime.now().timetuple()
	else:
		t_jetzt = (datetime.datetime.now() - datetime.timedelta(0,3600)).timetuple()
	jetzt = time.strftime('%H.%M', t_jetzt)
	heute = time.strftime('%d.%m.%Y', t_jetzt)
	global dayCache
	if heute in dayCache:
		try:
			for a in dayCache[heute][1]:
				l = []
				for b in a:
					if b[4] < jetzt: 
						l.append(b)
					else:
						break
				for b in l:		
					a.remove(b)
		except:
			pass

def testWebConnection():
	conn = httplib.HTTPConnection("www.google.com", timeout=WebTimeout)
	try:
		conn.request("GET", "/")
		data = conn.getresponse()
		#print "Status: %s   and reason: %s" % (data.status, data.reason)
		conn.close()
		return True
	except:
		conn.close()
	return False

def saveEnigmaSettingsToFile(path=serienRecMainPath):
	writeConfFile = open("%sConfig.backup" % path, "w")
	readSettings = open("/etc/enigma2/settings", "r")
	for rawData in readSettings.readlines():
		data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
		if data:
			writeConfFile.write(rawData)
	writeConfFile.close()
	readSettings.close()

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
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecAddSerie, seriesName)

	def handleSeriesSearchEnd(self, seriesName=None):
		if seriesName:
			self.session.open(serienRecMarker, seriesName)

#---------------------------------- Timer Functions ------------------------------------------
		
class serienRecAddTimer():

	@staticmethod
	def getTimersTime():

		recordHandler = NavigationInstance.instance.RecordTimer

		entry = None
		timers = []

		for timer in recordHandler.timer_list:
			timers.append((timer.name, timer.begin, timer.end, timer.service_ref))
		return timers

	@staticmethod
	def getTimersList():

		recordHandler = NavigationInstance.instance.RecordTimer

		timers = []
		serienRec_chlist = STBHelpers.buildSTBChannelList()

		for timer in recordHandler.timer_list:
			if timer and timer.service_ref and timer.eit is not None:

				location = 'NULL'
				recordedfile ='NULL' 
				if timer.dirname:
					location = timer.dirname
				channel = STBHelpers.getChannelByRef(serienRec_chlist,str(timer.service_ref))
				if channel:
					#recordedfile = getRecordFilename(timer.name,timer.description,timer.begin,channel)
					recordedfile = str(timer.begin) + " - " + str(timer.service_ref) + " - " + str(timer.name)
				timers.append({
					"title": timer.name,
					"description": timer.description,
					"id_channel": 'NULL',
					"channel": channel,
					"id_genre": 'NULL',
					"begin": timer.begin,
					"end": timer.end,
					"serviceref": timer.service_ref,
					"location": location,
					"recordedfile": recordedfile,
					"tags": timer.tags,
					"eit" : timer.eit
				})
		return timers		

	@staticmethod
	def removeTimerEntry(serien_name, start_time, eit=0):

		recordHandler = NavigationInstance.instance.RecordTimer
		removed = False
		print "[SerienRecorder] try to remove enigma2 Timer:", serien_name, start_time
		
		# entferne aktivierte Timer	
		for timer in recordHandler.timer_list:
			if timer and timer.service_ref:
				if eit > 0:
					if timer.eit == eit:
						recordHandler.removeEntry(timer)
						removed = True
						break
				if str(timer.name) == serien_name and int(timer.begin) == int(start_time):
					#if str(timer.service_ref) == entry_dict['channelref']:
					recordHandler.removeEntry(timer)
					removed = True
		
		# entferne deaktivierte Timer	
		if not removed:
			for timer in recordHandler.processed_timers:
				if timer and timer.service_ref:
					if eit > 0:
						if timer.eit == eit:
							recordHandler.removeEntry(timer)
							removed = True
							break
					if str(timer.name) == serien_name and int(timer.begin) == int(start_time):
						#if str(timer.service_ref) == entry_dict['channelref']:
						recordHandler.removeEntry(timer)
						removed = True
		
		return removed

	@staticmethod
	def addTimer(serviceref, begin, end, name, description, eit, disabled, dirname, vpsSettings, tags, logentries=None):

		recordHandler = NavigationInstance.instance.RecordTimer
		#config.plugins.serienRec.seriensubdir
		#if not dirname:
		#	try:
		#		dirname = config.plugins.serienRec.savetopath.value
		#	except Exception:
		#		dirname = preferredTimerPath()
		try:
			try:
				timer = RecordTimerEntry(
					ServiceReference(serviceref),
					begin,
					end,
					name,
					description,
					eit,
					disabled = disabled,
					justplay = config.plugins.serienRec.justplay.value,
					zapbeforerecord = config.plugins.serienRec.zapbeforerecord.value,
					justremind = config.plugins.serienRec.justremind.value,
					afterEvent = int(config.plugins.serienRec.afterEvent.value),
					dirname = dirname)
			except Exception:
				sys.exc_clear()

				timer = RecordTimerEntry(
					ServiceReference(serviceref),
					begin,
					end,
					name,
					description,
					eit,
					disabled,
					config.plugins.serienRec.justplay.value | config.plugins.serienRec.justremind.value,
					afterEvent = int(config.plugins.serienRec.afterEvent.value),
					dirname = dirname,
					tags = None)

			timer.repeated = 0

			# Add tags
			timerTags = timer.tags[:]
			timerTags.append('SerienRecorder')
			if len(tags) != 0:
				timerTags.extend(tags)
			timer.tags = timerTags

			# If eit = 0 the VPS plugin won't work properly for this timer, so we have to disable VPS in this case.
			if VPSPluginAvailable and eit is not 0:
				timer.vpsplugin_enabled = vpsSettings[0]
				timer.vpsplugin_overwrite = timer.vpsplugin_enabled and (not vpsSettings[1])

			if logentries:
				timer.log_entries = logentries

			timer.log(0, "[SerienRecorder] Timer created")

			conflicts = recordHandler.record(timer)
			if conflicts:
				errors = []
				for conflict in conflicts:
					errors.append(conflict.name)

				return {
					"result": False,
					"message": "Conflicting Timer(s) detected! %s" % " / ".join(errors)
				}
		except Exception, e:
			print "[%s] <%s>" %(__name__, e)
			return {
				"result": False,
				"message": "Could not add timer '%s'!" % e
			}

		print "[SerienRecorder] Versuche Timer anzulegen:", name, dirname
		writeLogFilter("timerDebug", "Versuche Timer anzulegen: ' %s - %s '" % (name, dirname))
		return {
			"result": True,
			"message": "Timer '%s' added" % name,
			"eit" : eit
		}

import os, re, threading, Queue

class downloadSearchResults(threading.Thread):
	def __init__ (self, seriesName, startOffset):
		threading.Thread.__init__(self)
		self.seriesName = seriesName
		self.startOffset = startOffset
		self.searchResults = None
	def run(self):
		self.searchResults = SeriesServer().doSearch(self.seriesName, self.startOffset)

	def getData(self):
		return self.searchResults

class downloadPlanerData(threading.Thread):
	def __init__ (self, daypage, webChannels):
		threading.Thread.__init__(self)
		self.daypage = daypage
		self.webChannels = webChannels
		self.planerData = None
	def run(self):
		try:
			self.planerData = SeriesServer().doGetPlanerData(self.daypage, self.webChannels)
		except:
			writeLog("Fehler beim Abrufen und Verarbeiten der SerienPlaner-Daten [%s]\n" % str(self.daypage), True)

	def getData(self):
		return self.daypage, self.planerData

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
			transmissionFailed = False
			transmissions = SeriesServer().doGetTransmissions(seriesID, timeSpan, markerChannels)
		except:
			transmissionFailed = True
			transmissions = None
		self.resultQueue.put((transmissionFailed, transmissions, seriesTitle, season, fromEpisode, numberOfRecords, currentTime, futureTime, excludedWeekdays))

class serienRecCheckForRecording():

	instance = None
	epgrefresh_instance = None

	def __init__(self, session, manuell, tvplaner_manuell=False):
		self.enableDirectoryCreation = False
		assert not serienRecCheckForRecording.instance, "Go is a singleton class!"
		serienRecCheckForRecording.instance = self
		self.session = session
		self.database = None
		#self.database = SRDatabase(serienRecDataBaseFilePath)
		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell
		print "1__init__ tvplaner_manuell: ", tvplaner_manuell
		self.newSeriesOrEpisodesFound = False
		self.color_print = "\033[93m"
		self.color_end = "\33[0m"
		self.senderListe = {}
		self.markers = []
		self.MessageList = []
		self.speedStartTime = 0
		self.speedEndTime = 0
		self.konflikt = ""
		self.count_url = 0
		self.countTimer = 0
		self.countTimerUpdate = 0
		self.countNotActiveTimer = 0
		self.countTimerFromWishlist = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.NoOfRecords = int(config.plugins.serienRec.NoOfRecords.value)

		global logFile
		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
		checkFileAccess()

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		writeLog("\n---------' %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
		self.daypage = 0

		global refreshTimer
		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

		global refreshTimerConnection
		if refreshTimerConnection:
			refreshTimerConnection = None

		self.tempDB = None
		#self.tempDB = SRTempDatabase()
		#self.tempDB.initialize()

		if config.plugins.serienRec.autochecktype.value == "0":
			writeLog("Auto-Check ist deaktiviert - nur manuelle Timersuche", True)
		elif config.plugins.serienRec.autochecktype.value == "1":
			writeLog("Auto-Check ist aktiviert - er wird zur gewählten Uhrzeit gestartet", True)
		elif config.plugins.serienRec.autochecktype.value == "2":
			writeLog("Auto-Check ist aktiviert - er wird nach dem EPGRefresh ausgeführt", True)

		if not self.manuell and config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value)*60)) * 1000, True)
			print "%s[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet.%s" % (self.color_print, self.color_end)
			print "%s[SerienRecorder] Verbleibende Zeit: %s Stunden%s" % (self.color_print, TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), self.color_end)
			writeLog("Verbleibende Zeit bis zum nächsten Auto-Check: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if self.manuell:
			print "[SerienRecorder] checkRecTimer manuell."
			global runAutocheckAtExit
			runAutocheckAtExit = False
			self.startCheck(True, self.tvplaner_manuell)
		else:
			try:
				from Plugins.Extensions.EPGRefresh.EPGRefresh import epgrefresh
				self.epgrefresh_instance = epgrefresh
				config.plugins.serienRec.autochecktype.addNotifier(self.setEPGRefreshCallback)
			except Exception as e:
				writeLog("EPGRefresh plugin nicht installiert! " + str(e), True)

	@staticmethod
	def createBackup():
		global logFile

		lt = time.localtime()
		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value

		# Remove old backups
		if config.plugins.serienRec.deleteBackupFilesOlderThan.value > 0:
			writeLog("\nEntferne alte Backup-Dateien und erzeuge neues Backup.", True)
			now = time.time()
			logFolderPattern = re.compile('\d{4}\d{2}\d{2}\d{2}\d{2}')
			for root, dirs, files in os.walk(config.plugins.serienRec.BackupPath.value, topdown=False):
				for name in dirs:
					if logFolderPattern.match(name) and os.stat(os.path.join(root, name)).st_ctime < (now - config.plugins.serienRec.deleteBackupFilesOlderThan.value * 24 * 60 * 60):
						shutil.rmtree(os.path.join(root, name), True)
						writeLog("Lösche Ordner: %s" % os.path.join(root, name), True)
		else:
			writeLog("Erzeuge neues Backup", True)

		BackupPath = "%s%s%s%s%s%s/" % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
		if not os.path.exists(BackupPath):
			try:
				os.makedirs(BackupPath)
			except:
				pass
		if os.path.isdir(BackupPath):
			if fileExists(serienRecDataBaseFilePath):
				database = SRDatabase(serienRecDataBaseFilePath)
				database.backup(BackupPath)
			if fileExists(logFile):
				shutil.copy(logFile, BackupPath)
			if fileExists("/etc/enigma2/timers.xml"):
				shutil.copy("/etc/enigma2/timers.xml", BackupPath)
			if fileExists("%sConfig.backup" % serienRecMainPath):
				shutil.copy("%sConfig.backup" % serienRecMainPath, BackupPath)
			saveEnigmaSettingsToFile(BackupPath)
			for filename in os.listdir(BackupPath):
				os.chmod(os.path.join(BackupPath, filename), 0o777)

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
				writeLog("Um die EPGRefresh Optionen nutzen zu können, muss mindestens die EPGRefresh Version 2.1.1 installiert sein. " + str(e), True)



	@staticmethod
	def getNextAutoCheckTimer(lt):
		acttime = (lt.tm_hour * 60 + lt.tm_min)
		deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
		if acttime < deltime:
			deltatime = deltime - acttime
		else:
			deltatime = abs(1440 - acttime + deltime)
		return deltatime

	def startCheck(self, manuell=False, tvplaner_manuell=False):
		self.database = SRDatabase(serienRecDataBaseFilePath)
		self.tempDB = SRTempDatabase()
		self.tempDB.initialize()

		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell
		print "%s[SerienRecorder] settings:%s" % (self.color_print, self.color_end)
		print "manuell:", manuell
		print "tvplaner_manuell:", tvplaner_manuell
		print "uhrzeit check:", config.plugins.serienRec.timeUpdate.value

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		global refreshTimer
		global refreshTimerConnection
		global logFile

		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
		checkFileAccess()

		logFileSave = SERIENRECORDER_LONG_LOGFILENAME % (config.plugins.serienRec.LogFilePath.value, str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))

		writeLog("\n---------' %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)

		if not self.manuell and not initDB():
			self.askForDSB()
			return

		if not self.database.hasMarkers() and not config.plugins.serienRec.tvplaner and not config.plugins.serienRec.tvplaner_create_marker:
			writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle SerienMarker leer."
			writeLog("Es sind keine Serien-Marker vorhanden - Auto-Check kann nicht ausgeführt werden.", True)
			writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			self.askForDSB()
			return

		if not self.database.hasChannels():
			writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle Channels leer."
			writeLog("Es wurden keine Sender zugeordnet - Auto-Check kann nicht ausgeführt werden.", True)
			writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			self.askForDSB()
			return

		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

			if refreshTimerConnection:
				refreshTimerConnection = None

			print "%s[SerienRecorder] Auto-Check Timer stop.%s" % (self.color_print, self.color_end)
			writeLog("Auto-Check stop.", True)

		if config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamOS():
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value)*60)) * 1000, True)

			print "%s[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet.%s" % (self.color_print, self.color_end)
			print "%s[SerienRecorder] Verbleibende Zeit: %s Stunden%s" % (self.color_print, TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), self.color_end)
			writeLog("Auto-Check Uhrzeit-Timer gestartet.", True)
			writeLog("Verbleibende Zeit: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if config.plugins.serienRec.AutoBackup.value == "before":
			self.createBackup()
				
		if not config.plugins.serienRec.longLogFileName.value:
			# logFile leeren (renamed to .old)
			if fileExists(logFile):
				shutil.move(logFile,"%s.old" % logFile)
		else:
			lt = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteLogFilesOlderThan.value)
			for filename in os.listdir(config.plugins.serienRec.LogFilePath.value):
				if (filename.find('SerienRecorder_') == 0) and (int(os.path.getmtime(os.path.join(config.plugins.serienRec.LogFilePath.value, filename))) < int(lt.strftime("%s"))):
					try:
						os.remove('%s%s' % (config.plugins.serienRec.LogFilePath.value, filename))
					except:
						writeLog("Logdatei konnte nicht gelöscht werden: %s" % os.path.join(config.plugins.serienRec.LogFilePath.value, filename), True)
					
		open(logFile, 'w').close()

		self.database.removeExpiredTimerConflicts()

		if self.tvplaner_manuell and config.plugins.serienRec.tvplaner.value:
			print "\n---------' Starte Check um %s (TV-Planer manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Check um %s (TV-Planer manuell) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		elif self.manuell:
			print "\n---------' Starte Check um %s (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Check um %s (manuell) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		elif config.plugins.serienRec.tvplaner.value:
			print "\n---------' Starte Auto-Check um %s (TV-Planer auto) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Auto-Check um %s (TV-Planer auto) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		else:
			print "\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
			if config.plugins.serienRec.showNotification.value in ("1", "3"):
				Notifications.AddPopup("SerienRecorder Suchlauf nach neuen Timern wurde gestartet.", MessageBox.TYPE_INFO, timeout=3, id="Suchlauf wurde gestartet")

		if config.plugins.serienRec.writeLogVersion.value:
			writeLog("STB Type: %s\nImage: %s" % (STBHelpers.getSTBType(), STBHelpers.getImageVersionString()), True)
		writeLog("SR Version: %s\nDatenbank Version: %s" % (config.plugins.serienRec.showversion.value, str(self.database.getVersion())), True)
		writeLog("Skin Auflösung: %s x %s" % (str(getDesktop(0).size().width()), str(getDesktop(0).size().height())), True)

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
		writeLog(sMsg, True)

		self.markers = []
		self.MessageList = []
		self.speedStartTime = time.clock()

		# teste Verbindung ins Internet
		if not testWebConnection():
			writeLog("\nKeine Verbindung ins Internet. Check wurde abgebrochen!!\n", True)

			# Statistik
			self.speedEndTime = time.clock()
			speedTime = (self.speedEndTime - self.speedStartTime)
			writeLog("---------' Auto-Check beendet ( Ausführungsdauer: %3.2f Sek.)'-------------------------------------------------------------------------" % speedTime, True)
			print "---------' Auto-Check beendet ( Ausführungsdauer: %3.2f Sek.)'----------------------------------------------------------------------------" % speedTime

			if config.plugins.serienRec.longLogFileName.value:
				shutil.copy(logFile, logFileSave)

			global autoCheckFinished
			autoCheckFinished = True

			if config.plugins.serienRec.AutoBackup.value == "after":
				self.createBackup()

			# in den deep-standby fahren.
			self.askForDSB()
			return

		# Versuche Verzeichnisse zu erreichen
		try:
			writeLog("\nPrüfe konfigurierte Aufnahmeverzeichnisse:", True)
			recordDirectories = self.database.getRecordDirectories(config.plugins.serienRec.savetopath.value)
			for directory in recordDirectories:
				writeLog("   %s" % directory, True)
				os.path.exists(directory)
		except:
			writeLog("Es konnten nicht alle Aufnahmeverzeichnisse gefunden werden", True)

		# suche nach neuen Serien, Covern und Planer-Cache
		if (not self.manuell) and (config.plugins.serienRec.firstscreen.value == "0") and config.plugins.serienRec.planerCacheEnabled.value:
			self.startCheck2()
		else:
			self.startCheck3()

	def startCheck2(self):
		webChannels = self.database.getActiveChannels()
		writeLog("\nLaden der SerienPlaner-Daten gestartet ...", True)

		markers = self.database.getAllMarkers(config.plugins.serienRec.BoxID.value)
		downloadPlanerDataResults = []
		for daypage in range(int(config.plugins.serienRec.planerCacheSize.value)):
			#planerData = SeriesServer().doGetPlanerData(int(daypage), webChannels)
			planerData = downloadPlanerData(int(daypage), webChannels)
			downloadPlanerDataResults.append(planerData)
			planerData.start()

		try:
			for planerDataThread in downloadPlanerDataResults:
				planerDataThread.join()
				if not planerDataThread.getData():
					continue

				(daypage, planerData) = planerDataThread.getData()
				self.processPlanerData(planerData, markers, daypage)

			self.postProcessPlanerData()
		except:
			writeLog("Fehler beim Abrufen oder Verarbeiten der SerienPlaner-Daten")
		writeLog("... Laden der SerienPlaner-Daten beendet\n", True)

		self.startCheck3()

	def processPlanerData(self, data, markers, daypage):
		if not data or len(data) == 0:
			pass
		daylist = [[]]

		headDate = [data["date"]]
		timers = []
		#txt = headDate[0].split(",")
		#(day, month, year) = txt[1].split(".")
		#UTCDatum = TimeHelpers.getRealUnixTime(0, 0, day, month, year)

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			timers = self.database.getTimer(daypage)

		for event in data["events"]:
			aufnahme = False
			serieAdded = 0
			start_h = event["time"][:+2]
			start_m = event["time"][+3:]
			start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, daypage)

			serien_name = event["name"].encode("utf-8")
			serien_name_lower = serien_name.lower()
			sender = event["channel"]
			title = event["title"].encode("utf-8")
			staffel = event["season"]
			episode = event["episode"]
			serien_id = event["id"]

			if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
				serienTimers = [timer for timer in timers if timer[0] == serien_name_lower]
				serienTimersOnChannel = [serienTimer for serienTimer in serienTimers if serienTimer[2] == sender.lower()]
				for serienTimerOnChannel in serienTimersOnChannel:
					if (int(serienTimerOnChannel[1]) >= (int(start_time) - 300)) and (int(serienTimerOnChannel[1]) < (int(start_time) + 300)):
						aufnahme = True

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				if serien_name_lower in markers:
					serieAdded = 1 if markers[serien_name_lower] else 2

				staffel = str(staffel).zfill(2)
				episode = str(episode).zfill(2)

				##############################
				#
				# CHECK
				#
				# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
				#
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False, title) > 0 and True or False
						else:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False) > 0 and True or False
					else:
						bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False) > 0 and True or False

				title = "%s - %s" % (seasonEpisodeString, title)
				regional = False
				paytv = False
				neu = event["new"]
				prime = False
				transmissionTime = event["time"]
				url = ''
				daylist[0].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value and headDate:
			d = headDate[0].split(',')
			d.reverse()
			key = d[0].strip()
			global dayCache
			dayCache.update({key:(headDate, daylist)})

	def postProcessPlanerData(self):
		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			writePlanerData(1)

	def adjustEPGtimes(self, current_time):

		writeLog("\n---------' Aktualisiere Timer '-------------------------------------------------------------------------------\n", True)

		##############################
		#
		# try to get eventID (eit) from epgCache
		#
		if config.plugins.serienRec.eventid.value:
			recordHandler = NavigationInstance.instance.RecordTimer
			#writeLog("<< Suche im EPG anhand der Uhrzeit", True)
			timers = self.database.getAllTimer(current_time)
			for timer in timers:
				(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit, active) = timer

				title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)

				new_serien_title = serien_title
				new_serien_time = 0
				transmission = None
				if str(episode).isdigit():
					if int(episode) != 0:
						transmission = self.tempDB.getTransmissionForTimerUpdate(serien_name, staffel, episode)
				else:
					transmission = self.tempDB.getTransmissionForTimerUpdate(serien_name, staffel, episode)
				if transmission:
					(new_serien_name, new_staffel, new_episode, new_serien_title, new_serien_time) = transmission
				#new_title = "%s - S%sE%s - %s" % (new_serien_name, str(new_staffel).zfill(2), str(new_episode).zfill(2), new_serien_title)

				(margin_before, margin_after) = self.database.getMargins(serien_name, webChannel, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)

				# event_matches = STBHelpers.getEPGEvent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = STBHelpers.getEPGEvent(['RITBDSE',(stbRef, 0, int(serien_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(serien_time)+(int(margin_before) * 60))
				new_event_matches = None
				if new_serien_time != 0 and eit > 0:
					new_event_matches = STBHelpers.getEPGEvent(['RITBDSE',(stbRef, 0, int(new_serien_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(new_serien_time)+(int(margin_before) * 60))
				if new_event_matches and len(new_event_matches) > 0 and (not event_matches or (event_matches and len(event_matches) == 0)):
					# Old event not found but new one with different start time
					event_matches = new_event_matches
				#else:
				# Wenn die Sendung zur ursprünglichen Startzeit im EPG gefunden wurde
				#new_serien_time = serien_time

				(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						eit = int(event_entry[1])
						start_unixtime = int(event_entry[3]) - (int(margin_before) * 60)
						end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)

						print "[SerienRecorder] try to modify enigma2 Timer:", title, serien_time

						if (str(staffel) is 'S' or str(staffel) is '0') and (str(episode) is '0' or str(episode) is '00'):
							writeLog("' %s - %s '" % (title, dirname), True)
							writeLog("   Timer kann nicht aktualisiert werden @ %s" % webChannel, True)
							break

						try:
							# suche in aktivierten Timern
							timerUpdated = self.updateTimer(recordHandler.timer_list + recordHandler.processed_timers, eit, end_unixtime, episode,
															new_serien_title, serien_name, serien_time,
															staffel, start_unixtime, stbRef, title,
															dirname)

						# if not timerUpdated:
						# 	# suche in deaktivierten Timern
						# 	self.updateTimer(recordHandler.processed_timers, eit, end_unixtime, episode,
						#                               new_serien_title, serien_name, serien_time,
						#                               staffel, start_unixtime, stbRef, title,
						#                               dirname)

						except Exception:
							print "[SerienRecorder] Modifying enigma2 Timer failed:", title, serien_time
							writeLog("' %s - %s '" % (title, dirname), True)
							writeLog("   Timeraktualisierung fehlgeschlagen @ %s" % webChannel, True)
						break
				else:
					writeLog("' %s - %s '" % (title, dirname), True)
					writeLog("   Sendung konnte nicht im EPG gefunden werden @ %s" % webChannel)

	def updateTimer(self, timer_list, eit, end_unixtime, episode, new_serien_title, serien_name, serien_time, staffel, start_unixtime, stbRef, title, dirname):
		timerUpdated = False
		timerFound = False
		for timer in timer_list:
			if timer and timer.service_ref:
				# skip all timer with false service ref
				if (str(timer.service_ref).lower() == str(stbRef).lower()) and (str(timer.begin) == str(serien_time)):
					# Timer gefunden, weil auf dem richtigen Sender und Startzeit im Timer entspricht Startzeit in SR DB
					timerFound = True
					# Muss der Timer aktualisiert werden?

					# Event ID
					updateEIT = False
					old_eit = timer.eit
					if timer.eit != int(eit):
						timer.eit = eit
						updateEIT = True

					# Startzeit
					updateStartTime = False
					if timer.begin != start_unixtime and abs(start_unixtime - timer.begin) > 30:
						timer.begin = start_unixtime
						timer.end = end_unixtime
						NavigationInstance.instance.RecordTimer.timeChanged(timer)
						updateStartTime = True

					# Timername
					updateName = False
					old_timername = timer.name
					if config.plugins.serienRec.TimerName.value == "0":
						timer_name = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), new_serien_title)
					elif config.plugins.serienRec.TimerName.value == "2":
						timer_name = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), new_serien_title)
					else:
						timer_name = serien_name

					if timer.name != timer_name:
						timer.name = timer_name
						updateName = True

					# Timerbeschreibung
					updateDescription = False
					old_timerdescription = timer.description
					timer_description = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), new_serien_title)

					if timer.description != timer_description:
						timer.description = timer_description
						updateDescription = True

					# Directory
					updateDirectory = False
					old_dirname = timer.dirname
					if timer.dirname != dirname:
						(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
						CreateDirectory(serien_name, dirname, dirname_serie)
						timer.dirname = dirname
						updateDirectory = True

					if updateEIT or updateStartTime or updateName or updateDescription or updateDirectory:
						writeLog("' %s - %s '" % (title, dirname), True)
						new_start = time.strftime("%d.%m. - %H:%M", time.localtime(int(start_unixtime)))
						old_start = time.strftime("%d.%m. - %H:%M", time.localtime(int(serien_time)))
						if updateStartTime:
							writeLog("   Startzeit wurde aktualisiert von %s auf %s" % (old_start, new_start), True)
							timer.log(0, "[SerienRecorder] Changed timer start from %s to %s" % (old_start, new_start))
						if updateEIT:
							writeLog("   Event ID wurde aktualisiert von %s auf %s" % (str(old_eit), str(eit)), True)
							timer.log(0, "[SerienRecorder] Changed event ID from %s to %s" % (str(old_eit), str(eit)))
						if updateName:
							writeLog("   Name wurde aktualisiert von %s auf %s" % (old_timername, timer_name), True)
							timer.log(0, "[SerienRecorder] Changed name from %s to %s" % (old_timername, timer_name))
						if updateDescription:
							writeLog("   Beschreibung wurde aktualisiert von %s auf %s" % (old_timerdescription, timer_description), True)
							timer.log(0, "[SerienRecorder] Changed description from %s to %s" % (old_timerdescription, timer_description))
						if updateDirectory:
							writeLog("   Verzeichnis wurde aktualisiert von %s auf %s" % (old_dirname, dirname), True)
							timer.log(0, "[SerienRecorder] Changed directory from %s to %s" % (old_dirname, dirname))
						self.countTimerUpdate += 1
						NavigationInstance.instance.RecordTimer.saveTimer()
						self.database.updateTimerStartTime(start_unixtime, eit, new_serien_title, serien_time, stbRef)
						timerUpdated = True
					else:
						# writeLog("' %s - %s '" % (title, dirname), True)
						# writeLog("   Timer muss nicht aktualisiert werden", True)
						timerUpdated = True
					break

		# Timer not found - maybe removed from image timer list
		if not timerFound:
			writeLog("' %s - %s '" % (title, dirname), True)
			writeLog("   Timer konnte nicht gefunden werden!", True)

		return timerUpdated

	def activateTimer(self):
		# versuche deaktivierte Timer zu aktivieren oder auf anderer Box zu erstellen
		deactivatedTimers = self.database.getDeactivatedTimers()
		for deactivatedTimer in deactivatedTimers:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = deactivatedTimer
			if eit > 0:
				recordHandler = NavigationInstance.instance.RecordTimer
				(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
				try:
					timerFound = False
					# suche in deaktivierten Timern
					for timer in recordHandler.processed_timers:
						if timer and timer.service_ref:
							if (timer.begin == serien_time) and (timer.eit == eit) and (str(timer.service_ref).lower() == stbRef.lower()):
								# versuche deaktivierten Timer zu aktivieren
								label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								if config.plugins.serienRec.TimerName.value == "0":
									timer_name = label_serie
								elif config.plugins.serienRec.TimerName.value == "2":
									timer_name = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								else:
									timer_name = serien_name
								writeLog("Versuche deaktivierten Timer zu aktivieren: ' %s - %s '" % (serien_title, dirname))
								
								if checkTuner(str(timer.begin), str(timer.end), str(timer.service_ref)):
									timer.disabled = False
									timersanitycheck = TimerSanityCheck(recordHandler.timer_list, timer)
									if timersanitycheck.check(): 
										self.countTimerUpdate += 1
										NavigationInstance.instance.RecordTimer.timeChanged(timer)

										# Eintrag in das timer file
										self.database.activateTimer(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit)
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
										writeLog("' %s ' - Timer wurde aktiviert -> %s %s @ %s" % (label_serie, show_start, timer_name, webChannel), True)
										timer.log(0, "[SerienRecorder] Activated timer")
									else:
										timer.disabled = True

								timerFound = True
								break

					if not timerFound:
						# suche in (manuell) aktivierten Timern
						for timer in recordHandler.timer_list:
							if timer and timer.service_ref:
								if (timer.begin == serien_time) and (timer.eit == eit) and (str(timer.service_ref).lower() == stbRef.lower()):
									# Eintrag in das timer file
									self.database.activateTimer(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit)
									timerFound = True
									break

					if not timerFound:
						# versuche deaktivierten Timer (auf anderer Box) zu erstellen
						(margin_before, margin_after) = self.database.getMargins(serien_name, webChannel, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)

						# get VPS settings for channel
						vpsSettings = self.database.getVPS(serien_name, webChannel)

						# get tags from marker
						tags = self.database.getTags(serien_name)

						# get addToDatabase for marker
						addToDatabase = self.database.getAddToDatabase(serien_name)

						epgcache = eEPGCache.getInstance()
						allevents = epgcache.lookupEvent(['IBD',(stbRef, 2, eit, -1)]) or []

						for eventid, begin, duration in allevents:
							if int(begin) == (int(serien_time) + (int(margin_before) * 60)):
								label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								if config.plugins.serienRec.TimerName.value == "0":
									timer_name = label_serie
								elif config.plugins.serienRec.TimerName.value == "2":
									timer_name = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								else:
									timer_name = serien_name
								writeLog("Versuche deaktivierten Timer aktiv zu erstellen: ' %s - %s '" % (serien_title, dirname))
								end_unixtime = int(begin) + int(duration)
								end_unixtime = int(end_unixtime) + (int(margin_after) * 60)
								result = serienRecAddTimer.addTimer(stbRef, str(serien_time), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title), eit, False, dirname, vpsSettings, tags, None)
								if result["result"]:
									self.countTimer += 1
									if addToDatabase:
										# Eintrag in das timer file
										self.database.activateTimer(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit)
									show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
									writeLog("' %s ' - Timer wurde angelegt -> %s %s @ %s" % (label_serie, show_start, timer_name, webChannel), True)
								break

				except:				
					pass

	def startCheck3(self):
		# read channels
		self.senderListe = {}
		for s in self.database.getChannels():
			self.senderListe[s[0].lower()] = s[:]

		webChannels = self.database.getActiveChannels()
		writeLog("\nAnzahl aktiver Websender: %d" % len(webChannels), True)
			
		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)
		search_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
		search_end = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(future_time)))
		search_rerun_end = time.strftime("%d.%m.%Y - %H:%M", time.localtime(future_time + (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400))
		writeLog("Berücksichtige Ausstrahlungstermine zwischen %s und %s" % (search_start, search_end), True)
		writeLog("Berücksichtige Wiederholungen zwischen %s und %s" % (search_start, search_rerun_end), True)
		
		# hier werden die wunschliste markers eingelesen
		self.emailData = None
		if config.plugins.serienRec.tvplaner.value and (not self.manuell or self.tvplaner_manuell):
			# When TV-Planer processing is enabled then regular autocheck
			# is only running for the transmissions received by email.
			try:
				self.emailData = getEmailData()
			except:
				writeLog("TV-Planer Verarbeitung fehlgeschlagen!", True)
				print "TV-Planer exception!"
				self.emailData = None
		print "lastFullCheckTime %s" % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(config.plugins.serienRec.tvplaner_last_full_check.value)))
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
		self.countTimer = 0
		self.countTimerUpdate = 0
		self.countNotActiveTimer = 0
		self.countTimerFromWishlist = 0
		self.countSerien = 0
		self.countActivatedSeries = 0
		self.NoOfRecords = int(config.plugins.serienRec.NoOfRecords.value)
		if str(config.plugins.serienRec.maxWebRequests.value).isdigit():
			ds = defer.DeferredSemaphore(tokens=int(config.plugins.serienRec.maxWebRequests.value))
		else:
			ds = defer.DeferredSemaphore(tokens=1)
		
		# regular processing through serienrecorder server
		# TODO: save all transmissions in files to protect from temporary SerienServer fails
		#       data will be read by the file reader below and used for timer programming
		if len(self.markers) > 0:
			while True:
				if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_skipSerienServer.value:
					# Skip serien server processing
					break

				downloads = []
				global transmissionFailed
				transmissionFailed = False
				self.tempDB.cleanUp()
				writeLog("\n---------' Verarbeite Daten vom Server %s---------------------------\n" % fullCheck, True)

				# Create a job queue to keep the jobs processed by the threads
				# Create a result queue to keep the results of the job threads
				jobQueue = Queue.Queue()
				resultQueue = Queue.Queue()

				#writeLog("Active threads: %d" % threading.active_count(), True)
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
								writeLog("' %s - Abfrage der SerienID bei SerienServer fehlgeschlagen - ignored '" % serienTitle, True)
								print "' %s - Abfrage der SerienID bei SerienServer fehlgeschlagen - ignored '" % serienTitle
								continue

							if seriesID is not None and seriesID != 0:
								try:
									getCover(None, serienTitle, seriesID, True)
								except:
									writeLog("' %s - Abruf des Covers fehlgeschlagen - ignored '" % serienTitle, True)
									print "' %s - Abruf des Covers fehlgeschlagen - ignored '" % serienTitle
								Url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(seriesID)
								# look if Series with this ID already exists
								if self.database.markerExists(Url):
									if False:
										# TODO: This should no longer necassary if we change the database schema
										# Series was already in database with different name - remove duplicate marker of TV-Planer and STBAuswahl
										try:
											writeLog("' %s - TV-Planer Marker ist Duplikat zu %s - TV-Planer Marker wird wieder aus Datenbank gelöscht '" % (serienTitle, row[0]), True)
											print "[SerienRecorder] ' %s - TV-Planer Marker ist Duplikat zu %s - TV-Planer Marker gelöscht '" % (serienTitle, row[0])
											cCursor.execute("SELECT ID FROM SerienMarker WHERE Serie=? AND Url LIKE 'https://www.wunschliste.de/serie%'", (serienTitle,))
											rowTVPlaner = cCursor.fetchone()
											if rowTVPlaner:
												cCursor.execute("DELETE FROM SerienMarker WHERE ID=?", (rowTVPlaner[0],))
												cCursor.execute("DELETE FROM STBAuswahl WHERE ID=?", (rowTVPlaner[0],))
										except:
											writeLog("' %s - TV-Planer Marker ist Duplikat zu %s - TV-Planer Marker konnte nicht gelöscht werden '" % (serienTitle, row[0]), True)
											print "[SerienRecorder] ' %s - TV-Planer Marker ist Duplikat zu %s - TV-Planer Marker konnte nicht gelöscht werden '" % (serienTitle, row[0])
										if row[0] != serienTitle:
											# old series title - rename
											try:
												# update name in database
												cCursor.execute("UPDATE SerienMarker SET Serie=? WHERE Url=?", (serienTitle, Url))
												writeLog("' %s - SerienMarker %r -> %r - Korrektur erfolgreich '" % (serienTitle, row[0], serienTitle), True)
												cCursor.execute("UPDATE AngelegteTimer SET Serie=? WHERE Serie=?", (serienTitle, row[0]))
												writeLog("' %s - Timer nutzen neuen Namen '" % (serienTitle, ), True)
												print "[SerienRecorder] ' %s - SerienMarker %r -> %r - Korrektur erfolgreich '" % (serienTitle, row[0], serienTitle)
												dbSerRec.commit()
												# get settings of old marker
												(serienTitle, SerieUrl, SerieStaffel, SerieSender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays) = self.database.getMarkers(config.plugins.serienRec.BoxID.value, config.plugins.serienRec.NoOfRecords.value, [ serienTitle ])[0]
											except:
												writeLog("' %s - SerienMarker %r -> %r - Korrektur fehlgeschlagen '" % (serienTitle, row[0], serienTitle), True)
												writeLog("' %s - bitte SerienMarker %r manuell löschen und Timer korrigieren '" % (serienTitle, row[0]), True)
												print "[SerienRecorder] ' %s - SerienMarker %r -> %r - Korrektur fehlgeschlagen '" % (serienTitle, row[0], serienTitle)
								else:
									print "[SerienRecorder] %r %r %r" % (serienTitle, str(seriesID), Url)
									try:
										self.database.updateMarkerURL(serienTitle, Url)
										writeLog("' %s - TV-Planer Marker -> Url %s - Korrektur erfolgreich '" % (serienTitle, Url), True)
										print "[SerienRecorder] ' %s - TV-Planer Marker -> Url %s - Korrektur erfolgreich '" % (serienTitle, Url)
									except:
										writeLog("' %s - TV-Planer Marker -> Url %s - Korrektur fehlgeschlagen ' " % (serienTitle, Url), True)
										print "[SerienRecorder] ' %s - TV-Planer Marker -> Url %s - Korrektur fehlgeschlagen '" % (serienTitle, Url)
							else:
								writeLog("' %s - TV-Planer Marker ohne SerienID -> ignoriert '" % (serienTitle,), True)
								print "[SerienRecorder] ' %s - TV-Planer Marker ohne SerienID -> ignoriert '" % (serienTitle,)
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
			writeLog("\n---------' Verarbeite TV-Planer E-Mail '-----------------------------------------------------------\n", True)
			download = None
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
					download = retry(0, ds.run, self.downloadEmail, serienTitle, (int(config.plugins.serienRec.TimeSpanForRegularTimer.value)), markerChannels)
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
			writeLog("\n---------' Verarbeite Daten von Dateien '---------------------------------------------------------------\n", True)
			c1 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>(?:\((.*?)x(.*?)\).)*<span class="titel">(.*?)</span></td></tr>')
			c2 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(\S+x\S+))(.*?)\).<span class="titel">(.*?)</span></td></tr>')
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
	
	def checkFinal(self):
		print "checkFinal"
		# final processing
		if config.plugins.serienRec.tvplaner_movies.value:
			# remove all serien markers created for movies
			try:
				self.database.removeMovieMarkers()
				print "[SerienRecorder] ' TV-Planer FilmMarker gelöscht '"
			except:
				writeLog("' TV-Planer FilmMarker löschen fehlgeschlagen '", True)
				print "[SerienRecorder] ' TV-Planer FilmMarker löschen fehlgeschlagen '"
			global transmissionFailed
			if transmissionFailed: 
				# always do fullcheck after transmission error
				config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
				config.plugins.serienRec.tvplaner_last_full_check.save()
				configfile.save()

		if config.plugins.serienRec.AutoBackup.value == "after":
			self.createBackup()

		if config.plugins.serienRec.longLogFileName.value:
			lt = time.localtime()
			logFileSave = SERIENRECORDER_LONG_LOGFILENAME % (config.plugins.serienRec.LogFilePath.value, str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
			shutil.copy(logFile, logFileSave)
		
		# trigger read of log file
		global autoCheckFinished
		autoCheckFinished = True
		print "checkFinal: autoCheckFinished"
		if config.plugins.serienRec.autochecktype.value == "1":
			lt = time.localtime()
			deltatime = self.getNextAutoCheckTimer(lt)
			writeLog("\nVerbleibende Zeit bis zum nächsten Auto-Check: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)
			if config.plugins.serienRec.tvplaner_full_check.value:
				autoCheckDays = ((int(config.plugins.serienRec.tvplaner_last_full_check.value) + (int(config.plugins.serienRec.checkfordays.value) - 1) * 86400) - int(time.time())) / 86400
				if autoCheckDays < 0:
					autoCheckDays = 0
				writeLog("Verbleibende Zeit bis zum nächsten vollen Auto-Check: %d Tage" % autoCheckDays, True)

		self.tempDB = None
		self.database = None

		# in den deep-standby fahren.
		self.askForDSB()

	def processTransmission(self, data, serien_name, staffeln, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays=None):
		print "processTransmissions: %r" % serien_name
		#print data
		self.count_url += 1

		if data is None:
			writeLog("Fehler beim Abrufen und Verarbeiten der Ausstrahlungstermine [%s]" % serien_name, True)
			#print "processTransmissions: no Data"
			return

		(fromTime, toTime) = self.database.getTimeSpan(serien_name, config.plugins.serienRec.globalFromTime.value, config.plugins.serienRec.globalToTime.value)
		if self.NoOfRecords < AnzahlAufnahmen:
			self.NoOfRecords = AnzahlAufnahmen

		TimeSpan_time = int(future_time)
		if config.plugins.serienRec.forceRecording.value:
			TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400

		# loop over all transmissions
		for current_serien_name, sender, startzeit, endzeit, staffel, episode, title, status in data:
			start_unixtime = startzeit
			end_unixtime = endzeit
			
			# install missing covers
			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			CreateDirectory(current_serien_name, dirname, dirname_serie, True)
			
			# setze die vorlauf/nachlauf-zeit
			(margin_before, margin_after) = self.database.getMargins(serien_name, sender, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			if not config.plugins.serienRec.forceRecording.value:
				if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						print "processTransmissions time range ignore: %r" % serien_name
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
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(self.senderListe, sender)
			if stbChannel == "":
				writeLogFilter("channels", "' %s ' - STB-Sender nicht gefunden ' -> ' %s '" % (label_serie, webChannel))
				continue

			if int(status) == 0:
				writeLogFilter("channels", "' %s ' - STB-Sender deaktiviert -> ' %s '" % (label_serie, webChannel))
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
								writeLogFilter("allowedEpisodes", "' %s ' - Episode nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
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
					writeLog("' %s ' - Timer vom Merkzettel wird angelegt @ %s" % (label_serie, stbChannel), True)
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
					writeLogFilter("allowedEpisodes", "' %s ' - Staffel nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
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

			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)

			self.tempDB.addTransmission([(current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays)])
		#print "processTransmissions exit: %r" % serien_name

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
		#raw.sort(key=lambda t : time.strptime("%s %s" % (t[1],t[2]),"%d.%m %H.%M"))
		def y(l):
			(day, month) = l[1].split('.')
			(start_hour, start_min) = l[2].split('.')
			now = datetime.datetime.now()
			if int(month) < now.month:
				return time.mktime((int(now.year) + 1, int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
			else:
				return time.mktime((int(now.year), int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
		raw.sort(key=y)
		
		# global termineCache
		# termineCache.update({serien_name:raw})
		
		# check for parsing error
		if not raw:
			# parsing error -> nothing to do
			return
		
		(fromTime, toTime) = self.database.getTimeSpan(serien_name, config.plugins.serienRec.globalFromTime.value, config.plugins.serienRec.globalToTime.value)
		if self.NoOfRecords < AnzahlAufnahmen:
			self.NoOfRecords = AnzahlAufnahmen
		
		TimeSpan_time = int(future_time)
		if config.plugins.serienRec.forceRecording.value:
			TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400
		
		# loop over all transmissions
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			# umlaute umwandeln
			#sender = decodeISO8859_1(sender, True)
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
			#title = decodeISO8859_1(title, True)
			#staffel = decodeISO8859_1(staffel, True)
			
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
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(self.senderListe, sender)
			if stbChannel == "":
				writeLogFilter("channels", "' %s ' - STB-Sender nicht gefunden ' -> ' %s '" % (label_serie, webChannel))
				continue
			
			if int(status) == 0:
				writeLogFilter("channels", "' %s ' - STB-Sender deaktiviert -> ' %s '" % (label_serie, webChannel))
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
				writeLogFilter("channels", "' %s ' - Sender nicht erlaubt -> %s -> %s" % (label_serie, sender, allowedSender))
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
								writeLogFilter("allowedEpisodes", "' %s ' - Episode nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
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
					writeLog("' %s ' - Timer vom Merkzettel wird angelegt @ %s" % (label_serie, stbChannel), True)
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
					writeLogFilter("allowedEpisodes", "' %s ' - Staffel nicht erlaubt -> ' %s ' -> ' %s '" % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
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
			
			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			
			self.tempDB.addTransmission([(current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays)])


	def downloadFile(self, url):
		#print "[Serien Recorder] call %s" % url
		try:
			pageFile = open("%sdata/" % serienRecMainPath + url.split("=")[1], "r")
			text = pageFile.read()
			pageFile.close()
		except:
			text = None
		return text

	def downloadEmail(self, seriesName, timeSpan, markerChannels):
		transmissions = []
		for key in self.emailData.keys():
			if self.emailData[key][0][0] == seriesName:
				seriesName = key
				break
		for transmission in self.emailData[seriesName]:
			if transmission[1] in markerChannels:
				transmissions.append(transmission[0:-1])
		return transmissions
		
	def createTimer(self, result=True):
		#writeLog("\n", True)
		# versuche deaktivierte Timer zu erstellen
		self.activateTimer()
		
		# jetzt die Timer erstellen	
		for x in range(self.NoOfRecords): 
			self.searchTimer(x)

		# gleiche alte Timer mit EPG ab
		current_time = int(time.time())
		if config.plugins.serienRec.eventid.value:
			self.adjustEPGtimes(current_time)

		writeLog("\n", True)

		# Datenbank aufräumen
		self.database.rebuild()
		self.tempDB.rebuild()

		global autoCheckFinished
		autoCheckFinished = True

		# Statistik
		self.speedEndTime = time.clock()
		speedTime = (self.speedEndTime-self.speedStartTime)
		if config.plugins.serienRec.eventid.value:
			writeLog("%s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate)), True)
			print "[SerienRecorder] %s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate))
		else:
			writeLog("%s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer)), True)
			print "[SerienRecorder] %s/%s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer))
		if self.countNotActiveTimer > 0:
			writeLog("%s Timer wurde(n) wegen Konfikten deaktiviert erstellt!" % str(self.countNotActiveTimer), True)
			print "[SerienRecorder] %s Timer wurde(n) wegen Konfikten deaktiviert erstellt!" % str(self.countNotActiveTimer)
		if self.countTimerFromWishlist > 0:
			writeLog("%s Timer vom Merkzettel wurde(n) erstellt!" % str(self.countTimerFromWishlist), True)
			print "[SerienRecorder] %s Timer vom Merkzettel wurde(n) erstellt!" % str(self.countTimerFromWishlist)
		writeLog("---------' Auto-Check beendet (Ausführungsdauer: %3.2f Sek.)'---------------------------------------------------------------------------" % speedTime, True)
		print "---------' Auto-Check beendet (Ausführungsdauer: %3.2f Sek.)'-------------------------------------------------------------------------------" % speedTime
		if (config.plugins.serienRec.showNotification.value in ("2", "3")) and (not self.manuell):
			statisticMessage = "Serien vorgemerkt: %s/%s\nTimer erstellt: %s\nTimer aktualisiert: %s\nTimer mit Konflikten: %s\nTimer vom Merkzettel: %s" % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate), str(self.countNotActiveTimer), str(self.countTimerFromWishlist))
			newSeasonOrEpisodeMessage = ""
			if self.newSeriesOrEpisodesFound:
				newSeasonOrEpisodeMessage = "\n\nNeuer Serien- oder Staffelbeginn gefunden"
			
			Notifications.AddPopup("SerienRecorder Suchlauf für neue Timer wurde beendet.\n\n%s%s" % (statisticMessage, newSeasonOrEpisodeMessage), MessageBox.TYPE_INFO, timeout=10, id="Suchlauf wurde beendet")
		
		return result

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
					for each in self.MessageList:
						Notifications.RemovePopup(each[3])

					print "[SerienRecorder] gehe in Deep-Standby"
					writeLog("gehe in Deep-Standby")
					if Screens.Standby.inStandby:
						RecordTimerEntry.TryQuitMainloop()
					else:
						Notifications.AddNotificationWithID("Shutdown", Screens.Standby.TryQuitMainloop, 1)
				else:
					print "[SerienRecorder] Eine laufende Aufnahme verhindert den Deep-Standby"
					writeLog("Eine laufende Aufnahme verhindert den Deep-Standby")
			else:
				print "[SerienRecorder] gehe in Standby"
				writeLog("gehe in Standby")
				Notifications.AddNotification(Screens.Standby.Standby)

	def searchTimer(self, NoOfRecords):
		if NoOfRecords:
			optionalText = " (%s. Wiederholung)" % NoOfRecords
		else:
			optionalText = ""

		writeLog("\n---------' Erstelle Timer%s '-------------------------------------------------------------------------------\n" % optionalText, True)

		transmissions = self.tempDB.getTransmissionsOrderedByNumberOfRecordings(NoOfRecords)
		for transmission in transmissions:
			(serien_name, staffel, episode, title, anzahl) = transmission
			(noOfRecords, preferredChannel, useAlternativeChannel) = self.database.getPreferredMarkerChannels(serien_name, config.plugins.serienRec.useAlternativeChannel.value, config.plugins.serienRec.NoOfRecords.value)

			###############################
			##
			## erstellt das serien verzeichnis
			(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
			self.enableDirectoryCreation = False

			self.konflikt = ""
			TimerDone = self.searchTimer2(serien_name, staffel, episode, title, optionalText, preferredChannel, dirname)
			if (not TimerDone) and useAlternativeChannel:
				if preferredChannel == 1:
					usedChannel = 2
				else:
					usedChannel = 1
				TimerDone = self.searchTimer2(serien_name, staffel, episode, title, optionalText, usedChannel, dirname)
			
			if not TimerDone:
				if str(episode).isdigit():
					if int(episode) == 0:
						transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode, title)
					else:
						transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode)
				else:
					transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode)
					
				for transmissionForTimer in transmissionsForTimer:
					(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel, excludedWeekdays) = transmissionForTimer
					if preferredChannel == 1:
						timer_stbChannel = stbChannel
						timer_stbRef = stbRef
						timer_start_unixtime = start_unixtime
						timer_end_unixtime = end_unixtime
						timer_eit = eit
					else:
						timer_stbChannel = altstbChannel
						timer_stbRef = altstbRef
						timer_start_unixtime = alt_start_unixtime
						timer_end_unixtime = alt_end_unixtime
						timer_eit = alt_eit
					
					##############################
					#
					# Setze deaktivierten Timer
					#
					# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt
					start_time = (time.localtime(int(timer_start_unixtime)).tm_hour * 60) + time.localtime(int(timer_start_unixtime)).tm_min
					end_time = (time.localtime(int(timer_end_unixtime)).tm_hour * 60) + time.localtime(int(timer_end_unixtime)).tm_min
					if TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel, True):
							if str(episode).isdigit():
								if int(episode) == 0:
									self.tempDB.removeTransmission(serien_name, staffel, episode, title, start_unixtime, stbRef)
								else:
									self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
							else:
								self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
							break

				if len(self.konflikt) > 0:
					if config.plugins.serienRec.showMessageOnConflicts.value:
						self.MessageList.append(("Timerkonflikte beim SerienRecorder Suchlauf:\n%s" % self.konflikt, MessageBox.TYPE_INFO, -1, self.konflikt))
						Notifications.AddPopup("Timerkonflikte beim SerienRecorder Suchlauf:\n%s" % self.konflikt, MessageBox.TYPE_INFO, timeout=-1, id=self.konflikt)
						
			##############################
			#
			# erstellt das serien verzeichnis
			if TimerDone and self.enableDirectoryCreation:
				CreateDirectory(serien_name, dirname, dirname_serie)
					

	def searchTimer2(self, serien_name, staffel, episode, title, optionalText, usedChannel, dirname):				
		#print "searchTimer2: %r" % serien_name
		# prepare postprocessing for forced recordings
		forceRecordings = []
		forceRecordings_W = []
		eventRecordings = []
		self.konflikt = ""

		TimerDone = False
		if str(episode).isdigit():
			if int(episode) == 0:
				transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode, title)
			else:
				transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode)
		else:
			transmissionsForTimer = self.tempDB.getTransmissionsToCreateTimer(serien_name, staffel, episode)

		for transmissionForTimer in transmissionsForTimer:
			(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel, excludedWeekdays) = transmissionForTimer
			if usedChannel == 1:
				timer_stbChannel = stbChannel
				timer_stbRef = stbRef
				timer_start_unixtime = start_unixtime
				timer_end_unixtime = end_unixtime
				timer_eit = eit
			else:
				timer_stbChannel = altstbChannel
				timer_stbRef = altstbRef
				timer_start_unixtime = alt_start_unixtime
				timer_end_unixtime = alt_end_unixtime
				timer_eit = alt_eit

			# Is channel assigned
			if timer_stbChannel == "":
				writeLogFilter("channels", "' %s ' - STB-Sender nicht in bevorzugter Senderliste zugewiesen -> ' %s '" % (label_serie, webChannel))
				# Nicht in bevorzugter Kanalliste - dann gehen wir davon aus, dass kein Timer angelegt werden soll.
				TimerDone = True
				continue

			##############################
			#
			# CHECK
			#
			# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
			#
			# check ob timer existiert
			startTimeLowBound = int(timer_start_unixtime) - (int(STBHelpers.getEPGTimeSpan()) * 60)
			startTimeHighBound = int(timer_start_unixtime) + (int(STBHelpers.getEPGTimeSpan()) * 60)

			if self.database.timerExists(webChannel, serien_name, staffel, episode, startTimeLowBound, startTimeHighBound):
				writeLogFilter("added", "' %s ' - Timer für diese Episode%s wurde bereits erstellt -> ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
				if str(episode).isdigit():
					if int(episode) == 0:
						self.tempDB.removeTransmission(serien_name, staffel, episode, title, start_unixtime, stbRef)
					else:
						self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
				else:
					self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
				continue

			# check anzahl timer und auf hdd
			bereits_vorhanden_HDD = 0
			if str(episode).isdigit():
				if int(episode) == 0:
					bereits_vorhanden = self.database.getNumberOfTimers(serien_name, staffel, episode, title, searchOnlyActiveTimers = True)
					if config.plugins.serienRec.sucheAufnahme.value:
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False, title)
				else:
					bereits_vorhanden = self.database.getNumberOfTimers(serien_name, staffel, episode, searchOnlyActiveTimers = True)
					if config.plugins.serienRec.sucheAufnahme.value:
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)
			else:
				bereits_vorhanden = self.database.getNumberOfTimers(serien_name, staffel, episode, searchOnlyActiveTimers = True)
				if config.plugins.serienRec.sucheAufnahme.value:
					bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)
				
			if bereits_vorhanden >= AnzahlAufnahmen:
				writeLogFilter("added", "' %s ' - Eingestellte Anzahl Timer für diese Episode%s wurden bereits erstellt -> ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
				TimerDone = True
				break

			if bereits_vorhanden_HDD >= AnzahlAufnahmen:
				writeLogFilter("disk", "' %s ' - Episode%s bereits auf HDD vorhanden -> ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
				TimerDone = True
				break

			# check for excluded weekdays - this can be done early so we can skip all other checks
			# if the transmission date is on an excluded weekday
			if str(excludedWeekdays).isdigit():
				print "[SerienRecorder] - Excluded weekdays check"
				#writeLog("- Excluded weekdays check", True)
				transmissionDate = datetime.date.fromtimestamp((int(timer_start_unixtime)))
				weekday = transmissionDate.weekday()
				print "    Serie = %s, Datum = %s, Wochentag = %s" % (label_serie, time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime))), weekday)
				#writeLog("   Serie = %s, Datum = %s, Wochentag = %s" % (label_serie, time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime))), weekday), True)
				if excludedWeekdays & (1 << weekday) != 0:
					writeLogFilter("timeRange", "' %s ' - Wochentag auf der Ausnahmeliste -> ' %s '" % (label_serie, transmissionDate.strftime('%A')))
					TimerDone = True
					continue

			if config.plugins.serienRec.splitEventTimer.value != "0" and '/' in str(episode):
			# Event-Programmierung auflösen -> 01/1x02/1x03
				writeLogFilter("timerDebug", "Event-Programmierung gefunden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
				splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, staffel, title)

				alreadyExistsCount = 0
				for idx,entry in enumerate(splitedSeasonEpisodeList):
					splitedTitle = "dump"
					if useTitles:
						splitedTitle = splitedTitleList[idx]
					alreadyExists = self.database.getNumberOfTimers(serien_name, entry[0], entry[1], splitedTitle, False)
					if alreadyExists:
						alreadyExistsCount += 1

				if len(splitedSeasonEpisodeList) == alreadyExistsCount:
					# Alle Einzelfolgen wurden bereits aufgenommen - der Event muss nicht mehr aufgenommen werden.
					writeLogFilter("timerDebug", "   ' %s ' - Timer für Einzelepisoden wurden bereits erstellt -> ' %s '" % (serien_name, check_SeasonEpisode))
					TimerDone = True
					continue
				elif config.plugins.serienRec.splitEventTimer.value == "2":
					# Nicht alle Einzelfolgen wurden bereits aufgenommen, es sollen aber Einzelfolgen bevorzugt werden
					writeLogFilter("timerDebug", "   ' %s ' - Versuche zunächst Timer für Einzelepisoden anzulegen" % serien_name)
					eventRecordings.append((title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel))
					continue

			##############################
			#
			# CHECK
			#
			# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt und finde Wiederholungen auf dem gleichen Sender
			#
			# prepare valid time range
			if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
				start_time = (time.localtime(int(timer_start_unixtime)).tm_hour * 60) + time.localtime(int(timer_start_unixtime)).tm_min
				end_time = (time.localtime(int(timer_end_unixtime)).tm_hour * 60) + time.localtime(int(timer_end_unixtime)).tm_min
				if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
					timeRangeList = "[%s:%s-%s:%s]" % (str(int(fromTime)/60).zfill(2), str(int(fromTime)%60).zfill(2), str(int(toTime)/60).zfill(2), str(int(toTime)%60).zfill(2))
					writeLogFilter("timeRange", "' %s ' - Timer (%s:%s-%s:%s) nicht in Zeitspanne %s" % (label_serie, str(start_time/60).zfill(2), str(start_time%60).zfill(2), str(end_time/60).zfill(2), str(end_time%60).zfill(2), timeRangeList))
					# forced recording activated?
					if not config.plugins.serienRec.forceRecording.value:
						continue
						
					# backup timer data for post processing
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					writeLogFilter("timeRange", "' %s ' - Backup Timer -> %s" % (label_serie, show_start))
					forceRecordings.append((title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel))
					continue
					
				##############################
				#
				# CHECK
				#
				# Ueberpruefe ob der sendetermin innerhalb der Wartezeit für Wiederholungen liegt
				#
				if config.plugins.serienRec.forceRecording.value:
					TimeSpan_time = int(future_time) + (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400
					if int(timer_start_unixtime) > int(TimeSpan_time):
						# backup timer data for post processing
						show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
						writeLogFilter("timeRange", "' %s ' - Backup Timer -> %s" % (label_serie, show_start))
						forceRecordings_W.append((title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel))
						continue

			##############################
			#
			# Setze Timer
			#
			if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
				if str(episode).isdigit():
					if int(episode) == 0:
						self.tempDB.removeTransmission(serien_name, staffel, episode, title, start_unixtime, stbRef)
					else:
						self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
				else:
					self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
				TimerDone = True
				break
				
		### end of for loop

		if not TimerDone:
			# post processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in forceRecordings_W:
				if self.database.getNumberOfTimers(serien_name, staffel, episode, title, False):
					continue
				# programmiere Timer (Wiederholung)
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
					if str(episode).isdigit():
						if int(episode) == 0:
							self.tempDB.removeTransmission(serien_name, staffel, episode, title, start_unixtime, stbRef)
						else:
							self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
					else:
						self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
					TimerDone = True
					#break
					
		if not TimerDone:
			# post processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in forceRecordings:
				if self.database.getNumberOfTimers(serien_name, staffel, episode, title, False):
					continue
				show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
				writeLog("' %s ' - Keine Wiederholung gefunden! -> %s" % (label_serie, show_start), True)
				# programmiere Timer
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
					if str(episode).isdigit():
						if int(episode) == 0:
							self.tempDB.removeTransmission(serien_name, staffel, episode, title, start_unixtime, stbRef)
						else:
							self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
					else:
						self.tempDB.removeTransmission(serien_name, staffel, episode, None, start_unixtime, stbRef)
					TimerDone = True
					#break

		if not TimerDone:
			# post processing event recordings
			for singleTitle, staffel, singleEpisode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in eventRecordings[:]:
				if self.shouldCreateEventTimer(serien_name, staffel, singleEpisode, singleTitle):
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					writeLog("   ' %s ' - Einzelepisoden nicht gefunden! -> %s" % (label_serie, show_start), True)
					# programmiere Timer
					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
						TimerDone = True
						#break

		return TimerDone

	@staticmethod
	def splitEvent(episode, staffel, title):
		splitedSeasonEpisodeList = []
		if 'x' in str(episode):
			seasonEpisodeList = episode.split('/')
			for seasonEpisode in seasonEpisodeList:
				if not 'x' in seasonEpisode:
					seasonEpisode = str(staffel) + 'x' + str(seasonEpisode)
				splitedSeasonEpisodeList.append(seasonEpisode.split('x'))
		else:
			seasonEpisodeList = episode.split('/')
			for seasonEpisode in seasonEpisodeList:
				seasonEpisode = str(staffel) + 'x' + str(seasonEpisode)
				splitedSeasonEpisodeList.append(seasonEpisode.split('x'))
		useTitles = True
		splitedTitleList = title.split('/')
		if len(splitedTitleList) != len(splitedSeasonEpisodeList):
			useTitles = False
		return splitedSeasonEpisodeList, splitedTitleList, useTitles

	def doTimer(self, current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode, optionalText = '', vomMerkzettel = False, tryDisabled = False):
		##############################
		#
		# CHECK
		#
		# ueberprueft ob tage x voraus passt und ob die startzeit nicht kleiner ist als die aktuelle uhrzeit
		#
		show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
		if int(start_unixtime) > int(future_time):
			show_future = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(future_time)))
			writeLogFilter("timeLimit", "' %s ' - Timer wird evtl. später angelegt -> Sendetermin: %s - Erlaubte Zeitspanne bis %s" % (label_serie, show_start, show_future))
			return True
		if int(current_time) > int(start_unixtime):
			show_current = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
			writeLogFilter("timeLimit", "' %s ' - Der Sendetermin liegt in der Vergangenheit: %s - Aktuelles Datum: %s" % (label_serie, show_start, show_current))
			return True

		# get VPS settings for channel
		vpsSettings = self.database.getVPS(serien_name, webChannel)

		# get tags from marker
		tags = self.database.getTags(serien_name)

		# get addToDatabase for marker
		addToDatabase = self.database.getAddToDatabase(serien_name)

		# provider_ref = ServiceReference(stbRef)
		# providerName = provider.getServiceName()
		# writeLogFilter("timeLimit", "addtimer stbRef : %s" % (str(stbRef) ) )

		# new_needs_ci=checkCI(provider_ref.ref,1)
		# writeLogFilter("timeLimit", "ci0  : %s" % (str(new_needs_ci1) ) )
		# writeLog("ci0  -> %s " % (str(new_needs_ci1)), True)
		# # new_needs_ci2=checkCI(provider_ref,1)
		# writeLogFilter("timeLimit", "ci1  : %s" % (str(new_needs_ci2) ) )
		
		# versuche timer anzulegen
		# setze strings für addtimer
		if checkTuner(start_unixtime, end_unixtime, stbRef):
			if config.plugins.serienRec.TimerName.value == "0":
				timer_name = label_serie
			elif config.plugins.serienRec.TimerName.value == "2":
				timer_name = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title)
			else:
				timer_name = serien_name
			result = serienRecAddTimer.addTimer(stbRef, str(start_unixtime), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, False, dirname, vpsSettings, tags, None)
			if result["result"]:
				self.countTimer += 1
				# Eintrag in das timer file
				self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit, addToDatabase)
				if vomMerkzettel:
					self.countTimerFromWishlist += 1
					writeLog("' %s ' - Timer (vom Merkzettel) wurde angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					self.database.updateBookmark(serien_name, staffel, episode)
					self.database.removeBookmark(serien_name, staffel, episode)
				else:
					writeLog("' %s ' - Timer wurde angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					# Event-Programmierung verarbeiten
					if config.plugins.serienRec.splitEventTimer.value == "1" and '/' in str(episode):
						splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, staffel, title)

						for idx,entry in enumerate(splitedSeasonEpisodeList):
							splitedTitle = "dump"
							if useTitles:
								splitedTitle = splitedTitleList[idx]
							alreadyExists = self.database.getNumberOfTimers(serien_name, entry[0], entry[1], splitedTitle, False)
							if not alreadyExists and addToDatabase:
								# Nicht vorhandene Einzelfolgen als bereits aufgenommen markieren
								self.database.addToTimerList(serien_name, entry[1], entry[1], entry[0], splitedTitle, int(time.time()-10), "", "", 0, 1)
								writeLogFilter("timerDebug", "   Einzelepisode wird nicht mehr aufgenommen: %s S%sE%s - %s" % (serien_name, str(entry[0]).zfill(2), str(entry[1]).zfill(2), splitedTitle))

				self.enableDirectoryCreation = True
				return True
			elif not tryDisabled:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog("' %s ' - Timer konnte nicht angelegt werden%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
				writeLog("' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"]), True)
			else:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog("' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"]), True)
				dbMessage = result["message"].replace("Conflicting Timer(s) detected!", "").strip()
				
				result = serienRecAddTimer.addTimer(stbRef, str(start_unixtime), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, True, dirname, vpsSettings, tags, None)
				if result["result"]:
					self.countNotActiveTimer += 1
					# Eintrag in das timer file
					self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit, addToDatabase, False)
					self.database.addTimerConflict(dbMessage, start_unixtime, webChannel)
					if vomMerkzettel:
						self.countTimerFromWishlist += 1
						writeLog("' %s ' - Timer (vom Merkzettel) wurde deaktiviert angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					else:
						writeLog("' %s ' - Timer wurde deaktiviert angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					self.enableDirectoryCreation = True
					return True
				else:
					self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
					print "' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
					writeLog("' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"]), True)
		else:
			print "Tuner belegt %s %s" % (label_serie, show_start)
			writeLog("Tuner belegt: %s %s" % (label_serie, show_start), True)
		return False

	@staticmethod
	def checkSender(mSlist, mSender):
		if mSender.lower() in mSlist:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = mSlist[mSender.lower()]
			# if altstbChannel == "":
			# 	altstbChannel = stbChannel
			# 	altstbRef = stbRef
			# elif stbChannel == "":
			# 	stbChannel = altstbChannel
			# 	stbRef = altstbRef
		else:
			webChannel = mSender
			stbChannel = ""
			stbRef = ""
			altstbChannel = ""
			altstbRef = ""
			status = "0"
		return webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status

	def shouldCreateEventTimer(self, serien_name, staffel, episode, title):
		if self.database.getNumberOfTimers(serien_name, staffel, episode, title, False):
			return False

		result = True
		if config.plugins.serienRec.splitEventTimer.value != "2" and '/' in str(episode):
			# Event-Programmierung auflösen -> 01/1x02/1x03
			splitedSeasonEpisodeList = []
			if 'x' in str(episode):
				episode = str(staffel) + 'x' + str(episode)
				seasonEpisodeList = episode.split('/')
				for seasonEpisode in seasonEpisodeList:
					splitedSeasonEpisodeList.append(seasonEpisode.split('x'))
			else:
				seasonEpisodeList = episode.split('/')
				for seasonEpisode in seasonEpisodeList:
					seasonEpisode = str(staffel) + 'x' + str(seasonEpisode)
					splitedSeasonEpisodeList.append(seasonEpisode.split('x'))

			useTitles = True
			splitedTitleList = title.split('/')
			if len(splitedTitleList) != len(splitedSeasonEpisodeList):
				useTitles = False

			# Möglichst die Einzelfolgen bevorzugen und Event ignorieren
			alreadyExistsCount = 0
			for idx,entry in enumerate(splitedSeasonEpisodeList):
				title = "dump"
				if useTitles:
					title = splitedTitleList[idx]
				alreadyExists = self.database.getNumberOfTimers(serien_name, entry[0], entry[1], title, False)
				if alreadyExists:
					alreadyExistsCount += 1

			if alreadyExistsCount == len(splitedSeasonEpisodeList):
				result = False

		return result

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, addToDatabase, TimerAktiviert = True):
		if not addToDatabase:
			print "[SerienRecorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", "   Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			(margin_before, margin_after) = self.database.getMargins(serien_name, webChannel, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)

			if self.database.timerExistsByServiceRef(serien_name, stbRef, int(start_time) + (int(margin_before) * 60) - (int(STBHelpers.getEPGTimeSpan()) * 60), int(start_time) + (int(margin_before) * 60) + (int(STBHelpers.getEPGTimeSpan()) * 60)):
				self.database.updateTimerEIT(serien_name, stbRef, eit, int(start_time) + (int(margin_before) * 60) - (int(STBHelpers.getEPGTimeSpan()) * 60), int(start_time) + (int(margin_before) * 60) + (int(STBHelpers.getEPGTimeSpan()) * 60), TimerAktiviert)
				print "[SerienRecorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
				writeLogFilter("timerDebug", "   Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
			else:
				self.database.addToTimerList(serien_name, episode, episode, staffel, title, start_time, stbRef, webChannel, eit, TimerAktiviert)
				print "[SerienRecorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
				writeLogFilter("timerDebug", "   Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))

	@staticmethod
	def dataError(error, url=None):
		print "[SerienRecorder] Es ist ein Fehler aufgetreten - die Daten konnten nicht abgerufen/verarbeitet werden: (%s)" % error

class serienRecTimer(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.WochenTag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		self.ErrorMsg = "unbekannt"
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Liste der aufgenommenen Folgen bearbeiten"),
			"cancel": (self.keyCancel, "zurück zur Serienplaner-Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "ausgewählten Timer löschen"),
			"green" : (self.viewChange, "Sortierung ändern"),
			"yellow": (self.keyYellow, "umschalten alle/nur aktive Timer anzeigen"),
			"blue"  : (self.keyBlue, "alle noch ausstehenden Timer löschen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"9"		: (self.dropAllTimer, "Alle Timer aus der Datenbank löschen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			#"ok"    : self.keyOK,
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.changesMade = False
		self.filter = True
		
		self.onLayoutFinish.append(self.readTimer)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Entferne Timer")
		if config.plugins.serienRec.recordListView.value == 0:
			self['text_green'].setText("Zeige neueste Timer zuerst")
		elif config.plugins.serienRec.recordListView.value == 1:
			self['text_green'].setText("Zeige früheste Timer zuerst")
		self['text_ok'].setText("Liste bearbeiten")
		self['text_yellow'].setText("Zeige auch alte Timer")
		self['text_blue'].setText("Entferne neue Timer")
		self.num_bt_text[4][1] = "Datenbank leeren"

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

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
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return
			
		serien_name = self['menu_list'].getCurrent()[0][0]
		url = self.database.getMarkerURL(serien_name)
		if url:
			serien_id = getSeriesIDByURL(url)
			if serien_id:
				self.session.open(serienRecShowInfo, serien_name, serien_id)
				#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
				#				  MessageBox.TYPE_INFO, timeout=10)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][0]
			print "[SerienRecorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][0]
			print "[SerienRecorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.readTimer()
				
	def viewChange(self):
		if config.plugins.serienRec.recordListView.value == 1:
			config.plugins.serienRec.recordListView.value = 0
			self['text_green'].setText("Zeige neueste Timer zuerst")
		else:
			config.plugins.serienRec.recordListView.value = 1
			self['text_green'].setText("Zeige früheste Timer zuerst")
		config.plugins.serienRec.recordListView.save()
		configfile.save()
		self.readTimer()

	def readTimer(self, showTitle=True):
		current_time = int(time.time())
		deltimer = 0
		timerList = []

		timers = self.database.getAllTimer(current_time if self.filter else None)
		for timer in timers:
			(serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer) = timer
			if int(start_time) < int(current_time):
				deltimer += 1
				timerList.append((serie, staffel, episode, title, start_time, webChannel, "1", 0, bool(activeTimer)))
			else:
				timerList.append((serie, staffel, episode, title, start_time, webChannel, "0", eit, bool(activeTimer)))
		
		if showTitle:
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			if self.filter:
				self['title'].setText("Timer-Liste: %s ausstehende Timer" % len(timerList))
			else:
				self['title'].setText("Timer-Liste: %s abgeschlossene und %s ausstehende Timer" % (deltimer, len(timerList)-deltimer))

		if config.plugins.serienRec.recordListView.value == 0:
			timerList.sort(key=lambda t : t[4])
		elif config.plugins.serienRec.recordListView.value == 1:
			timerList.sort(key=lambda t : t[4])
			timerList.reverse()

		self.chooseMenuList.setList(map(self.buildList, timerList))
		if len(timerList) == 0:
			if showTitle:
				self['title'].instance.setForegroundColor(parseColor("foreground"))
				self['title'].setText("Serien Timer - 0 Serien in der Aufnahmeliste.")

		self.getCover()

	def buildList(self, entry):
		(serie, staffel, episode, title, start_time, webChannel, foundIcon, eit, activeTimer) = entry
		xtime = time.strftime(self.WochenTag[time.localtime(int(start_time)).tm_wday]+", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))
		xtitle = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title)

		if int(foundIcon) == 1:
			imageFound = "%simages/found.png" % serienRecMainPath
		else:
			imageFound = "%simages/black.png" % serienRecMainPath

		if activeTimer:
			SerieColor = None
		else:
			SerieColor = parseColor('red').argb()

		foregroundColor = parseColor('foreground').argb()

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 8 * skinFactor, 32 * skinFactor, 32 * skinFactor, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel, SerieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29 * skinFactor, 250 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, foregroundColor, foregroundColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, re.sub("(?<= - )dump\Z", "(Manuell hinzugefügt !!)", xtitle), foregroundColor, foregroundColor)
			]

	def keyOK(self):
		self.session.open(serienRecModifyAdded, False)

	def callDeleteSelectedTimer(self, answer):
		if answer:
			serien_name = self['menu_list'].getCurrent()[0][0]
			staffel = self['menu_list'].getCurrent()[0][1]
			episode = self['menu_list'].getCurrent()[0][2]
			serien_title = self['menu_list'].getCurrent()[0][3]
			serien_time = self['menu_list'].getCurrent()[0][4]
			serien_channel = self['menu_list'].getCurrent()[0][5]
			serien_eit = self['menu_list'].getCurrent()[0][7]
			self.removeTimer(serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)
		else:
			return
			
	def removeTimer(self, serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit=0):
		if config.plugins.serienRec.TimerName.value == "1":    #"<Serienname>"
			title = serien_name
		elif config.plugins.serienRec.TimerName.value == "2":  #"SnnEmm - <Episodentitel>"
			title = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title)
		else:                                                  #"<Serienname> - SnnEmm - <Episodentitel>"
			title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
		removed = serienRecAddTimer.removeTimerEntry(title, serien_time, serien_eit)
		if not removed:
			print "[SerienRecorder] enigma2 NOOOTTT removed"
		else:
			print "[SerienRecorder] enigma2 Timer removed."

		self.database.removeTimer(serien_name, staffel, episode, None, serien_time, serien_channel, (serien_eit if serien_eit > 0 else None))

		self.changesMade = True
		self.readTimer(False)
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Timer '- %s -' entfernt." % serien_name)

	def keyRed(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Timer leer."
			return
		else:
			serien_name = self['menu_list'].getCurrent()[0][0]
			staffel = self['menu_list'].getCurrent()[0][1]
			episode = self['menu_list'].getCurrent()[0][2]
			serien_title = self['menu_list'].getCurrent()[0][3]
			serien_time = self['menu_list'].getCurrent()[0][4]
			serien_channel = self['menu_list'].getCurrent()[0][5]
			serien_eit = self['menu_list'].getCurrent()[0][7]

			print self['menu_list'].getCurrent()[0]

			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, "Soll '%s - S%sE%s - %s' wirklich entfernt werden?" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), re.sub("\Adump\Z", "(Manuell hinzugefügt !!)", serien_title)), MessageBox.TYPE_YESNO, default = False)
			else:
				self.removeTimer(serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)

	def keyYellow(self):
		if self.filter:
			self['text_yellow'].setText("Zeige nur neue Timer")
			self.filter = False
		else:
			self['text_yellow'].setText("Zeige auch alte Timer")
			self.filter = True
		self.readTimer()
		
	def keyBlue(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeNewTimerFromDB, MessageBox,
										  "Sollen wirklich alle noch ausstehenden Timer von der Box und aus der Datenbank entfernt werden?",
										  MessageBox.TYPE_YESNO, default = False)
		else:
			self.removeNewTimerFromDB(True)

	def removeNewTimerFromDB(self, answer):
		if answer:
			current_time = int(time.time())
			timers = self.database.getAllTimer(current_time)
			for timer in timers:
				(serie, staffel, episode, title, start_time, stbRef, webChannel, eit, activeTimer) = timer
				self.removeTimer(serie, staffel, episode, title, start_time, webChannel, eit)

			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Alle noch ausstehenden Timer wurden entfernt.")
		else:
			return

	def removeOldTimerFromDB(self, answer):
		if answer:
			self.database.removeAllOldTimer()
			self.database.rebuild()

			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Alle alten Timer wurden entfernt.")
		else:
			return

	def dropAllTimer(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeOldTimerFromDB, MessageBox,
										  "Sollen wirklich alle alten Timer aus der Datenbank entfernt werden?", MessageBox.TYPE_YESNO,
										  default=False)
		else:
			self.removeOldTimerFromDB(True)
			
	def getCover(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_id = None
		url = self.database.getMarkerURL(serien_name)
		if url:
			serien_id = getSeriesIDByURL(url)
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)
			
	def keyLeft(self):
		self['menu_list'].pageUp()
		self.getCover()

	def keyRight(self):
		self['menu_list'].pageDown()
		self.getCover()

	def keyDown(self):
		self['menu_list'].down()
		self.getCover()

	def keyUp(self):
		self['menu_list'].up()
		self.getCover()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if config.plugins.serienRec.refreshViews.value:
			self.close(self.changesMade)
		else:
			self.close(False)

class serienRecRunAutoCheck(Screen, HelpableScreen):
	def __init__(self, session, manuell=True, tvplaner_manuell=False):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell
		print "0__init__ tvplaner_manuell:", tvplaner_manuell
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
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
		self.logliste = []
		self.points = ""

		self.timer_default = eTimer()
		if isDreamOS():
			self.timer_default_conn = self.timer_default.timeout.connect(self.realStartCheck)
		else:
			self.timer_default.callback.append(self.realStartCheck)

		self.onLayoutFinish.append(self.startCheck)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)
		
		self['text_red'].setText("Abbrechen")
		self.num_bt_text[0][0] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na
			
		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			self.num_bt_text[1][2] = buttonText_na
			Skin1_Settings(self)
		else:
			self.num_bt_text[1][2] = ""

			self.displayMode = 2
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
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		if config.plugins.serienRec.logWrapAround.value:
			self.chooseMenuList.l.setItemHeight(int(70*skinFactor))
		else:
			self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['log'] = self.chooseMenuList
		self['log'].show()

		self['title'].setText("Suche nach neuen Timern läuft.")
		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_exit'].show()
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
		
	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.startCheck()

	def startCheck(self):
		# Log Reload Timer
		print "startCheck timer"
		self.readLogTimer = eTimer()
		if isDreamOS():
			self.readLogTimer_conn = self.readLogTimer.timeout.connect(self.readLog)
		else:
			self.readLogTimer.callback.append(self.readLog)
		global autoCheckFinished
		autoCheckFinished = False
		self.readLogTimer.start(2500)
		self.readLog()
		self.timer_default.start(0)

	def realStartCheck(self):
		self.timer_default.stop()
		if self.manuell:
			print "realStartCheck"
			global autoCheckFinished
			autoCheckFinished = False
			serienRecCheckForRecording(self.session, True, self.tvplaner_manuell)

	def readLog(self):
		print "readLog called"
		global autoCheckFinished
		if autoCheckFinished or not self.manuell:
			if self.readLogTimer:
				self.readLogTimer.stop()
				self.readLogTimer = None
			print "[SerienRecorder] update log reader stopped."
			self['title'].setText("Auto-Check fertig !")
			readLog = open(logFile, "r")
			for zeile in readLog.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					self.logliste.append(zeile)
			readLog.close()
			self.chooseMenuList.setList(map(self.buildList, self.logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self['config'].moveToIndex(int(count-1))
		else:
			print "[SerienRecorder] waiting"
			self.points += " ."
			self['title'].setText("Suche nach neuen Timern läuft.%s" % self.points)
					
	@staticmethod
	def buildList(entry):
		(zeile) = entry
		width = 850
		if config.plugins.serienRec.SkinType.value == "":
			width = 1240

		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, width * skinFactor, 65 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 2 * skinFactor, width * skinFactor, 20 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]

	def pageUp(self):
		self['log'].pageUp()

	def pageDown(self):
		self['log'].pageDown()
		
	def __onClose(self):
		print "[SerienRecorder] update log reader stopped."
		if self.readLogTimer:
			self.readLogTimer.stop()
			self.readLogTimer = None
			
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		global autoCheckFinished
		if autoCheckFinished:
			self.close(self.manuell and config.plugins.serienRec.refreshViews.value)

		
#---------------------------------- Marker Functions ------------------------------------------

class serienRecAddSerie(Screen, HelpableScreen):
	def __init__(self, session, serien_name):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.ErrorMsg = "unbekannt"
		self.serienlist = []
		self.skin = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Marker für ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "zurück zur vorherigen Ansicht"),
			"blue"  : (self.keyBlue, "Serie manuell suchen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.loading = True

		self.onLayoutFinish.append(self.searchSerie)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Abbrechen")
		self['text_ok'].setText("Marker hinzufügen")
		self['text_blue'].setText("Suche wiederholen")

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()
		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_ok'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()
			
			self['text_red'].show()
			self['text_ok'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_id = self['menu_list'].getCurrent()[0][2]
		serien_name = self['menu_list'].getCurrent()[0][0]

		self.session.open(serienRecShowInfo, serien_name, serien_id)
		#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
		#			  MessageBox.TYPE_INFO, timeout=10)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return
				
			check = self['menu_list'].getCurrent()
			if check is None:
				return
				
			serien_name = self['menu_list'].getCurrent()[0][0]
			print "[SerienRecorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][0]
			print "[SerienRecorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.searchSerie()

	def searchSerie(self, start = 0):
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche nach ' %s '" % self.serien_name)
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		if start == 0:
			self.serienlist = []

		searchResults = downloadSearchResults(self.serien_name, start)
		searchResults.start()
		searchResults.join()

		self.results(searchResults.getData())

	def results(self, serienlist):
		(startOffset, moreResults, searchResults) = serienlist
		self.serienlist.extend(searchResults)
		self['title'].setText("Die Suche für ' %s ' ergab %s Teffer." % (self.serien_name, str(len(self.serienlist))))
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		# deep copy list
		resultList = self.serienlist[:]

		if moreResults > 0:
			resultList.append(("", "", ""))
			resultList.append(("=> Weitere Ergebnisse laden?", str(moreResults), "-1"))
		self.chooseMenuList.setList(map(self.buildList, resultList))
		self['menu_list'].moveToIndex(startOffset)
		self.loading = False
		self.getCover()

	@staticmethod
	def buildList(entry):
		(name_Serie, year_Serie, id_Serie) = entry

		# weitere Ergebnisse Eintrag
		if id_Serie == "-1":
			year_Serie = ""

		#name_Serie = doReplaces(name_Serie)

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 350 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name_Serie),
			(eListboxPythonMultiContent.TYPE_TEXT, 450 * skinFactor, 0, 350 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, year_Serie)
			]

	def keyOK(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] keine infos gefunden"
			return

		Serie = self['menu_list'].getCurrent()[0][0]
		Year = self['menu_list'].getCurrent()[0][1]
		Id = self['menu_list'].getCurrent()[0][2]
		print Serie, Year, Id

		if Id == "":
			return

		if Id == "-1":
			self.chooseMenuList.setList([])
			self.searchSerie(int(Year))
			return

		self.serien_name = ""
		database = SRDatabase(serienRecDataBaseFilePath)
		if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
			boxID = None
		else:
			boxID = config.plugins.serienRec.BoxID.value
		url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(Id)
		if database.addMarker(url, Serie, boxID):
			writeLog("\nSerien Marker für ' %s ' wurde angelegt" % Serie, True)
			self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % Serie)
			self['title'].instance.setForegroundColor(parseColor("green"))
			if config.plugins.serienRec.openMarkerScreen.value:
				self.close(Serie)
		else:
			self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % Serie)
			self['title'].instance.setForegroundColor(parseColor("red"))

	def keyRed(self):
		self.close()

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:", text = self.serien_name)

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.chooseMenuList.setList([])
			self['title'].setText("")
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.serien_name = serien_name
			self.serienlist = []
			self.searchSerie()

	def keyLeft(self):
		self['menu_list'].pageUp()
		self.getCover()

	def keyRight(self):
		self['menu_list'].pageDown()
		self.getCover()

	def keyDown(self):
		self['menu_list'].down()
		self.getCover()

	def keyUp(self):
		self['menu_list'].up()
		self.getCover()

	def getCover(self):
		if self.loading:
			return
		
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_id = self['menu_list'].getCurrent()[0][2]
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		self.close()

#---------------------------------- Setup Functions ------------------------------------------

class serienRecSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, readConfig=False):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"	: (self.keyOK, "Fenster für Verzeichnisauswahl öffnen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"red"	: (self.keyRed, "alle Einstellungen auf die Standardwerte zurücksetzen"),
			"green"	: (self.save, "Einstellungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "Einstellungen in Datei speichern"),
			"blue"  : (self.keyBlue, "Einstellungen aus Datei laden"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"startTeletext" : (self.showAbout, "Über dieses Plugin"),
			"menu"	: (self.openChannelSetup, "Sender zuordnen"),
			#"deleteForward" : (self.keyDelForward, "---"),
			#"deleteBackward": (self.keyDelBackward, "---"),
			"nextBouquet":	(self.bouquetPlus, "zur vorherigen Seite blättern"),
			"prevBouquet":	(self.bouquetMinus, "zur nächsten Seite blättern"),
			#"8"	: (self.imaptest, "Testet die IMAP Einstellungen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		if readConfig:
			ReadConfigFile()

		self.setupSkin()
		#global showAllButtons
		#if showAllButtons:
		#	Skin1_Settings(self)

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

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		if config.plugins.serienRec.setupType.value == "1":
			self['config_information_text'].setText(self.HilfeTexte[config.plugins.serienRec.BoxID][0])
		else:
			self['config_information_text'].setText(self.HilfeTexte[config.plugins.serienRec.setupType][0])
			
		#config.plugins.serienRec.showAdvice.value = True
		if config.plugins.serienRec.showAdvice.value:
			self.onShown.append(self.showAdvice)
		self.onLayoutFinish.append(self.setSkinProperties)
		
	def showAdvice(self):
		self.onShown.remove(self.showAdvice)
		self.session.openWithCallback(self.switchOffAdvice, MessageBox, ("Hinweis:\n"
										"Zusätzliche Informationen zu den Einstellungen erhalten Sie durch langes Drücken der Taste 'HILFE'.\n"
										"Es wird dann die entsprechenden Stelle in der Bedienungsanleitung angezeigt.\n"
										"\n"
										"Diesen Hinweis nicht mehr anzeigen:\n"), MessageBox.TYPE_YESNO, default = False)
										
	def switchOffAdvice(self, answer=False):
		if answer:
			config.plugins.serienRec.showAdvice.value = False
		config.plugins.serienRec.showAdvice.save()
		configfile.save()
		
	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)
		
		self['config'] = ConfigList([])
		self['config'].show()

		self['config_information'].show()
		self['config_information_text'].show()

		self['title'].setText("SerienRecorder - Einstellungen:")
		self['text_red'].setText("Defaultwerte")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Ordner auswählen")
		self['text_yellow'].setText("in Datei speichern")
		self['text_blue'].setText("aus Datei laden")
		self['text_menu'].setText("Sender zuordnen")

		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_green'].show()
			#self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			#self['bt_8'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			#self['text_ok'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, "Hilfe"],
								[buttonText_na, buttonText_na, "Sender zuordnen"])



	def showManual(self):
		if OperaBrowserInstalled:
			if self['config'].getCurrent()[1] in self.HilfeTexte:
				self.session.open(Browser, ("%s#%s") % (SR_OperatingManual.replace(".html", "_kapitel_01.html"), self.HilfeTexte[self['config'].getCurrent()[1]][1]), True)
			else:
				self.session.open(Browser, ("%s#1.3_Die_globalen_Einstellungen") % SR_OperatingManual.replace(".html", "_kapitel_01.html"), True)
		elif DMMBrowserInstalled:
			if self['config'].getCurrent()[1] in self.HilfeTexte:
				self.session.open(Browser, True, ("%s#%s") % (SR_OperatingManual.replace(".html", "_kapitel_01.html"), self.HilfeTexte[self['config'].getCurrent()[1]][1]))
			else:
				self.session.open(Browser, True, ("%s#1.3_Die_globalen_Einstellungen") % SR_OperatingManual.replace(".html", "_kapitel_01.html"))
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

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
			#self.save()
		
	def keyYellow(self):
		config.plugins.serienRec.save()
		saveEnigmaSettingsToFile()
		self.session.open(MessageBox, "Die aktuelle Konfiguration wurde in der Datei 'Config.backup' \nim Verzeichnis '%s' gespeichert." % serienRecMainPath, MessageBox.TYPE_INFO, timeout = 10)
		
	def keyBlue(self):
		self.session.openWithCallback(self.importSettings, MessageBox, "Die Konfiguration aus der Datei 'Config.backup' \nim Verzeichnis '%s' wird geladen." % serienRecMainPath, MessageBox.TYPE_YESNO, default = False)

	def importSettings(self, answer=False):
		if answer:
			writeSettings = open("/etc/enigma2/settings_new", "w")
			
			readSettings = open("/etc/enigma2/settings", "r")
			for rawData in readSettings.readlines():
				data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
				if not data:
					writeSettings.write(rawData)

			if fileExists("%sConfig.backup" % serienRecMainPath):
				readConfFile = open("%sConfig.backup" % serienRecMainPath, "r")
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
				self.session.open(MessageBox, "Die Datei 'Config.backup' \nim Verzeichnis '%s' wurde nicht gefunden." % serienRecMainPath, MessageBox.TYPE_INFO, timeout = 10)

	def bouquetPlus(self):
		self['config'].instance.moveSelection(self['config'].instance.pageUp)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]][0]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.tvplaner_movies_filepath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def bouquetMinus(self):
		self['config'].instance.moveSelection(self['config'].instance.pageDown)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]][0]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.tvplaner_movies_filepath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyDown(self):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.updateInterval:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.checkfordays:
			x = int(config.plugins.serienRec.TimeSpanForRegularTimer.value)
			config.plugins.serienRec.TimeSpanForRegularTimer = ConfigInteger(7, (int(config.plugins.serienRec.checkfordays.value),999))
			if int(config.plugins.serienRec.checkfordays.value) > x:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = int(config.plugins.serienRec.checkfordays.value)
			else:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = x
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_mail_age:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_check_interval:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_server_port:
			self.changedEntry()
		
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]][0]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.tvplaner_movies_filepath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyUp(self):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.updateInterval:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.checkfordays:
			x = int(config.plugins.serienRec.TimeSpanForRegularTimer.value)
			config.plugins.serienRec.TimeSpanForRegularTimer = ConfigInteger(7, (int(config.plugins.serienRec.checkfordays.value),999))
			if int(config.plugins.serienRec.checkfordays.value) > x:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = int(config.plugins.serienRec.checkfordays.value)
			else:
				config.plugins.serienRec.TimeSpanForRegularTimer.value = x
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_mail_age:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_check_interval:
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.imap_server_port:
			self.changedEntry()
			
		if self['config'].instance.getCurrentIndex() <= 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]][0]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.tvplaner_movies_filepath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		if self['config'].getCurrent()[1] == config.plugins.serienRec.autochecktype:
			if config.plugins.serienRec.autochecktype.value == "0":
				config.plugins.serienRec.updateInterval.setValue(0)
			else:
				config.plugins.serienRec.updateInterval.setValue(24)
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.setupType:
			self.changedEntry()
			self['config'].instance.moveSelectionTo(int(config.plugins.serienRec.setupType.value) + 1)
		else:
			if self['config'].getCurrent()[1] == config.plugins.serienRec.forceRecording:
				self.setInfoText()
			if self['config'].getCurrent()[1] not in (config.plugins.serienRec.setupType,
													  config.plugins.serienRec.savetopath,
													  config.plugins.serienRec.tvplaner_movies_filepath,
													  config.plugins.serienRec.seasonsubdirnumerlength,
													  config.plugins.serienRec.coverPath,
													  config.plugins.serienRec.BackupPath,
													  config.plugins.serienRec.deleteBackupFilesOlderThan,
													  #config.plugins.serienRec.updateInterval,
													  config.plugins.serienRec.deltime,
													  config.plugins.serienRec.maxDelayForAutocheck,
													  config.plugins.serienRec.imap_server,
													  config.plugins.serienRec.imap_server_port,
													  config.plugins.serienRec.imap_login,
													  config.plugins.serienRec.imap_password,
													  config.plugins.serienRec.imap_mailbox,
													  config.plugins.serienRec.imap_mail_subject,
													  config.plugins.serienRec.imap_check_interval,
													  #config.plugins.serienRec.maxWebRequests,
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
													  config.plugins.serienRec.deleteOlderThan,
													  config.plugins.serienRec.NoOfRecords,
													  config.plugins.serienRec.tuner):
				self.changedEntry()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		if self['config'].getCurrent()[1] == config.plugins.serienRec.autochecktype:
			if config.plugins.serienRec.autochecktype.value == "0":
				config.plugins.serienRec.updateInterval.setValue(0)
			else:
				config.plugins.serienRec.updateInterval.setValue(24)
			self.changedEntry()
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.setupType:
			self.changedEntry()
			self['config'].instance.moveSelectionTo(int(config.plugins.serienRec.setupType.value) + 1)
		else:
			if self['config'].getCurrent()[1] == config.plugins.serienRec.forceRecording:
				self.setInfoText()
			if self['config'].getCurrent()[1] not in (config.plugins.serienRec.savetopath,
													  config.plugins.serienRec.tvplaner_movies_filepath,
													  config.plugins.serienRec.seasonsubdirnumerlength,
													  config.plugins.serienRec.coverPath,
													  config.plugins.serienRec.BackupPath,
													  config.plugins.serienRec.deleteBackupFilesOlderThan,
													  #config.plugins.serienRec.updateInterval,
													  config.plugins.serienRec.deltime,
													  config.plugins.serienRec.maxDelayForAutocheck,
													  #config.plugins.serienRec.maxWebRequests,
													  config.plugins.serienRec.imap_server,
													  config.plugins.serienRec.imap_server_port,
													  config.plugins.serienRec.imap_login,
													  config.plugins.serienRec.imap_password,
													  config.plugins.serienRec.imap_mailbox,
													  config.plugins.serienRec.imap_mail_subject,
													  config.plugins.serienRec.imap_check_interval,
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
													  config.plugins.serienRec.deleteOlderThan,
													  config.plugins.serienRec.NoOfRecords,
													  config.plugins.serienRec.tuner):
				self.changedEntry()

	def createConfigList(self):
		self.list = []
		self.list.append(getConfigListEntry("---------  SYSTEM:  -------------------------------------------------------------------------------------------", ConfigNothing()))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("ID der Box:", config.plugins.serienRec.BoxID))
			self.list.append(getConfigListEntry("Neue Serien-Marker nur auf dieser Box aktivieren:", config.plugins.serienRec.activateNewOnThisSTBOnly))
		self.list.append(getConfigListEntry("Umfang der Einstellungen:", config.plugins.serienRec.setupType))
		self.list.append(getConfigListEntry("Speicherort der Serienaufnahmen:", config.plugins.serienRec.savetopath))
		self.list.append(getConfigListEntry("Serien-Verzeichnis anlegen:", config.plugins.serienRec.seriensubdir))
		if config.plugins.serienRec.seriensubdir.value:
			self.list.append(getConfigListEntry("Staffel-Verzeichnis anlegen:", config.plugins.serienRec.seasonsubdir))
			if config.plugins.serienRec.seasonsubdir.value:
				self.list.append(getConfigListEntry("    Mindestlänge der Staffelnummer im Verzeichnisnamen:", config.plugins.serienRec.seasonsubdirnumerlength))
				self.list.append(getConfigListEntry("    Füllzeichen für Staffelnummer im Verzeichnisnamen:", config.plugins.serienRec.seasonsubdirfillchar))
		#self.list.append(getConfigListEntry("Anzahl gleichzeitiger Web-Anfragen:", config.plugins.serienRec.maxWebRequests))
		self.list.append(getConfigListEntry("Automatisches Plugin-Update:", config.plugins.serienRec.Autoupdate))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("Speicherort der Datenbank:", config.plugins.serienRec.databasePath))
			self.list.append(getConfigListEntry("Erstelle Backup:", config.plugins.serienRec.AutoBackup))
			if config.plugins.serienRec.AutoBackup.value != "0":
				self.list.append(getConfigListEntry("    Speicherort für Backup:", config.plugins.serienRec.BackupPath))
				self.list.append(getConfigListEntry("    Backup-Dateien löschen die älter als x Tage sind:", config.plugins.serienRec.deleteBackupFilesOlderThan))

		self.list.append(getConfigListEntry("", ConfigNothing()))
		self.list.append(getConfigListEntry("---------  AUTO-CHECK:  ---------------------------------------------------------------------------------------", ConfigNothing()))
		#self.list.append(getConfigListEntry("Intervall für autom. Suchlauf (in Std.) (00 = kein autom. Suchlauf, 24 = nach Uhrzeit):", config.plugins.serienRec.updateInterval)) #3600000
		#self.list.append(getConfigListEntry("Intervall für autom. Suchlauf (Std.) (00 = keiner, 24 = nach Uhrzeit):", config.plugins.serienRec.updateInterval)) #3600000
		self.list.append(getConfigListEntry("Automatischen Suchlauf ausführen:", config.plugins.serienRec.autochecktype))
		if config.plugins.serienRec.autochecktype.value == "1":
			if config.plugins.serienRec.updateInterval.value == 24:
				self.list.append(getConfigListEntry("    Uhrzeit für automatischen Suchlauf:", config.plugins.serienRec.deltime))
				self.list.append(getConfigListEntry("    maximale Verzögerung für automatischen Suchlauf (Min.):", config.plugins.serienRec.maxDelayForAutocheck))
#		self.list.append(getConfigListEntry("Lese Daten aus Dateien mit den Daten der Serienwebseite", config.plugins.serienRec.readdatafromfiles))
		self.list.append(getConfigListEntry("Wunschliste TV-Planer E-Mails nutzen:", config.plugins.serienRec.tvplaner))
		if config.plugins.serienRec.tvplaner.value:
			self.list.append(getConfigListEntry("    IMAP Server:", config.plugins.serienRec.imap_server))
			self.list.append(getConfigListEntry("    IMAP Server SSL:", config.plugins.serienRec.imap_server_ssl))
			self.list.append(getConfigListEntry("    IMAP Server Port:", config.plugins.serienRec.imap_server_port))
			self.list.append(getConfigListEntry("    IMAP Login:", config.plugins.serienRec.imap_login))
			self.list.append(getConfigListEntry("    IMAP Passwort:", config.plugins.serienRec.imap_password))
			self.list.append(getConfigListEntry("    IMAP Mailbox:", config.plugins.serienRec.imap_mailbox))
			self.list.append(getConfigListEntry("    TV-Planer Subject:", config.plugins.serienRec.imap_mail_subject))
			self.list.append(getConfigListEntry("    maximales Alter der E-Mail (Tage):", config.plugins.serienRec.imap_mail_age))
#			self.list.append(getConfigListEntry("    Neue Serien Marker erzeugen:", config.plugins.serienRec.tvplaner_create_marker))
#			self.list.append(getConfigListEntry("    Mailbox alle <n> Minuten überprüfen:", config.plugins.serienRec.imap_check_interval))
			self.list.append(getConfigListEntry("    Voller Suchlauf mindestens einmal im Erstellungszeitraum:", config.plugins.serienRec.tvplaner_full_check))
			self.list.append(getConfigListEntry("    Timer nur aus der TV-Planer E-Mail anlegen:", config.plugins.serienRec.tvplaner_skipSerienServer))
			self.list.append(getConfigListEntry("    Timer für Serien anlegen:", config.plugins.serienRec.tvplaner_series))
			if config.plugins.serienRec.tvplaner_series.value:
				self.list.append(getConfigListEntry("        Neue TV-Planer Serien nur auf dieser Box aktivieren:", config.plugins.serienRec.tvplaner_series_activeSTB))
			self.list.append(getConfigListEntry("    Timer für Filme anlegen:", config.plugins.serienRec.tvplaner_movies))
			if config.plugins.serienRec.tvplaner_movies.value:
				self.list.append(getConfigListEntry("        Neue TV-Planer Filme nur auf dieser Box aktivieren:", config.plugins.serienRec.tvplaner_movies_activeSTB))
				self.list.append(getConfigListEntry("        Speicherort für Filme:", config.plugins.serienRec.tvplaner_movies_filepath))
				self.list.append(getConfigListEntry("        Unterverzeichnis für jeden Film:", config.plugins.serienRec.tvplaner_movies_createsubdir))
		self.list.append(getConfigListEntry("Timer für X Tage erstellen:", config.plugins.serienRec.checkfordays))
		if config.plugins.serienRec.setupType.value == "1":
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
			if not isDreamOS():
				self.list.append(getConfigListEntry("nach Änderungen Suchlauf beim Beenden starten:", config.plugins.serienRec.runAutocheckAtExit))
		#if config.plugins.serienRec.updateInterval.value == 24:
		if config.plugins.serienRec.autochecktype.value == "1":
			self.list.append(getConfigListEntry("Aus Deep-Standby aufwecken:", config.plugins.serienRec.wakeUpDSB))
		if config.plugins.serienRec.autochecktype.value in ("1", "2"):
			self.list.append(getConfigListEntry("Aktion nach dem automatischen Suchlauf:", config.plugins.serienRec.afterAutocheck))
			if config.plugins.serienRec.setupType.value == "1":
				if int(config.plugins.serienRec.afterAutocheck.value):
					self.list.append(getConfigListEntry("    Timeout für (Deep-)Standby-Abfrage (in Sek.):", config.plugins.serienRec.DSBTimeout))
			
		self.list.append(getConfigListEntry("", ConfigNothing()))
		self.list.append(getConfigListEntry("---------  TIMER:  --------------------------------------------------------------------------------------------", ConfigNothing()))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("Timer-Art:", self.kindOfTimer))
			self.list.append(getConfigListEntry("Nach dem Event:", config.plugins.serienRec.afterEvent))
		self.list.append(getConfigListEntry("Timervorlauf (in Min.):", config.plugins.serienRec.margin_before))
		self.list.append(getConfigListEntry("Timernachlauf (in Min.):", config.plugins.serienRec.margin_after))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("Timername:", config.plugins.serienRec.TimerName))
			self.list.append(getConfigListEntry("Manuelle Timer immer erstellen:", config.plugins.serienRec.forceManualRecording))
			self.list.append(getConfigListEntry("Event-Programmierungen behandeln:", config.plugins.serienRec.splitEventTimer))

		tvbouquets = STBHelpers.getTVBouquets()
		if len(tvbouquets) < 2:
			config.plugins.serienRec.selectBouquets.value = False
		else:
			if config.plugins.serienRec.setupType.value == "1":
				self.list.append(getConfigListEntry("Bouquets auswählen:", config.plugins.serienRec.selectBouquets))
			if config.plugins.serienRec.selectBouquets.value:
				self.getTVBouquetSelection()
				if config.plugins.serienRec.setupType.value == "1":
					self.list.append(getConfigListEntry("    Standard Bouquet:", config.plugins.serienRec.MainBouquet))
					self.list.append(getConfigListEntry("    Alternatives Bouquet:", config.plugins.serienRec.AlternativeBouquet))
					self.list.append(getConfigListEntry("    Verwende alternative Sender bei Konflikten:", config.plugins.serienRec.useAlternativeChannel))
		
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("", ConfigNothing()))
			self.list.append(getConfigListEntry("---------  OPTIMIERUNGEN:  ------------------------------------------------------------------------------------", ConfigNothing()))
			self.list.append(getConfigListEntry("Intensive Suche nach angelegten Timern:", config.plugins.serienRec.intensiveTimersuche))
			self.list.append(getConfigListEntry("Zeige ob die Episode als Aufnahme auf der HDD ist:", config.plugins.serienRec.sucheAufnahme))
			self.list.append(getConfigListEntry("", ConfigNothing()))
			self.list.append(getConfigListEntry("---------  GUI:  ----------------------------------------------------------------------------------------------", ConfigNothing()))
			self.list.append(getConfigListEntry("Skin:", config.plugins.serienRec.SkinType))
			global showAllButtons
			if config.plugins.serienRec.SkinType.value not in ("", "Skin2", "AtileHD", "StyleFHD", "Black Box"):
				self.list.append(getConfigListEntry("    werden bei diesem Skin immer ALLE Tasten angezeigt:", config.plugins.serienRec.showAllButtons))
				showAllButtons = config.plugins.serienRec.showAllButtons.value
			elif config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
				showAllButtons = False
			else:
				showAllButtons = True
			if not showAllButtons:
				self.list.append(getConfigListEntry("    Wechselzeit der Tastenanzeige (Sek.):", config.plugins.serienRec.DisplayRefreshRate))
			self.list.append(getConfigListEntry("Starte Plugin mit:", config.plugins.serienRec.firstscreen))
			self.list.append(getConfigListEntry("Zeige Picons:", config.plugins.serienRec.showPicons))
			if config.plugins.serienRec.showPicons.value:
				self.list.append(getConfigListEntry("    Verzeichnis mit Picons:", config.plugins.serienRec.piconPath))
			self.list.append(getConfigListEntry("Cover herunterladen:", config.plugins.serienRec.downloadCover))
			if config.plugins.serienRec.downloadCover.value:
				self.list.append(getConfigListEntry("    Speicherort der Cover:", config.plugins.serienRec.coverPath))
				self.list.append(getConfigListEntry("    Zeige Cover:", config.plugins.serienRec.showCover))
				self.list.append(getConfigListEntry("    Platzhalter anlegen wenn Cover nicht vorhanden:", config.plugins.serienRec.createPlaceholderCover))
			self.list.append(getConfigListEntry("Korrektur der Schriftgröße in Listen:", config.plugins.serienRec.listFontsize))
			self.list.append(getConfigListEntry("Staffel-Filter in Sendetermine Ansicht:", config.plugins.serienRec.seasonFilter))
			self.list.append(getConfigListEntry("Timer-Filter in Sendetermine Ansicht:", config.plugins.serienRec.timerFilter))
			self.list.append(getConfigListEntry("Sortierung der Serien-Marker:", config.plugins.serienRec.markerSort))
			self.list.append(getConfigListEntry("Anzahl der wählbaren Staffeln im Menü Serien-Marker:", config.plugins.serienRec.max_season))
			self.list.append(getConfigListEntry("Öffne Marker-Ansicht nach Hinzufügen neuer Marker:", config.plugins.serienRec.openMarkerScreen))
			self.list.append(getConfigListEntry("Vor Löschen in Serien-Marker und Timer-Liste Benutzer fragen:", config.plugins.serienRec.confirmOnDelete))
			self.list.append(getConfigListEntry("Benachrichtigung beim Suchlauf:", config.plugins.serienRec.showNotification))
			self.list.append(getConfigListEntry("Benachrichtigung bei Timerkonflikten:", config.plugins.serienRec.showMessageOnConflicts))
			self.list.append(getConfigListEntry("Screens bei Änderungen sofort aktualisieren:", config.plugins.serienRec.refreshViews))


		self.list.append(getConfigListEntry("", ConfigNothing()))
		self.list.append(getConfigListEntry("---------  LOG:  ----------------------------------------------------------------------------------------------", ConfigNothing()))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("Speicherort für Log-Datei:", config.plugins.serienRec.LogFilePath))
			self.list.append(getConfigListEntry("Log-Dateiname mit Datum/Uhrzeit:", config.plugins.serienRec.longLogFileName))
			if config.plugins.serienRec.longLogFileName.value:
				self.list.append(getConfigListEntry("    Log-Dateien löschen die älter als x Tage sind:", config.plugins.serienRec.deleteLogFilesOlderThan))
		self.list.append(getConfigListEntry("DEBUG LOG aktivieren:", config.plugins.serienRec.writeLog))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("DEBUG LOG - STB Informationen:", config.plugins.serienRec.writeLogVersion))
			self.list.append(getConfigListEntry("DEBUG LOG - Senderliste:", config.plugins.serienRec.writeLogChannels))
			self.list.append(getConfigListEntry("DEBUG LOG - Episoden:", config.plugins.serienRec.writeLogAllowedEpisodes))
			self.list.append(getConfigListEntry("DEBUG LOG - Added:", config.plugins.serienRec.writeLogAdded))
			self.list.append(getConfigListEntry("DEBUG LOG - Festplatte:", config.plugins.serienRec.writeLogDisk))
			self.list.append(getConfigListEntry("DEBUG LOG - Tageszeit:", config.plugins.serienRec.writeLogTimeRange))
			self.list.append(getConfigListEntry("DEBUG LOG - Zeitbegrenzung:", config.plugins.serienRec.writeLogTimeLimit))
			self.list.append(getConfigListEntry("DEBUG LOG - Timer Debugging:", config.plugins.serienRec.writeLogTimerDebug))
			self.list.append(getConfigListEntry("DEBUG LOG - Scroll zum Ende:", config.plugins.serienRec.logScrollLast))
			self.list.append(getConfigListEntry("DEBUG LOG - Anzeige mit Zeilenumbruch:", config.plugins.serienRec.logWrapAround))

	def getTVBouquetSelection(self):
		self.bouquetList = []
		tvbouquets = STBHelpers.getTVBouquets()
		for bouquet in tvbouquets:
			self.bouquetList.append((bouquet[1], bouquet[1]))

		config.plugins.serienRec.MainBouquet.setChoices(choices = self.bouquetList, default = self.bouquetList[0][0])
		config.plugins.serienRec.AlternativeBouquet.setChoices(choices = self.bouquetList, default = self.bouquetList[1][0])
		
	def changedEntry(self, dummy=False):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyOK(self):
		ConfigListScreen.keyOK(self)
		if self['config'].getCurrent()[1] == config.plugins.serienRec.savetopath:
			#start_dir = "/media/hdd/movie/"
			start_dir = config.plugins.serienRec.savetopath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Aufnahme-Verzeichnis für Serien auswählen")
		if self['config'].getCurrent()[1] == config.plugins.serienRec.tvplaner_movies_filepath:
			#start_dir = "/media/hdd/movie/"
			start_dir = config.plugins.serienRec.tvplaner_movies_filepath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Aufnahme-Verzeichnis für Filme auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
			start_dir = config.plugins.serienRec.LogFilePath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "LogFile-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.BackupPath:
			start_dir = config.plugins.serienRec.BackupPath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Backup-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.databasePath:
			start_dir = config.plugins.serienRec.databasePath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Datenbank-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.coverPath:
			start_dir = config.plugins.serienRec.coverPath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Cover-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.piconPath:
			start_dir = config.plugins.serienRec.piconPath.value
			self.session.openWithCallback(self.selectedMediaFile, serienRecFileList, start_dir, "Picon-Verzeichnis auswählen")
			
	def selectedMediaFile(self, res):
		if res is not None:
			if self['config'].getCurrent()[1] == config.plugins.serienRec.savetopath:
				print res
				config.plugins.serienRec.savetopath.value = res
				self.changedEntry()
			if self['config'].getCurrent()[1] == config.plugins.serienRec.tvplaner_movies_filepath:
				print res
				config.plugins.serienRec.tvplaner_movies_filepath.value = res
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
				print res
				config.plugins.serienRec.LogFilePath.value = res
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.BackupPath:
				print res
				config.plugins.serienRec.BackupPath.value = res
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.databasePath:
				print res
				config.plugins.serienRec.databasePath.value = res
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.coverPath:
				print res
				config.plugins.serienRec.coverPath.value = res
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.piconPath:
				print res
				config.plugins.serienRec.piconPath.value = res
				self.changedEntry()

	def setInfoText(self):
		lt = time.localtime()
		self.HilfeTexte = {
			config.plugins.serienRec.BoxID :                   ("Die ID (Nummer) der STB. Läuft der SerienRecorder auf mehreren Boxen, die alle auf die selbe Datenbank (im Netzwerk) zugreifen, "
																"können einzelne Marker über diese ID für jede Box einzeln aktiviert oder deaktiviert werden. Timer werden dann nur auf den Boxen erstellt, "
																"für die der Marker aktiviert ist.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.activateNewOnThisSTBOnly: ("Bei 'ja' werden neue Serien-Marker nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.setupType :               ("Hier kann die Komplexität des Einstellungs-Menüs eingestellt werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.savetopath :              ("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von Serien gespeichert werden.", "Speicherort_der_Aufnahme"),
			config.plugins.serienRec.seriensubdir :            ("Bei 'ja' wird für jede Serien ein eigenes Unterverzeichnis (z.B.\n'%s<Serien_Name>/') für die Aufnahmen erstellt." % config.plugins.serienRec.savetopath.value, "Serien_Verzeichnis_anlegen"),
			config.plugins.serienRec.seasonsubdir :            ("Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis (z.B.\n"
																"'%s<Serien_Name>/Season %s') erstellt." % (config.plugins.serienRec.savetopath.value, str("1").zfill(config.plugins.serienRec.seasonsubdirnumerlength.value)), "Staffel_Verzeichnis_anlegen"),
			config.plugins.serienRec.seasonsubdirnumerlength : ("Die Anzahl der Stellen, auf die die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.seasonsubdirfillchar :    ("Auswahl, ob die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.deltime :                 ("Uhrzeit, zu der der automatische Timer-Suchlauf täglich ausgeführt wird (%s:%s Uhr)." % (str(config.plugins.serienRec.deltime.value[0]).zfill(2), str(config.plugins.serienRec.deltime.value[1]).zfill(2)), "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.maxDelayForAutocheck :    ("Hier wird die Zeitspanne (in Minuten) eingestellt, innerhalb welcher der automatische Timer-Suchlauf ausgeführt wird. Diese Zeitspanne beginnt zu der oben eingestellten Uhrzeit.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.Autoupdate :              ("Bei 'ja' wird bei jedem Start des SerienRecorders nach verfügbaren Updates gesucht.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.tvplaner :                ("Bei 'ja' ruft der SerienRecorder regelmäßig eine IMAP Mailbox ab und sucht nach E-Mails des Wunschliste TV-Planers", ""),
			config.plugins.serienRec.imap_server :             ("Name des IMAP Servers (z.B. imap.gmx.de)", ""),
			config.plugins.serienRec.imap_server_ssl :         ("Zugriff über SSL (Port ohne SSL = 143, Port mit SSL = 993", ""),
			config.plugins.serienRec.imap_server_port :        ("Portnummer für den Zugriff", ""),
			config.plugins.serienRec.imap_login :              ("Benutzername des IMAP Accounts (z.B. abc@gmx.de)", ""),
			config.plugins.serienRec.imap_password :           ("Passwort des IMAP Accounts", ""),
			config.plugins.serienRec.imap_mailbox :            ("Name des Ordners in dem die E-Mails ankommen (z.B. INBOX)", ""),
			config.plugins.serienRec.imap_mail_subject :       ("Betreff der TV-Planer E-Mails (default: TV Wunschliste TV-Planer)", ""),
			config.plugins.serienRec.imap_check_interval :     ("Die Mailbox wird alle <n> Minuten überprüft (default: 30)", ""),
			config.plugins.serienRec.tvplaner_create_marker :  ("Bei 'ja' werden nicht vorhandene Serien Marker automatisch erzeugt", ""),
			config.plugins.serienRec.tvplaner_series :         ("Bei 'ja' werden Timer für Serien angelegt", ""),
			config.plugins.serienRec.tvplaner_series_activeSTB: ("Bei 'ja' werden neue TV-Planer Serien nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt.", ""),
			config.plugins.serienRec.tvplaner_movies :         ("Bei 'ja' werden Timer für Filme angelegt", ""),
			config.plugins.serienRec.tvplaner_movies_activeSTB: ("Bei 'ja' werden neue TV-Planer Filme nur für diese Box aktiviert, ansonsten für alle Boxen der Datenbank. Diese Option hat nur dann Auswirkungen wenn man mehrere Boxen mit einer Datenbank betreibt.", ""),
			config.plugins.serienRec.tvplaner_movies_filepath :("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von Filmen gespeichert werden.", "Speicherort_der_Aufnahme"),
			config.plugins.serienRec.tvplaner_movies_createsubdir :            ("Bei 'ja' wird für jeden Film ein eigenes Unterverzeichnis (z.B.\n'%s<Filmname>/') für die Aufnahmen erstellt." % config.plugins.serienRec.tvplaner_movies_filepath.value, ""), 	
			config.plugins.serienRec.tvplaner_full_check :     ("Bei 'ja' wird vor dem Erreichen der eingestellten Zahl von Aufnahmetagen wieder ein voller Suchlauf gestartet", ""),
			config.plugins.serienRec.tvplaner_skipSerienServer :     ("Bei 'ja' werden Timer nur aus der TV-Planer E-Mail angelegt, es werden keine Termine vom Serien-Server abgerufen.", ""),
			config.plugins.serienRec.databasePath :            ("Das Verzeichnis auswählen und/oder erstellen, in dem die Datenbank gespeichert wird.", "Speicherort_der_Datenbank"),
			config.plugins.serienRec.AutoBackup :              ("Bei 'vor dem Suchlauf' werden vor jedem Timer-Suchlauf die Datenbank des SR, die 'alte' log-Datei und die enigma2-Timer-Datei ('/etc/enigma2/timers.xml') in ein neues Verzeichnis kopiert, "
																"dessen Name sich aus dem aktuellen Datum und der aktuellen Uhrzeit zusammensetzt (z.B.\n'%s%s%s%s%s%s/').\n"
																"Bei 'nach dem Suchlauf' wird das Backup nach dem Timer-Suchlauf erstellt. Bei 'nein' wird kein Backup erstellt (nicht empfohlen)."% (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)), "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.deleteBackupFilesOlderThan: ("Backup-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht.\n\nBei '0' ist die Funktion deaktiviert.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.coverPath :               ("Das Verzeichnis auswählen und/oder erstellen, in dem die Cover gespeichert werden.", "Speicherort_der_Cover"),
			config.plugins.serienRec.BackupPath :              ("Das Verzeichnis auswählen und/oder erstellen, in dem die Backups gespeichert werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.checkfordays :            ("Es werden nur Timer für Folgen erstellt, die innerhalb der nächsten hier eingestellten Anzahl von Tagen ausgestrahlt werden \n"
																"(also bis %s)." % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400))), "Timer_Fuer_X_Tage"),
			config.plugins.serienRec.globalFromTime :          ("Die Uhrzeit, ab wann Aufnahmen erlaubt sind.\n"
																"Die erlaubte Zeitspanne beginnt um %s:%s Uhr." % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2)), "Frueheste_Zeit"),
			config.plugins.serienRec.globalToTime :            ("Die Uhrzeit, bis wann Aufnahmen erlaubt sind.\n"
																"Die erlaubte Zeitspanne endet um %s:%s Uhr." % (str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)), "Spaeteste_Zeit"),
			config.plugins.serienRec.eventid :                 ("Bei 'ja' wird versucht die Sendung anhand der Anfangs- und Endzeiten im EPG zu finden. "
																"Außerdem erfolgt bei jedem Timer-Suchlauf ein Abgleich der Anfangs- und Endzeiten aller Timer mit den EPG-Daten.\n"
																  "Diese Funktion muss aktiviert sein, wenn VPS benutzt werden soll.", "Hole_EventID"),
			config.plugins.serienRec.epgTimeSpan :                 ("Die Anzahl Minuten um die der EPG Suchzeitraum nach vorne und hinten vergrößert werden soll (Standard: 10 min).\n\n"
																"Beispiel: Eine Sendung soll laut Wunschliste um 3:20 Uhr starten, im EPG ist die Startzeit aber 3:28 Uhr, um die Sendung im EPG zu finden wird der Suchzeitraum um den eingestellten Wert "
																  "vergrößert, im Standard wird also von 3:10 Uhr bis 3:30 Uhr gesucht um die Sendung im EPG zu finden.", "Hole_EventID"),
			config.plugins.serienRec.forceRecording :          ("Bei 'ja' werden auch Timer für Folgen erstellt, die ausserhalb der erlaubten Zeitspanne (%s:%s - %s:%s) ausgestrahlt werden, "
																"falls KEINE Wiederholung innerhalb der erlaubten Zeitspanne gefunden wird. Wird eine passende Wiederholung zu einem späteren Zeitpunkt gefunden, dann wird der Timer für diese Wiederholung erstellt.\n"
																"Bei 'nein' werden ausschließlich Timer für jene Folgen erstellt, die innerhalb der erlaubten Zeitspanne liegen." % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2), str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)), "Immer_aufnehmen"),
			config.plugins.serienRec.TimeSpanForRegularTimer : ("Die Anzahl der Tage, die maximal auf eine Wiederholung gewartet wird, die innerhalb der erlaubten Zeitspanne ausgestrahlt wird. "
																"Wird keine passende Wiederholung gefunden (oder aber eine Wiederholung, die aber zu weit in der Zukunft liegt), "
																"wird ein Timer für den frühestmöglichen Termin (auch außerhalb der erlaubten Zeitspanne) erstellt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.NoOfRecords :             ("Die Anzahl der Aufnahmen, die von einer Folge gemacht werden sollen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.selectNoOfTuners :        ("Bei 'ja' wird die Anzahl der vom SR benutzten Tuner für gleichzeitige Aufnahmen begrenzt.\n"
																"Bei 'nein' werden alle verfügbaren Tuner für Timer benutzt, die Überprüfung ob noch ein weiterer Timer erzeugt werden kann, übernimmt enigma2.", "Anzahl_der_Tuner"),
			config.plugins.serienRec.tuner :                   ("Die maximale Anzahl von Tunern für gleichzeitige (sich überschneidende) Timer. Überprüft werden dabei ALLE Timer, nicht nur die vom SerienRecorder erstellten.", "Anzahl_der_Tuner"),
			config.plugins.serienRec.runAutocheckAtExit :      ("Bei 'ja' wird nach Beenden des SR automatisch ein Timer-Suchlauf ausgeführt, falls bei den Sendern und/oder Markern Änderungen vorgenommen wurden, "
																"die Einfluss auf die Erstellung neuer Timer haben. (z.B. neue Serie hinzugefügt, neuer Sender zugewiesen, etc.)", "Suchlauf_beim_Beenden"),
			config.plugins.serienRec.wakeUpDSB :               ("Bei 'ja' wird die STB vor dem automatischen Timer-Suchlauf hochgefahren, falls sie sich im Deep-Standby befindet.\n"
																"Bei 'nein' wird der automatische Timer-Suchlauf NICHT ausgeführt, wenn sich die STB im Deep-Standby befindet.", "Deep-Standby"),
			config.plugins.serienRec.afterAutocheck :          ("Hier kann ausgewählt werden, ob die STB nach dem automatischen Suchlauf in Standby oder Deep-Standby gehen soll.", "Deep-Standby"),
			config.plugins.serienRec.DSBTimeout :              ("Bevor die STB in den Deep-Standby fährt, wird für die hier eingestellte Dauer (in Sekunden) eine entsprechende Nachricht auf dem Bildschirm angezeigt. "
																"Während dieser Zeitspanne hat der Benutzer die Möglichkeit, das Herunterfahren der STB abzubrechen. Nach Ablauf dieser Zeitspanne fährt die STB automatisch in den Deep-Stanby.", "Deep-Standby"),
			self.kindOfTimer :                                 ("Es kann ausgewählt werden, wie Timer angelegt werden. Die Auswahlmöglichkeiten sind:\n"
																"  - 'aufnehmen': Ein 'normaler' Timer wird erstellt\n"
																"  - 'umschalten': Es wird ein Timer erstellt, bei dem nur auf den aufzunehmenden Sender umgeschaltet wird. Es erfolgt KEINE Aufnahme\n"
																"  - 'umschalten und aufnehmen': Es wird ein Timer erstellt, bei dem vor der Aufnahme auf den aufzunehmenden Sender umgeschaltet wird\n"
																"  - 'Erinnerung': Es wird ein Timer erstellt, bei dem lediglich eine Erinnerungs-Nachricht auf dem Bildschirm eingeblendet wird. Es wird weder umgeschaltet, noch erfolgt eine Aufnahme", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.afterEvent :              ("Es kann ausgewählt werden, was nach dem Event passieren soll. Die Auswahlmöglichkeiten sind:\n"
																"  - 'nichts': Die STB bleibt im aktuellen Zustand.\n"
																"  - 'in Standby gehen': Die STB geht in den Standby\n"
																"  - 'in Deep-Standby gehen': Die STB geht in den Deep-Standby\n"
																"  - 'automatisch': Die STB entscheidet automatisch (Standardwert)", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.margin_before :           ("Die Vorlaufzeit für Aufnahmen in Minuten.\n"
																"Die Aufnahme startet um die hier eingestellte Anzahl von Minuten vor dem tatsächlichen Beginn der Sendung", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.margin_after :            ("Die Nachlaufzeit für Aufnahmen in Minuten.\n"
																"Die Aufnahme endet um die hier eingestellte Anzahl von Minuten noch dem tatsächlichen Ende der Sendung", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.forceManualRecording :    ("Bei 'nein' erfolgt beim manuellen Anlegen von Timern in 'Sendetermine' eine Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen erreicht wurde. "
																"In diesem Fall wird der Timer NICHT angelegt, und es erfolgt ein entsprechender Eintrag im log.\n"
																"Bei 'ja' wird beim manuellen Anlegen von Timern in 'Sendetermine' die Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen vorhanden sind, "
																"ausgeschaltet. D.h. der Timer wird auf jeden Fall angelegt, sofern nicht ein Konflikt mit anderen Timern besteht.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.splitEventTimer :          ("Bei 'Nein' werden Event-Programmierungen (S01E01/1x02/1x03) als eigenständige Sendungen behandelt. "
																"Ansonsten wird versucht die einzelnen Episoden eines Events erkennen.\n\n"
																"Bei 'Timer anlegen' wird zwar weiterhin nur ein Timer angelegt, aber die Einzelepisoden werden in der Datenbank als 'bereits aufgenommen' markiert."
																"Sollten bereits alle Einzelepisoden vorhanden sein, wird für das Event kein Timer angelegt.\n\n"
																"Bei 'Einzelepisoden bevorzugen' wird versucht Timer für die Einzelepisoden anzulegen. "
																"Falls das nicht möglich ist, wird das Event aufgenommen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.TimerName :               ("Es kann ausgewählt werden, wie der Timername gebildet werden soll, dieser Name bestimmt auch den Namen der Aufnahme. Die Beschreibung enthält weiterhin die Staffel und Episoden Informationen.\n"
																"Falls das Plugin 'SerienFilm' verwendet wird, sollte man die Einstellung '<Serienname>' wählen, damit die Episoden korrekt in virtuellen Ordnern zusammengefasst werden."
																"In diesem Fall funktioniert aber die Funktion 'Zeige ob die Episode als Aufnahme auf der HDD ist' nicht, weil der Dateiname die nötigen Informationen nicht enthält.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.selectBouquets :          ("Bei 'ja' können 2 Bouquets (Standard und Alternativ) für die Sender-Zuordnung verwendet werden.\n"
																"Bei 'nein' werden alle Bouquets (in einer Liste zusammengefasst) für die Sender-Zuordnung benutzt.", "Bouquet_Auswahl"),
			config.plugins.serienRec.MainBouquet :             ("Auswahl, welches Bouquet bei der Sender-Zuordnung als Standard verwendet werden soll.", "Bouquet_Auswahl"),
			config.plugins.serienRec.AlternativeBouquet :      ("Auswahl, welches Bouquet bei der Sender-Zuordnung als Alternative verwendet werden soll.", "Bouquet_Auswahl"),
			config.plugins.serienRec.useAlternativeChannel :   ("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
																"falls der Timer auf dem bevorzugten Sender nicht angelegt werden kann.", "Bouquet_Auswahl"),
			config.plugins.serienRec.showPicons :              ("Bei 'ja' werden in der Hauptansicht auch die Sender-Logos angezeigt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.piconPath :               ("Wählen Sie das Verzeichnis aus dem die Sender-Logos geladen werden sollen. Der SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.downloadCover :           ("Bei 'nein' werden keine Cover heruntergeladen und angezeigt.\n"
																"Bei 'ja' werden Cover heruntergeladen.\n"
																"  - Wenn 'Zeige Cover' auf 'ja' steht, werden alle Cover heruntergeladen.\n"
																"  - Wenn 'Zeige Cover' auf 'nein' steht, werden beim Auto-Check nur Cover der Serien-Marker heruntergeladen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showCover :               ("Bei 'nein' werden keine Cover angezeigt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.createPlaceholderCover :  ("Bei 'ja' werden Platzhalter Dateien erzeugt wenn kein Cover vorhanden ist - das hat den Vorteil, dass nicht immer wieder nach dem Cover gesucht wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.listFontsize :            ("Damit kann bei zu großer oder zu kleiner Schrift eine individuelle Anpassung erfolgen. SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.intensiveTimersuche :     ("Bei 'ja' wird in der Hauptansicht intensiver nach vorhandenen Timern gesucht, d.h. es wird vor der Suche versucht die Anfangszeit aus dem EPGCACHE zu aktualisieren was aber zeitintensiv ist.", "intensive_Suche"),
			config.plugins.serienRec.sucheAufnahme :           ("Bei 'ja' wird ein Symbol für jede Episode angezeigt, die als Aufnahme auf der Festplatte gefunden wurde, diese Suche ist aber sehr zeitintensiv.\n"
																"Zusätzlich sorgt diese Option dafür, dass für Episoden die auf der Festplatte gefunden werden, kein Timer mehr angelegt wird.", "Aufnahme_vorhanden"),
			config.plugins.serienRec.markerSort :              ("Bei 'Alphabetisch' werden die Serien-Marker alphabetisch sortiert.\n"
																"Bei 'Wunschliste' werden die Serien-Marker so wie bei Wunschliste sortiert, d.h 'der, die, das und the' werden bei der Sortierung nicht berücksichtigt.\n"
																"Dadurch werden z.B. 'Die Simpsons' unter 'S' einsortiert.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.max_season :              ("Die höchste Staffelnummer, die für Serienmarker in der Staffel-Auswahl gewählt werden kann.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.confirmOnDelete :         ("Bei 'ja' erfolt eine Sicherheitsabfrage ('Soll ... wirklich entfernt werden?') vor dem entgültigen Löschen von Serienmarkern oder Timern.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showNotification :        ("Je nach Einstellung wird eine Nachricht auf dem Bildschirm eingeblendet, sobald der automatische Timer-Suchlauf startet bzw. endet.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showMessageOnConflicts :  ("Bei 'ja' wird für jeden Timer, der beim automatische Timer-Suchlauf wegen eines Konflikts nicht angelegt werden konnte, eine Nachricht auf dem Bildschirm eingeblendet.\n"
																"Diese Nachrichten bleiben solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.DisplayRefreshRate :      ("Das Zeitintervall in Sekunden, in dem die Anzeige der Options-Tasten wechselt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.seasonFilter :      		("Bei 'ja' werden in der Sendetermine Ansicht nur Termine angezeigt, die der am Marker eingestellten Staffeln entsprechen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.timerFilter :      		("Bei 'ja' werden in der Sendetermine Ansicht nur Termine angezeigt, für die noch Timer angelegt werden müssen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.refreshViews :            ("Bei 'ja' werden die Anzeigen nach Änderungen von Markern, Sendern, etc. sofort aktualisiert, was aber je nach STB-Typ und Internet-Verbindung zeitintensiv sein kann.\n"
																"Bei 'nein' erfolgt die Aktualisierung erst, wenn die Anzeige erneut geöffnet wird.", "Sofortige_Aktualisierung"),
			config.plugins.serienRec.openMarkerScreen :        ("Bei 'ja' wird nach Anlegen eines neuen Markers die Marker-Anzeige geöffnet, um den neuen Marker bearbeiten zu können.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.LogFilePath :             ("Das Verzeichnis auswählen und/oder erstellen, in dem die Log-Dateien gespeichert werden.", "Das_Log"),
			config.plugins.serienRec.longLogFileName :         ("Bei 'nein' wird bei jedem Timer-Suchlauf die Log-Datei neu erzeugt.\n"
																"Bei 'ja' wird NACH jedem Timer-Suchlauf die soeben neu erzeugte Log-Datei in eine Datei kopiert, deren Name das aktuelle Datum und die aktuelle Uhrzeit beinhaltet "
																"(z.B.\n"+SERIENRECORDER_LONG_LOGFILENAME % (config.plugins.serienRec.LogFilePath.value, str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)), "Das_Log"),
			config.plugins.serienRec.deleteLogFilesOlderThan : ("Log-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht.", "Das_Log"),
			config.plugins.serienRec.writeLog :                ("Bei 'nein' erfolgen nur grundlegende Eintragungen in die log-Datei, z.B. Datum/Uhrzeit des Timer-Suchlaufs, Beginn neuer Staffeln, Gesamtergebnis des Timer-Suchlaufs.\n"
																"Bei 'ja' erfolgen detaillierte Eintragungen, abhängig von den ausgewählten Filtern.", "Das_Log"),
			config.plugins.serienRec.writeLogVersion :         ("Bei 'ja' erfolgen Einträge in die log-Datei, die Informationen über die verwendete STB und das Image beinhalten.", "Das_Log"),
			config.plugins.serienRec.writeLogChannels :        ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn dem ausstrahlenden Sender in der Sender-Zuordnung kein STB-Sender zugeordnet ist, oder der STB-Sender deaktiviert ist.", "Das_Log"),
			config.plugins.serienRec.writeLogAllowedEpisodes : ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn die zu timende Staffel oder Folge in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist.", "Das_Log"),
			config.plugins.serienRec.writeLogAdded :           ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Timern vorhanden ist.", "Das_Log"),
			config.plugins.serienRec.writeLogDisk :            ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Aufnahmen vorhanden ist.", "Das_Log"),
			config.plugins.serienRec.writeLogTimeRange :       ("Bei 'ja' erfolgen Einträge in die log-Datei, wenn die zu timende Folge nicht in der erlaubten Zeitspanne (%s:%s - %s:%s) liegt, "
																"sowie wenn gemäß der Einstellung 'Immer Timer anlegen, wenn keine Wiederholung gefunden wird' = 'ja' "
																"ein Timer ausserhalb der erlaubten Zeitspanne angelegt wird." % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2), str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)), "Das_Log"),
			config.plugins.serienRec.writeLogTimeLimit :       ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der Sendetermin für die zu timende Folge in der Verganhenheit, \n"
																"oder mehr als die in 'Timer für X Tage erstellen' eingestellte Anzahl von Tagen in der Zukunft liegt (jetzt also nach %s)." % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400))), "Das_Log"),
			config.plugins.serienRec.writeLogTimerDebug :      ("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der zu erstellende Timer bereits vorhanden ist, oder der Timer erfolgreich angelegt wurde.", "Das_Log"),
			config.plugins.serienRec.logScrollLast :           ("Bei 'ja' wird beim Anzeigen der log-Datei ans Ende gesprungen, bei 'nein' auf den Anfang.", "Das_Log"),
			config.plugins.serienRec.logWrapAround :           ("Bei 'ja' erfolgt die Anzeige der log-Datei mit Zeilenumbruch, d.h. es werden 3 Zeilen pro Eintrag angezeigt.\n"
																"Bei 'nein' erfolgt die Anzeige der log-Datei mit 1 Zeile pro Eintrag (Bei langen Zeilen sind dann die Enden nicht mehr sichbar!)", "Das_Log"),
			config.plugins.serienRec.firstscreen :             ("Beim Start des SerienRecorder startet das Plugin mit dem ausgewählten Screen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.SkinType :                ("Hier kann das Erscheinungsbild des SR ausgewählt werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showAllButtons :          ("Hier kann für eigene Skins angegeben werden, ob immer ALLE Options-Tasten angezeigt werden, oder ob die Anzeige wechselt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.autochecktype :           ("Bei 'manuell' wird kein automatischer Suchlauf durchgeführt, die Suche muss manuell über die INFO/EPG Taste gestartet werden.\n\n"
																"Bei 'zur gewählten Uhrzeit' wird der automatische Suchlauf täglich zur eingestellten Uhrzeit ausgeführt.\n\n"
																"Bei 'nach EPGRefresh' wird der automatische Suchlauf ausgeführt, nachdem der EPGRefresh beendet ist (benötigt EPGRefresh v2.1.1 oder größer) - nicht verfügbar auf VU+ Boxen.", "1.3_Die_globalen_Einstellungen"),
		}

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]][0]
		except:
			text = "Keine Information verfügbar."

		self["config_information_text"].setText(text)

	def save(self):
		config.plugins.serienRec.showNotification.save()
		config.plugins.serienRec.autochecktype.save()

		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
		elif config.plugins.serienRec.updateInterval.value == 0:
			config.plugins.serienRec.timeUpdate.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False

		if not config.plugins.serienRec.selectBouquets.value:
			config.plugins.serienRec.MainBouquet.value = None
			config.plugins.serienRec.AlternativeBouquet.value = None
			config.plugins.serienRec.useAlternativeChannel.value = False

		if not config.plugins.serienRec.seriensubdir.value:
			config.plugins.serienRec.seasonsubdir.value = False

		if config.plugins.serienRec.autochecktype.value != "1":
			config.plugins.serienRec.wakeUpDSB.value = False

		if config.plugins.serienRec.planerCacheSize.value > 4:
			config.plugins.serienRec.planerCacheSize.value = 4

		if not config.plugins.serienRec.downloadCover.value:
			config.plugins.serienRec.showCover.value = False

		if config.plugins.serienRec.TimerName.value == "1":
			config.plugins.serienRec.sucheAufnahme.value = False

		config.plugins.serienRec.BoxID.save()
		config.plugins.serienRec.activateNewOnThisSTBOnly.save()
		config.plugins.serienRec.setupType.save()
		config.plugins.serienRec.savetopath.save()
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.afterEvent.save()
		config.plugins.serienRec.seriensubdir.save()
		config.plugins.serienRec.seasonsubdir.save()
		config.plugins.serienRec.seasonsubdirnumerlength.save()
		config.plugins.serienRec.seasonsubdirfillchar.save()
		config.plugins.serienRec.updateInterval.save()
		config.plugins.serienRec.readdatafromfiles.save()
		config.plugins.serienRec.tvplaner.save()
		config.plugins.serienRec.imap_server.save()
		config.plugins.serienRec.imap_server_ssl.save()
		config.plugins.serienRec.imap_server_port.save()
		if config.plugins.serienRec.imap_login.value != "*":
			config.plugins.serienRec.imap_login_hidden.value = SerienRecorderHelpers.encrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_login.value)
			config.plugins.serienRec.imap_login.value = "*"
		config.plugins.serienRec.imap_login.save()
		config.plugins.serienRec.imap_login_hidden.save()
		if config.plugins.serienRec.imap_password.value != "*":
			config.plugins.serienRec.imap_password_hidden.value = SerienRecorderHelpers.encrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_password.value)
			config.plugins.serienRec.imap_password.value = "*"
		config.plugins.serienRec.imap_password.save()
		config.plugins.serienRec.imap_password_hidden.save()
		config.plugins.serienRec.imap_mailbox.save()
		config.plugins.serienRec.imap_mail_subject.save()
		config.plugins.serienRec.imap_mail_age.save()
		config.plugins.serienRec.imap_check_interval.save()
		config.plugins.serienRec.tvplaner_create_marker.save()
		config.plugins.serienRec.tvplaner_series.save()
		config.plugins.serienRec.tvplaner_series_activeSTB.save()
		config.plugins.serienRec.tvplaner_movies.save()
		config.plugins.serienRec.tvplaner_movies_activeSTB.save()
		config.plugins.serienRec.tvplaner_movies_filepath.save()
		config.plugins.serienRec.tvplaner_movies_createsubdir.save()
		config.plugins.serienRec.tvplaner_full_check.save()
		if config.plugins.serienRec.tvplaner_full_check.value:
			config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
			config.plugins.serienRec.tvplaner_last_full_check.save()
		config.plugins.serienRec.tvplaner_skipSerienServer.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.AutoBackup.save()
		config.plugins.serienRec.deleteBackupFilesOlderThan.save()
		config.plugins.serienRec.coverPath.save()
		config.plugins.serienRec.BackupPath.save()
		config.plugins.serienRec.maxWebRequests.save()
		config.plugins.serienRec.margin_before.save()
		config.plugins.serienRec.margin_after.save()
		config.plugins.serienRec.markerSort.save()
		config.plugins.serienRec.max_season.save()
		config.plugins.serienRec.Autoupdate.save()
		config.plugins.serienRec.globalFromTime.save()
		config.plugins.serienRec.globalToTime.save()
		config.plugins.serienRec.timeUpdate.save()
		config.plugins.serienRec.deltime.save()
		config.plugins.serienRec.maxDelayForAutocheck.save()
		config.plugins.serienRec.wakeUpDSB.save()
		config.plugins.serienRec.afterAutocheck.save()
		config.plugins.serienRec.eventid.save()
		config.plugins.serienRec.epgTimeSpan.save()
		config.plugins.serienRec.LogFilePath.save()
		config.plugins.serienRec.longLogFileName.save()
		config.plugins.serienRec.deleteLogFilesOlderThan.save()
		config.plugins.serienRec.writeLog.save()
		config.plugins.serienRec.writeLogChannels.save()
		config.plugins.serienRec.writeLogAllowedEpisodes.save()
		config.plugins.serienRec.writeLogAdded.save()
		config.plugins.serienRec.writeLogDisk.save()
		config.plugins.serienRec.writeLogTimeRange.save()
		config.plugins.serienRec.writeLogTimeLimit.save()
		config.plugins.serienRec.writeLogTimerDebug.save()
		config.plugins.serienRec.writeLogVersion.save()
		config.plugins.serienRec.confirmOnDelete.save()
		config.plugins.serienRec.deleteOlderThan.save()
		config.plugins.serienRec.runAutocheckAtExit.save()
		config.plugins.serienRec.planerCacheEnabled.save()
		config.plugins.serienRec.planerCacheSize.save()
		config.plugins.serienRec.forceRecording.save()
		config.plugins.serienRec.forceManualRecording.save()
		if int(config.plugins.serienRec.checkfordays.value) > int(config.plugins.serienRec.TimeSpanForRegularTimer.value):
			config.plugins.serienRec.TimeSpanForRegularTimer.value = int(config.plugins.serienRec.checkfordays.value)
		config.plugins.serienRec.TimeSpanForRegularTimer.save()
		config.plugins.serienRec.showMessageOnConflicts.save()
		config.plugins.serienRec.DisplayRefreshRate.save()
		config.plugins.serienRec.refreshViews.save()
		config.plugins.serienRec.openMarkerScreen.save()
		config.plugins.serienRec.showPicons.save()
		config.plugins.serienRec.piconPath.save()
		config.plugins.serienRec.downloadCover.save()
		config.plugins.serienRec.showCover.save()
		config.plugins.serienRec.createPlaceholderCover.save()
		config.plugins.serienRec.listFontsize.save()
		config.plugins.serienRec.intensiveTimersuche.save()
		config.plugins.serienRec.sucheAufnahme.save()
		config.plugins.serienRec.selectNoOfTuners.save()
		config.plugins.serienRec.tuner.save()
		config.plugins.serienRec.seasonFilter.save()
		config.plugins.serienRec.timerFilter.save()
		config.plugins.serienRec.logScrollLast.save()
		config.plugins.serienRec.logWrapAround.save()
		config.plugins.serienRec.NoOfRecords.save()
		config.plugins.serienRec.DSBTimeout.save()
		config.plugins.serienRec.selectBouquets.save()
		config.plugins.serienRec.MainBouquet.save()
		config.plugins.serienRec.AlternativeBouquet.save()
		config.plugins.serienRec.useAlternativeChannel.save()
		if config.plugins.serienRec.selectBouquets.value:
			config.plugins.serienRec.bouquetList.value = str(list(zip(*self.bouquetList)[1]))
		else:
			config.plugins.serienRec.bouquetList.value = ""
		config.plugins.serienRec.bouquetList.save()
		config.plugins.serienRec.splitEventTimer.save()
		config.plugins.serienRec.justplay.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTPLAY__))
		config.plugins.serienRec.zapbeforerecord.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_ZAPBEFORERECORD__))
		config.plugins.serienRec.justremind.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTREMIND__))
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.zapbeforerecord.save()
		config.plugins.serienRec.justremind.save()
		# Save obsolete dbversion config setting here to remove it from file
		config.plugins.serienRec.dbversion.save()
		config.plugins.serienRec.TimerName.save()
		config.plugins.serienRec.firstscreen.save()
		config.plugins.serienRec.SkinType.save()
		config.plugins.serienRec.showAllButtons.save()
		config.plugins.serienRec.databasePath.save()
		configfile.save()
			
		if self.SkinType != config.plugins.serienRec.SkinType.value:
			SelectSkin()
			setSkinProperties(self)

		global serienRecDataBaseFilePath
		if serienRecDataBaseFilePath == "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			self.close((True, self.setupModified, True))
		else:
			self.session.openWithCallback(self.changeDBQuestion, MessageBox,
										  "Das Datenbank Verzeichnis wurde geändert - die Box muss neu gestartet werden.\nSoll das Datenbank Verzeichnis wirklich geändert werden?",
										  MessageBox.TYPE_YESNO, default=True)

	def changeDBQuestion(self, answer):
		global serienRecDataBaseFilePath
		if answer:
			if not os.path.exists("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value):
				self.session.openWithCallback(self.copyDBQuestion, MessageBox,
											  "Im ausgewählten Verzeichnis existiert noch keine Datenbank.\nSoll die bestehende Datenbank kopiert werden?",
											  MessageBox.TYPE_YESNO, default=True)
			else:
				serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

			self.session.open(Screens.Standby.TryQuitMainloop, 3)
		else:
			config.plugins.serienRec.databasePath.value = os.path.dirname(serienRecDataBaseFilePath)
			config.plugins.serienRec.databasePath.save()
			configfile.save()
			self.close((True, True, True))

	def copyDBQuestion(self, answer):
		global serienRecDataBaseFilePath
		if answer:
			try:
				shutil.copyfile(serienRecDataBaseFilePath, "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)
				serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
			except:
				writeLog("Fehler beim Kopieren der Datenbank")
				Notifications.AddPopup("Die SerienRecorder Datenbank konnte nicht kopiert werden.\nDer alte Datenbankpfad wird wiederhergestellt!", MessageBox.TYPE_INFO, timeout=10)
				config.plugins.serienRec.databasePath.value = os.path.dirname(serienRecDataBaseFilePath)
				config.plugins.serienRec.databasePath.save()
				configfile.save()
		else:
			serienRecDataBaseFilePath = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

	def openChannelSetup(self):
		self.session.openWithCallback(self.changedEntry, serienRecMainChannelEdit)

	def keyCancel(self):
		if self.setupModified:
			self.save()
		else:
			configfile.load()
			ReadConfigFile()
			self.close((False, False, True))


class serienRecChannelSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, webSender):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.webSender = webSender
		self.database = SRDatabase(serienRecDataBaseFilePath)
		
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red"	: (self.cancel, "Änderungen verwerfen und zurück zur Sender-Ansicht"),
			"green"	: (self.save, "Einstellungen speichern und zurück zur Sender-Ansicht"),
			"cancel": (self.cancel, "Änderungen verwerfen und zurück zur Sender-Ansicht"),
			"ok"	: (self.ok, "---"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"startTeletext" : (self.showAbout, "Über dieses Plugin"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"ok"	: self.ok,
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)

		(Vorlaufzeit, Nachlaufzeit, vps) = self.database.getChannelsSettings(self.webSender)

		if str(Vorlaufzeit).isdigit():
			self.margin_before = ConfigInteger(Vorlaufzeit, (0,99))
			self.enable_margin_before = ConfigYesNo(default = True)
		else:
			self.margin_before = ConfigInteger(config.plugins.serienRec.margin_before.value, (0,99))
			self.enable_margin_before = ConfigYesNo(default = False)
			
		if str(Nachlaufzeit).isdigit():
			self.margin_after = ConfigInteger(Nachlaufzeit, (0,99))
			self.enable_margin_after = ConfigYesNo(default = True)
		else:
			self.margin_after = ConfigInteger(config.plugins.serienRec.margin_after.value, (0,99))
			self.enable_margin_after = ConfigYesNo(default = False)

		if str(vps).isdigit():
			self.enable_vps = ConfigYesNo(default = bool(vps & 0x1))
			self.enable_vps_savemode = ConfigYesNo(default = bool(vps & 0x2))
		else:
			self.enable_vps = ConfigYesNo(default = False)
			self.enable_vps_savemode = ConfigYesNo(default = False)
		
		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[self.enable_margin_before])
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

		self['title'].setText("SerienRecorder - Einstellungen für '%s':" % self.webSender)
		self['text_red'].setText("Abbrechen")
		self['text_green'].setText("Speichern")
		global showAllButtons
		if not showAllButtons:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, "Hilfe"],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def createConfigList(self):
		self.margin_after_index = 1
		self.list = []
		self.list.append(getConfigListEntry("vom globalen Setup abweichenden Timervorlauf aktivieren:", self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry("      Timervorlauf (in Min.):", self.margin_before))
			self.margin_after_index += 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichenden Timernachlauf aktivieren:", self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry("      Timernachlauf (in Min.):", self.margin_after))

		if VPSPluginAvailable:
			self.list.append(getConfigListEntry("VPS für diesen Sender aktivieren:", self.enable_vps))
			if self.enable_vps.value:
				self.list.append(getConfigListEntry("      Sicherheitsmodus aktivieren:", self.enable_vps_savemode))

	def UpdateMenuValues(self):
		if self['config'].instance.getCurrentIndex() == 0:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self['config'].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		self.changedEntry()
	
	def changedEntry(self):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.UpdateMenuValues()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.UpdateMenuValues()

	def keyDown(self):
		#self.changedEntry()
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

	def keyUp(self):
		#self.changedEntry()
		if self['config'].instance.getCurrentIndex() < 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

	def ok(self):
		ConfigListScreen.keyOK(self)

	def setInfoText(self):
		self.HilfeTexte = {
			self.enable_margin_before : ("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
										 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n" 
										 "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
										 "Bei 'nein' gilt die Einstellung im globalen Setup.") % self.webSender,
			self.margin_before :        ("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
										 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
										 "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.webSender,
			self.enable_margin_after :  ("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
										 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
										 "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
										 "Bei 'nein' gilt die Einstellung im globalen Setup.") % self.webSender,
			self.margin_after :         ("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
										 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
										 "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.webSender,
			self.enable_vps :           ("Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
										 "und endet, wenn der Sender das Ende der Ausstrahlung angibt.") % self.webSender,
			self.enable_vps_savemode :  ("Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet.Die programmierten Start- und Endzeiten werden eingehalten.\n"
										 "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.") % self.webSender
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

		vpsSettings = (int(self.enable_vps_savemode.value) << 1) + int(self.enable_vps.value)
			
		self.database.setChannelSettings(self.webSender, Vorlaufzeit, Nachlaufzeit, vpsSettings)
		self.close()

	def cancel(self):
		self.close()

class serienRecFileList(Screen, HelpableScreen):
	def __init__(self, session, initDir, title, seriesName = ''):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.initDir = initDir
		self.title = title
		self.seriesNames = seriesName
		
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left":   (self.keyLeft, "zur vorherigen Seite blättern"),
			"right":  (self.keyRight, "zur nächsten Seite blättern"),
			"up":     (self.keyUp, "eine Zeile nach oben"),
			"down":   (self.keyDown, "eine Zeile nach unten"),
			"ok":     (self.keyOk, "ins ausgewählte Verzeichnis wechseln"),
			"green":  (self.keyGreen, "ausgewähltes Verzeichnis übernehmen"),
			"red":    (self.keyRed, "ausgewähltes Verzeichnis löschen"),
			"blue":   (self.keyBlue, "neues Verzeichnis anlegen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		self.updateFile()
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)
		
		self['menu_list'] = FileList(self.initDir, inhibitMounts = False, inhibitDirs = False, showMountpoints = False, showFiles = False)
		self['menu_list'].show()
		self['title'].hide()
		self['path'].show()

		self['text_red'].setText("Verzeichnis löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Auswahl")
		self['text_blue'].setText("Verzeichnis anlegen")
		global showAllButtons
		if not showAllButtons:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			
			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, "Hilfe"],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def keyCancel(self):
		self.close(None)

	def keyRed(self):
		try:
			os.rmdir(self['menu_list'].getSelection()[0])
		except:
			pass
		self.updateFile()
		
	def keyGreen(self):
		directory = self['menu_list'].getSelection()[0]
		if (directory.endswith("/")):
			self.fullpath = self['menu_list'].getSelection()[0]
		else:
			self.fullpath = "%s/" % self['menu_list'].getSelection()[0]
		self.close(self.fullpath)

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Verzeichnis-Name eingeben:", text = self.seriesNames)

	def wSearch(self, Path_name):
		if Path_name:
			Path_name = "%s%s/" % (self['menu_list'].getSelection()[0], Path_name)
			print Path_name
			if not os.path.exists(Path_name):
				try:
					os.makedirs(Path_name)
				except:
					pass
		self.updateFile()
			
	def keyUp(self):
		self['menu_list'].up()
		self.updateFile()

	def keyDown(self):
		self['menu_list'].down()
		self.updateFile()

	def keyLeft(self):
		self['menu_list'].pageUp()
		self.updateFile()

	def keyRight(self):
		self['menu_list'].pageDown()
		self.updateFile()

	def keyOk(self):
		if self['menu_list'].canDescent():
			self['menu_list'].descent()
			self.updateFile()

	def updateFile(self):
		currFolder = self['menu_list'].getSelection()[0]
		self['path'].setText("Auswahl:\n%s" % currFolder)

		
#---------------------------------- Info Functions ------------------------------------------

class serienRecReadLog(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"red"   : (self.keyRed, "zurück zur vorherigen Ansicht"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		self.onLayoutFinish.append(self.readLog)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Schließen")
		self.num_bt_text[0][0] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			self.num_bt_text[1][2] = buttonText_na
			Skin1_Settings(self)
		else:
			self.num_bt_text[1][2] = ""

			self.displayMode = 2
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
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		if config.plugins.serienRec.logWrapAround.value:
			self.chooseMenuList.l.setItemHeight(int(70*skinFactor))
		else:
			self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['log'] = self.chooseMenuList
		self['log'].show()
		self['video'].hide()
		self['cover'].hide()

		self['title'].setText("Lese LogFile: (%s)" % logFile)
		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_exit'].show()
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
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.readLog()
				
	def readLog(self):
		if not fileExists(logFile):
			open(logFile, 'w').close()

		logFile_leer = os.path.getsize(logFile)
		if not logFile_leer == 0:
			readLog = open(logFile, "r")
			logliste = []
			for zeile in readLog.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					logliste.append(zeile)
			readLog.close()
			self['title'].hide()
			self['path'].setText("LogFile:\n(%s)" % logFile)
			self['path'].show()
			self.chooseMenuList.setList(map(self.buildList, logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(logliste)
				if count != 0:
					self['log'].moveToIndex(int(count-1))

	@staticmethod
	def buildList(entry):
		(zeile) = entry
		width = 850
		if config.plugins.serienRec.SkinType.value == "":
			width = 1240

		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, width * skinFactor, 65 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 2 * skinFactor, width * skinFactor, 20 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def keyLeft(self):
		self['log'].pageUp()

	def keyRight(self):
		self['log'].pageDown()

	def keyDown(self):
		self['log'].down()

	def keyUp(self):
		self['log'].up()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close()

	def keyRed(self):
		self.close()

class serienRecShowConflicts(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.skin = None
		self.conflictsListe = []
		self.session = session
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"blue"	: (self.keyBlue, "alle Einträge aus der Liste endgültig löschen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.onLayoutFinish.append(self.readConflicts)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Abbrechen")
		self['text_blue'].setText("Liste leeren")
		self.num_bt_text[1][1] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			self.num_bt_text[1][2] = buttonText_na
			Skin1_Settings(self)
		else:
			self.num_bt_text[1][2] = ""

			self.displayMode = 2
			self.updateMenuKeys()
		
			self.displayTimer = eTimer()
			if isDreamOS():
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)
			
	def setupSkin(self):
		InitSkin(self)
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		self['title'].setText("Timer-Konflikte")
		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_info'].show()
			self['bt_menu'].show()
			
			self['text_red'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
				
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.readConflicts()
				
	def readConflicts(self):
		conflicts = self.database.getTimerConflicts()
		for conflict in conflicts:
			(zeile, start_time, webChannel) = conflict
			data = zeile.split('/')
			if data:
				self.conflictsListe.append(("%s" % data[0].strip()))
				self.conflictsListe.append(("    @ %s (%s) in Konflikt mit:" % (webChannel, time.strftime("%d.%m.%Y - %H:%M", time.localtime(start_time)))))
				data = data[1:]
				for row2 in data:
					self.conflictsListe.append(("            -> %s" % row2.strip()))
				self.conflictsListe.append(("-" * 100))
				self.conflictsListe.append((""))
		self.chooseMenuList.setList(map(self.buildList, self.conflictsListe))
					
	def buildList(self, entry):
		(zeile) = entry
		return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850 * skinFactor, 20 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def keyLeft(self):
		self['menu_list'].pageUp()

	def keyRight(self):
		self['menu_list'].pageDown()

	def keyDown(self):
		self['menu_list'].down()

	def keyUp(self):
		self['menu_list'].up()

	def keyBlue(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Conflict-List leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Soll die Liste wirklich geleert werden?", MessageBox.TYPE_YESNO, default = False)
			else:
				self.callDeleteMsg(True)

	def callDeleteMsg(self, answer):
		if answer:
			self.database.removeAllTimerConflicts()
			self.readConflicts()
		else:
			return
			
	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None
			
	def keyCancel(self):
		self.close()

class serienRecModifyAdded(Screen, HelpableScreen):
	def __init__(self, session, skip=True):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.ErrorMsg = "unbekannt"
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "für die ausgewählte Serien neue Einträge hinzufügen"),
			"cancel": (self.keyCancel, "alle Änderungen verwerfen und zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "ausgewählten Eintrag löschen"),
			"green" : (self.keyGreen, "alle Änderungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "umschalten Sortierung ein/aus"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.delAdded = False
		self.addedlist = []
		self.addedlist_tmp = []
		self.dbData = []
		self.modus = "menu_list"
		self.aStaffel = "0"
		self.aFromEpisode = 0
		self.aToEpisode = 0

		if skip:
			self.onShown.append(self.functionWillBeDeleted)
		else:
			self.onLayoutFinish.append(self.readAdded)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def functionWillBeDeleted(self):
		self.session.open(serienRecMarker)
		self.hide()
		self.session.open(MessageBox, "WICHTIGER Hinweis:\n\n"
									  "Dieser Funktionsaufruf wird ab dem nächsten Update nicht mehr zur Verfügung stehen!!\n\n"
									  "Die manuelle Bearbeitung der Timer-Liste, d.h. Hinzufügen und Löschen einzelner Episoden "
									  "kann in der Episoden-Liste der jeweiligen Serie erfolgen. Dazu in der Serien-Marker Ansicht die gewünschte Serie auswählen, "
									  "und mit der Taste 5 die Episoden-Liste öffnen. Danach können mit der grünen Taste einzelne Episoden für die Timererstellung "
									  "gesperrt oder wieder freigegeben werden.", MessageBox.TYPE_INFO)
		self.close()

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Eintrag löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Neuer Eintrag")
		if config.plugins.serienRec.addedListSorted.value:
			self['text_yellow'].setText("unsortierte Liste")
		else:
			self['text_yellow'].setText("Sortieren")
		self.num_bt_text[1][0] = buttonText_na

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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

		#normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
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
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		url = self.database.getMarkerURL(serien_name)
		serien_id = getSeriesIDByURL(url)
		self.session.open(serienRecShowInfo, serien_name, serien_id)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)

	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.modus == "menu_list":
				check = self['menu_list'].getCurrent()
				if check is None:
					return
				serien_name = self['menu_list'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check is None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]

			print "[SerienRecorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.modus == "menu_list":
				check = self['menu_list'].getCurrent()
				if check is None:
					return
				serien_name = self['menu_list'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check is None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]

			print "[SerienRecorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)

	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.readAdded()

	def readAdded(self):
		self.addedlist = []
		timers = self.database.getAllTimer(None)
		for timer in timers:
			(Serie, Staffel, Episode, title, start_time, stbRef, webChannel, eit, active) = timer
			zeile = "%s - S%sE%s - %s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2), title)
			self.addedlist.append((zeile.replace(" - dump", " - %s" % "(Manuell hinzugefügt !!)"), Serie, Staffel, Episode, title, start_time, webChannel))

		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Diese Episoden werden nicht mehr aufgenommen !")
		self.addedlist_tmp = self.addedlist[:]
		if config.plugins.serienRec.addedListSorted.value:
			self.addedlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
		self.getCover()

	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode, title, start_time, webChannel) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile, foregroundColor)
			]

	def buildList_popup(self, entry):
		(Serie,) = entry
		foregroundColor = parseColor('foreground').argb()
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, foregroundColor)
			]

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
		if self.aStaffel is None or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, NTIVirtualKeyBoard, title = "von Episode:")

	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if self.aFromEpisode is None or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, NTIVirtualKeyBoard, title = "bis Episode:")

	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		if self.aToEpisode == "":
			self.aToEpisode = self.aFromEpisode

		if self.aToEpisode is None: # or self.aFromEpisode is None or self.aStaffel is None:
			return
		else:
			print "[SerienRecorder] Staffel: %s" % self.aStaffel
			print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
			print "[SerienRecorder] bis Episode: %s" % self.aToEpisode

			if self.aStaffel.startswith('0') and len(self.aStaffel) > 1:
				self.aStaffel = self.aStaffel[1:]

			if self.database.addToTimerList(self.aSerie, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump", int(time.time()), "", "", 0, 1):
				self.readAdded()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = self.database.getMarkerNames()
			self.chooseMenuList_popup.setList(map(self.buildList_popup, l))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "menu_list"
			self['menu_list'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() is None:
				print "[SerienRecorder] Marker-Liste leer."
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aStaffel = "0"
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.aSerie)

	def keyRed(self):
		check = None
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Added-File leer."
			return
		else:
			zeile = self['menu_list'].getCurrent()[0]
			(txt, serie, staffel, episode, title, start_time, webChannel) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_time, webChannel.lower()))
			self.addedlist_tmp.remove(zeile)
			self.addedlist.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
			self.delAdded = True

	def keyGreen(self):
		if self.modus == "menu_list" and self.delAdded:
			self.database.removeTimers(self.dbData)
		self.close()

	def keyYellow(self):
		if self.modus == "menu_list" and len(self.addedlist_tmp) != 0:
			if config.plugins.serienRec.addedListSorted.value:
				self.addedlist_tmp = self.addedlist[:]
				self['text_yellow'].setText("Sortieren")
				config.plugins.serienRec.addedListSorted.setValue(False)
			else:
				self.addedlist_tmp.sort()
				self['text_yellow'].setText("unsortierte Liste")
				config.plugins.serienRec.addedListSorted.setValue(True)
			config.plugins.serienRec.addedListSorted.save()
			configfile.save()

			self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
			self.getCover()

	def getCover(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		url = self.database.getMarkerURL(serien_name)
		serien_id = getSeriesIDByURL(url)
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)

	def keyLeft(self):
		self[self.modus].pageUp()
		self.getCover()

	def keyRight(self):
		self[self.modus].pageDown()
		self.getCover()

	def keyDown(self):
		self[self.modus].down()
		self.getCover()

	def keyUp(self):
		self[self.modus].up()
		self.getCover()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def callDeleteMsg(self, answer):
		if answer:
			self.keyGreen()
		self.close()

	def keyCancel(self):
		if self.delAdded:
			self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Sollen die Änderungen gespeichert werden?", MessageBox.TYPE_YESNO, default = True)
		else:
			self.close()

class serienRecWishlist(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.ErrorMsg = "unbekannt"
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "für die ausgewählte Serien neue Einträge hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "ausgewählten Eintrag löschen"),
			"green" : (self.keyGreen, "alle Änderungen speichern und zurück zur vorherigen Ansicht"),
			"yellow": (self.keyYellow, "umschalten Sortierung ein/aus"),
			"blue"	: (self.keyBlue, "alle Einträge aus der Liste endgültig löschen"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.delAdded = False
		self.wishlist = []
		self.wishlist_tmp = []
		self.dbData = []
		self.modus = "menu_list"
		
		self.onLayoutFinish.append(self.readWishlist)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Eintrag löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Eintrag anlegen")
		if config.plugins.serienRec.wishListSorted.value:
			self['text_yellow'].setText("unsortierte Liste")
		else:
			self['text_yellow'].setText("Sortieren")
		self['text_blue'].setText("Liste leeren")
		self.num_bt_text[2][1] = buttonText_na

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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
		
		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(25*skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['title'].setText("Diese Episoden sind zur Aufnahme vorgemerkt")

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
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		url = self.database.getMarkerURL(serien_name)
		serien_id = getSeriesIDByURL(url)
		if serien_id:
			self.session.open(serienRecShowInfo, serien_name, serien_id)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.modus == "menu_list":
				check = self['menu_list'].getCurrent()
				if check is None:
					return
				serien_name = self['menu_list'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check is None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]
			
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.modus == "menu_list":
				check = self['menu_list'].getCurrent()
				if check is None:
					return
				serien_name = self['menu_list'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check is None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]
			
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.readWishlist()
				
	def readWishlist(self):
		self.wishlist = []
		bookmarks = self.database.getBookmarks()
		for bookmark in bookmarks:
			(Serie, Staffel, Episode, numberOfRecordings) = bookmark
			zeile = "%s S%sE%s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2))
			self.wishlist.append((zeile, Serie, Staffel, Episode))
		
		self.wishlist_tmp = self.wishlist[:]
		if config.plugins.serienRec.wishListSorted.value:
			self.wishlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
		self.getCover()
		
	@staticmethod
	def buildList(entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	@staticmethod
	def buildList_popup(entry):
		(Serie,) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
			]

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
		if self.aStaffel is None or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, NTIVirtualKeyBoard, title = "von Episode:")
	
	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if self.aFromEpisode is None or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, NTIVirtualKeyBoard, title = "bis Episode:")
	
	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		print "[SerienRecorder] Staffel: %s" % self.aStaffel
		print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
		print "[SerienRecorder] bis Episode: %s" % self.aToEpisode
		
		if self.aToEpisode is None or self.aFromEpisode is None or self.aStaffel is None or self.aToEpisode == "":
			return
		else:
			self.database.addBookmark(self.aSerie, self.aFromEpisode, self.aToEpisode, self.aStaffel, int(config.plugins.serienRec.NoOfRecords.value))
			self.readWishlist()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = self.database.getMarkerNames()
			self.chooseMenuList_popup.setList(map(self.buildList_popup, l))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "menu_list"
			self['menu_list'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() is None:
				print "[SerienRecorder] Marker-Liste leer."
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aStaffel = 0
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, NTIVirtualKeyBoard, title = "%s: Staffel eingeben:" % self.aSerie)

	def keyRed(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Merkzettel ist leer."
			return
		else:
			zeile = self['menu_list'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower()))
			self.wishlist_tmp.remove(zeile)
			self.wishlist.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
			self.delAdded = True
			
	def keyGreen(self):
		if self.delAdded:
			self.database.removeBookmarks(self.dbData)
		self.close()
			
	def keyYellow(self):
		if len(self.wishlist_tmp) != 0:
			if config.plugins.serienRec.wishListSorted.value:
				self.wishlist_tmp = self.wishlist[:]
				self['text_yellow'].setText("Sortieren")
				config.plugins.serienRec.wishListSorted.setValue(False)
			else:
				self.wishlist_tmp.sort()
				self['text_yellow'].setText("unsortierte Liste")
				config.plugins.serienRec.wishListSorted.setValue(True)
			config.plugins.serienRec.wishListSorted.save()
			configfile.save()
			
			self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
			self.getCover()
		
	def keyBlue(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Merkzettel ist leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callClearListMsg, MessageBox, "Soll die Liste wirklich geleert werden?", MessageBox.TYPE_YESNO, default = False)
			else:
				self.callClearListMsg(True)

	def callClearListMsg(self, answer):
		if answer:
			self.database.removeAllBookmarks()
			self.readWishlist()
		else:
			return
			
	def getCover(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return
			serien_name = self['menu_list'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check is None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]


		url = self.database.getMarkerURL(serien_name)
		serien_id = getSeriesIDByURL(url)
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)
			
	def keyLeft(self):
		self[self.modus].pageUp()
		self.getCover()

	def keyRight(self):
		self[self.modus].pageDown()
		self.getCover()

	def keyDown(self):
		self[self.modus].down()
		self.getCover()

	def keyUp(self):
		self[self.modus].up()
		self.getCover()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None
			
	def callDeleteMsg(self, answer):
		if answer:
			self.keyGreen()
		self.close()
			
	def keyCancel(self):
		if self.delAdded:
			self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Sollen die Änderungen gespeichert werden?", MessageBox.TYPE_YESNO, default = True)
		else:
			self.close()

class serienRecShowInfo(Screen, HelpableScreen):
	def __init__(self, session, serieName, serieID):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serieName = serieName
		self.serieID = serieID
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.pageUp, "zur vorherigen Seite blättern"),
			"right" : (self.pageDown, "zur nächsten Seite blättern"),
			"up"    : (self.pageUp, "zur vorherigen Seite blättern"),
			"down"  : (self.pageDown, "zur nächsten Seite blättern"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"red"   : (self.keyCancel, "zurück zur vorherigen Ansicht"),
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
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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

		self['title'].setText("Serien Beschreibung: %s" % self.serieName)

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()
		global showAllButtons
		if not showAllButtons:
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
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			print "[SerienRecorder] starte youtube suche für %s" % self.serieName
			self.session.open(searchYouTube, self.serieName)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			print "[SerienRecorder] starte Wikipedia Suche für %s" % self.serieName
			self.session.open(wikiSearch, self.serieName)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			self.session.open(Browser, SR_OperatingManual, True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def getCover(self):
		url = self.database.getMarkerURL(self.serieName)
		serien_id = getSeriesIDByURL(url)
		self.ErrorMsg = "'getCover()'"
		getCover(self, self.serieName, serien_id)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)

			if result[1]:
				self.getData()
				
	def getData(self):
		try:
			infoText = SeriesServer().getSeriesInfo(self.serieID)
		except:
			infoText = 'Es ist ein Fehler beim Abrufen der Serien-Informationen aufgetreten!'
		self['info'].setText(infoText)
		self.getCover()

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

#---------------------------------- Main Functions ------------------------------------------

class serienRecMain(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.picloader = None
		self.ErrorMsg = "unbekannt"
		self.skin = None
		self.chooseMenuList = None
		self.chooseMenuList_popup = None
		self.popup_list = []
		self.piconLoader = PiconLoader()
		self.database = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "SerienRecorder beenden"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "Anzeige-Modus auswählen"),
			"green"	: (self.keyGreen, "Ansicht Sender-Zuordnung öffnen"),
			"yellow": (self.keyYellow, "Ansicht Serien-Marker öffnen"),
			"blue"	: (self.keyBlue, "Ansicht Timer-Liste öffnen"),
			"info" 	: (self.keyCheck, "Suchlauf für Timer mit TV-Planer starten"),
			"info_long" 	: (self.keyCheckLong, "Suchlauf für Timer starten"),
			"menu"	: (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"nextBouquet" : (self.nextPage, "Serienplaner des nächsten Tages laden"),
			"prevBouquet" : (self.backPage, "Serienplaner des vorherigen Tages laden"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"1"		: (self.searchSeries, "Serie manuell suchen"),
			"2"		: (self.reloadSerienplaner, "Serienplaner neu laden"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"5"		: (self.imaptest, "IMAP Test"),
		}, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)
		
		ReadConfigFile()

		if not os.path.exists(config.plugins.serienRec.piconPath.value):
			config.plugins.serienRec.showPicons.value = False

		self.setupSkin()
		
		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
		elif config.plugins.serienRec.updateInterval.value == 0:
			config.plugins.serienRec.timeUpdate.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False

		global showMainScreen
		if config.plugins.serienRec.firstscreen.value == "0":
			showMainScreen = True
		else:
			showMainScreen = False

		self.pRegional = 0
		self.pPaytv = 1
		self.pPrime = 1
		self.color_print = "\033[93m"
		self.color_end = "\33[0m"
		self.page = 0
		self.modus = "list"
		self.loading = True
		self.daylist = [[]]
		self.displayTimer = None
		self.displayMode = 1
		self.serviceRefs = None

		self.onLayoutFinish.append(self.setSkinProperties)

		self.onFirstExecBegin.append(self.showSplashScreen)
		self.onFirstExecBegin.append(self.checkForUpdate)

		if config.plugins.serienRec.showStartupInfoText.value:
			global InfoFile
			if fileExists(InfoFile):
				self.onFirstExecBegin.append(self.showInfoText)
			else:
				self.onFirstExecBegin.append(self.startScreen)
		else:
			self.onFirstExecBegin.append(self.startScreen)
		self.onClose.append(self.__onClose)

	def imaptest(self):
		try:
			if config.plugins.serienRec.imap_server_ssl.value:
				mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value,
										 config.plugins.serienRec.imap_server_port.value)
			else:
				mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value,
									 config.plugins.serienRec.imap_server_port.value)

		except:
			self.session.open(MessageBox, "Verbindung zum E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
			writeLog("IMAP Check: Verbindung zum Server fehlgeschlagen", True)
			return None

		try:
			mail.login(SerienRecorderHelpers.decrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
					   SerienRecorderHelpers.decrypt(SerienRecorderHelpers.getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))

		except imaplib.IMAP4.error:
			self.session.open(MessageBox, "Anmeldung am E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
			writeLog("IMAP Check: Anmeldung auf Server fehlgeschlagen", True)
			return None

		try:
			import string

			writeLog("Postfächer:", True)
			result, data = mail.list('""', '*')
			if result == 'OK':
				for item in data[:]:
					x = item.split()
					mailbox = string.join(x[2:])
					writeLog("%s" % mailbox, True)
		except imaplib.IMAP4.error:
			self.session.open(MessageBox, "Abrufen der Postfächer vom E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
			writeLog("IMAP Check: Abrufen der Postfächer fehlgeschlagen", True)

		try:
			mail.select(config.plugins.serienRec.imap_mailbox.value)

		except imaplib.IMAP4.error:
			self.session.open(MessageBox, "Postfach [%r] nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, MessageBox.TYPE_INFO, timeout=10)
			writeLog("IMAP Check: Mailbox %r nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, True)
			mail.logout()
			return None

		searchstr = TimeHelpers.getMailSearchString()
		writeLog("IMAP Check: %s" % searchstr, True)
		try:
			result, data = mail.uid('search', None, searchstr)
			writeLog("IMAP Check: %s (%d)" % (result, len(data[0].split(' '))), True)
			if result != 'OK':
				writeLog("IMAP Check: %s" % data, True)

		except imaplib.IMAP4.error:
			self.session.open(MessageBox, "Fehler beim Abrufen der TV-Planer E-Mail", MessageBox.TYPE_INFO, timeout=10)
			writeLog("IMAP Check: Fehler beim Abrufen der Mailbox", True)
			writeLog("IMAP Check: %s" % mail.error.message, True)

		mail.logout()
		self.session.open(MessageBox, "IMAP Test abgeschlossen - siehe Log", MessageBox.TYPE_INFO, timeout=10)

	def showInfoText(self):
		self.session.openWithCallback(self.startScreen, ShowStartupInfo)

	def showSplashScreen(self):
		self.session.openWithCallback(self.checkForUpdate, ShowSplashScreen, config.plugins.serienRec.showversion.value)

	def checkForUpdate(self):
		if config.plugins.serienRec.Autoupdate.value:
			checkGitHubUpdate(self.session).checkForUpdate()

		self.startScreen()

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)
		
		self['text_red'].setText("Anzeige-Modus")
		self['text_green'].setText("Sender zuordnen")
		self['text_ok'].setText("Marker hinzufügen")
		self['text_yellow'].setText("Serien Marker")
		self['text_blue'].setText("Timer-Liste")
		self.num_bt_text[0][1] = "IMAP-Test"
		self.num_bt_text[1][0] = "Serie suchen"
		self.num_bt_text[2][0] = "neu laden"
		self.num_bt_text[2][2] = "Timer suchen"
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
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

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50 * skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(30 * skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['title'].setText("Lade infos from Web...")

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
			self['text_5'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def test(self):
		i = 0

	def reloadSerienplaner(self):
		lt = datetime.datetime.now()
		lt += datetime.timedelta(days=self.page)
		key = time.strftime('%d.%m.%Y', lt.timetuple())
		if key in dayCache: 
			del dayCache[key]
		self.readPlanerData(False)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		self.session.openWithCallback(self.readPlanerData, serienRecShowSeasonBegins)

	def searchSeries(self):
		if self.modus == "list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecAddSerie, serien_name)

	def handleSeriesSearchEnd(self, serien_name=None):
		if serien_name:
			self.session.openWithCallback(self.readPlanerData, serienRecMarker, serien_name)
		else:
			self.readPlanerData(False)

	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		(serien_name, serien_id) = self.getSeriesNameID()
		self.session.open(serienRecShowInfo, serien_name, serien_id)
		#self.session.open(MessageBox, "Diese Funktion steht in dieser Version noch nicht zur Verfügung!",
		#			  MessageBox.TYPE_INFO, timeout=10)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return

			check = self['menu_list'].getCurrent()
			if check is None:
				return

			(serien_name, serien_id) = self.getSeriesNameID()
			print "[SerienRecorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][6]
			print "[SerienRecorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Wikipedia von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def showManual(self):
		if OperaBrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, SR_OperatingManual, False)
		elif DMMBrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, True, SR_OperatingManual)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def setHeadline(self):
		if int(config.plugins.serienRec.screenplaner.value) == 1:
			self['headline'].setText("Serien-Planer (Serien Tagesübersicht)")
			self['text_red'].setText("Top 30")
		elif int(config.plugins.serienRec.screenplaner.value) == 2:
			self['headline'].setText("Top 30 SerienRecorder Serien")
			self['text_red'].setText("Tagesübersicht")

		self['headline'].instance.setForegroundColor(parseColor("red"))

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False, False)
			if result[1]:
				self.readPlanerData()

	def startScreen(self):
		print "[SerienRecorder] version %s is running..." % config.plugins.serienRec.showversion.value

		global refreshTimer
		if not refreshTimer:
			if config.plugins.serienRec.timeUpdate.value:
				serienRecCheckForRecording(self.session, False, False)

		if not initDB():
			self.keyCancel()
			self.close()
			return

		self.database = SRDatabase(serienRecDataBaseFilePath)
		if not self.database.hasChannels():
			print "[SerienRecorder] Channellist is empty !"
			self.session.openWithCallback(self.readPlanerData, serienRecMainChannelEdit)
		else:
			self.serviceRefs = self.database.getActiveServiceRefs()
			if not showMainScreen:
				self.session.openWithCallback(self.readPlanerData, serienRecMarker)
			else:
				self.readPlanerData(False)

	def readPlanerData(self, answer=True):
		if not showMainScreen:
			self.keyCancel()
			self.close()
			return

		self.loading = True
		loadPlanerData(config.plugins.serienRec.screenplaner.value)
			
		global dayCache
		if answer:
			dayCache.clear()
			
		self.setHeadline()
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		lt = datetime.datetime.now()
		if config.plugins.serienRec.screenplaner.value == 1:
			lt += datetime.timedelta(days=self.page)
		key = time.strftime('%d.%m.%Y', lt.timetuple())
		if key in dayCache:
			try:
				self['title'].setText("Lade Infos vom Speicher...")
				if config.plugins.serienRec.screenplaner.value == 1:
					self.processPlanerData(dayCache[key], True)
				else:
					self.processTopThirty(dayCache[key], True)
			except:
				writeLog("Fehler beim Abrufen und Verarbeiten der Daten\n", True)
		else:
			self['title'].setText("Lade Infos vom Web...")
			webChannels = self.database.getActiveChannels()
			try:
				if config.plugins.serienRec.screenplaner.value == 1:
					planerData = SeriesServer().doGetPlanerData(int(self.page), webChannels)
					self.processPlanerData(planerData, False)
				else:
					topThirtyData = SeriesServer().doGetTopThirty()
					self.processTopThirty(topThirtyData, False)
			except:
				writeLog("Fehler beim Abrufen und Verarbeiten der Daten\n", True)
			
	def processPlanerData(self, data, useCache=False):
		if not data or len(data) == 0:
			self['title'].setText("Fehler beim Abrufen der SerienPlaner-Daten")
			return
		if useCache:
			(headDate, self.daylist) = data
		else:
			self.daylist = [[]]
			headDate = [data["date"]]


			markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)
			timers = self.database.getTimer(self.page)

			for event in data["events"]:
				aufnahme = False
				serieAdded = 0
				start_h = event["time"][:+2]
				start_m = event["time"][+3:]
				start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, self.page)

				serien_name = event["name"].encode("utf-8")
				serien_name_lower = serien_name.lower()
				serien_id = int(event["id"])
				sender = event["channel"]
				title = event["title"].encode("utf-8")
				staffel = event["season"]
				episode = event["episode"]
				self.ErrorMsg = "%s - S%sE%s - %s (%s)" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title, sender)

				serienTimers = [timer for timer in timers if timer[0] == serien_name_lower]
				serienTimersOnChannel = [serienTimer for serienTimer in serienTimers if serienTimer[2] == sender.lower()]
				for serienTimerOnChannel in serienTimersOnChannel:
					if (int(serienTimerOnChannel[1]) >= (int(start_time) - 300)) and (int(serienTimerOnChannel[1]) < (int(start_time) + 300)):
						aufnahme = True

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				if serien_id in markers:
					serieAdded = 1 if markers[serien_id] else 2

				staffel = str(staffel).zfill(2)
				episode = str(episode).zfill(2)

				##############################
				#
				# CHECK
				#
				# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
				#
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					(dirname, dirname_serie) = getDirname(self.database, serien_name, staffel)
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False, title) > 0 and True or False
						else:
							bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False) > 0 and True or False
					else:
						bereits_vorhanden = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False) > 0 and True or False

				title = "%s - %s" % (seasonEpisodeString, title)
				regional = False
				paytv = False
				neu = event["new"]
				prime = False
				transmissionTime = event["time"]
				url = ''
				self.daylist[0].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

			print "[SerienRecorder] Es wurden %s Serie(n) gefunden" % len(self.daylist[0])
			
			if headDate:
				d = headDate[0].split(',')
				d.reverse()
				key = d[0].strip()
				global dayCache
				dayCache.update({key:(headDate, self.daylist)})
				if config.plugins.serienRec.planerCacheEnabled.value:
					writePlanerData(1)
				
		self.loading = False

		if len(self.daylist[0]) != 0:
			if headDate:
				self['title'].setText("Es wurden für - %s - %s Serie(n) gefunden." % (headDate[0], len(self.daylist[0])))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			else:
				self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[0]))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.chooseMenuList.setList(map(self.buildPlanerList, self.daylist[0]))
			self.ErrorMsg = "'getCover()'"
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[0]))
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			print "[SerienRecorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
			self.chooseMenuList.setList(map(self.buildPlanerList, self.daylist[0]))

	def processTopThirty(self, data, useCache=False):
		if not data or len(data) == 0:
			self['title'].setText("Fehler beim Abrufen der SerienPlaner-Daten")
			return
		if useCache:
			(headDate, self.daylist) = data
		else:
			self.daylist = [[]]
			headDate = [data["date"]]

			markers = self.database.getAllMarkerStatusForBoxID(config.plugins.serienRec.BoxID.value)

			rank = 0
			for serie in data["series"]:
				serien_name = serie["name"].encode("utf-8")
				serien_id = int(serie["id"])
				average = serie["average"]

				# 0 = no marker, 1 = active marker, 2 = deactive marker
				serieAdded = 0
				if serien_id in markers:
					serieAdded = 1 if markers[serien_id] else 2

				rank += 1
				self.daylist[0].append((serien_name, average, serien_id, serieAdded, rank))

			if headDate:
				d = headDate[0].split(',')
				d.reverse()
				key = d[0].strip()
				global dayCache
				dayCache.update({key: (headDate, self.daylist)})
				if config.plugins.serienRec.planerCacheEnabled.value:
					writePlanerData(2)

		self.loading = False
		self['title'].setText("")
		self.chooseMenuList.setList(map(self.buildTopThirtyList, self.daylist[0]))
		self.ErrorMsg = "'getCover()'"
		self.getCover()

	def buildPlanerList(self, entry):
		(regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id) = entry
		
		imageNone = "%simages/black.png" % serienRecMainPath
		imageNeu = "%simages/neu.png" % serienRecMainPath
		imageTimer = "%simages/timer.png" % serienRecMainPath
		imageHDD = "%simages/hdd_icon.png" % serienRecMainPath
		
		if serieAdded == 1:
			seriesColor = parseColor('green').argb()
		elif serieAdded == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None
		if aufnahme:
			seriesColor = parseColor('blue').argb()

		titleColor = timeColor = parseColor('foreground').argb()

		if int(neu) == 0:
			imageNeu = imageNone
			
		if bereits_vorhanden:
			imageHDDTimer = imageHDD
		elif aufnahme:
			imageHDDTimer = imageTimer
		else:
			imageHDDTimer = imageNone
		
		if config.plugins.serienRec.showPicons.value:
			picon = loadPNG(imageNone)
			if sender:
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(sender))
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 5 * skinFactor, 80 * skinFactor, 40 * skinFactor, picon),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330 * skinFactor, 7 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330 * skinFactor, 30 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 100 * skinFactor, 29 * skinFactor, 150 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, transmissionTime, timeColor, timeColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 365 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 365 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 7, 30 * skinFactor, 22 * skinFactor, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 30 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 280 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 29 * skinFactor, 150 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, transmissionTime, timeColor, timeColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 340 * skinFactor, 3, 520 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 340 * skinFactor, 29 * skinFactor, 520 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
				]

	def buildTopThirtyList(self, entry):
		(serien_name, average, serien_id, serieAdded, rank) = entry

		if serieAdded == 1:
			seriesColor = parseColor('green').argb()
		elif serieAdded == 2:
			seriesColor = parseColor('red').argb()
		else:
			seriesColor = None

		title = "%d Abrufe/Tag" % average
		titleColor = parseColor('foreground').argb()

		rank = "%d." % rank

		return [entry,
				(eListboxPythonMultiContent.TYPE_TEXT, 5 * skinFactor, 3, 40 * skinFactor, 26 * skinFactor, 0,
				 RT_HALIGN_RIGHT | RT_VALIGN_CENTER, rank, titleColor, titleColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 70 * skinFactor, 3, 520 * skinFactor, 26 * skinFactor, 0,
				 RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, seriesColor, seriesColor),
				(eListboxPythonMultiContent.TYPE_TEXT, 70 * skinFactor, 29 * skinFactor, 520 * skinFactor,
				 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, titleColor, titleColor)
				]

	def keyOK(self):
		if self.modus == "list":
			if self.loading:
				return

			check = self['menu_list'].getCurrent()
			if check is None:
				return

			if config.plugins.serienRec.screenplaner.value == 1:
				sender = self['menu_list'].getCurrent()[0][7]
				staffel = self['menu_list'].getCurrent()[0][8]
			else:
				sender = None
				staffel = None

			(serien_name, serien_id) = self.getSeriesNameID()
			if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
				boxID = None
			else:
				boxID = config.plugins.serienRec.BoxID.value

			url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(serien_id)
			if self.database.addMarker(url, serien_name, boxID):
				writeLog("\nSerien Marker für ' %s ' wurde angelegt" % serien_name, True)
				self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
				global runAutocheckAtExit
				runAutocheckAtExit = True
				if config.plugins.serienRec.tvplaner_full_check.value:
					config.plugins.serienRec.tvplaner_last_full_check.value = int(0)
					config.plugins.serienRec.tvplaner_last_full_check.save()
					configfile.save()
				if config.plugins.serienRec.openMarkerScreen.value:
					self.session.open(serienRecMarker, serien_name)
			else:
				self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))

	def getCover(self):
		if self.loading:
			return
		
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		(serien_name, serien_id) = self.getSeriesNameID()
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)
		
	def keyRed(self):
		if self.modus == "list":
			if config.plugins.serienRec.screenplaner.value == 1:
				config.plugins.serienRec.screenplaner.value = 2
			else:
				config.plugins.serienRec.screenplaner.value = 1
			config.plugins.serienRec.screenplaner.save()
			configfile.save()
			self.readPlanerData(False)

	def getSeriesNameID(self):
		if config.plugins.serienRec.screenplaner.value == 1:
			serien_name = self['menu_list'].getCurrent()[0][6]
			serien_id = self['menu_list'].getCurrent()[0][14]
		else:
			serien_name = self['menu_list'].getCurrent()[0][0]
			serien_id = self['menu_list'].getCurrent()[0][2]

		return (serien_name, serien_id)

	def keyGreen(self):
		self.session.openWithCallback(self.readPlanerData, serienRecMainChannelEdit)

	def keyYellow(self):
		self.session.openWithCallback(self.readPlanerData, serienRecMarker)
		
	def keyBlue(self):
		self.session.openWithCallback(self.readPlanerData, serienRecTimer)

	def keyCheckLong(self):
		self.session.openWithCallback(self.readPlanerData, serienRecRunAutoCheck, True)

	def keyCheck(self):
		self.session.openWithCallback(self.readPlanerData, serienRecRunAutoCheck, True, config.plugins.serienRec.tvplaner.value)

	def keyLeft(self):
		if self.modus == "list":
			self['menu_list'].pageUp()
			self.getCover()

	def keyRight(self):
		if self.modus == "list":
			self['menu_list'].pageDown()
			self.getCover()

	def keyDown(self):
		if self.modus == "list":
			self['menu_list'].down()
			self.getCover()

	def keyUp(self):
		if self.modus == "list":
			self['menu_list'].up()
			self.getCover()

	def nextPage(self):
		if config.plugins.serienRec.screenplaner.value == 1 and self.page < 4:
			self.page += 1
			self.chooseMenuList.setList(map(self.buildPlanerList, []))
			self.readPlanerData(False)

	def backPage(self):
		if config.plugins.serienRec.screenplaner.value == 1 and not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildPlanerList, []))
		self.readPlanerData(False)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if self.modus == "list":
			try:
				self.displayTimer.stop()
				self.displayTimer = None
			except:
				pass

			global runAutocheckAtExit
			if runAutocheckAtExit and config.plugins.serienRec.runAutocheckAtExit.value:
				singleTimer = eTimer()
				if isDreamOS():
					singleTimer_conn = singleTimer.timeout.connect(serienRecCheckForRecording(self.session, True, False))
				else:
					singleTimer.callback.append(serienRecCheckForRecording(self.session, True, False))
				singleTimer.start(10000, True)
			
			#self.hide()
			#self.showSplashScreen()
			self.close()

def getNextWakeup():
	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value and config.plugins.serienRec.autochecktype.value == "1":
		print "[SerienRecorder] Deep-Standby WakeUp: AN"
		now = time.localtime()
		current_time = int(time.time())
		
		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0], config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

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
		writeLog("\nSerienRecorder Start: %s" % uhrzeit, True)

		def startAutoCheckTimer():
			serienRecCheckForRecording(session, False, False)

		#if initDB():
		if config.plugins.serienRec.autochecktype.value in ("1", "2") and config.plugins.serienRec.timeUpdate.value:
			print "[SerienRecorder] Auto-Check: AN"
			startTimer = eTimer()
			if isDreamOS():
				startTimerConnection = startTimer.timeout.connect(startAutoCheckTimer)
			else:
				startTimer.callback.append(startAutoCheckTimer)
			startTimer.start(60 * 1000, True)
			#serienRecCheckForRecording(session, False, False)
		else:
			print "[SerienRecorder] Auto-Check: AUS"

		#API
		from SerienRecorderResource import addWebInterfaceForDreamMultimedia
		addWebInterfaceForDreamMultimedia(session)



