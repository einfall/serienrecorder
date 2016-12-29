# -*- coding: utf-8 -*-
from __init__ import _

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaTest
from Tools.LoadPixmap import LoadPixmap
from Components.Pixmap import Pixmap
from Components.AVSwitch import AVSwitch
from Screens.InfoBar import MoviePlayer
from Components.PluginComponent import plugins
from Components.Button import Button
from Components.VideoWindow import VideoWindow
from Screens.Screen import Screen
from Plugins.Plugin import PluginDescriptor
from twisted.web.client import getPage
from twisted.web.client import downloadPage
from HTMLParser import HTMLParser

from Components.ServicePosition import ServicePositionGauge
from Tools.NumericalTextInput import NumericalTextInput
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config, ConfigInteger, ConfigSelection, getConfigListEntry, ConfigText, ConfigDirectory, ConfigYesNo, configfile, ConfigSelection, ConfigSubsection, ConfigPIN, NoSave, ConfigNothing, ConfigClock, ConfigSelectionNumber

from Components.ScrollLabel import ScrollLabel
from Components.FileList import FileList
from Components.Sources.StaticText import StaticText

from Screens.HelpMenu import HelpableScreen
from Screens.InputBox import InputBox
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
import Screens.Standby

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, eServiceReference, getDesktop, loadJPG, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM, gPixmapPtr, ePicLoad, eTimer, eServiceCenter
from Tools.Directories import pathExists, fileExists, SCOPE_SKIN_IMAGE, resolveFilename
import sys, os, base64, re, time, shutil, datetime, codecs, urllib, urllib2, random, itertools, traceback
from twisted.web import client, error as weberror
from twisted.internet import reactor, defer
from skin import parseColor, loadSkin, parseFont
import imaplib
import email

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

from ServiceReference import ServiceReference

# Tageditor
from Screens.MovieSelection import getPreferredTagEditor

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
		writeErrorLog("   ReadConfigFile(): Error creating Skin-List")
		pass
	config.plugins.serienRec.SkinType = ConfigSelection(choices = choices, default="") 
	config.plugins.serienRec.showAllButtons = ConfigYesNo(default = False)
	config.plugins.serienRec.DisplayRefreshRate = ConfigInteger(10, (1,60))

	config.plugins.serienRec.piconPath = ConfigText(default="/usr/share/enigma2/picon/", fixed_size=False, visible_width=80)
	
	#config.plugins.serienRec.fake_entry = NoSave(ConfigNothing())
	config.plugins.serienRec.BoxID = ConfigSelectionNumber(1, 16, 1, default = 1)
	config.plugins.serienRec.activateNewOnThisSTBOnly = ConfigYesNo(default = False)
	config.plugins.serienRec.setupType = ConfigSelection(choices = [("0", "einfach"), ("1", "Experte")], default = "0")
	config.plugins.serienRec.seriensubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdirnumerlength = ConfigInteger(1, (1,4))
	config.plugins.serienRec.seasonsubdirfillchar = ConfigSelection(choices = [("0","'0'"), ("<SPACE>", "<SPACE>")], default="0")
	config.plugins.serienRec.justplay = ConfigYesNo(default = False)
	config.plugins.serienRec.justremind = ConfigYesNo(default = False)
	config.plugins.serienRec.zapbeforerecord = ConfigYesNo(default = False)
	config.plugins.serienRec.afterEvent = ConfigSelection(choices = [("0", "nichts"), ("1", "in Standby gehen"), ("2", "in Deep-Standby gehen"), ("3", "automatisch")], default="3")
	config.plugins.serienRec.AutoBackup = ConfigYesNo(default = False)
	config.plugins.serienRec.BackupPath = ConfigText(default = "/media/hdd/SR_Backup/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.deleteBackupFilesOlderThan = ConfigInteger(0, (0,999))
	config.plugins.serienRec.eventid = ConfigYesNo(default = True)
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
	config.plugins.serienRec.imap_mail_age = ConfigInteger(1, (0, 100))
	config.plugins.serienRec.imap_check_interval = ConfigInteger(30, (0, 10000))
	config.plugins.serienRec.tvplaner_create_marker = ConfigYesNo(default = True)
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
	config.plugins.serienRec.ActionOnNew = ConfigSelection(choices = [("0", "keine"), ("1", "benachrichten"), ("4", "suchen")], default="0")
	config.plugins.serienRec.ActionOnNewManuell = ConfigYesNo(default = True)
	config.plugins.serienRec.deleteOlderThan = ConfigInteger(7, (1,99))
	config.plugins.serienRec.planerCacheEnabled = ConfigYesNo(default = True)
	config.plugins.serienRec.planerCacheSize = ConfigInteger((int(config.plugins.serienRec.checkfordays.value)), (1,4))
	config.plugins.serienRec.NoOfRecords = ConfigInteger(1, (1,9))
	config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default = True)
	config.plugins.serienRec.showPicons = ConfigYesNo(default = True)
	config.plugins.serienRec.listFontsize = ConfigSelectionNumber(-5, 35, 1, default = 0)
	config.plugins.serienRec.intensiveTimersuche = ConfigYesNo(default = True)
	config.plugins.serienRec.sucheAufnahme = ConfigYesNo(default = True)
	config.plugins.serienRec.selectNoOfTuners = ConfigYesNo(default = True)
	config.plugins.serienRec.tuner = ConfigInteger(4, (1,8))
	config.plugins.serienRec.logScrollLast = ConfigYesNo(default = False)
	config.plugins.serienRec.logWrapAround = ConfigYesNo(default = False)
	config.plugins.serienRec.TimerName = ConfigSelection(choices = [("0", "<Serienname> - SnnEmm - <Episodentitel>"), ("1", "<Serienname>"), ("2", "SnnEmm - <Episodentitel>")], default="0")
	config.plugins.serienRec.refreshViews = ConfigYesNo(default = True)
	config.plugins.serienRec.defaultStaffel = ConfigSelection(choices = [("0","'Alle'"), ("1", "'Manuell'")], default="0")
	config.plugins.serienRec.openMarkerScreen = ConfigYesNo(default = True)
	config.plugins.serienRec.runAutocheckAtExit = ConfigYesNo(default = False)
	config.plugins.serienRec.showCover = ConfigYesNo(default = False)
	config.plugins.serienRec.showAdvice = ConfigYesNo(default = True)
	config.plugins.serienRec.showStartupInfoText = ConfigYesNo(default = True)
	config.plugins.serienRec.writeErrorLog = ConfigYesNo(default = False)
	
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
	config.plugins.serienRec.version = NoSave(ConfigText(default="032"))
	config.plugins.serienRec.showversion = NoSave(ConfigText(default=SerienRecorderHelpers.SRVERSION))
	config.plugins.serienRec.screenmode = ConfigInteger(0, (0,2))
	config.plugins.serienRec.screenplaner = ConfigInteger(1, (1,5))
	config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))
	config.plugins.serienRec.addedListSorted = ConfigYesNo(default = False)
	config.plugins.serienRec.wishListSorted = ConfigYesNo(default = False)
	config.plugins.serienRec.serienRecShowSeasonBegins_filter = ConfigYesNo(default = False)
	config.plugins.serienRec.dbversion = NoSave(ConfigText(default="3.2"))

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
	if config.plugins.serienRec.screenplaner.value is 1 and config.plugins.serienRec.screenmode.value > 2:
		config.plugins.serienRec.screenmode.value = 2
	if config.plugins.serienRec.screenplaner.value > 1 and config.plugins.serienRec.screenmode.value > 1:
		config.plugins.serienRec.screenmode.value = 1

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
serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

#dbTmp = sqlite3.connect("%sSR_Tmp.db" % config.plugins.serienRec.databasePath.value)
dbTmp = sqlite3.connect(":memory:")
dbTmp.text_factory = lambda x: str(x.decode("utf-8"))
dbSerRec = None
#dbSerRec = sqlite3.connect(serienRecDataBase)
# dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))

autoCheckFinished = False
refreshTimer = None
refreshTimerConnection = None
coverToShow = None
runAutocheckAtExit = False
startTimer = None
startTimerConnection = None

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


SR_OperatingManual = "file://usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html"

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

class PiconLoader:
	def __init__(self):
		self.nameCache = { }
		self.partnerbox = re.compile('1:0:[0-9a-fA-F]+:[1-9a-fA-F]+[0-9a-fA-F]*:[1-9a-fA-F]+[0-9a-fA-F]*:[1-9a-fA-F]+[0-9a-fA-F]*:[1-9a-fA-F]+[0-9a-fA-F]*:[0-9a-fA-F]+:[0-9a-fA-F]+:[0-9a-fA-F]+:http')

	def getPicon(self, sRef):
		if not sRef:
			return None

		pos = sRef.rfind(':')
		pos2 = sRef.rfind(':', 0, pos)
		if pos - pos2 == 1 or self.partnerbox.match(sRef) is not None:
			sRef = sRef[:pos2].replace(':', '_')
		else:
			sRef = sRef[:pos].replace(':', '_')
		pngname = self.nameCache.get(sRef, "")
		if pngname == "":
			pngname = self.findPicon(sRef)
			if pngname != "":
				self.nameCache[sRef] = pngname
			if pngname == "": # no picon for service found
				pngname = self.nameCache.get("default", "")
				if pngname == "": # no default yet in cache..
					pngname = self.findPicon("picon_default")
					if pngname != "":
						self.nameCache["default"] = pngname
		if fileExists(pngname):
			return pngname
		else:
			return None

	def findPicon(self, sRef):
		pngname = "%s%s.png" % (config.plugins.serienRec.piconPath.value, sRef)
		if not fileExists(pngname):
			pngname = ""
		return pngname

	def piconPathChanged(self, configElement = None):
		self.nameCache.clear()


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

def getCover(self, serien_name, serien_id):
	if not config.plugins.serienRec.showCover.value:
		return

	serien_name = serien_name.encode('utf-8')
	serien_nameCover = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)
	png_serien_nameCover = "%s%s.png" % (config.plugins.serienRec.coverPath.value, serien_name)

	if self is not None: 
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
		if self is not None: showCover(serien_nameCover, self, serien_nameCover)
	elif serien_id:
		try:
			posterURL = SeriesServer().doGetCoverURL(int(serien_id), serien_name)
			if posterURL:
				downloadPage(posterURL, serien_nameCover).addCallback(showCover, self, serien_nameCover, False).addErrback(getCoverDataError, self, serien_nameCover)
		except:
			getCoverDataError("failed", self, serien_nameCover)

def getCoverDataError(error, self, serien_nameCover):
	if self is not None: 
		writeLog("Fehler bei: %s (%s)" % (self.ErrorMsg, serien_nameCover), True)
		writeErrorLog("   getCover(): %s\n   Serie: %s\n   %s" % (error, serien_nameCover, self.ErrorMsg))
		print "[SerienRecorder] Fehler bei: %s" % self.ErrorMsg
	else:
		ErrorMsg = "Cover-Suche (%s) auf 'Wunschliste.de' erfolglos" % serien_nameCover
		writeLog("Fehler: %s" % ErrorMsg, True)
		writeErrorLog("   getCover(): %s\n   Serie: %s" % (error, serien_nameCover))
		print "[SerienRecorder] Fehler: %s" % ErrorMsg
	writeLog("      %s" % str(error), True)
	print error

def showCover(data, self, serien_nameCover, force_show=True):
	if self is not None: 
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
			if isDreamboxOS:
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
		if not fileExists(logFile):
			try:
				open(logFile, 'w').close()
			except (IOError, OSError) as e:
				logFile = SERIENRECORDER_LOGFILENAME % serienRecMainPath
				open(logFile, 'w').close()

		writeLogFile = open(logFile, "a")
		writeLogFile.write('%s\n' % (text))
		writeLogFile.close()

def writeLogFilter(logtype, text, forceWrite=False):
	global logFile
	if config.plugins.serienRec.writeLog.value or forceWrite:
		if not fileExists(logFile):
			try:
				open(logFile, 'w').close()
			except (IOError, OSError) as e:
				logFile = SERIENRECORDER_LOGFILENAME % serienRecMainPath
				open(logFile, 'w').close()

		writeLogFile = open(logFile, "a")
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
	check_stbRef = check_stbRef.split(":")[4:7]
	
	timers = serienRecAddTimer.getTimersTime()
	for name, begin, end, service_ref in timers:
		#print name, begin, end, service_ref
		if not ((int(check_end) < int(begin)) or (int(check_start) > int(end))):
			#print "between"
			cRecords += 1

			service_ref = str(service_ref).split(":")[4:7]
			if str(check_stbRef).lower() == str(service_ref).lower():
				if int(check_start) > int(begin): begin = check_start
				if int(check_end) < int(end): end = check_end
				lTimerStart.update({int(begin) : int(end)})
				lTimerEnd.update({int(end) : int(begin)})
			else:
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
		return (len(lTuner) < int(config.plugins.serienRec.tuner.value))

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
			
def checkTimerAdded(sender, serie, staffel, episode, start_unixtime):
	global dbSerRec
	#"Castle" "S03E20 - Die Pizza-Connection" "1392997800" "1:0:19:EF76:3F9:1:C00000:0:0:0:" "kabel eins"
	found = False
	cCursor = dbSerRec.cursor()
	sql = "SELECT * FROM AngelegteTimer WHERE LOWER(webChannel)=? AND LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
	cCursor.execute(sql, (sender.lower(), serie.lower(), str(staffel).lower(), episode.lower(), int(start_unixtime)-(int(STBHelpers.getEPGTimeSpan())*60), int(start_unixtime)+(int(STBHelpers.getEPGTimeSpan())*60)))
	row = cCursor.fetchone()
	if row:
		found = True
	cCursor.close()
	return found

def checkAlreadyAdded(serie, staffel, episode, title = None, searchOnlyActiveTimers = False):
	global dbSerRec
	Anzahl = 0
	cCursor = dbSerRec.cursor()
	if searchOnlyActiveTimers:
		if title is None:
			cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND TimerAktiviert=1", (serie.lower(), str(staffel).lower(), episode.lower()))
		else:
			cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND TimerAktiviert=1", (serie.lower(), str(staffel).lower(), episode.lower(), title.lower()))
	else:
		if title is None:
			cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serie.lower(), str(staffel).lower(), episode.lower()))
		else:
			cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=?", (serie.lower(), str(staffel).lower(), episode.lower(), title.lower()))
	(Anzahl,) = cCursor.fetchone()	
	cCursor.close()
	return Anzahl

def getAlreadyAdded(serie, searchOnlyActiveTimers = False):
	global dbSerRec
	cCursor = dbSerRec.cursor()
	if searchOnlyActiveTimers:
		cCursor.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE LOWER(Serie)=? AND TimerAktiviert=1 ORDER BY Staffel, Episode", (serie.lower(),))
	else:
		cCursor.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE LOWER(Serie)=? ORDER BY Staffel, Episode", (serie.lower(),))

	rows = cCursor.fetchall()
	cCursor.close()
	return rows

def getDirname(serien_name, staffel):
	global dbSerRec
	if config.plugins.serienRec.seasonsubdirfillchar.value == '<SPACE>':
		seasonsubdirfillchar = ' '
	else:
		seasonsubdirfillchar = config.plugins.serienRec.seasonsubdirfillchar.value
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
	row = cCursor.fetchone()
	if not row:
		dirname = config.plugins.serienRec.savetopath.value
		dirname_serie = dirname
		if config.plugins.serienRec.seriensubdir.value:
			dirname = "%s%s/" % (dirname, "".join(i for i in serien_name if i not in "\/:*?<>|."))
			dirname_serie = dirname
			if config.plugins.serienRec.seasonsubdir.value:
				dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
	else: 
		(dirname, seasonsubdir) = row
		if dirname:
			if not re.search('.*?/\Z', dirname):
				dirname = "%s/" % dirname
			dirname_serie = dirname
			if ((seasonsubdir == -1) and config.plugins.serienRec.seasonsubdir.value) or (seasonsubdir == 1):
				dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
		else:
			dirname = config.plugins.serienRec.savetopath.value
			dirname_serie = dirname
			if config.plugins.serienRec.seriensubdir.value:
				dirname = "%s%s/" % (dirname, "".join(i for i in serien_name if i not in "\/:*?<>|."))
				dirname_serie = dirname
				if config.plugins.serienRec.seasonsubdir.value:
					dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
		
	cCursor.close()
	return dirname, dirname_serie

def CreateDirectory(serien_name, staffel):
	(dirname, dirname_serie) = getDirname(serien_name, staffel)
	if not fileExists(dirname):
		print "[SerienRecorder] Erstelle Verzeichnis %s" % dirname
		writeLog("Erstelle Verzeichnis: ' %s '" % dirname)
		try:
			os.makedirs(dirname)
		except OSError as e:
			if e.error != 17:
				raise

	if fileExists(dirname):
		if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)) and not fileExists("%sfolder.jpg" % dirname_serie):
			shutil.copy("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name), "%sfolder.jpg" % dirname_serie)
		if config.plugins.serienRec.seasonsubdir.value:
			if config.plugins.serienRec.seasonsubdirfillchar.value == '<SPACE>':
				seasonsubdirfillchar = ' '
			else:
				seasonsubdirfillchar = config.plugins.serienRec.seasonsubdirfillchar.value
			if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name)) and not fileExists("%sfolder.jpg" % dirname):
				shutil.copy("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_name), "%sfolder.jpg" % dirname)



def getMargins(serien_name, webSender):
	global dbSerRec
	cCursor = dbSerRec.cursor()
	#writeLog("getMargins: ' %s ' @ ' %s " % (serien_name, webSender))
	cCursor.execute("SELECT MAX(IFNULL(SerienMarker.Vorlaufzeit, -1), IFNULL(Channels.Vorlaufzeit, -1)), MAX(IFNULL(SerienMarker.Nachlaufzeit, -1), IFNULL(Channels.Nachlaufzeit, -1)) FROM SerienMarker, Channels WHERE LOWER(SerienMarker.Serie)=? AND LOWER(Channels.WebChannel)=?", (serien_name.lower(), webSender.lower()))
	data = cCursor.fetchone()
	if not data:
		margin_before = config.plugins.serienRec.margin_before.value
		margin_after = config.plugins.serienRec.margin_after.value
	else:
		(margin_before, margin_after) = data

	if margin_before is None or margin_before is -1:
		margin_before = config.plugins.serienRec.margin_before.value

	if margin_after is None or margin_after is -1:
		margin_after = config.plugins.serienRec.margin_after.value

	cCursor.close()
	return margin_before, margin_after


def getVPS(webSender, serien_name):
	global dbSerRec
	result = 0
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT CASE WHEN SerienMarker.vps IS NOT NULL AND SerienMarker.vps IS NOT '' THEN SerienMarker.vps ELSE Channels.vps END as vps FROM Channels,SerienMarker WHERE LOWER(Channels.WebChannel)=? AND LOWER(SerienMarker.Serie)=?", (webSender.lower(), serien_name.lower()))
	raw = cCursor.fetchone()
	if raw:
		(result,) = raw
	cCursor.close()
	return (bool(result & 0x1), bool(result & 0x2))

def getTags(serien_name):
	global dbSerRec
	tags = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT tags FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
	data = cCursor.fetchone()
	if data:
		(tagString,) = data
		if tagString is not None and len(tagString) > 0:
			tags = pickle.loads(tagString)
	cCursor.close()
	return tags

def encode(key, clear):
	enc = []
	for i in range(len(clear)):
		key_c = key[i % len(key)]
		enc_c = chr((ord(clear[i]) + ord(key_c)) % 256)
		enc.append(enc_c)
	return base64.urlsafe_b64encode("".join(enc))

def decode(key, enc):
	dec = []
	enc = base64.urlsafe_b64decode(enc)
	for i in range(len(enc)):
		key_c = key[i % len(key)]
		dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
		dec.append(dec_c)
	return "".join(dec)

def getmac(interface):
	try:
		mac = open('/sys/class/net/'+interface+'/address').readline()
	except:
		mac = "00:00:00:00:00:00"
	return mac[0:17]

def getEmailData():
	# extract all html parts
	def get_html(email_message_instance):
	 maintype = email_message_instance.get_content_maintype()
	 if maintype == 'multipart':
		 for part in email_message_instance.get_payload():
			 if part.get_content_type() == 'text/html':
				 return part.get_payload()

	writeLog("\n---------' Laden TV-Planer E-Mail '---------------------------------------------------------------\n", True)
	
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
	
	if config.plugins.serienRec.imap_mail_age.value < 1 and config.plugins.serienRec.imap_mail_age.value > 100:
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
		mail.login(decode(getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value), decode(getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))
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
	
	date = (datetime.date.today() - datetime.timedelta(config.plugins.serienRec.imap_mail_age.value)).strftime("%d-%b-%Y")
	searchstr = '(SENTSINCE {date} HEADER Subject "' + config.plugins.serienRec.imap_mail_subject.value + '")'
	searchstr = searchstr.format(date=date)
	try:
		result, data = mail.uid('search', None, searchstr)
	
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
	class TVPlaner_HTMLParser(HTMLParser):
		def __init__(self):
			HTMLParser.__init__(self)
			self.state = 'start'
			self.date = ()
			self.transmission = []
			self.transmissions = []
		def handle_starttag(self, tag, attrs):
			# print "Encountered a start tag:", tag, attrs
			if self.state == 'start' and tag == 'h3':
				self.state = 'date_h3'
			elif self.state == 'date_h3_time' and tag == 'span':
				self.state = 'time_span'
			elif self.state == 'transmission_table' and tag == 'table':
				self.state = 'transmission'
			elif self.state == 'transmission' and tag == 'tr':
				self.state = 'transmission_start'
			elif self.state == 'transmission_start' and tag == 'strong':
				# next day - reset
				self.state = 'transmission'
			elif self.state == 'transmission_serie' and tag == 'strong':
				self.data = ''
			elif self.state == 'transmission_season' and tag == 'span' :
				for name, value in attrs:
					if name == 'title' and value == 'Episode':
						self.transmission.append('')
						self.state = 'transmission_episode'
						break

		def handle_endtag(self, tag):
			# print "Encountered an end tag :", tag
			if self.state == 'transmission_end' and tag == 'tr':
				self.transmissions.append(tuple(self.transmission))
				self.transmission = []
				self.state = 'transmission'
			elif self.state == 'time_span' and tag == 'span':
				# no time - starting at 00:00 Uhr
				self.date = ( self.date, '00:00' )
				self.state = 'transmission_table'
			elif self.state == 'transmission_serie' and tag == 'strong':
				# append collected data
				self.transmission.append(self.data)
				self.state = 'transmission_season'
			elif self.state == 'transmission_season' and tag == 'div':
				# no season and no episode
				# title has been already pushed as season - insert empty season and episode before last
				self.transmission.insert(self.transmission[-1], '')
				self.transmission.insert(self.transmission[-1], '')
				self.state = 'transmission_desc'
			elif self.state == 'transmission_episode' and tag == 'div':
				# season but no episode
				self.transmission.append('')
				self.state = 'transmission_title'

		def handle_data(self, data):
			# print "Encountered some data  : %r" % data
			if self.state == 'date_h3':
				# match date
				# 'TV-Planer f=C3=BCr Donnerstag, den 22.12.2016 '
				date_regexp=re.compile('TV-Planer.*?den (.*?) ')
				self.date = date_regexp.findall(data)[0]
				self.state = 'date_h3_time'
			elif self.state == 'time_span':
				# match time
				# ' (ab 05:00 Uhr)'
				time_regexp=re.compile(' \(ab (.*?) Uhr')
				self.date = ( self.date, time_regexp.findall(data)[0] )
				self.state = 'transmission_table'
			elif self.state == 'transmission_start':
				# match start time
				time_regexp=re.compile('(.*?) Uhr')
				time = time_regexp.findall(data)
				if len(time) > 0:
					self.transmission.append(time[0])
					self.state = 'transmission_serie'
				else:
					self.state = 'error'
			elif self.state == 'transmission_serie':
				# match serie
				self.data += data
			elif self.state == 'transmission_season':
				# match season
				self.transmission.append(data)
				self.state = 'transmission_episode'
			elif self.state == 'transmission_episode':
				# match episode
				self.transmission.append(data)
				self.state = 'transmission_title'
			elif self.state == 'transmission_title':
				# match title
				self.transmission.append(data)
				self.state = 'transmission_desc'
			elif self.state == 'transmission_desc':
				# match description
				if data != 'FREE-TV NEU' and data != "NEU":
					self.transmission.append(data)
					self.state = 'transmission_endtime'
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
	html = html.replace('=\r\n', '').replace('\r\n','').replace('=3D', '=')
	
	parser = TVPlaner_HTMLParser()
	html = parser.unescape(html).encode('utf-8')
	if html is None or len(html) == 0:
		writeLog("TV-Planer: leeres HTML nach HTMLParser", True)
		return None
	try:
		parser.feed(html)
		print parser.date
		print parser.transmissions
	except:
		writeLog("TV-Planer: HTML Parsing schlug fehl", True)
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
	for starttime, seriesname, season, episode, titel, description, endtime, channel in parser.transmissions:
		if season == '' and episode == '':
			# this is probably a movie - ignore for now
			continue
		
		transmission = [ doReplaces(seriesname) ]
		# channel
		channel = channel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').strip()
		transmission += [ doReplaces(channel) ]
#		Channel = []
#		cCursor = dbSerRec.cursor()
#		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (channel.lower(),))
#		row = cCursor.fetchone()
#		if row:
#			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
#			if altstbChannel == "":
#				altstbChannel = stbChannel
#				altstbRef = stbRef
#			elif stbChannel == "":
#				stbChannel = altstbChannel
#				stbRef = altstbRef
#			Channel.append((webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status))
#		else:
#			writeLog("TV-Planer: STB-Sender für %r nicht gefunden" % channel, True)
#			print "[SerienRecorder] ' %s - S%sE%s - %s - %r -> STB sender not found'" % (seriesname, str(season).zfill(2), str(episode).zfill(2), titel, webChannel)
#			continue
#		cCursor.close()
#		if not Channel:
#			writeLog("TV-Planer: STB-Sender für %r nicht gefunden" % channel, True)
#			print "[SerienRecorder] ' %s - S%sE%s - %s - %r -> STB sender not found'" % (seriesname, str(season).zfill(2), str(episode).zfill(2), titel, webChannel)
#			continue
#		try:
#			transmission += [ Channel[0][1] ]
#		except:
#			writeLog("TV-Planer: STB-Sender für %r nicht gefunden, %r" % (channel, Channel), True)
#			print "[SerienRecorder] ' %s - S%sE%s - %s - %r -> STB sender not found'" % (seriesname, str(season).zfill(2), str(episode).zfill(2), titel, webChannel)
#			continue
		# start time
		(hour, minute) = starttime.split(':')
		transmissionstart_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionstart_unix < liststarttime_unix:
			transmissionstart_unix = TimeHelpers.getRealUnixTimeWithDayOffset(minute, hour, day, month, year, 1)
		transmission += [ transmissionstart_unix ]
		# end time
		(hour, minute) = endtime.split('.')
		transmissionend_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionend_unix < liststarttime_unix:
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
		transmission += [ doReplaces(titel) ]
		# last
		transmission += [ '0' ]
		# store in dictionary transmissiondict[seriesname] = [ seriesname: [ transmission 0 ], [ transmission 1], .... ]
		if seriesname in transmissiondict:
			transmissiondict[seriesname] += [ transmission ]
		else:
			transmissiondict[seriesname] = [ transmission ]
		writeLog("' %s - S%sE%s - %s - %r '" % (seriesname, str(season).zfill(2), str(episode).zfill(2), titel, channel), True)
		print "[SerienRecorder] ' %s - S%sE%s - %s - %r '" % (seriesname, str(season).zfill(2), str(episode).zfill(2), titel, channel)
	
	if config.plugins.serienRec.tvplaner_create_marker.value:
		cCursor = dbSerRec.cursor()
		for seriesname in transmissiondict.keys():
			cCursor.execute("SELECT Serie FROM SerienMarker WHERE LOWER(Serie)=?", (seriesname.lower(),))
			row = cCursor.fetchone()
			if not row:
				# marker isn't in database, creat new marker
				# url stored in marker isn't the final one, it is corrected later
				try:
					cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (seriesname, 'url'))
					dbSerRec.commit()
					writeLog("' %s - Serien Marker erzeugt '" % seriesname, True)
					print "[SerienRecorder] ' %s - Serien Marker erzeugt '" % seriesname
				except:
					writeLog("' %s - Serien Marker konnte nicht erzeugt werden '" % seriesname, True)
					print "[SerienRecorder] ' %s - Serien Marker konnte nicht erzeugt werden '" % seriesname
		cCursor.close()
	
	return transmissiondict

