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
from Screens.Screen import Screen
from Plugins.Plugin import PluginDescriptor
from twisted.web.client import getPage
from twisted.web.client import downloadPage

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
from Screens.Standby import TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, eServiceReference, getDesktop, loadJPG, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM, gPixmapPtr, ePicLoad, eTimer, eServiceCenter, eConsoleAppContainer
from Tools.Directories import pathExists, fileExists, SCOPE_SKIN_IMAGE, resolveFilename
import sys, os, base64, re, time, shutil, datetime, codecs, urllib2
from twisted.web import client, error as weberror
from twisted.internet import reactor, defer
from urllib import urlencode
from skin import parseColor, loadSkin

from Screens.ChannelSelection import service_types_tv
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
#from Components.Renderer.RunningText import RunningText
import sqlite3

colorRed    = 0xf23d21
colorGreen  = 0x389416
colorBlue   = 0x0064c7
colorYellow = 0xbab329
colorWhite  = 0xffffff


serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"

try:
	default_before = int(config.recording.margin_before.value)
	default_after = int(config.recording.margin_after.value)
except Exception:
	default_before = 0
	default_after = 0

showAllButtons = False
longButtonText = False
buttonText_na = _("-----")
skinName = "SerienRecorder3.0"
skin = "%sskins/SR_Skin.xml" % serienRecMainPath

def SelectSkin():
	global showAllButtons
	showAllButtons = False
	global longButtonText
	longButtonText = False
	global buttonText_na
	buttonText_na = _("-----")
	
	global skinName
	skinName = "SerienRecorder3.0"
	global skin
	skin = "%sskins/SR_Skin.xml" % serienRecMainPath
	
	if config.plugins.serienRec.SkinType.value == "Skinpart":
		try:
			from skin import lookupScreen
			x, path = lookupScreen("SerienRecorder", 0)
			if x:
				skinName = "SerienRecorder"
				showAllButtons = config.plugins.serienRec.showAllButtons.value
		except:
			pass

	elif config.plugins.serienRec.SkinType.value in ("", "Skin2", "AtileHD"):
		skin = "%sskins/%s/SR_Skin.xml" % (serienRecMainPath, config.plugins.serienRec.SkinType.value)
		skin = skin.replace("//", "/")
		if config.plugins.serienRec.SkinType.value in ("Skin2", ):
			showAllButtons = True
		if config.plugins.serienRec.SkinType.value in ("Skin2", "AtileHD"):
			buttonText_na = ""
	else:
		if fileExists("%sskins/%s/SR_Skin.xml" % (serienRecMainPath, config.plugins.serienRec.SkinType.value)):
			skin = "%sskins/%s/SR_Skin.xml" % (serienRecMainPath, config.plugins.serienRec.SkinType.value)
			showAllButtons = config.plugins.serienRec.showAllButtons.value
			buttonText_na = ""
		
def ReadConfigFile():
	config.plugins.serienRec = ConfigSubsection()
	config.plugins.serienRec.savetopath = ConfigText(default = "/media/hdd/movie/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.databasePath = ConfigText(default = serienRecMainPath, fixed_size=False, visible_width=80)
	
	choices = [("Skinpart", _("Skinpart")), ("", _("SerienRecorder 1")), ("Skin2", _("SerienRecorder 2")), ("AtileHD", _("AtileHD"))]
	t = list(os.walk("%sskins" % serienRecMainPath))
	for x in t[0][1]:
		if x not in ("Skin2", "AtileHD"):
			choices.append((x, x))
	config.plugins.serienRec.SkinType = ConfigSelection(choices = choices, default="") 
	config.plugins.serienRec.showAllButtons = ConfigYesNo(default = False)
	config.plugins.serienRec.DisplayRefreshRate = ConfigInteger(10, (1,60))
	
	#config.plugins.serienRec.fake_entry = NoSave(ConfigNothing())
	config.plugins.serienRec.BoxID = ConfigSelectionNumber(1, 16, 1, default = 1)
	config.plugins.serienRec.seriensubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdir = ConfigYesNo(default = False)
	config.plugins.serienRec.seasonsubdirnumerlength = ConfigInteger(1, (1,4))
	config.plugins.serienRec.seasonsubdirfillchar = ConfigSelection(choices = [("0","'0'"), ("<SPACE>", "<SPACE>")], default="0")
	config.plugins.serienRec.justplay = ConfigYesNo(default = False)
	config.plugins.serienRec.justremind = ConfigYesNo(default = False)
	config.plugins.serienRec.zapbeforerecord = ConfigYesNo(default = False)
	config.plugins.serienRec.AutoBackup = ConfigYesNo(default = False)
	config.plugins.serienRec.BackupPath = ConfigText(default = "/media/hdd/SR_Backup/", fixed_size=False, visible_width=80)
	config.plugins.serienRec.eventid = ConfigYesNo(default = True)
	config.plugins.serienRec.update = ConfigYesNo(default = False)
	config.plugins.serienRec.updateInterval = ConfigInteger(0, (0,24))
	config.plugins.serienRec.timeUpdate = ConfigYesNo(default = False)
	config.plugins.serienRec.deltime = ConfigClock(default = 6*3600+time.timezone)
	config.plugins.serienRec.maxWebRequests = ConfigInteger(1, (1,99))
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
	config.plugins.serienRec.afterAutocheck = ConfigYesNo(default = False)
	config.plugins.serienRec.DSBTimeout = ConfigInteger(20, (0,999))
	config.plugins.serienRec.showNotification = ConfigSelection(choices = [("0", _("keine")), ("1", _("bei Suchlauf-Start")), ("2", _("bei Suchlauf-Ende")), ("3", _("bei Suchlauf-Start und Ende"))], default = "1")
	config.plugins.serienRec.LogFilePath = ConfigText(default = serienRecMainPath, fixed_size=False, visible_width=80)
	config.plugins.serienRec.longLogFileName = ConfigYesNo(default = False)
	config.plugins.serienRec.deleteLogFilesOlderThan = ConfigInteger(14, (0,999))
	config.plugins.serienRec.writeLog = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogChannels = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogAllowedSender = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogAllowedEpisodes = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogAdded = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogDisk = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimeRange = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimeLimit = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogTimerDebug = ConfigYesNo(default = True)
	config.plugins.serienRec.writeLogVersion = ConfigYesNo(default = True)
	config.plugins.serienRec.confirmOnDelete = ConfigYesNo(default = True)
	config.plugins.serienRec.ActionOnNew = ConfigSelection(choices = [("0", _("keine")), ("1", _("nur Benachrichtigung")), ("2", _("nur Marker anlegen")), ("3", _("Benachrichtigung und Marker anlegen"))], default="0")
	config.plugins.serienRec.ActionOnNewManuell = ConfigYesNo(default = True)
	config.plugins.serienRec.deleteOlderThan = ConfigInteger(7, (1,99))
	config.plugins.serienRec.NoOfRecords = ConfigInteger(1, (1,9))
	config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default = True)
	config.plugins.serienRec.showPicons = ConfigYesNo(default = True)
	config.plugins.serienRec.listFontsize = ConfigSelectionNumber(-5, 5, 1, default = 0)
	config.plugins.serienRec.intensiveTimersuche = ConfigYesNo(default = True)
	config.plugins.serienRec.breakTimersuche = ConfigYesNo(default = False)
	config.plugins.serienRec.sucheAufnahme = ConfigYesNo(default = True)
	config.plugins.serienRec.selectNoOfTuners = ConfigYesNo(default = True)
	config.plugins.serienRec.tuner = ConfigInteger(4, (1,4))
	config.plugins.serienRec.logScrollLast = ConfigYesNo(default = False)
	config.plugins.serienRec.logWrapAround = ConfigYesNo(default = False)
	config.plugins.serienRec.TimerName = ConfigSelection(choices = [("0", _("<Serienname> - SnnEmm - <Episodentitel>")), ("1", _("<Serienname>"))], default="0")
	config.plugins.serienRec.refreshViews = ConfigYesNo(default = True)
	config.plugins.serienRec.defaultStaffel = ConfigSelection(choices = [("0","'Alle'"), ("1", "'Manuell'")], default="0")
	config.plugins.serienRec.openMarkerScreen = ConfigYesNo(default = True)
	config.plugins.serienRec.runAutocheckAtExit = ConfigYesNo(default = False)

	config.plugins.serienRec.selectBouquets = ConfigYesNo(default = False)
	#config.plugins.serienRec.MainBouquet = ConfigSelection(choices = [("Favourites (TV)", _("Favourites (TV)")), ("Favourites-SD (TV)", _("Favourites-SD (TV)"))], default="Favourites (TV)")
	#config.plugins.serienRec.AlternativeBouquet = ConfigSelection(choices = [("Favourites (TV)", _("Favourites (TV)")), ("Favourites-SD (TV)", _("Favourites-SD (TV)"))], default="Favourites-SD (TV)")
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

	config.plugins.serienRec.firstscreen = ConfigSelection(choices = [("0","SerienPlaner"), ("1", "SerienMarker")], default="0")
	
	# interne
	config.plugins.serienRec.version = NoSave(ConfigText(default="030"))
	config.plugins.serienRec.showversion = NoSave(ConfigText(default="3.0.8"))
	config.plugins.serienRec.screenmode = ConfigInteger(0, (0,2))
	config.plugins.serienRec.screeplaner = ConfigInteger(1, (1,3))
	config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))
	config.plugins.serienRec.serienRecShowSeasonBegins_filter = ConfigYesNo(default = False)
	config.plugins.serienRec.dbversion = NoSave(ConfigText(default="3.0"))
	
	SelectSkin()
ReadConfigFile()

if config.plugins.serienRec.firstscreen.value == "0":
	showMainScreen = True
else:
	showMainScreen = False

#logFile = "%slog" % serienRecMainPath
logFile = "%slog" % (config.plugins.serienRec.LogFilePath.value)
serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

#dbTmp = sqlite3.connect("%sSR_Tmp.db" % config.plugins.serienRec.databasePath.value)
dbTmp = sqlite3.connect(":memory:")
dbTmp.text_factory = lambda x: str(x.decode("utf-8"))
dbSerRec = sqlite3.connect(serienRecDataBase)
dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))

autoCheckFinished = False
refreshTimer = None
refreshTimerConnection = None
EPGTimeSpan = 10
coverToShow = None
runAutocheckAtExit = False

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


# init Opera Webbrowser
if fileExists("/usr/lib/enigma2/python/Plugins/Extensions/HbbTV/browser.pyo"):
	from Plugins.Extensions.HbbTV.browser import Browser
	BrowserInstalled = True
else:
	BrowserInstalled = False

	

# the new API for the Dreambox DM7080HD changes the behavior
# of eTimer append - here are the changes

try:
	from enigma import eMediaDatabase
except ImportError as ie:
	isDreamboxOS = False
else:
	isDreamboxOS = True

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
def writeTestLog(text):
	if not fileExists("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/TestLogs"):
		open("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/TestLogs", 'w').close()

	writeLogFile = open("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/TestLogs", "a")
	writeLogFile.write('%s\n' % (text))
	writeLogFile.close()


def iso8859_Decode(txt):
	txt = unicode(txt, 'ISO-8859-1')
	txt = txt.encode('utf-8')
	txt = txt.replace('...','').replace('..','').replace(':','')

	# &apos;, &quot;, &amp;, &lt;, and &gt;
	txt = txt.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	return txt

def convertWunschlisteTimetoUnixtime(rawTime):
	year = rawTime[:+4]
	month = rawTime[+4]+rawTime[+5]
	day = rawTime[+6]+rawTime[+7]
	std = rawTime[+9]+rawTime[+10]
	min = rawTime[+11]+rawTime[+12]
	utime = datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")
	return utime

def getNextDayUnixtime(min, hour, day, month):
	now = datetime.datetime.now()
	if int(month) < now.month:
		now.year += 1
	date = datetime.datetime(int(now.year),int(month),int(day),int(hour),int(min))
	date += datetime.timedelta(days=1)
	return date.strftime("%s")

def getUnixTimeAll(min, hour, day, month):
	now = datetime.datetime.now()
	if int(month) < now.month:
		now.year += 1
	return datetime.datetime(now.year, int(month), int(day), int(hour), int(min)).strftime("%s")
	
def getUnixTimeWithDayOffset(std, min, AddDays):
	now = datetime.datetime.now()
	date = datetime.datetime(now.year, now.month, now.day, int(std), int(min))
	date += datetime.timedelta(days=AddDays)
	return date.strftime("%s")

def getRealUnixTime(min, std, day, month, year):
	return datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")

def getServiceList(ref):
	root = eServiceReference(str(ref))
	serviceHandler = eServiceCenter.getInstance()
	return serviceHandler.list(root).getContent("SN", True)

def getTVBouquets():
	return getServiceList(service_types_tv + ' FROM BOUQUET "bouquets.tv" ORDER BY bouquet')

def buildSTBchannellist(BouquetName = None):
	serien_chlist = None
	serien_chlist = []
	print "[SerienRecorder] read STV Channellist.."
	tvbouquets = getTVBouquets()
	print "[SerienRecorder] found %s bouquet: %s" % (len(tvbouquets), tvbouquets)

	if not BouquetName:
		for bouquet in tvbouquets:
			bouquetlist = []
			bouquetlist = getServiceList(bouquet[0])
			for (serviceref, servicename) in bouquetlist:
				serien_chlist.append((servicename, serviceref))
	else:
		for bouquet in tvbouquets:
			if bouquet[1] == BouquetName:
				bouquetlist = []
				bouquetlist = getServiceList(bouquet[0])
				for (serviceref, servicename) in bouquetlist:
					serien_chlist.append((servicename, serviceref))
				break
	return serien_chlist

def getChannelByRef(stb_chlist,serviceref):
	for (channelname,channelref) in stb_chlist:
		if channelref == serviceref:
			return channelname

def getEPGevent(query, channelref, title, starttime):
	if not query or len(query) != 2:
		return

	epgmatches = []
	epgcache = eEPGCache.getInstance()
	allevents = epgcache.lookupEvent(query) or []

	for serviceref, eit, name, begin, duration, shortdesc, extdesc in allevents:
		_name = name.strip().replace(".","").replace(":","").replace("-","").replace("  "," ").lower()
		_title = title.strip().replace(".","").replace(":","").replace("-","").replace("  "," ").lower()
		if (channelref == serviceref) and (_name.count(_title) or _title.count(_name)):
			if int(int(begin)-(int(EPGTimeSpan)*60)) <= int(starttime) <= int(int(begin)+(int(EPGTimeSpan)*60)):
				epgmatches.append((serviceref, eit, name, begin, duration, shortdesc, extdesc))
	return epgmatches

def getStartEndTimeFromEPG(start_unixtime_eit, end_unixtime_eit, margin_before, margin_after, serien_name, STBRef):
	eit = 0
	if config.plugins.serienRec.eventid.value:
		# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
		event_matches = getEPGevent(['RITBDSE', (STBRef, 0, int(start_unixtime_eit) + (int(margin_before) * 60), -1)], STBRef, serien_name, int(start_unixtime_eit) + (int(margin_before) * 60))
		if event_matches and len(event_matches) > 0:
			for event_entry in event_matches:
				print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
				eit = int(event_entry[1])
				start_unixtime_eit = int(event_entry[3]) - (int(margin_before) * 60)
				end_unixtime_eit = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
				break

	return eit, end_unixtime_eit, start_unixtime_eit

def getUrl(url):
	req = urllib2.Request(url)
	res = urllib2.urlopen(req)
	finalurl = res.geturl()
	return finalurl

def getCover(self, serien_name, id):
	self['cover'].hide()

	serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name
	global coverToShow
	coverToShow = serien_nameCover
	if not fileExists("/tmp/serienrecorder/"):
		shutil.os.mkdir("/tmp/serienrecorder/")
	if fileExists(serien_nameCover):
		showCover(serien_nameCover, self, serien_nameCover)
	elif id:
		url = "http://www.wunschliste.de%s/links" % id
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(getImdblink, self, serien_nameCover).addErrback(getCoverDataError, self)

def getCoverDataError(error, self):
	#self['title'].setText(_("Cover-Suche auf 'Wunschliste.de' erfolglos"))
	#self['title'].instance.setForegroundColor(parseColor("white"))
	writeLog(_("[Serien Recorder] Fehler bei: %s") % self.ErrorMsg, True)
	print "[Serien Recorder] Fehler bei: %s" % self.ErrorMsg
	print error

def getImdblink(data, self, serien_nameCover):
	ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S)
	if ilink:
		getPage(ilink[0], headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(loadImdbCover, self, serien_nameCover).addErrback(getCoverDataError, self)
	else:
		print "[Serien Recorder] es wurde kein imdb-link für ein cover gefunden."
		
def loadImdbCover(data, self, serien_nameCover):
	imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
	if imageLink_raw:
		print imageLink_raw
		extra_imdb_convert = "@._V1_SX320.jpg"
		aufgeteilt = imageLink_raw[0].split('._V1._')
		imdb_url = "http://ia.media-imdb.com/%s._V1._SX420_SY420_.jpg" % aufgeteilt[0]
		print imdb_url
		downloadPage(imdb_url, serien_nameCover).addCallback(showCover, self, serien_nameCover, False).addErrback(getCoverDataError, self)
	
def showCover(data, self, serien_nameCover, force_show=True):
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
			if ptr != None:
				self['cover'].instance.setPixmap(ptr)
				self['cover'].show()
	else:
		print("Coverfile not found: %s" % serien_nameCover)

def setSkinProperties(self, isLayoutFinshed=True):
	global longButtonText
	if isLayoutFinshed:
		try:
			x = self['text_3'].instance.size()
			if x.width() > 250:
				longButtonText = True
			else:
				longButtonText = False
		except: 
			longButtonText = False
	
	if longButtonText:
		self.num_bt_text = ([_("Zeige Log"), buttonText_na, _("Abbrechen")],
							[_("Timer-Übersicht"), _("Konflikt-Liste"), _("YouTube (lang: Wikipedia)")],
							[buttonText_na, _("Merkzettel"), ""],
							[_("Neue Serienstarts"), buttonText_na, _("Hilfe")],
							[_("Serien Beschreibung"), buttonText_na, _("globale Einstellungen")])
	else:
		self.num_bt_text = ([_("Zeige Log"), buttonText_na, _("Abbrechen")],
							[_("Timer-Übersicht"), _("Konflikt-Liste"), _("YouTube/Wikipedia")],
							[buttonText_na, _("Merkzettel"), ""],
							[_("Neue Serienstarts"), buttonText_na, _("Hilfe")],
							[_("Serien Beschreibung"), buttonText_na, _("globale Einstellungen")])

	if showAllButtons:
		Skin1_Settings(self)
							
def InitSkin(self):
	global showAllButtons
	global longButtonText
	global buttonText_na
	global skin
	global skinName
	
	self.skinName = skinName
	if skin:
		SRSkin = open(skin)
		self.skin = SRSkin.read()
		SRSkin.close()

	self['bt_red'] = Pixmap()
	self['bt_green'] = Pixmap()
	self['bt_yellow'] = Pixmap()
	self['bt_blue'] = Pixmap()

	self['bt_ok'] = Pixmap()
	self['bt_exit'] = Pixmap()
	self['bt_text'] = Pixmap()
	self['bt_epg'] = Pixmap()
	self['bt_info'] = Pixmap()
	self['bt_menu'] = Pixmap()
	self['bt_0'] = Pixmap()
	self['bt_1'] = Pixmap()
	self['bt_2'] = Pixmap()
	self['bt_3'] = Pixmap()
	self['bt_4'] = Pixmap()
	self['bt_5'] = Pixmap()
	self['bt_6'] = Pixmap()
	self['bt_7'] = Pixmap()
	self['bt_8'] = Pixmap()
	self['bt_9'] = Pixmap()

	self['text_red'] = Label("")
	self['text_green'] = Label("")
	self['text_yellow'] = Label("")
	self['text_blue'] = Label(_(""))

	self['text_ok'] = Label("")
	self['text_exit'] = Label("")
	self['text_text'] = Label("")
	self['text_epg'] = Label("")
	self['text_info'] = Label("")
	self['text_menu'] = Label("")

	self['text_0'] = Label("")
	self['text_1'] = Label("")
	self['text_2'] = Label("")
	self['text_3'] = Label("")
	self['text_4'] = Label("")
	self['text_5'] = Label("")
	self['text_6'] = Label("")
	self['text_7'] = Label("")
	self['text_8'] = Label("")
	self['text_9'] = Label("")

	self['Web_Channel'] = Label("")
	self['Web_Channel'].hide()
	self['STB_Channel'] = Label("")
	self['STB_Channel'].hide()
	self['alt_STB_Channel'] = Label("")
	self['alt_STB_Channel'].hide()
	self['separator'] = Label("")
	self['separator'].hide()
	self['path'] = Label("")
	self['path'].hide()
	self['config'] = MenuList([])
	self['config'].hide()
	self['list'] = MenuList([])
	self['list'].hide()
	self['popup_list'] = MenuList([])
	self['popup_list'].hide()
	self['popup_list2'] = MenuList([])
	self['popup_list2'].hide()
	self['popup_bg'] = Pixmap()
	self['popup_bg'].hide()
	self['cover'] = Pixmap()
	self['cover'].hide()
	self['config_information'] = Label("")
	self['config_information'].hide()
	self['config_information_text'] = Label("")
	self['config_information_text'].hide()
	self['info'] = ScrollLabel()
	self['info'].hide()

	self['title'] = Label("")
	self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
	self['headline'] = Label("")
	
	setSkinProperties(self, False)
							
	if not showAllButtons:
		self['bt_red'].hide()
		self['bt_green'].hide()
		self['bt_yellow'].hide()
		self['bt_blue'].hide()

		self['bt_ok'].hide()
		self['bt_exit'].hide()
		self['bt_text'].hide()
		self['bt_epg'].hide()
		self['bt_info'].hide()
		self['bt_menu'].hide()
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

		self['text_red'].hide()
		self['text_green'].hide()
		self['text_yellow'].hide()
		self['text_blue'].hide()

		self['text_ok'].hide()
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

def Skin1_Settings(self):			
	self['text_0'].setText(self.num_bt_text[0][0])
	self['text_1'].setText(self.num_bt_text[1][0])
	self['text_2'].setText(self.num_bt_text[2][0])
	self['text_3'].setText(self.num_bt_text[3][0])
	self['text_4'].setText(self.num_bt_text[4][0])
	self['text_5'].setText(self.num_bt_text[0][1])
	self['text_6'].setText(self.num_bt_text[1][1])
	self['text_7'].setText(self.num_bt_text[2][1])
	self['text_8'].setText(self.num_bt_text[3][1])
	self['text_9'].setText(self.num_bt_text[4][1])
	self['text_exit'].setText(self.num_bt_text[0][2])
	self['text_text'].setText(self.num_bt_text[1][2])
	self['text_epg'].setText(self.num_bt_text[2][2])
	self['text_info'].setText(self.num_bt_text[3][2])
	self['text_menu'].setText(self.num_bt_text[4][2])
		
def updateMenuKeys(self):	
	if self.displayMode == 0:
		self.displayMode = 1
		self['bt_0'].hide()
		self['bt_1'].hide()
		self['bt_2'].hide()
		self['bt_3'].hide()
		self['bt_4'].hide()
	elif self.displayMode == 1:
		self.displayMode = 2
		self['bt_5'].hide()
		self['bt_6'].hide()
		self['bt_7'].hide()
		self['bt_8'].hide()
		self['bt_9'].hide()
	else:
		self.displayMode = 0
		self['bt_0'].show()
		self['bt_1'].show()
		self['bt_2'].show()
		self['bt_3'].show()
		self['bt_4'].show()
		self['bt_5'].show()
		self['bt_6'].show()
		self['bt_7'].show()
		self['bt_8'].show()
		self['bt_9'].show()
	self['text_0'].setText(self.num_bt_text[0][self.displayMode])
	self['text_1'].setText(self.num_bt_text[1][self.displayMode])
	self['text_2'].setText(self.num_bt_text[2][self.displayMode])
	self['text_3'].setText(self.num_bt_text[3][self.displayMode])
	self['text_4'].setText(self.num_bt_text[4][self.displayMode])

def writeLog(text, forceWrite=False):
	if config.plugins.serienRec.writeLog.value or forceWrite:
		if not fileExists(logFile):
			open(logFile, 'w').close()

		writeLogFile = open(logFile, "a")
		writeLogFile.write('%s\n' % (text))
		writeLogFile.close()

def writeLogFilter(type, text, forceWrite=False):
	if config.plugins.serienRec.writeLog.value or forceWrite:
		if not fileExists(logFile):
			open(logFile, 'w').close()

		writeLogFile = open(logFile, "a")
		if (type == "channels" and config.plugins.serienRec.writeLogChannels.value) or \
		   (type == "allowedSender" and config.plugins.serienRec.writeLogAllowedSender.value) or \
		   (type == "allowedEpisodes" and config.plugins.serienRec.writeLogAllowedEpisodes.value) or \
		   (type == "added" and config.plugins.serienRec.writeLogAdded.value) or \
		   (type == "disk" and config.plugins.serienRec.writeLogDisk.value) or \
		   (type == "timeRange" and config.plugins.serienRec.writeLogTimeRange.value) or \
		   (type == "timeLimit" and config.plugins.serienRec.writeLogTimeLimit.value) or \
		   (type == "timerDebug" and config.plugins.serienRec.writeLogTimerDebug.value):
			# write log
			writeLogFile.write('%s\n' % (text))
		
		writeLogFile.close()

def checkTuner(check_start, check_end):
	if not config.plugins.serienRec.selectNoOfTuners.value:
		return True
		
	timers = serienRecAddTimer.getTimersTime()
	cTuner = 1
	for name, begin, end in timers:
		print name, begin, end
		if not ((int(check_end) < int(begin)) or (int(check_start) > int(end))):
			print "between"
			cTuner += 1
			break
			
	if cTuner <= int(config.plugins.serienRec.tuner.value):
		return True
	else:
		return False

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
		logFile = "%slog" % serienRecMainPath			
		Notifications.AddPopup(_("[Serien Recorder]\nDatei 'log' kann nicht im angegebenen Pfad (%s) erzeugt werden.\n\nEs wird '%s' verwendet!") % (config.plugins.serienRec.LogFilePath.value, logFile), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] checkFileAccess")
			
def checkTimerAdded(sender, serie, staffel, episode, start_unixtime):
	#"Castle" "S03E20 - Die Pizza-Connection" "1392997800" "1:0:19:EF76:3F9:1:C00000:0:0:0:" "kabel eins"
	found = False
	cCursor = dbSerRec.cursor()
	sql = "SELECT * FROM AngelegteTimer WHERE LOWER(webChannel)=? AND LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
	cCursor.execute(sql, (sender.lower(), serie.lower(), str(staffel).lower(), episode.lower(), int(start_unixtime)-(int(EPGTimeSpan)*60), int(start_unixtime)+(int(EPGTimeSpan)*60)))
	row = cCursor.fetchone()
	if row:
		found = True
	cCursor.close()
	return found

def checkAlreadyAdded(serie, staffel, episode):
	Anzahl = 0
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serie.lower(), str(staffel).lower(), episode.lower()))
	(Anzahl,) = cCursor.fetchone()	
	cCursor.close()
	return Anzahl

def getDirname(serien_name, staffel):
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
			dirname = "%s%s/" % (dirname, serien_name)
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
				dirname = "%s%s/" % (dirname, serien_name)
				dirname_serie = dirname
				if config.plugins.serienRec.seasonsubdir.value:
					dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
		
	cCursor.close()	
	return (dirname, dirname_serie)

def countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, stopAfterFirstHit = False):
	count = 0
	if fileExists(dirname):
		searchString = '%s.*?%s.*?\.ts\Z' % (re.escape(serien_name), re.escape(seasonEpisodeString))
		dirs = os.listdir(dirname)
		for dir in dirs:
			if re.search(searchString, dir):
				count += 1
				if stopAfterFirstHit:
					break

	return count