def getSpecialsAllowed(serien_name):
	global dbSerRec
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT AlleStaffelnAb, TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
	data = cCursor.fetchone()
	if data:
		(AlleStaffelnAb, TimerForSpecials,) = data
		if int(AlleStaffelnAb) == 0:
			TimerForSpecials = True
		elif not str(TimerForSpecials).isdigit():
			TimerForSpecials = False
	else:
		TimerForSpecials = False
	cCursor.close()
	return bool(TimerForSpecials)
	
def getTimeSpan(serien_name):
	global dbSerRec
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT AufnahmezeitVon, AufnahmezeitBis FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
	data = cCursor.fetchone()
	if data:
		(fromTime, toTime) = data
		if not str(fromTime).isdigit():
			fromTime = (config.plugins.serienRec.globalFromTime.value[0]*60)+config.plugins.serienRec.globalFromTime.value[1]
		if not str(toTime).isdigit():
			toTime = (config.plugins.serienRec.globalToTime.value[0]*60)+config.plugins.serienRec.globalToTime.value[1]
	else:
		fromTime = (config.plugins.serienRec.globalFromTime.value[0]*60)+config.plugins.serienRec.globalFromTime.value[1]
		toTime = (config.plugins.serienRec.globalToTime.value[0]*60)+config.plugins.serienRec.globalToTime.value[1]
	cCursor.close()
	
	return (fromTime, toTime)
	
# Serien may contain a list of selected series names
def getMarker(Serien=None):
	global dbSerRec
	return_list = []
	cCursor = dbSerRec.cursor()
	serienselect = ''
	if Serien is not None and len(Serien) > 0:
		serienselect = 'WHERE Serie IN ('
		for i in range(len(Serien) - 1):
			serienselect += '"' + Serien[i] + '",'
		serienselect += '"' + Serien[-1] + '")'
	print "[SerienRecorder] %s" % serienselect
	cCursor.execute("SELECT ID, Serie, Url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays FROM SerienMarker " + serienselect + " ORDER BY Serie")
	cMarkerList = cCursor.fetchall()
	for row in cMarkerList:
		(ID, serie, url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays) = row
		SerieEnabled = True
		cTmp = dbSerRec.cursor()
		cTmp.execute("SELECT ErlaubteSTB FROM STBAuswahl WHERE ID=?", (ID,))
		row2 = cTmp.fetchone()
		if row2:
			(ErlaubteSTB,) = row2
			if ErlaubteSTB is not None and not (ErlaubteSTB & (1 << (int(config.plugins.serienRec.BoxID.value) - 1))):
				SerieEnabled = False
		else:
			cTmp.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
			dbSerRec.commit()
		cTmp.close()

		if alleSender:
			sender = ['Alle',]
		else:
			sender = []
			cSender = dbSerRec.cursor()
			cSender.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=? ORDER BY LOWER(ErlaubterSender)", (ID,))
			cSenderList = cSender.fetchall()
			if len(cSenderList) > 0:
				sender = list(zip(*cSenderList)[0])
			cSender.close()
			
		if AlleStaffelnAb == -2:			# 'Manuell'
			staffeln = [AlleStaffelnAb,]
		else:
			staffeln = []
			cStaffel = dbSerRec.cursor()
			cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
			cStaffelList = cStaffel.fetchall()
			if len(cStaffelList) > 0:
				staffeln = list(zip(*cStaffelList)[0])
			if AlleStaffelnAb < 999999:
				staffeln.insert(0, -1)
				staffeln.append(AlleStaffelnAb)
			cStaffel.close()
			
		AnzahlAufnahmen = int(config.plugins.serienRec.NoOfRecords.value)
		if str(AnzahlWiederholungen).isdigit():
			AnzahlAufnahmen = int(AnzahlWiederholungen)
					
		return_list.append((serie, url, staffeln, sender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays))
	cCursor.close()
	return return_list

def getActiveServiceRefs():
	global dbSerRec
	serviceRefs = {}
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT WebChannel, ServiceRef FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
	for row in cCursor:
		(webChannel,serviceRef) = row

		serviceRefs[webChannel] = serviceRef
	cCursor.close()
	return serviceRefs

def getWebSenderAktiv():
	global dbSerRec
	fSender = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT WebChannel FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
	for row in cCursor:
		(webChannel,) = row
		fSender.append(webChannel)
	cCursor.close()
	return fSender

def getMarkerChannels(seriesID):
	global dbSerRec
	fSender = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=? ORDER BY LOWER(ErlaubterSender)", (seriesID,))
	for row in cCursor:
		(webChannel,) = row
		fSender.append(webChannel)

	if len(fSender) == 0:
		fSender = getWebSenderAktiv()
	cCursor.close()
	return fSender

def addToWishlist(seriesName, fromEpisode, toEpisode, season):
	global dbSerRec
	if int(fromEpisode) != 0 or int(toEpisode) != 0:
		AnzahlAufnahmen = int(config.plugins.serienRec.NoOfRecords.value)
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT AnzahlWiederholungen FROM SerienMarker WHERE LOWER(Serie)=?", (seriesName.lower(),))
		row = cCursor.fetchone()
		if row:
			(AnzahlWiederholungen,) = row
			if str(AnzahlWiederholungen).isdigit():
				AnzahlAufnahmen = int(AnzahlWiederholungen)
		for i in range(int(fromEpisode), int(toEpisode)+1):
			print "[SerienRecorder] %s Staffel: %s Episode: %s " % (str(seriesName), str(season), str(i))
			cCursor.execute("SELECT * FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (seriesName.lower(), season.lower(), str(i).zfill(2).lower()))
			row = cCursor.fetchone()
			if not row:
				cCursor.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?)", (seriesName, season, str(i).zfill(2), AnzahlAufnahmen))
		dbSerRec.commit()
		cCursor.close()
		return True
	else:
		return False

def addToAddedList(seriesName, fromEpisode, toEpisode, season, episodeTitle):
	global dbSerRec
	# Es gibt Episodennummern die nicht nur aus Zahlen bestehen, z.B. 14a
	# um solche Folgen in die Datenbank zu bringen wird hier eine Unterscheidung gemacht.
	if fromEpisode == toEpisode:
		cCursor = dbSerRec.cursor()
		cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (seriesName, season, str(fromEpisode).zfill(2), episodeTitle, (int(time.time())), "", "", 0, 1))
		dbSerRec.commit()
		cCursor.close()
	else:
		if int(fromEpisode) != 0 or int(toEpisode) != 0:
			cCursor = dbSerRec.cursor()
			for i in range(int(fromEpisode), int(toEpisode)+1):
				print "[SerienRecorder] %s Staffel: %s Episode: %s " % (str(seriesName), str(season), str(i))
				cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (seriesName, season, str(i).zfill(2), episodeTitle, (int(time.time())), "", "", 0, 1))
			dbSerRec.commit()
			cCursor.close()
			return True
		else:
			return False

def initDB():
	global dbSerRec

	# If database is at old default location (SerienRecorder plugin folder) we have to move the db to new default location
	if fileExists("%sSerienRecorder.db" % serienRecMainPath):
		shutil.move("%sSerienRecorder.db" % serienRecMainPath, serienRecDataBase)

	try:
		dbSerRec = sqlite3.connect(serienRecDataBase)
		dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	except:
		writeLog("Fehler beim Initialisieren der Datenbank")
		Notifications.AddPopup("SerienRecorder Datenbank kann nicht initialisiert werden.\nSerienRecorder wurde beendet!", MessageBox.TYPE_INFO, timeout=10)
		return False

	if os.path.getsize(serienRecDataBase) == 0:
		cCursor = dbSerRec.cursor()
		cCursor.execute('''CREATE TABLE IF NOT EXISTS dbInfo (Key TEXT NOT NULL UNIQUE, 
														   Value TEXT NOT NULL DEFAULT "")''') 

		cCursor.execute('''CREATE TABLE IF NOT EXISTS NeuerStaffelbeginn (Serie TEXT NOT NULL, 
																		  Staffel TEXT, 
																		  Sender TEXT NOT NULL, 
																		  StaffelStart TEXT NOT NULL, 
																		  UTCStaffelStart INTEGER, 
																		  Url TEXT NOT NULL, 
																		  CreationFlag INTEGER DEFAULT 1)''') 

		cCursor.execute('''CREATE TABLE IF NOT EXISTS Channels (WebChannel TEXT NOT NULL UNIQUE, 
																STBChannel TEXT NOT NULL DEFAULT "", 
																ServiceRef TEXT NOT NULL DEFAULT "", 
																alternativSTBChannel TEXT NOT NULL DEFAULT "", 
																alternativServiceRef TEXT NOT NULL DEFAULT "", 
																Erlaubt INTEGER DEFAULT 0, 
																Vorlaufzeit INTEGER DEFAULT NULL, 
																Nachlaufzeit INTEGER DEFAULT NULL,
																vps INTEGER DEFAULT 0)''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS SerienMarker (ID INTEGER PRIMARY KEY AUTOINCREMENT, 
																	Serie TEXT NOT NULL, 
																	Url TEXT NOT NULL, 
																	AufnahmeVerzeichnis TEXT, 
																	AlleStaffelnAb INTEGER DEFAULT 0, 
																	alleSender INTEGER DEFAULT 1, 
																	Vorlaufzeit INTEGER DEFAULT NULL, 
																	Nachlaufzeit INTEGER DEFAULT NULL, 
																	AufnahmezeitVon INTEGER DEFAULT NULL,
																	AufnahmezeitBis INTEGER DEFAULT NULL, 
																	AnzahlWiederholungen INTEGER DEFAULT NULL,
																	preferredChannel INTEGER DEFAULT 1,
																	useAlternativeChannel INTEGER DEFAULT -1,
																	AbEpisode INTEGER DEFAULT 0,
																	Staffelverzeichnis INTEGER DEFAULT -1,
																	TimerForSpecials INTEGER DEFAULT 0,
																	vps INTEGER DEFAULT NULL,
																	excludedWeekdays INTEGER DEFAULT NULL,
																	tags TEXT)''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS SenderAuswahl (ID INTEGER, 
																	 ErlaubterSender TEXT NOT NULL, 
																	 FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS StaffelAuswahl (ID INTEGER, 
																	  ErlaubteStaffel INTEGER, 
																	  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																  ErlaubteSTB INTEGER, 
																  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer (Serie TEXT NOT NULL, 
																	  Staffel TEXT, 
																	  Episode TEXT, 
																	  Titel TEXT, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  ServiceRef TEXT NOT NULL, 
																	  webChannel TEXT NOT NULL, 
																	  EventID INTEGER DEFAULT 0,
																	  TimerAktiviert INTEGER DEFAULT 1)''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  webChannel TEXT NOT NULL)''')

		cCursor.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																  Staffel TEXT NOT NULL, 
																  Episode TEXT NOT NULL,
																  AnzahlWiederholungen INTEGER DEFAULT NULL)''')

		cCursor.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('Version', ?)", (config.plugins.serienRec.dbversion.value,))	
		dbSerRec.commit()
		cCursor.close()

		ImportFilesToDB()
	else:
		dbVersionMatch = False
		dbIncompatible = False

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
		tables = cCursor.fetchall()
		for table in tables:
			if table[0] == "dbInfo":
				cCursor.execute("SELECT Key, Value FROM dbInfo WHERE Key='Version'")
				raw = cCursor.fetchone()
				if raw:
					(dbKey, dbValue) = raw
					if dbValue == config.plugins.serienRec.dbversion.value:
						dbVersionMatch = True
						break
					elif dbValue > config.plugins.serienRec.dbversion.value:
						writeLog("Datenbankversion nicht kompatibel: SerienRecorder Version muss mindestens %s sein." % dbValue)
						Notifications.AddPopup("Die SerienRecorder Datenbank ist mit dieser Version nicht kompatibel.\nAktualisieren Sie mindestens auf Version %s!" % dbValue, MessageBox.TYPE_INFO, timeout=10)
						dbIncompatible = True
		cCursor.close()

		# Database incompatible - do cleanup
		if dbIncompatible:
			dbSerRec.close()
			return False

		if not dbVersionMatch:
			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD AbEpisode INTEGER DEFAULT 0')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD Staffelverzeichnis INTEGER DEFAULT -1')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD TimerForSpecials INTEGER DEFAULT 0')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE AngelegteTimer ADD TimerAktiviert INTEGER DEFAULT 1')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE Channels ADD vps INTEGER DEFAULT 0')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD vps INTEGER DEFAULT NULL')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD excludedWeekdays INTEGER DEFAULT NULL')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			try:
				cCursor = dbSerRec.cursor()
				cCursor.execute('ALTER TABLE SerienMarker ADD tags TEXT')
				dbSerRec.commit()
				cCursor.close()
			except:
				pass

			cCursor = dbSerRec.cursor()
			cCursor.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																		  StartZeitstempel INTEGER NOT NULL, 
																		  webChannel TEXT NOT NULL)''')

			cCursor.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																	  Staffel TEXT NOT NULL, 
																	  Episode TEXT NOT NULL,
																	  AnzahlWiederholungen INTEGER DEFAULT NULL)''')

			cCursor.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																	  ErlaubteSTB INTEGER, 
																	  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

			dbSerRec.commit()
			cCursor.close()
			
			updateDB()

	# Analyze database for query optimizer
	cCursor = dbSerRec.cursor()
	cCursor.execute("ANALYZE")
	cCursor.execute("ANALYZE sqlite_master")
	cCursor.close()

	dbSerRec.close()
	dbSerRec = sqlite3.connect(serienRecDataBase)
	dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	return True
	
def updateDB():
	global dbSerRec
	global serienRecDataBase
	dbSerRec.close()
	shutil.move(serienRecDataBase, "%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value)
	dbSerRec = sqlite3.connect("%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value)

	serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
	dbNew = sqlite3.connect(serienRecDataBase)
	cNew = dbNew.cursor()

	cNew.execute('''CREATE TABLE IF NOT EXISTS dbInfo (Key TEXT NOT NULL UNIQUE, 
													   Value TEXT NOT NULL DEFAULT "")''') 

	cNew.execute('''CREATE TABLE IF NOT EXISTS Channels (WebChannel TEXT NOT NULL UNIQUE, 
														 STBChannel TEXT NOT NULL DEFAULT "", 
														 ServiceRef TEXT NOT NULL DEFAULT "", 
														 alternativSTBChannel TEXT NOT NULL DEFAULT "", 
														 alternativServiceRef TEXT NOT NULL DEFAULT "", 
														 Erlaubt INTEGER DEFAULT 0, 
														 Vorlaufzeit INTEGER DEFAULT NULL, 
														 Nachlaufzeit INTEGER DEFAULT NULL,
														 vps INTEGER DEFAULT 0)''')
															
	cNew.execute('''CREATE TABLE IF NOT EXISTS SerienMarker (ID INTEGER PRIMARY KEY AUTOINCREMENT, 
															 Serie TEXT NOT NULL, 
															 Url TEXT NOT NULL, 
															 AufnahmeVerzeichnis TEXT, 
															 AlleStaffelnAb INTEGER DEFAULT 0, 
															 alleSender INTEGER DEFAULT 1, 
															 Vorlaufzeit INTEGER DEFAULT NULL, 
															 Nachlaufzeit INTEGER DEFAULT NULL, 
															 AufnahmezeitVon INTEGER DEFAULT NULL,
															 AufnahmezeitBis INTEGER DEFAULT NULL, 
															 AnzahlWiederholungen INTEGER DEFAULT NULL,
															 preferredChannel INTEGER DEFAULT 1,
															 useAlternativeChannel INTEGER DEFAULT -1,
															 AbEpisode INTEGER DEFAULT 0,
															 Staffelverzeichnis INTEGER DEFAULT -1,
															 TimerForSpecials INTEGER DEFAULT 0,
															 vps INTEGER DEFAULT NULL,
															 excludedWeekdays INTEGER DEFAULT NULL,
															 tags TEXT)''')

	cNew.execute('''CREATE TABLE IF NOT EXISTS SenderAuswahl (ID INTEGER, 
															  ErlaubterSender TEXT NOT NULL, 
															  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')
																 
	cNew.execute('''CREATE TABLE IF NOT EXISTS StaffelAuswahl (ID INTEGER, 
															   ErlaubteStaffel INTEGER, 
															   FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

	cNew.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
														   ErlaubteSTB INTEGER, 
														   FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

	cNew.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer (Serie TEXT NOT NULL, 
															   Staffel TEXT, 
															   Episode TEXT, 
															   Titel TEXT, 
															   StartZeitstempel INTEGER NOT NULL, 
															   ServiceRef TEXT NOT NULL, 
															   webChannel TEXT NOT NULL, 
															   EventID INTEGER DEFAULT 0,
															   TimerAktiviert INTEGER DEFAULT 1)''')

	cNew.execute('''CREATE TABLE IF NOT EXISTS NeuerStaffelbeginn (Serie TEXT NOT NULL, 
																   Staffel TEXT, 
																   Sender TEXT NOT NULL, 
																   StaffelStart TEXT NOT NULL, 
																   UTCStaffelStart INTEGER, 
																   Url TEXT NOT NULL, 
																   CreationFlag INTEGER DEFAULT 1)''') 

	cNew.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
															   StartZeitstempel INTEGER NOT NULL, 
															   webChannel TEXT NOT NULL)''')

	cNew.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
														   Staffel TEXT NOT NULL, 
														   Episode TEXT NOT NULL,
														   AnzahlWiederholungen INTEGER DEFAULT NULL)''')

	dbNew.commit()

	cNew.execute("ATTACH DATABASE '%sSerienRecorder_old.db' AS 'dbOLD'" % config.plugins.serienRec.databasePath.value)
	cNew.execute("INSERT INTO Channels SELECT * FROM dbOLD.Channels ORDER BY WebChannel")
	cNew.execute("INSERT INTO NeuerStaffelbeginn SELECT * FROM dbOLD.NeuerStaffelbeginn")
	cNew.execute("INSERT INTO AngelegteTimer SELECT * FROM dbOLD.AngelegteTimer")
	cNew.execute("INSERT INTO TimerKonflikte SELECT * FROM dbOLD.TimerKonflikte")
	cNew.execute("INSERT INTO Merkzettel SELECT * FROM dbOLD.Merkzettel")
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT * FROM SerienMarker ORDER BY Serie")
	raw = cCursor.fetchall()
	for each in raw:
		(ID,Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials,vps,excludedWeekdays,tags) = each
		if preferredChannel != 1:
			preferredChannel = 0
		if useAlternativeChannel != 1:
			useAlternativeChannel = -1
		if not str(AbEpisode).isdigit():
			AbEpisode = 0
		if not str(Staffelverzeichnis).isdigit():
			Staffelverzeichnis = -1
		if AlleStaffelnAb == 0:
			TimerForSpecials = 0
		elif not str(TimerForSpecials).isdigit():
			TimerForSpecials = 0
		elif TimerForSpecials == -1:
			TimerForSpecials = config.plugins.serienRec.TimerForSpecials.value
		if (AufnahmezeitVon <= 23) and (AufnahmezeitBis <= 23):
			if str(AufnahmezeitVon).isdigit():
				AufnahmezeitVon *= 60
			else:
				AufnahmezeitVon = None
			if str(AufnahmezeitBis).isdigit():
				AufnahmezeitBis *= 60
				AufnahmezeitBis += 59
			else:
				AufnahmezeitBis = None
		
		sql = "INSERT INTO SerienMarker (Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials,vps,excludedWeekdays,tags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
		cNew.execute(sql, (Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials,vps,excludedWeekdays,tags))
		newID = cNew.lastrowid
		cCursor.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=?", (ID,))
		for raw2 in cCursor:
			(ErlaubterSender,) = raw2
			cNew.execute("INSERT INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?,?)", (newID,ErlaubterSender))
		cCursor.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=?", (ID,))
		for raw2 in cCursor:
			(ErlaubteStaffel,) = raw2
			cNew.execute("INSERT INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?,?)", (newID,ErlaubteStaffel))
		cCursor.execute("SELECT ErlaubteSTB FROM STBAuswahl WHERE ID=?", (ID,))
		raw2 = cCursor.fetchone()
		if raw2:
			(ErlaubteSTB,) = raw2
			cNew.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (newID,ErlaubteSTB))
		else:
			cNew.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (newID,0xFFFF))
		
	cCursor.close()
	cNew.execute("DETACH DATABASE 'dbOLD'")
	cNew.execute("DELETE FROM dbInfo WHERE Key='Version'")	
	cNew.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('Version', ?)", (config.plugins.serienRec.dbversion.value,))	
	dbNew.commit()
	cNew.close()
	dbNew.close()
	dbSerRec.close()

	config.plugins.serienRec.fromTime = NoSave(ConfigInteger(00, (0,23)))
	config.plugins.serienRec.toTime = NoSave(ConfigInteger(23, (0,23)))
	config.plugins.serienRec.globalFromTime.value[0] = int(config.plugins.serienRec.fromTime.value)
	config.plugins.serienRec.globalFromTime.value[1] = 0
	config.plugins.serienRec.globalToTime.value[0] = int(config.plugins.serienRec.toTime.value)
	config.plugins.serienRec.globalToTime.value[1] = 59
	config.plugins.serienRec.fromTime.save()
	config.plugins.serienRec.toTime.save()
	config.plugins.serienRec.globalFromTime.save()
	config.plugins.serienRec.globalToTime.save()
	configfile.save()

	dbSerRec = sqlite3.connect(serienRecDataBase)
	dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	
	# Codierung Channels korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps FROM Channels")
	for row in cCursor:
		(WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) = row
		try:
			WebChannelNew = WebChannel.decode('utf-8')
		except:
			WebChannelNew = decodeISO8859_1(WebChannel)
			cTmp = dbSerRec.cursor()
			cTmp.execute ("DELETE FROM Channels WHERE WebChannel=?", (WebChannel,))
			sql = "INSERT OR IGNORE INTO Channels (WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) VALUES (?,?,?,?,?,?,?,?,?)"
			cTmp.execute(sql, (WebChannelNew,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps))
			cTmp.close()

		try:
			STBChannelNew = STBChannel.decode('utf-8')
		except:
			STBChannelNew = decodeISO8859_1(STBChannel)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE Channels SET STBChannel=? WHERE STBChannel=?", (STBChannelNew,STBChannel))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f

	# Codierung AngelegteTimer korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT Serie,Titel,webChannel FROM AngelegteTimer")
	for row in cCursor:
		(Serie,Titel,webChannel) = row
		try:
			SerieNew = Serie.decode('utf-8')
		except:
			SerieNew = decodeISO8859_1(Serie)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			TitelNew = Titel.decode('utf-8')
		except:
			TitelNew = decodeISO8859_1(Titel)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Titel=? WHERE Titel=?", (TitelNew,Titel))
			cTmp.close()
			
		try:
			webChannelNew = webChannel.decode('utf-8')
		except:
			webChannelNew = decodeISO8859_1(webChannel)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET webChannel=? WHERE webChannel=?", (webChannelNew,webChannel))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f
	
	# Codierung SerienMarker korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT Serie FROM SerienMarker")
	for row in cCursor:
		(Serie,) = row
		try:
			SerieNew = Serie.decode('utf-8')
		except:
			SerieNew = decodeISO8859_1(Serie)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE SerienMarker SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f
		
	# Codierung SenderAuswahl korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT ErlaubterSender FROM SenderAuswahl")
	for row in cCursor:
		(ErlaubterSender,) = row
		try:
			ErlaubterSenderNew = ErlaubterSender.decode('utf-8')
		except:
			ErlaubterSenderNew = decodeISO8859_1(ErlaubterSender)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE SenderAuswahl SET ErlaubterSender=? WHERE ErlaubterSender=?", (ErlaubterSenderNew,ErlaubterSender))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f
		
	# Codierung NeuerStaffelbeginn korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT Serie,Sender FROM NeuerStaffelbeginn")
	for row in cCursor:
		(Serie,Sender) = row
		try:
			SerieNew = Serie.decode("utf-8")
		except:
			SerieNew = decodeISO8859_1(Serie)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			SenderNew = Sender.decode('utf-8')
		except:
			SenderNew = decodeISO8859_1(Sender)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Sender=? WHERE Sender=?", (SenderNew,Sender))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f

	cCursor = dbSerRec.cursor()
	cCursor.execute("VACUUM")
	dbSerRec.commit()
	cCursor.close()
	
def ImportFilesToDB():
	channelFile = "%schannels" % serienRecMainPath
	addedFile = "%sadded" % serienRecMainPath
	timerFile = "%stimer" % serienRecMainPath
	markerFile = "%smarker" % serienRecMainPath

	if fileExists(channelFile):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if not row:
			cCursor.execute("DELETE FROM Channels")
			readChannel = open(channelFile, "r")
			for rawData in readChannel.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(webChannel, stbChannel, stbRef, status) = data[0]
				if stbChannel == "Nicht gefunden":
					stbChannel = ""
				if stbRef == "serviceref":
					stbRef = ""
				cCursor.execute("INSERT OR IGNORE INTO Channels (WebChannel, STBChannel, ServiceRef, Erlaubt) VALUES (?, ?, ?, ?)", (webChannel, stbChannel, stbRef, status))
			readChannel.close()
		dbSerRec.commit()
		cCursor.close()
		
		shutil.move(channelFile, "%s_old" % channelFile)
		#os.remove(channelFile)
		
		# Codierung Channels korrigieren
		f = dbSerRec.text_factory
		dbSerRec.text_factory = str
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps FROM Channels")
		for row in cCursor:
			(WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) = row
			try:
				WebChannelNew = WebChannel.decode('utf-8')
			except:
				WebChannelNew = decodeISO8859_1(WebChannel)
				cTmp = dbSerRec.cursor()
				cTmp.execute ("DELETE FROM Channels WHERE WebChannel=?", (WebChannel,))
				sql = "INSERT OR IGNORE INTO Channels (WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) VALUES (?,?,?,?,?,?,?,?,?)"
				cTmp.execute(sql, (WebChannelNew,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps))
				cTmp.close()

			try:
				STBChannelNew = STBChannel.decode('utf-8')
			except:
				STBChannelNew = decodeISO8859_1(STBChannel)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE Channels SET STBChannel=? WHERE STBChannel=?", (STBChannelNew,STBChannel))
				cTmp.close()
				
		cCursor.close()
		dbSerRec.commit()
		dbSerRec.text_factory = f

	if fileExists(addedFile):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM AngelegteTimer")
		row = cCursor.fetchone()
		if not row:
			readAdded = open(addedFile, "r")
			for rawData in readAdded.readlines():
				data = rawData.strip().rsplit(" ", 1)
				serie = data[0]
				try:
					data = re.findall('"S(.*?)E(.*?)"', '"%s"' % data[1], re.S)
				except:
					continue
				(staffel, episode) = data[0]
				if str(staffel).isdigit():
					staffel = int(staffel)
				cCursor.execute('INSERT OR IGNORE INTO AngelegteTimer (Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel) VALUES (?, ?, ?, "", 0, "", "")', (serie, staffel, episode))
			readAdded.close()
		dbSerRec.commit()
		cCursor.close()
		
		shutil.move(addedFile, "%s_old" % addedFile)
		#os.remove(addedFile)

		# Codierung AngelegteTimer korrigieren
		f = dbSerRec.text_factory
		dbSerRec.text_factory = str
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Titel FROM AngelegteTimer")
		for row in cCursor:
			(Serie,Titel) = row
			try:
				SerieNew = Serie.decode('utf-8')
			except:
				SerieNew = decodeISO8859_1(Serie)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
				cTmp.close()
				
			try:
				TitelNew = Titel.decode('utf-8')
			except:
				TitelNew = decodeISO8859_1(Titel)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Titel=? WHERE Titel=?", (TitelNew,Titel))
				cTmp.close()
				
		cCursor.close()
		dbSerRec.commit()
		dbSerRec.text_factory = f

	if fileExists(timerFile):
		cCursor = dbSerRec.cursor()
		readTimer = open(timerFile, "r")
		for rawData in readTimer.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, xtitle, start_time, stbRef, webChannel) = data[0]
			data = re.findall('"S(.*?)E(.*?) - (.*?)"', '"%s"' % xtitle, re.S)
			(staffel, episode, title) = data[0]
			if str(staffel).isdigit():
				staffel = int(staffel)
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serie.lower(), str(staffel).lower(), episode.lower()))
			if not cCursor.fetchone():
				sql = "INSERT OR IGNORE INTO AngelegteTimer (Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel) VALUES (?, ?, ?, ?, ?, ?, ?)"
				cCursor.execute(sql, (serie, staffel, episode, title, start_time, stbRef, webChannel))
			else:
				sql = "UPDATE OR IGNORE AngelegteTimer SET Titel=?, StartZeitstempel=?, ServiceRef=?, webChannel=? WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?"
				cCursor.execute(sql, (title, start_time, stbRef, webChannel, serie.lower(), str(staffel).lower(), episode.lower()))
		readTimer.close()
		dbSerRec.commit()
		cCursor.close()
		
		shutil.move(timerFile, "%s_old" % timerFile)
		#os.remove(timerFile)
		
		# Codierung AngelegteTimer korrigieren
		f = dbSerRec.text_factory
		dbSerRec.text_factory = str
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie,Titel,webChannel FROM AngelegteTimer")
		for row in cCursor:
			(Serie,Titel,webChannel) = row
			try:
				SerieNew = Serie.decode('utf-8')
			except:
				SerieNew = decodeISO8859_1(Serie)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
				cTmp.close()
				
			try:
				TitelNew = Titel.decode('utf-8')
			except:
				TitelNew = decodeISO8859_1(Titel)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Titel=? WHERE Titel=?", (TitelNew,Titel))
				cTmp.close()
				
			try:
				webChannelNew = webChannel.decode('utf-8')
			except:
				webChannelNew = decodeISO8859_1(webChannel)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET webChannel=? WHERE webChannel=?", (webChannelNew,webChannel))
				cTmp.close()
				
		cCursor.close()
		dbSerRec.commit()
		dbSerRec.text_factory = f
		
	if fileExists(markerFile):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker")
		row = cCursor.fetchone()
		if not row:
			readMarker = open(markerFile, "r")
			for rawData in readMarker.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie, url, staffeln, sender) = data[0]
				staffeln = staffeln.replace("[","").replace("]","").replace("'","").replace(" ","").split(",")
				AlleStaffelnAb = 999999
				if "Manuell" in staffeln:
					AlleStaffelnAb = -2
					staffeln = []
				elif "Alle" in staffeln:
					AlleStaffelnAb = 0
					staffeln = []
				else:
					if "folgende" in staffeln:
						staffeln.remove("folgende")
						staffeln.sort(key=int, reverse=True)
						AlleStaffelnAb = int(staffeln[0])
						staffeln = staffeln[1:]
						
					staffeln.sort(key=int)

				sender = sender.replace("[","").replace("]","").replace("'","").split(",")
				alleSender = 0
				if "Alle" in sender:
					alleSender = 1
					sender = []
				else:
					sender.sort()

				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, ?, -1)", (serie, url, AlleStaffelnAb, alleSender))
				ID = cCursor.lastrowid
				if len(staffeln) > 0:
					IDs = [ID,]*len(staffeln)					
					staffel_list = zip(IDs, staffeln)
					cCursor.executemany("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", staffel_list)
				if len(sender) > 0:
					IDs = [ID,]*len(sender)					
					sender_list = zip(IDs, sender)
					cCursor.executemany("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", sender_list)
				cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
			readMarker.close()
		dbSerRec.commit()
		cCursor.close()
		
		shutil.move(markerFile, "%s_old" % markerFile)
		#os.remove(markerFile)

		# Codierung SerienMarker korrigieren
		f = dbSerRec.text_factory
		dbSerRec.text_factory = str
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie FROM SerienMarker")
		for row in cCursor:
			(Serie,) = row
			try:
				SerieNew = Serie.decode('utf-8')
			except:
				SerieNew = decodeISO8859_1(Serie)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE SerienMarker SET Serie=? WHERE Serie=?", (SerieNew,Serie))
				cTmp.close()
				
		cCursor.close()
		dbSerRec.commit()
		dbSerRec.text_factory = f
			
		# Codierung SenderAuswahl korrigieren
		f = dbSerRec.text_factory
		dbSerRec.text_factory = str
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ErlaubterSender FROM SenderAuswahl")
		for row in cCursor:
			(ErlaubterSender,) = row
			try:
				ErlaubterSenderNew = ErlaubterSender.decode('utf-8')
			except:
				ErlaubterSenderNew = decodeISO8859_1(ErlaubterSender)
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE SenderAuswahl SET ErlaubterSender=? WHERE ErlaubterSender=?", (ErlaubterSenderNew,ErlaubterSender))
				cTmp.close()
				
		cCursor.close()
		dbSerRec.commit()
		dbSerRec.text_factory = f
		
	# Codierung NeuerStaffelbeginn korrigieren
	f = dbSerRec.text_factory
	dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT Serie,Sender FROM NeuerStaffelbeginn")
	for row in cCursor:
		(Serie,Sender) = row
		try:
			SerieNew = Serie.decode("utf-8")
		except:
			SerieNew = decodeISO8859_1(Serie)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			SenderNew = Sender.decode('utf-8')
		except:
			SenderNew = decodeISO8859_1(Sender)
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Sender=? WHERE Sender=?", (SenderNew,Sender))
			cTmp.close()
			
	cCursor.close()
	dbSerRec.commit()
	dbSerRec.text_factory = f

	cCursor = dbSerRec.cursor()
	cCursor.execute("VACUUM")
	dbSerRec.commit()
	cCursor.close()
	
	return True

def writePlanerData():
	if not os.path.exists("%stmp/" % serienRecMainPath):
		try:
			os.makedirs("%stmp/" % serienRecMainPath)
		except:
			pass
	if os.path.isdir("%stmp/" % serienRecMainPath):
		try:
			os.chmod("%stmp/planer_%s" % (serienRecMainPath, config.plugins.serienRec.screenplaner.value), 0o666)
		except:
			pass

		f = open("%stmp/planer_%s" % (serienRecMainPath, config.plugins.serienRec.screenplaner.value), "wb")
		try:
			p = pickle.Pickler(f, 2)
			global dayCache
			p.dump(dayCache)
		except:
			pass
		f.close()

		try:
			os.chmod("%stmp/planer_%s" % (serienRecMainPath, config.plugins.serienRec.screenplaner.value), 0o666)
		except:
			pass

def readPlanerData():
	global dayCache
	dayCache.clear()
	
	planerFile = "%stmp/planer_%s" % (serienRecMainPath, config.plugins.serienRec.screenplaner.value)
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
					a0(b)
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
		print "[SerienRecorder] try to temove enigma2 Timer:", serien_name, start_time
		
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
		writeLog("Versuche Timer anzulegen: ' %s - %s '" % (name, dirname))
		return {
			"result": True,
			"message": "Timer '%s' added" % name,
			"eit" : eit
		}