def CreateDirectory(serien_name, staffel):
	(dirname, dirname_serie) = getDirname(serien_name, staffel)
	if not fileExists(dirname):
		print "[Serien Recorder] erstelle Subdir %s" % dirname
		writeLog(_("[Serien Recorder] erstelle Subdir: ' %s '") % dirname)
		os.makedirs(dirname)
	if fileExists(dirname):
		if fileExists("/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("%s%s.jpg" % (dirname_serie, serien_name)):
			shutil.copy("/tmp/serienrecorder/%s.png" % serien_name, "%s%s.jpg" % (dirname_serie, serien_name))
		if fileExists("/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("%s%s.jpg" % (dirname, serien_name)):
			shutil.copy("/tmp/serienrecorder/%s.png" % serien_name, "%s%s.jpg" % (dirname, serien_name))

def allowedTimeRange(fromTime, toTime, start_time, end_time):
	if fromTime < toTime:
		if start_time < end_time:
			if (start_time >= fromTime) and (end_time <= toTime):
				return True
	else:
		if start_time >= fromTime:
			if end_time >= fromTime:
				if start_time < end_time:
					return True
			elif end_time <= toTime:
				return True
		elif start_time < end_time:
			if (start_time <= toTime) and (end_time <= toTime):
				return True
	return False

def getMargins(serien_name, webSender):
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT Vorlaufzeit, Nachlaufzeit FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
	data = cCursor.fetchone()
	if not data:
		data = (None, None)
	(Vorlaufzeit1, Nachlaufzeit1) = data
	if not str(Vorlaufzeit1).isdigit():
		Vorlaufzeit1 = None
	if not str(Nachlaufzeit1).isdigit():
		Nachlaufzeit1 = None
		
	cCursor.execute("SELECT Vorlaufzeit, Nachlaufzeit FROM Channels WHERE LOWER(WebChannel)=?", (webSender.lower(), ))
	data = cCursor.fetchone()
	if not data:
		data = (None, None)
	(Vorlaufzeit2, Nachlaufzeit2) = data
	if not str(Vorlaufzeit2).isdigit():
		Vorlaufzeit2 = None
	if not str(Nachlaufzeit2).isdigit():
		Nachlaufzeit2 = None

	margin_before = max(Vorlaufzeit1, Vorlaufzeit2)
	margin_after = max(Nachlaufzeit1, Nachlaufzeit2)
	
	if not str(margin_before).isdigit():
		margin_before = config.plugins.serienRec.margin_before.value
	if not str(margin_after).isdigit():
		margin_after = config.plugins.serienRec.margin_after.value
		
	cCursor.close()
	return (margin_before, margin_after)	

def getVPS(webSender):
	result = 0
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT vps FROM Channels WHERE LOWER(WebChannel)=?", (webSender.lower(), ))
	raw = cCursor.fetchone()
	if raw:
		(result,) = raw
	cCursor.close()
	return (bool(result & 0x1), bool(result & 0x2))

def getSpecialsAllowed(serien_name):
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
	
def getMarker():
	return_list = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT ID, Serie, Url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode FROM SerienMarker ORDER BY Serie")
	cMarkerList = cCursor.fetchall()
	for row in cMarkerList:
		(ID, serie, url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode) = row
		
		SerieEnabled = True
		cTmp = dbSerRec.cursor()
		cTmp.execute("SELECT ErlaubteSTB FROM STBAuswahl WHERE ID=?", (ID,))
		row2 = cTmp.fetchone()
		if row2:
			(ErlaubteSTB,) = row2
			if not (ErlaubteSTB & (1 << (int(config.plugins.serienRec.BoxID.value) - 1))):
				SerieEnabled = False
		else:
			cTmp.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
			dbSerRec.commit()
		cTmp.close()
		
		if SerieEnabled:
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
					
			return_list.append((serie, url, staffeln, sender, AbEpisode, AnzahlAufnahmen))
	cCursor.close()
	return return_list

def getWebSender():
	fSender = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels")
	for row in cCursor:
		(webChannel, stbChannel, stbRef, status) = row
		fSender.append((webChannel))
	cCursor.close()
	return fSender

def getWebSenderAktiv():
	fSender = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
	for row in cCursor:
		(webChannel, stbChannel, stbRef) = row
		fSender.append((webChannel))
	cCursor.close()
	return fSender

def initDB():
	global dbSerRec
	
	if not os.path.exists(serienRecDataBase):
		try:
			dbSerRec = sqlite3.connect(serienRecDataBase)
			dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
		except:
			writeLog(_("[Serien Recorder] Fehler beim Initialisieren der Datenbank"))
			Notifications.AddPopup(_("[Serien Recorder]\nFehler:\nDatenbank kann nicht initialisiert werden.\nSerienRecorder wurde beendet!"), MessageBox.TYPE_INFO, timeout=-1)
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
																	TimerForSpecials INTEGER DEFAULT 0)''')

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
		cCursor.close()

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
															 TimerForSpecials INTEGER DEFAULT 0)''')
																
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
		(ID,Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials) = each
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
		
		sql = "INSERT INTO SerienMarker (Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
		cNew.execute(sql, (Serie,Url,AufnahmeVerzeichnis,AlleStaffelnAb,alleSender,Vorlaufzeit,Nachlaufzeit,AufnahmezeitVon,AufnahmezeitBis,AnzahlWiederholungen,preferredChannel,useAlternativeChannel,AbEpisode,Staffelverzeichnis,TimerForSpecials))
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
			WebChannelNew = unicode(WebChannel, 'ISO-8859-1')
			WebChannelNew = WebChannelNew.encode('utf-8')
			cTmp = dbSerRec.cursor()
			cTmp.execute ("DELETE FROM Channels WHERE WebChannel=?", (WebChannel,))
			sql = "INSERT OR IGNORE INTO Channels (WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) VALUES (?,?,?,?,?,?,?,?,?)"
			cTmp.execute(sql, (WebChannelNew,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps))
			cTmp.close()

		try:
			STBChannelNew = STBChannel.decode('utf-8')
		except:
			STBChannelNew = unicode(STBChannel, 'ISO-8859-1')
			STBChannelNew = STBChannelNew.encode('utf-8')
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
			SerieNew = unicode(Serie, 'ISO-8859-1')
			SerieNew = SerieNew.encode('utf-8')
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			TitelNew = Titel.decode('utf-8')
		except:
			TitelNew = unicode(Titel, 'ISO-8859-1')
			TitelNew = TitelNew.encode('utf-8')
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Titel=? WHERE Titel=?", (TitelNew,Titel))
			cTmp.close()
			
		try:
			webChannelNew = webChannel.decode('utf-8')
		except:
			webChannelNew = unicode(webChannel, 'ISO-8859-1')
			webChannelNew = webChannelNew.encode('utf-8')
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
			SerieNew = unicode(Serie, 'ISO-8859-1')
			SerieNew = SerieNew.encode('utf-8')
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
			ErlaubterSenderNew = unicode(ErlaubterSender, 'ISO-8859-1')
			ErlaubterSenderNew = ErlaubterSenderNew.encode('utf-8')
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
			SerieNew = unicode(Serie, 'ISO-8859-1')
			SerieNew = SerieNew.encode("utf-8")
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			SenderNew = Sender.decode('utf-8')
		except:
			SenderNew = unicode(Sender, 'ISO-8859-1')
			SenderNew = SenderNew.encode('utf-8')
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
				WebChannelNew = unicode(WebChannel, 'ISO-8859-1')
				WebChannelNew = WebChannelNew.encode('utf-8')
				cTmp = dbSerRec.cursor()
				cTmp.execute ("DELETE FROM Channels WHERE WebChannel=?", (WebChannel,))
				sql = "INSERT OR IGNORE INTO Channels (WebChannel,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps) VALUES (?,?,?,?,?,?,?,?,?)"
				cTmp.execute(sql, (WebChannelNew,STBChannel,ServiceRef,alternativSTBChannel,alternativServiceRef,Erlaubt,Vorlaufzeit,Nachlaufzeit,vps))
				cTmp.close()

			try:
				STBChannelNew = STBChannel.decode('utf-8')
			except:
				STBChannelNew = unicode(STBChannel, 'ISO-8859-1')
				STBChannelNew = STBChannelNew.encode('utf-8')
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
				SerieNew = unicode(Serie, 'ISO-8859-1')
				SerieNew = SerieNew.encode('utf-8')
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
				cTmp.close()
				
			try:
				TitelNew = Titel.decode('utf-8')
			except:
				TitelNew = unicode(Titel, 'ISO-8859-1')
				TitelNew = TitelNew.encode('utf-8')
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
				SerieNew = unicode(Serie, 'ISO-8859-1')
				SerieNew = SerieNew.encode('utf-8')
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Serie=? WHERE Serie=?", (SerieNew,Serie))
				cTmp.close()
				
			try:
				TitelNew = Titel.decode('utf-8')
			except:
				TitelNew = unicode(Titel, 'ISO-8859-1')
				TitelNew = TitelNew.encode('utf-8')
				cTmp = dbSerRec.cursor()
				cTmp.execute("UPDATE OR IGNORE AngelegteTimer SET Titel=? WHERE Titel=?", (TitelNew,Titel))
				cTmp.close()
				
			try:
				webChannelNew = webChannel.decode('utf-8')
			except:
				webChannelNew = unicode(webChannel, 'ISO-8859-1')
				webChannelNew = webChannelNew.encode('utf-8')
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
				SerieNew = unicode(Serie, 'ISO-8859-1')
				SerieNew = SerieNew.encode('utf-8')
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
				ErlaubterSenderNew = unicode(ErlaubterSender, 'ISO-8859-1')
				ErlaubterSenderNew = ErlaubterSenderNew.encode('utf-8')
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
			SerieNew = unicode(Serie, 'ISO-8859-1')
			SerieNew = SerieNew.encode("utf-8")
			cTmp = dbSerRec.cursor()
			cTmp.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET Serie=? WHERE Serie=?", (SerieNew,Serie))
			cTmp.close()
			
		try:
			SenderNew = Sender.decode('utf-8')
		except:
			SenderNew = unicode(Sender, 'ISO-8859-1')
			SenderNew = SenderNew.encode('utf-8')
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

def getImageVersionString():
	from Tools.Directories import resolveFilename, SCOPE_SYSETC
	 
	creator = _("n/a")
	version = _("n/a")
	isDreambox = False
 
	try:
		if fileExists(resolveFilename(SCOPE_SYSETC, 'enigma2/Dream')):
			# it's a Dreambox
			isDreambox = True
 
		file = open(resolveFilename(SCOPE_SYSETC, 'image-version'), 'r')
		lines = file.readlines()
		for x in lines:
			splitted = x.split('=')
			if splitted[0] == "creator":
				creator = splitted[1].split('<')
				creator = creator[0].strip(' ')
			if splitted[0] == "version":
				if isDreambox:
 					if splitted[0] == "version":
						#     YYYY MM DD hh mm
						#0120 2005 11 29 01 16
						#0123 4567 89 01 23 45
						version = splitted[1]
						image_type = version[0] # 0 = release, 1 = experimental
						major = version[1]
						minor = version[2]
						revision = version[3]
						year = version[4:8]
						month = version[8:10]
						day = version[10:12]
						date = '-'.join((year, month, day))
						if image_type == '0':
							image_type = _("Release")
							version = '.'.join((major, minor, revision))
							version = ' '.join((image_type, version, date))
						else:
							image_type = _("Experimental")
							version = ' '.join((image_type, date))
				else:
					version = splitted[1]
 		file.close()
 	except:
 		return _("nicht verfügbar")

 	if creator.lower() == "vti":
 		from enigma import getVTiVersionString
 		version = getVTiVersionString()
	if isDreambox:
		from enigma import getEnigmaVersionString
		creator = getEnigmaVersionString()

	return ' '.join((creator, version))

	
def getSTBType():
	try:
		from Tools.HardwareInfoVu import HardwareInfoVu
		STBType = HardwareInfoVu().get_device_name()
	except:
		try:
			from Tools.HardwareInfo import HardwareInfo
			STBType = HardwareInfo().get_device_name()
		except:
			STBType = "unknown"
	return STBType
		

class PicLoader:
	def __init__(self, width, height, sc=None):
		self.picload = ePicLoad()
		if(not sc):
			sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((width, height, sc[0], sc[1], False, 1, "#ff000000"))

	def load(self, filename):
		if isDreamboxOS:
			self.picload.startDecode(filename, False)
		else:
			self.picload.startDecode(filename, 0, 0, False)
		data = self.picload.getData()
		return data

	def destroy(self):
		del self.picload
		
class imdbVideo():
	def __init__(self):
		print "imdbvideos.."

	def videolist(self, url):
		url = url + "videogallery"
		print url
		headers = { 'User-Agent' : 'Mozilla/5.0' }
		req = urllib2.Request(url, None, headers)
		data = urllib2.urlopen(req).read()
		lst = []
		videos = re.findall('viconst="(.*?)".*?src="(.*?)" class="video" />', data, re.S)
		if videos:
			for id,image in videos:
				url = "http://www.imdb.com/video/screenplay/%s/imdb/single" % id
				lst.append((url, image))

		if len(lst) != 0:
			return lst
		else:
			return None

	def stream_url(self, url):
		headers = { 'User-Agent' : 'Mozilla/5.0' }
		req = urllib2.Request(url, None, headers)
		data = urllib2.urlopen(req).read()
		stream_url = re.findall('"start":0,"url":"(.*?)"', data, re.S)
		if stream_url:
			return stream_url[0]
		else:
			return None

	def dataError(self, error):
		return None

	
#---------------------------------- Timer Functions ------------------------------------------
		
class serienRecAddTimer():

	@staticmethod
	def getTimersTime():

		recordHandler = NavigationInstance.instance.RecordTimer

		entry = None
		timers = []

		for timer in recordHandler.timer_list:
			timers.append((timer.name, timer.begin, timer.end))
		return timers

	@staticmethod
	def getTimersList():

		recordHandler = NavigationInstance.instance.RecordTimer

		entry = None
		timers = []
		serienRec_chlist = buildSTBchannellist()

		for timer in recordHandler.timer_list:
			if timer and timer.service_ref and timer.eit is not None:

				location = 'NULL'
				channel = 'NULL'
				recordedfile ='NULL' 
				if timer.dirname:
					location = timer.dirname
				channel = getChannelByRef(serienRec_chlist,str(timer.service_ref))
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
		timers = []
		removed = False
		print "[Serien Recorder] try to temove enigma2 Timer:", serien_name, start_time
		
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
	def addTimer(session, serviceref, begin, end, name, description, eit, disabled, dirname, vpsSettings, logentries=None, recordfile=None, forceWrite=True):

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
					AFTEREVENT.AUTO,
					dirname = dirname,
					tags = None)

			timer.repeated = 0

			if VPSPluginAvailable:
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
			print e
			return {
				"result": False,
				"message": "Could not add timer '%s'!" % e
			}

		#if not config.plugins.skyrecorder.silent_timer_mode or config.plugins.skyrecorder.silent_timer_mode.value == False:
		#message = session.open(MessageBox, _("%s - %s added.\nZiel: %s") % (name, description, dirname), MessageBox.TYPE_INFO, timeout=3)
		print "[Serien Recorder] Versuche Timer anzulegen:", name, dirname
		if forceWrite:
			writeLog(_("[Serien Recorder] Versuche Timer anzulegen: ' %s - %s '") % (name, dirname))
		return {
			"result": True,
			"message": "Timer '%s' added" % name,
			"eit" : eit
		}