class serienRecCheckForRecording():

	instance = None
	epgrefresh_instance = None

	def __init__(self, session, manuell, tvplaner_manuell=False):
		assert not serienRecCheckForRecording.instance, "Go is a singleton class!"
		serienRecCheckForRecording.instance = self
		self.session = session
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
			
		cTmp = dbTmp.cursor()
		cTmp.execute('''CREATE TABLE IF NOT EXISTS GefundeneFolgen (CurrentTime INTEGER,
																	FutureTime INTEGER,
																	SerieName TEXT,
																	Staffel TEXT, 
																	Episode TEXT, 
																	SeasonEpisode TEXT,
																	Title TEXT,
																	LabelSerie TEXT, 
																	webChannel TEXT, 
																	stbChannel TEXT, 
																	ServiceRef TEXT, 
																	StartTime INTEGER,
																	EndTime INTEGER,
																	EventID INTEGER,
																	alternativStbChannel TEXT, 
																	alternativServiceRef TEXT, 
																	alternativStartTime INTEGER,
																	alternativEndTime INTEGER,
																	alternativEventID INTEGER,
																	DirName TEXT,
																	AnzahlAufnahmen INTEGER,
																	AufnahmezeitVon INTEGER,
																	AufnahmezeitBis INTEGER,
																	vomMerkzettel INTEGER DEFAULT 0,
																	excludedWeekdays INTEGER DEFAULT NULL)''')

		dbTmp.commit()
		cTmp.close()

		if config.plugins.serienRec.autochecktype.value == "0":
			writeLog("Auto-Check ist deaktiviert - nur manuelle Timersuche", True)
		elif config.plugins.serienRec.autochecktype.value == "1":
			writeLog("Auto-Check wird zur gewählten Uhrzeit gestartet", True)
		elif config.plugins.serienRec.autochecktype.value == "2":
			writeLog("Auto-Check wird nach dem EPGRefresh ausgeführt", True)

		if not self.manuell and config.plugins.serienRec.autochecktype.value == "1" and config.plugins.serienRec.timeUpdate.value:
			deltatime = self.getNextAutoCheckTimer(lt)
			refreshTimer = eTimer()
			if isDreamboxOS:
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
				writeLog("EPGRefresh not installed! " + str(e), True)

	def setEPGRefreshCallback(self, configentry = None):
		try:
			if self.epgrefresh_instance:
				if config.plugins.serienRec.autochecktype.value == "2":
					self.epgrefresh_instance.addFinishNotifier(self.startCheck)
				else:
					self.epgrefresh_instance.removeFinishNotifier(self.startCheck)
		except Exception as e:
			writeLog("EPGRefresh (v2.1.1 or higher) not installed! " + str(e), True)

	@staticmethod
	def getNextAutoCheckTimer(lt):
		acttime = (lt[3] * 60 + lt[4])
		deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
		if acttime < deltime:
			deltatime = deltime - acttime
		else:
			deltatime = abs(1440 - acttime + deltime)
		return deltatime

	def startCheck(self, manuell=False, tvplaner_manuell=False):
		self.manuell = manuell
		self.tvplaner_manuell = tvplaner_manuell
		print "%s[SerienRecorder] settings:%s" % (self.color_print, self.color_end)
		print "manuell:", manuell
		print "tvplaner_manuell:", tvplaner_manuell
		print "uhrzeit check:", config.plugins.serienRec.timeUpdate.value

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		global dbSerRec
		global refreshTimer
		global refreshTimerConnection
		global isDreamboxOS
		global logFile
		global logFileSave

		logFile = SERIENRECORDER_LOGFILENAME % config.plugins.serienRec.LogFilePath.value
		checkFileAccess()
		if config.plugins.serienRec.longLogFileName.value:
			logFileSave = SERIENRECORDER_LONG_LOGFILENAME % (config.plugins.serienRec.LogFilePath.value, str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))

		writeLog("\n---------' %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)

		if not self.manuell and not initDB():
			self.askForDSB()
			return

		cCursor = dbSerRec.cursor()

		cCursor.execute("SELECT * FROM SerienMarker")
		row = cCursor.fetchone()
		if not row and not config.plugins.serienRec.tvplaner and not config.plugins.serienRec.tvplaner_create_marker:
			writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle SerienMarker leer."
			writeLog("Es sind keine Serien-Marker vorhanden - Auto-Check kann nicht ausgeführt werden.", True)
			writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			cCursor.close()
			self.askForDSB()
			return

		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if not row:
			writeLog("\n---------' Starte Auto-Check um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[SerienRecorder] check: Tabelle Channels leer."
			writeLog("Es wurden keine Sender zugeordnet - Auto-Check kann nicht ausgeführt werden.", True)
			writeLog("---------' Auto-Check beendet '---------------------------------------------------------------------------------------", True)
			cCursor.close()
			self.askForDSB()
			return
		cCursor.close()

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
			if isDreamboxOS:
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(((deltatime * 60) + random.randint(0, int(config.plugins.serienRec.maxDelayForAutocheck.value)*60)) * 1000, True)

			print "%s[SerienRecorder] Auto-Check Uhrzeit-Timer gestartet.%s" % (self.color_print, self.color_end)
			print "%s[SerienRecorder] Verbleibende Zeit: %s Stunden%s" % (self.color_print, TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), self.color_end)
			writeLog("Auto-Check Uhrzeit-Timer gestartet.", True)
			writeLog("Verbleibende Zeit: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)

		if config.plugins.serienRec.AutoBackup.value:
			# Remove old backups
			if config.plugins.serienRec.deleteBackupFilesOlderThan.value > 0:
				writeLog("Entferne alte Backup-Dateien und erzeuge neues Backup.", True)
				now = time.time()
				logFolderPattern = re.compile('\d{4}\d{2}\d{2}\d{2}\d{2}')
				for root, dirs, files in os.walk(config.plugins.serienRec.BackupPath.value, topdown=False):
					for name in dirs:
						if logFolderPattern.match(name) and os.stat(os.path.join(root, name)).st_ctime < (now - config.plugins.serienRec.deleteBackupFilesOlderThan.value * 24 * 60 * 60):
							shutil.rmtree(os.path.join(root, name), True)
							writeLog("Lösche Ordner: %s" % os.path.join(root, name), True)

			BackupPath = "%s%s%s%s%s%s/" % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
			if not os.path.exists(BackupPath):
				try:
					os.makedirs(BackupPath)
				except:
					pass
			if os.path.isdir(BackupPath):
				if fileExists(serienRecDataBase):
					f = dbSerRec.text_factory
					dbSerRec.close()
					shutil.copy(serienRecDataBase, BackupPath)
					dbSerRec = sqlite3.connect(serienRecDataBase)
					dbSerRec.text_factory = f
				if fileExists(logFile):
					shutil.copy(logFile, BackupPath)
				if fileExists("/etc/enigma2/timers.xml"):
					shutil.copy("/etc/enigma2/timers.xml", BackupPath)
				if fileExists("%sConfig.backup" % serienRecMainPath):
					shutil.copy("%sConfig.backup" % serienRecMainPath, BackupPath)
				saveEnigmaSettingsToFile(BackupPath)
				for filename in os.listdir(BackupPath):
					os.chmod(os.path.join(BackupPath, filename), 0o777)
				
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("DELETE FROM TimerKonflikte WHERE StartZeitstempel<=?", (int(time.time()),))
		dbSerRec.commit()
		cCursor.close()
		
		if self.manuell:
			print "\n---------' Starte Auto-Check um %s (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Auto-Check um %s (manuell) '-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
		else:
			print "\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte Auto-Check um %s (auto)'-------------------------------------------------------------------------------\n" % self.uhrzeit, True)
			if config.plugins.serienRec.showNotification.value in ("1", "3"):
				Notifications.AddPopup("SerienRecorder Suchlauf nach neuen Timern wurde gestartet.", MessageBox.TYPE_INFO, timeout=3, id="Suchlauf wurde gestartet")

		if config.plugins.serienRec.writeLogVersion.value:
			writeLog("STB Type: %s\nImage: %s" % (STBHelpers.getSTBType(), STBHelpers.getImageVersionString()), True)
		writeLog("SR Version: %s" % config.plugins.serienRec.showversion.value, True)
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
			writeLog("\nKeine Verbindung ins Internet. Auto-Check wurde abgebrochen!!\n", True)

			# Statistik
			self.speedEndTime = time.clock()
			speedTime = (self.speedEndTime - self.speedStartTime)
			writeLog("---------' Auto-Check beendet ( Ausführungsdauer: %s Sek.)'-------------------------------------------------------------------------" % str(speedTime), True)
			print "---------' Auto-Check beendet ( Ausführungsdauer: %s Sek.)'----------------------------------------------------------------------------" % str(speedTime)

			if config.plugins.serienRec.longLogFileName.value:
				shutil.copy(logFile, logFileSave)

			global autoCheckFinished
			autoCheckFinished = True

			# in den deep-standby fahren.
			self.askForDSB()
			return
		
		
		# suche nach neuen Serien, Covern und Planer-Cache
		if ((config.plugins.serienRec.ActionOnNew.value != "0") and ((not self.manuell) or config.plugins.serienRec.ActionOnNewManuell.value)) or ((not self.manuell) and (config.plugins.serienRec.firstscreen.value == "0") and config.plugins.serienRec.planerCacheEnabled.value):
			self.startCheck2()
		else:
			self.startCheck3()

	def startCheck2(self):
		writeLog("\nLaden der SerienPlaner-Daten gestartet ...", True)

		webChannels = getWebSenderAktiv()
		markers = getAllMarkers()
		for daypage in range(int(config.plugins.serienRec.planerCacheSize.value)):
			try:
				planerData = SeriesServer().doGetPlanerData(int(config.plugins.serienRec.screenplaner.value), int(daypage), webChannels)
				self.processPlanerData(planerData, markers, daypage)
			except:
				writeLog("Fehler beim Abrufen und Verarbeiten der SerienPlaner-Daten [%s]\n" % str(daypage), True)

		self.postProcessPlanerData()
		writeLog("... Laden der SerienPlaner-Daten beendet\n", True)

		self.startCheck3()

	def processPlanerData(self, data, markers, daypage):
		if not data or len(data) == 0:
			raise
		daylist = [[],[],[]]

		headDate = [data["date"]]
		txt = headDate[0].split(",")
		(day, month, year) = txt[1].split(".")
		UTCDatum = TimeHelpers.getRealUnixTime(0, 0, day, month, year)

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			timers = getTimer(daypage)

		for event in data["events"]:
			aufnahme = False
			serieAdded = 0
			start_h = event["time"][:+2]
			start_m = event["time"][+3:]
			start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, daypage)

			serien_name = doReplaces(event["name"].encode("utf-8"))
			serien_name_lower = serien_name.lower()
			sender = event["channel"]
			title = event["title"].encode("utf-8")
			staffel = event["season"]
			episode = event["episode"]
			serien_id = event["id"]

			if (config.plugins.serienRec.ActionOnNew.value != "0") and ((not self.manuell) or config.plugins.serienRec.ActionOnNewManuell.value):
				if str(episode).isdigit():
					if int(episode) == 1:
						if not serien_name_lower in markers:
							cCursor = dbSerRec.cursor()
							cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND LOWER(Staffel)=?", (serien_name.lower(), str(staffel).lower()))
							row = cCursor.fetchone()
							if not row:
								data = (serien_name, staffel, sender, headDate[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id)
								cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url) VALUES (?, ?, ?, ?, ?, ?)", data)
								dbSerRec.commit()

								if not self.manuell:
									self.newSeriesOrEpisodesFound = True
									if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
										self.MessageList.append(("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, -1, "Neue Episode"))
										Notifications.AddPopup("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, timeout=-1, id="Neue Episode")
							cCursor.close()

						else:
							cCursor = dbSerRec.cursor()
							if str(staffel).isdigit():
								cCursor.execute("SELECT ID, AlleStaffelnAb FROM SerienMarker WHERE LOWER(Serie)=? AND AlleStaffelnAb>=0 AND AlleStaffelnAb<=?", (serien_name.lower(), staffel))
								row = cCursor.fetchone()
								if row:
									(ID, AlleStaffelnAb) = row
									staffeln = []
									cCursor.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
									cStaffelList = cCursor.fetchall()
									if len(cStaffelList) > 0:
										staffeln = zip(*cStaffelList)[0]
									if not staffel in staffeln:
										cCursor = dbSerRec.cursor()
										cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND LOWER(Staffel)=?", (serien_name.lower(), str(staffel).lower()))
										row = cCursor.fetchone()
										if not row:
											data = (serien_name, staffel, sender, headDate[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2")
											cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
											dbSerRec.commit()

											if not self.manuell:
												self.newSeriesOrEpisodesFound = True
												if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
													self.MessageList.append(("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, -1, "Neue Episode"))
													Notifications.AddPopup("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, timeout=-1, id="Neue Episode")
							else:
								cCursor.execute("SELECT TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=? AND TimerForSpecials=0", (serien_name.lower(),))
								row = cCursor.fetchone()
								if not row:
									cCursor = dbSerRec.cursor()
									cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND LOWER(Staffel)=?", (serien_name.lower(), str(staffel).lower()))
									row = cCursor.fetchone()
									if not row:
										data = (serien_name, staffel, sender, headDate[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2")
										cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
										dbSerRec.commit()

										if not self.manuell:
											self.newSeriesOrEpisodesFound = True
											if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
												self.MessageList.append(("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, -1, "Neue Episode"))
												Notifications.AddPopup("Der SerienRecorder hat Serien- / Staffelbeginn gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'", MessageBox.TYPE_INFO, timeout=-1, id="Neue Episode")

							cCursor.close()

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
					(dirname, dirname_serie) = getDirname(serien_name, staffel)
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
				if int(neu) == 1:
					daylist[1].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				if re.search('01', episode, re.S):
					daylist[2].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value and headDate:
			d = headDate[0].split(',')
			d.reverse()
			key = d[0].strip()
			global dayCache
			dayCache.update({key:(headDate, daylist)})

	def postProcessPlanerData(self):
		if (not self.manuell) and config.plugins.serienRec.planerCacheEnabled.value:
			writePlanerData()
			
		if (config.plugins.serienRec.ActionOnNew.value != "0") and ((not self.manuell) or config.plugins.serienRec.ActionOnNewManuell.value):
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie, Staffel, StaffelStart FROM NeuerStaffelbeginn WHERE CreationFlag>0 ORDER BY UTCStaffelStart")
			for row in cCursor:
				(Serie, Staffel, StaffelStart) = row
				if str(Staffel).isdigit():
					writeLog("%d. Staffel von '%s' beginnt am %s" % (int(Staffel), Serie, StaffelStart), True)
				else:
					writeLog("Staffel %s von '%s' beginnt am %s" % (Staffel, Serie, StaffelStart), True)

			if config.plugins.serienRec.ActionOnNew.value != "0":
				lt = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteOlderThan.value)
				cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE UTCStaffelStart<=?", (lt.strftime("%s"),))
				
			dbSerRec.commit()
			cCursor.close()

	def adjustEPGtimes(self, current_time):
		cTimer = dbSerRec.cursor()
		cCursor = dbSerRec.cursor()
		cCursorTmp = dbTmp.cursor()

		writeLog("\n---------' Aktualisiere Timer '-------------------------------------------------------------------------------\n", True)

		##############################
		#
		# try to get eventID (eit) from epgCache
		#
		if config.plugins.serienRec.eventid.value:
			recordHandler = NavigationInstance.instance.RecordTimer
			#writeLog("<< Suche im EPG anhand der Uhrzeit", True)
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>?", (current_time, ))
			for row in cCursor:
				(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row

				new_serien_title = serien_title
				new_serien_time = 0
				cCursorTmp.execute("SELECT SerieName, Staffel, Episode, Title, StartTime FROM GefundeneFolgen WHERE EventID > 0 AND SerieName=? AND Staffel=? AND Episode=?", (serien_name, staffel, episode))
				tmpRow = cCursorTmp.fetchone()
				if tmpRow:
					(new_serien_name, new_staffel, new_episode, new_serien_title, new_serien_time) = tmpRow

				(margin_before, margin_after) = getMargins(serien_name, webChannel)
		
				# event_matches = STBHelpers.getEPGEvent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = STBHelpers.getEPGEvent(['RITBDSE',(stbRef, 0, int(serien_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(serien_time)+(int(margin_before) * 60))
				new_event_matches = None
				if new_serien_time != 0 and eit > 0:
					new_event_matches = STBHelpers.getEPGEvent(['RITBDSE',(stbRef, 0, int(new_serien_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(new_serien_time)+(int(margin_before) * 60))
				if new_event_matches and len(new_event_matches) > 0 and (not event_matches or (event_matches and len(event_matches) == 0)):
					# Old event not found but new one with different start time
					event_matches = new_event_matches
				else:
					# Wenn die Sendung zur ursprünglichen Startzeit im EPG gefunden wurde
					new_serien_time = serien_time

				if event_matches and len(event_matches) > 0:
					title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
					(dirname, dirname_serie) = getDirname(serien_name, staffel)
					for event_entry in event_matches:
						writeLog("' %s - %s '" % (title, dirname))
						eit = int(event_entry[1])
						start_unixtime = int(event_entry[3]) - (int(margin_before) * 60)
						end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
						
						print "[SerienRecorder] try to modify enigma2 Timer:", title, serien_time

						timerUpdated = False
						if str(staffel) is 'S' and str(episode) is '0':
							writeLog("   Timer kann nicht aktualisiert werden @ %s" % webChannel, True)
							break

						try:
							# suche in aktivierten Timern
							timerUpdated = self.updateTimer(recordHandler.timer_list, cTimer, eit, end_unixtime, episode,
							                              new_serien_title, serien_name, serien_time,
							                              staffel, start_unixtime, stbRef, title,
							                              webChannel)

							if not timerUpdated:
								# suche in deaktivierten Timern
								timerUpdated = self.updateTimer(recordHandler.processed_timers, cTimer, eit, end_unixtime, episode,
							                              new_serien_title, serien_name, serien_time,
							                              staffel, start_unixtime, stbRef, title,
							                              webChannel)
						except Exception:
							print "[SerienRecorder] Modifying enigma2 Timer failed:", title, serien_time
							writeLog("' %s ' - Timeraktualisierung fehlgeschlagen @ %s" % (title, webChannel), True)
						if not timerUpdated:
							writeLog("   Timer muss nicht aktualisiert werden @ %s" % webChannel, True)
						break
						
			dbSerRec.commit()


		cCursor.close()
		cTimer.close()

	def updateTimer(self, timer_list, cTimer, eit, end_unixtime, episode, new_serien_title, serien_name, serien_time, staffel, start_unixtime, stbRef, title, webChannel):
		timerUpdated = False
		for timer in timer_list:
			if timer and timer.service_ref:
				# skip all timer with false service ref
				if (str(timer.service_ref).lower() != stbRef.lower()) or timer.begin != int(serien_time):
					continue

				# Timer gefunden, weil auf dem richtigen Sender und Startzeit im Timer entspricht Startzeit in SR DB
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

				if updateEIT or updateStartTime or updateName or updateDescription:
					NavigationInstance.instance.RecordTimer.saveTimer()
					sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=?, Titel=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=?"
					cTimer.execute(sql, (start_unixtime, eit, new_serien_title, serien_time, stbRef.lower()))
					new_start = time.strftime("%d.%m - %H:%M", time.localtime(int(start_unixtime)))
					old_start = time.strftime("%d.%m - %H:%M", time.localtime(int(serien_time)))
					if updateStartTime:
						writeLog("   Startzeit wurde aktualisiert von %s auf %s @ %s" % (old_start, new_start, webChannel), True)
					if updateEIT:
						writeLog("   Event ID wurde aktualisiert von %s auf %s @ %s" % (str(old_eit), str(eit), webChannel), True)
					if updateName:
						writeLog("   Name wurde aktualisiert von %s auf %s @ %s" % (old_timername, timer_name, webChannel), True)
					if updateDescription:
						writeLog("   Beschreibung wurde aktualisiert von %s auf %s @ %s" % (old_timerdescription, timer_description, webChannel), True)
					self.countTimerUpdate += 1
					timerUpdated = True
				break

		return timerUpdated

	def activateTimer(self):
		# versuche deaktivierte Timer zu aktivieren oder auf anderer Box zu erstellen
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE TimerAktiviert=0")
		for row in cCursor:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row
			if eit > 0:
				recordHandler = NavigationInstance.instance.RecordTimer
				try:
					timerFound = False
					# suche in deaktivierten Timern
					for timer in recordHandler.processed_timers:
						if timer and timer.service_ref:
							if (timer.begin == serien_time) and (timer.eit == eit) and (str(timer.service_ref).lower() == stbRef.lower()):
								# versuche deaktivierten Timer zu aktivieren
								(dirname, dirname_serie) = getDirname(serien_name, staffel)
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
										cTimer = dbSerRec.cursor()
										cTimer.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE Serie=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", row)
										dbSerRec.commit()
										cTimer.close()
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
										writeLog("' %s ' - Timer wurde aktiviert -> %s %s @ %s" % (label_serie, show_start, timer_name, webChannel), True)
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
									cTimer = dbSerRec.cursor()
									cTimer.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE Serie=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", row)
									dbSerRec.commit()
									cTimer.close()

									timerFound = True
									break

					if not timerFound:
						# versuche deaktivierten Timer (auf anderer Box) zu erstellen
						(margin_before, margin_after) = getMargins(serien_name, webChannel)

						# get VPS settings for channel
						vpsSettings = getVPS(webChannel, serien_name)

						# get tags from marker
						tags = getTags(serien_name)
						
						epgmatches = []
						epgcache = eEPGCache.getInstance()
						allevents = epgcache.lookupEvent(['IBD',(stbRef, 2, eit, -1)]) or []

						for eventid, begin, duration in allevents:
							if int(begin) == (int(serien_time) + (int(margin_before) * 60)):
								(dirname, dirname_serie) = getDirname(serien_name, staffel)
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
									# Eintrag in das timer file
									cTimer = dbSerRec.cursor()
									cTimer.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE Serie=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", row)
									dbSerRec.commit()
									cTimer.close()
									show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
									writeLog("' %s ' - Timer wurde angelegt -> %s %s @ %s" % (label_serie, show_start, timer_name, webChannel), True)
								break

				except:				
					pass

		dbSerRec.commit()
		cCursor.close()
		
	def startCheck3(self):
		cTmp = dbTmp.cursor()
		cTmp.execute("DELETE FROM GefundeneFolgen")
		dbTmp.commit()
		cTmp.close()
		
		# read channels
		self.senderListe = {}
		for s in self.readSenderListe():
			self.senderListe[s[0].lower()] = s[:]
			
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
		if self.emailData is None:
			self.markers = getMarker()
		else:
			self.markers = getMarker(self.emailData.keys())
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
		downloads = []
		if len(self.markers) > 0:
			writeLog("\n---------' Verarbeite Daten vom Server '---------------------------------------------------------------\n", True)
			webChannels = getWebSenderAktiv()
			for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,SerieEnabled,excludedWeekdays in self.markers:
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
						seriesID = SeriesServer().getSeriesID(serienTitle)
						print "[SerienRecorder] seriesID = %r" % str(seriesID)
						cCursor = dbSerRec.cursor()
						if seriesID != 0:
							Url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(seriesID)
							print "[SerienRecorder] %r %r %r" % (serienTitle, str(seriesID), Url)
							try:
								cCursor.execute("UPDATE SerienMarker SET Url=? WHERE LOWER(Serie)=?", (Url, serienTitle.lower()))
								dbSerRec.commit()
								writeLog("' %s - TV-Planer Marker -> Url %s - Update'" % (serienTitle, Url), True)
								print "[SerienRecorder] ' %s - TV-Planer Marker -> Url %s - Update'" % (serienTitle, Url)
							except:
								writeLog("' %s - TV-Planer Marker -> Url %s - Update failed '" % (serienTitle, Url), True)
								print "[SerienRecorder] ' %s - TV-Planer Marker -> Url %s - Update failed '" % (serienTitle, Url)
							try:
								cCursor.execute("SELECT Serie FROM SerienMarker WHERE LOWER(Serie)=?", (serienTitle.lower(),))
								erlaubteSTB = 0xFFFF
								if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
									erlaubteSTB = 0
									erlaubteSTB |= (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
								cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (cCursor.lastrowid, erlaubteSTB))
#								cCursor.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?) ON DUPLICATE KEY UPDATE ErlaubteSTB=?", (cCursor.lastrowid, erlaubteSTB, erlaubteSTB))
								dbSerRec.commit()
								writeLog("' %s - TV-Planer erlaubte STB -> Update %d '" % (serienTitle, erlaubteSTB), True)
								print "[SerienRecorder] ' %s - TV-Planer erlaubte STB -> Update %d '" % (serienTitle, erlaubteSTB)
							except:
								writeLog("' %s - TV-Planer erlaubte STB -> Update %d failed '" % (serienTitle, erlaubteSTB), True)
								print "[SerienRecorder] ' %s - TV-Planer erlaubt STB -> Update %d failed '" % (serienTitle, erlaubteSTB)
						cCursor.close()
							
					download = retry(1, ds.run, self.downloadTransmissions, seriesID, (int(config.plugins.serienRec.TimeSpanForRegularTimer.value)), markerChannels)
					download.addCallback(self.processTransmission, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays)
					download.addErrback(self.dataError,SerieUrl)
					downloads.append(download)
			
			finished = defer.DeferredList(downloads).addCallback(self.createTimer).addErrback(self.dataError)
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
		if config.plugins.serienRec.tvplaner.value and self.emailData != None and len(self.markers) > 0:
			# check mailbox for TV-Planer EMail and create timer
			writeLog("\n---------' Verarbeite TV-Planer E-Mail '-----------------------------------------------------------\n", True)
			webChannels = getWebSenderAktiv()
			for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,SerieEnabled,excludedWeekdays in self.markers:
				self.countSerien += 1
				if SerieEnabled:
					# Download only if series is enabled
					if 'Alle' in SerieSender:
						markerChannels = webChannels
					else:
						markerChannels = SerieSender
					
					self.countActivatedSeries += 1
					download = retry(0, ds.run, self.downloadEmail, serienTitle, (int(config.plugins.serienRec.TimeSpanForRegularTimer.value)), markerChannels)
					download.addErrback(self.dataError, SerieUrl)
					download.addCallback(self.processTransmission, serienTitle, SerieStaffel, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays)
					download.addErrback(self.dataError, SerieUrl)
					downloads.append(download)
					
			download.addCallbacks(self.createTimer, self.dataError)
		
		# this is only for experts that have data files available in a directory
		# TODO: use saved transmissions for programming timer
		if config.plugins.serienRec.readdatafromfiles.value and len(self.markers) > 0:
			# use this only when WL is down and you have copies of the webpages on disk in serienrecorder/data
			##('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
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
		if config.plugins.serienRec.longLogFileName.value:
			shutil.copy(logFile, logFileSave)
		
		# trigger read of log file
		global autoCheckFinished
		autoCheckFinished = True
		print "checkFinal: autoCheckFinished"
		if config.plugins.serienRec.autochecktype.value == "1":
			lt = time.localtime()
			deltatime = self.getNextAutoCheckTimer(lt)
			writeLog("\nVerbleibende Zeit bis zum nächsten Auto-Check: %s Stunden" % TimeHelpers.td2HHMMstr(datetime.timedelta(minutes=deltatime+int(config.plugins.serienRec.maxDelayForAutocheck.value))), True)
		
		# in den deep-standby fahren.
		self.askForDSB()

	@staticmethod
	def downloadTransmissions(seriesID, timeSpan, markerChannels):
		#print "downloadTransmission"
		try:
			transmissions = SeriesServer().doGetTransmissions(seriesID, timeSpan, markerChannels)
		except:
			print "downloadTransmissions: failed"
			transmissions = None
		return transmissions

	def processTransmission(self, data, serien_name, staffeln, AbEpisode, AnzahlAufnahmen, current_time, future_time, excludedWeekdays=None):
		#print "processTransmissions"
		self.count_url += 1

		if data is None:
			writeLog("Fehler beim Abrufen und Verarbeiten der Ausstrahlungstermine [%s]" % serien_name, True)
			#print "processTransmissions: no Data"
			return

		(fromTime, toTime) = getTimeSpan(serien_name)
		if self.NoOfRecords < AnzahlAufnahmen:
			self.NoOfRecords = AnzahlAufnahmen

		TimeSpan_time = int(future_time)
		if config.plugins.serienRec.forceRecording.value:
			TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400

		# loop over all transmissions
		for current_serien_name, sender, startzeit, endzeit, staffel, episode, title, status in data:
			start_unixtime = startzeit
			end_unixtime = endzeit

			# setze die vorlauf/nachlauf-zeit
			(margin_before, margin_after) = getMargins(serien_name, sender)
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			if not config.plugins.serienRec.forceRecording.value:
				if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not TimeHelpers.allowedTimeRange(fromTime, toTime, start_time, end_time):
						continue

			# if there is no season or episode number it can be a special
			# but if we have more than one special and wunschliste.de does not
			# give us an episode number we are unable to differentiate between these specials
			if not staffel and not episode:
				staffel = "S"
				episode = "0"

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
			elif getSpecialsAllowed(serien_name):
				serieAllowed = True

			vomMerkzettel = False
			if not serieAllowed:
				cCursorTmp = dbSerRec.cursor()
				cCursorTmp.execute("SELECT * FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), str(episode).zfill(2).lower()))
				row = cCursorTmp.fetchone()
				if row:
					writeLog("' %s ' - Timer vom Merkzettel wird angelegt @ %s" % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True
				cCursorTmp.close()

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
			alt_eit, alt_end_unixtime, alt_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, altstbRef)

			(dirname, dirname_serie) = getDirname(serien_name, staffel)

			cCursorTmp = dbTmp.cursor()
			sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, Staffel, Episode, SeasonEpisode, Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, EventID, alternativStbChannel, alternativServiceRef, alternativStartTime, alternativEndTime, alternativEventID, DirName, AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel, excludedWeekdays) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
			cCursorTmp.execute(sql, (current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays))
			cCursorTmp.close()
			#print "processTransmission exit"

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
		
		(fromTime, toTime) = getTimeSpan(serien_name)
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
			(margin_before, margin_after) = getMargins(serien_name, sender)
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
			
			# if there is no season or episode number it can be a special
			# but if we have more than one special and wunschliste.de does not
			# give us an episode number we are unable to differentiate between these specials
			if not staffel and not episode:
				staffel = "S"
				episode = "0"
			
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
				writeLogFilter("channels", _("[Serien Recorder] ' %s ' - STB-Channel nicht gefunden ' -> ' %s '") % (label_serie, webChannel))
				continue
			
			if int(status) == 0:
				writeLogFilter("channels", _("[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '") % (label_serie, webChannel))
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
				writeLogFilter("allowedSender", _("[Serien Recorder] ' %s ' - Sender nicht erlaubt -> %s -> %s") % (label_serie, sender, allowedSender))
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
							if config.plugins.serienRec.writeLogAllowedSender.value:
								liste = staffeln[:]
								liste.sort()
								liste.reverse()
								if -1 in staffeln:
									liste.remove(-1)
									liste[0] = _("ab %s") % liste[0]
								liste.reverse()
								liste.insert(0, _("0 ab E%s") % str(AbEpisode).zfill(2))
								writeLogFilter("allowedEpisodes", _("[Serien Recorder] ' %s ' - Episode nicht erlaubt -> ' %s ' -> ' %s '") % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
							continue
						else:
							serieAllowed = True
				elif int(staffel) in staffeln:
					serieAllowed = True
				elif -1 in staffeln:		# 'folgende'
					if int(staffel) >= max(staffeln):
						serieAllowed = True
			elif getSpecialsAllowed(serien_name):
				serieAllowed = True
			
			vomMerkzettel = False
			if not serieAllowed:
				cCursorTmp = dbSerRec.cursor()
				cCursorTmp.execute("SELECT * FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), str(episode).zfill(2).lower()))
				row = cCursorTmp.fetchone()
				if row:
					writeLog(_("[Serien Recorder] ' %s ' - Timer vom Merkzettel wird angelegt @ %s") % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True
				cCursorTmp.close()
			
			if not serieAllowed:
				#if config.plugins.serienRec.writeLogAllowedSender.value:
				if False:
					liste = staffeln[:]
					liste.sort()
					liste.reverse()
					if -1 in staffeln:
						liste.remove(-1)
						liste[0] = _("ab %s") % liste[0]
					liste.reverse()
					if str(episode).isdigit():
						if int(episode) < int(AbEpisode):
							liste.insert(0, _("0 ab E%s") % str(AbEpisode).zfill(2))
					if -2 in staffeln:
						liste.remove(-2)
						liste.insert(0, _("Manuell"))
					writeLogFilter("allowedEpisodes", _("[Serien Recorder] ' %s ' - Staffel nicht erlaubt -> ' %s ' -> ' %s '") % (label_serie, seasonEpisodeString, str(liste).replace("'", "").replace('"', "")))
				continue
			
			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit, new_end_unixtime, new_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, stbRef)
			alt_eit, alt_end_unixtime, alt_start_unixtime = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, altstbRef)
			
			(dirname, dirname_serie) = getDirname(serien_name, staffel)
			
			cCursorTmp = dbTmp.cursor()
			sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, Staffel, Episode, SeasonEpisode, Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, EventID, alternativStbChannel, alternativServiceRef, alternativStartTime, alternativEndTime, alternativEventID, DirName, AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel, excludedWeekdays) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
			cCursorTmp.execute(sql, (current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel), excludedWeekdays))
			cCursorTmp.close()

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
		#print "downloadEmail"
		return self.emailData[seriesName]
		
	def createTimer(self, result=True):
		#print "createTimer"
		dbTmp.commit()

		#writeLog("\n", True)
		# versuche deaktivierte Timer zu erstellen
		self.activateTimer()
		
		# jetzt die Timer erstellen	
		for x in range(self.NoOfRecords): 
			self.searchTimer(x)
			dbTmp.commit()
		
		# gleiche alte Timer mit EPG ab
		current_time = int(time.time())
		if config.plugins.serienRec.eventid.value:
			self.adjustEPGtimes(current_time)

		writeLog("\n", True)

		# Datenbank aufräumen
		cCursor = dbSerRec.cursor()
		cCursor.execute("VACUUM")
		cCursor.close()
		cCursor = dbTmp.cursor()
		cCursor.execute("VACUUM")
		cCursor.close()
		#dbTmp.close()

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
		writeLog("---------' Auto-Check beendet (Ausführungsdauer: %s Sek.)'---------------------------------------------------------------------------" % str(speedTime), True)
		print "---------' Auto-Check beendet (Ausführungsdauer: %s Sek.)'-------------------------------------------------------------------------------" % str(speedTime)
		if (config.plugins.serienRec.showNotification.value in ("2", "3")) and (not self.manuell):
			statisticMessage = "Serien vorgemerkt: %s/%s\nTimer erstellt: %s\nTimer aktualisiert: %s\nTimer mit Konflikten: %s\nTimer vom Merkzettel: %s" % (str(self.countActivatedSeries), str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate), str(self.countNotActiveTimer), str(self.countTimerFromWishlist))
			newSeasonOrEpisodeMessage = ""
			if self.newSeriesOrEpisodesFound:
				newSeasonOrEpisodeMessage = "\n\nNeuer Serien- oder Staffelbeginn gefunden"
			
			Notifications.AddPopup("SerienRecorder Suchlauf für neue Timer wurde beendet.\n\n%s%s" % (statisticMessage, newSeasonOrEpisodeMessage), MessageBox.TYPE_INFO, timeout=10, id="Suchlauf wurde beendet")
		
		return result

	def askForDSB(self):
		if not self.manuell:
			dbSerRec.close()
			if (config.plugins.serienRec.updateInterval.value == 24) and (config.plugins.serienRec.wakeUpDSB.value or config.plugins.serienRec.autochecktype.value == "2") and int(config.plugins.serienRec.afterAutocheck.value):
				if config.plugins.serienRec.DSBTimeout.value > 0:
					try:
						self.session.openWithCallback(self.gotoDeepStandby, MessageBox, "Soll der SerienRecorder die Box in (Deep-)Standby versetzen?", MessageBox.TYPE_YESNO, default=True, timeout=config.plugins.serienRec.DSBTimeout.value)
					except:
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
					writeLog("Eine laufenden Aufnahme verhindert den Deep-Standby")
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
			
		cTmp = dbTmp.cursor()
		cTmp.execute("SELECT * FROM (SELECT SerieName, Staffel, Episode, Title, COUNT(*) AS Anzahl FROM GefundeneFolgen WHERE AnzahlAufnahmen>? GROUP BY SerieName, Staffel, Episode, Title) ORDER BY Anzahl", (NoOfRecords,))
		for row in cTmp:
			(serien_name, staffel, episode, title, anzahl) = row

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT preferredChannel, useAlternativeChannel FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
			row = cCursor.fetchone()
			if row:
				(preferredChannel, useAlternativeChannel) = row
				if useAlternativeChannel == -1:
					useAlternativeChannel = config.plugins.serienRec.useAlternativeChannel.value
				useAlternativeChannel = bool(useAlternativeChannel)
			else:
				preferredChannel = 1
				useAlternativeChannel = False
			cCursor.close()
			
			###############################
			##
			## erstellt das serien verzeichnis
			(dirname, dirname_serie) = getDirname(serien_name, staffel)
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
				cTimer = dbTmp.cursor()
				if str(episode).isdigit():
					if int(episode) == 0:
						cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower()))
					else:
						cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
				else:
					cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
					
				for row2 in cTimer:
					(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel, excludedWeekdays) = row2
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
							cAdded = dbTmp.cursor()
							if str(episode).isdigit():
								if int(episode) == 0:
									cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_unixtime, stbRef.lower()))
								else:
									cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
							else:
								cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
							cAdded.close()
							break
				cTimer.close()
				
				if len(self.konflikt) > 0:
					if config.plugins.serienRec.showMessageOnConflicts.value:
						self.MessageList.append(("Timerkonflikte beim SerienRecorder Suchlauf:\n%s" % self.konflikt, MessageBox.TYPE_INFO, -1, self.konflikt))
						Notifications.AddPopup("Timerkonflikte beim SerienRecorder Suchlauf:\n%s" % self.konflikt, MessageBox.TYPE_INFO, timeout=-1, id=self.konflikt)
						
			##############################
			#
			# erstellt das serien verzeichnis
			if TimerDone and self.enableDirectoryCreation:
				CreateDirectory(serien_name, staffel)
					
		cTmp.close()
					
	def searchTimer2(self, serien_name, staffel, episode, title, optionalText, usedChannel, dirname):				
		# prepare postprocessing for forced recordings
		forceRecordings = []
		forceRecordings_W = []
		eventRecordings = []
		self.konflikt = ""

		TimerDone = False
		cTimer = dbTmp.cursor()
		if str(episode).isdigit():
			if int(episode) == 0:
				cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower()))
			else:
				cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
		else:
			cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
			
		for row in cTimer:
			(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel, excludedWeekdays) = row
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
			if checkTimerAdded(webChannel, serien_name, staffel, episode, int(timer_start_unixtime)):
				writeLogFilter("added", "' %s ' - Timer für diese Episode%s wurde bereits erstellt -> ' %s '" % (label_serie, optionalText, check_SeasonEpisode))
				cAdded = dbTmp.cursor()
				if str(episode).isdigit():
					if int(episode) == 0:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_unixtime, stbRef.lower()))
					else:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				else:
					cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				cAdded.close()
				continue

			# check anzahl timer und auf hdd
			bereits_vorhanden_HDD = 0
			if str(episode).isdigit():
				if int(episode) == 0:
					bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, episode, title, searchOnlyActiveTimers = True)
					if config.plugins.serienRec.sucheAufnahme.value:
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False, title)
				else:
					bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, episode, searchOnlyActiveTimers = True)
					if config.plugins.serienRec.sucheAufnahme.value:
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)
			else:
				bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, episode, searchOnlyActiveTimers = True)
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
					title = "dump"
					if useTitles:
						title = splitedTitleList[idx]
					alreadyExists = checkAlreadyAdded(serien_name, entry[0], entry[1], title, False)
					if alreadyExists:
						alreadyExistsCount += 1

				if len(splitedSeasonEpisodeList) == alreadyExistsCount:
					# Alle Einzelfolgen wurden bereits aufgenommen - der Event muss nicht mehr aufgenommen werden.
					writeLogFilter("timerDebug", "' %s ' - Timer für Einzelepisoden wurden bereits erstellt -> ' %s '" % (serien_name, check_SeasonEpisode))
					TimerDone = True
					continue
				elif config.plugins.serienRec.splitEventTimer.value == "2":
					# Nicht alle Einzelfolgen wurden bereits aufgenommen, es sollen aber Einzelfolgen bevorzugt werden
					writeLogFilter("timerDebug", "' %s ' - Versuche zunächst Timer für Einzelepisoden anzulegen" % serien_name)
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
				cAdded = dbTmp.cursor()
				if str(episode).isdigit():
					if int(episode) == 0:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_unixtime, stbRef.lower()))
					else:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				else:
					cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				cAdded.close()
				TimerDone = True
				break
				
		### end of for loop
		cTimer.close()
		
		if not TimerDone:
			# post processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in forceRecordings_W:
				if checkAlreadyAdded(serien_name, staffel, episode, title, False):
					continue
				# programmiere Timer (Wiederholung)
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
					cAdded = dbTmp.cursor()
					if str(episode).isdigit():
						if int(episode) == 0:
							cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_unixtime, stbRef.lower()))
						else:
							cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
					else:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
					cAdded.close()
					TimerDone = True
					#break
					
		if not TimerDone:
			# post processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in forceRecordings:
				if checkAlreadyAdded(serien_name, staffel, episode, title, False):
					continue
				show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
				writeLog("' %s ' - Keine Wiederholung gefunden! -> %s" % (label_serie, show_start), True)
				# programmiere Timer
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
					cAdded = dbTmp.cursor()
					if str(episode).isdigit():
						if int(episode) == 0:
							cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), title.lower(), start_unixtime, stbRef.lower()))
						else:
							cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
					else:
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
					cAdded.close()
					TimerDone = True
					#break

		if not TimerDone:
			# post processing event recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in eventRecordings[:]:
				if self.shouldCreateEventTimer(serien_name, staffel, episode, title):
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					writeLog("' %s ' - Einzelepisoden nicht gefunden! -> %s" % (label_serie, show_start), True)
					# programmiere Timer
					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
						TimerDone = True
						#break

		return TimerDone

	@staticmethod
	def splitEvent(episode, staffel, title):
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
		vpsSettings = getVPS(webChannel, serien_name)

		#get tags from marker
		tags = getTags(serien_name)
			
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
				self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit)
				if vomMerkzettel:
					self.countTimerFromWishlist += 1
					writeLog("' %s ' - Timer (vom Merkzettel) wurde angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					cCursor = dbSerRec.cursor()
					cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), episode.lower()))
					dbSerRec.commit()	
					cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), str(staffel).lower(), episode.lower()))
					dbSerRec.commit()	
					cCursor.close()
				else:
					writeLog("' %s ' - Timer wurde angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					# Event-Programmierung verarbeiten
					if config.plugins.serienRec.splitEventTimer.value == "1" and '/' in str(episode):
						splitedSeasonEpisodeList, splitedTitleList, useTitles = self.splitEvent(episode, staffel, title)

						for idx,entry in enumerate(splitedSeasonEpisodeList):
							title = "dump"
							if useTitles:
								title = splitedTitleList[idx]
							alreadyExists = checkAlreadyAdded(serien_name, entry[0], entry[1], title, False)
							if not alreadyExists:
								# Nicht vorhandene Einzelfolgen als bereits aufgenommen markieren
								addToAddedList(serien_name, entry[1], entry[1], entry[0], title)
								writeLogFilter("timerDebug", "Einzelepisode wird nicht mehr aufgenommen: %s S%sE%s - %s" % (serien_name, str(entry[0]).zfill(2), str(entry[1]).zfill(2), title))

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
					self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit, False)
					cCursor = dbSerRec.cursor()
					cCursor.execute("INSERT OR IGNORE INTO TimerKonflikte (Message, StartZeitstempel, webChannel) VALUES (?, ?, ?)", (dbMessage, int(start_unixtime), webChannel))
					if vomMerkzettel:
						self.countTimerFromWishlist += 1
						writeLog("' %s ' - Timer (vom Merkzettel) wurde deaktiviert angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
						#cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), episode.lower()))
						#dbSerRec.commit()	
						#cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), str(staffel).lower(), episode.lower()))
						#dbSerRec.commit()
					else:
						writeLog("' %s ' - Timer wurde deaktiviert angelegt%s -> %s %s @ %s" % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					cCursor.close()
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
	def readSenderListe():
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels")
		for row in cCursor:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
			fSender.append((webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status))
		cCursor.close()
		return fSender
		
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
		return (webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status)

	@staticmethod
	def checkTimer(serie, start_time, webchannel):
		(margin_before, margin_after) = getMargins(serie, webchannel)

		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=? AND LOWER(webChannel)=?"
		cCursor.execute(sql, (serie.lower(), (int(start_time) - (int(margin_before) * 60)), webchannel.lower()))
		if cCursor.fetchone():
			cCursor.close()
			return True
		else:
			cCursor.close()
			return False

	@staticmethod
	def shouldCreateEventTimer(serien_name, staffel, episode, title):
		if checkAlreadyAdded(serien_name, staffel, episode, title, False):
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
				alreadyExists = checkAlreadyAdded(serien_name, entry[0], entry[1], title, False)
				if alreadyExists:
					alreadyExistsCount += 1

			if alreadyExistsCount == len(splitedSeasonEpisodeList):
				result = False

		return result

			
	@staticmethod
	def addRecTimer(serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, TimerAktiviert = True):
		(margin_before, margin_after) = getMargins(serien_name, webChannel)
		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		#sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ?<=StartZeitstempel<=?"
		cCursor.execute(sql, (serien_name.lower(), stbRef.lower(), int(start_time) + (int(margin_before) * 60) - (int(STBHelpers.getEPGTimeSpan()) * 60), int(start_time) + (int(margin_before) * 60) + (int(STBHelpers.getEPGTimeSpan()) * 60)))
		row = cCursor.fetchone()
		if row:
			sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=?, TimerAktiviert=? WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
			cCursor.execute(sql, (eit, int(TimerAktiviert), serien_name.lower(), stbRef.lower(), int(start_time) + (int(margin_before) * 60) - (int(STBHelpers.getEPGTimeSpan()) * 60), int(start_time) + (int(margin_before) * 60) + (int(STBHelpers.getEPGTimeSpan()) * 60)))
			print "[SerienRecorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", "Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, int(TimerAktiviert)))
			#cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			print "[SerienRecorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", "Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))

		dbSerRec.commit()
		cCursor.close()
		
	def dataError(self, error, url=None):
		print "[SerienRecorder] Es ist ein Fehler aufgetreten - die Daten konnten nicht abgerufen/verarbeitet werden: (%s)" % error

		if url:
			writeLog("Es ist ein Fehler aufgetreten  - die Daten konnten nicht abgerufen werden: (%s)" % error, True)
			writeErrorLog("   serienRecCheckForRecording(): %s\n   Url: %s" % (error, url))
		else:
			writeLog("Es ist ein Fehler aufgetreten  - die Daten konnten nicht verarbeitet werden: (%s)" % error, True)
			writeErrorLog("   serienRecCheckForRecording(): %s\n   createTimer()" % error)

class serienRecTimer(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.WochenTag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		self.ErrorMsg = "unbekannt"

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
			if isDreamboxOS:
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
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
			serien_id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if serien_id:
				self.session.open(serienRecShowInfo, serien_name, serien_id[0])

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

		cCursor = dbSerRec.cursor()
		if self.filter:
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel, EventID, TimerAktiviert FROM AngelegteTimer WHERE StartZeitstempel>=?", (current_time, ))
		else:
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel, EventID, TimerAktiviert FROM AngelegteTimer")
		for row in cCursor:
			(serie, staffel, episode, title, start_time, webChannel, eit, activeTimer) = row
			if int(start_time) < int(current_time):
				deltimer += 1
				timerList.append((serie, staffel, episode, title, start_time, webChannel, "1", 0, bool(activeTimer)))
			else:
				timerList.append((serie, staffel, episode, title, start_time, webChannel, "0", eit, bool(activeTimer)))
		cCursor.close()
		
		if showTitle:
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			if self.filter:
				self['title'].setText("Timer-Liste: %s Timer sind vorhanden." % len(timerList))
			else:
				self['title'].setText("Timer-Liste: %s Aufnahme(n) und %s Timer sind vorhanden." % (deltimer, len(timerList)-deltimer))

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
			SerieColor = parseColor('foreground').argb()
		else:
			SerieColor = parseColor('red').argb()

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 8 * skinFactor, 32 * skinFactor, 32 * skinFactor, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel, SerieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29 * skinFactor, 250 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, parseColor('yellow').argb()),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, re.sub("(?<= - )dump\Z", "(Manuell hinzugefügt !!)", xtitle), parseColor('yellow').argb())
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
		cCursor = dbSerRec.cursor()
		if serien_eit > 0:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE EventID=? AND StartZeitstempel>=?", (serien_eit, int(time.time())))
		else:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND Episode=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (serien_name.lower(), staffel.lower(), episode, serien_time, serien_channel.lower()))
		dbSerRec.commit()
		cCursor.close()
		
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

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND Episode=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (serien_name.lower(), staffel.lower(), episode, serien_time, serien_channel.lower()))
			if cCursor.fetchone():
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, "Soll '%s - S%sE%s - %s' wirklich entfernt werden?" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), re.sub("\Adump\Z", "(Manuell hinzugefügt !!)", serien_title)), MessageBox.TYPE_YESNO, default = False)
				else:
					self.removeTimer(serien_name, staffel, episode, serien_title, serien_time, serien_channel, serien_eit)
			else:
				print "[SerienRecorder] keinen passenden timer gefunden."
			cCursor.close()
			
	def keyYellow(self):
		if self.filter:
			self['text_yellow'].setText("Zeige nur neue Timer")
			self.filter = False
		else:
			self['text_yellow'].setText("Zeige auch alte Timer")
			self.filter = True
		self.readTimer()
		
	def removeNewTimerFromDB(self, answer):
		if answer:
			current_time = int(time.time())
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel, EventID, TimerAktiviert FROM AngelegteTimer WHERE StartZeitstempel>=?",(current_time,))
			for row in cCursor:
				(serie, staffel, episode, title, start_time, webChannel, eit, activeTimer) = row
				self.removeTimer(serie, staffel, episode, title, start_time, webChannel, eit)
			cCursor.close()

			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("Alle noch ausstehenden Timer wurden entfernt.")
		else:
			return

	def keyBlue(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeOldTimerFromDB, MessageBox,
			                              "Sollen wirklich alle noch ausstehenden Timer von der Box und aus der Datenbank entfernt werden?",
			                              MessageBox.TYPE_YESNO, default = False)
		else:
			self.removeOldTimerFromDB(True)

	def removeOldTimerFromDB(self, answer):
		if answer:
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM AngelegteTimer WHERE StartZeitstempel<?", (int(time.time()),))
			dbSerRec.commit()
			cCursor.execute("VACUUM")
			dbSerRec.commit()
			cCursor.close()

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
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		serien_id = None
		if row:
			(url, ) = row
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
		if isDreamboxOS:
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
			if isDreamboxOS:
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
		if isDreamboxOS:
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

class serienRecMarker(Screen, HelpableScreen):
	def __init__(self, session, SelectSerie=None):
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

		if not showMainScreen:
			self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
				"ok"       : (self.keyOK, "zur Staffelauswahl"),
				"cancel"   : (self.keyCancel, "SerienRecorder beenden"),
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
		
		self.onLayoutFinish.append(self.readSerienMarker)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)
		
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
			if not showMainScreen:
				self.num_bt_text[0][2] = "Exit (lang: Serienplaner)"
		else:
			self.num_bt_text[4][2] = "Setup Serie/global"
			self['text_red'].setText("(De)aktivieren/Löschen")
			self['text_blue'].setText("Timer-Liste")
			if not showMainScreen:
				self.num_bt_text[0][2] = "Exit/Serienplaner"

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
			self.updateMenuKeys()
			self.displayTimer = eTimer()
			if isDreamboxOS:
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)
		
	def setupSkin(self):
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
			
	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def markerSetup(self):
		if self['menu_list'].getCurrent() is None:
			return
		serien_name = self['menu_list'].getCurrent()[0][0]
		self.session.openWithCallback(self.SetupFinished, serienRecMarkerSetup, serien_name)

	def SetupFinished(self, result):
		if result:
			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			self.readSerienMarker()
		return
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.openWithCallback(self.SetupFinished, serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_url = self['menu_list'].getCurrent()[0][1]
		serien_id = getSeriesIDByURL(serien_url)
		if serien_id:
			self.session.open(serienRecShowInfo, serien_name, serien_id)

	def episodeList(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][0]
			serien_url = self['menu_list'].getCurrent()[0][1]
			serien_id = getSeriesIDByURL(serien_url)
			if serien_id:
				self.session.open(serienRecEpisodes, serien_name, "http://www.wunschliste.de/%s" % serien_id, self.serien_nameCover)

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
				self.readSerienMarker()
				
	def getCover(self):
		if self.loading:
			return
		
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		self.serien_nameCover = "%s%s.png" % (config.plugins.serienRec.coverPath.value, serien_name)
		serien_id = getSeriesIDByURL(self['menu_list'].getCurrent()[0][1])
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)

	def readSerienMarker(self, SelectSerie=None):
		if SelectSerie: self.SelectSerie = SelectSerie
		markerList = []
		numberOfDeactivatedSeries = 0

		cCursor = dbSerRec.cursor()
		#cCursor.execute("SELECT SerienMarker.ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB FROM SerienMarker LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID ORDER BY Serie")
		cCursor.execute("SELECT SerienMarker.ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, COUNT(StaffelAuswahl.ID) AS ErlaubteStaffelCount FROM SerienMarker LEFT JOIN StaffelAuswahl ON StaffelAuswahl.ID = SerienMarker.ID LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID GROUP BY Serie ORDER BY Serie")
		cMarkerList = cCursor.fetchall()
		for row in cMarkerList:
			(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, ErlaubteStaffelCount) = row
			if alleSender:
				sender = ['Alle',]
			else:
				sender = []
				cSender = dbSerRec.cursor()
				cSender.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=? ORDER BY LOWER(ErlaubterSender)", (ID,))
				cSenderList = cSender.fetchall()
				if len(cSenderList) > 0:
					sender = list(zip(*cSenderList)[0])
				cSender.close()
			
			if AlleStaffelnAb == -2: 		# 'Manuell'
				staffeln = ['Manuell',]
			elif AlleStaffelnAb == 0:		# 'Alle'
				staffeln = ['Alle',]
			else:
				staffeln = []
				if ErlaubteStaffelCount > 0:
					cStaffel = dbSerRec.cursor()
					cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
					cStaffelList = cStaffel.fetchall()
					if len(cStaffelList) > 0:
						staffeln = list(zip(*cStaffelList)[0])
						staffeln.sort()
					cStaffel.close()
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

			markerList.append((Serie, Url, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, bool(useAlternativeChannel), SerieAktiviert))
				
		cCursor.close()
		self['title'].setText("Serien Marker - %d/%d Serien vorgemerkt." % (len(markerList)-numberOfDeactivatedSeries, len(markerList)))
		if len(markerList) != 0:
			self.chooseMenuList.setList(map(self.buildList, markerList))
			if self.SelectSerie:
				try:
					idx = zip(*markerList)[0].index(self.SelectSerie)
					self['menu_list'].moveToIndex(idx)
				except:
					pass
			self.loading = False
			self.getCover()

	@staticmethod
	def buildList(entry):
		(serie, url, staffeln, sendern, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel, SerieAktiviert) = entry

		if preferredChannel == 1:
			senderText = "Std."
			if useAlternativeChannel:
				senderText = "%s, Alt." % senderText
		else:
			senderText = "Alt."
			if useAlternativeChannel:
				senderText = "%s, Std." % senderText

		if SerieAktiviert:
			serieColor = parseColor('yellow').argb()
		else:
			serieColor = parseColor('red').argb()

		senderText = "Sender (%s): %s" % (senderText, sendern)
		staffelText = "Staffel: %s" % staffeln
		infoText = "Wdh./Vorl./Nachl.: %s / %s / %s" % (int(AnzahlAufnahmen) - 1, int(Vorlaufzeit), int(Nachlaufzeit))
		folderText = "Dir: %s" % AufnahmeVerzeichnis

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 750 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, serieColor, serieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29 * skinFactor, 350 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffelText),
			(eListboxPythonMultiContent.TYPE_TEXT, 400 * skinFactor, 29 * skinFactor, 450 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, senderText),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 49 * skinFactor, 350 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, infoText),
			(eListboxPythonMultiContent.TYPE_TEXT, 400 * skinFactor, 49 * skinFactor, 450 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, folderText)
			]

	def keyCheck(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return

		if self.modus == "menu_list":
			self.session.open(serienRecRunAutoCheck, True)

	def keyCheckLong(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return
		
		if not config.plugins.serienRec.tvplaner.value:
			print "[SerienRecorder] TV-Planer nicht aktiviert"
			return
			
		if self.modus == "menu_list":
			self.session.open(serienRecRunAutoCheck, True, config.plugins.serienRec.tvplaner.value)

	def keyOK(self):
		if self.modus == "popup_list":
			self.select_serie = self['menu_list'].getCurrent()[0][0]
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
			self.chooseMenuList_popup.setList(map(self.buildList2, self.staffel_liste))
		elif self.modus == "popup_list2":
			self.select_serie = self['menu_list'].getCurrent()[0][0]
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
			self.select_serie = self['menu_list'].getCurrent()[0][0]
			self['popup_list'].show()
			self['popup_bg'].show()
			
			staffeln = ["Manuell", "Alle", "Specials", "folgende"]
			staffeln.extend(range(config.plugins.serienRec.max_season.value+1))
			mode_list = [0,]*len(staffeln)
			index_list = range(len(staffeln))
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT ID, AlleStaffelnAb, AbEpisode, TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
			row = cCursor.fetchone()
			if row:
				(ID, AlleStaffelnAb, self.AbEpisode, TimerForSpecials) = row
				if AlleStaffelnAb == -2:		# 'Manuell'
					mode_list[0] = 1
				else:	
					if AlleStaffelnAb == 0:		# 'Alle'
						mode_list[1] = 1
					else:
						if bool(TimerForSpecials):
							mode_list[2] = 1
						cStaffel = dbSerRec.cursor()
						cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
						cStaffelList = cStaffel.fetchall()
						if AlleStaffelnAb >= 999999:
							cStaffelList = []
							cStaffel = dbSerRec.cursor()
							cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
							cStaffelList = cStaffel.fetchall()
							if len(cStaffelList) > 0:
								cStaffelList = zip(*cStaffelList)[0]
							for staffel in cStaffelList:
								mode_list[staffel + 4] = 1
						elif (AlleStaffelnAb > 0) and (AlleStaffelnAb <= (len(staffeln)-4)):
							cStaffelList = []
							mode_list[AlleStaffelnAb + 4] = 1
							mode_list[3] = 1
							cStaffel = dbSerRec.cursor()
							cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
							cStaffelList = cStaffel.fetchall()
							if len(cStaffelList) > 0:
								cStaffelList = zip(*cStaffelList)[0]
							for staffel in cStaffelList:
								mode_list[staffel + 4] = 1
								if (staffel + 1) == AlleStaffelnAb:
									mode_list[AlleStaffelnAb + 4] = 0
									AlleStaffelnAb = staffel
						if self.AbEpisode > 0:
							mode_list[4] = 1
							
						cStaffel.close()
					
			else:
				print "kein Eintrag in DB (SerienMarker)"
			cCursor.close()
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

			getSender = getWebSenderAktiv()
			if len(getSender) != 0:
				self.modus = "popup_list2"
				self['popup_list'].show()
				self['popup_bg'].show()
				self.select_serie = self['menu_list'].getCurrent()[0][0]

				getSender.insert(0, 'Alle')
				mode_list = [0,]*len(getSender)
				index_list = range(len(getSender))
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT ID, alleSender FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
				row = cCursor.fetchone()
				if row:
					(ID, alleSender) = row
					if alleSender:
						mode_list[0] = 1
					else:
						cSender = dbSerRec.cursor()
						cSender.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=?", (ID,))
						for row in cSender:
							(sender,) = row
							if sender in getSender:
								idx = getSender.index(sender)
								mode_list[idx] = 1
						cSender.close()
				else:
					print "kein Eintrag in DB (SerienMarker)"
				cCursor.close()
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

			serien_name = self['menu_list'].getCurrent()[0][0]
			serien_url = self['menu_list'].getCurrent()[0][1]
			
			print serien_url
			self.session.openWithCallback(self.callTimerAdded, serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)

	def callDisableAll(self, answer):
		if answer:
			self.selected_serien_name = self['menu_list'].getCurrent()[0][0]
			cCursor = dbSerRec.cursor()
			mask = (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
			cCursor.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=ErlaubteSTB &(~?)", (mask,))
			dbSerRec.commit()
			self.readSerienMarker()
			cCursor.close()
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
		cCursor = dbSerRec.cursor()
		if answer:
			print "[SerienRecorder] lösche %s aus der added liste" % serien_name
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=?", (serien_name.lower(),))
		cCursor.execute("DELETE FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
		dbSerRec.commit()
		cCursor.close()
		self.changesMade = True
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
				self.selected_serien_name = self['menu_list'].getCurrent()[0][0]
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (self.selected_serien_name.lower(),))
				row = cCursor.fetchone()
				if row:
					(ID, ErlaubteSTB) = row
					if ErlaubteSTB is not None:
						ErlaubteSTB ^= (1 << (int(config.plugins.serienRec.BoxID.value) - 1)) 
						cCursor.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=? WHERE ID=?", (ErlaubteSTB, ID))
						dbSerRec.commit()
					self.readSerienMarker(self.selected_serien_name)
				cCursor.close()
					
	def keyRedLong(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['menu_list'].getCurrent()[0][0]
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.selected_serien_name.lower(),))
				row = cCursor.fetchone()
				if row:
					print "gefunden."
					if config.plugins.serienRec.confirmOnDelete.value:
						self.session.openWithCallback(self.callSaveMsg, MessageBox, "Soll '%s' wirklich entfernt werden?" % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
					else:
						self.session.openWithCallback(self.callDelMsg, MessageBox, "Sollen die Einträge für '%s' auch aus der Timer-Liste entfernt werden?" % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
				cCursor.close()

	def disableAll(self):
		if self.modus == "menu_list":
			check = self['menu_list'].getCurrent()
			if check is None:
				print "[SerienRecorder] Serien Marker leer."
				return
			else:
				self.session.openWithCallback(self.callDisableAll, MessageBox, "Wollen Sie alle Serien-Marker für diese Box deaktivieren?", MessageBox.TYPE_YESNO, default = False)

	def insertStaffelMarker(self):
		print self.select_serie
		AlleStaffelnAb = 999999
		TimerForSpecials = 0
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ID, AbEpisode FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
		row = cCursor.fetchone()
		if row:
			(ID, AbEpisode) = row
			cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID=?", (ID,))
			liste = self.staffel_liste[1:]
			liste = zip(*liste)
			if 1 in liste[1]:
				#staffeln = ['Manuell','Alle','Specials','folgende',...]
				for row in self.staffel_liste:
					(staffel, mode, index) = row
					if (index == 0) and (mode == 1):		# 'Manuell'
						AlleStaffelnAb = -2
						AbEpisode = 0
						TimerForSpecials = 0
						break
					elif (index == 1) and (mode == 1):		# 'Alle'
						AlleStaffelnAb = 0
						AbEpisode = 0
						TimerForSpecials = 0
						break
					else:
						if (index == 2) and (mode == 1):		#'Specials'
							TimerForSpecials = 1
						if (index == 3) and (mode == 1):		#'folgende'
							liste = self.staffel_liste[5:]
							liste.reverse()
							liste = zip(*liste)
							if 1 in liste[1]:
								idx = liste[1].index(1)
								AlleStaffelnAb = liste[0][idx]
								try:
									idx = liste[1].index(0, idx+1, len(liste[1]))
									AlleStaffelnAb = liste[0][idx-1]
								except:
									AlleStaffelnAb = 0
									break
						if (index == 4) and (mode != 1):		
							AbEpisode = 0
						elif (index > 4) and mode == 1:
							if str(staffel).isdigit():
								if staffel >= AlleStaffelnAb:
									#break
									continue
								elif (staffel + 1) == AlleStaffelnAb:
									AlleStaffelnAb = staffel
								else:	
									cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, staffel))
			else:
				AlleStaffelnAb = -2
				AbEpisode = 0
			
		self.changesMade = True
		global runAutocheckAtExit
		runAutocheckAtExit = True
		cCursor.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=?, AbEpisode=?, TimerForSpecials=? WHERE LOWER(Serie)=?", (AlleStaffelnAb, AbEpisode, TimerForSpecials, self.select_serie.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.readSerienMarker()

	def insertSenderMarker(self):
		print self.select_serie
		alleSender = 0
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
		row = cCursor.fetchone()
		if row:
			(ID,) = row
			cCursor.execute("DELETE FROM SenderAuswahl WHERE ID=?", (ID,))
			liste = self.sender_liste[1:]
			liste = zip(*liste)
			if 1 in liste[1]:
				idx = liste[1].index(1)
				for row in self.sender_liste:
					(sender, mode, index) = row
					if (index == 0) and (mode == 1):		# 'Alle'
						alleSender = 1
						break
					elif mode == 1:		# Sender erlaubt
						cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, sender))
			else:
				alleSender = 1
			
		self.changesMade = True
		global runAutocheckAtExit
		runAutocheckAtExit = True
		cCursor.execute("UPDATE OR IGNORE SerienMarker SET alleSender=? WHERE LOWER(Serie)=?", (alleSender, self.select_serie.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.readSerienMarker()

	def keyBlue(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.readSerienMarker, serienRecTimer)

	def searchSeries(self):
		if self.modus == "menu_list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			self.session.openWithCallback(self.readSerienMarker, serienRecAddSerie, serien_name)

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
			print episode
			cCursor = dbSerRec.cursor()
			cCursor.execute("UPDATE OR IGNORE SerienMarker SET AbEpisode=? WHERE LOWER(Serie)=?", (int(episode), self.select_serie.lower()))
			dbSerRec.commit()
			cCursor.close
		self.insertStaffelMarker()
			
	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyExit(self):
		if self.modus == "popup_list" or self.modus == "popup_list2":
			self.keyCancel()
		else:
			global showMainScreen
			showMainScreen = True
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
			#if not showMainScreen:
				#self.hide()
				#self.session.openWithCallback(self.readSerienMarker, ShowSplashScreen, config.plugins.serienRec.showversion.value)
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)

class serienRecAddSerie(Screen, HelpableScreen):
	def __init__(self, session, serien_name):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.ErrorMsg = "unbekannt"
		self.serienlist = None
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
			if isDreamboxOS:
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

	def searchSerie(self):
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche nach ' %s '" % self.serien_name)
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		self.results(SeriesServer().doSearch(self.serien_name))

	def results(self, serienlist):	
		self.serienlist = serienlist
		self.chooseMenuList.setList(map(self.buildList, self.serienlist))
		self['title'].setText("Die Suche für ' %s ' ergab %s Teffer." % (self.serien_name, str(sum([1 if x[2] != "-1" else int(x[1]) for x in serienlist]))))
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		self.loading = False
		self.getCover()

	@staticmethod
	def buildList(entry):
		(name_Serie, year_Serie, id_Serie) = entry

		# weitere Ergebnisse Eintrag
		if id_Serie == "-1":
			year_Serie = ""

		name_Serie = doReplaces(name_Serie)

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

		Serie = doReplaces(self['menu_list'].getCurrent()[0][0])
		Year = self['menu_list'].getCurrent()[0][1]
		Id = self['menu_list'].getCurrent()[0][2]
		print Serie, Year, Id

		if Id == "-1":
			self.keyBlue()
			return

		self.serien_name = ""
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(),))
		row = cCursor.fetchone()	
		if not row:
			Url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(Id)
			if config.plugins.serienRec.defaultStaffel.value == "0":
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (Serie, Url))
			else:
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, -2, 1, 1, -1, 0, -1, 0)", (Serie, Url))
			erlaubteSTB = 0xFFFF
			if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
				erlaubteSTB = 0
				erlaubteSTB |= (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
			cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (cCursor.lastrowid, erlaubteSTB))
			dbSerRec.commit()
			cCursor.close()
			self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % Serie)
			self['title'].instance.setForegroundColor(parseColor("green"))
			if config.plugins.serienRec.openMarkerScreen.value:
				self.close(Serie)
		else:
			self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % Serie)
			self['title'].instance.setForegroundColor(parseColor("red"))
			cCursor.close()

	def keyRed(self):
		self.close()

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:", text = self.serien_name)

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.chooseMenuList.setList(map(self.buildList, []))
			self['title'].setText("")
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.serien_name = serien_name
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

	def dataError(self, error, url=None):
		if url:
			writeErrorLog("   serienRecAddSerie(): %s\n   Serie: %s\n   Url:%s" % (error, self.serien_name, url))
		else:
			writeErrorLog("   serienRecAddSerie(): %s\n   Serie: %s" % (error, self.serien_name))
		print error