class serienRecCheckForRecording():

	instance = None

	def __init__(self, session, manuell):
		assert not serienRecCheckForRecording.instance, "Go is a singleton class!"
		serienRecCheckForRecording.instance = self
		self.session = session
		self.manuell = manuell
		self.daylist = []
		self.page = 1
		self.color_print = "\033[93m"
		self.color_end = "\33[0m"

		global logFile
		logFile = "%slog" % (config.plugins.serienRec.LogFilePath.value)
		checkFileAccess()
		
		self.daypage = 0
		global dbSerRec
		cCursor = dbSerRec.cursor()
		
		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		cCursor.execute("SELECT * FROM SerienMarker")
		row = cCursor.fetchone()
		if not row:
			writeLog(_("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------") % self.uhrzeit, True)
			print "[Serien Recorder] check: Tabelle SerienMarker leer."
			writeLog(_("[Serien Recorder] check: Tabelle SerienMarker leer."), True)
			writeLog(_("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"), True)
			cCursor.close()
			return

		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if not row:
			writeLog(_("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------") % self.uhrzeit, True)
			print "[Serien Recorder] check: Tabelle Channels leer."
			writeLog(_("[Serien Recorder] check: Tabelle Channels leer."), True)
			writeLog(_("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"), True)
			cCursor.close()
			return
		cCursor.close()
		
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
																	vomMerkzettel INTEGER DEFAULT 0)''')
		dbTmp.commit()
		cTmp.close()

		if not self.manuell and config.plugins.serienRec.update.value:
			refreshTimer = eTimer()
			if isDreamboxOS:
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
			refreshTimer.start(updateZeit, True)
			print "%sSerien Recorder] AutoCheck Hour-Timer gestartet.%s" % (self.color_print, self.color_end)
			writeLog(_("[Serien Recorder] AutoCheck Hour-Timer gestartet."), True)
		elif not self.manuell and config.plugins.serienRec.timeUpdate.value:
			#loctime = time.localtime()
			acttime = (lt[3] * 60 + lt[4])
			deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
			if acttime < deltime:
				deltatime = deltime - acttime
			else:
				deltatime = abs(1440 - acttime + deltime)
			refreshTimer = eTimer()
			if isDreamboxOS:
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(deltatime * 60 * 1000, True)
			print "%s[Serien Recorder] AutoCheck Clock-Timer gestartet.%s" % (self.color_print, self.color_end)
			print "%s[Serien Recorder] Verbleibende Zeit: %s Minuten%s" % (self.color_print, str(deltatime), self.color_end)
			writeLog(_("[Serien Recorder] AutoCheck Clock-Timer gestartet."), True)
			writeLog(_("[Serien Recorder] Verbleibende Zeit: %s Minuten") % str(deltatime), True)
		else:
			print "[Serien Recorder] checkRecTimer manuell."
			global runAutocheckAtExit
			runAutocheckAtExit = False
			self.startCheck(True)

	def startCheck(self, amanuell=False):
		print "%s[Serien Recorder] settings:%s" % (self.color_print, self.color_end)
		print "manuell:", amanuell
		print "stunden check:", config.plugins.serienRec.update.value
		print "uhrzeit check:", config.plugins.serienRec.timeUpdate.value

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		global logFile
		global logFileSave
		logFile = "%slog" % (config.plugins.serienRec.LogFilePath.value)
		checkFileAccess()
		if config.plugins.serienRec.longLogFileName.value:
			logFileSave = "%slog_%s%s%s%s%s" % (config.plugins.serienRec.LogFilePath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
		
		global refreshTimer
		global refreshTimerConnection
		global isDreamboxOS
		if refreshTimer:
			refreshTimer.stop()
			refreshTimer = None

			if refreshTimerConnection:
				refreshTimerConnection = None

			print "%s[Serien Recorder] AutoCheck Timer stop.%s" % (self.color_print, self.color_end)
			writeLog(_("[Serien Recorder] AutoCheck Timer stop."), True)

		if config.plugins.serienRec.update.value:
			refreshTimer = eTimer()
			if isDreamboxOS:
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
			refreshTimer.start(updateZeit, True)
			print "%s[Serien Recorder] AutoCheck Hour-Timer gestartet.%s" % (self.color_print, self.color_end)
			writeLog(_("[Serien Recorder] AutoCheck Hour-Timer gestartet."), True)
		elif config.plugins.serienRec.timeUpdate.value:
			#loctime = time.localtime()
			acttime = (lt[3] * 60 + lt[4])
			deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
			if acttime < deltime:
				deltatime = deltime - acttime
			else:
				deltatime = abs(1440 - acttime + deltime)
			refreshTimer = eTimer()
			if isDreamboxOS:
				refreshTimerConnection = refreshTimer.timeout.connect(self.startCheck)
			else:
				refreshTimer.callback.append(self.startCheck)
			refreshTimer.start(deltatime * 60 * 1000, True)
			print "%s[Serien Recorder] AutoCheck Clock-Timer gestartet.%s" % (self.color_print, self.color_end)
			print "%s[Serien Recorder] Verbleibende Zeit: %s Minuten%s" % (self.color_print, str(deltatime), self.color_end)
			writeLog(_("[Serien Recorder] AutoCheck Clock-Timer gestartet."), True)
			writeLog(_("[Serien Recorder] Verbleibende Zeit: %s Minuten") % str(deltatime), True)

		if config.plugins.serienRec.AutoBackup.value:
			BackupPath = "%s%s%s%s%s%s/" % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
			if not os.path.exists(BackupPath):
				try:
					os.makedirs(BackupPath)
				except:
					pass
			if os.path.isdir(BackupPath):
				global dbSerRec
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
				for filename in os.listdir(BackupPath):
					os.chmod(os.path.join(BackupPath, filename), 0777)
				
		if not config.plugins.serienRec.longLogFileName.value:
			# logFile leeren (renamed to _old)
			if fileExists(logFile):
				shutil.move(logFile,"%s_old" % logFile)
		else:
			date = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteLogFilesOlderThan.value)
			date = date.strftime("%s")
			for filename in os.listdir(config.plugins.serienRec.LogFilePath.value):
				if (filename.find('log_') == 0) and (int(os.path.getmtime(os.path.join(config.plugins.serienRec.LogFilePath.value, filename))) < int(date)):
					os.remove('%s%s' % (config.plugins.serienRec.LogFilePath.value, filename))
					
		open(logFile, 'w').close()

		cCursor = dbSerRec.cursor()
		cCursor.execute("DELETE FROM TimerKonflikte WHERE StartZeitstempel<=?", (int(time.time()),))
		dbSerRec.commit()
		cCursor.close()
		
		if amanuell:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------\n") % (self.uhrzeit, str(self.page)), True)
		else:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------\n") % (self.uhrzeit, str(self.page)), True)
			if config.plugins.serienRec.showNotification.value in ("1", "3"):
				Notifications.AddPopup(_("[Serien Recorder]\nAutomatischer Suchlauf für neue Timer wurde gestartet."), MessageBox.TYPE_INFO, timeout=3, id="[Serien Recorder] Suchlauf wurde gestartet")

		if config.plugins.serienRec.writeLogVersion.value:
			writeLog("STB Type: %s\nImage: %s" % (getSTBType(), getImageVersionString()), True)
		writeLog("SR Version: %s" % config.plugins.serienRec.showversion.value, True)

		sMsg = "\nDEBUG Filter: "
		if config.plugins.serienRec.writeLogChannels.value:
			sMsg += "Senderliste "
		if config.plugins.serienRec.writeLogAllowedSender.value:
			sMsg += "Sender "
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

		self.urls = []
		self.new_urls = []
		self.urls = []
		self.speedStartTime = time.clock()

		# suche nach neuen Serien
		if (config.plugins.serienRec.ActionOnNew.value == "0") or (amanuell and (not config.plugins.serienRec.ActionOnNewManuell.value)):
			self.startCheck3()
		else:
			self.startCheck2(amanuell)

	def startCheck2(self, amanuell):
		if str(config.plugins.serienRec.maxWebRequests.value).isdigit():
			ds = defer.DeferredSemaphore(tokens=int(config.plugins.serienRec.maxWebRequests.value))
		else:
			ds = defer.DeferredSemaphore(tokens=1)

		c1 = re.compile('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', re.S)
		c2 = re.compile('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?<tr><td rowspan="2"></td><td>(.*?)<span class="epg_ep.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', re.S)
		downloads = [ds.run(self.readWebpageForNewStaffel, "http://www.wunschliste.de/serienplaner/%s/%s" % (str(config.plugins.serienRec.screeplaner.value), str(daypage))).addCallback(self.parseWebpageForNewStaffel, c1, c2, amanuell).addErrback(self.dataError) for daypage in range(int(config.plugins.serienRec.checkfordays.value))]
		finished = defer.DeferredList(downloads).addCallback(self.createNewMarker).addCallback(self.startCheck3).addErrback(self.checkError)
		
	def readWebpageForNewStaffel(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'})
		
	def parseWebpageForNewStaffel(self, data, c1, c2, amanuell):
		# read channels
		self.senderListe = {}
		for s in self.readSenderListe():
			self.senderListe[s[0].lower()] = s[:]
			
		head_datum = re.findall('<li class="datum">(.*?)</li>', data, re.S)
		txt = head_datum[0].split(",")
		(day, month, year) = txt[1].split(".")
		UTCDatum = getRealUnixTime(0, 0, day, month, year)
		
		if int(config.plugins.serienRec.screeplaner.value) == 2:
			# Soaps
			raw_tmp = c2.findall(data)
			raw=[]
			for each in raw_tmp:
				each=list(each)
				if each[9]:
					z=re.findall('<span class="epg_st.*?title="Staffel.*?>(.*?)</span>', each[9], re.S)
					if len(z):
						each[9]=z[0]
				raw.append(tuple(each))
		else:
			# Serien
			#raw = re.findall('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', data, re.S)
			raw = c1.findall(data)
			
		if raw:
			for regional,paytv,neu,prime,time,url,serien_name,serien_id,sender,staffel,episode,title in raw:
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				staffel = iso8859_Decode(staffel)

				if str(episode).isdigit():
					if int(episode) == 1:
						(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(self.senderListe, sender)
						if int(status) == 1:
							if not self.checkMarker(serien_name):
								cCursor = dbSerRec.cursor()
								cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND LOWER(Staffel)=?", (serien_name.lower(), str(staffel).lower()))
								row = cCursor.fetchone()
								if not row:
									data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id)
									cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url) VALUES (?, ?, ?, ?, ?, ?)", data)
									dbSerRec.commit()

									if not amanuell:
										if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
											Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] Neue Episode")
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
												data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2") 
												cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
												dbSerRec.commit()

												if not amanuell:
													if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
														Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] Neue Episode")
								else:
									cCursor.execute("SELECT TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=? AND TimerForSpecials=0", (serien_name.lower(),))				
									row = cCursor.fetchone()
									if not row:
										cCursor = dbSerRec.cursor()
										cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND LOWER(Staffel)=?", (serien_name.lower(), str(staffel).lower()))
										row = cCursor.fetchone()
										if not row:
											data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2") 
											cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
											dbSerRec.commit()

											if not amanuell:
												if config.plugins.serienRec.ActionOnNew.value in ("1", "3"):
													Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] Neue Episode")
								
								cCursor.close()
						
							
	def createNewMarker(self, result=True):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, StaffelStart FROM NeuerStaffelbeginn WHERE CreationFlag>0 ORDER BY UTCStaffelStart")
		for row in cCursor:
			(Serie, Staffel, StaffelStart) = row
			if str(Staffel).isdigit():
				writeLog(_("[Serien Recorder] %d. Staffel von '%s' beginnt am %s") % (int(Staffel), Serie, StaffelStart), True) 
			else:
				writeLog(_("[Serien Recorder] Staffel %s von '%s' beginnt am %s") % (Staffel, Serie, StaffelStart), True) 

		if config.plugins.serienRec.ActionOnNew.value in ("2", "3"):
			cTmp = dbSerRec.cursor()
			cCursor.execute("SELECT Serie, MIN(Staffel), Sender, Url FROM NeuerStaffelbeginn WHERE CreationFlag=1 GROUP BY Serie")
			for row in cCursor:
				(Serie, Staffel, Sender, Url) = row
				if str(Staffel).isdigit():
					cTmp.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, 0, -1)", (Serie, Url, Staffel))
					ID = cTmp.lastrowid
					cTmp.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
					cTmp.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
					writeLog(_("[Serien Recorder] Neuer Marker für '%s' wurde angelegt") % Serie, True)
				
			cCursor.execute("SELECT Serie, MAX(Staffel), Sender, Url FROM NeuerStaffelbeginn WHERE CreationFlag=1 GROUP BY Serie")
			for row in cCursor:
				(Serie, Staffel, Sender, Url) = row
				if not str(Staffel).isdigit():
					cTmp.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(),))
					row = cTmp.fetchone()
					if not row:
						cTmp.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel, TimerForSpecials) VALUES (?, ?, ?, 0, -1, 1)", (Serie, Url, Staffel))
						ID = cTmp.lastrowid
						cTmp.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
						cTmp.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
					else:
						cTmp.execute("UPDATE OR IGNORE SerienMarker SET TimerForSpecials=1 WHERE LOWER(Serie)=?", (Serie.lower(),))
					writeLog(_("[Serien Recorder] Neuer Marker für '%s' wurde angelegt") % Serie, True)

			cTmp.close()
			cCursor.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET CreationFlag=0 WHERE CreationFlag=1")
			
		if config.plugins.serienRec.ActionOnNew.value != "0":
			date = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteOlderThan.value)
			date = date.strftime("%s")
			cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE UTCStaffelStart<=?", (date,))
			
		dbSerRec.commit()
		cCursor.close()
		return result

	def adjustEPGtimes(self, current_time):
		cTimer = dbSerRec.cursor()
		cCursor = dbSerRec.cursor()

		##############################
		#
		# try to get eventID (eit) from epgCache
		#
		if config.plugins.serienRec.eventid.value:
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>? AND EventID=0", (current_time, ))
			for row in cCursor:
				(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row
						
				(margin_before, margin_after) = getMargins(serien_name, webChannel)
		
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(serien_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(serien_time)+(int(margin_before) * 60))
				if event_matches and len(event_matches) > 0:
					title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
					(dirname, dirname_serie) = getDirname(serien_name, staffel)
					for event_entry in event_matches:
						writeLog(_("[Serien Recorder] Versuche Timer zu aktualisieren: ' %s - %s '") % (title, dirname))
						eit = int(event_entry[1])
						start_unixtime = int(event_entry[3]) - (int(margin_before) * 60)
						end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
						
						print "[Serien Recorder] try to modify enigma2 Timer:", title, serien_time
						recordHandler = NavigationInstance.instance.RecordTimer
						try:
							timerFound = False
							# suche in aktivierten Timern
							for timer in recordHandler.timer_list:
								if timer and timer.service_ref:
									if (timer.begin == int(serien_time)) and (timer.eit != eit):
										timer.begin = start_unixtime
										timer.end = end_unixtime
										timer.eit = eit
										NavigationInstance.instance.RecordTimer.timeChanged(timer)
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=? AND EventID=0"
										cTimer.execute(sql, (start_unixtime, eit, serien_time, stbRef.lower()))
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
										old_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
										writeLog(_("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> von %s -> auf %s @ %s") % (title, old_start, show_start, webChannel), True)
										self.countTimerUpdate += 1
										timerFound = True
										break
							if not timerFound:
								# suche in deaktivierten Timern
								for timer in recordHandler.processed_timers:
									if timer and timer.service_ref:
										if (timer.begin == int(serien_time)) and (timer.eit != eit):
											timer.begin = start_unixtime
											timer.end = end_unixtime
											timer.eit = eit
											NavigationInstance.instance.RecordTimer.timeChanged(timer)
											sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=? AND EventID=0"
											cTimer.execute(sql, (start_unixtime, eit, serien_time, stbRef.lower()))
											show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
											old_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
											writeLog(_("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> von %s -> auf %s @ %s") % (title, old_start, show_start, webChannel), True)
											self.countTimerUpdate += 1
											break
						except Exception:				
							print "[Serien Recorder] Modifying enigma2 Timer failed:", title, serien_time
						break
						
		dbSerRec.commit()
					
		cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>? AND EventID>0", (current_time, ))
		for row in cCursor:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row

			(margin_before, margin_after) = getMargins(serien_name, webChannel)

			epgmatches = []
			epgcache = eEPGCache.getInstance()
			allevents = epgcache.lookupEvent(['IBD',(stbRef, 2, eit, -1)]) or []

			for eventid, begin, duration in allevents:
				if int(eventid) == int(eit):
					if int(begin) != (int(serien_time) + (int(margin_before) * 60)):
						title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
						(dirname, dirname_serie) = getDirname(serien_name, staffel)
						writeLog(_("[Serien Recorder] Versuche Timer zu aktualisieren: ' %s - %s '") % (title, dirname))
						start_unixtime = int(begin)
						start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
						end_unixtime = int(begin) + int(duration)
						end_unixtime = int(end_unixtime) + (int(margin_after) * 60)
						
						print "[Serien Recorder] try to modify enigma2 Timer:", title, serien_time
						recordHandler = NavigationInstance.instance.RecordTimer
						try:
							timerFound = False
							# suche in aktivierten Timern
							for timer in recordHandler.timer_list:
								if timer and timer.service_ref:
									if timer.eit == eit:
										timer.begin = start_unixtime
										timer.end = end_unixtime
										NavigationInstance.instance.RecordTimer.timeChanged(timer)
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=? AND EventID=?"
										cTimer.execute(sql, (start_unixtime, serien_time, stbRef.lower(), eit))
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
										old_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
										writeLog(_("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> von %s -> auf %s @ %s") % (title, old_start, show_start, webChannel), True)
										self.countTimerUpdate += 1
										timerFound = True
										break
							if not timerFound:
								# suche in deaktivierten Timern
								for timer in recordHandler.processed_timers:
									if timer and timer.service_ref:
										if timer.eit == eit:
											timer.begin = start_unixtime
											timer.end = end_unixtime
											NavigationInstance.instance.RecordTimer.timeChanged(timer)
											sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=? AND EventID=?"
											cTimer.execute(sql, (start_unixtime, serien_time, stbRef.lower(), eit))
											show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
											old_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
											writeLog(_("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> von %s -> auf %s @ %s") % (title, old_start, show_start, webChannel), True)
											self.countTimerUpdate += 1
											break
						except Exception:				
							print "[Serien Recorder] Modifying enigma2 Timer failed:", title, serien_time
					break
					
		dbSerRec.commit()
		cCursor.close()
		cTimer.close()

		# versuche deaktivierte Timer (auf anderer Box) zu erstellen
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
							if (timer.begin == serien_time) and (timer.service_ref == stbRef):
								timerFound = True
								break
					if not timerFound:
						(margin_before, margin_after) = getMargins(serien_name, webChannel)

						# get VPS settings for channel
						vpsSettings = getVPS(webChannel)
						
						epgmatches = []
						epgcache = eEPGCache.getInstance()
						allevents = epgcache.lookupEvent(['IBD',(stbRef, 2, eit, -1)]) or []

						for eventid, begin, duration in allevents:
							if int(begin) == (int(serien_time) + (int(margin_before) * 60)):
								(dirname, dirname_serie) = getDirname(serien_name, staffel)
								label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
								if config.plugins.serienRec.TimerName.value == "0":
									timer_name = label_serie
								else:
									timer_name = serien_name
								writeLog(_("[Serien Recorder] Versuche deaktivierten Timer aktiv zu erstellen: ' %s - %s '") % (serien_title, dirname))
								end_unixtime = int(begin) + int(duration)
								end_unixtime = int(end_unixtime) + (int(margin_after) * 60)
								result = serienRecAddTimer.addTimer(self.session, stbRef, str(serien_time), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), serien_title), eit, False, dirname, vpsSettings, None, recordfile=".ts")
								if result["result"]:
									self.countTimer += 1
									# Eintrag in das timer file
									cTimer = dbSerRec.cursor()
									cTimer.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE Serie=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", row)
									dbSerRec.commit()
									cTimer.close()
									show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(serien_time)))
									writeLog(_("[Serien Recorder] ' %s ' - Timer wurde angelegt -> %s %s @ %s") % (label_serie, show_start, timer_name, webChannel), True)
								break

				except:				
					pass

		dbSerRec.commit()
		cCursor.close()
		
	def startCheck3(self, result=True):
		self.cTmp = dbTmp.cursor()
		self.cTmp.execute("DELETE FROM GefundeneFolgen")
		
		# read channels
		self.senderListe = {}
		for s in self.readSenderListe():
			self.senderListe[s[0].lower()] = s[:]
			
		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)
		
		## hier werden die wunschliste urls eingelesen vom serien marker
		self.urls = getMarker()
		self.count_url = 0
		self.countTimer = 0
		self.countTimerUpdate = 0
		self.countNotActiveTimer = 0
		self.countTimerFromWishlist = 0
		self.countSerien = self.countMarker()
		self.NoOfRecords = int(config.plugins.serienRec.NoOfRecords.value)
		if str(config.plugins.serienRec.maxWebRequests.value).isdigit():
			ds = defer.DeferredSemaphore(tokens=int(config.plugins.serienRec.maxWebRequests.value))
		else:
			ds = defer.DeferredSemaphore(tokens=1)

		##('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		#c1 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>')
		c1 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>(?:\((.*?)x(.*?)\).)*<span class="titel">(.*?)</span></td></tr>')
		c2 = re.compile('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(.*?x))(.*?)\).<span class="titel">(.*?)</span></td></tr>')
		downloads = [ds.run(self.download, SerieUrl).addCallback(self.parseWebpage,c1,c2,serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen,current_time,future_time).addErrback(self.dataError) for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen in self.urls]
		finished = defer.DeferredList(downloads).addCallback(self.createTimer).addErrback(self.dataError)
		
	def download(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, timeout=20, headers={'Content-Type':'application/x-www-form-urlencoded'})

	def parseWebpage(self, data, c1, c2, serien_name, SerieUrl, staffeln, allowedSender, AbEpisode, AnzahlAufnahmen, current_time, future_time):
		self.count_url += 1

		raw = c1.findall(data)
		raw2 = c2.findall(data)
		raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])
		# check for parsing error
		if not raw:
			# parsing error -> nothing to do
			return
			
		(fromTime, toTime) = getTimeSpan(serien_name)
		if self.NoOfRecords < AnzahlAufnahmen:
			self.NoOfRecords = AnzahlAufnahmen
		
		# loop over all transmissions
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			# umlaute umwandeln
			sender = iso8859_Decode(sender)
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
			title = iso8859_Decode(title)
			staffel = iso8859_Decode(staffel)

			# if there is no season or episode number it can be a special
			# but if we have more than one special and wunschliste.de does not
			# give us an episode number we are unable to differentiate between these specials
			if not staffel and not episode:
				staffel = "S"

			# initialize strings
			seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
			label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)
			sTitle = "%s - %s" % (serien_name, seasonEpisodeString)

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
				cCursorTmp.execute("SELECT * FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), episode.lower()))
				row = cCursorTmp.fetchone()
				if row:
					writeLog(_("[Serien Recorder] ' %s ' - Timer vom Merkzettel wird angelegt @ %s") % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True
				cCursorTmp.close()
				
			if not serieAllowed:
				if config.plugins.serienRec.writeLogAllowedSender.value:
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

			# Process time and date relevant data

			(margin_before, margin_after) = getMargins(serien_name, sender)

			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = startzeit.split('.')
			(end_hour, end_min) = endzeit.split('.')

			start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)

			if int(start_hour) > int(end_hour):
				end_unixtime = getNextDayUnixtime(end_min, end_hour, day, month)
			else:
				end_unixtime = getUnixTimeAll(end_min, end_hour, day, month)

			# setze die vorlauf/nachlauf-zeit
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)


			# The transmission list is sorted by date, so it is save to break if we reach the time span for regular timers
			if config.plugins.serienRec.breakTimersuche.value:
				if (int(fromTime) > 0) or (int(toTime) < (23*60)+59):
					start_time = (time.localtime(int(start_unixtime)).tm_hour * 60) + time.localtime(int(start_unixtime)).tm_min
					end_time = (time.localtime(int(end_unixtime)).tm_hour * 60) + time.localtime(int(end_unixtime)).tm_min
					if not allowedTimeRange(fromTime, toTime, start_time, end_time):
						if not config.plugins.serienRec.forceRecording.value:
							break

				TimeSpan_time = int(future_time)
				if config.plugins.serienRec.forceRecording.value:
					TimeSpan_time += (int(config.plugins.serienRec.TimeSpanForRegularTimer.value) - int(config.plugins.serienRec.checkfordays.value)) * 86400
				if int(start_unixtime) > int(TimeSpan_time):
					# We reached the maximal time range to look for transmissions, so we can break here
					break

			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit, new_end_unixtime, new_start_unixtime = getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, stbRef)
			alt_eit, alt_end_unixtime, alt_start_unixtime = getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, altstbRef)

			(dirname, dirname_serie) = getDirname(serien_name, staffel)

			cCursorTmp = dbTmp.cursor()
			sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, Staffel, Episode, SeasonEpisode, Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, EventID, alternativStbChannel, alternativServiceRef, alternativStartTime, alternativEndTime, alternativEventID, DirName, AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
			cCursorTmp.execute(sql, (current_time, future_time, serien_name, staffel, episode, seasonEpisodeString, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel)))
			cCursorTmp.close()
			
	def createTimer(self, result=True):
		dbTmp.commit()

		# jetzt die Timer erstellen	
		for x in range(self.NoOfRecords): 
			self.searchTimer(x)
			dbTmp.commit()
		
		# gleiche alte Timer mit EPG ab
		current_time = int(time.time())
		if config.plugins.serienRec.eventid.value:
			self.adjustEPGtimes(current_time)
	
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
			writeLog(_("[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert.") % (str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate)), True)
			print "[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate))
		else:
			writeLog(_("[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt.") % (str(self.countSerien), str(self.countTimer)), True)
			print "[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countSerien), str(self.countTimer))
		if self.countNotActiveTimer > 0:
			writeLog(_("[Serien Recorder] %s Timer wurde(n) wegen Konfikten deaktiviert erstellt!") % str(self.countNotActiveTimer), True)
			print "[Serien Recorder] %s Timer wurde(n) wegen Konfikten deaktiviert erstellt!" % str(self.countNotActiveTimer)
		if self.countTimerFromWishlist > 0:
			writeLog(_("[Serien Recorder] %s Timer vom Merkzettel wurde(n) erstellt!") % str(self.countTimerFromWishlist), True)
			print "[Serien Recorder] %s Timer vom Merkzettel wurde(n) erstellt!" % str(self.countTimerFromWishlist)
		writeLog(_("---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------") % str(speedTime), True)
		print "---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------" % str(speedTime)
		if (config.plugins.serienRec.showNotification.value in ("2", "3")) and (not self.manuell):
			statisticMessage = _("Serien vorgemerkt: %s\nTimer erstellt: %s\nTimer aktualisiert: %s\nTimer mit Konflikten: %s\nTimer vom Merkzettel: %s") % (str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate), str(self.countNotActiveTimer), str(self.countTimerFromWishlist))
			Notifications.AddPopup(_("[Serien Recorder]\nAutomatischer Suchlauf für neue Timer wurde beendet.\n\n%s") % statisticMessage, MessageBox.TYPE_INFO, timeout=10, id="[Serien Recorder] Suchlauf wurde beendet")

		if config.plugins.serienRec.longLogFileName.value:
			shutil.copy(logFile, logFileSave)
		
		global autoCheckFinished
		autoCheckFinished = True

		# in den deep-standby fahren.
		if (config.plugins.serienRec.updateInterval.value == 24) and config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.afterAutocheck.value and not self.manuell:
			if config.plugins.serienRec.DSBTimeout.value > 0:
				self.session.openWithCallback(self.gotoDeepStandby, MessageBox, _("[Serien Recorder]\nBox in Deep-Standby fahren?"), MessageBox.TYPE_YESNO, default=True, timeout=config.plugins.serienRec.DSBTimeout.value)
			else:
				self.gotoDeepStandby(True)
				
		return result
				
	def gotoDeepStandby(self, answer):
		if answer:
			print "[Serien Recorder] gehe in Deep-Standby"
			writeLog(_("[Serien Recorder] gehe in Deep-Standby"))
			self.session.open(TryQuitMainloop, 1)

	def searchTimer(self, NoOfRecords):
		if NoOfRecords:
			optionalText = _(" (%s. Wiederholung)") % NoOfRecords
		else:
			optionalText = ""

		writeLog(_("\n---------' Erstelle Timer%s '-------------------------------------------------------------------------------\n") % optionalText, True)
			
		cTmp = dbTmp.cursor()
		cTmp.execute("SELECT * FROM (SELECT SerieName, Staffel, Episode, COUNT(*) AS Anzahl FROM GefundeneFolgen GROUP BY SerieName, Staffel, Episode) ORDER BY Anzahl")
		for row in cTmp:
			(serien_name, staffel, episode, anzahl) = row

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
			#if not fileExists(dirname):
			#	print "[Serien Recorder] erstelle Subdir %s" % dirname
			#	writeLog(_("[Serien Recorder] erstelle Subdir: ' %s '") % dirname)
			#	os.makedirs(dirname)
			#if fileExists(dirname):
			#	if fileExists("/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("%s%s.jpg" % (dirname_serie, serien_name)):
			#		shutil.copy("/tmp/serienrecorder/%s.png" % serien_name, "%s%s.jpg" % (dirname_serie, serien_name))
			#	if fileExists("/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("%s%s.jpg" % (dirname, serien_name)):
			#		shutil.copy("/tmp/serienrecorder/%s.png" % serien_name, "%s%s.jpg" % (dirname, serien_name))
			self.enableDirectoryCreation = False

			self.konflikt = ""
			TimerDone = self.searchTimer2(serien_name, staffel, episode, optionalText, preferredChannel, dirname)
			if (not TimerDone) and (useAlternativeChannel):
				if preferredChannel == 1:
					usedChannel = 2
				else:
					usedChannel = 1
				TimerDone = self.searchTimer2(serien_name, staffel, episode, optionalText, usedChannel, dirname)
			
			if not TimerDone:
				cTimer = dbTmp.cursor()
				cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
				for row2 in cTimer:
					(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel) = row2
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
					if allowedTimeRange(fromTime, toTime, start_time, end_time):
						if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel, True):
							cAdded = dbTmp.cursor()
							cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
							cAdded.close()
							break
				cTimer.close()
				
				if len(self.konflikt) > 0:
					if config.plugins.serienRec.showMessageOnConflicts.value:
						Notifications.AddPopup(_("[Serien Recorder]\nACHTUNG!  -  %s") % self.konflikt, MessageBox.TYPE_INFO, timeout=-1)
						
			##############################
			#
			# erstellt das serien verzeichnis
			if TimerDone and self.enableDirectoryCreation:
				CreateDirectory(serien_name, staffel)
					
		cTmp.close()
					
	def searchTimer2(self, serien_name, staffel, episode, optionalText, usedChannel, dirname):				
		# prepare postprocessing for forced recordings
		forceRecordings = []
		self.konflikt = ""

		TimerDone = False
		cTimer = dbTmp.cursor()
		cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), str(staffel).lower(), episode.lower()))
		for row in cTimer:
			(current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, start_unixtime, end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, vomMerkzettel) = row
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
			
			##############################
			#
			# CHECK
			#
			# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
			#
			# check ob timer existiert
			if checkTimerAdded(webChannel, serien_name, staffel, episode, int(timer_start_unixtime)):
				writeLogFilter("added", _("[Serien Recorder] ' %s ' - Staffel/Episode%s Timer wurde bereits erstellt -> ' %s '") % (label_serie, optionalText, check_SeasonEpisode))
				cAdded = dbTmp.cursor()
				cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				cAdded.close()
				continue

			# check anzahl timer
			if checkAlreadyAdded(serien_name, staffel, episode) >= AnzahlAufnahmen:
				writeLogFilter("added", _("[Serien Recorder] ' %s ' - Staffel/Episode%s bereits in added vorhanden -> ' %s '") % (label_serie, optionalText, check_SeasonEpisode))
				TimerDone = True
				break

			# check anzahl auf hdd
			bereits_vorhanden = countEpisodeOnHDD(dirname, check_SeasonEpisode, serien_name, False)

			if bereits_vorhanden >= AnzahlAufnahmen:
				writeLogFilter("disk", _("[Serien Recorder] ' %s ' - Staffel/Episode%s bereits auf hdd vorhanden -> ' %s '") % (label_serie, optionalText, check_SeasonEpisode))
				TimerDone = True
				break
				
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
				if not allowedTimeRange(fromTime, toTime, start_time, end_time):
					timeRangeList = "[%s:%s-%s:%s]" % (str(int(fromTime)/60).zfill(2), str(int(fromTime)%60).zfill(2), str(int(toTime)/60).zfill(2), str(int(toTime)%60).zfill(2))
					writeLogFilter("timeRange", _("[Serien Recorder] ' %s ' - Timer (%s:%s-%s:%s) nicht in Zeitspanne %s") % (label_serie, str(start_time/60).zfill(2), str(start_time%60).zfill(2), str(end_time/60).zfill(2), str(end_time%60).zfill(2), timeRangeList))
					# forced recording activated?
					if not config.plugins.serienRec.forceRecording.value:
						continue
						
					# backup timer data for post processing
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
					writeLogFilter("timeRange", _("[Serien Recorder] ' %s ' - Backup Timer -> %s") % (label_serie, show_start))
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
						writeLogFilter("timeRange", _("[Serien Recorder] ' %s ' - Backup Timer -> %s") % (label_serie, show_start))
						forceRecordings.append((title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel))
						continue

			##############################
			#
			# Setze Timer
			#
			if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
				cAdded = dbTmp.cursor()
				cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
				cAdded.close()
				TimerDone = True
				break
				
		### end of for loop
		cTimer.close()
		
		if not TimerDone:
			# post processing for forced recordings
			for title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, vomMerkzettel in forceRecordings:
				show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(timer_start_unixtime)))
				writeLog(_("[Serien Recorder] ' %s ' - Keine Wiederholung gefunden! -> %s") % (label_serie, show_start), True)
				# programmiere Timer
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel):
					cAdded = dbTmp.cursor()
					cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), str(staffel).lower(), episode.lower(), start_unixtime, stbRef.lower()))
					cAdded.close()
					TimerDone = True
					break
					
		return TimerDone
		
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
			writeLogFilter("timeLimit", _("[Serien Recorder] ' %s ' - Timer wird später angelegt -> Sendetermin: %s - Erlaubte Zeitspanne bis %s") % (label_serie, show_start, show_future))
			return True
		if int(current_time) > int(start_unixtime):
			show_current = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
			writeLogFilter("timeLimit", _("[Serien Recorder] ' %s ' - Der Sendetermin liegt in der Vergangenheit: %s - Aktuelles Datum: %s") % (label_serie, show_start, show_current))
			return True

		# get VPS settings for channel
		vpsSettings = getVPS(webChannel)
			
		# versuche timer anzulegen
		# setze strings für addtimer
		if checkTuner(start_unixtime, end_unixtime):
			if config.plugins.serienRec.TimerName.value == "0":
				timer_name = label_serie
			else:
				timer_name = serien_name
			result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, False, dirname, vpsSettings, None, recordfile=".ts")
			if result["result"]:
				self.countTimer += 1
				# Eintrag in das timer file
				self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit)
				if vomMerkzettel:
					self.countTimerFromWishlist += 1
					writeLog(_("[Serien Recorder] ' %s ' - Timer (vom Merkzettel) wurde angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					cCursor = dbSerRec.cursor()
					cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), episode.lower()))
					dbSerRec.commit()	
					cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), str(staffel).lower(), episode.lower()))
					dbSerRec.commit()	
					cCursor.close()
				else:
					writeLog(_("[Serien Recorder] ' %s ' - Timer wurde angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
				self.enableDirectoryCreation = True
				return True
			elif not tryDisabled:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog(_("[Serien Recorder] ' %s ' - Timer konnte nicht angelegt werden%s -> %s %s @ %s") % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
			else:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog(_("[Serien Recorder] ' %s ' - ACHTUNG! -> %s") % (label_serie, result["message"]), True)
				dbMessage = result["message"].replace("Conflicting Timer(s) detected!", "").strip()
				
				result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), timer_name, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, True, dirname, vpsSettings, None, recordfile=".ts")
				if result["result"]:
					self.countNotActiveTimer += 1
					# Eintrag in das timer file
					self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit, False)
					cCursor = dbSerRec.cursor()
					cCursor.execute("INSERT OR IGNORE INTO TimerKonflikte (Message, StartZeitstempel, webChannel) VALUES (?, ?, ?)", (dbMessage, int(start_unixtime), webChannel))
					if vomMerkzettel:
						self.countTimerFromWishlist += 1
						writeLog(_("[Serien Recorder] ' %s ' - Timer (vom Merkzettel) wurde deaktiviert angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
						#cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (serien_name.lower(), str(staffel).lower(), episode.lower()))
						#dbSerRec.commit()	
						#cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), str(staffel).lower(), episode.lower()))
						#dbSerRec.commit()
					else:
						writeLog(_("[Serien Recorder] ' %s ' - Timer wurde deaktiviert angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, timer_name, stbChannel), True)
					cCursor.close()
					self.enableDirectoryCreation = True
					return True
		else:
			print "[Serien Recorder] Tuner belegt %s %s" % (label_serie, show_start)
			writeLog(_("[Serien Recorder] Tuner belegt: %s %s") % (label_serie, show_start), True)
		return False
			
	def checkMarker(self, Serie):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			return True
		else:	
			return False

	def countMarker(self):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Count(*) FROM SerienMarker")
		(count,) = cCursor.fetchone()	
		cCursor.close()
		return count

	def readSenderListe(self):
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels")
		for row in cCursor:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
			fSender.append((webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status))
		cCursor.close()
		return fSender
		
	def checkSender(self, mSlist, mSender):
		if mSender.lower() in mSlist:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = mSlist[mSender.lower()]
			if altstbChannel == "":
				altstbChannel = stbChannel
				altstbRef = stbRef
			elif stbChannel == "":
				stbChannel = altstbChannel
				stbRef = altstbRef
		else:
			webChannel = mSender
			stbChannel = ""
			stbRef = ""
			altstbChannel = ""
			altstbRef = ""
			status = "0"
		return (webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status)

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, TimerAktiviert = True):
		(margin_before, margin_after) = getMargins(serien_name, webChannel)
		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		#sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ?<=StartZeitstempel<=?"
		cCursor.execute(sql, (serien_name.lower(), stbRef.lower(), int(start_time) + (int(margin_before) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(margin_before) * 60) + (int(EPGTimeSpan) * 60)))
		row = cCursor.fetchone()
		if row:
			sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=?, TimerAktiviert=? WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
			cCursor.execute(sql, (eit, int(TimerAktiviert), serien_name.lower(), stbRef.lower(), int(start_time) + (int(margin_before) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(margin_before) * 60) + (int(EPGTimeSpan) * 60)))
			print "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", _("[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, int(TimerAktiviert)))
			#cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			print "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", _("[Serien Recorder] Timer angelegt: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		dbSerRec.commit()
		cCursor.close()
		
	def dataError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog(_("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)") % error, True)
		
		if config.plugins.serienRec.longLogFileName.value:
			shutil.copy(logFile, logFileSave)
		
		global autoCheckFinished
		autoCheckFinished = True
		
		# in den deep-standby fahren.
		if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.afterAutocheck.value and not self.manuell:
			if config.plugins.serienRec.DSBTimeout.value > 0:
				self.session.openWithCallback(self.gotoDeepStandby, MessageBox, _("[Serien Recorder]\nBox in Deep-Standby fahren?"), MessageBox.TYPE_YESNO, default=True, timeout=config.plugins.serienRec.DSBTimeout.value)
			else:
				self.gotoDeepStandby(True)
		self.close()

	def checkError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog(_("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)") % error, True)
		
		if config.plugins.serienRec.longLogFileName.value:
			shutil.copy(logFile, logFileSave)
		
		global autoCheckFinished
		autoCheckFinished = True
		
		# in den deep-standby fahren.
		if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.afterAutocheck.value and not self.manuell:
			if config.plugins.serienRec.DSBTimeout.value > 0:
				self.session.openWithCallback(self.gotoDeepStandby, MessageBox, _("[Serien Recorder]\nBox in Deep-Standby fahren?"), MessageBox.TYPE_YESNO, default=True, timeout=config.plugins.serienRec.DSBTimeout.value)
			else:
				self.gotoDeepStandby(True)
		self.close()

class serienRecTimer(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			#"ok"    : self.keyOK,
			"cancel": (self.keyCancel, _("zurück zur Serienplaner-Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("ausgewählten Timer löschen")),
			"green" : (self.viewChange, _("Sortierung ändern")),
			"yellow": (self.keyYellow, _("umschalten alle/nur aktive Timer anzeigen")),
			"blue"  : (self.keyBlue, _("alle vergangenen Timer aus der Datenbank löschen")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
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

		self['text_red'].setText(_("Entferne Timer"))
		if config.plugins.serienRec.recordListView.value == 0:
			self['text_green'].setText(_("Zeige früheste Timer zuerst"))
		elif config.plugins.serienRec.recordListView.value == 1:
			self['text_green'].setText(_("Zeige neuste Timer zuerst"))
		self['text_yellow'].setText(_("Zeige auch alte Timer"))
		self['text_blue'].setText(_("Entferne alle alten"))

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(50)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['cover'].show()

		if not showAllButtons:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
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

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		check = self['config'].getCurrent()
		if check == None:
			return
			
		serien_name = self['config'].getCurrent()[0][0]
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readTimer()
				
	def viewChange(self):
		if config.plugins.serienRec.recordListView.value == 1:
			config.plugins.serienRec.recordListView.value = 0
			self['text_green'].setText(_("Zeige neuste Timer zuerst"))
		else:
			config.plugins.serienRec.recordListView.value = 1
			self['text_green'].setText(_("Zeige früheste Timer zuerst"))
		config.plugins.serienRec.recordListView.save()
		self.readTimer()

	def readTimer(self, showTitle=True):
		current_time = int(time.time())
		deltimer = 0
		timerList = []

		cCursor = dbSerRec.cursor()
		if self.filter:
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>=?", (current_time, ))
		else:
			cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, webChannel, EventID FROM AngelegteTimer")
		for row in cCursor:
			(serie, staffel, episode, title, start_time, webChannel, eit) = row
			if int(start_time) < int(current_time):
				deltimer += 1
				timerList.append((serie, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), start_time, webChannel, "1", eit))
			else:
				timerList.append((serie, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), start_time, webChannel, "0", eit))
		cCursor.close()
		
		if showTitle:			
			self['title'].instance.setForegroundColor(parseColor("white"))
			if self.filter:
				self['title'].setText(_("TimerList: %s Timer sind vorhanden.") % len(timerList))
			else:
				self['title'].setText(_("TimerList: %s Aufnahme(n) und %s Timer sind vorhanden.") % (deltimer, len(timerList)-deltimer))

		if config.plugins.serienRec.recordListView.value == 0:
			timerList.sort(key=lambda t : t[2])
		elif config.plugins.serienRec.recordListView.value == 1:
			timerList.sort(key=lambda t : t[2])
			timerList.reverse()

		self.chooseMenuList.setList(map(self.buildList, timerList))
		if len(timerList) == 0:
			if showTitle:			
				self['title'].instance.setForegroundColor(parseColor("white"))
				self['title'].setText(_("Serien Timer - 0 Serien in der Aufnahmeliste."))

		self.getCover()

	def buildList(self, entry):
		(serie, title, start_time, webChannel, foundIcon, eit) = entry
		WochenTag=[_("Mo"), _("Di"), _("Mi"), _("Do"), _("Fr"), _("Sa"), _("So")]
		xtime = time.strftime(WochenTag[time.localtime(int(start_time)).tm_wday]+", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))

		if int(foundIcon) == 1:
			imageFound = "%simages/found.png" % serienRecMainPath
		else:
			imageFound = "%simages/black.png" % serienRecMainPath
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 8, 32, 32, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29, 250, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, colorYellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, colorYellow)
			]

	def keyOK(self):
		pass

	def callDeleteSelectedTimer(self, answer):
		if answer:
			serien_name = self['config'].getCurrent()[0][0]
			serien_title = self['config'].getCurrent()[0][1]
			serien_time = self['config'].getCurrent()[0][2]
			serien_channel = self['config'].getCurrent()[0][3]
			serien_eit = self['config'].getCurrent()[0][5]
			self.removeTimer(serien_name, serien_title, serien_time, serien_channel, serien_eit)
		else:
			return
			
	def removeTimer(self, serien_name, serien_title, serien_time, serien_channel, serien_eit=0):
		title = "%s - %s" % (serien_name, serien_title)
		removed = serienRecAddTimer.removeTimerEntry(title, serien_time, serien_eit)
		if not removed:
			print "[Serien Recorder] enigma2 NOOOTTT removed"
		else:
			print "[Serien Recorder] enigma2 Timer removed."
		cCursor = dbSerRec.cursor()
		if serien_eit > 0:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE EventID=?", (serien_eit, ))
		else:
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (serien_name.lower(), serien_time, serien_channel.lower()))
		dbSerRec.commit()
		cCursor.close()
		
		self.changesMade = True
		self.readTimer(False)
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText(_("Timer '- %s -' entfernt.") % serien_name)

	def keyRed(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Timer leer."
			return
		else:
			serien_name = self['config'].getCurrent()[0][0]
			serien_title = self['config'].getCurrent()[0][1]
			serien_time = self['config'].getCurrent()[0][2]
			serien_channel = self['config'].getCurrent()[0][3]
			serien_eit = self['config'].getCurrent()[0][5]
			found = False
			print self['config'].getCurrent()[0]

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (serien_name.lower(), serien_time, serien_channel.lower()))
			if cCursor.fetchone():
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, _("Soll '%s - %s' wirklich entfernt werden?") % (serien_name, serien_title), MessageBox.TYPE_YESNO, default = False)				
				else:
					self.removeTimer(serien_name, serien_title, serien_time, serien_channel, serien_eit)
			else:
				print "[Serien Recorder] keinen passenden timer gefunden."
			cCursor.close()
			
	def keyYellow(self):
		if self.filter:
			self['text_yellow'].setText(_("Zeige nur neue Timer"))
			self.filter = False
		else:
			self['text_yellow'].setText(_("Zeige auch alte Timer"))
			self.filter = True
		self.readTimer(self)
		
	def removeOldTimerFromDB(self, answer):
		if answer:
			current_time = int(time.time())
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM AngelegteTimer WHERE StartZeitstempel<?", (current_time, ))
			dbSerRec.commit()
			cCursor.close()
		
			self.readTimer(False)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText(_("Alle alten Timer wurden entfernt."))
		else:
			return

	def keyBlue(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeOldTimerFromDB, MessageBox, _("Sollen wirklich alle alten Timer entfernt werden?"), MessageBox.TYPE_YESNO, default = False)				
		else:
			self.removeOldTimerFromDB(True)
			
	def getCover(self):
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][0]
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		id = None
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				id = "/%s" % id[0]
		getCover(self, serien_name, id)
			
	def keyLeft(self):
		self['config'].pageUp()
		self.getCover()

	def keyRight(self):
		self['config'].pageDown()
		self.getCover()

	def keyDown(self):
		self['config'].down()
		self.getCover()

	def keyUp(self):
		self['config'].up()
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

	def dataError(self, error):
		print error

class serienRecRunAutoCheck(Screen, HelpableScreen):
	def __init__(self, session, manuell=True):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.manuell = manuell

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.logliste = []
		self.points = ""

		self.onLayoutFinish.append(self.startCheck)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)
		
		self['text_red'].setText(_("Abbrechen"))
		self.num_bt_text[0][0] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na
			
		self.displayTimer = None
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
			self.chooseMenuList.l.setItemHeight(70)
		else:
			self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['title'].setText(_("Suche nach neuen Timern läuft."))

		if not showAllButtons:
			self['bt_red'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

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
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.startCheck()
				
	def startCheck(self):
		if self.manuell:
			global autoCheckFinished
			autoCheckFinished = False
			serienRecCheckForRecording(self.session, True)

		# Log Reload Timer
		self.readLogTimer = eTimer()
		if isDreamboxOS:
			self.readLogTimer_conn = self.readLogTimer.timeout.connect(self.readLog)
		else:
			self.readLogTimer.callback.append(self.readLog)
		self.readLogTimer.start(2500)
		self.readLog()

	def readLog(self):
		global autoCheckFinished
		if autoCheckFinished or not self.manuell:
			if self.readLogTimer:
				self.readLogTimer.stop()
				self.readLogTimer = None
			print "[Serien Recorder] update log reader stopped."
			self['title'].setText(_('Autocheck fertig !'))
			readLog = open(logFile, "r")
			for zeile in readLog.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					self.logliste.append((zeile.replace(_('[Serien Recorder]'),'')))
			readLog.close()
			self.chooseMenuList.setList(map(self.buildList, self.logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self['config'].moveToIndex(int(count-1))
			autoCheckFinished = False
		else:
			self.points += " ."
			self['title'].setText(_('Suche nach neuen Timern läuft.%s') % self.points)
					
	def buildList(self, entry):
		(zeile) = entry
		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 65, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def pageUp(self):
		self['config'].pageUp()

	def pageDown(self):
		self['config'].pageDown()
		
	def __onClose(self):
		print "[Serien Recorder] update log reader stopped."
		if self.readLogTimer:
			self.readLogTimer.stop()
			self.readLogTimer = None
			
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close(self.manuell)

		
#---------------------------------- Marker Functions ------------------------------------------

class serienRecMarker(Screen, HelpableScreen):
	def __init__(self, session, SelectSerie=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.SelectSerie = SelectSerie
		
		if not showMainScreen:
			self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
				"ok"       : (self.keyOK, _("zur Staffelauswahl")),
				"cancel"   : (self.keyCancel, _("SerienRecorder beenden")),
				"red"	   : (self.keyRed, _("umschalten ausgewählter Serien-Marker aktiviert/deaktiviert")),
				"red_long" : (self.keyRedLong, _("ausgewählten Serien-Marker löschen")),
				"green"    : (self.keyGreen, _("zur Senderauswahl")),
				"yellow"   : (self.keyYellow, _("Sendetermine für ausgewählte Serien anzeigen")),
				"blue"	   : (self.keyBlue, _("Serie manuell suchen")),
				"info"	   : (self.keyCheck, _("Suchlauf für Timer starten")),
				"left"     : (self.keyLeft, _("zur vorherigen Seite blättern")),
				"right"    : (self.keyRight, _("zur nächsten Seite blättern")),
				"up"       : (self.keyUp, _("eine Zeile nach oben")),
				"down"     : (self.keyDown, _("eine Zeile nach unten")),
				"menu"     : (self.markerSetup, _("Menü für Serien-Einstellungen öffnen")),
				"menu_long": (self.recSetup, _("Menü für globale Einstellungen öffnen")),
				"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
				"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
				"cancel_long" : (self.keyExit, _("zurück zur Serienplaner-Ansicht")),
				"0"		   : (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
				"1"		   : (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
				"3"		   : (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
				"4"		   : (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
				"6"		   : (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
				"7"		   : (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
			}, -1)
		else:
			self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
				"ok"       : (self.keyOK, _("zur Staffelauswahl")),
				"cancel"   : (self.keyCancel, _("zurück zur Serienplaner-Ansicht")),
				"red"	   : (self.keyRed, _("umschalten ausgewählter Serien-Marker aktiviert/deaktiviert")),
				"red_long" : (self.keyRedLong, _("ausgewählten Serien-Marker löschen")),
				"green"    : (self.keyGreen, _("zur Senderauswahl")),
				"yellow"   : (self.keyYellow, _("Sendetermine für ausgewählte Serien anzeigen")),
				"blue"	   : (self.keyBlue, _("Serie manuell suchen")),
				"info"	   : (self.keyCheck, _("Suchlauf für Timer starten")),
				"left"     : (self.keyLeft, _("zur vorherigen Seite blättern")),
				"right"    : (self.keyRight, _("zur nächsten Seite blättern")),
				"up"       : (self.keyUp, _("eine Zeile nach oben")),
				"down"     : (self.keyDown, _("eine Zeile nach unten")),
				"menu"     : (self.markerSetup, _("Menü für Serien-Einstellungen öffnen")),
				"menu_long": (self.recSetup, _("Menü für globale Einstellungen öffnen")),
				"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
				"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
				"cancel_long" : (self.keyExit, _("zurück zur Serienplaner-Ansicht")),
				"0"		   : (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
				"1"		   : (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
				"3"		   : (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
				"4"		   : (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
				"6"		   : (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
				"7"		   : (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
			}, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.modus = "config"
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
		
		self['text_green'].setText(_("Sender auswählen."))
		self['text_ok'].setText(_("Staffel(n) auswählen."))
		self['text_yellow'].setText(_("Sendetermine"))
		self['text_blue'].setText(_("Serie suchen"))
		self.num_bt_text[2][2] = _("Timer suchen")

		if longButtonText:
			self.num_bt_text[4][2] = _("Setup Serie (lang: global)")
			self['text_red'].setText(_("An/Aus (lang: Löschen)"))
			if not showMainScreen:
				self.num_bt_text[0][2] = _("Exit (lang: Serienplaner)")
		else:
			self.num_bt_text[4][2] = _("Setup Serie/global")
			self['text_red'].setText(_("(De)aktivieren/Löschen"))
			if not showMainScreen:
				self.num_bt_text[0][2] = _("Exit/Serienplaner")

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(70)
		self['config'] = self.chooseMenuList
		self['config'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['cover'].show()

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
		if self['config'].getCurrent() == None:
			return
		serien_name = self['config'].getCurrent()[0][0]
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

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def serieInfo(self):
		if self.loading:
			return

		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][0]
		serien_url = self['config'].getCurrent()[0][1]
		id = re.findall('epg_print.pl\?s=([0-9]+)', serien_url)
		if id:
			self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return

			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return

			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readSerienMarker()
				
	def getCover(self):
		if self.loading:
			return
		
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][0]
		self.serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name
		id = re.findall('epg_print.pl\?s=([0-9]+)', self['config'].getCurrent()[0][1])
		if id:
			id = "/%s" %  id[0]
		getCover(self, serien_name, id)

	def readSerienMarker(self):
		markerList = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials FROM SerienMarker ORDER BY Serie")
		cMarkerList = cCursor.fetchall()
		for row in cMarkerList:
			(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials) = row
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
				cStaffel = dbSerRec.cursor()
				cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
				cStaffelList = cStaffel.fetchall()
				if len(cStaffelList) > 0:
					staffeln = list(zip(*cStaffelList)[0])
					staffeln.sort()
				if AlleStaffelnAb < 999999:
					staffeln.append('ab %s' % AlleStaffelnAb)
				if AbEpisode > 0:
					staffeln.insert(0, '0 ab E%s' % AbEpisode)
				if bool(TimerForSpecials):
					staffeln.insert(0, 'Specials')
				cStaffel.close()
			
			if useAlternativeChannel == -1:
				useAlternativeChannel = config.plugins.serienRec.useAlternativeChannel.value
			
			SerieAktiviert = True
			cSerie = dbSerRec.cursor()
			cSerie.execute("SELECT ErlaubteSTB FROM STBAuswahl WHERE ID=?", (ID,))
			row2 = cSerie.fetchone()
			if row2:
				(ErlaubteSTB,) = row2
				if not (ErlaubteSTB & (1 << (int(config.plugins.serienRec.BoxID.value) - 1))):
					SerieAktiviert = False
			cSerie.close()
			
			staffeln = str(staffeln).replace("[","").replace("]","").replace("'","").replace('"',"")
			sender = str(sender).replace("[","").replace("]","").replace("'","").replace('"',"")
			markerList.append((Serie, Url, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, bool(useAlternativeChannel), SerieAktiviert))
				
		cCursor.close()
		self['title'].setText(_("Serien Marker - %s Serien vorgemerkt.") % len(markerList))
		if len(markerList) != 0:
			#markerList.sort()
			self.chooseMenuList.setList(map(self.buildList, markerList))
			if self.SelectSerie:
				try:
					idx = zip(*markerList)[0].index(self.SelectSerie)
					self['config'].moveToIndex(idx)
				except:
					pass
			self.loading = False
			self.getCover()

	def buildList(self, entry):
		(serie, url, staffeln, sendern, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel, SerieAktiviert) = entry
		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = config.plugins.serienRec.savetopath.value

		if not AnzahlAufnahmen:
			AnzahlAufnahmen = config.plugins.serienRec.NoOfRecords.value
		elif AnzahlAufnahmen < 1:
			AnzahlAufnahmen = 1
		
		if not Vorlaufzeit:
			Vorlaufzeit = config.plugins.serienRec.margin_before.value
		elif Vorlaufzeit < 0:
			Vorlaufzeit = 0
		
		if not Nachlaufzeit:
			Nachlaufzeit = config.plugins.serienRec.margin_after.value
		elif Nachlaufzeit < 0:
			Nachlaufzeit = 0
		
		if preferredChannel == 1:
			SenderText = _("Std.")
			if useAlternativeChannel:
				SenderText = _("%s, Alt.") % SenderText
		else:
			SenderText = _("Alt.")
			if useAlternativeChannel:
				SenderText = _("%s, Std.") % SenderText

		if SerieAktiviert:
			SerieColor = colorYellow
		else:
			SerieColor = colorRed

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 750, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, SerieColor, SerieColor),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Staffel: %s") % staffeln),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Sender (%s): %s") % (SenderText, sendern)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 49, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Wdh./Vorl./Nachl.: %s / %s / %s") % (int(AnzahlAufnahmen) - 1, int(Vorlaufzeit), int(Nachlaufzeit))),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 49, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Dir: %s") % AufnahmeVerzeichnis)
			]

	def keyCheck(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Marker leer."
			return

		if self.modus == "config":
			self.session.open(serienRecRunAutoCheck, True)

	def keyOK(self):
		if self.modus == "popup_list":
			self.select_serie = self['config'].getCurrent()[0][0]
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
			self.select_serie = self['config'].getCurrent()[0][0]
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
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return

			self.modus = "popup_list"
			self.select_serie = self['config'].getCurrent()[0][0]
			self['popup_list'].show()
			self['popup_bg'].show()
			
			staffeln = [_('Manuell'),_('Alle'),_('Specials'),_('folgende')]
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
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 4, 30, 17, loadPNG(imageMode)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 0, 500, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(staffel).zfill(2))
			]

	def keyGreen(self):
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return

			getSender = getWebSenderAktiv()
			if len(getSender) != 0:
				self.modus = "popup_list2"
				self['popup_list'].show()
				self['popup_bg'].show()
				self.select_serie = self['config'].getCurrent()[0][0]

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
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			serien_url = self['config'].getCurrent()[0][1]

			print "teestt"
			#serien_url = getUrl(serien_url.replace('epg_print.pl?s=',''))
			print serien_url
			#self.session.open(serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)
			self.session.openWithCallback(self.callTimerAdded, serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)

	def callSaveMsg(self, answer):
		if answer:
			self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Timer-Liste entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
		else:
			return

	def callDelMsg(self, answer):
		print self.selected_serien_name, answer
		self.removeSerienMarker(self.selected_serien_name, answer)
		
	def removeSerienMarker(self, serien_name, answer):
		cCursor = dbSerRec.cursor()
		if answer:
			print "[Serien Recorder] lösche %s aus der added liste" % serien_name
			cCursor.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=?", (serien_name.lower(),))
		cCursor.execute("DELETE FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (serien_name.lower(),))
		cCursor.execute("DELETE FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
		dbSerRec.commit()
		cCursor.close()
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText(_("Serie '- %s -' entfernt.") % serien_name)
		self.readSerienMarker()	
			
	def keyRed(self):
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['config'].getCurrent()[0][0]
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", (self.selected_serien_name.lower(),))
				row = cCursor.fetchone()
				if row:
					(ID, ErlaubteSTB) = row
					ErlaubteSTB ^= (1 << (int(config.plugins.serienRec.BoxID.value) - 1)) 
					cCursor.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=? WHERE ID=?", (ErlaubteSTB, ID))
					dbSerRec.commit()
					self.readSerienMarker()
				cCursor.close()
					
	def keyRedLong(self):
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['config'].getCurrent()[0][0]
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.selected_serien_name.lower(),))
				row = cCursor.fetchone()
				if row:
					print "gefunden."
					if config.plugins.serienRec.confirmOnDelete.value:
						self.session.openWithCallback(self.callSaveMsg, MessageBox, _("Soll '%s' wirklich entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
					else:
						self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Timer-Liste entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
				cCursor.close()

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
		if self.modus == "config":
			self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Serien Titel eingeben:")), text = "")

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
			self.modus = "config"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			if (self.staffel_liste[0][1] == 0) and (self.staffel_liste[1][1] == 0) and (self.staffel_liste[4][1] == 1):		# nicht ('Manuell' oder 'Alle') und '00'
				self.session.openWithCallback(self.selectEpisode, VirtualKeyBoard, title = (_("Episode eingeben ab der Timer erstellt werden sollen:")), text = str(self.AbEpisode))
			else:
				self.insertStaffelMarker()
		elif self.modus == "popup_list2":
			self.modus = "config"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.insertSenderMarker()
		else:
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)

	def dataError(self, error):
		print error

class serienRecAddSerie(Screen, HelpableScreen):
	def __init__(self, session, serien_name):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("Marker für ausgewählte Serie hinzufügen")),
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("zurück zur vorherigen Ansicht")),
			"blue"  : (self.keyBlue, _("Serie manuell suchen")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
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

		self['text_red'].setText(_("Abbrechen"))
		self['text_ok'].setText(_("Hinzufügen"))
		self['text_blue'].setText(_("Serie Suchen"))

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['cover'].show()

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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.loading:
			return

		check = self['config'].getCurrent()
		if check == None:
			return

		serien_id = self['config'].getCurrent()[0][2]
		serien_name = self['config'].getCurrent()[0][0]

		self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % serien_id)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return
				
			check = self['config'].getCurrent()
			if check == None:
				return
				
			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.searchSerie()
				
	def searchSerie(self):
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText(_("Suche nach ' %s '") % self.serien_name)
		self['title'].instance.setForegroundColor(parseColor("white"))
		url = "http://www.wunschliste.de/ajax/search_dropdown.pl?%s" % urlencode({'q': self.serien_name})
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.results).addErrback(self.dataError)

	def results(self, data):
		self.serienlist = []
		first = False
		count_lines = len(data.splitlines())
		if count_lines == 1:
			print "[Serien Recorder] only one hit for ' %s '" % self.serien_name
			first = True

		if int(count_lines) >= 1:
			for line in data.splitlines():
				infos = line.split('|')
				if len(infos) == 3:
					(name_Serie, year_Serie, id_Serie) = infos
					# encode utf-8
					name_Serie = iso8859_Decode(name_Serie)
					raw = re.findall('(.*?)(\[%s\])?\Z' % self.serien_name, name_Serie, re.I | re.S)
					if raw:
						(name_Serie, x) = raw
						self.serienlist.append((name_Serie[0], year_Serie, id_Serie))
					else:
						self.serienlist.append((name_Serie, year_Serie, id_Serie))
		else:
			print "[Serien Recorder] keine Sendetermine für ' %s ' gefunden." % self.serien_name

		self.chooseMenuList.setList(map(self.buildList, self.serienlist))
		self['title'].setText(_("Die Suche für ' %s ' ergab %s Teffer.") % (self.serien_name, str(len(self.serienlist))))
		self['title'].instance.setForegroundColor(parseColor("white"))
		self.loading = False
		self.getCover()

	def buildList(self, entry):
		(name_Serie, year_Serie, id_Serie) = entry

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name_Serie),
			(eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, year_Serie)
			]

	def keyOK(self):
		if self.loading:
			return

		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] keine infos gefunden"
			return

		Serie = self['config'].getCurrent()[0][0]
		Year = self['config'].getCurrent()[0][1]
		Id = self['config'].getCurrent()[0][2]
		print Serie, Year, Id

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(),))
		row = cCursor.fetchone()	
		if not row:
			Url = 'http://www.wunschliste.de/epg_print.pl?s='+str(Id)
			if config.plugins.serienRec.defaultStaffel.value == "0":
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (Serie, Url))
			else:
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, -2, 1, 1, -1, 0, -1, 0)", (Serie, Url))
			cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (cCursor.lastrowid, 0xFFFF))
			dbSerRec.commit()
			cCursor.close()
			self['title'].setText(_("Serie '- %s -' zum Serien Marker hinzugefügt.") % Serie)
			self['title'].instance.setForegroundColor(parseColor("green"))
			if config.plugins.serienRec.openMarkerScreen.value:
				self.session.open(serienRecMarker, Serie)
		else:
			self['title'].setText(_("Serie '- %s -' existiert bereits im Serien Marker.") % Serie)
			self['title'].instance.setForegroundColor(parseColor("red"))
			cCursor.close()

	def keyRed(self):
		self.close()

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Serien Titel eingeben:")), text = "")

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.chooseMenuList.setList(map(self.buildList, []))
			self['title'].setText("")
			self['title'].instance.setForegroundColor(parseColor("white"))
			self.serien_name = serien_name
			self.searchSerie()

	def keyLeft(self):
		self['config'].pageUp()
		self.getCover()

	def keyRight(self):
		self['config'].pageDown()
		self.getCover()

	def keyDown(self):
		self['config'].down()
		self.getCover()

	def keyUp(self):
		self['config'].up()
		self.getCover()

	def getCover(self):
		if self.loading:
			return
		
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][0]
		id = "/%s" % self['config'].getCurrent()[0][2]
		getCover(self, serien_name, id)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self['title'].instance.setForegroundColor(parseColor("white"))
		self.close()

	def dataError(self, error):
		print error

class serienRecSendeTermine(Screen, HelpableScreen):
	def __init__(self, session, serien_name, serie_url, serien_cover):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serie_url = serie_url
		self.serien_cover = serien_cover

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("umschalten ausgewählter Sendetermin aktiviert/deaktiviert")),
			"cancel": (self.keyCancel, _("zurück zur Serien-Marker-Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("zurück zur Serien-Marker-Ansicht")),
			"green" : (self.keyGreen, _("Timer für aktivierte Sendetermine erstellen")),
			"yellow": (self.keyYellow, _("umschalten Filter (aktive Sender) aktiviert/deaktiviert")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.FilterEnabled = True
		self.changesMade = False
		
		self.setupSkin()
		
		self.sendetermine_list = []
		self.loading = True
		
		self.onLayoutFinish.append(self.searchSerie)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText(_("Abbrechen"))
		self['text_ok'].setText(_("Auswahl"))
		if self.FilterEnabled:
			self['text_yellow'].setText(_("Filter ausschalten"))
			self.title_txt = _("gefiltert")
		else:
			self['text_yellow'].setText(_("Filter einschalten"))
			self.title_txt = _("alle")

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(50)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['title'].setText(_("Lade Web-Channel / STB-Channels..."))

		self['cover'].show()

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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.loading:
			return

		id = re.findall('epg_print.pl\?s=([0-9]+)', self.serie_url)
		if id:
			self.session.open(serienRecShowInfo, self.serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return
				
			print "[Serien Recorder] starte youtube suche für %s" % self.serien_name
			self.session.open(searchYouTube, self.serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			print "[Serien Recorder] starte Wikipedia Suche für %s" % self.serien_name
			self.session.open(wikiSearch, self.serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.searchSerie()
				
	def searchSerie(self):
		if not self.serien_cover == "nix":
			showCover(self.serien_cover, self, self.serien_cover)
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText(_("Suche ' %s '") % self.serien_name)
		print self.serie_url
		getPage(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.resultsTermine, self.serien_name).addErrback(self.dataError)

	def resultsTermine(self, data, serien_name):
		parsingOK = False
		self.sendetermine_list = []

		raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		
		raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(.*?x))(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])
		if raw:
			parsingOK = True

		if parsingOK:
			def y(l):
				(day, month) = l[1].split('.')
				(start_hour, start_min) = l[2].split('.')
				now = datetime.datetime.now()
				if int(month) < now.month:
					now.year += 1
				return time.mktime((now.year, int(month), int(day), int(start_hour), int(start_min), 0, 0, 0, 0))		
			raw.sort(key=y)
		
			for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
				# umlaute umwandeln
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				title = iso8859_Decode(title)
				staffel = iso8859_Decode(staffel)

				if self.FilterEnabled:
					# filter sender
					cSender_list = self.checkSender(sender)
					if len(cSender_list) == 0:
						webChannel = sender
						stbChannel = ""
						altstbChannel = ""
					else:
						(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSender_list[0]

					if stbChannel == "":
						print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel)
						continue
						
					if int(status) == 0:
						print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel)
						continue
					
				self.sendetermine_list.append([serien_name, sender, datum, startzeit, endzeit, staffel, str(episode).zfill(2), title, "0"])

			self['text_green'].setText(_("Timer erstellen"))
			
		self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))
		self.loading = False
		self['title'].setText(_("%s Sendetermine für ' %s ' gefunden. (%s)") % (str(len(self.sendetermine_list)), self.serien_name, self.title_txt))

	def buildList_termine(self, entry):
		#(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry
		(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry

		seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
		(dirname, dirname_serie) = getDirname(serien_name, staffel)
		
		imageMinus = "%simages/minus.png" % serienRecMainPath
		imagePlus = "%simages/plus.png" % serienRecMainPath
		imageNone = "%simages/black.png" % serienRecMainPath
		imageHDD = "%simages/hdd.png" % serienRecMainPath
		imageTimer = "%simages/timerlist.png" % serienRecMainPath
		imageAdded = "%simages/added.png" % serienRecMainPath

		rightImage = imageNone

		#check 1 (hdd)
		bereits_vorhanden = countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, True) and True or False
		if bereits_vorhanden:
			rightImage = imageHDD
		else:
			(margin_before, margin_after) = getMargins(serien_name, sender)

			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = start.split('.')

			# check 2 (im timer file)
			start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			if checkTimerAdded(sender, serien_name, staffel, episode, int(start_unixtime)):
				rightImage = imageTimer
			else:
				# check 2 (im added file)
				if checkAlreadyAdded(serien_name, staffel, episode):
					rightImage = imageAdded
				else:
					rightImage = imageNone

		if int(status) == 0:
			leftImage = imageMinus
		else:
			leftImage = imagePlus
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 15, 16, 16, loadPNG(leftImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
			(eListboxPythonMultiContent.TYPE_TEXT, 40, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s %s" % (datum, start), colorYellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s - %s" % (seasonEpisodeString, title), colorYellow),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, loadPNG(rightImage))
			]

	def getTimes(self):
		changesMade = False
		self.countTimer = 0
		if len(self.sendetermine_list) != 0:
			lt = time.localtime()
			self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
			print "\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------") % self.uhrzeit, True)
			for serien_name, sender, datum, startzeit, endzeit, staffel, episode, title, status in self.sendetermine_list:
				if int(status) == 1:
					# initialize strings
					seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))
					label_serie = "%s - %s - %s" % (serien_name, seasonEpisodeString, title)
					
					# formatiere start/end-zeit
					(day, month) = datum.split('.')
					(start_hour, start_min) = startzeit.split('.')
					(end_hour, end_min) = endzeit.split('.')

					start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)

					if int(start_hour) > int(end_hour):
						end_unixtime = getNextDayUnixtime(end_min, end_hour, day, month)
					else:
						end_unixtime = getUnixTimeAll(end_min, end_hour, day, month)

					# setze die vorlauf/nachlauf-zeit
					(margin_before, margin_after) = getMargins(serien_name, sender)
					start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
					end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

					# get VPS settings for channel
					vpsSettings = getVPS(sender)

					# überprüft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert

					#check 1 (hdd)
					(dirname, dirname_serie) = getDirname(serien_name, staffel)
					bereits_vorhanden = countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, False)
					bereits_vorhanden += checkAlreadyAdded(serien_name, staffel, episode)
					
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

					params = (serien_name, sender, startzeit, start_unixtime, margin_before, margin_after, end_unixtime, label_serie, staffel, episode, title, dirname, preferredChannel, bool(useAlternativeChannel), vpsSettings)
					if bereits_vorhanden < NoOfRecords:
						TimerDone = self.doTimer(params)
					else:
						writeLog(_("[Serien Recorder] Serie ' %s ' -> Staffel/Episode bereits vorhanden ' %s '") % (serien_name, seasonEpisodeString))
						TimerDone = self.doTimer(params, config.plugins.serienRec.forceManualRecording.value)
					if TimerDone:
						# erstellt das serien verzeichnis
						CreateDirectory(serien_name, staffel)

			writeLog(_("[Serien Recorder] Es wurde(n) %s Timer erstellt.") % str(self.countTimer), True)
			print "[Serien Recorder] Es wurde(n) %s Timer erstellt." % str(self.countTimer)
			writeLog(_("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"), True)
			print "---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"
			#self.session.open(serienRecRunAutoCheck, False)
			self.session.open(serienRecReadLog)
			if self.countTimer:
				changesMade = True

		else:
			self['title'].setText(_("Keine Sendetermine ausgewählt."))
			print "[Serien Recorder] keine Sendetermine ausgewählt."
			
		return changesMade

	def doTimer(self, params, answer=True):
		if not answer:
			return False
		else:
			(serien_name, sender, startzeit, start_unixtime, margin_before, margin_after, end_unixtime, label_serie, staffel, episode, title, dirname, preferredChannel, useAlternativeChannel, vpsSettings) = params
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
				writeLog(_("[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '") % (serien_name, webChannel))
			elif int(status) == 0:
				writeLog(_("[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '") % (serien_name, webChannel))
			else:
				if config.plugins.serienRec.TimerName.value == "0":
					timer_name = label_serie
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
				eit, end_unixtime_eit, start_unixtime_eit = getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, timer_stbRef)
				seasonEpisodeString = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

				# versuche timer anzulegen
				if checkTuner(start_unixtime_eit, end_unixtime_eit):
					result = serienRecAddTimer.addTimer(self.session, timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), eit, False, dirname, vpsSettings, None, recordfile=".ts")
					if result["result"]:
						if self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit):
							self.countTimer += 1
							TimerOK = True
					else:
						konflikt = result["message"]
				else:
					print "[Serien Recorder] Tuner belegt: %s %s" % (label_serie, startzeit)
					writeLog(_("[Serien Recorder] Tuner belegt: %s %s") % (label_serie, startzeit), True)

				if (not TimerOK) and (useAlternativeChannel):
					# try to get eventID (eit) from epgCache
					alt_eit, alt_end_unixtime_eit, alt_start_unixtime_eit = getStartEndTimeFromEPG(start_unixtime, end_unixtime, margin_before, margin_after, serien_name, timer_altstbRef)
					# versuche timer anzulegen
					if checkTuner(alt_start_unixtime_eit, alt_end_unixtime_eit):
						result = serienRecAddTimer.addTimer(self.session, timer_altstbRef, str(alt_start_unixtime_eit), str(alt_end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), alt_eit, False, dirname, vpsSettings, None, recordfile=".ts")
						if result["result"]:
							if self.addRecTimer(serien_name, staffel, episode, title, str(alt_start_unixtime_eit), timer_altstbRef, webChannel, alt_eit):
								self.countTimer += 1
								TimerOK = True
						else:
							konflikt = result["message"]
							writeLog(_("[Serien Recorder] ' %s ' - ACHTUNG! -> %s") % (label_serie, konflikt), True)
							result = serienRecAddTimer.addTimer(self.session, timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), timer_name, "%s - %s" % (seasonEpisodeString, title), eit, True, dirname, vpsSettings, None, recordfile=".ts")
							if result["result"]:
								if self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit, False):
									self.countTimer += 1
									TimerOK = True
					else:
						print "[Serien Recorder] Tuner belegt: %s %s" % (label_serie, startzeit)
						writeLog(_("[Serien Recorder] Tuner belegt: %s %s") % (label_serie, startzeit), True)
			return TimerOK
			
	def keyOK(self):
		if self.loading:
			return

		check = self['config'].getCurrent()
		if check == None:
			return

		sindex = self['config'].getSelectedIndex()
		if len(self.sendetermine_list) != 0:
			if int(self.sendetermine_list[sindex][8]) == 0:
				self.sendetermine_list[sindex][8] = "1"
			else:
				self.sendetermine_list[sindex][8] = "0"
			self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))

	def keyLeft(self):
		self['config'].pageUp()

	def keyRight(self):
		self['config'].pageDown()

	def keyDown(self):
		self['config'].down()

	def keyUp(self):
		self['config'].up()

	def checkSender(self, mSender):
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (mSender.lower(),))
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
			print "[Serien Recorder] Timer bereits vorhanden: %s %s - %s" % (serien_name, seasonEpisodeString, title)
			writeLog(_("[Serien Recorder] Timer bereits vorhanden: %s %s - %s") % (serien_name, seasonEpisodeString, title))
			result = True
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit, TimerAktiviert))
			dbSerRec.commit()
			print "[Serien Recorder] Timer angelegt: %s %s - %s" % (serien_name, seasonEpisodeString, title)
			writeLog(_("[Serien Recorder] Timer angelegt: %s %s - %s") % (serien_name, seasonEpisodeString, title))
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
			self.searchSerie()
			
	def keyYellow(self):
		self['text_red'].setText("")
		self['text_green'].setText("")
		self['text_yellow'].setText("")

		self.sendetermine_list = []
		self.loading = True
		self.chooseMenuList.setList(map(self.buildList_termine, self.sendetermine_list))

		if self.FilterEnabled:
			self.FilterEnabled = False
			self['text_yellow'].setText(_("Filter einschalten"))
			self.title_txt = _("alle")
		else:
			self.FilterEnabled = True
			self['text_yellow'].setText(_("Filter ausschalten"))
			self.title_txt = _("gefiltert")
			
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText(_("Suche ' %s '") % self.serien_name)
		print self.serie_url
		getPage(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.resultsTermine, self.serien_name).addErrback(self.dataError)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if config.plugins.serienRec.refreshViews.value:
			self.close(self.changesMade)
		else:
			self.close(False)

	def dataError(self, error):
		print error


#---------------------------------- Channel Functions ------------------------------------------

class serienRecMainChannelEdit(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"       : (self.keyOK, _("Popup-Fenster zur Auswahl des STB-Channels öffnen")),
			"cancel"   : (self.keyCancel, _("zurück zur Serienplaner-Ansicht")),
			"red"	   : (self.keyRed, _("umschalten ausgewählter Sender für Timererstellung aktiviert/deaktiviert")),
			"red_long" : (self.keyRedLong, _("ausgewählten Sender aus der Channelliste endgültig löschen")),
			"green"    : (self.keyGreen, _("Channel-Zuordnung zurücksetzen")),
			"menu"     : (self.channelSetup, _("Menü für Sender-Einstellungen öffnen")),
			"menu_long": (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"left"     : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right"    : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"       : (self.keyUp, _("eine Zeile nach oben")),
			"down"     : (self.keyDown, _("eine Zeile nach unten")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zum ausgewählten Sender auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zum ausgewählten Sender auf Wikipedia suchen")),
			"0"		   : (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		   : (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		   : (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"6"		   : (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		   : (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.modus = "list"
		self.changesMade = False
		
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if row:
			cCursor.close()
			self.onLayoutFinish.append(self.showChannels)
		else:
			cCursor.close()
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = buildSTBchannellist(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = buildSTBchannellist()
			self.onLayoutFinish.append(self.readWebChannels)

		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_green'].setText(_("Reset Senderliste"))
		self['text_ok'].setText(_("Sender auswählen"))

		self.num_bt_text[4][0] = buttonText_na
		if longButtonText:
			self['text_red'].setText(_("An/Aus (lang: Löschen)"))
			self.num_bt_text[4][2] = _("Setup Sender (lang: global)")
		else:
			self['text_red'].setText(_("(De)aktivieren/Löschen"))
			self.num_bt_text[4][2] = _("Setup Sender/global")

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['list'].show()
		
		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		# popup2
		self.chooseMenuList_popup2 = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup2.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup2.l.setItemHeight(25)
		self['popup_list2'] = self.chooseMenuList_popup2
		self['popup_list2'].hide()

		self['title'].setText(_("Lade Web-Channel / STB-Channels..."))

		self['Web_Channel'].setText(_("Web-Channel"))
		self['STB_Channel'].setText(_("STB-Channel"))
		self['alt_STB_Channel'].setText(_("alt. STB-Channel"))

		self['Web_Channel'].show()
		self['STB_Channel'].show()
		self['alt_STB_Channel'].show()
		self['separator'].show()
		
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()
			
	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def channelSetup(self):
		webSender = self['list'].getCurrent()[0][0]
		self.session.open(serienRecChannelSetup, webSender)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			check = self['list'].getCurrent()
			if check == None:
				return

			sender_name = self['list'].getCurrent()[0][0]
			self.session.open(searchYouTube, sender_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			check = self['list'].getCurrent()
			if check == None:
				return

			sender_name = self['list'].getCurrent()[0][0]
			self.session.open(wikiSearch, sender_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.showChannels()
				
	def showChannels(self):
		self.serienRecChlist = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels ORDER BY LOWER(WebChannel)")
		for row in cCursor:
			(webSender, servicename, serviceref, altservicename, altserviceref, status) = row
			self.serienRecChlist.append((webSender, servicename, altservicename, status))

		if len(self.serienRecChlist) != 0:
			self['title'].setText(_("Channel-Zuordnung"))
			self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
		else:
			print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."
		cCursor.close()
		
	def readWebChannels(self):
		print "[SerienRecorder] call webpage.."
		self['title'].setText(_("Lade Web-Channels..."))
		url = "http://www.wunschliste.de/updates/stationen"
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.createWebChannels).addErrback(self.dataError)
		
	def createWebChannels(self, data):
		print "[SerienRecorder] get webchannels.."
		self['title'].setText(_("Lade Web-Channels..."))
		stations = re.findall('<option value=".*?>(.*?)</option>', data, re.S)
		if stations:
			web_chlist = []
			for station in stations:
				if station != 'alle':
					station = iso8859_Decode(station)
					web_chlist.append((station.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')))

			web_chlist.sort(key=lambda x: x.lower())
			print web_chlist
			self.serienRecChlist = []
			if len(web_chlist) != 0:
				self['title'].setText(_("erstelle Channels-List..."))
				cCursor = dbSerRec.cursor()
				sql = "INSERT OR IGNORE INTO Channels (WebChannel, STBChannel, ServiceRef, Erlaubt) VALUES (?, ?, ?, ?)"
				for webSender in web_chlist:
					cCursor.execute("SELECT * FROM Channels WHERE LOWER(WebChannel)=?", (webSender.lower(),))
					row = cCursor.fetchone()
					if not row:
						found = False
						for servicename,serviceref in self.stbChlist:
							#if re.search(webSender.lower(), servicename.lower(), re.S):
							if re.search("\A%s\Z" % webSender.lower().replace('+','\+').replace('.','\.'), servicename.lower(), re.S):
								cCursor.execute(sql, (webSender, servicename, serviceref, 1))
								self.serienRecChlist.append((webSender, servicename, "", "1"))
								found = True
								break
						if not found:
							cCursor.execute(sql, (webSender, "", "", 0))
							self.serienRecChlist.append((webSender, "", "", "0"))
						self.changesMade = True
						global runAutocheckAtExit
						runAutocheckAtExit = True
				dbSerRec.commit()
				cCursor.close()
			else:
				print "[SerienRecorder] webChannel list leer.."

			if len(self.serienRecChlist) != 0:
				self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
			else:
				print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."

		else:
			print "[SerienRecorder] get webChannel error.."
			
		self['title'].setText(_("Web-Channel / STB-Channels."))

	def buildList(self, entry):
		(webSender, stbSender, altstbSender, status) = entry
		if int(status) == 0:		
			imageStatus = "%simages/minus.png" % serienRecMainPath
		else:
			imageStatus = "%simages/plus.png" % serienRecMainPath
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 8, 16, 16, loadPNG(imageStatus)),
			(eListboxPythonMultiContent.TYPE_TEXT, 35, 3, 300, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 350, 3, 250, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 600, 3, 250, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, altstbSender, colorYellow)
			]

	def buildList_popup(self, entry):
		(servicename,serviceref) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 250, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, servicename)
			]

	def keyOK(self):
		if self.modus == "list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = buildSTBchannellist(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = buildSTBchannellist()
			self.stbChlist.insert(0, ("", ""))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.stbChlist))
			idx = 0
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE LOWER(WebChannel)=?", (self['list'].getCurrent()[0][0].lower(),))
			row = cCursor.fetchone()
			if row:
				(stbChannel, altstbChannel) = row
				if stbChannel:
					try:
						idx = zip(*self.stbChlist)[0].index(stbChannel)
					except:
						pass
			cCursor.close()
			self['popup_list'].moveToIndex(idx)
			self['title'].setText(_("Standard STB-Channel für %s:") % self['list'].getCurrent()[0][0])
		elif config.plugins.serienRec.selectBouquets.value:
			if self.modus == "popup_list":
				self.modus = "popup_list2"
				self['popup_list'].hide()
				self['popup_list2'].show()
				self['popup_bg'].show()
				self.stbChlist = buildSTBchannellist(config.plugins.serienRec.AlternativeBouquet.value)
				self.stbChlist.insert(0, ("", ""))
				self.chooseMenuList_popup2.setList(map(self.buildList_popup, self.stbChlist))
				idx = 0
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE LOWER(WebChannel)=?", (self['list'].getCurrent()[0][0].lower(),))
				row = cCursor.fetchone()
				if row:
					(stbChannel, altstbChannel) = row
					if stbChannel:
						try:
							idx = zip(*self.stbChlist)[0].index(altstbChannel)
						except:
							pass
				cCursor.close()
				self['popup_list2'].moveToIndex(idx)
				self['title'].setText(_("alternativer STB-Channels für %s:") % self['list'].getCurrent()[0][0])
			else:
				self.modus = "list"
				self['popup_list'].hide()
				self['popup_list2'].hide()
				self['popup_bg'].hide()

				check = self['list'].getCurrent()
				if check == None:
					print "[Serien Recorder] Channel-List leer (list)."
					return

				check = self['popup_list'].getCurrent()
				if check == None:
					print "[Serien Recorder] Channel-List leer (popup_list)."
					return

				chlistSender = self['list'].getCurrent()[0][0]
				stbSender = self['popup_list'].getCurrent()[0][0]
				stbRef = self['popup_list'].getCurrent()[0][1]
				altstbSender = self['popup_list2'].getCurrent()[0][0]
				altstbRef = self['popup_list2'].getCurrent()[0][1]
				print "[SerienRecorder] select:", chlistSender, stbSender, stbRef, altstbSender, altstbRef
				cCursor = dbSerRec.cursor()
				sql = "UPDATE OR IGNORE Channels SET STBChannel=?, ServiceRef=?, alternativSTBChannel=?, alternativServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?"
				if stbSender != "" or altstbSender != "":
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 1, chlistSender.lower()))
				else:
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 0, chlistSender.lower()))
				self.changesMade = True
				global runAutocheckAtExit
				runAutocheckAtExit = True
				dbSerRec.commit()
				cCursor.close()
				self['title'].setText(_("Channel-Zuordnung"))
				self.showChannels()
		else:
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_list2'].hide()
			self['popup_bg'].hide()

			if self['list'].getCurrent() == None:
				print "[Serien Recorder] Channel-List leer (list)."
				return

			if self['popup_list'].getCurrent() == None:
				print "[Serien Recorder] Channel-List leer (popup_list)."
				return

			chlistSender = self['list'].getCurrent()[0][0]
			stbSender = self['popup_list'].getCurrent()[0][0]
			stbRef = self['popup_list'].getCurrent()[0][1]
			print "[SerienRecorder] select:", chlistSender, stbSender, stbRef
			cCursor = dbSerRec.cursor()
			sql = "UPDATE OR IGNORE Channels SET STBChannel=?, ServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?"
			if stbSender != "":
				cCursor.execute(sql, (stbSender, stbRef, 1, chlistSender.lower()))
			else:
				cCursor.execute(sql, (stbSender, stbRef, 0, chlistSender.lower()))
			self.changesMade = True
			global runAutocheckAtExit
			runAutocheckAtExit = True
			dbSerRec.commit()
			cCursor.close()
			self['title'].setText(_("Channel-Zuordnung"))
			self.showChannels()
				
	def keyRed(self):
		if self['list'].getCurrent() == None:
			print "[Serien Recorder] Channel-List leer."
			return

		if self.modus == "list":
			chlistSender = self['list'].getCurrent()[0][0]
			sender_status = self['list'].getCurrent()[0][2]
			print sender_status

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (chlistSender.lower(),))
			row = cCursor.fetchone()
			if row:
				(webSender, servicename, serviceref, status) = row
				sql = "UPDATE OR IGNORE Channels SET Erlaubt=? WHERE LOWER(WebChannel)=?"
				if int(status) == 0:
					cCursor.execute(sql, (1, chlistSender.lower()))
					print "[SerienRecorder] change to:", webSender, servicename, serviceref, "1"
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("")
					self['title'].setText(_("Sender '- %s -' wurde aktiviert.") % webSender)
				else:
					cCursor.execute(sql, (0, chlistSender.lower()))
					print "[SerienRecorder] change to:",webSender, servicename, serviceref, "0"
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("")
					self['title'].setText(_("Sender '- %s -' wurde deaktiviert.") % webSender)
				self.changesMade = True
				global runAutocheckAtExit
				runAutocheckAtExit = True
				dbSerRec.commit()
				
			cCursor.close()	
			self['title'].instance.setForegroundColor(parseColor("white"))
			self.showChannels()

	def keyGreen(self):
		self.session.openWithCallback(self.channelReset, MessageBox, _("Sender-Liste zurücksetzen ?"), MessageBox.TYPE_YESNO)

	def channelReset(self, answer):
		if answer:
			print "[Serien Recorder] channel-list reset..."

			if config.plugins.serienRec.selectBouquets.value:
				self.stbChlist = buildSTBchannellist(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChlist = buildSTBchannellist()
			self.readWebChannels()
		else:
			print "[Serien Recorder] channel-list ok."

	def keyRedLong(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Marker leer."
			return
		else:
			self.selected_sender = self['list'].getCurrent()[0][0]
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM Channels WHERE LOWER(WebChannel)=?", (self.selected_sender.lower(),))
			row = cCursor.fetchone()
			if row:
				print "gefunden."
				if config.plugins.serienRec.confirmOnDelete.value:
					self.session.openWithCallback(self.channelDelete, MessageBox, _("Soll '%s' wirklich entfernt werden?") % self.selected_sender, MessageBox.TYPE_YESNO, default = False)
				else:
					self.channelDelete(True)
			cCursor.close()

	def channelDelete(self, answer):
		if not answer:
			return
		cCursor = dbSerRec.cursor()
		cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE LOWER(Sender)=?", (self.selected_sender.lower(),))
		cCursor.execute("DELETE FROM SenderAuswahl WHERE LOWER(ErlaubterSender)=?", (self.selected_sender.lower(),))
		cCursor.execute("DELETE FROM Channels WHERE LOWER(WebChannel)=?", (self.selected_sender.lower(),))
		dbSerRec.commit()
		cCursor.close()
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText(_("Sender '- %s -' entfernt.") % self.selected_sender)
		self.showChannels()	
			
	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list2'].hide()
			self['popup_bg'].hide()
		else:
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)
			
	def dataError(self, error):
		print error

		
#---------------------------------- Setup Functions ------------------------------------------

class serienRecSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, readConfig=False):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"	: (self.keyOK, _("Fenster für Verzeichnisauswahl öffnen")),
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"red"	: (self.keyRed, _("alle Einstellungen auf die Standardwerte zurücksetzen")),
			"green"	: (self.save, _("Einstellungen speichern und zurück zur vorherigen Ansicht")),
			"yellow": (self.keyYellow, _("Einstellungen in Datei speichern")),
			"blue"  : (self.keyBlue, _("Einstellungen aus Datei laden")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			#"deleteForward" : (self.keyDelForward, _("---")),
			#"deleteBackward": (self.keyDelBackward, _("---")),
			"nextBouquet":	(self.bouquetPlus, _("zur vorherigen Seite blättern")),
			"prevBouquet":	(self.bouquetMinus, _("zur nächsten Seite blättern")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		if readConfig:
			ReadConfigFile()
			
		self.setupSkin()
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
		self.kindOfTimer = ConfigSelection(choices = [("1", _("umschalten")), ("0", _("aufnehmen")), ("2", _("umschalten und aufnehmen")), ("4", _("Erinnerung"))], default=str(kindOfTimer_default))

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[config.plugins.serienRec.BoxID])
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

		self['title'].setText(_("Serien Recorder - Einstellungen:"))
		self['text_red'].setText(_("Defaultwerte"))
		self['text_green'].setText(_("Speichern"))
		self['text_ok'].setText(_("Verzeichnis auswählen"))
		self['text_yellow'].setText(_("in Datei speichern"))
		self['text_blue'].setText(_("aus Datei laden"))

		self['config_information'].show()
		self['config_information_text'].show()

		if not showAllButtons:
			self['text_0'].setText(_("Abbrechen"))
			self['text_1'].setText(_("About"))

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
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, _("Abbrechen")],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, _("Hilfe")],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def keyRed(self):
		self.session.openWithCallback(self.resetSettings, MessageBox, _("Wollen Sie die Einstellungen wirklich zurücksetzen?"), MessageBox.TYPE_YESNO, default = False)

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
		writeConfFile = open("%sConfig.backup" % serienRecMainPath, "w")
		readSettings = open("/etc/enigma2/settings", "r")
		for rawData in readSettings.readlines():
			data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
			if data:
				writeConfFile.write(rawData)
		writeConfFile.close()
		readSettings.close()
		self.session.open(MessageBox, _("Die aktuelle Konfiguration wurde in der Datei 'Config.backup' \nim Verzeichnis '%s' gespeichert.") % serienRecMainPath, MessageBox.TYPE_INFO, timeout = 10)
		
	def keyBlue(self):
		self.session.openWithCallback(self.importSettings, MessageBox, _("Die Konfiguration aus der Datei 'Config.backup' \nim Verzeichnis '%s' wird geladen.") % serienRecMainPath, MessageBox.TYPE_YESNO, default = False)
		
	def importSettings(self, answer=False):
		if answer:
			writeSettings = open("/etc/enigma2/settings_new", "w")
			
			readSettings = open("/etc/enigma2/settings", "r")
			for rawData in readSettings.readlines():
				data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
				if not data:
					writeSettings.write(rawData)

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
			#self.save()
		
	#def keyDelForward(self):
	#	self.changedEntry()

	#def keyDelBackward(self):
	#	self.changedEntry()

	def bouquetPlus(self):
		self['config'].instance.moveSelection(self['config'].instance.pageUp)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def bouquetMinus(self):
		self['config'].instance.moveSelection(self['config'].instance.pageDown)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyDown(self):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.updateInterval:
			self.changedEntry()
			
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyUp(self):
		if self['config'].getCurrent()[1] == config.plugins.serienRec.updateInterval:
			self.changedEntry()
			
		if self['config'].instance.getCurrentIndex() <= 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)
		
		if self['config'].getCurrent()[1] in (config.plugins.serienRec.savetopath, config.plugins.serienRec.LogFilePath, config.plugins.serienRec.BackupPath, config.plugins.serienRec.databasePath):
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.changedEntry()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.changedEntry()

	def createConfigList(self):
		self.list = []
		self.list.append(getConfigListEntry(_("---------  SYSTEM:  -------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("ID der Box:"), config.plugins.serienRec.BoxID))
		self.list.append(getConfigListEntry(_("Speicherort der Aufnahmen:"), config.plugins.serienRec.savetopath))
		self.list.append(getConfigListEntry(_("Serien-Verzeichnis anlegen:"), config.plugins.serienRec.seriensubdir))
		self.list.append(getConfigListEntry(_("Staffel-Verzeichnis anlegen:"), config.plugins.serienRec.seasonsubdir))
		if config.plugins.serienRec.seasonsubdir.value:
			self.list.append(getConfigListEntry(_("    Mindestlänge der Staffelnummer im Verzeichnisnamen:"), config.plugins.serienRec.seasonsubdirnumerlength))
			self.list.append(getConfigListEntry(_("    Füllzeichen für Staffelnummer im Verzeichnisnamen:"), config.plugins.serienRec.seasonsubdirfillchar))
		self.list.append(getConfigListEntry(_("Anzahl gleichzeitiger Web-Anfragen:"), config.plugins.serienRec.maxWebRequests))
		self.list.append(getConfigListEntry(_("Automatisches Plugin-Update:"), config.plugins.serienRec.Autoupdate))
		self.list.append(getConfigListEntry(_("Speicherort der Datenbank:"), config.plugins.serienRec.databasePath))
		self.list.append(getConfigListEntry(_("Erstelle Backup vor Suchlauf:"), config.plugins.serienRec.AutoBackup))
		if config.plugins.serienRec.AutoBackup.value:
			self.list.append(getConfigListEntry(_("    Speicherort für Backup:"), config.plugins.serienRec.BackupPath))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  AUTO-CHECK:  ---------------------------------------------------------------------------------------")))
		#self.list.append(getConfigListEntry(_("Intervall für autom. Suchlauf (in Std.) (00 = kein autom. Suchlauf, 24 = nach Uhrzeit):"), config.plugins.serienRec.updateInterval)) #3600000
		self.list.append(getConfigListEntry(_("Intervall für autom. Suchlauf (Std.) (00 = keiner, 24 = nach Uhrzeit):"), config.plugins.serienRec.updateInterval)) #3600000
		if config.plugins.serienRec.updateInterval.value == 24:
			self.list.append(getConfigListEntry(_("    Uhrzeit für automatischen Suchlauf (nur wenn Intervall = 24):"), config.plugins.serienRec.deltime))
		self.list.append(getConfigListEntry(_("Timer für X Tage erstellen:"), config.plugins.serienRec.checkfordays))
		self.list.append(getConfigListEntry(_("Früheste Zeit für Timer:"), config.plugins.serienRec.globalFromTime))
		self.list.append(getConfigListEntry(_("Späteste Zeit für Timer:"), config.plugins.serienRec.globalToTime))
		self.list.append(getConfigListEntry(_("Versuche die Eventid vom EPGCACHE zu holen:"), config.plugins.serienRec.eventid))
		self.list.append(getConfigListEntry(_("Immer aufnehmen wenn keine Wiederholung gefunden wird:"), config.plugins.serienRec.forceRecording))
		if config.plugins.serienRec.forceRecording.value:
			self.list.append(getConfigListEntry(_("    maximal X Tage auf Wiederholung warten:"), config.plugins.serienRec.TimeSpanForRegularTimer))
		self.list.append(getConfigListEntry(_("Anzahl der Aufnahmen pro Episode:"), config.plugins.serienRec.NoOfRecords))
		self.list.append(getConfigListEntry(_("Anzahl der gleichzeitigen Aufnahmen einschränken:"), config.plugins.serienRec.selectNoOfTuners))
		if config.plugins.serienRec.selectNoOfTuners.value:
			self.list.append(getConfigListEntry(_("    maximale Anzahl gleichzeitigen Aufnahmen:"), config.plugins.serienRec.tuner))
		self.list.append(getConfigListEntry(_("Aktion bei neuer Serie/Staffel:"), config.plugins.serienRec.ActionOnNew))
		if config.plugins.serienRec.ActionOnNew.value != "0":
			self.list.append(getConfigListEntry(_("    auch bei manuellem Suchlauf:"), config.plugins.serienRec.ActionOnNewManuell))
			self.list.append(getConfigListEntry(_("    Einträge löschen die älter sind als X Tage:"), config.plugins.serienRec.deleteOlderThan))
		self.list.append(getConfigListEntry(_("nach Änderungen Suchlauf beim Beenden starten:"), config.plugins.serienRec.runAutocheckAtExit))
		if config.plugins.serienRec.updateInterval.value == 24:
			self.list.append(getConfigListEntry(_("Aus Deep-StandBy aufwecken:"), config.plugins.serienRec.wakeUpDSB))
			self.list.append(getConfigListEntry(_("Nach dem automatischen Suchlauf in Deep-StandBy gehen:"), config.plugins.serienRec.afterAutocheck))
			if config.plugins.serienRec.afterAutocheck.value:
				self.list.append(getConfigListEntry(_("    Timeout für Deep-StandBy-Abfrage (in Sek.):"), config.plugins.serienRec.DSBTimeout))
			
		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  TIMER:  --------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Timer-Art:"), self.kindOfTimer))
		self.list.append(getConfigListEntry(_("Timervorlauf (in Min.):"), config.plugins.serienRec.margin_before))
		self.list.append(getConfigListEntry(_("Timernachlauf (in Min.):"), config.plugins.serienRec.margin_after))
		self.list.append(getConfigListEntry(_("Timername:"), config.plugins.serienRec.TimerName))
		self.list.append(getConfigListEntry(_("Manuelle Timer immer erstellen:"), config.plugins.serienRec.forceManualRecording))
		tvbouquets = getTVBouquets()
		if len(tvbouquets) < 2:
			config.plugins.serienRec.selectBouquets.value = False
		else:
			self.list.append(getConfigListEntry(_("Bouquets auswählen:"), config.plugins.serienRec.selectBouquets))
			if config.plugins.serienRec.selectBouquets.value:
				self.getTVBouquetSelection()
				self.list.append(getConfigListEntry(_("    Standard Bouquet:"), config.plugins.serienRec.MainBouquet))
				self.list.append(getConfigListEntry(_("    Alternatives Bouquet:"), config.plugins.serienRec.AlternativeBouquet))
				self.list.append(getConfigListEntry(_("    Verwende alternative Channels bei Konflikten:"), config.plugins.serienRec.useAlternativeChannel))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  OPTIMIERUNGEN:  ------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Intensive Suche nach angelegten Timern:"), config.plugins.serienRec.intensiveTimersuche))
		self.list.append(getConfigListEntry(_("Zeige ob die Episode als Aufnahme auf der HDD ist:"), config.plugins.serienRec.sucheAufnahme))
		self.list.append(getConfigListEntry(_("Zeitspanne für Timersuche einschränken:"), config.plugins.serienRec.breakTimersuche))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  GUI:  ----------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Skin:"), config.plugins.serienRec.SkinType))
		global showAllButtons
		if config.plugins.serienRec.SkinType.value not in ("", "Skin2", "AtileHD"):
			self.list.append(getConfigListEntry(_("    werden bei diesem Skin immer ALLE Tasten angezeigt:"), config.plugins.serienRec.showAllButtons))
			showAllButtons = config.plugins.serienRec.showAllButtons.value
		elif config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
			showAllButtons = False
		else:
			showAllButtons = True
		if not showAllButtons:
			self.list.append(getConfigListEntry(_("    Wechselzeit der Tastenanzeige (Sek.):"), config.plugins.serienRec.DisplayRefreshRate))
		self.list.append(getConfigListEntry(_("Starte Plugin mit:"), config.plugins.serienRec.firstscreen))
		self.list.append(getConfigListEntry(_("Zeige Picons:"), config.plugins.serienRec.showPicons))
		self.list.append(getConfigListEntry(_("Korrektur der Schriftgröße in Listen:"), config.plugins.serienRec.listFontsize))
		self.list.append(getConfigListEntry(_("Anzahl der wählbaren Staffeln im Menü SerienMarker:"), config.plugins.serienRec.max_season))
		self.list.append(getConfigListEntry(_("Vor Löschen in SerienMarker und TimerList Benutzer fragen:"), config.plugins.serienRec.confirmOnDelete))
		self.list.append(getConfigListEntry(_("Benachrichtigung beim Suchlauf:"), config.plugins.serienRec.showNotification))
		self.list.append(getConfigListEntry(_("Benachrichtigung bei Timerkonflikten:"), config.plugins.serienRec.showMessageOnConflicts))
		self.list.append(getConfigListEntry(_("Screens bei Änderungen sofort aktualisieren:"), config.plugins.serienRec.refreshViews))
		self.list.append(getConfigListEntry(_("Staffelauswahl bei neuen Markern:"), config.plugins.serienRec.defaultStaffel))
		self.list.append(getConfigListEntry(_("Öffne Marker-Ansicht nach Hinzufügen neuer Marker:"), config.plugins.serienRec.openMarkerScreen))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  LOG:  ----------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Speicherort für LogFile:"), config.plugins.serienRec.LogFilePath))
		self.list.append(getConfigListEntry(_("LogFile-Name mit Datum/Uhrzeit:"), config.plugins.serienRec.longLogFileName))
		if config.plugins.serienRec.longLogFileName.value:
			self.list.append(getConfigListEntry(_("    Log-Files löschen die älter sind als X Tage:"), config.plugins.serienRec.deleteLogFilesOlderThan))
		self.list.append(getConfigListEntry(_("DEBUG LOG aktivieren:"), config.plugins.serienRec.writeLog))
		self.list.append(getConfigListEntry(_("DEBUG LOG - STB Informationen:"), config.plugins.serienRec.writeLogVersion))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Senderliste:"), config.plugins.serienRec.writeLogChannels))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Seriensender:"), config.plugins.serienRec.writeLogAllowedSender))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Episoden:"), config.plugins.serienRec.writeLogAllowedEpisodes))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Added:"), config.plugins.serienRec.writeLogAdded))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Festplatte:"), config.plugins.serienRec.writeLogDisk))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Tageszeit:"), config.plugins.serienRec.writeLogTimeRange))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Zeitbegrenzung:"), config.plugins.serienRec.writeLogTimeLimit))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Timer Debugging:"), config.plugins.serienRec.writeLogTimerDebug))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Scroll zum Ende:"), config.plugins.serienRec.logScrollLast))
		self.list.append(getConfigListEntry(_("DEBUG LOG - Anzeige mit Zeilenumbruch:"), config.plugins.serienRec.logWrapAround))

	def getTVBouquetSelection(self):
		self.bouquetList = []
		tvbouquets = getTVBouquets()
		for bouquet in tvbouquets:
			self.bouquetList.append((bouquet[1], bouquet[1]))

		#config.plugins.serienRec.MainBouquet.setChoices(choices = [("Favourites (TV)", _("Favourites (TV)")), ("Favourites-SD (TV)", _("Favourites-SD (TV)"))], default="Favourites (TV)")
		#config.plugins.serienRec.AlternativeBouquet.setChoices(choices = [("Favourites (TV)", _("Favourites (TV)")), ("Favourites-SD (TV)", _("Favourites-SD (TV)"))], default="Favourites-SD (TV)")
		config.plugins.serienRec.MainBouquet.setChoices(choices = self.bouquetList, default = self.bouquetList[0][0])
		config.plugins.serienRec.AlternativeBouquet.setChoices(choices = self.bouquetList, default = self.bouquetList[1][0])
		
	def changedEntry(self):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyOK(self):
		ConfigListScreen.keyOK(self)
		if self['config'].getCurrent()[1] == config.plugins.serienRec.savetopath:
			#start_dir = "/media/hdd/movie/"
			start_dir = config.plugins.serienRec.savetopath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Aufnahme-Verzeichnis auswählen"))
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
			start_dir = config.plugins.serienRec.LogFilePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("LogFile-Verzeichnis auswählen"))
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.BackupPath:
			start_dir = config.plugins.serienRec.BackupPath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Backup-Verzeichnis auswählen"))
		elif self['config'].getCurrent()[1] == config.plugins.serienRec.databasePath:
			start_dir = config.plugins.serienRec.databasePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Datenbank-Verzeichnis auswählen"))

	def selectedMediaFile(self, res):
		if res is not None:
			if self['config'].getCurrent()[1] == config.plugins.serienRec.savetopath:
				print res
				config.plugins.serienRec.savetopath.value = res
				#config.plugins.serienRec.savetopath.save()
				#configfile.save()
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
				print res
				config.plugins.serienRec.LogFilePath.value = res
				#config.plugins.serienRec.LogFilePath.save()
				#configfile.save()
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.BackupPath:
				print res
				config.plugins.serienRec.BackupPath.value = res
				#config.plugins.serienRec.BackupPath.save()
				#configfile.save()
				self.changedEntry()
			elif self['config'].getCurrent()[1] == config.plugins.serienRec.databasePath:
				print res
				config.plugins.serienRec.databasePath.value = res
				#config.plugins.serienRec.databasePath.save()
				#configfile.save()
				self.changedEntry()

	def setInfoText(self):
		lt = time.localtime()
		self.HilfeTexte = {
			config.plugins.serienRec.BoxID :                   (_("Die ID (Nummer) der STB. Läuft der SerienRecorder auf mehreren Boxen, die alle auf die selbe Datenbank (im Netzwerk) zugreifen, "
			                                                    "können einzelne Marker über diese ID für jede Box einzeln aktiviert oder deaktiviert werden. Timer werden dann nur auf den Boxen erstellt, "
																"für die der Marker aktiviert ist.")),
			config.plugins.serienRec.savetopath :              (_("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen gespeichert werden.")),
			config.plugins.serienRec.seriensubdir :            (_("Bei 'ja' wird für jede Serien ein eigenes Unterverzeichnis (z.B.\n'%s<Serien_Name>/') für die Aufnahmen erstellt.")) % config.plugins.serienRec.savetopath.value,
			config.plugins.serienRec.seasonsubdir :            (_("Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis (z.B.\n"
			                                                    "'%s<Serien_Name>/Season %s') erstellt.")) % (config.plugins.serienRec.savetopath.value, str("1").zfill(config.plugins.serienRec.seasonsubdirnumerlength.value)),
			config.plugins.serienRec.seasonsubdirnumerlength : (_("Die Anzahl der Stellen, auf die die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt wird.")),
			config.plugins.serienRec.seasonsubdirfillchar :    (_("Auswahl, ob die Staffelnummer im Namen des Staffel-Verzeichnisses mit führenden Nullen oder mit Leerzeichen aufgefüllt werden.")),
			config.plugins.serienRec.deltime :                 (_("Uhrzeit, zu der der automatische Timer-Suchlauf täglich ausgeführt wird (%s:%s Uhr).")) % (str(config.plugins.serienRec.deltime.value[0]).zfill(2), str(config.plugins.serienRec.deltime.value[1]).zfill(2)),
			config.plugins.serienRec.maxWebRequests :          (_("Die maximale Anzahl der gleichzeitigen Suchanfragen auf 'wunschliste.de'.\n"
			                                                    "ACHTUING: Eine höhere Anzahl kann den Timer-Suchlauf beschleunigen, kann bei langsamer Internet-Verbindung aber auch zu Problemen führen!!")),
			config.plugins.serienRec.Autoupdate :              (_("Bei 'ja' wird bei jedem Start des SerienRecorders nach verfügbaren Updates gesucht.")),
			config.plugins.serienRec.databasePath :            (_("Das Verzeichnis auswählen und/oder erstellen, in dem die Datenbank gespeichert wird.")),
			config.plugins.serienRec.AutoBackup :              (_("Bei 'ja' werden vor jedem Timer-Suchlauf die Datenbank des SR, die 'alte' log-Datei und die enigma2-Timer-Datei ('/etc/enigma2/timers.xml') in ein neues Verzeichnis kopiert, "
			                                                    "dessen Name sich aus dem aktuellen Datum und der aktuellen Uhrzeit zusammensetzt (z.B.\n'%s%s%s%s%s%s/').")) % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)),
			config.plugins.serienRec.BackupPath :              (_("Das Verzeichnis auswählen und/oder erstellen, in dem die Backups gespeichert werden.")),
			config.plugins.serienRec.checkfordays :            (_("Es werden nur Timer für Folgen erstellt, die innerhalb der nächsten hier eingestellten Anzahl von Tagen ausgestrahlt werden \n"
			                                                    "(also bis %s).")) % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400))),
			config.plugins.serienRec.globalFromTime :          (_("Die Uhrzeit, ab wann Aufnahmen erlaubt sind.\n"
							                                    "Die erlaubte Zeitspanne beginnt um %s:%s Uhr.")) % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2)),
			config.plugins.serienRec.globalToTime :            (_("Die Uhrzeit, bis wann Aufnahmen erlaubt sind.\n"
						                                        "Die erlaubte Zeitspanne endet um %s:%s Uhr.")) % (str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)),
			config.plugins.serienRec.eventid :                 (_("Bei 'ja' wird beim Anlegen eines Timers versucht die Anfangs- und Endzeiten vom EPG zu holen. "
			                                                    "Außerdem erfolgt bei jedem Timer-Suchlauf ein Abgleich der Anfangs- und Endzeiten aller Timer mit den EPG-Daten.")),
			config.plugins.serienRec.forceRecording :          (_("Bei 'ja' werden auch Timer für Folgen erstellt, die ausserhalb der erlaubten Zeitspanne (%s:%s - %s:%s) ausgestrahlt werden, "
			                                                    "wenn KEINE Wiederholung innerhalb der erlaubten Zeitspanne gefunden wird. Wird eine passende Wiederholung zu einem späteren Zeitpunkt gefunden, dann wird der Timer für diese Wiederholung erstellt.\n"
			                                                    "Bei 'nein' werden ausschließlich Timer für jene Folgen erstellt, die innerhalb der erlaubten Zeitspanne liegen.")) % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2), str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)),
			config.plugins.serienRec.TimeSpanForRegularTimer : (_("Die Anzahl der Tage, die maximal auf eine Wiederholung gewartet wird, die innerhalb der erlaubten Zeitspanne ausgestrahlt wird. "
			                                                    "Wird keine passende Wiederholung gefunden (oder aber eine Wiederholung, die aber zu weit in der Zukunft liegt), "
																"wird ein Timer für den frühestmöglichen Termin (auch außerhalb der erlaubten Zeitspanne) erstellt.")),
			config.plugins.serienRec.NoOfRecords :             (_("Die Anzahl der Aufnahmen, die von einer Folge gemacht werden sollen.")),
			config.plugins.serienRec.selectNoOfTuners :        (_("Bei 'ja' wird die Anzahl von gleichzeitigen (sich überschneidenden) Timern begrenzt.\n"
                                                                "Bei 'nein' werden alle verfügbaren Tuner für Timer benutzt, die Überprüfung ob noch ein weiterer Timer erzeugt werden kann, übernimmt enigma2.")),
			config.plugins.serienRec.tuner :                   (_("Die maximale Anzahl von Timern, die gleichzeitig (sich überschneidend) erstellt werden. Überprüft werden dabei ALLE Timer, nicht nur die vom SerienRecorder erstellten.")),
			config.plugins.serienRec.ActionOnNew :             (_("Wird eine neue Staffel oder Serie gefunden (d.h. Folge 1), wird die hier eingestellt Aktion ausgeführt:\n"
			                                                    "  - 'keine': es erfolgt keine weitere Aktion.\n"
																"  - 'nur Benachrichtigung': Es wird eine Nachricht auf dem Bildschirm eingeblendet, die auf den Staffel-/Serienstart hinweist. "
																"Diese Nachricht bleibt solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) wird.\n"
																"  - 'nur Marker anlegen': Es wird automatisch ein neuer Serienmarker für die gefundene Serie angelegt.\n"
																"  - 'Benachrichtigung und Marker anlegen': Es wird sowohl ein neuer Serienmarker angelegt, als auch eine Nachricht auf dem Bildschirm eingeblendet, die auf den Staffel-/Serienstart hinweist. "
																"Diese Nachricht bleibt solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) wird.")),
			config.plugins.serienRec.ActionOnNewManuell :      (_("Bei 'nein' wird bei manuell gestarteten Suchläufen NICHT nach Staffel-/Serienstarts gesucht.")),
			config.plugins.serienRec.deleteOlderThan :         (_("Staffel-/Serienstarts die älter als die hier eingestellte Anzahl von Tagen (also vor dem %s) sind, werden beim Timer-Suchlauf automatisch aus der Datenbank entfernt "
																"und auch nicht mehr angezeigt.")) % time.strftime("%d.%m.%Y", time.localtime(int(time.time()) - (int(config.plugins.serienRec.deleteOlderThan.value) * 86400))),
			config.plugins.serienRec.runAutocheckAtExit :      (_("Bei 'ja' wird nach Beenden des SR automatisch ein Timer-Suchlauf ausgeführt, falls bei den Channels und/oder Markern Änderungen vorgenommen wurden, "
			                                                    "die Einfluss auf die Erstellung neuer Timer haben. (z.B. neue Serie hinzugefügt, neuer Channel zugewiesen, etc.)")),
			config.plugins.serienRec.wakeUpDSB :               (_("Bei 'ja' wird die STB vor dem automatischen Timer-Suchlauf hochgefahren, falls sie sich im Deep-Standby befindet.\n"
			                                                    "Bei 'nein' wird der automatische Timer-Suchlauf NICHT ausgeführt, wenn sich die STB im Deep-Standby befindet.")),
			config.plugins.serienRec.afterAutocheck :          (_("Bei 'ja' wird die STB nach dem automatischen Timer-Suchlauf wieder in den Deep-Standby gefahren.")),
			config.plugins.serienRec.DSBTimeout :              (_("Bevor die STB in den Deep-Standby fährt, wird für die hier eingestellte Dauer (in Sekunden) eine entsprechende Nachricht auf dem Bildschirm angezeigt. "
			                                                    "Während dieser Zeitspanne hat der Benutzer die Möglichkeit, das Herunterfahren der STB abzubrechen. Nach Ablauf dieser Zeitspanne fährt die STB automatisch in den Deep-Stanby.")),
			self.kindOfTimer :                                 (_("Es kann ausgewählt werden, wie Timer angelegt werden. Die Auswahlmöglichkeiten sind:\n"
			                                                    "  - 'aufnehmen': Ein 'normaler' Timer wird erstellt\n"
																"  - 'umschalten': Es wird ein Timer erstellt, bei dem nur auf den aufzunehmenden Sender umgeschaltet wird. Es erfolgt KEINE Aufnahme\n"
																"  - 'umschalten und aufnehmen': Es wird ein Timer erstellt, bei dem vor der Aufnahme auf den aufzunehmenden Sender umgeschaltet wird\n"
																"  - 'Erinnerung': Es wird ein Timer erstellt, bei dem lediglich eine Erinnerungs-Nachricht auf dem Bildschirm eingeblendet wird. Es wird weder umgeschaltet, noch erfolgt eine Aufnahme")),
			config.plugins.serienRec.margin_before :           (_("Die Vorlaufzeit für Aufnahmen in Minuten.\n"
			                                                    "Die Aufnahme startet um die hier eingestellte Anzahl von Minuten vor dem tatsächlichen Beginn der Sendung")),
			config.plugins.serienRec.margin_after :            (_("Die Nachlaufzeit für Aufnahmen in Minuten.\n"
			                                                    "Die Aufnahme endet um die hier eingestellte Anzahl von Minuten noch dem tatsächlichen Ende der Sendung")),
			config.plugins.serienRec.forceManualRecording :    (_("Bei 'nein' erfolgt beim manuellen Anlegen von Timern in 'Sendetermine' eine Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen erreicht wurde. "
			                                                    "In diesem Fall wird der Timer NICHT angelegt, und es erfolgt ein entsprechender Eintrag im log.\n"
			                                                    "Bei 'ja' wird beim manuellen Anlegen von Timern in 'Sendetermine' die Überprüfung, ob für die zu timende Folge bereits die maximale Anzahl von Timern und/oder Aufnahmen vorhanden sind, "
			                                                    "ausgeschaltet. D.h. der Timer wird auf jeden Fall angelegt, soferne nicht ein Konflikt mit anderen Timern besteht.")),
			config.plugins.serienRec.TimerName :               (_("Es kann ausgewählt werden, wie der Timername gebildet werden soll, dieser Name bestimmt auch den Namen der Aufnahme. Die Beschreibung enthält weiterhin die Staffel und Episoden Informationen.\n"
																"Falls das Plugin 'SerienFilm' verwendet wird, sollte man die Einstellung '<Serienname>' wählen, damit die Episoden korrekt in virtuellen Ordnern zusammengefasst werden.")),
			config.plugins.serienRec.selectBouquets :          (_("Bei 'ja' werden 2 Bouquets (Standard und Alternativ) für die Channel-Zuordnung verwendet werden.\n"
			                                                    "Bei 'nein' wird das erste Bouquet für die Channel-Zuordnung benutzt.")),
			config.plugins.serienRec.MainBouquet :             (_("Auswahl, welches Bouquet bei der Channel-Zuordnung als Standard verwendet werden sollen.")),
			config.plugins.serienRec.AlternativeBouquet :      (_("Auswahl, welches Bouquet bei der Channel-Zuordnung als Alternative verwendet werden sollen.")),
			config.plugins.serienRec.useAlternativeChannel :   (_("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Channel (Standard oder alternativ) zu erstellen, "
										                        "falls der Timer auf dem bevorzugten Channel nicht angelegt werden kann.")),
			config.plugins.serienRec.showPicons :              (_("Bei 'ja' werden in der Hauptansicht auch die Sender-Logos angezeigt.")),
			config.plugins.serienRec.listFontsize :            (_("Damit kann bei zu großer oder zu kleiner Schrift eine individuelle Anpassung erfolgen. Serien Recorder muß neu gestartet werden damit die Änderung wirksam wird.")),
			config.plugins.serienRec.intensiveTimersuche :     (_("Bei 'ja' wird in der Hauptansicht intensiver nach vorhandenen Timern gesucht, d.h. es wird vor der Suche versucht die Anfangszeit aus dem EPGCACHE zu aktualisieren was aber zeitintensiv ist.")),
			config.plugins.serienRec.sucheAufnahme :           (_("Bei 'ja' wird in der Hauptansicht ein Symbol für jede Episode angezeigt, die als Aufnahme auf der Festplatte gefunden wurde, diese Suche ist aber sehr zeitintensiv.")),
			config.plugins.serienRec.max_season :              (_("Die höchste Staffelnummer, die für Serienmarker in der Staffel-Auswahl gewählt werden kann.")),
			config.plugins.serienRec.confirmOnDelete :         (_("Bei 'ja' erfolt eine Sicherheitsabfrage ('Soll ... wirklich entfernt werden?') vor dem entgültigen Löschen von Serienmarkern oder Timern.")),
			config.plugins.serienRec.showNotification :        (_("Je nach Einstellung wird eine Nachricht auf dem Bildschirm eingeblendet, sobald der automatische Timer-Suchlauf startet bzw. endet.")),
			config.plugins.serienRec.showMessageOnConflicts :  (_("Bei 'ja' wird für jeden Timer, der beim automatische Timer-Suchlauf wegen eines Konflikts nicht angelegt werden konnte, eine Nachricht auf dem Bildschirm eingeblendet.\n"
			                                                    "Diese Nachrichten bleiben solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden.")),
			config.plugins.serienRec.DisplayRefreshRate :      (_("Das Zeitintervall in Sekunden, in dem die Anzeige der Options-Tasten wechselt.")),
			config.plugins.serienRec.refreshViews :            (_("Bei 'ja' werden die Anzeigen nach Änderungen von Markern, Channels, etc. sofort aktualisiert, was aber je nach STB-Typ und Internet-Verbindung zeitintensiv sein kann.\n"
			                                                    "Bei 'nein' wird erfolgt die Aktualisierung erst wenn die Anzeige erneut geöffnet wird.")),
			config.plugins.serienRec.defaultStaffel :          (_("Auswahl, ob bei neuen Markern die Staffeln manuell eingegeben werden, oder 'Alle' ausgewählt wird.")),
			config.plugins.serienRec.openMarkerScreen :        (_("Bei 'ja' wird nach Anlegen eines neuen Markers die Marker-Anzeige geöffnet, um den neuen Marker bearbeiten zu können.")),
			config.plugins.serienRec.LogFilePath :             (_("Das Verzeichnis auswählen und/oder erstellen, in dem die log-Dateien gespeichert werden.")),
			config.plugins.serienRec.longLogFileName :         (_("Bei 'nein' wird bei jedem Timer-Suchlauf die log-Datei neu erzeugt.\n"
			                                                    "Bei 'ja' wird NACH jedem Timer-Suchlauf die soeben neu erzeugte log-Datei in eine Datei kopiert, deren Name das aktuelle Datum und die aktuelle Uhrzeit beinhaltet "
																"(z.B.\n%slog_%s%s%s%s%s")) % (config.plugins.serienRec.LogFilePath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)),
			config.plugins.serienRec.deleteLogFilesOlderThan : (_("log-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht.")),
			config.plugins.serienRec.writeLog :                (_("Bei 'nein' erfolgen nur grundlegende Eintragungen in die log-Datei, z.B. Datum/Uhrzeit des Timer-Suchlaufs, Beginn neuer Staffeln, Gesamtergebnis des Timer-Suchlaufs.\n"
			                                                    "Bei 'ja' erfolgen detaillierte Eintragungen, abhängig von den ausgewählten Filtern.")),
			config.plugins.serienRec.writeLogVersion :         (_("Bei 'ja' erfolgen Einträge in die log-Datei, die Informationen über die verwendete STB und das Image beinhalten.")),
			config.plugins.serienRec.writeLogChannels :        (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn dem ausstrahlenden Sender in der Channel-Zuordnung kein STB-Channel zugeordnet ist, oder der STB-Channel deaktiviert ist.")),
			config.plugins.serienRec.writeLogAllowedSender :   (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der ausstrahlende Sender in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist.")),
			config.plugins.serienRec.writeLogAllowedEpisodes : (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn die zu timende Staffel oder Folge in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist.")),
			config.plugins.serienRec.writeLogAdded :           (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Timern vorhanden ist.")),
			config.plugins.serienRec.writeLogDisk :            (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Aufnahmen vorhanden ist.")),
			config.plugins.serienRec.writeLogTimeRange :       (_("Bei 'ja' erfolgen Einträge in die log-Datei, wenn die zu timende Folge nicht in der erlaubten Zeitspanne (%s:%s - %s:%s) liegt, "
			                                                    "sowie wenn gemäß der Einstellung 'Immer aufnehmen wenn keine Wiederholung gefunden wird' = 'ja' "
																"ein Timer ausserhalb der erlaubten Zeitspanne angelegt wird.")) % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2), str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)),
			config.plugins.serienRec.writeLogTimeLimit :       (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der Sendetermin für die zu timende Folge in der Verganhenheit, \n"
			                                                    "oder mehr als die in 'Timer für X Tage erstellen' eingestellte Anzahl von Tagen in der Zukunft liegt (jetzt also nach %s).")) % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400))),
			config.plugins.serienRec.writeLogTimerDebug :      (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der zu erstellende Timer bereits vorhanden ist, oder der Timer erfolgreich angelegt wurde.")),
			config.plugins.serienRec.logScrollLast :           (_("Bei 'ja' wird beim Anzeigen der log-Datei ans Ende gesprungen, bei 'nein' auf den Anfang.")),
			config.plugins.serienRec.logWrapAround :           (_("Bei 'ja' erfolgt die Anzeige der log-Datei mit Zeilenumbruch, d.h. es werden 3 Zeilen pro Eintrag angezeigt.\n"
			                                                    "Bei 'nein' erfolgt die Anzeige der log-Datei mit 1 Zeile pro Eintrag (Bei langen Zeilen sind dann die Enden nicht mehr sichbar!)")),
			config.plugins.serienRec.firstscreen :             (_("Beim Start des SerienRecorder startet das Plugin mit dem ausgewählten Screen.")),
			config.plugins.serienRec.SkinType :                (_("Hier kann das Erscheinungsbild des SR ausgewählt werden.")),
			config.plugins.serienRec.showAllButtons :          (_("Hier kann für eigene Skins angegeben werden, ob immer ALLE Options-Tasten angezeigt werden, oder ob die Anzeige wechselt.")),
		}			
				
		if config.plugins.serienRec.updateInterval.value == 0:
			self.HilfeTexte.update({
				config.plugins.serienRec.updateInterval :  (_("Zeitintervall (in Stunden) für den automatischen Timer-Suchlauf.\n"
															"Bei '00' ist der automatische Timer-Suchlauf komplett ausgeschaltet.\n"
															"Bei '24' erfolgt der automatische Timer-Suchlauf täglich zur eingestellten Uhrzeit.\n"
															"Bei jeder anderen Einstellung in den eingestellten Intervallen."))
			})
		elif config.plugins.serienRec.updateInterval.value == 24:
			self.HilfeTexte.update({
				config.plugins.serienRec.updateInterval :  (_("Zeitintervall (in Stunden) für den automatischen Timer-Suchlauf.\n"
															"Bei '00' ist der automatische Timer-Suchlauf komplett ausgeschaltet.\n"
															"Bei '24' erfolgt der automatische Timer-Suchlauf täglich zur eingestellten Uhrzeit (%s:%s Uhr).\n"
															"Bei jeder anderen Einstellung in den eingestellten Intervallen.")) % (str(config.plugins.serienRec.deltime.value[0]).zfill(2), str(config.plugins.serienRec.deltime.value[1]).zfill(2))
			})
		else:
			self.HilfeTexte.update({
				config.plugins.serienRec.updateInterval :  (_("Zeitintervall (in Stunden) für den automatischen Timer-Suchlauf.\n"
															"Bei '00' ist der automatische Timer-Suchlauf komplett ausgeschaltet.\n"
															"Bei '24' erfolgt der automatische Timer-Suchlauf täglich zur eingestellten Uhrzeit.\n"
															"Bei jeder anderen Einstellung in den eingestellten Intervallen (alle %s Stunden).")) % str(config.plugins.serienRec.updateInterval.value)
			})
			
		if config.plugins.serienRec.forceRecording.value:
			self.HilfeTexte.update({
				config.plugins.serienRec.breakTimersuche : (_("Bei 'ja' wird die Timersuche nach Ablauf der Wartezeit für Wiederholungen (dzt. %s Tage) abgebrochen.")) % int(config.plugins.serienRec.TimeSpanForRegularTimer.value)
			})
		else:
			self.HilfeTexte.update({
				config.plugins.serienRec.breakTimersuche : (_("Bei 'ja' wird die Timersuche abgebrochen, wenn der Ausstrahlungstermin zu weit in der Zukunft liegt (also nach %s).")) % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400)))
			})

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")

		self["config_information_text"].setText(text)
		
	def save(self):
		config.plugins.serienRec.showNotification.save()
		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
			config.plugins.serienRec.update.value = False
		elif config.plugins.serienRec.updateInterval.value == 0: 
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = True

		if not config.plugins.serienRec.selectBouquets.value:
			config.plugins.serienRec.MainBouquet.value = None
			config.plugins.serienRec.AlternativeBouquet.value = None
			config.plugins.serienRec.useAlternativeChannel.value = False
		
		config.plugins.serienRec.BoxID.save()		
		config.plugins.serienRec.savetopath.save()
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.seriensubdir.save()
		config.plugins.serienRec.seasonsubdir.save()
		config.plugins.serienRec.seasonsubdirnumerlength.save()
		config.plugins.serienRec.seasonsubdirfillchar.save()
		config.plugins.serienRec.update.save()
		config.plugins.serienRec.updateInterval.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.AutoBackup.save()
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
		config.plugins.serienRec.wakeUpDSB.save()
		config.plugins.serienRec.afterAutocheck.save()
		config.plugins.serienRec.eventid.save()
		config.plugins.serienRec.LogFilePath.save()
		config.plugins.serienRec.longLogFileName.save()
		config.plugins.serienRec.deleteLogFilesOlderThan.save()
		config.plugins.serienRec.writeLog.save()
		config.plugins.serienRec.writeLogChannels.save()
		config.plugins.serienRec.writeLogAllowedSender.save()
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
		config.plugins.serienRec.listFontsize.save()
		config.plugins.serienRec.intensiveTimersuche.save()
		config.plugins.serienRec.sucheAufnahme.save()
		config.plugins.serienRec.breakTimersuche.save()
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
			
		global serienRecDataBase
		if serienRecDataBase == "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			self.close((True, self.setupModified, True))
		else:		
			global dbSerRec
			f = dbSerRec.text_factory
			dbSerRec.close()
			if not os.path.exists("%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value):
				self.session.openWithCallback(self.callDbChangedMsg, MessageBox, _("Im ausgewählten Verzeichnis existiert noch keine Datenbank.\nSoll die bestehende Datenbank kopiert werden?"), MessageBox.TYPE_YESNO, default = True)
			else:
				serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
				dbSerRec = sqlite3.connect(serienRecDataBase)
				dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
				success = initDB()
				self.close((True, True, success))

	def callDbChangedMsg(self, answer):
		global serienRecDataBase
		if answer:
			shutil.copyfile(serienRecDataBase, "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value)
			serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
			global dbSerRec
			dbSerRec = sqlite3.connect(serienRecDataBase)
			dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
		else:
			serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
		
		success = initDB()
		self.close((True, True, success))

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
			"red"	: (self.cancel, _("Änderungen verwerfen und zurück zur Serien-Marker-Ansicht")),
			"green"	: (self.save, _("Einstellungen speichern und zurück zur Serien-Marker-Ansicht")),
			"cancel": (self.cancel, _("Änderungen verwerfen und zurück zur Serien-Marker-Ansicht")),
			"ok"	: (self.ok, _("Fenster für Verzeichnisauswahl öffnen")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		if showAllButtons:
			Skin1_Settings(self)

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel FROM SerienMarker WHERE LOWER(Serie)=?", (self.Serie.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (None, -1, None, None, None, None, None, 1, -1)
		(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel) = row
		cCursor.close()

		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = ""
		self.savetopath = ConfigText(default = AufnahmeVerzeichnis, fixed_size=False, visible_width=50)
		self.seasonsubdir = ConfigSelection(choices = [("-1", _("gemäß Setup (dzt. %s)") % str(config.plugins.serienRec.seasonsubdir.value).replace('True', _('ja')).replace('False', _('nein'))), ("0", _("nein")), ("1", _("ja"))], default=str(Staffelverzeichnis))
		
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

		self.preferredChannel = ConfigSelection(choices = [("1", _("Standard")), ("2", _("Alternativ"))], default=str(preferredChannel))
		self.useAlternativeChannel = ConfigSelection(choices = [("-1", _("gemäß Setup (dzt. %s)") % str(config.plugins.serienRec.useAlternativeChannel.value).replace('True', _('ja')).replace('False', _('nein'))), ("0", _("nein")), ("1", _("ja"))], default=str(useAlternativeChannel))
		
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

		self['title'].setText(_("Serien Recorder - Einstellungen für '%s':") % self.Serie)
		self['text_red'].setText(_("Abbrechen"))
		self['text_green'].setText(_("Speichern"))
		self['text_ok'].setText(_("Verzeichnis auswählen"))

		if not showAllButtons:
			self['text_0'].setText(_("Abbrechen"))
			self['text_1'].setText(_("About"))

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
			self.num_bt_text = ([buttonText_na, buttonText_na, _("Abbrechen")],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, _("Hilfe")],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def createConfigList(self):
		self.margin_before_index = 1
		self.list = []
		self.list.append(getConfigListEntry(_("vom globalen Setup abweichender Speicherort der Aufnahmen:"), self.savetopath))
		if self.savetopath.value:
			self.list.append(getConfigListEntry(_("Staffel-Verzeichnis anlegen:"), self.seasonsubdir))
			self.margin_before_index += 1
			
		self.margin_after_index = self.margin_before_index + 1

		self.list.append(getConfigListEntry(_("vom globalen Setup abweichenden Timervorlauf aktivieren:"), self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry(_("      Timervorlauf (in Min.):"), self.margin_before))
			self.margin_after_index += 1

		self.NoOfRecords_index = self.margin_after_index + 1
			
		self.list.append(getConfigListEntry(_("vom globalen Setup abweichenden Timernachlauf aktivieren:"), self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry(_("      Timernachlauf (in Min.):"), self.margin_after))
			self.NoOfRecords_index += 1
			
		self.fromTime_index = self.NoOfRecords_index + 1
			
		self.list.append(getConfigListEntry(_("vom globalen Setup abweichende Anzahl der Aufnahmen aktivieren:"), self.enable_NoOfRecords))
		if self.enable_NoOfRecords.value:
			self.list.append(getConfigListEntry(_("      Anzahl der Aufnahmen:"), self.NoOfRecords))
			self.fromTime_index += 1

		self.toTime_index = self.fromTime_index + 1
			
		self.list.append(getConfigListEntry(_("vom globalen Setup abweichende Früheste Zeit für Timer aktivieren:"), self.enable_fromTime))
		if self.enable_fromTime.value:
			self.list.append(getConfigListEntry(_("      Früheste Zeit für Timer:"), self.fromTime))
			self.toTime_index += 1

		self.list.append(getConfigListEntry(_("vom globalen Setup abweichende Späteste Zeit für Timer aktivieren:"), self.enable_toTime))
		if self.enable_toTime.value:
			self.list.append(getConfigListEntry(_("      Späteste Zeit für Timer:"), self.toTime))

		self.list.append(getConfigListEntry(_("Bevorzugte Channel-Liste:"), self.preferredChannel))
		self.list.append(getConfigListEntry(_("Verwende alternative Channels bei Konflikten:"), self.useAlternativeChannel))

			
	def UpdateMenuValues(self):
		if self["config"].instance.getCurrentIndex() == self.margin_before_index:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self["config"].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		elif self["config"].instance.getCurrentIndex() == self.NoOfRecords_index:
			if self.enable_NoOfRecords.value and not self.NoOfRecords.value:
				self.NoOfRecords.value = config.plugins.serienRec.NoOfRecords.value
		elif self["config"].instance.getCurrentIndex() == self.fromTime_index:
			if self.enable_fromTime.value and not self.fromTime.value:
				self.fromTime.value = config.plugins.serienRec.globalFromTime.value
		elif self["config"].instance.getCurrentIndex() == self.toTime_index:
			if self.enable_toTime.value and not self.toTime.value:
				self.toTime.value = config.plugins.serienRec.globalToTime.value
		self.changedEntry()
	
	def changedEntry(self):
		self.createConfigList()
		self["config"].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.UpdateMenuValues()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.UpdateMenuValues()

	def keyDown(self):
		#self.changedEntry()
		if self["config"].instance.getCurrentIndex() >= (len(self.list) - 1):
			self["config"].instance.moveSelectionTo(0)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveDown)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()
			
	def keyUp(self):
		#self.changedEntry()
		if self["config"].instance.getCurrentIndex() < 1:
			self["config"].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)

		if self['config'].getCurrent()[1] == self.savetopath:
			self['bt_ok'].show()
			self['text_ok'].show()
		else:
			self['bt_ok'].hide()
			self['text_ok'].hide()
			
	def ok(self):
		ConfigListScreen.keyOK(self)
		if self["config"].instance.getCurrentIndex() == 0:
			start_dir = self.savetopath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Aufnahme-Verzeichnis auswählen"))

	def selectedMediaFile(self, res):
		if res is not None:
			if self["config"].instance.getCurrentIndex() == 0:
				print res
				self.savetopath.value = res
				if self.savetopath.value == "":
					self.savetopath.value = None
				self.changedEntry()

	def setInfoText(self):
		self.HilfeTexte = {
			self.savetopath :            (_("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen von '%s' gespeichert werden.")) % self.Serie,
			self.seasonsubdir :          (_("Bei 'ja' wird für jede Staffel ein eigenes Unterverzeichnis im Serien-Verzeichnis für '%s' (z.B.\n'%sSeason 001') erstellt.")) % (self.Serie, self.savetopath.value),
			self.enable_margin_before :  (_("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n" 
										  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n" 
						  				  "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
						  				  "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.margin_before :         (_("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
								          "Ist auch beim aufzunehmenden Sender eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.")) % self.Serie,
			self.enable_margin_after :   (_("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
									  	  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
									      "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
									  	  "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.margin_after :          (_("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
								          "Ist auch beim aufzunehmenden Sender eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.")) % self.Serie,
			self.enable_NoOfRecords :    (_("Bei 'ja' kann die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen, eingestellt werden.\n"
									      "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.\n"
									      "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.NoOfRecords :           (_("Die Anzahl der Aufnahmen, die von einer Folge von '%s' gemacht werden sollen.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Anzahl der Aufnahmen.")) % self.Serie,
			self.enable_fromTime :       (_("Bei 'ja' kann die erlaubte Zeitspanne (ab Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
									      "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.\n"
									      "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.fromTime :              (_("Die Uhrzeit, ab wann Aufnahmen von '%s' erlaubt sind.\n"
							              "Die erlaubte Zeitspanne beginnt um %s:%s Uhr.\n" 
							              "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.")) % (self.Serie, str(self.fromTime.value[0]).zfill(2), str(self.fromTime.value[1]).zfill(2)),
			self.enable_toTime :         (_("Bei 'ja' kann die erlaubte Zeitspanne (bis Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.\n"
								          "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.toTime :                (_("Die Uhrzeit, bis wann Aufnahmen von '%s' erlaubt sind.\n"
						                  "Die erlaubte Zeitspanne endet um %s:%s Uhr.\n" 
						                  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.") )% (self.Serie, str(self.toTime.value[0]).zfill(2), str(self.toTime.value[1]).zfill(2)),
			self.preferredChannel :      (_("Auswahl, ob die Standard-Channels oder die alternativen Channels für die Aufnahmen von '%s' verwendet werden sollen.")) % self.Serie,
			self.useAlternativeChannel : (_("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Channel (Standard oder alternativ) zu erstellen, "
										  "falls der Timer für '%s' auf dem bevorzugten Channel nicht angelegt werden kann.\n"
										  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Verwendung von alternativen Channels.\n"
										  "Bei 'gemäß Setup' gilt die Einstellung vom globalen Setup.")) % self.Serie
		}			
				
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")

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

		if (not self.savetopath.value) or (self.savetopath.value == ""):
			Staffelverzeichnis = -1
		else:
			Staffelverzeichnis = self.seasonsubdir.value
			
		cCursor = dbSerRec.cursor()
		sql = "UPDATE OR IGNORE SerienMarker SET AufnahmeVerzeichnis=?, Staffelverzeichnis=?, Vorlaufzeit=?, Nachlaufzeit=?, AnzahlWiederholungen=?, AufnahmezeitVon=?, AufnahmezeitBis=?, preferredChannel=?, useAlternativeChannel=? WHERE LOWER(Serie)=?"
		cCursor.execute(sql, (self.savetopath.value, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, int(self.preferredChannel.value), int(self.useAlternativeChannel.value), self.Serie.lower()))
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
			"red"	: (self.cancel, _("Änderungen verwerfen und zurück zur Channel-Ansicht")),
			"green"	: (self.save, _("Einstellungen speichern und zurück zur Channel-Ansicht")),
			"cancel": (self.cancel, _("Änderungen verwerfen und zurück zur Channel-Ansicht")),
			"ok"	: (self.ok, _("---")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"ok"	: self.ok,
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
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

		self['title'].setText(_("Serien Recorder - Einstellungen für '%s':") % self.webSender)
		self['text_red'].setText(_("Abbrechen"))
		self['text_green'].setText(_("Speichern"))

		if not showAllButtons:
			self['text_0'].setText(_("Abbrechen"))
			self['text_1'].setText(_("About"))

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, _("Abbrechen")],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, _("Hilfe")],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def createConfigList(self):
		self.margin_after_index = 1
		self.list = []
		self.list.append(getConfigListEntry(_("vom globalen Setup abweichenden Timervorlauf aktivieren:"), self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry(_("      Timervorlauf (in Min.):"), self.margin_before))
			self.margin_after_index += 1

		self.list.append(getConfigListEntry(_("vom globalen Setup abweichenden Timernachlauf aktivieren:"), self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry(_("      Timernachlauf (in Min.):"), self.margin_after))

		if VPSPluginAvailable:
			self.list.append(getConfigListEntry(_("VPS für diesen Sender aktivieren:"), self.enable_vps))
			if self.enable_vps.value:
				self.list.append(getConfigListEntry(_("      Sicherheitsmodus aktivieren:"), self.enable_vps_savemode))

	def UpdateMenuValues(self):
		if self["config"].instance.getCurrentIndex() == 0:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self["config"].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		self.changedEntry()
	
	def changedEntry(self):
		self.createConfigList()
		self["config"].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.UpdateMenuValues()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.UpdateMenuValues()

	def keyDown(self):
		#self.changedEntry()
		if self["config"].instance.getCurrentIndex() >= (len(self.list) - 1):
			self["config"].instance.moveSelectionTo(0)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveDown)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)

	def keyUp(self):
		#self.changedEntry()
		if self["config"].instance.getCurrentIndex() < 1:
			self["config"].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)

		#self.setInfoText()
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")
		self["config_information_text"].setText(text)

	def ok(self):
		ConfigListScreen.keyOK(self)

	def setInfoText(self):
		self.HilfeTexte = {
			self.enable_margin_before : (_("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n" 
		                                 "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n" 
					                     "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
					                     "Bei 'nein' gilt die Einstellung im globalen Setup.")) % self.webSender,
			self.margin_before :        (_("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
					                     "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
					                     "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.")) % self.webSender,
			self.enable_margin_after :  (_("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
				                         "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
				                         "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
					                     "Bei 'nein' gilt die Einstellung im globalen Setup.")) % self.webSender,
			self.margin_after :         (_("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
				                         "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
				                         "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.")) % self.webSender,
			self.enable_vps :           (_("Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
			                             "und endet, wenn der Sender das Ende der Ausstrahlung angibt.")) % self.webSender,
			self.enable_vps_savemode :  (_("Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet.Die programmierten Start- und Endzeiten werden eingehalten.\n"
			                             "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.")) % self.webSender
		}
		
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
		except:
			text = _("Keine Information verfügbar.")

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
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left":   (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right":  (self.keyRight, _("zur nächsten Seite blättern")),
			"up":     (self.keyUp, _("eine Zeile nach oben")),
			"down":   (self.keyDown, _("eine Zeile nach unten")),
			"ok":     (self.keyOk, _("ins ausgewählte Verzeichnis wechseln")),
			"green":  (self.keyGreen, _("ausgewähltes Verzeichnis übernehmen")),
			"red":    (self.keyRed, _("ausgewähltes Verzeichnis löschen")),
			"blue":   (self.keyBlue, _("neues Verzeichnis anlegen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
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
		
		self['config'] = FileList(self.initDir, inhibitMounts = False, inhibitDirs = False, showMountpoints = False, showFiles = False)
		self['config'].show()
		self['title'].hide()
		self['path'].show()

		self['text_red'].setText(_("Verzeichnis löschen"))
		self['text_green'].setText(_("Speichern"))
		self['text_ok'].setText(_("Auswahl"))
		self['text_blue'].setText(_("Verzeichnis anlegen"))

		if not showAllButtons:
			self['text_0'].setText(_("Abbrechen"))
			self['text_1'].setText(_("About"))

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
			self.num_bt_text = ([buttonText_na, buttonText_na, _("Abbrechen")],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, buttonText_na],
								[buttonText_na, buttonText_na, _("Hilfe")],
								[buttonText_na, buttonText_na, buttonText_na])

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def keyCancel(self):
		self.close(None)

	def keyRed(self):
		try:
			os.rmdir(self['config'].getSelection()[0])
		except:
			pass
		self.updateFile()
		
	def keyGreen(self):
		directory = self['config'].getSelection()[0]
		if (directory.endswith("/")):
			self.fullpath = self['config'].getSelection()[0]
		else:
			self.fullpath = "%s/" % self['config'].getSelection()[0]
		self.close(self.fullpath)

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Verzeichnis-Name eingeben:")), text = "")

	def wSearch(self, Path_name):
		if Path_name:
			Path_name = "%s%s/" % (self['config'].getSelection()[0], Path_name)
			print Path_name
			if not os.path.exists(Path_name):
				try:
					os.makedirs(Path_name)
				except:
					pass
		self.updateFile()
			
	def keyUp(self):
		self['config'].up()
		self.updateFile()

	def keyDown(self):
		self['config'].down()
		self.updateFile()

	def keyLeft(self):
		self['config'].pageUp()
		self.updateFile()

	def keyRight(self):
		self['config'].pageDown()
		self.updateFile()

	def keyOk(self):
		if self['config'].canDescent():
			self['config'].descent()
			self.updateFile()

	def updateFile(self):
		currFolder = self['config'].getSelection()[0]
		self['path'].setText(_("Auswahl:\n%s") % currFolder)

		
#---------------------------------- Info Functions ------------------------------------------

class serienRecReadLog(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.logliste = []

		self.onLayoutFinish.append(self.readLog)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText(_("Abbrechen"))
		self.num_bt_text[0][0] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None
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
			self.chooseMenuList.l.setItemHeight(70)
		else:
			self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['title'].setText(_("Lese LogFile: (%s)") % logFile)

		if not showAllButtons:
			self['bt_red'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_menu'].show()
			
			self['text_red'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
		
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readLog()
				
	def readLog(self):
		if not fileExists(logFile):
			open(logFile, 'w').close()

		logFile_leer = os.path.getsize(logFile)
		if not logFile_leer == 0:
			readLog = open(logFile, "r")
			self.logliste = []
			for zeile in readLog.readlines():
				if (not config.plugins.serienRec.logWrapAround.value) or (len(zeile.strip()) > 0):
					self.logliste.append((zeile.replace(_('[Serien Recorder]'),'')))
			readLog.close()
			self['title'].hide()
			self['path'].setText(_("LogFile:\n(%s)") % logFile)
			self['path'].show()
			self.chooseMenuList.setList(map(self.buildList, self.logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self['config'].moveToIndex(int(count-1))

	def buildList(self, entry):
		(zeile) = entry
		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 65, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def keyLeft(self):
		self['config'].pageUp()

	def keyRight(self):
		self['config'].pageDown()

	def keyDown(self):
		self['config'].down()

	def keyUp(self):
		self['config'].up()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close()

class serienRecShowConflicts(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"blue"	: (self.keyBlue, _("alle Einträge aus der Liste endgültig löschen")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
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

		self['text_red'].setText(_("Abbrechen"))
		self['text_blue'].setText(_("Liste leeren"))
		self.num_bt_text[1][1] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['title'].setText(_("Timer-Konflikte"))

		if not showAllButtons:
			self['bt_red'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
				
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

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
				self.conflictsListe.append((_("    @ %s (%s) in Konflikt mit:") % (webChannel, time.strftime("%d.%m.%Y - %H:%M", time.localtime(start_time)))))
				data = data[1:]
				for row2 in data:
					self.conflictsListe.append(("            -> %s" % row2.strip()))
				self.conflictsListe.append(("-" * 100))
				self.conflictsListe.append((""))
		cCursor.close()
		self.chooseMenuList.setList(map(self.buildList, self.conflictsListe))
					
	def buildList(self, entry):
		(zeile) = entry
		return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def keyLeft(self):
		self['config'].pageUp()

	def keyRight(self):
		self['config'].pageDown()

	def keyDown(self):
		self['config'].down()

	def keyUp(self):
		self['config'].up()

	def keyBlue(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Conflict-List leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, _("Soll die Liste wirklich geleert werden?"), MessageBox.TYPE_YESNO, default = False)
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
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("für die ausgewählte Serien neue Einträge hinzufügen")),
			"cancel": (self.keyCancel, _("alle Änderungen verwerfen und zurück zur vorherigen Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("ausgewählten Eintrag löschen")),
			"green" : (self.keyGreen, _("alle Änderungen speichern und zurück zur vorherigen Ansicht")),
			"yellow": (self.keyYellow, _("umschalten Sortierung ein/aus")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.delAdded = False
		self.sortedList = False
		self.addedliste = []
		self.addedliste_tmp = []
		self.dbData = []
		self.modus = "config"
		
		self.onLayoutFinish.append(self.readAdded)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText(_("Eintrag löschen"))
		self['text_green'].setText(_("Speichern"))
		self['text_ok'].setText(_("Neuer Eintrag"))
		self['text_yellow'].setText(_("Sortieren"))
		self.num_bt_text[1][0] = buttonText_na

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['cover'].show()

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
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				return
			serien_name = self['config'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check == None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.modus == "config":
				check = self['config'].getCurrent()
				if check == None:
					return
				serien_name = self['config'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check == None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]

			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.modus == "config":
				check = self['config'].getCurrent()
				if check == None:
					return
				serien_name = self['config'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check == None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]

			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readAdded()
				
	def readAdded(self):
		self.addedliste = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Episode FROM AngelegteTimer")
		for row in cCursor:
			(Serie, Staffel, Episode) = row
			zeile = "%s S%sE%s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2))
			self.addedliste.append((zeile, Serie, Staffel, Episode))
		cCursor.close()
		
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText(_("Diese Episoden werden nicht mehr aufgenommen !"))
		self.addedliste_tmp = self.addedliste[:]
		self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		self.getCover()
			
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
		(Serie,) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
			]

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
		if self.aStaffel == None or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, VirtualKeyBoard, title = (_("von Episode:")), text = "")
	
	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if self.aFromEpisode == None or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, VirtualKeyBoard, title = (_("bis Episode:")), text = "")
	
	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		print "[Serien Recorder] Staffel: %s" % self.aStaffel
		print "[Serien Recorder] von Episode: %s" % self.aFromEpisode
		print "[Serien Recorder] bis Episode: %s" % self.aToEpisode
		
		if self.aToEpisode == None or self.aFromEpisode == None or self.aStaffel == None or self.aToEpisode == "":
			return
		else:
			if int(self.aFromEpisode) != 0 or int(self.aToEpisode) != 0:
				cCursor = dbSerRec.cursor()
				for i in range(int(self.aFromEpisode), int(self.aToEpisode)+1):
					print "[Serien Recorder] %s Staffel: %s Episode: %s " % (str(self.aSerie), str(self.aStaffel), str(i))
					cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (self.aSerie, self.aStaffel, str(i).zfill(2), "dump", 0, "dump", "dump", 0, 1))
				dbSerRec.commit()
				cCursor.close()
				self.readAdded()

	def keyOK(self):
		if self.modus == "config":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['config'].hide()
			addedlist = []

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie FROM SerienMarker ORDER BY Serie")
			cMarkerList = cCursor.fetchall()
			for row in cMarkerList:
				addedlist.append(row)
			cCursor.close()
			self.chooseMenuList_popup.setList(map(self.buildList_popup, addedlist))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "config"
			self['config'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() == None:
				print "[Serien Recorder] Marker-Liste leer."
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aStaffel = 0
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, VirtualKeyBoard, title = (_("%s: Staffel eingeben:") % self.aSerie), text = "")

	def keyRed(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Added-File leer."
			return
		else:
			zeile = self['config'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower()))
			self.addedliste_tmp.remove(zeile)
			self.addedliste.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			self.delAdded = True;
			
	def keyGreen(self):
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
		self.close()
			
	def keyYellow(self):
		if len(self.addedliste_tmp) != 0:
			if self.sortedList:
				self.addedliste_tmp = self.addedliste[:]
				self['text_yellow'].setText(_("Sortieren"))
				self.sortedList = False
			else:
				self.addedliste_tmp.sort()
				self['text_yellow'].setText(_("unsortierte Liste"))
				self.sortedList = True

			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		
	def getCover(self):
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				return
			serien_name = self['config'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check == None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		id = None
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				id = "/%s" % id[0]
		getCover(self, serien_name, id)
			
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
			self.session.openWithCallback(self.callDeleteMsg, MessageBox, _("Sollen die Änderungen gespeichert werden?"), MessageBox.TYPE_YESNO, default = True)
		else:
			self.close()

class serienRecShowSeasonBegins(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("Marker für die ausgewählte Serie hinzufügen")),
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"red"	: (self.keyRed, _("ausgewählten Eintrag löschen")),
			"yellow": (self.keyYellow, _("umschalten alle/nur zukünftige anzeigen")),
			"blue"	: (self.keyBlue, _("alle Einträge aus der Liste endgültig löschen")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
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
		self.onLayoutFinish.append(self.readProposal)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText(_("Eintrag löschen"))
		self['text_ok'].setText(_("Marker übernehmen"))
		if self.filter:
			self['text_yellow'].setText(_("Zeige alle"))
		else:
			self['text_yellow'].setText(_("Zeige nur neue"))
		self['text_blue'].setText(_("Liste leeren"))

		self.num_bt_text[3][0] = buttonText_na
			
		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(50)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['cover'].show()

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
		cCursor = dbSerRec.cursor()
		if self.filter:
			now = datetime.datetime.now()
			current_time = datetime.datetime(now.year, now.month, now.day, 00, 00).strftime("%s")
			cCursor.execute("SELECT Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag FROM NeuerStaffelbeginn WHERE UTCStaffelStart >= ? GROUP BY Serie, Staffel", (current_time, ))
		else:
			cCursor.execute("SELECT Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag FROM NeuerStaffelbeginn WHERE CreationFlag=? OR CreationFlag>=1 GROUP BY Serie, Staffel", (self.filter, ))
		for row in cCursor:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = row
			self.proposalList.append((Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag))
		cCursor.close()
		
		self['title'].setText(_("Neue Serie(n) / Staffel(n):"))
		
		self.proposalList.sort(key=lambda x: time.strptime(x[3].split(",")[1].strip(), "%d.%m.%Y"))
		self.chooseMenuList.setList(map(self.buildList, self.proposalList))
		self.getCover()
			
	def buildList(self, entry):
		(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = entry
		
		if CreationFlag == 0:
			imageFound = "%simages/found.png" % serienRecMainPath
		else:
			imageFound = "%simages/black.png" % serienRecMainPath
		
		if CreationFlag == 2:
			setFarbe = colorRed
		else:
			setFarbe = colorWhite
			
		Staffel = "S%sE01" % str(Staffel).zfill(2)
		WochenTag=[_("Mo"), _("Di"), _("Mi"), _("Do"), _("Fr"), _("Sa"), _("So")]
		xtime = time.strftime(WochenTag[time.localtime(int(UTCTime)).tm_wday]+", %d.%m.%Y", time.localtime(int(UTCTime)))

		if config.plugins.serienRec.showPicons.value:
			self.picloader = PicLoader(80, 40)
			picon = self.picloader.load("%simages/sender/%s.png" % (serienRecMainPath, Sender))
			self.picloader.destroy()
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 5, 80, 40, picon),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340, 15, 30, 30, loadPNG(imageFound)),
				(eListboxPythonMultiContent.TYPE_TEXT, 110, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 110, 29, 200, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, colorYellow, colorYellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, colorYellow, colorYellow)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 15, 30, 30, loadPNG(imageFound)),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 200, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, colorYellow, colorYellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, colorYellow, colorYellow)
				]

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def serieInfo(self):
		check = self['config'].getCurrent()
		if check == None:
			return
		url = self['config'].getCurrent()[0][5]
		id = re.findall('epg_print.pl\?s=([0-9]+)', url)
		if id:
			serien_name = self['config'].getCurrent()[0][0]
			self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][0]
			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
				
	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readProposal()
				
	def getCover(self):
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][0]
		id = re.findall('epg_print.pl\?s=([0-9]+)', self['config'].getCurrent()[0][5])
		if id:
			id = "/%s" % id[0]
		getCover(self, serien_name, id)

	def keyRed(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['config'].getCurrent()[0]
			cCursor = dbSerRec.cursor()
			data = (Serie, Staffel, Sender, Datum) 
			cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
			dbSerRec.commit()
			cCursor.close()
			self.readProposal()

	def keyOK(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['config'].getCurrent()[0]
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
					cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
					dbSerRec.commit()
					cCursor.close()

				cCursor = dbSerRec.cursor()
				data = (Serie, Staffel, Sender, Datum) 
				cCursor.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET CreationFlag=0 WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
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
			self['text_yellow'].setText(_("Zeige alle"))
		else:
			self.filter = False
			self['text_yellow'].setText(_("Zeige nur neue"))
		self.readProposal()
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.value = self.filter
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.save()

	def keyBlue(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, _("Soll die Liste wirklich geleert werden?"), MessageBox.TYPE_YESNO, default = False)
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
		self['config'].pageUp()
		self.getCover()

	def keyRight(self):
		self['config'].pageDown()
		self.getCover()

	def keyDown(self):
		self['config'].down()
		self.getCover()

	def keyUp(self):
		self['config'].up()
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

	def dataError(self, error):
		print error

class serienRecWishlist(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("für die ausgewählte Serien neue Einträge hinzufügen")),
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("ausgewählten Eintrag löschen")),
			"green" : (self.keyGreen, _("alle Änderungen speichern und zurück zur vorherigen Ansicht")),
			"yellow": (self.keyYellow, _("umschalten Sortierung ein/aus")),
			"blue"	: (self.keyBlue, _("alle Einträge aus der Liste endgültig löschen")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()
		
		self.delAdded = False
		self.sortedList = False
		self.addedliste = []
		self.addedliste_tmp = []
		self.dbData = []
		self.modus = "config"
		
		self.onLayoutFinish.append(self.readWishlist)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)

		self['text_red'].setText(_("Eintrag löschen"))
		self['text_green'].setText(_("Speichern"))
		self['text_ok'].setText(_("Eintrag anlegen"))
		self['text_yellow'].setText(_("Sortieren"))
		self['text_blue'].setText(_("Liste leeren"))
		self.num_bt_text[2][1] = buttonText_na

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(25)
		self['config'] = self.chooseMenuList
		self['config'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['title'].setText(_("Diese Episoden sind zur Aufnahme vorgemerkt"))

		self['cover'].show()

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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				return
			serien_name = self['config'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check == None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/%s" % id[0])

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.modus == "config":
				check = self['config'].getCurrent()
				if check == None:
					return
				serien_name = self['config'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check == None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]
			
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.modus == "config":
				check = self['config'].getCurrent()
				if check == None:
					return
				serien_name = self['config'].getCurrent()[0][1]
			else:
				check = self['popup_list'].getCurrent()
				if check == None:
					return
				serien_name = self['popup_list'].getCurrent()[0][0]
			
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.readWishlist()
				
	def readWishlist(self):
		self.addedliste = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Episode FROM Merkzettel")
		for row in cCursor:
			(Serie, Staffel, Episode) = row
			zeile = "%s S%sE%s" % (Serie, str(Staffel).zfill(2), str(Episode).zfill(2))
			self.addedliste.append((zeile, Serie, Staffel, Episode))
		cCursor.close()
		
		self.addedliste_tmp = self.addedliste[:]
		self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		self.getCover()
		
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
		(Serie,) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 560, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
			]

	def answerStaffel(self, aStaffel):
		self.aStaffel = aStaffel
		if self.aStaffel == None or self.aStaffel == "":
			return
		self.session.openWithCallback(self.answerFromEpisode, VirtualKeyBoard, title = (_("von Episode:")), text = "")
	
	def answerFromEpisode(self, aFromEpisode):
		self.aFromEpisode = aFromEpisode
		if self.aFromEpisode == None or self.aFromEpisode == "":
			return
		self.session.openWithCallback(self.answerToEpisode, VirtualKeyBoard, title = (_("bis Episode:")), text = "")
	
	def answerToEpisode(self, aToEpisode):
		self.aToEpisode = aToEpisode
		print "[Serien Recorder] Staffel: %s" % self.aStaffel
		print "[Serien Recorder] von Episode: %s" % self.aFromEpisode
		print "[Serien Recorder] bis Episode: %s" % self.aToEpisode
		
		if self.aToEpisode == None or self.aFromEpisode == None or self.aStaffel == None or self.aToEpisode == "":
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
					print "[Serien Recorder] %s Staffel: %s Episode: %s " % (str(self.aSerie), str(self.aStaffel), str(i))
					cCursor.execute("SELECT * FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (self.aSerie.lower(), self.aStaffel.lower(), str(i).zfill(2).lower()))
					row = cCursor.fetchone()
					if not row:
						cCursor.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?)", (self.aSerie, self.aStaffel, str(i).zfill(2), AnzahlAufnahmen))
				dbSerRec.commit()
				cCursor.close()
				self.readWishlist()

	def keyOK(self):
		if self.modus == "config":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['config'].hide()
			self.addedlist = []

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT Serie FROM SerienMarker ORDER BY Serie")
			cMarkerList = cCursor.fetchall()
			for row in cMarkerList:
				self.addedlist.append(row)
			cCursor.close()
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.addedlist))
			self['popup_list'].moveToIndex(0)
		else:
			self.modus = "config"
			self['config'].show()
			self['popup_list'].hide()
			self['popup_bg'].hide()

			if self['popup_list'].getCurrent() == None:
				print "[Serien Recorder] Marker-Liste leer."
				return

			self.aSerie = self['popup_list'].getCurrent()[0][0]
			self.aStaffel = 0
			self.aFromEpisode = 0
			self.aToEpisode = 0
			self.session.openWithCallback(self.answerStaffel, VirtualKeyBoard, title = (_("%s: Staffel eingeben:") % self.aSerie), text = "")

	def keyRed(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Merkzettel ist leer."
			return
		else:
			zeile = self['config'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), str(staffel).lower(), episode.lower()))
			self.addedliste_tmp.remove(zeile)
			self.addedliste.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			self.delAdded = True;
			
	def keyGreen(self):
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
		self.close()
			
	def keyYellow(self):
		if len(self.addedliste_tmp) != 0:
			if self.sortedList:
				self.addedliste_tmp = self.addedliste[:]
				self['text_yellow'].setText(_("Sortieren"))
				self.sortedList = False
			else:
				self.addedliste_tmp.sort()
				self['text_yellow'].setText(_("unsortierte Liste"))
				self.sortedList = True
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		
	def keyBlue(self):
		check = self['config'].getCurrent()
		if check == None:
			print "[Serien Recorder] Merkzettel ist leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callClearListMsg, MessageBox, _("Soll die Liste wirklich geleert werden?"), MessageBox.TYPE_YESNO, default = False)
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
		if self.modus == "config":
			check = self['config'].getCurrent()
			if check == None:
				return
			serien_name = self['config'].getCurrent()[0][1]
		else:
			check = self['popup_list'].getCurrent()
			if check == None:
				return
			serien_name = self['popup_list'].getCurrent()[0][0]

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
		row = cCursor.fetchone()
		cCursor.close()
		id = None
		if row:
			(url, ) = row
			id = re.findall('epg_print.pl\?s=([0-9]+)', url)
			if id:
				id = "/%s" % id[0]
		getCover(self, serien_name, id)
			
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
			self.session.openWithCallback(self.callDeleteMsg, MessageBox, _("Sollen die Änderungen gespeichert werden?"), MessageBox.TYPE_YESNO, default = True)
		else:
			self.close()

class serienRecShowInfo(Screen, HelpableScreen):
	def __init__(self, session, serieName, serieUrl):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serieName = serieName
		self.serieUrl = serieUrl

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"left"  : (self.pageUp, _("zur vorherigen Seite blättern")),
			"right" : (self.pageDown, _("zur nächsten Seite blättern")),
			"up"    : (self.pageUp, _("zur vorherigen Seite blättern")),
			"down"  : (self.pageDown, _("zur nächsten Seite blättern")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
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

		self['text_red'].setText(_("Zurück"))
		self.num_bt_text[4][0] = buttonText_na

		self.displayTimer = None
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

		self['title'].setText(_("Serien Beschreibung: %s") % self.serieName)

		self['cover'].show()

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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def youtubeSearch(self):
		if epgTranslatorInstalled:
			print "[Serien Recorder] starte youtube suche für %s" % self.serieName
			self.session.open(searchYouTube, self.serieName)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			print "[Serien Recorder] starte Wikipedia Suche für %s" % self.serieName
			self.session.open(wikiSearch, self.serieName)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.getData()
				
	def getData(self):
		getPage(self.serieUrl, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)
		serien_nameCover = "/tmp/serienrecorder/%s.png" % self.serieName
		showCover(serien_nameCover, self, serien_nameCover)

	def parseData(self, data):
		info = re.findall('<p class="mb4 credits">(.*?)<div class="newsliste mb4">', data, re.S)
		if info:
			info = info[0]
			raw = re.findall('<li><a href=".*?">(.*?)</li>', info)
			for text in raw:
				raw2 = re.findall('(.*?)</a><span>(.*?)</span>', text, re.S)
				if raw2:
					info = info.replace(text, '%s..%s' % (str(re.sub('<.*?>', '', raw2[0][0])).ljust(40-len(raw2[0][0])/3, '.'), str(re.sub('<.*?>', '', raw2[0][1])).rjust(40-len(raw2[0][1])/3, '.')))

			info = info.replace('</div>', '').replace('<br>', '\n')
			beschreibung = re.sub('<!--(.*\n)*(.*)-->', '', info, re.S)
			beschreibung = re.sub('<.*?>', '', beschreibung)
			beschreibung = re.sub('\n{3,}', '\n\n', beschreibung)
			beschreibung = unicode(beschreibung, 'ISO-8859-1')
			beschreibung = beschreibung.encode('utf-8')
			beschreibung = beschreibung.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
			self['info'].setText(str(beschreibung).replace('Cast & Crew\n','Cast & Crew:\n'))

	def dataError(self, error):
		print error

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

class serienRecShowImdbVideos(Screen, HelpableScreen):
	def __init__(self, session, ilink, serien_name, serien_id):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.ilink = ilink
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serien_id = serien_id

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("ausgewähltes Video abspielen")),
			"cancel": (self.keyCancel, _("zurück zur vorherigen Ansicht")),
			"menu"  : (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
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

		self['text_ok'].setText(_("Video zeigen"))

		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(50)
		self['config'] = self.chooseMenuList
		self['config'].show()

		self['title'].setText(_("Lade imdbVideos..."))

		self['cover'].show()

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
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def serieInfo(self):
		check = self['config'].getCurrent()
		if check == None:
			return
		self.session.open(serienRecShowInfo, self.serien_name, "http://www.wunschliste.de/%s" % self.serien_id)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)

	def showManual(self):
		if BrowserInstalled:
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", True)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					serienRecCheckForRecording(self.session, False)

			if result[1]:
				self.getVideos()
				
	def getVideos(self):
		videos = imdbVideo().videolist(self.ilink.replace('combined',''))
		if videos != None:
			count = len(videos)
			self['title'].setText(_("Es wurde(n) (%s) imdbVideos gefunden.") % str(count))
			self.chooseMenuList.setList(map(self.buildList, videos))
		else:
			self['title'].setText(_("Keine imdbVideos gefunden."))
			
	def buildList(self, entry):
		(id, image) = entry

		#self.picloader = PicLoader(250, 150)
		#picon = self.picloader.load("%simages/sender/%s.png" % (serienRecMainPath, Sender))
		#self.picloader.destroy()
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 750, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, id)
			]

	def keyOK(self):
		check = self['config'].getCurrent()
		if check == None:
			return

		url = self['config'].getCurrent()[0][0]
		image = self['config'].getCurrent()[0][1]
		print url
		
		stream = imdbVideo().stream_url(url)
		if stream != None:
			#sref = eServiceReference(0x1001, 0, stream)
			sref = eServiceReference(4097, 0, stream)
			self.session.open(MoviePlayer, sref)

	def getCover(self):
		getCover(self, self.serien_name, "/%s" % self.serien_id)

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		self.close()

#########################################
#
#   About screen
#
#########################################

class serienRecAboutScreen(Screen, ConfigListScreen):
	DESKTOP_WIDTH       = getDesktop(0).size().width()
	DESKTOP_HEIGHT      = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderAbout" position="%d,%d" size="650,250" title="%s" >
			<widget name="pluginInfo" position="5,5" size="640,240" valign="center" halign="center" zPosition="5" transparent="1" foregroundColor="white" font="Regular;18"/>
		</screen>""" % ((DESKTOP_WIDTH - 650) / 2, (DESKTOP_HEIGHT - 250) / 2, _("Über SerienRecorder"))

	def __init__(self,session):
		self.session = session
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions"], {
			"cancel": self.exit,
			"ok": self.exit
		}, -1)

		self.info =("SerienRecorder for Enigma2 (v%s) (c) 2014 by einfall and w22754\n"
					"\n"
					"For more info:\n"
					"http://www.vuplus-support.org/wbb3/index.php?page=Thread&threadID=60724\n"
					"\n"
					"If you like this plugin and want to support us, please donate to:\n"
					"@einfall: send PN for Amazon-Wishlist,\n"
					"@w22754: PayPal to w22754@yahoo.de") % config.plugins.serienRec.showversion.value

		self["pluginInfo"] = Label(self.info)

	def exit(self):
		self.close()
		
#########################################
#
#   PluginNotInstalled screen
#
#########################################

class serienRecPluginNotInstalledScreen(Screen, ConfigListScreen):
	DESKTOP_WIDTH       = getDesktop(0).size().width()
	DESKTOP_HEIGHT      = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderAbout" position="%d,%d" size="650,150" title="%s" >
			<widget name="pluginInfo" position="5,5" size="640,140" valign="center" halign="center" zPosition="5" transparent="1" foregroundColor="white" font="Regular;18"/>
		</screen>""" % ((DESKTOP_WIDTH - 650) / 2, (DESKTOP_HEIGHT - 150) / 2, _("Plugin nicht installiert"))

	def __init__(self,session,PluginName):
		self.session = session
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions"], {
			"cancel": self.exit,
			"ok": self.exit
		}, -1)

		self.info =(_("SerienRecorder für Enigma2 (v%s) (c) 2014 von einfall und w22754\n"
					"\n"
					"Für diese Funktion wird folgendes Plugin benötigt:\n"
					"%s")) % (config.plugins.serienRec.showversion.value, PluginName)

		self["pluginInfo"] = Label(self.info)

	def exit(self):
		self.close()
		

#---------------------------------- Main Functions ------------------------------------------

class serienRecMain(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"    : (self.keyOK, _("Marker für die ausgewählte Serie hinzufügen")),
			"cancel": (self.keyCancel, _("SerienRecorder beenden")),
			"left"  : (self.keyLeft, _("zur vorherigen Seite blättern")),
			"right" : (self.keyRight, _("zur nächsten Seite blättern")),
			"up"    : (self.keyUp, _("eine Zeile nach oben")),
			"down"  : (self.keyDown, _("eine Zeile nach unten")),
			"red"	: (self.keyRed, _("Anzeige-Modus auswählen")),
			"green"	: (self.keyGreen, _("Ansicht Sender-Zuordnung öffnen")),
			"yellow": (self.keyYellow, _("Ansicht Serien-Marker öffnen")),
			"blue"	: (self.keyBlue, _("Ansicht Timer-Liste öffnen")),
			"info" 	: (self.keyCheck, _("Suchlauf für Timer starten")),
			"menu"	: (self.recSetup, _("Menü für globale Einstellungen öffnen")),
			"nextBouquet" : (self.nextPage, _("Serienplaner des nächsten Tages laden")),
			"prevBouquet" : (self.backPage, _("Serienplaner des vorherigen Tages laden")),
			"startTeletext"       : (self.youtubeSearch, _("Trailer zur ausgewählten Serie auf YouTube suchen")),
			"startTeletext_long"  : (self.WikipediaSearch, _("Informationen zur ausgewählten Serie auf Wikipedia suchen")),
			"0"		: (self.readLogFile, _("Log-File des letzten Suchlaufs anzeigen")),
			"1"		: (self.modifyAddedFile, _("Liste der aufgenommenen Folgen bearbeiten")),
			"3"		: (self.showProposalDB, _("Liste der Serien/Staffel-Starts anzeigen")),
			"4"		: (self.serieInfo, _("Informationen zur ausgewählten Serie anzeigen")),
			"6"		: (self.showConflicts, _("Liste der Timer-Konflikte anzeigen")),
			"7"		: (self.showWishlist, _("Wunschliste (vorgemerkte Folgen) anzeigen")),
			"9"     : (self.importFromFile, _("manueller Import der Daten von älteren Versionen (bis 2.3)")),
			#"5"		: (self.test, _("-")),
		}, -1)
		self.helpList[0][2].sort()
		
		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)
		
		ReadConfigFile()

		if not initDB():
			self.close()

		self.setupSkin()
			
		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
			config.plugins.serienRec.update.value = False
		elif config.plugins.serienRec.updateInterval.value == 0: 
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = True

		self.pNeu = int(config.plugins.serienRec.screenmode.value)

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
		self.ErrorMsg = _("unbekannt")
		self.modus = "list"
		self.loading = True
		self.forceRefresh = False
		self.daylist = []
		
		#self.onLayoutFinish.append(self.startScreen)
		self.onFirstExecBegin.append(self.startScreen)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)
		
	def setSkinProperties(self):
		setSkinProperties(self)
		
		self['text_red'].setText(_("Anzeige-Modus"))
		self['text_green'].setText(_("Sender zuordnen"))
		self['text_ok'].setText(_("Marker hinzufügen"))
		self['text_yellow'].setText(_("Serien Marker"))
		self['text_blue'].setText(_("Timer-Liste"))
		self.num_bt_text[2][2] = _("Timer suchen")
		
		self.displayTimer = None
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
		self.chooseMenuList.l.setItemHeight(50)
		self['config'] = self.chooseMenuList
		self['config'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(30)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		self['title'].setText(_("Lade infos from Web..."))

		self['cover'].show()

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
		return
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_id = self['config'].getCurrent()[0][14]
		url = "http://www.wunschliste.de/%s/links" % serien_id
		print url
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink2).addErrback(self.dataError)
			
	def getImdblink2(self, data):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			print ilink
			serien_name = self['config'].getCurrent()[0][6]
			serien_id = self['config'].getCurrent()[0][14]
			self.session.open(serienRecShowImdbVideos, ilink[0], serien_name, serien_id)

	def importFromFile(self):
		if not initDB():
			self.close()
		self['title'].setText(_("File-Import erfolgreich ausgeführt"))
		self['title'].instance.setForegroundColor(parseColor("white"))

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showProposalDB(self):
		self.session.openWithCallback(self.readWebpage, serienRecShowSeasonBegins)

	def serieInfo(self):
		if self.loading:
			return

		check = self['config'].getCurrent()
		if check == None:
			return

		serien_url = self['config'].getCurrent()[0][5]
		serien_name = self['config'].getCurrent()[0][6]
		
		self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de%s" % serien_url)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def showWishlist(self):
		self.session.open(serienRecWishlist)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.loading:
				return

			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][6]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "EPGTranslator von Kashmir")

	def WikipediaSearch(self):
		if WikipediaInstalled:
			if self.loading:
				return
				
			check = self['config'].getCurrent()
			if check == None:
				return

			serien_name = self['config'].getCurrent()[0][6]
			print "[Serien Recorder] starte Wikipedia Suche für %s" % serien_name
			self.session.open(wikiSearch, serien_name)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Wikipedia von Kashmir")

	def showManual(self):
		if BrowserInstalled:
			if self.loading:
				return
				
			self.session.open(Browser, "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/Help/SerienRecorder.html", False)
		else:
			self.session.open(serienRecPluginNotInstalledScreen, "Opera Webbrowser")
			
	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def setHeadline(self):
		# aktuelle internationale Serien
		if int(config.plugins.serienRec.screeplaner.value) == 1:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText(_("Alle Serien (aktuelle internationale Serien)"))
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText(_("Neue Serien (aktuelle internationale Serien)"))
			elif int(config.plugins.serienRec.screenmode.value) == 2:
				self['headline'].setText(_("Nach aktivierten Sendern (aktuelle internationale Serien)"))
			## E01
			elif int(config.plugins.serienRec.screenmode.value) == 3:
				self['headline'].setText(_("Alle Serienstarts"))
			
		# soaps
		elif int(config.plugins.serienRec.screeplaner.value) == 2:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText(_("Alle Serien (Soaps)"))
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText(_("Neue Serien ((Soaps)"))
			elif int(config.plugins.serienRec.screenmode.value) == 2:
				self['headline'].setText(_("Nach aktivierten Sendern (Soaps)"))
			
		# internationale Serienklassiker
		elif int(config.plugins.serienRec.screeplaner.value) == 3:
			if int(config.plugins.serienRec.screenmode.value) == 0:
				self['headline'].setText(_("Alle Serien (internationale Serienklassiker)"))
			elif int(config.plugins.serienRec.screenmode.value) == 1:
				self['headline'].setText(_("Neue Serien (internationale Serienklassiker)"))
			elif int(config.plugins.serienRec.screenmode.value) == 2:
				self['headline'].setText(_("Nach aktivierten Sendern (internationale Serienklassiker)"))
		self.pNeu = int(config.plugins.serienRec.screenmode.value)
		
		self['headline'].instance.setForegroundColor(parseColor("red"))

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if not result[2]:
			self.close()
		else:	
			if result[0]:
				if config.plugins.serienRec.update.value:
					#print "%s[Serien Recorder] AutoCheck Hour-Timer: %s%s" % (self.color_print, config.plugins.serienRec.update.value, self.color_end)
					serienRecCheckForRecording(self.session, False)
				elif config.plugins.serienRec.timeUpdate.value:
					#print "%s[Serien Recorder] AutoCheck Clock-Timer: %s%s" % (self.color_print, config.plugins.serienRec.timeUpdate.value, self.color_end)
					serienRecCheckForRecording(self.session, False)
				#elif not config.plugins.serienRec.update.value:
				#	print "%s[Serien Recorder] AutoCheck Hour-Timer: %s%s" % (self.color_print, config.plugins.serienRec.update.value, self.color_end)
				#elif config.plugins.serienRec.timeUpdate.value:
				#	print "%s[Serien Recorder] AutoCheck Clock-Timer: %s%s" % (self.color_print, config.plugins.serienRec.timeUpdate.value, self.color_end)

			if result[1]:
				self.readWebpage()

	def startScreen(self):
		print "[Serien Recorder] version %s is running..." % config.plugins.serienRec.showversion.value
		
		global refreshTimer
		if not refreshTimer:
			if config.plugins.serienRec.update.value or config.plugins.serienRec.timeUpdate.value:
				serienRecCheckForRecording(self.session, False)
		
		if config.plugins.serienRec.Autoupdate.value:
			checkUpdate(self.session).checkforupdate()
			
		self.dayChache = {}
		if self.isChannelsListEmpty():
			print "[Serien Recorder] Channellist is empty !"
			self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		else:
			if config.plugins.serienRec.firstscreen.value == "1":
				self.forceRefresh = True
				self.session.openWithCallback(self.readWebpage, serienRecMarker)
			else:
				self.readWebpage()

	def readWebpage(self, answer=True):
		if not showMainScreen:
			self.keyCancel()
			self.close()

		if answer or self.forceRefresh:
			self.forceRefresh = False
			self['title'].instance.setForegroundColor(parseColor("white"))
			self['title'].setText(_("Lade Infos vom Web..."))
			self.loading = True
			url = "http://www.wunschliste.de/serienplaner/%s/%s" % (str(config.plugins.serienRec.screeplaner.value), str(self.page))
			print url
			self.setHeadline()

			c1 = re.compile('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', re.S)
			c2 = re.compile('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?<tr><td rowspan="2"></td><td>(.*?)<span class="epg_ep.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', re.S)

			#date = datetime.datetime.now()
			#date += datetime.timedelta(days=self.page)
			#key = '%s.%s.' % (str(date.day).zfill(2), str(date.month).zfill(2))
			#if key in self.dayChache:
			#	self.parseWebpage(self.dayChache[key])
			#else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseWebpage, c1, c2).addErrback(self.dataError)

	def parseWebpage(self, data, c1, c2):
		self.daylist = []
		self.ErrorMsg = "start reading from Wunschliste.de"
		head_datum = re.findall('<li class="datum">(.*?)</li>', data, re.S)
		#if head_datum:
		#	d = head_datum[0].split(',')
		#	d.reverse()
		#	d = d[0].split('.')
		#	key = '%s.%s.' % (d[0].strip().zfill(2), d[1].strip().zfill(2))
		#	self.dayChache.update({key:data})

		if int(config.plugins.serienRec.screeplaner.value) == 2:
			# Soaps
			raw_tmp = c2.findall(data)
			raw=[]
			for each in raw_tmp:
				each=list(each)
				if each[9]:
					z=re.findall('<span class="epg_st.*?title="Staffel.*?>(.*?)</span>', each[9], re.S)
					if len(z):
						each[9]=z[0]
				raw.append(tuple(each))
		else:
			# Serien
			raw = c1.findall(data)

		if raw:
			for regional,paytv,neu,prime,time,url,serien_name,serien_id,sender,staffel,episode,title in raw:
				aufnahme = False
				serieAdded = False
				start_h = time[:+2]
				start_m = time[+3:]
				start_time = getUnixTimeWithDayOffset(start_h, start_m, self.page)
				
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				title = iso8859_Decode(title)
				staffel = iso8859_Decode(staffel)
				self.ErrorMsg = "%s - S%sE%s - %s (%s)" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title, sender)
				
				cSender_list = self.checkSender(sender)
				
				if self.checkTimer(serien_name, start_time, sender):
					aufnahme = True
				else:
					##############################
					#
					# try to get eventID (eit) from epgCache
					#
					if config.plugins.serienRec.eventid.value and config.plugins.serienRec.intensiveTimersuche.value:
						if len(cSender_list) != 0:
							(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSender_list[0]

							(margin_before, margin_after) = getMargins(serien_name, webChannel)
							
							# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
							event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(start_time)+(int(margin_before) * 60))
							if event_matches and len(event_matches) > 0:
								for event_entry in event_matches:
									print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
									start_time_eit = int(event_entry[3])
									if self.checkTimer(serien_name, start_time_eit, sender):
										aufnahme = True
										break

							if not aufnahme and (stbRef != altstbRef):
								event_matches = getEPGevent(['RITBDSE',(altstbRef, 0, int(start_time)+(int(margin_before) * 60), -1)], altstbRef, serien_name, int(start_time)+(int(margin_before) * 60))
								if event_matches and len(event_matches) > 0:
									for event_entry in event_matches:
										print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
										start_time_eit = int(event_entry[3])
										if self.checkTimer(serien_name, start_time_eit, sender):
											aufnahme = True
											break

				if self.checkMarker(serien_name):
					serieAdded = True

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
					bereits_vorhanden = countEpisodeOnHDD(dirname, seasonEpisodeString, serien_name, True) > 0 and True or False
						
				title = "%s - %s" % (seasonEpisodeString, title)
				if self.pNeu == 0:
					self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 1:
					if int(neu) == 1:
						self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 2:
					if len(cSender_list) != 0:
						(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSender_list[0]
						if int(status) == 1:
							self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 3:
					if re.search('01', episode, re.S):
						self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

		print "[Serien Recorder] Es wurden %s Serie(n) gefunden" % len(self.daylist)
		
		self.loading = False
		if len(self.daylist) != 0:
			if head_datum:
				self['title'].setText(_("Es wurden für - %s - %s Serie(n) gefunden.") % (head_datum[0], len(self.daylist)))
				self['title'].instance.setForegroundColor(parseColor("white"))
			else:
				self['title'].setText(_("Es wurden für heute %s Serie(n) gefunden.") % len(self.daylist))
				self['title'].instance.setForegroundColor(parseColor("white"))
			self.chooseMenuList.setList(map(self.buildList, self.daylist))
			self.ErrorMsg = "'getCover()'"
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self['title'].setText(_("Es wurden für heute %s Serie(n) gefunden.") % len(self.daylist))
			self['title'].instance.setForegroundColor(parseColor("white"))
			print "[Serien Recorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
			self.chooseMenuList.setList(map(self.buildList, self.daylist))
			
	def buildList(self, entry):
		(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id) = entry
		#entry = [(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id)]
		
		imageNone = "%simages/black.png" % serienRecMainPath
		imageNeu = "%simages/neu.png" % serienRecMainPath
		imageTimer = "%simages/timer.png" % serienRecMainPath
		imageHDD = "%simages/hdd_24x24.png" % serienRecMainPath
		
		if serieAdded:
			setFarbe = colorGreen
		else:
			setFarbe = colorWhite
			if str(episode).isdigit():
				if int(episode) == 1:
					setFarbe = colorRed

		if int(neu) == 0:					
			imageNeu = imageNone
			
		if bereits_vorhanden:
			imageHDDTimer = imageHDD
		elif aufnahme:
			imageHDDTimer = imageTimer
		else:
			imageHDDTimer = imageNone
		
		if config.plugins.serienRec.showPicons.value:
			self.picloader = PicLoader(80, 40)
			picon = self.picloader.load("%simages/sender/%s.png" % (serienRecMainPath, sender))
			self.picloader.destroy()
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 00, 5, 80, 40, picon),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330, 7, 30, 22, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 330, 30, 30, 22, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 100, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 100, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, colorYellow, colorYellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 365, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 365, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, colorYellow, colorYellow)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 7, 30, 22, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 5, 30, 30, 22, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 40, 3, 280, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 40, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, colorYellow, colorYellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 340, 3, 520, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 340, 29, 520, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, colorYellow, colorYellow)
				]

	def keyOK(self):
		if self.modus == "list":
			if self.loading:
				return

			check = self['config'].getCurrent()
			if check == None:
				return

			serien_neu = self['config'].getCurrent()[0][2]
			serien_url = self['config'].getCurrent()[0][5]
			serien_name = self['config'].getCurrent()[0][6]
			sender = self['config'].getCurrent()[0][7]
			staffel = self['config'].getCurrent()[0][8]
			serien_id = self['config'].getCurrent()[0][14]

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
				cCursor.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))
				dbSerRec.commit()
				cCursor.close()
				self['title'].setText(_("Serie '- %s -' zum Serien Marker hinzugefügt.") % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
				global runAutocheckAtExit
				runAutocheckAtExit = True
				if config.plugins.serienRec.openMarkerScreen.value:
					self.session.open(serienRecMarker, serien_name)
			else:
				self['title'].setText(_("Serie '- %s -' existiert bereits im Serien Marker.") % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))
				cCursor.close()

		elif self.modus == "popup":
			status = self['popup_list'].getCurrent()[0][0]
			planer_id = self['popup_list'].getCurrent()[0][1]
			name = self['popup_list'].getCurrent()[0][2]
			print status, planer_id, name

			self['popup_list'].hide()
			self['popup_bg'].hide()
			self['config'].show()
			self.modus = "list"
			self.pNeu = int(status)
			config.plugins.serienRec.screenmode.value = int(status)
			config.plugins.serienRec.screeplaner.value = int(planer_id)
			print "[SerienRecorder] neu: %s - planer: %s" % (config.plugins.serienRec.screenmode.value, config.plugins.serienRec.screeplaner.value)
			config.plugins.serienRec.screenmode.save()
			config.plugins.serienRec.screeplaner.save()
			configfile.save()
			self.chooseMenuList.setList(map(self.buildList, []))
			self.readWebpage()

	def getCover(self):
		if self.loading:
			return
		
		check = self['config'].getCurrent()
		if check == None:
			return

		serien_name = self['config'].getCurrent()[0][6]
		id = self['config'].getCurrent()[0][5]
		getCover(self, serien_name, id)
		
	def keyRed(self):
		if self.modus == "list":
			self.popup_list = []
			
			# aktuelle internationale Serien
			self.popup_list.append(('0', '1', _('Alle Serien (aktuelle internationale Serien)')))
			self.popup_list.append(('1', '1', _('Neue Serien (aktuelle internationale Serien)')))
			self.popup_list.append(('2', '1', _('Nach aktivierten Sendern (aktuelle internationale Serien)')))
			
			# soaps
			self.popup_list.append(('0', '2', _('Alle Serien (Soaps)')))
			self.popup_list.append(('1', '2', _('Neue Serien (Soaps)')))
			self.popup_list.append(('2', '2', _('Nach aktivierten Sendern (Soaps)')))
			
			# internationale Serienklassiker
			self.popup_list.append(('0', '3', _('Alle Serien (internationale Serienklassiker)')))
			self.popup_list.append(('1', '3', _('Neue Serien (internationale Serienklassiker)')))
			self.popup_list.append(('2', '3', _('Nach aktivierten Sendern (internationale Serienklassiker)')))
			
			# E01
			self.popup_list.append(('3', '1', _('Alle Serienstarts')))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.popup_list))
			
			self['popup_bg'].show()
			self['popup_list'].show()
			self['config'].hide()

			if int(config.plugins.serienRec.screeplaner.value) == 1:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 0
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 1
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 2
				## E01
				elif int(config.plugins.serienRec.screenmode.value) == 3:
					idx = 9
				
			# soaps
			elif int(config.plugins.serienRec.screeplaner.value) == 2:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 3
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 4
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 5
				
			# internationale Serienklassiker
			elif int(config.plugins.serienRec.screeplaner.value) == 3:
				if int(config.plugins.serienRec.screenmode.value) == 0:
					idx = 6
				elif int(config.plugins.serienRec.screenmode.value) == 1:
					idx = 7
				elif int(config.plugins.serienRec.screenmode.value) == 2:
					idx = 8

			self['popup_list'].moveToIndex(idx)
			self.modus = "popup"
			self.loading = False

	def buildList_popup(self, entry):
		(mode, planer_id, name) = entry

		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 0, 800, 30, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name)
			]

	def isChannelsListEmpty(self):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Count(*) from Channels")
		(count,) = cCursor.fetchone()
		print "[Serien Recorder] count channels %s" % count
		if count == 0:
			print "channels: true"
			return True
		else:
			print "channels: false"
			return False

	def checkTimer(self, serie, start_time, webchannel):
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

	def checkSender(self, mSender):
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (mSender.lower(),))
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

	def checkMarker(self, Serie):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(),))
		row = cCursor.fetchone()
		cCursor.close()
		if row:
			return True
		else:
			return False

	def keyGreen(self):
		self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		
	def keyYellow(self):
		self.session.openWithCallback(self.readWebpage, serienRecMarker)
		
	def keyBlue(self):
		self.session.openWithCallback(self.readWebpage, serienRecTimer)

	def keyCheck(self):
		self.session.openWithCallback(self.readWebpage, serienRecRunAutoCheck, True)
		
	def keyLeft(self):
		if self.modus == "list":
			self['config'].pageUp()
			self.getCover()
		else:
			self['popup_list'].pageUp()

	def keyRight(self):
		if self.modus == "list":
			self['config'].pageDown()
			self.getCover()
		else:
			self['popup_list'].pageDown()

	def keyDown(self):
		if self.modus == "list":
			self['config'].down()
			self.getCover()
		else:
			self['popup_list'].down()

	def keyUp(self):
		if self.modus == "list":
			self['config'].up()
			self.getCover()
		else:
			self['popup_list'].up()

	def nextPage(self):
		self.page += 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self.readWebpage()

	def backPage(self):
		if not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self.readWebpage()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

	def keyCancel(self):
		if self.modus == "list":
			try:
				self.displyTimer.stop()
			except:
				pass

			if runAutocheckAtExit and config.plugins.serienRec.runAutocheckAtExit.value:
				singleTimer = eTimer()
				if isDreamboxOS:
					self.singleTimer_conn = self.singleTimer.timeout.connect(serienRecCheckForRecording(self.session, True))
				else:
					singleTimer.callback.append(serienRecCheckForRecording(self.session, True))
				singleTimer.start(10000, True)
			
			#self.hide()
			#self.showAbout()
			self.close()
		elif self.modus == "popup":
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self['config'].show()
			self.modus = "list"

	def dataError(self, error):
		self['title'].setText(_("Suche auf 'Wunschliste.de' erfolglos"))
		self['title'].instance.setForegroundColor(parseColor("white"))
		writeLog(_("[Serien Recorder] Fehler bei: %s") % self.ErrorMsg, True)
		print "[Serien Recorder] Fehler bei: %s" % self.ErrorMsg
		print error

class checkUpdate():

	def __init__(self, session):
		self.session = session

	def checkforupdate(self):
		try:
			getPage("http://master.dl.sourceforge.net/project/serienrec/version.txt").addCallback(self.gotUpdateInfo).addErrback(self.gotError)
		except Exception, error:
			print str(error)

	def gotError(self, error=""):
		return

	def gotUpdateInfo(self, html):
		tmp_infolines = html.splitlines()
		remoteversion = tmp_infolines[0]
		self.updateurl = tmp_infolines[1]
		self.delete_files = tmp_infolines[2]
		if config.plugins.serienRec.version.value < remoteversion:
			self.session.openWithCallback(self.startUpdate,MessageBox,_("Für das Serien Recorder Plugin ist ein Update verfügbar!\nWollen Sie es jetzt herunterladen und installieren?"), MessageBox.TYPE_YESNO)
		else:
			getPage("http://sourceforge.net/projects/w22754/files/SerienRecorder.txt").addCallback(self.gotUpdateInfoFromW22754).addErrback(self.gotError)
			print "[Serien Recorder] kein update von @einfall verfügbar."

	def gotUpdateInfoFromW22754(self, html):
		tmp_infolines = html.splitlines()
		remoteversion = tmp_infolines[0].split(".")
		self.updateurl = tmp_infolines[1]
		version = config.plugins.serienRec.showversion.value.split(".")
		
		if len(version) < 3:
			version.extend((3-len(version)) * '0')
		if len(remoteversion) < 3:
			remoteversion.extend((3-len(remoteversion)) * '0')
		
		update = False
		if int(remoteversion[0]) > int(version[0]):
			update = True
		elif (int(remoteversion[0]) == int(version[0])) and (int(remoteversion[1]) > int(version[1])):
			update = True
		elif (int(remoteversion[0]) == int(version[0])) and (int(remoteversion[1]) == int(version[1])) and (int(remoteversion[2]) > int(version[2])):
			update = True
		
		if update:
			self.session.openWithCallback(self.startUpdate,MessageBox,_("Für das Serien Recorder Plugin ist ein Update verfügbar!\nWollen Sie es jetzt herunterladen und installieren?"), MessageBox.TYPE_YESNO)
		else:
			print "[Serien Recorder] kein update von @w22754 verfügbar."
			return

	def startUpdate(self,answer):
		if answer:
			self.session.open(SerienRecorderUpdateScreen,self.updateurl)
		else:
			return

class SerienRecorderUpdateScreen(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	skin = """
		<screen name="SerienRecorderUpdate" position="%d,%d" size="720,320" title="%s" backgroundColor="#26181d20" flags="wfNoBorder">
			<widget name="mplog" position="5,5" size="710,310" font="Regular;24" valign="center" halign="center" foregroundColor="white" transparent="1" zPosition="5"/>
		</screen>""" % ((DESKTOP_WIDTH - 720) / 2, (DESKTOP_HEIGHT - 320) / 2, _("Serien Recorder Update"))

	def __init__(self, session, updateurl):
		self.session = session
		Screen.__init__(self, session)

		self.updateurl = updateurl

		#self["mplog"] = ScrollLabel()
		self["mplog"] = Label()
		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		sl = self["mplog"]
		sl.instance.setZPosition(5)
		self["mplog"].setText(_("Starte Update, bitte warten..."))
		self.startPluginUpdate()

	def startPluginUpdate(self):
		self.container=eConsoleAppContainer()
		self.container.appClosed.append(self.finishedPluginUpdate)
		self.container.stdoutAvail.append(self.mplog)
		#self.container.stderrAvail.append(self.mplog)
		#self.container.dataAvail.append(self.mplog)
		self.container.execute("opkg install --force-overwrite --force-depends %s" % str(self.updateurl))

	def finishedPluginUpdate(self,retval):
		self.session.openWithCallback(self.restartGUI, MessageBox, _("Serien Recorder wurde erfolgreich aktualisiert!\nWollen Sie jetzt Enigma2 GUI neu starten?"), MessageBox.TYPE_YESNO)

	def restartGUI(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()

	def mplog(self,str):
		self["mplog"].setText(str)

def getNextWakeup():
	color_print = "\033[93m"
	color_end = "\33[0m"

	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value:
		print color_print+"[Serien Recorder] Deep-Standby WakeUp: AN" +color_end
		now = time.localtime()
		current_time = int(time.time())
		
		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0], config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			print color_print+"[Serien Recorder] WakeUp-Timer + 1 day."+color_end
			begin = begin + 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin = begin - 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		print color_print+"[Serien Recorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit +color_end

		return begin
	else:
		print color_print+"[Serien Recorder] Deep-Standby WakeUp: AUS" +color_end

def autostart(reason, **kwargs):
	if reason == 0 and "session" in kwargs:
		session = kwargs["session"]
		color_print = "\033[93m"
		color_end = "\33[0m"
		
		dbSerRec = sqlite3.connect(serienRecDataBase)
		dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
		
		if initDB():
			if config.plugins.serienRec.update.value or config.plugins.serienRec.timeUpdate.value:
				print color_print+"[Serien Recorder] AutoCheck: AN"+color_end
				serienRecCheckForRecording(session, False)
			else:
				print color_print+"[Serien Recorder] AutoCheck: AUS"+color_end
			
def main(session, **kwargs):
	session.open(serienRecMain)
	#print "open screen %s", config.plugins.serienRec.firstscreen.value
	#exec("session.open("+config.plugins.serienRec.firstscreen.value+")")

def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=autostart, wakeupfnc=getNextWakeup),
		#PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc = autostart, wakeupfnc=getNextWakeup,
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=main)
		]
	