class serienRecSendeTermine(Screen, HelpableScreen):
	def __init__(self, session, serien_name, serie_url, serien_cover):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.addedEpisodes = getAlreadyAdded(serien_name, False)
		self.serie_url = serie_url
		self.serien_cover = serien_cover
		self.skin = None
		self.serien_id = 0

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "umschalten ausgewählter Sendetermin aktiviert/deaktiviert"),
			"cancel": (self.keyCancel, "zurück zur Serien-Marker-Ansicht"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"red"	: (self.keyRed, "zurück zur Serien-Marker-Ansicht"),
			"green" : (self.keyGreen, "Timer für aktivierte Sendetermine erstellen"),
			"yellow": (self.keyYellow, "umschalten Filter (aktive Sender) aktiviert/deaktiviert"),
			"blue"	: (self.keyBlue, "Ansicht Timer-Liste öffnen"),
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

		self.FilterMode = 1
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
		setSkinProperties(self)

		self['text_red'].setText("Abbrechen")
		self['text_ok'].setText("Auswahl")
		if self.FilterMode is 1:
			self['text_yellow'].setText("Filter umschalten")
			self.title_txt = "aktive Sender"
		elif self.FilterMode is 2:
			self['text_yellow'].setText("Filter ausschalten")
			self.title_txt = "Marker Sender"
		else:
			self['text_yellow'].setText("Filter einschalten")
			self.title_txt = "alle"
		self['text_blue'].setText("Timer-Liste")

		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
			self.updateMenuKeys()
		
			self.displayTimer = eTimer()
			if isDreamboxOS:
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)
			
	def setupSkin(self):
		InitSkin(self)
		
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(50*skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		self['title'].setText("Lade Web-Sender / STB-Sender...")

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
		if self.loading:
			return

		serien_id = getSeriesIDByURL(self.serie_url)
		if serien_id:
			self.session.open(serienRecShowInfo, self.serien_name, serien_id)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return
				
			print "[SerienRecorder] starte youtube suche für %s" % self.serien_name
			self.session.open(searchYouTube, self.serien_name)
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "EPGTranslator von Kashmir", MessageBox.TYPE_INFO, timeout = 10)

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			print "[SerienRecorder] starte Wikipedia Suche für %s" % self.serien_name
			self.session.open(wikiSearch, self.serien_name)
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
				self.searchEvents()

	def searchEvents(self, result=None):
		self['title'].setText("Suche ' %s '" % self.serien_name)
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		print self.serie_url

		transmissions = None

		if self.serie_url:
			self.serien_id = getSeriesIDByURL(self.serie_url)
			if self.serien_id is None or self.serien_id == 0:
				# This is a marker created by TV Planer function - get id from server
				try:
					self.serien_id = SeriesServer().getSeriesID(self.serien_name)
				except:
					self.serien_id = 0
			
			if self.serien_id != 0:
				print self.serien_id
				
				getCover(self, self.serien_name, self.serien_id)
				
				if self.FilterMode is 0:
					webChannels = []
				elif self.FilterMode is 1:
					webChannels = getWebSenderAktiv()
				else:
					webChannels = getMarkerChannels(self.serien_id)
				
				try:
					transmissions = SeriesServer().doGetTransmissions(self.serien_id, 0, webChannels)
				except:
					transmissions = None
			else:
				transmissions = None
		
		self.resultsEvents(transmissions)

	def resultsEvents(self, transmissions):
		if transmissions is None:
			self['title'].setText("Fehler beim Abrufen der Termine für ' %s '" % self.serien_name)
			return
		self.sendetermine_list = []

		#build unique dir list by season
		dirList = {}
		#build unique channel list
		channelList = {}
		#build unique margins
		marginList = {}

		for serien_name,sender,startzeit,endzeit,staffel,episode,title,status in transmissions:

			datum = time.strftime("%d.%m", time.localtime(startzeit))
			seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

			bereits_vorhanden = False
			if config.plugins.serienRec.sucheAufnahme.value:
				if not staffel in dirList:
					dirList[staffel] = getDirname(serien_name, staffel)

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
					marginList[sender] = getMargins(serien_name, sender)

				(margin_before, margin_after) = marginList[sender]

				# check 2 (im timer file)
				start_unixtime = startzeit - (int(margin_before) * 60)

				if self.isTimerAdded(sender, staffel, episode, int(start_unixtime), title):
					addedType = 2
				elif self.isAlreadyAdded(staffel, episode, title):
					addedType = 3
				else:
					addedType = 0

			startTime = time.strftime("%H.%M", time.localtime(startzeit))
			endTime = time.strftime("%H.%M", time.localtime(endzeit))
			self.sendetermine_list.append([serien_name, sender, datum, startTime, endTime, staffel, episode, title, status, addedType])

		if len(self.sendetermine_list):
			self['text_green'].setText("Timer erstellen")

		self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))
		self.loading = False
		self['title'].setText("%s Sendetermine für ' %s ' gefunden. (%s)" % (str(len(self.sendetermine_list)), self.serien_name, self.title_txt))

	@staticmethod
	def buildList_termine(entry):
		(serien_name, sender, datum, start, end, staffel, episode, title, status, addedType) = entry

		# addedType: 0 = None, 1 = on HDD, 2 = Timer available, 3 = in DB

		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

		imageMinus = "%simages/minus.png" % serienRecMainPath
		imagePlus = "%simages/plus.png" % serienRecMainPath
		imageNone = "%simages/black.png" % serienRecMainPath

		if int(status) == 0:
			leftImage = imageMinus
		else:
			leftImage = imagePlus

		imageHDD = imageNone
		imageTimer = imageNone
		if addedType == 1:
			titleColor = parseColor('yellow').argb()
			imageHDD = "%simages/hdd_icon.png" % serienRecMainPath
		elif addedType == 2:
			titleColor = parseColor('blue').argb()
			imageTimer = "%simages/timer.png" % serienRecMainPath
		elif addedType == 3:
			titleColor = parseColor('green').argb()
		else:
			titleColor = parseColor('red').argb()

		dateColor = parseColor('yellow').argb()

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 15 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(leftImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 29 * skinFactor, 150 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s %s" % (datum, start), dateColor, dateColor),
		    (eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 265 * skinFactor, 7 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageTimer)),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 265 * skinFactor, 30 * skinFactor, 30 * skinFactor, 22 * skinFactor, loadPNG(imageHDD)),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
			(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 498 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s - %s" % (seasonEpisodeString, title), titleColor, titleColor)
			]

	def isAlreadyAdded(self, season, episode, title=None):
		result = False
		# Title is only relevant if season and episode is 0
		# this happen when Wunschliste has no episode and season information
		seasonEpisodeString = "S%sE%s" % (str(season).zfill(2), str(episode).zfill(2))
		if seasonEpisodeString != "S00E00":
			title = None
		if not title:
			for addedEpisode in self.addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode:
					result = True
					break
		else:
			for addedEpisode in self.addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode and addedEpisode[2] == title:
					result = True
					break

		return result

	def isTimerAdded(self, sender, season, episode, start_unixtime, title=None):
		result = False
		if not title:
			for addedEpisode in self.addedEpisodes:
				if addedEpisode[0] == season and addedEpisode[1] == episode and addedEpisode[3] == sender.lower() and int(start_unixtime)-(int(STBHelpers.getEPGTimeSpan())*60) <= addedEpisode[4] <= int(start_unixtime)+(int(STBHelpers.getEPGTimeSpan())*60):
					result = True
					break
		else:
			for addedEpisode in self.addedEpisodes:
				if ((addedEpisode[0] == season and addedEpisode[1] == episode) or addedEpisode[2] == title) and addedEpisode[3] == sender.lower() and int(start_unixtime)-(int(STBHelpers.getEPGTimeSpan())*60) <= addedEpisode[4] <= int(start_unixtime)+(int(STBHelpers.getEPGTimeSpan())*60):
					result = True
					break

		return result

	def getTimes(self):
		changesMade = False
		self.countTimer = 0
		if len(self.sendetermine_list) != 0:
			lt = time.localtime()
			self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
			print "\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog("\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit, True)
			for serien_name, sender, datum, startzeit, endzeit, staffel, episode, title, status, rightimage in self.sendetermine_list:
				if int(status) == 1:
					# initialize strings
					seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
					label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)
					
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
					(margin_before, margin_after) = getMargins(serien_name, sender)
					start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
					end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

					# get VPS settings for channel
					vpsSettings = getVPS(sender, serien_name)

					# get tags from marker
					tags = getTags(serien_name)

					# überprüft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert

					(dirname, dirname_serie) = getDirname(serien_name, staffel)

					# check anzahl auf hdd und added
					if str(episode).isdigit():
						if int(episode) == 0:
							bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, str(int(episode)), title, searchOnlyActiveTimers = True)
							bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False, title)
						else:
							bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, str(int(episode)), searchOnlyActiveTimers = True)
							bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False)
					else:
						bereits_vorhanden = checkAlreadyAdded(serien_name, staffel, episode, searchOnlyActiveTimers = True)
						bereits_vorhanden_HDD = STBHelpers.countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False)

					NoOfRecords = config.plugins.serienRec.NoOfRecords.value
					preferredChannel = 1
					useAlternativeChannel = 0
					cCursor = dbSerRec.cursor()
					cCursor.execute("SELECT AnzahlWiederholungen, preferredChannel, useAlternativeChannel FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
					row = cCursor.fetchone()
					if row:
						(NoOfRecords, preferredChannel, useAlternativeChannel) = row
						if useAlternativeChannel == -1:
							useAlternativeChannel = config.plugins.serienRec.useAlternativeChannel.value
						if not NoOfRecords:
							NoOfRecords = config.plugins.serienRec.NoOfRecords.value
					cCursor.close()

					params = (serien_name, sender, startzeit, start_unixtime, margin_before, margin_after, end_unixtime, label_serie, staffel, episode, title, dirname, preferredChannel, bool(useAlternativeChannel), vpsSettings, tags)
					if (bereits_vorhanden < NoOfRecords) and (bereits_vorhanden_HDD < NoOfRecords):
						TimerDone = self.doTimer(params)
					else:
						writeLog("Serie ' %s ' -> Staffel/Episode bereits vorhanden ' %s '" % (serien_name, seasonEpisodeString))
						TimerDone = self.doTimer(params, config.plugins.serienRec.forceManualRecording.value)
					if TimerDone:
						# erstellt das serien verzeichnis
						CreateDirectory(serien_name, staffel)

			writeLog("Es wurde(n) %s Timer erstellt." % str(self.countTimer), True)
			print "[SerienRecorder] Es wurde(n) %s Timer erstellt." % str(self.countTimer)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			print "---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"
			#self.session.open(serienRecRunAutoCheck, False)
			self.session.open(serienRecReadLog)
			if self.countTimer:
				changesMade = True

		else:
			self['title'].setText("Keine Sendetermine ausgewählt.")
			print "[SerienRecorder] keine Sendetermine ausgewählt."
			
		return changesMade

	def doTimer(self, params, answer=True):
		if not answer:
			return False
		else:
			(serien_name, sender, startzeit, start_unixtime, margin_before, margin_after, end_unixtime, label_serie, staffel, episode, title, dirname, preferredChannel, useAlternativeChannel, vpsSettings, tags) = params
			# check sender
			cSener_list = self.checkSender(sender)
			if len(cSener_list) == 0:
				webChannel = sender
				stbChannel = ""
				altstbChannel = ""
			else:
				(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSener_list[0]

			TimerOK = False
			if stbChannel == "":
				writeLog("' %s ' - Kein STB-Kanal gefunden -> ' %s '" % (serien_name, webChannel))
			elif int(status) == 0:
				writeLog("' %s ' - STB-Kanel deaktiviert -> ' %s '" % (serien_name, webChannel))
			else:
				if config.plugins.serienRec.TimerName.value == "0":
					timer_name = label_serie
				elif config.plugins.serienRec.TimerName.value == "2":
					timer_name = "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title)
				else:
					timer_name = serien_name

				if preferredChannel == 1:
					timer_stbChannel = stbChannel
					timer_stbRef = stbRef
					timer_altstbChannel = altstbChannel
					timer_altstbRef = altstbRef
				else:
					timer_stbChannel = altstbChannel
					timer_stbRef = altstbRef
					timer_altstbChannel = stbChannel
					timer_altstbRef = stbRef
			
				# try to get eventID (eit) from epgCache
				eit, end_unixtime_eit, start_unixtime_eit = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, timer_stbRef)
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				konflikt = None

				# versuche timer anzulegen
				#if checkTuner(start_unixtime_eit, end_unixtime_eit, timer_stbRef):
				if True:
					result = serienRecAddTimer.addTimer(timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), eit, False, dirname, vpsSettings, tags, None)
					if result["result"]:
						if self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit):
							self.countTimer += 1
							TimerOK = True
					else:
						konflikt = result["message"]
				else:
					print "[SerienRecorder] Tuner belegt: %s %s" % (label_serie, startzeit)
					writeLog("Tuner belegt: %s %s" % (label_serie, startzeit), True)

				if (not TimerOK) and (useAlternativeChannel):
					# try to get eventID (eit) from epgCache
					alt_eit, alt_end_unixtime_eit, alt_start_unixtime_eit = STBHelpers.getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, timer_altstbRef)
					# versuche timer anzulegen
					#if checkTuner(alt_start_unixtime_eit, alt_end_unixtime_eit, timer_altstbRef):
					if True:
						result = serienRecAddTimer.addTimer(timer_altstbRef, str(alt_start_unixtime_eit), str(alt_end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), alt_eit, False, dirname, vpsSettings, tags, None)
						if result["result"]:
							konflikt = None
							if self.addRecTimer(serien_name, staffel, episode, title, str(alt_start_unixtime_eit), timer_altstbRef, webChannel, alt_eit):
								self.countTimer += 1
								TimerOK = True
						else:
							konflikt = result["message"]
					else:
						print "[SerienRecorder] Tuner belegt: %s %s" % (label_serie, startzeit)
						writeLog("Tuner belegt: %s %s" % (label_serie, startzeit), True)

				if (not TimerOK) and (konflikt):
					writeLog("' %s ' - ACHTUNG! -> %s" % (label_serie, konflikt), True)
					dbMessage = result["message"].replace("Conflicting Timer(s) detected!", "").strip()

					result = serienRecAddTimer.addTimer(timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), eit, True, dirname, vpsSettings, tags, None)
					if result["result"]:
						if self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit, False):
							self.countTimer += 1
							TimerOK = True
						cCursor = dbSerRec.cursor()
						cCursor.execute("INSERT OR IGNORE INTO TimerKonflikte (Message, StartZeitstempel, webChannel) VALUES (?, ?, ?)", (dbMessage, int(start_unixtime_eit), webChannel))
						cCursor.close()

			return TimerOK

	def keyOK(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		sindex = self['menu_list'].getSelectedIndex()
		if len(self.sendetermine_list) != 0:
			if int(self.sendetermine_list[sindex][8]) == 0:
				self.sendetermine_list[sindex][8] = "1"
			else:
				self.sendetermine_list[sindex][8] = "0"
			self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))

	def keyLeft(self):
		self['menu_list'].pageUp()

	def keyRight(self):
		self['menu_list'].pageDown()

	def keyDown(self):
		self['menu_list'].down()

	def keyUp(self):
		self['menu_list'].up()

	def checkSender(self, mSender):
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT DISTINCT alleSender, SerienMarker.ID FROM SenderAuswahl, SerienMarker WHERE SerienMarker.Url LIKE ?", ('%' + self.serien_id, ))
		row = cCursor.fetchone()
		alleSender = 1
		id = 0
		if row:
			(alleSender, id) = row

		if alleSender == 1 or self.FilterMode == 1:
			cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (mSender.lower(),))
		else:
			cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels, SenderAuswahl WHERE LOWER(WebChannel)=? AND LOWER(SenderAuswahl.ErlaubterSender)=? AND SenderAuswahl.ID=?", (mSender.lower(),mSender.lower(),id))
		row = cCursor.fetchone()
		if row:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
			if altstbChannel == "":
				altstbChannel = stbChannel
				altstbRef = stbRef
			elif stbChannel == "":
				stbChannel = altstbChannel
				stbRef = altstbRef
			fSender.append((webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status))
		cCursor.close()
		return fSender

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, TimerAktiviert=True):
		result = False
		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=?", (serien_name.lower(), start_time))
		row = cCursor.fetchone()
		if row:
			print "[SerienRecorder] Timer bereits vorhanden: %s %s - %s" % (serien_name, seasonEpisodeString, title)
			writeLog("Timer bereits vorhanden: %s %s - %s" % (serien_name, seasonEpisodeString, title))
			result = True
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, int(TimerAktiviert)))
			dbSerRec.commit()
			print "[SerienRecorder] Timer angelegt: %s %s - %s" % (serien_name, seasonEpisodeString, title)
			writeLog("Timer angelegt: %s %s - %s" % (serien_name, seasonEpisodeString, title))
			result = True
		cCursor.close()
		return result	
		
	def keyRed(self):
		if config.plugins.serienRec.refreshViews.value:
			self.close(self.changesMade)
		else:
			self.close(False)

	def keyGreen(self):
		if self.getTimes():
			self.changesMade = True
			self.searchEvents()
			
	def keyYellow(self):
		self['text_red'].setText("")
		self['text_green'].setText("")
		self['text_yellow'].setText("")

		self.sendetermine_list = []
		self.loading = True
		self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))

		if self.FilterMode is 0:
			self.FilterMode = 1
			self['text_yellow'].setText("Filter umschalten")
			self.title_txt = "aktive Sender"
		elif self.FilterMode is 1:
			self.FilterMode = 2
			self['text_yellow'].setText("Filter ausschalten")
			self.title_txt = "Marker Sender"
		else:
			self.FilterMode = 0
			self['text_yellow'].setText("Filter einschalten")
			self.title_txt = "alle"
			
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche ' %s '" % self.serien_name)
		print self.serie_url

		self.start = time.time()

		if self.FilterMode is 0:
			webChannels = []
		elif self.FilterMode is 1:
			webChannels = getWebSenderAktiv()
		else:
			webChannels = getMarkerChannels(self.serien_id)

		try:
			transmissions = SeriesServer().doGetTransmissions(self.serien_id, 0, webChannels)
		except:
			transmissions = None
		self.resultsEvents(transmissions)

	def keyBlue(self):
		self.session.openWithCallback(self.searchEvents, serienRecTimer)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if config.plugins.serienRec.refreshViews.value:
			self.close(self.changesMade)
		else:
			self.close(False)

	def dataError(self, error, url=None):
		if url:
			writeErrorLog("   serienRecSendeTermine(): %s\n   Serie: %s\n   Url: %s" % (error, self.serien_name, url))
		else:
			writeErrorLog("   serienRecSendeTermine(): %s\n   Serie: %s" % (error, self.serien_name))
		print error


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
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		if readConfig:
			ReadConfigFile()
			
		self.setupSkin()
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)

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
		self.session.openWithCallback(self.switchOffAdvice, MessageBox, _("Hinweis:\n"
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
		
	def setupSkin(self):
		self.skin = None
		InitSkin(self)
		
		self['config'] = ConfigList([])
		#self['config'].list.setItemHeight(22) funktioniert nicht
		self['config'].show()

		self['title'].setText("SerienRecorder - Einstellungen:")
		self['text_red'].setText("Defaultwerte")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Verzeichnis auswählen")
		self['text_yellow'].setText("in Datei speichern")
		self['text_blue'].setText("aus Datei laden")
		self['text_menu'].setText("Sender zuordnen")

		self['config_information'].show()
		self['config_information_text'].show()
		global showAllButtons
		if not showAllButtons:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			#self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			#self['text_ok'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['bt_menu'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
								[buttonText_na, buttonText_na, "About"],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
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
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
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
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
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
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
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
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.coverPath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
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
			if self['config'].getCurrent()[1] in (config.plugins.serienRec.forceRecording, config.plugins.serienRec.ActionOnNew): self.setInfoText()
			if self['config'].getCurrent()[1] not in (config.plugins.serienRec.setupType,
													  config.plugins.serienRec.savetopath,
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
			if self['config'].getCurrent()[1] in (config.plugins.serienRec.forceRecording, config.plugins.serienRec.ActionOnNew): self.setInfoText()
			if self['config'].getCurrent()[1] not in (config.plugins.serienRec.savetopath,
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
		self.list.append(getConfigListEntry("---------  SYSTEM:  -------------------------------------------------------------------------------------------"))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("ID der Box:", config.plugins.serienRec.BoxID))
			self.list.append(getConfigListEntry("Neue Serien-Marker nur auf dieser Box aktivieren:", config.plugins.serienRec.activateNewOnThisSTBOnly))
		self.list.append(getConfigListEntry("Umfang der Einstellungen:", config.plugins.serienRec.setupType))
		self.list.append(getConfigListEntry("Speicherort der Aufnahmen:", config.plugins.serienRec.savetopath))
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
			self.list.append(getConfigListEntry("Erstelle Backup vor Suchlauf:", config.plugins.serienRec.AutoBackup))
			if config.plugins.serienRec.AutoBackup.value:
				self.list.append(getConfigListEntry("    Speicherort für Backup:", config.plugins.serienRec.BackupPath))
				self.list.append(getConfigListEntry("    Backup-Dateien löschen die älter als x Tage sind:", config.plugins.serienRec.deleteBackupFilesOlderThan))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry("---------  AUTO-CHECK:  ---------------------------------------------------------------------------------------"))
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
			self.list.append(getConfigListEntry("    Neue Serien Marker erzeugen:", config.plugins.serienRec.tvplaner_create_marker))
#			self.list.append(getConfigListEntry("    Mailbox alle <n> Minuten überprüfen:", config.plugins.serienRec.imap_check_interval))
		self.list.append(getConfigListEntry("Timer für X Tage erstellen:", config.plugins.serienRec.checkfordays))
		if config.plugins.serienRec.setupType.value == "1":
			self.list.append(getConfigListEntry("Früheste Zeit für Timer:", config.plugins.serienRec.globalFromTime))
			self.list.append(getConfigListEntry("Späteste Zeit für Timer:", config.plugins.serienRec.globalToTime))
			self.list.append(getConfigListEntry("Versuche Timer aus dem EPG zu aktualisieren:", config.plugins.serienRec.eventid))
			self.list.append(getConfigListEntry("Immer aufnehmen wenn keine Wiederholung gefunden wird:", config.plugins.serienRec.forceRecording))
			if config.plugins.serienRec.forceRecording.value:
				self.list.append(getConfigListEntry("    maximal X Tage auf Wiederholung warten:", config.plugins.serienRec.TimeSpanForRegularTimer))
			self.list.append(getConfigListEntry("Anzahl der Aufnahmen pro Episode:", config.plugins.serienRec.NoOfRecords))
			self.list.append(getConfigListEntry("Anzahl der Tuner für Aufnahmen einschränken:", config.plugins.serienRec.selectNoOfTuners))
			if config.plugins.serienRec.selectNoOfTuners.value:
				self.list.append(getConfigListEntry("    maximale Anzahl der zu benutzenden Tuner:", config.plugins.serienRec.tuner))
			self.list.append(getConfigListEntry("Aktion bei neuer Serie/Staffel:", config.plugins.serienRec.ActionOnNew))
			if config.plugins.serienRec.ActionOnNew.value != "0":
				self.list.append(getConfigListEntry("    auch bei manuellem Suchlauf:", config.plugins.serienRec.ActionOnNewManuell))
				self.list.append(getConfigListEntry("    Einträge löschen die älter sind als X Tage:", config.plugins.serienRec.deleteOlderThan))
			if not isDreamboxOS:
				self.list.append(getConfigListEntry("nach Änderungen Suchlauf beim Beenden starten:", config.plugins.serienRec.runAutocheckAtExit))
		#if config.plugins.serienRec.updateInterval.value == 24:
		if config.plugins.serienRec.autochecktype.value == "1":
			self.list.append(getConfigListEntry("Aus Deep-Standby aufwecken:", config.plugins.serienRec.wakeUpDSB))
		if config.plugins.serienRec.autochecktype.value in ("1", "2"):
			self.list.append(getConfigListEntry("Aktion nach dem automatischen Suchlauf:", config.plugins.serienRec.afterAutocheck))
			if config.plugins.serienRec.setupType.value == "1":
				if int(config.plugins.serienRec.afterAutocheck.value):
					self.list.append(getConfigListEntry("    Timeout für (Deep-)Standby-Abfrage (in Sek.):", config.plugins.serienRec.DSBTimeout))
			
		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry("---------  TIMER:  --------------------------------------------------------------------------------------------"))
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
			self.list.append(getConfigListEntry(""))
			self.list.append(getConfigListEntry("---------  OPTIMIERUNGEN:  ------------------------------------------------------------------------------------"))
			self.list.append(getConfigListEntry("Intensive Suche nach angelegten Timern:", config.plugins.serienRec.intensiveTimersuche))
			self.list.append(getConfigListEntry("Zeige ob die Episode als Aufnahme auf der HDD ist:", config.plugins.serienRec.sucheAufnahme))
			self.list.append(getConfigListEntry(""))
			self.list.append(getConfigListEntry("---------  GUI:  ----------------------------------------------------------------------------------------------"))
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
			self.list.append(getConfigListEntry("Zeige Cover:", config.plugins.serienRec.showCover))
			if config.plugins.serienRec.showCover.value:
				self.list.append(getConfigListEntry("    Speicherort der Cover:", config.plugins.serienRec.coverPath))
			self.list.append(getConfigListEntry("Korrektur der Schriftgröße in Listen:", config.plugins.serienRec.listFontsize))
			self.list.append(getConfigListEntry("Anzahl der wählbaren Staffeln im Menü SerienMarker:", config.plugins.serienRec.max_season))
			self.list.append(getConfigListEntry("Vor Löschen in SerienMarker und Timer-Liste Benutzer fragen:", config.plugins.serienRec.confirmOnDelete))
			self.list.append(getConfigListEntry("Benachrichtigung beim Suchlauf:", config.plugins.serienRec.showNotification))
			self.list.append(getConfigListEntry("Benachrichtigung bei Timerkonflikten:", config.plugins.serienRec.showMessageOnConflicts))
			self.list.append(getConfigListEntry("Screens bei Änderungen sofort aktualisieren:", config.plugins.serienRec.refreshViews))
			self.list.append(getConfigListEntry("Staffelauswahl bei neuen Markern:", config.plugins.serienRec.defaultStaffel))
			self.list.append(getConfigListEntry("Öffne Marker-Ansicht nach Hinzufügen neuer Marker:", config.plugins.serienRec.openMarkerScreen))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry("---------  LOG:  ----------------------------------------------------------------------------------------------"))
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
			self.list.append(getConfigListEntry("ERROR LOG aktivieren:", config.plugins.serienRec.writeErrorLog))

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
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Aufnahme-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
			start_dir = config.plugins.serienRec.LogFilePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "LogFile-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.BackupPath:
			start_dir = config.plugins.serienRec.BackupPath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Backup-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.databasePath:
			start_dir = config.plugins.serienRec.databasePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Datenbank-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.coverPath:
			start_dir = config.plugins.serienRec.coverPath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Cover-Verzeichnis auswählen")
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.piconPath:
			start_dir = config.plugins.serienRec.piconPath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Picon-Verzeichnis auswählen")
			
	def selectedMediaFile(self, res):
		if res is not None:
			if self['config'].getCurrent()[1] == config.plugins.serienRec.savetopath:
				print res
				config.plugins.serienRec.savetopath.value = res
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
			config.plugins.serienRec.savetopath :              ("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen gespeichert werden.", "Speicherort_der_Aufnahme"),
			config.plugins.serienRec.seriensubdir :            ("Bei 'ja' wird für jede Serien ein eigenes Unterverzeichnis (z.B.\n'%s<Serien_Name>/') für die Aufnahmen erstellt." % config.plugins.serienRec.savetopath.value, "Serien_Verzeichnis_anlegen"),
			config.plugins.serienRec.seasonsubdir :            ("Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis (z.B.\n"
			                                                    "'%s<Serien_Name>/Season %s') erstellt." % (config.plugins.serienRec.savetopath.value, str("1").zfill(config.plugins.serienRec.seasonsubdirnumerlength.value)), "Staffel_Verzeichnis_anlegen"),
			config.plugins.serienRec.seasonsubdirnumerlength : ("Die Anzahl der Stellen, auf die die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.seasonsubdirfillchar :    ("Auswahl, ob die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.deltime :                 ("Uhrzeit, zu der der automatische Timer-Suchlauf täglich ausgeführt wird (%s:%s Uhr)." % (str(config.plugins.serienRec.deltime.value[0]).zfill(2), str(config.plugins.serienRec.deltime.value[1]).zfill(2)), "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.maxDelayForAutocheck :    ("Hier wird die Zeitspanne (in Minuten) eingestellt, innerhalb welcher der automatische Timer-Suchlauf ausgeführt wird. Diese Zeitspanne beginnt zu der oben eingestellten Uhrzeit.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.Autoupdate :              ("Bei 'ja' wird bei jedem Start des SerienRecorders nach verfügbaren Updates gesucht.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.tvplaner :                ("Bei 'ja' ruft der SerienRecorder regelmäßig eine IMAP Mailbox ab und sucht nach E-Mails des Wunschliste TV-Planers", ""),
			config.plugins.serienRec.imap_server :             ("Name des IMAP Servers (z.B. imap.gmx.de)", "x"),
			config.plugins.serienRec.imap_server_ssl :         ("Zugriff über SSL (Port ohne SSL = 143, Port mit SSL = 993", ""),
			config.plugins.serienRec.imap_server_port :        ("Portnummer für den Zugriff", ""),
			config.plugins.serienRec.imap_login :              ("Benutzername des IMAP Accounts (z.B. abc@gmx.de)", "x"),
			config.plugins.serienRec.imap_password :           ("Passwort des IMAP Accounts", "x"),
			config.plugins.serienRec.imap_mailbox :            ("Name des Ordners in dem die E-Mails ankommen (z.B. INBOX)", "x"),
			config.plugins.serienRec.imap_mail_subject :       ("Betreff der TV-Planer E-Mails (default: TV Wunschliste TV-Planer)", "x"),
			config.plugins.serienRec.imap_check_interval :     ("Die Mailbox wird alle <n> Minuten überprüft (default: 30)", "x"),
			config.plugins.serienRec.tvplaner_create_marker :  ("Bei 'ja' werden nicht vorhandene Serien Marker automatisch erzeugt", "x"),
			config.plugins.serienRec.databasePath :            ("Das Verzeichnis auswählen und/oder erstellen, in dem die Datenbank gespeichert wird.", "Speicherort_der_Datenbank"),
			config.plugins.serienRec.AutoBackup :              ("Bei 'ja' werden vor jedem Timer-Suchlauf die Datenbank des SR, die 'alte' log-Datei und die enigma2-Timer-Datei ('/etc/enigma2/timers.xml') in ein neues Verzeichnis kopiert, "
			                                                    "dessen Name sich aus dem aktuellen Datum und der aktuellen Uhrzeit zusammensetzt (z.B.\n'%s%s%s%s%s%s/')." % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)), "1.3_Die_globalen_Einstellungen"),
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
			config.plugins.serienRec.ActionOnNew :             ("Wird eine neue Staffel oder Serie gefunden (d.h. Folge 1), wird die hier eingestellt Aktion ausgeführt:\n"
			                                                    "  - 'keine': Es wird nicht nach neuen Serien/Staffeln gesucht.\n"
																"  - 'benachrichtigen': Wurde eine neue Serie oder Staffel gefunden wirde eine Nachricht eingeblendet.\n"
																"  - 'suchen': Es wird nur eine Suche durchgeführt, die Ergebnisse können über Taste 3 abgerufen werden.", "Aktion_bei_neuer_Staffel"),
			config.plugins.serienRec.ActionOnNewManuell :      ("Bei 'nein' wird bei manuell gestarteten Suchläufen NICHT nach Staffel-/Serienstarts gesucht.", "Aktion_bei_neuer_Staffel"),
			config.plugins.serienRec.deleteOlderThan :         ("Staffel-/Serienstarts die älter als die hier eingestellte Anzahl von Tagen (also vor dem %s) sind, werden beim Timer-Suchlauf automatisch aus der Datenbank entfernt "
																"und auch nicht mehr angezeigt." % time.strftime("%d.%m.%Y", time.localtime(int(time.time()) - (int(config.plugins.serienRec.deleteOlderThan.value) * 86400))), "1.3_Die_globalen_Einstellungen"),
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
			                                                    "Ansonsten wird versucht die einzelnen Episoden einer Event-Programmierung zu erkennen.\n\n"
			                                                    "Bei 'Timer anlegen' wird zwar weiterhin nur ein Timer angelegt, aber die Einzelepisoden werden in der Datenbank als 'bereits aufgenommen' markiert."
			                                                    "Sollten bereits alle Einzelepisoden vorhanden sein, wird für das Event kein Timer angelegt.\n\n"
			                                                    "Bei 'Einzelepisoden bevorzugen' wird versucht Timer für die Einzelepisoden anzulegen. "
			                                                    "Falls das nicht möglich ist, wird das Event aufgenommen.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.TimerName :               ("Es kann ausgewählt werden, wie der Timername gebildet werden soll, dieser Name bestimmt auch den Namen der Aufnahme. Die Beschreibung enthält weiterhin die Staffel und Episoden Informationen.\n"
																"Falls das Plugin 'SerienFilm' verwendet wird, sollte man die Einstellung '<Serienname>' wählen, damit die Episoden korrekt in virtuellen Ordnern zusammengefasst werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.selectBouquets :          ("Bei 'ja' werden 2 Bouquets (Standard und Alternativ) für die Sender-Zuordnung verwendet werden.\n"
			                                                    "Bei 'nein' wird das erste Bouquet für die Sender-Zuordnung benutzt.", "Bouquet_Auswahl"),
			config.plugins.serienRec.MainBouquet :             ("Auswahl, welches Bouquet bei der Sender-Zuordnung als Standard verwendet werden soll.", "Bouquet_Auswahl"),
			config.plugins.serienRec.AlternativeBouquet :      ("Auswahl, welches Bouquet bei der Sender-Zuordnung als Alternative verwendet werden soll.", "Bouquet_Auswahl"),
			config.plugins.serienRec.useAlternativeChannel :   ("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
										                        "falls der Timer auf dem bevorzugten Sender nicht angelegt werden kann.", "Bouquet_Auswahl"),
			config.plugins.serienRec.showPicons :              ("Bei 'ja' werden in der Hauptansicht auch die Sender-Logos angezeigt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.piconPath :               ("Wählen Sie das Verzeichnis aus dem die Sender-Logos geladen werden sollen. Der SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showCover :               ("Bei 'nein' werden keine Cover angezeigt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.listFontsize :            ("Damit kann bei zu großer oder zu kleiner Schrift eine individuelle Anpassung erfolgen. SerienRecorder muß neu gestartet werden damit die Änderung wirksam wird.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.intensiveTimersuche :     ("Bei 'ja' wird in der Hauptansicht intensiver nach vorhandenen Timern gesucht, d.h. es wird vor der Suche versucht die Anfangszeit aus dem EPGCACHE zu aktualisieren was aber zeitintensiv ist.", "intensive_Suche"),
			config.plugins.serienRec.sucheAufnahme :           ("Bei 'ja' wird ein Symbol für jede Episode angezeigt, die als Aufnahme auf der Festplatte gefunden wurde, diese Suche ist aber sehr zeitintensiv.", "Aufnahme_vorhanden"),
			config.plugins.serienRec.max_season :              ("Die höchste Staffelnummer, die für Serienmarker in der Staffel-Auswahl gewählt werden kann.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.confirmOnDelete :         ("Bei 'ja' erfolt eine Sicherheitsabfrage ('Soll ... wirklich entfernt werden?') vor dem entgültigen Löschen von Serienmarkern oder Timern.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showNotification :        ("Je nach Einstellung wird eine Nachricht auf dem Bildschirm eingeblendet, sobald der automatische Timer-Suchlauf startet bzw. endet.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.showMessageOnConflicts :  ("Bei 'ja' wird für jeden Timer, der beim automatische Timer-Suchlauf wegen eines Konflikts nicht angelegt werden konnte, eine Nachricht auf dem Bildschirm eingeblendet.\n"
			                                                    "Diese Nachrichten bleiben solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.DisplayRefreshRate :      ("Das Zeitintervall in Sekunden, in dem die Anzeige der Options-Tasten wechselt.", "1.3_Die_globalen_Einstellungen"),
			config.plugins.serienRec.refreshViews :            ("Bei 'ja' werden die Anzeigen nach Änderungen von Markern, Sendern, etc. sofort aktualisiert, was aber je nach STB-Typ und Internet-Verbindung zeitintensiv sein kann.\n"
			                                                    "Bei 'nein' erfolgt die Aktualisierung erst, wenn die Anzeige erneut geöffnet wird.", "Sofortige_Aktualisierung"),
			config.plugins.serienRec.defaultStaffel :          ("Auswahl, ob bei neuen Markern die Staffeln manuell eingegeben werden, oder 'Alle' ausgewählt wird.", "1.3_Die_globalen_Einstellungen"),
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
			                                                    "sowie wenn gemäß der Einstellung 'Immer aufnehmen wenn keine Wiederholung gefunden wird' = 'ja' "
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
		    config.plugins.serienRec.writeErrorLog:			   ("Bei 'ja' werden Verbindungs- und Lade-Fehler in einer eigenen Datei protokolliert.", "Das_Log"),
		}			

		# if config.plugins.serienRec.ActionOnNew.value != "0":
		# 	self.HilfeTexte.update({
		# 		config.plugins.serienRec.planerCacheEnabled : ("Bei 'ja' werden beim automatischen Suchlauf die Daten für den Serienplaner und die Sendetermine geladen und gespeichert. "
		# 													   "Die Speicherung der Serienplaner-Daten erfolgt nicht, wenn der Suchlauf manuell gestartet wurde.", "Daten_speichern")
		# 	})
		# else:
		# 	self.HilfeTexte.update({
		# 		config.plugins.serienRec.planerCacheEnabled : ("Bei 'ja' werden beim automatischen Suchlauf die Sendetermine geladen und gespeichert.", "Daten_speichern")
		# 	})

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

		if config.plugins.serienRec.ActionOnNew.value != "0" or config.plugins.serienRec.firstscreen.value == "0":
			config.plugins.serienRec.planerCacheEnabled.value = True
			config.plugins.serienRec.planerCacheSize.value = 4
		else:
			config.plugins.serienRec.planerCacheEnabled.value = False
			config.plugins.serienRec.planerCacheSize.value = 4

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
			print "secure login"
			config.plugins.serienRec.imap_login_hidden.value = encode(getmac("eth0"), config.plugins.serienRec.imap_login.value)
			config.plugins.serienRec.imap_login.value = "*"
		config.plugins.serienRec.imap_login.save()
		config.plugins.serienRec.imap_login_hidden.save()
		if config.plugins.serienRec.imap_password.value != "*":
			print "secure passwort"
			config.plugins.serienRec.imap_password_hidden.value = encode(getmac("eth0"), config.plugins.serienRec.imap_password.value)
			config.plugins.serienRec.imap_password.value = "*"
		config.plugins.serienRec.imap_password.save()
		config.plugins.serienRec.imap_password_hidden.save()
		config.plugins.serienRec.imap_mailbox.save()
		config.plugins.serienRec.imap_mail_subject.save()
		config.plugins.serienRec.imap_mail_age.save()
		config.plugins.serienRec.imap_check_interval.save()
		config.plugins.serienRec.tvplaner_create_marker.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.AutoBackup.save()
		config.plugins.serienRec.deleteBackupFilesOlderThan.save()
		config.plugins.serienRec.coverPath.save()
		config.plugins.serienRec.BackupPath.save()
		config.plugins.serienRec.maxWebRequests.save()
		config.plugins.serienRec.margin_before.save()
		config.plugins.serienRec.margin_after.save()
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
		config.plugins.serienRec.ActionOnNew.save()
		config.plugins.serienRec.ActionOnNewManuell.save()
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
		config.plugins.serienRec.defaultStaffel.save()
		config.plugins.serienRec.openMarkerScreen.save()
		config.plugins.serienRec.showPicons.save()
		config.plugins.serienRec.piconPath.save()
		config.plugins.serienRec.showCover.save()
		config.plugins.serienRec.listFontsize.save()
		config.plugins.serienRec.intensiveTimersuche.save()
		config.plugins.serienRec.sucheAufnahme.save()
		config.plugins.serienRec.selectNoOfTuners.save()
		config.plugins.serienRec.tuner.save()
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
		config.plugins.serienRec.writeErrorLog.save()
		configfile.save()
			
		if self.SkinType != config.plugins.serienRec.SkinType.value:
			SelectSkin()
			setSkinProperties(self)

		if config.plugins.serienRec.ActionOnNew.value in ("2", "3"):
			self.session.open(MessageBox, "Die Einstellung 'Aktion bei neuer Serie/Staffel' ist so eingestellt, dass automatisch neue Serien-Marker für jede gefundene neue Serie/Staffel angelegt werden. Dies kann zu sehr vielen Serien-Markern bzw. Timern und Aufnahmen führen.", MessageBox.TYPE_INFO)
			
		global serienRecDataBase
		if serienRecDataBase == "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			self.close((True, self.setupModified, True))
		else:		
			global dbSerRec
			if dbSerRec is not None:
				dbSerRec.close()
			if not os.path.exists("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value):
				self.session.openWithCallback(self.callDbChangedMsg, MessageBox, "Im ausgewählten Verzeichnis existiert noch keine Datenbank.\nSoll die bestehende Datenbank kopiert werden?", MessageBox.TYPE_YESNO, default = True)
			else:
				serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
				dbSerRec = sqlite3.connect(serienRecDataBase)
				dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
				success = initDB()
				self.close((True, True, success))

	def callDbChangedMsg(self, answer):
		global serienRecDataBase
		if answer:
			try:
				shutil.copyfile(serienRecDataBase, "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)
				serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
				global dbSerRec
				dbSerRec = sqlite3.connect(serienRecDataBase)
				dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
			except:
				writeLog("Fehler beim Kopieren der Datenbank")
				Notifications.AddPopup("SerienRecorder Datenbank konnte nicht kopiert werden.\nDer alte Datenbankpfad wird wiederhergestellt!", MessageBox.TYPE_INFO, timeout=10)
				serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
		else:
			serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
		
		success = initDB()
		self.close((True, True, success))

	def openChannelSetup(self):
		self.session.openWithCallback(self.changedEntry, serienRecMainChannelEdit)

	def keyCancel(self):
		if self.setupModified:
			self.save()
		else:
			self.close((False, False, True))

class serienRecMarkerSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, Serie):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.Serie = Serie
		
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red"	: (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"green"	: (self.save, "Einstellungen speichern und zurück zur Serien-Marker-Ansicht"),
			"cancel": (self.cancel, "Änderungen verwerfen und zurück zur Serien-Marker-Ansicht"),
			"ok"	: (self.ok, "Fenster für Verzeichnisauswahl öffnen"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
		    "startTeletext" : (self.showAbout, "Über dieses Plugin"),
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags FROM SerienMarker WHERE LOWER(Serie)=?", (self.Serie.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (None, -1, None, None, None, None, None, 1, -1, None, None, "")
		(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags) = row
		cCursor.close()

		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = ""
		self.savetopath = ConfigText(default = AufnahmeVerzeichnis, fixed_size=False, visible_width=50)
		self.seasonsubdir = ConfigSelection(choices = [("-1", "gemäß Setup (dzt. %s)" % str(config.plugins.serienRec.seasonsubdir.value).replace("True", "ja").replace("False", "nein")), ("0", "nein"), ("1", "ja")], default=str(Staffelverzeichnis))
		
		if str(Vorlaufzeit).isdigit():
			self.margin_before = ConfigInteger(Vorlaufzeit, (0,999))
			self.enable_margin_before = ConfigYesNo(default = True)
		else:
			self.margin_before = ConfigInteger(config.plugins.serienRec.margin_before.value, (0,999))
			self.enable_margin_before = ConfigYesNo(default = False)
			
		if str(Nachlaufzeit).isdigit():
			self.margin_after = ConfigInteger(Nachlaufzeit, (0,999))
			self.enable_margin_after = ConfigYesNo(default = True)
		else:
			self.margin_after = ConfigInteger(config.plugins.serienRec.margin_after.value, (0,999))
			self.enable_margin_after = ConfigYesNo(default = False)
			
		if str(AnzahlWiederholungen).isdigit():
			self.NoOfRecords = ConfigInteger(AnzahlWiederholungen, (1,9))
			self.enable_NoOfRecords = ConfigYesNo(default = True)
		else:
			self.NoOfRecords = ConfigInteger(config.plugins.serienRec.NoOfRecords.value, (1,9))
			self.enable_NoOfRecords = ConfigYesNo(default = False)

		if str(AufnahmezeitVon).isdigit():
			self.fromTime = ConfigClock(default = int(AufnahmezeitVon)*60+time.timezone)
			self.enable_fromTime = ConfigYesNo(default = True)
		else:
			self.fromTime = ConfigClock(default = ((config.plugins.serienRec.globalFromTime.value[0]*60)+config.plugins.serienRec.globalFromTime.value[1])*60+time.timezone)
			self.enable_fromTime = ConfigYesNo(default = False)
			
		if str(AufnahmezeitBis).isdigit():
			self.toTime = ConfigClock(default = int(AufnahmezeitBis)*60+time.timezone)
			self.enable_toTime = ConfigYesNo(default = True)
		else:
			self.toTime = ConfigClock(default = ((config.plugins.serienRec.globalToTime.value[0]*60)+config.plugins.serienRec.globalToTime.value[1])*60+time.timezone)
			self.enable_toTime = ConfigYesNo(default = False)

		if str(vps).isdigit():
			self.override_vps = ConfigYesNo(default = True)
			self.enable_vps = ConfigYesNo(default = bool(vps & 0x1))
			self.enable_vps_savemode = ConfigYesNo(default = bool(vps & 0x2))
		else:
			self.override_vps = ConfigYesNo(default = False)
			self.enable_vps = ConfigYesNo(default = False)
			self.enable_vps_savemode = ConfigYesNo(default = False)

		self.preferredChannel = ConfigSelection(choices = [("1", "Standard"), ("2", "Alternativ")], default=str(preferredChannel))
		self.useAlternativeChannel = ConfigSelection(choices = [("-1", "gemäß Setup (dzt. %s)" % str(config.plugins.serienRec.useAlternativeChannel.value).replace("True", "ja").replace("False", "nein")), ("0", "nein"), ("1", "ja")], default=str(useAlternativeChannel))

		# excluded weekdays
		# each weekday is represented by a bit in the database field
		# 0 = Monday to 6 = Sunday, so if all weekdays are excluded we got 1111111 = 127
		if str(excludedWeekdays).isdigit():
			self.enable_excludedWeekdays = ConfigYesNo(default = True)
			self.excludeMonday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 0)))
			self.excludeTuesday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 1)))
			self.excludeWednesday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 2)))
			self.excludeThursday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 3)))
			self.excludeFriday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 4)))
			self.excludeSaturday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 5)))
			self.excludeSunday = ConfigYesNo(default = bool(excludedWeekdays & (1 << 6)))
		else:
			self.enable_excludedWeekdays = ConfigYesNo(default = False)
			self.excludeMonday = ConfigYesNo(default = False)
			self.excludeTuesday = ConfigYesNo(default = False)
			self.excludeWednesday = ConfigYesNo(default = False)
			self.excludeThursday = ConfigYesNo(default = False)
			self.excludeFriday = ConfigYesNo(default = False)
			self.excludeSaturday = ConfigYesNo(default = False)
			self.excludeSunday = ConfigYesNo(default = False)

		# tags
		if tags is None or len(tags) == 0:
			self.serienmarker_tags = []
		else:
			self.serienmarker_tags = pickle.loads(tags)
		self.tags = NoSave(ConfigSelection(choices = [len(self.serienmarker_tags) == 0 and "Keine" or ' '.join(self.serienmarker_tags)]))

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
		self['text_ok'].setText("Verzeichnis auswählen")
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
		self.margin_before_index = 1
		self.list = []
		self.list.append(getConfigListEntry("vom globalen Setup abweichender Speicherort der Aufnahmen:", self.savetopath))
		if self.savetopath.value:
			self.list.append(getConfigListEntry("Staffel-Verzeichnis anlegen:", self.seasonsubdir))
			self.margin_before_index += 1
			
		self.margin_after_index = self.margin_before_index + 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichenden Timervorlauf aktivieren:", self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry("      Timervorlauf (in Min.):", self.margin_before))
			self.margin_after_index += 1

		self.NoOfRecords_index = self.margin_after_index + 1
			
		self.list.append(getConfigListEntry("vom globalen Setup abweichenden Timernachlauf aktivieren:", self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry("      Timernachlauf (in Min.):", self.margin_after))
			self.NoOfRecords_index += 1
			
		self.fromTime_index = self.NoOfRecords_index + 1
			
		self.list.append(getConfigListEntry("vom globalen Setup abweichende Anzahl der Aufnahmen aktivieren:", self.enable_NoOfRecords))
		if self.enable_NoOfRecords.value:
			self.list.append(getConfigListEntry("      Anzahl der Aufnahmen:", self.NoOfRecords))
			self.fromTime_index += 1

		self.toTime_index = self.fromTime_index + 1
			
		self.list.append(getConfigListEntry("vom globalen Setup abweichende Früheste Zeit für Timer aktivieren:", self.enable_fromTime))
		if self.enable_fromTime.value:
			self.list.append(getConfigListEntry("      Früheste Zeit für Timer:", self.fromTime))
			self.toTime_index += 1

		self.list.append(getConfigListEntry("vom globalen Setup abweichende Späteste Zeit für Timer aktivieren:", self.enable_toTime))
		if self.enable_toTime.value:
			self.list.append(getConfigListEntry("      Späteste Zeit für Timer:", self.toTime))

		if VPSPluginAvailable:
			self.list.append(getConfigListEntry("vom Sender Setup abweichende VPS Einstellungen:", self.override_vps))
			if self.override_vps.value:
				self.list.append(getConfigListEntry("      VPS für diesen Serien-Marker aktivieren:", self.enable_vps))
				if self.enable_vps.value:
					self.list.append(getConfigListEntry("            Sicherheitsmodus aktivieren:", self.enable_vps_savemode))

		self.list.append(getConfigListEntry("Bevorzugte Sender-Liste:", self.preferredChannel))
		self.list.append(getConfigListEntry("Verwende alternative Sender bei Konflikten:", self.useAlternativeChannel))

		self.list.append(getConfigListEntry("Wochentage von der Timer-Erstellung ausschließen:", self.enable_excludedWeekdays))
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

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()
			
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
				if not self.savetopath.value:
					start_dir = config.plugins.serienRec.savetopath.value
				else:
					start_dir = self.savetopath.value
				self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, "Aufnahme-Verzeichnis auswählen")


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
		writeLog("Choose tags was called.", True)
		preferredTagEditor = getPreferredTagEditor()
		if preferredTagEditor:
			writeLog("Has preferred tageditor.", True)
			self.session.openWithCallback(
				self.tagEditFinished,
				preferredTagEditor,
				self.serienmarker_tags
			)

	def setInfoText(self):
		self.HilfeTexte = {
			self.savetopath :            "Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von '%s' gespeichert werden." % self.Serie,
			self.seasonsubdir :          "Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis für '%s' (z.B.\n'%sSeason 001') erstellt." % (self.Serie, self.savetopath.value),
			self.enable_margin_before :  ("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
										  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n" 
						  				  "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
						  				  "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.margin_before :         ("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
								          "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.Serie,
			self.enable_margin_after :   ("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
									  	  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
									      "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
									  	  "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.margin_after :          ("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
								          "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.Serie,
			self.enable_NoOfRecords :    ("Bei 'ja' kann die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen, eingestellt werden.\n"
									      "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.\n"
									      "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.NoOfRecords :           ("Die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.") % self.Serie,
			self.enable_fromTime :       ("Bei 'ja' kann die erlaubte Zeitspanne (ab Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
									      "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.\n"
									      "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.fromTime :              ("Die Uhrzeit, ab wann Aufnahmen von '%s' erlaubt sind.\n"
							              "Die erlaubte Zeitspanne beginnt um %s:%s Uhr.\n" 
							              "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.") % (self.Serie, str(self.fromTime.value[0]).zfill(2), str(self.fromTime.value[1]).zfill(2)),
			self.enable_toTime :         ("Bei 'ja' kann die erlaubte Zeitspanne (bis Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.\n"
								          "Bei 'nein' gilt die Einstellung vom globalen Setup.") % self.Serie,
			self.toTime :                ("Die Uhrzeit, bis wann Aufnahmen von '%s' erlaubt sind.\n"
						                  "Die erlaubte Zeitspanne endet um %s:%s Uhr.\n" 
						                  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.") % (self.Serie, str(self.toTime.value[0]).zfill(2), str(self.toTime.value[1]).zfill(2)),
			self.override_vps :          ("Bei 'ja' kann VPS für Aufnahmen von '%s' eingestellt werden.\n"
										  "Diese Einstellung hat Vorrang gegenüber der Einstellung des Senders für VPS.\n"
										  "Bei 'nein' gilt die Einstellung vom Sender.") % self.Serie,
			self.enable_vps :            ("Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
			                              "und endet, wenn der Sender das Ende der Ausstrahlung angibt.\n"
										  "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.Serie,
			self.enable_vps_savemode :   ("Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet. Die programmierten Start- und Endzeiten werden eingehalten.\n"
			                              "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.\n"
										  "Diese Einstellung hat Vorrang gegenüber der Sender Einstellung für VPS.") % self.Serie,
			self.preferredChannel :      "Auswahl, ob die Standard-Sender oder die alternativen Sender für die Aufnahmen von '%s' verwendet werden sollen." % self.Serie,
			self.useAlternativeChannel : ("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Sender (Standard oder alternativ) zu erstellen, "
										  "falls der Timer für '%s' auf dem bevorzugten Sender nicht angelegt werden kann.\n"
										  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Verwendung von alternativen Sendern.\n"
										  "Bei 'gemäß Setup' gilt die Einstellung vom globalen Setup.") % self.Serie,
		    self.enable_excludedWeekdays : ("Bei 'ja' können bestimmte Wochentage für die Erstellung von Timern für '%s' ausgenommen werden.\n"
										  "Es werden also an diesen Wochentage für diese Serie keine Timer erstellt.\n"
										  "Bei 'nein' werden alle Wochentage berücksichtigt.") % self.Serie,
			self.tags :                   ("Verwaltet die Tags für die Timer, die für %s angelegt werden.\n\n"
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
			AufnahmezeitVon = (self.fromTime.value[0]*60)+self.fromTime.value[1]
			
		if not self.enable_toTime.value:
			AufnahmezeitBis = None
		else:
			AufnahmezeitBis = (self.toTime.value[0]*60)+self.toTime.value[1]

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

		cCursor = dbSerRec.cursor()
		sql = "UPDATE OR IGNORE SerienMarker SET AufnahmeVerzeichnis=?, Staffelverzeichnis=?, Vorlaufzeit=?, Nachlaufzeit=?, AnzahlWiederholungen=?, AufnahmezeitVon=?, AufnahmezeitBis=?, preferredChannel=?, useAlternativeChannel=?, vps=?, excludedWeekdays=?, tags=? WHERE LOWER(Serie)=?"
		cCursor.execute(sql, (self.savetopath.value, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, int(self.preferredChannel.value), int(self.useAlternativeChannel.value), vpsSettings, excludedWeekdays, tags, self.Serie.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.close(True)

	def cancel(self):
		self.close(False)

class serienRecChannelSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, webSender):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.webSender = webSender
		
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Vorlaufzeit, Nachlaufzeit, vps FROM Channels WHERE LOWER(WebChannel)=?", (self.webSender.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (None, None, None)
		(Vorlaufzeit, Nachlaufzeit, vps) = row
		cCursor.close()

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
			
		cCursor = dbSerRec.cursor()
		cCursor.execute("UPDATE OR IGNORE Channels SET Vorlaufzeit=?, Nachlaufzeit=?, vps=? WHERE LOWER(WebChannel)=?", (Vorlaufzeit, Nachlaufzeit, vpsSettings, self.webSender.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.close()

	def cancel(self):
		self.close()

class SerienRecFileList(Screen, HelpableScreen):
	def __init__(self, session, initDir, title):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.initDir = initDir
		self.title = title
		
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
		self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Verzeichnis-Name eingeben:")

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
			if isDreamboxOS:
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
		self.session = session

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
			if isDreamboxOS:
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
		self.conflictsListe = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Message, StartZeitstempel, webChannel FROM TimerKonflikte ORDER BY StartZeitstempel")
		for row in cCursor:
			(zeile, start_time, webChannel) = row
			data = zeile.split('/')
			if data:
				self.conflictsListe.append(("%s" % data[0].strip()))
				self.conflictsListe.append(("    @ %s (%s) in Konflikt mit:" % (webChannel, time.strftime("%d.%m.%Y - %H:%M", time.localtime(start_time)))))
				data = data[1:]
				for row2 in data:
					self.conflictsListe.append(("            -> %s" % row2.strip()))
				self.conflictsListe.append(("-" * 100))
				self.conflictsListe.append((""))
		cCursor.close()
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
				cCursor = dbSerRec.cursor()
				cCursor.execute("DELETE FROM TimerKonflikte")
				dbSerRec.commit()
				cCursor.close()
				self.readConflicts()

	def callDeleteMsg(self, answer):
		if answer:
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM TimerKonflikte")
			dbSerRec.commit()
			cCursor.close()
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
			if isDreamboxOS:
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
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
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel FROM AngelegteTimer")
		for row in cCursor:
			(Serie, Staffel, Episode, title, start_time, webChannel) = row
			zeile = "%s - S%sE%s - %s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2), title)
			self.addedlist.append((zeile.replace(" - dump", " - %s" % "(Manuell hinzugefügt !!)"), Serie, Staffel, Episode, title, start_time, webChannel))
		cCursor.close()

		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Diese Episoden werden nicht mehr aufgenommen !")
		self.addedlist_tmp = self.addedlist[:]
		if config.plugins.serienRec.addedListSorted.value:
			self.addedlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.addedlist_tmp))
		self.getCover()

	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode, title, start_time, webChannel) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
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
		if self.aToEpisode == "":
			self.aToEpisode = self.aFromEpisode

		if self.aToEpisode is None: # or self.aFromEpisode is None or self.aStaffel is None:
			return
		else:
			print "[SerienRecorder] Staffel: %s" % self.aStaffel
			print "[SerienRecorder] von Episode: %s" % self.aFromEpisode
			print "[SerienRecorder] bis Episode: %s" % self.aToEpisode

			if addToAddedList(self.aSerie, self.aFromEpisode, self.aToEpisode, self.aStaffel, "dump"):
				self.readAdded()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = []

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie FROM SerienMarker ORDER BY Serie")
			cMarkerList = cCursor.fetchall()
			for row in cMarkerList:
				l.append(row)
			cCursor.close()
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
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND StartZeitstempel=? AND LOWER(webChannel)=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
		self.close()

	def keyYellow(self):
		if len(self.addedlist_tmp) != 0:
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		serien_id = None
		if row:
			(url, ) = row
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

class serienRecShowSeasonBegins(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.ErrorMsg = "unbekannt"
		self.piconLoader = PiconLoader()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "Marker für die ausgewählte Serie hinzufügen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"red"	: (self.keyRed, "ausgewählten Eintrag löschen"),
			"yellow": (self.keyYellow, "umschalten alle/nur zukünftige anzeigen"),
			"blue"	: (self.keyBlue, "alle Einträge aus der Liste endgültig löschen"),
			"left"  : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right" : (self.keyRight, "zur nächsten Seite blättern"),
			"up"    : (self.keyUp, "eine Zeile nach oben"),
			"down"  : (self.keyDown, "eine Zeile nach unten"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"4"		: (self.serieInfo, "Informationen zur ausgewählten Serie anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.filter = config.plugins.serienRec.serienRecShowSeasonBegins_filter.value

		self.setupSkin()

		self.changesMade = False
		self.proposalList = []
		self.serviceRefs = getActiveServiceRefs()
		self.onLayoutFinish.append(self.readProposal)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText("Eintrag löschen")
		self['text_ok'].setText("Marker hinzufügen")
		if self.filter:
			self['text_yellow'].setText("Zeige alle")
		else:
			self['text_yellow'].setText("Zeige nur neue")
		self['text_blue'].setText("Liste leeren")

		self.num_bt_text[3][0] = buttonText_na
			
		self.displayTimer = None
		global showAllButtons
		if showAllButtons:
			Skin1_Settings(self)
		else:
			self.displayMode = 2
			self.updateMenuKeys()
		
			self.displayTimer = eTimer()
			if isDreamboxOS:
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
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()
			
			self['text_red'].show()
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
		
	def readProposal(self):
		self.proposalList = []
		markers = getAllMarkers()
		cCursor = dbSerRec.cursor()
		if self.filter:
			now = datetime.datetime.now()
			current_time = datetime.datetime(now.year, now.month, now.day, 00, 00).strftime("%s")
			cCursor.execute("SELECT Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag FROM NeuerStaffelbeginn WHERE UTCStaffelStart >= ? GROUP BY Serie, Staffel", (current_time, ))
		else:
			cCursor.execute("SELECT Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag FROM NeuerStaffelbeginn WHERE CreationFlag=? OR CreationFlag>=1 GROUP BY Serie, Staffel", (self.filter, ))
		for row in cCursor:
			# 0 = no marker, 1 = active marker, 2 = deactive marker
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = row
			if Serie.lower() in markers:
				CreationFlag = 2 if markers[Serie.lower()] else 3
			self.proposalList.append((Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag))
		cCursor.close()
		
		self['title'].setText("Neue Serie(n) / Staffel(n):")
		
		self.proposalList.sort(key=lambda x: time.strptime(x[3].split(",")[1].strip(), "%d.%m.%Y"))
		self.chooseMenuList.setList(map(self.buildList, self.proposalList))
		self.getCover()
			
	def buildList(self, entry):
		(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = entry

		icon = imageNone = "%simages/black.png" % serienRecMainPath
		imageNeu = "%simages/neu.png" % serienRecMainPath

		if CreationFlag == 2:
			setFarbe = parseColor('green').argb()
		elif CreationFlag == 3:
			setFarbe = parseColor('red').argb()
		elif str(Staffel).isdigit() and int(Staffel) == 0:
			setFarbe = parseColor('grey').argb()
		else:
			setFarbe = parseColor('foreground').argb()

		if str(Staffel).isdigit() and int(Staffel) == 1:
			icon = imageNeu

		Staffel = "S%sE01" % str(Staffel).zfill(2)
		WochenTag=["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		xtime = time.strftime(WochenTag[time.localtime(int(UTCTime)).tm_wday]+", %d.%m.%Y", time.localtime(int(UTCTime)))

		if config.plugins.serienRec.showPicons.value:
			picon = imageNone
			if Sender:
				piconPath = self.piconLoader.getPicon(self.serviceRefs.get(Sender))
				if piconPath:
					self.picloader = PicLoader(80 * skinFactor, 40 * skinFactor)
					picon = self.picloader.load(piconPath)
					self.picloader.destroy()

			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 5, 80 * skinFactor, 40 * skinFactor, picon),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340 * skinFactor, 15 * skinFactor, 30 * skinFactor, 30 * skinFactor, loadPNG(icon)),
				(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 110 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, parseColor('yellow').argb(), parseColor('yellow').argb()),
				(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 375 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, parseColor('yellow').argb(), parseColor('yellow').argb())
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 15 * skinFactor, 30 * skinFactor, 30 * skinFactor, loadPNG(icon)),
				(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 3, 200 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 50 * skinFactor, 29 * skinFactor, 200 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, parseColor('yellow').argb(), parseColor('yellow').argb()),
				(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 3, 500 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300 * skinFactor, 29 * skinFactor, 500 * skinFactor, 18 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, parseColor('yellow').argb(), parseColor('yellow').argb())
				]

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def serieInfo(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return
		url = self['menu_list'].getCurrent()[0][5]
		serien_id = getSeriesIDByURL(url)
		if serien_id > 0:
			serien_name = self['menu_list'].getCurrent()[0][0]
			self.session.open(serienRecShowInfo, serien_name, serien_id)

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
				self.readProposal()
				
	def getCover(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][0]
		serien_id = getSeriesIDByURL(self['menu_list'].getCurrent()[0][5])
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)

	def keyRed(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['menu_list'].getCurrent()[0]
			cCursor = dbSerRec.cursor()
			data = (Serie, Staffel, Sender, Datum) 
			cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
			dbSerRec.commit()
			cCursor.close()
			self.readProposal()

	def keyOK(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['menu_list'].getCurrent()[0]
			if CreationFlag:
				(ID, AbStaffel, AlleSender) = self.checkMarker(Serie)
				if ID > 0:
					cCursor = dbSerRec.cursor()
					if str(Staffel).isdigit():
						if AbStaffel > Staffel:
							cCursor.execute("SELECT * FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel=?", (ID, Staffel))
							row = cCursor.fetchone()
							if not row:
								cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, Staffel))
								cCursor.execute("SELECT * FROM StaffelAuswahl WHERE ID=? ORDER DESC BY ErlaubteStaffel", (ID,))
								staffel_Liste = cCursor.fetchall()
								for row in staffel_Liste:
									(ID, ErlaubteStaffel) = row
									if AbStaffel == (ErlaubteStaffel + 1):
										AbStaffel = ErlaubteStaffel
									else:
										break
								cCursor.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=? WHERE ID=?", (AbStaffel, ID))
								cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel>=?", (ID, AbStaffel))
					else:
						cCursor.execute("UPDATE OR IGNORE SerienMarker SET TimerForSpecials=1 WHERE ID=?", (ID,))
					
					if not AlleSender:
						cCursor.execute("SELECT * FROM SenderAuswahl WHERE ID=? AND ErlaubterSender=?", (ID, Sender))
						row = cCursor.fetchone()
						if not row:
							cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
					
					dbSerRec.commit()
					cCursor.close()
				else:
					cCursor = dbSerRec.cursor()
					if config.plugins.serienRec.defaultStaffel.value == "0":
						cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, 0, 1, -1)", (Serie, Url))
						ID = cCursor.lastrowid
					else:
						if str(Staffel).isdigit():
							cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, ?, -1)", (Serie, Url, AbStaffel, AlleSender))
							ID = cCursor.lastrowid
							cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, Staffel))
						else:
							cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel, TimerForSpecials) VALUES (?, ?, ?, ?, -1, 1)", (Serie, Url, AbStaffel, AlleSender))
							ID = cCursor.lastrowid
						cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
					erlaubteSTB = 0xFFFF
					if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
						erlaubteSTB = 0
						erlaubteSTB |= (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
					cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, erlaubteSTB))
					dbSerRec.commit()
					cCursor.close()

				cCursor = dbSerRec.cursor()
				data = (Serie, Staffel, Sender, Datum) 
				cCursor.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET CreationFlag=2 WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
				dbSerRec.commit()
				cCursor.close()
				self.changesMade = True
				global runAutocheckAtExit
				runAutocheckAtExit = True
				if config.plugins.serienRec.openMarkerScreen.value:
					self.session.open(serienRecMarker, Serie)
				
			self.readProposal()
		
	def keyYellow(self):
		if not self.filter:
			self.filter = True
			self['text_yellow'].setText("Zeige alle")
		else:
			self.filter = False
			self['text_yellow'].setText("Zeige nur neue")
		self.readProposal()
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.value = self.filter
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.save()
		configfile.save()
		
	def keyBlue(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Proposal-DB leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Soll die Liste wirklich geleert werden?", MessageBox.TYPE_YESNO, default = False)
			else:
				cCursor = dbSerRec.cursor()
				cCursor.execute("DELETE FROM NeuerStaffelbeginn")
				dbSerRec.commit()
				cCursor.close()
				self.readProposal()

	def callDeleteMsg(self, answer):
		if answer:
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM NeuerStaffelbeginn")
			dbSerRec.commit()
			cCursor.close()
			self.readProposal()
		else:
			return
			
	def checkMarker(self, mSerie):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ID, AlleStaffelnAb, alleSender FROM SerienMarker WHERE LOWER(Serie)=?", (mSerie.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (0, 999999, 0)
		cCursor.close()
		return row

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

class serienRecWishlist(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.ErrorMsg = "unbekannt"

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
			if isDreamboxOS:
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
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
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Episode FROM Merkzettel")
		for row in cCursor:
			(Serie, Staffel, Episode) = row
			zeile = "%s S%sE%s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2))
			self.wishlist.append((zeile, Serie, Staffel, Episode))
		cCursor.close()
		
		self.wishlist_tmp = self.wishlist[:]
		if config.plugins.serienRec.wishListSorted.value:
			self.wishlist_tmp.sort()
		self.chooseMenuList.setList(map(self.buildList, self.wishlist_tmp))
		self.getCover()
		
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
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
			if int(self.aFromEpisode) != 0 or int(self.aToEpisode) != 0:
				AnzahlAufnahmen = int(config.plugins.serienRec.NoOfRecords.value)
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT AnzahlWiederholungen FROM SerienMarker WHERE LOWER(Serie)=?", (self.aSerie.lower(),))
				row = cCursor.fetchone()
				if row:
					(AnzahlWiederholungen,) = row
					if str(AnzahlWiederholungen).isdigit():
						AnzahlAufnahmen = int(AnzahlWiederholungen)
				for i in range(int(self.aFromEpisode), int(self.aToEpisode)+1):
					print "[SerienRecorder] %s Staffel: %s Episode: %s " % (str(self.aSerie), str(self.aStaffel), str(i))
					cCursor.execute("SELECT * FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (self.aSerie.lower(), self.aStaffel.lower(), str(i).zfill(2).lower()))
					row = cCursor.fetchone()
					if not row:
						cCursor.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?)", (self.aSerie, self.aStaffel, str(i).zfill(2), AnzahlAufnahmen))
				dbSerRec.commit()
				cCursor.close()
				self.readWishlist()

	def keyOK(self):
		if self.modus == "menu_list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['menu_list'].hide()
			l = []

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie FROM SerienMarker ORDER BY Serie")
			cMarkerList = cCursor.fetchall()
			for row in cMarkerList:
				l.append(row)
			cCursor.close()
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
			self.delAdded = True;
			
	def keyGreen(self):
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
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
				cCursor = dbSerRec.cursor()
				cCursor.execute("DELETE FROM Merkzettel")
				dbSerRec.commit()
				cCursor.close()
				self.readWishlist()

	def callClearListMsg(self, answer):
		if answer:
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM Merkzettel")
			dbSerRec.commit()
			cCursor.close()
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

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		serien_id = None
		if row:
			(url, ) = row
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
			if isDreamboxOS:
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
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (self.serieName.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		serien_id = None
		if row:
			(url, ) = row
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

class serienRecShowEpisodeInfo(Screen, HelpableScreen):
	def __init__(self, session, serieName, episodeTitle, serieUrl):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serieName = serieName
		self.serieUrl = serieUrl
		self.episodeTitle = episodeTitle
		self.skin = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red"   : (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.pageUp, "zur vorherigen Seite blättern"),
			"right" : (self.pageDown, "zur nächsten Seite blättern"),
			"up"    : (self.pageUp, "zur vorherigen Seite blättern"),
			"down"  : (self.pageDown, "zur nächsten Seite blättern"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"       : (self.youtubeSearch, "Trailer zur ausgewählten Serie auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zur ausgewählten Serie auf Wikipedia suchen"),
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
			if isDreamboxOS:
				self.displayTimer_conn = self.displayTimer.timeout.connect(self.updateMenuKeys)
			else:
				self.displayTimer.callback.append(self.updateMenuKeys)
			self.displayTimer.start(config.plugins.serienRec.DisplayRefreshRate.value * 1000)

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['info'].show()

		self['title'].setText("Episoden Beschreibung: %s" % self.episodeTitle)

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
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		elif DMMBrowserInstalled:
			self.session.open(Browser, True, "file://usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html")
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
				self.getData()

	def getData(self):
		try:
			infoText = SeriesServer().getEpisodeInfo(self.serieUrl)
		except:
			infoText = 'Es ist ein Fehler beim Abrufen der Episoden-Informationen aufgetreten!'
		self['info'].setText(infoText)
		self.getCover()

	def dataError(self, error):
		writeErrorLog("   serienRecShowEpisodeInfo(): %s\n   Serie: %s\n   Episode: %s\n   Url: %s" % (error, self.serieName, self.episodeTitle, self.serieUrl))
		print error

	def pageUp(self):
		self['info'].pageUp()

	def pageDown(self):
		self['info'].pageDown()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def getCover(self):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (self.serieName.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		serien_id = None
		if row:
			(url, ) = row
			serien_id = getSeriesIDByURL(url)
		self.ErrorMsg = "'getCover()'"
		getCover(self, self.serieName, serien_id)

	def keyCancel(self):
		self.close()

class serienRecShowImdbVideos(Screen, HelpableScreen):
	def __init__(self, session, ilink, serien_name, serien_id):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.ilink = ilink
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serien_id = serien_id
		self.ErrorMsg = "unbekannt"

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, "ausgewähltes Video abspielen"),
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
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

		self.onLayoutFinish.append(self.getVideos)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_ok'].setText("Video zeigen")

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
			if isDreamboxOS:
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

		self['title'].setText("Lade imdbVideos...")

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()
		global showAllButtons
		if not showAllButtons:
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_menu'].show()
			
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		self.close()
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return
		self.session.open(serienRecShowInfo, self.serien_name, self.serien_id)

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
				self.getVideos()
				
	def getVideos(self):
		videos = imdbVideo().videolist(self.ilink.replace('combined',''))
		if videos != None:
			count = len(videos)
			self['title'].setText("Es wurde(n) (%s) imdbVideos gefunden." % str(count))
			self.chooseMenuList.setList(map(self.buildList, videos))
		else:
			self['title'].setText("Keine imdbVideos gefunden.")
			
	def buildList(self, entry):
		(serien_id, image) = entry

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 750 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_id)
			]

	def keyOK(self):
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		url = self['menu_list'].getCurrent()[0][0]
		image = self['menu_list'].getCurrent()[0][1]
		print url
		
		stream = imdbVideo().stream_url(url)
		if stream is not None:
			#sref = eServiceReference(0x1001, 0, stream)
			sref = eServiceReference(4097, 0, stream)
			self.session.open(MoviePlayer, sref)

	def getCover(self):
		self.ErrorMsg = "'getCover()'"
		getCover(self, self.serien_name, self.serien_id)

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
			"info" 	: (self.keyCheck, "Suchlauf für Timer starten"),
			"info_lang" 	: (self.keyCheckLong, "Suchlauf für Timer mit TV-Planer starten"),
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
			"5"		: (self.test, "-"),
		}, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)
		
		ReadConfigFile()

		if not initDB():
			self.close()

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
		self.daylist = [[],[],[]]
		self.displayTimer = None
		self.displayMode = 1
		self.serviceRefs = getActiveServiceRefs()
		
		global dayCache
		if len(dayCache):
			optimizePlanerData()
		else:
			readPlanerData()

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
			if isDreamboxOS:
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
		
	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def test(self):
		try:
			if config.plugins.serienRec.imap_server_ssl.value:
				mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value,
										 config.plugins.serienRec.imap_server_port.value)
			else:
				mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value,
									 config.plugins.serienRec.imap_server_port.value)

		except imaplib.IMAP4.abort:
			writeLog("IMAP Check: Verbindung zum Server fehlgeschlagen", True)
			return None

		try:
			mail.login(decode(getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
					   decode(getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))

		except imaplib.IMAP4.error:
			writeLog("IMAP Check: Anmeldung auf Server fehlgeschlagen", True)
			return None

		try:
			import string

			writeLog("Mailboxes:", True)
			result, data = mail.list('""', '*')
			if result == 'OK':
				for item in data[:]:
					x = item.split()
					mailbox = string.join(x[2:])
					writeLog("%s" % mailbox, True)
		except imaplib.IMAP4.error:
			writeLog("IMAP Check: Abrufen der Mailboxen fehlgeschlagen", True)
		mail.logout()
		self.session.open(MessageBox, "IMAP Mailboxes abgerufen - siehe Log", MessageBox.TYPE_INFO, timeout=10)

	def getImdblink2(self, data):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S)
		if ilink:
			print ilink
			serien_name = self['menu_list'].getCurrent()[0][6]
			serien_id = self['menu_list'].getCurrent()[0][14]
			self.session.open(serienRecShowImdbVideos, ilink[0], serien_name, serien_id)

	def reloadSerienplaner(self):
		lt = datetime.datetime.now()
		lt += datetime.timedelta(days=self.page)
		key = time.strftime('%d.%m.%Y', lt.timetuple())
		if key in dayCache: 
			del dayCache[key]
		self.readWebpage(False)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		self.session.openWithCallback(self.readWebpage, serienRecShowSeasonBegins)

	def searchSeries(self):
		if self.modus == "list":
			self.session.openWithCallback(self.wSearch, NTIVirtualKeyBoard, title = "Serien Titel eingeben:")

	def wSearch(self, serien_name):
		if serien_name:
			self.session.openWithCallback(self.handleSeriesSearchEnd, serienRecAddSerie, serien_name)

	def handleSeriesSearchEnd(self, serien_name=None):
		if serien_name:
			self.session.openWithCallback(self.readWebpage, serienRecMarker, serien_name)
		else:
			self.readWebpage(False)

	def serieInfo(self):
		if self.loading:
			return

		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_id = self['menu_list'].getCurrent()[0][14]
		serien_name = self['menu_list'].getCurrent()[0][6]
		
		self.session.open(serienRecShowInfo, serien_name, serien_id)

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

			serien_name = self['menu_list'].getCurrent()[0][6]
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
				
			self.session.open(Browser, True, "file:///usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html")
		else:
			self.session.open(MessageBox, "Um diese Funktion nutzen zu können muss das Plugin '%s' installiert sein." % "Webbrowser", MessageBox.TYPE_INFO, timeout = 10)
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def setHeadline(self):
		# aktuelle internationale Serien
		if int(config.plugins.serienRec.screenplaner.value) == 1:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText("Alle Serien (aktuelle internationale Serien)")
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText("Neue Serien (aktuelle internationale Serien)")
			## E01
			elif int(config.plugins.serienRec.screenmode.value) == 2:
				self['headline'].setText("Alle Serienstarts")
			
		# soaps
		elif int(config.plugins.serienRec.screenplaner.value) == 2:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText("Alle Serien (Soaps)")
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText("Neue Serien ((Soaps)")

		# internationale Serienklassiker
		elif int(config.plugins.serienRec.screenplaner.value) == 3:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText("Alle Serien (internationale Serienklassiker)")
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText("Neue Serien (internationale Serienklassiker)")

		# deutsche Serien
		elif int(config.plugins.serienRec.screenplaner.value) == 5:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText("Alle Serien (deutsche Serien)")
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText("Neue Serien (deutsche Serien)")

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
				self.readWebpage()

	def startScreen(self):
		print "[SerienRecorder] version %s is running..." % config.plugins.serienRec.showversion.value
		
		global refreshTimer
		if not refreshTimer:
			if config.plugins.serienRec.timeUpdate.value:
				serienRecCheckForRecording(self.session, False, False)

		if self.isChannelsListEmpty():
			print "[SerienRecorder] Channellist is empty !"
			self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		else:
			if not showMainScreen:
				self.session.openWithCallback(self.readWebpage, serienRecMarker)
			else:
				self.readWebpage(False)

	def readWebpage(self, answer=True):
		if not showMainScreen:
			self.keyCancel()
			self.close()

		self.loading = True
			
		global dayCache
		if answer:
			dayCache.clear()
			
		self.setHeadline()
		self['title'].instance.setForegroundColor(parseColor("foreground"))

		lt = datetime.datetime.now()
		lt += datetime.timedelta(days=self.page)
		key = time.strftime('%d.%m.%Y', lt.timetuple())
		if key in dayCache:
			try:
				self['title'].setText("Lade Infos vom Speicher...")
				self.processPlanerData(dayCache[key], True)
			except:
				writeLog("Fehler beim Abrufen und Verarbeiten der SerienPlaner-Daten\n", True)
		else:
			self['title'].setText("Lade Infos vom Web...")
			webChannels = getWebSenderAktiv()
			try:
				planerData = SeriesServer().doGetPlanerData(int(config.plugins.serienRec.screenplaner.value), int(self.page), webChannels)
				self.processPlanerData(planerData, False)
			except:
				writeLog("Fehler beim Abrufen und Verarbeiten der SerienPlaner-Daten\n", True)
			
	def processPlanerData(self, data, useCache=False):
		if not data or len(data) == 0:
			self['title'].setText("Fehler beim Abrufen der SerienPlaner-Daten")
			return
		if useCache:
			(headDate, self.daylist) = data
		else:
			self.daylist = [[],[],[]]
			headDate = [data["date"]]

			markers = getAllMarkers()
			timers = getTimer(self.page)

			for event in data["events"]:
				aufnahme = False
				serieAdded = 0
				start_h = event["time"][:+2]
				start_m = event["time"][+3:]
				start_time = TimeHelpers.getUnixTimeWithDayOffset(start_h, start_m, self.page)

				serien_name = doReplaces(event["name"].encode("utf-8"))
				serien_name_lower = serien_name.lower()
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
					(dirname, dirname_serie) = getDirname(serien_name, staffel)
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
				serien_id = event["id"]
				self.daylist[0].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				if int(neu) == 1:
					self.daylist[1].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				if re.search('01', episode, re.S):
					self.daylist[2].append((regional,paytv,neu,prime,transmissionTime,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

			print "[SerienRecorder] Es wurden %s Serie(n) gefunden" % len(self.daylist[int(config.plugins.serienRec.screenmode.value)])
			
			if headDate:
				d = headDate[0].split(',')
				d.reverse()
				key = d[0].strip()
				global dayCache
				dayCache.update({key:(headDate, self.daylist)})
				if config.plugins.serienRec.planerCacheEnabled.value:
					writePlanerData()
				
		self.loading = False

		if len(self.daylist[int(config.plugins.serienRec.screenmode.value)]) != 0:
			if headDate:
				self['title'].setText("Es wurden für - %s - %s Serie(n) gefunden." % (headDate[0], len(self.daylist[int(config.plugins.serienRec.screenmode.value)])))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			else:
				self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[int(config.plugins.serienRec.screenmode.value)]))
				self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.chooseMenuList.setList(map(self.buildList, self.daylist[int(config.plugins.serienRec.screenmode.value)]))
			self.ErrorMsg = "'getCover()'"
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist[int(config.plugins.serienRec.screenmode.value)]))
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			print "[SerienRecorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
			self.chooseMenuList.setList(map(self.buildList, self.daylist[int(config.plugins.serienRec.screenmode.value)]))

	def buildList(self, entry):
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
			seriesColor = parseColor('foreground').argb()
			if aufnahme:
				seriesColor = parseColor('blue').argb()

		titleColor = timeColor = parseColor('yellow').argb()

		if int(neu) == 0:
			imageNeu = imageNone
			
		if bereits_vorhanden:
			imageHDDTimer = imageHDD
		elif aufnahme:
			imageHDDTimer = imageTimer
		else:
			imageHDDTimer = imageNone
		
		if config.plugins.serienRec.showPicons.value:
			picon = imageNone
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

	def keyOK(self):
		if self.modus == "list":
			if self.loading:
				return

			check = self['menu_list'].getCurrent()
			if check is None:
				return

			serien_name = self['menu_list'].getCurrent()[0][6]
			sender = self['menu_list'].getCurrent()[0][7]
			staffel = self['menu_list'].getCurrent()[0][8]
			serien_id = self['menu_list'].getCurrent()[0][14]

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
			row = cCursor.fetchone()
			if not row:
				if config.plugins.serienRec.defaultStaffel.value == "0":
					cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (serien_name, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id))
					ID = cCursor.lastrowid
				else:
					cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 999999, 0, 1, -1, 0, -1, 0)", (serien_name, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id))
					ID = cCursor.lastrowid
					cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?,?)", (ID, staffel))
					cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?,?)", (ID, sender))
				erlaubteSTB = 0xFFFF
				if config.plugins.serienRec.activateNewOnThisSTBOnly.value:
					erlaubteSTB = 0
					erlaubteSTB |= (1 << (int(config.plugins.serienRec.BoxID.value) - 1))
				cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, erlaubteSTB))
				dbSerRec.commit()
				cCursor.close()
				self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
				global runAutocheckAtExit
				runAutocheckAtExit = True
				if config.plugins.serienRec.openMarkerScreen.value:
					self.session.open(serienRecMarker, serien_name)
			else:
				self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))
				cCursor.close()

		elif self.modus == "popup":
			status = self['popup_list'].getCurrent()[0][0]
			planer_id = self['popup_list'].getCurrent()[0][1]
			name = self['popup_list'].getCurrent()[0][2]
			print status, planer_id, name

			self['popup_list'].hide()
			self['popup_bg'].hide()
			self['menu_list'].show()
			self.modus = "list"
			config.plugins.serienRec.screenmode.value = int(status)
			config.plugins.serienRec.screenplaner.value = int(planer_id)
			print "[SerienRecorder] neu: %s - planer: %s" % (config.plugins.serienRec.screenmode.value, config.plugins.serienRec.screenplaner.value)
			config.plugins.serienRec.screenmode.save()
			config.plugins.serienRec.screenplaner.save()
			configfile.save()
			self.chooseMenuList.setList(map(self.buildList, []))
			self.readWebpage(True)

	def getCover(self):
		if self.loading:
			return
		
		check = self['menu_list'].getCurrent()
		if check is None:
			return

		serien_name = self['menu_list'].getCurrent()[0][6]
		serien_id = self['menu_list'].getCurrent()[0][14]
		self.ErrorMsg = "'getCover()'"
		getCover(self, serien_name, serien_id)
		
	def keyRed(self):
		if self.modus == "list":
			#idx = 0
			self.popup_list = []

			# aktuelle internationale Serien
			self.popup_list.append(("0", "1", "Alle Serien (aktuelle internationale Serien)"))
			self.popup_list.append(("1", "1", "Neue Serien (aktuelle internationale Serien)"))

			# soaps
			self.popup_list.append(("0", "2", "Alle Serien (Soaps)"))
			self.popup_list.append(("1", "2", "Neue Serien (Soaps)"))

			# internationale Serienklassiker
			self.popup_list.append(("0", "3", "Alle Serien (internationale Serienklassiker)"))
			self.popup_list.append(("1", "3", "Neue Serien (internationale Serienklassiker)"))

			# deutsche Serien
			self.popup_list.append(("0", "5", "Alle Serien (deutsche Serien)"))
			self.popup_list.append(("1", "5", "Neue Serien (deutsche Serien)"))

			# E01
			self.popup_list.append(("2", "1", "Alle Serienstarts"))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.popup_list))
			
			self['popup_bg'].show()
			self['popup_list'].show()
			self['menu_list'].hide()

			idx = 0
			if int(config.plugins.serienRec.screenplaner.value) == 1:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 0
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 1
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 2
				## E01
				elif int(config.plugins.serienRec.screenmode.value) == 3:
					idx = 12
					#idx = 15
				
			# soaps
			elif int(config.plugins.serienRec.screenplaner.value) == 2:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 3
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 4
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 5
				
			# internationale Serienklassiker
			elif int(config.plugins.serienRec.screenplaner.value) == 3:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 6
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 7
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 8

			# deutsche Serien
			elif int(config.plugins.serienRec.screenplaner.value) == 5:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 9
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 10
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 11

			self['popup_list'].moveToIndex(idx)
			self.modus = "popup"
			self.loading = False

	@staticmethod
	def buildList_popup(entry):
		(mode, planer_id, name) = entry

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 800 * skinFactor, 30 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name)
			]

	@staticmethod
	def isChannelsListEmpty():
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Count(*) from Channels")
		(count,) = cCursor.fetchone()
		print "[SerienRecorder] count channels %s" % count
		if count == 0:
			print "channels: true"
			return True
		else:
			print "channels: false"
			return False

	@staticmethod
	def checkTimer(serie, start_time, webchannel):
		(margin_before, margin_after) = getMargins(serie, webchannel)

		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel>=? AND StartZeitstempel<? AND LOWER(webChannel)=?"
		cCursor.execute(sql, (serie.lower(), (int(start_time) - (int(margin_before) * 60) - 300), (int(start_time) - (int(margin_before) * 60) + 300), webchannel.lower()))
		if cCursor.fetchone():
			cCursor.close()
			return True
		else:
			cCursor.close()
			return False

	def keyGreen(self):
		self.session.openWithCallback(self.readWebpage, MessageBox, ("Die Funktion 'Sender zuordnen' lässt sich jetzt in den globalen Einstellungen über die MENÜ Taste aufrufen."),
		                              MessageBox.TYPE_INFO, timeout=10)
		#self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		
	def keyYellow(self):
		self.session.openWithCallback(self.readWebpage, serienRecMarker)
		
	def keyBlue(self):
		self.session.openWithCallback(self.readWebpage, serienRecTimer)

	def keyCheck(self):
		self.session.openWithCallback(self.readWebpage, serienRecRunAutoCheck, True)

	def keyCheckLong(self):
		self.session.openWithCallback(self.readWebpage, serienRecRunAutoCheck, True, config.plugins.serienRec.tvplaner.value)
		
	def keyLeft(self):
		if self.modus == "list":
			self['menu_list'].pageUp()
			self.getCover()
		else:
			self['popup_list'].pageUp()

	def keyRight(self):
		if self.modus == "list":
			self['menu_list'].pageDown()
			self.getCover()
		else:
			self['popup_list'].pageDown()

	def keyDown(self):
		if self.modus == "list":
			self['menu_list'].down()
			self.getCover()
		else:
			self['popup_list'].down()

	def keyUp(self):
		if self.modus == "list":
			self['menu_list'].up()
			self.getCover()
		else:
			self['popup_list'].up()

	def nextPage(self):
		if self.page < 4:
			self.page += 1
			self.chooseMenuList.setList(map(self.buildList, []))
			self.readWebpage(False)

	def backPage(self):
		if not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self.readWebpage(False)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None
		dbSerRec.close()

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
				if isDreamboxOS:
					singleTimer_conn = singleTimer.timeout.connect(serienRecCheckForRecording(self.session, True, False))
				else:
					singleTimer.callback.append(serienRecCheckForRecording(self.session, True, False))
				singleTimer.start(10000, True)
			
			#self.hide()
			#self.showSplashScreen()
			self.close()
		elif self.modus == "popup":
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self['menu_list'].show()
			self.modus = "list"

	def dataError(self, error, url):
		self['title'].setText("Suche auf 'Wunschliste.de' erfolglos")
		self['title'].instance.setForegroundColor(parseColor("foreground"))
		writeLog("Fehler bei: %s" % self.ErrorMsg, True)
		writeLog("      %s" % error, True)
		writeErrorLog("   serienRecMain(): %s\n   %s\n   Url: %s" % (error, self.ErrorMsg, url))
		print "[SerienRecorder] Fehler bei: %s" % self.ErrorMsg
		print error


def getTimer(dayOffset):
	timer = []
	cCursor = dbSerRec.cursor()
	dayOffsetInSeconds = dayOffset * 86400
	sql = "SELECT LOWER(Serie), StartZeitstempel, LOWER(webChannel) FROM AngelegteTimer WHERE (StartZeitstempel >= STRFTIME('%s', CURRENT_DATE)+?) AND (StartZeitstempel < (STRFTIME('%s', CURRENT_DATE)+?+86399))"
	cCursor.execute(sql, (dayOffsetInSeconds, dayOffsetInSeconds))
	for row in cCursor:
		(seriesName, startTimestamp, webChannel) = row
		timer.append((seriesName, startTimestamp, webChannel))
	cCursor.close()
	return timer


def getAllMarkers():
	markers = {}
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT LOWER(Serie), ErlaubteSTB FROM SerienMarker LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID")
	for row in cCursor:
		(seriesName,allowedSTB) = row
		seriesActivated = True
		if allowedSTB is not None and not (allowedSTB & (1 << (int(config.plugins.serienRec.BoxID.value) - 1))):
			seriesActivated = False
		markers[seriesName] = seriesActivated
	cCursor.close()
	return markers


def getNextWakeup():
	color_print = "\033[93m"
	color_end = "\33[0m"

	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value and config.plugins.serienRec.autochecktype.value == "1":
		print color_print+"[SerienRecorder] Deep-Standby WakeUp: AN" +color_end
		now = time.localtime()
		current_time = int(time.time())
		
		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0], config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			print color_print+"[SerienRecorder] WakeUp-Timer + 1 day."+color_end
			begin += 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin -= 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		print color_print+"[SerienRecorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit +color_end

		return begin
	else:
		print color_print+"[SerienRecorder] Deep-Standby WakeUp: AUS" +color_end

def autostart(reason, **kwargs):
	if reason == 0 and "session" in kwargs:
		session = kwargs["session"]
		color_print = "\033[93m"
		color_end = "\33[0m"

		global startTimer
		global startTimerConnection
		lt = time.localtime()
		uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
		writeLog("\nSerienRecorder Start: %s" % uhrzeit, True)

		def startAutoCheckTimer():
			serienRecCheckForRecording(session, False, False)

		#if initDB():
		if config.plugins.serienRec.autochecktype.value in ("1", "2") and config.plugins.serienRec.timeUpdate.value:
			print color_print+"[SerienRecorder] Auto-Check: AN"+color_end
			startTimer = eTimer()
			if isDreamboxOS:
				startTimerConnection = startTimer.timeout.connect(startAutoCheckTimer)
			else:
				startTimer.callback.append(startAutoCheckTimer)
			startTimer.start(60 * 1000, True)
			#serienRecCheckForRecording(session, False, False)
		else:
			print color_print+"[SerienRecorder] Auto-Check: AUS"+color_end

		#API
		from SerienRecorderResource import addWebInterfaceForDreamMultimedia
		addWebInterfaceForDreamMultimedia(session)


def main(session, **kwargs):
	session.open(serienRecMain)
	#print "open screen %s", config.plugins.serienRec.firstscreen.value
	#exec("session.open("+config.plugins.serienRec.firstscreen.value+")")

def SRSetup(menuid, **kwargs):
	if menuid == "mainmenu":
		return [("SerienRecorder", main, "serien_recorder", None)]
	else:
		return []
		
def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=autostart, wakeupfnc=getNextWakeup),
		#PluginDescriptor(name="SerienRecorder", description="Record your favourite series.", where = [PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc = autostart, wakeupfnc=getNextWakeup,
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.", where = [PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.", where = [PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=main),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.", where = [PluginDescriptor.WHERE_MENU], fnc=SRSetup),
		]
	
