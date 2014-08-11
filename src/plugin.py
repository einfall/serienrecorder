# -*- coding: utf-8 -*-
from __init__ import _

from Components.ActionMap import *
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmap, MultiContentEntryPixmapAlphaTest
from Components.config import config
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
from Components.ConfigList import *
from Components.config import *
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config, ConfigInteger, ConfigSelection, getConfigListEntry, ConfigText, ConfigDirectory, ConfigYesNo, configfile, ConfigSelection, ConfigSubsection, ConfigPIN, NoSave, ConfigNothing, ConfigClock

from Components.ScrollLabel import ScrollLabel
from Components.FileList import FileList
from Components.Sources.StaticText import StaticText

from Screens.HelpMenu import HelpableScreen
from Screens.InputBox import InputBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.VirtualKeyBoard import VirtualKeyBoard

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, eServiceReference, getDesktop, loadJPG, RT_VALIGN_CENTER, RT_VALIGN_TOP, RT_VALIGN_BOTTOM, gPixmapPtr, ePicLoad, eTimer
from Tools.Directories import pathExists, fileExists, SCOPE_SKIN_IMAGE, resolveFilename
import sys, os, base64, re, time, shutil, datetime, codecs, urllib2
from twisted.web import client, error as weberror
from twisted.internet import reactor
from twisted.internet import defer
from urllib import urlencode
from skin import parseColor

from Screens.ChannelSelection import service_types_tv
from enigma import eServiceCenter, eServiceReference, eConsoleAppContainer
from ServiceReference import ServiceReference

from Components.UsageConfig import preferredTimerPath, preferredInstantRecordPath
from Components.config import config

# Navigation (RecordTimer)
import NavigationInstance

# Timer
from ServiceReference import ServiceReference
from RecordTimer import RecordTimerEntry
from RecordTimer import RecordTimer, parseEvent, AFTEREVENT
from Components.TimerSanityCheck import TimerSanityCheck

# EPGCache & Event
from enigma import eEPGCache, eServiceReference, eServiceCenter, iServiceInformation

from Tools import Notifications
import sqlite3

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"
#logFile = "%slog" % serienRecMainPath
#serienRecDataBase = "%sSerienRecorder.db" % serienRecMainPath
#
#dbTmp = sqlite3.connect(":memory:")
##dbTmp = sqlite3.connect("%sSR_Tmp.db" % serienRecMainPath)
#dbTmp.text_factory = lambda x: str(x.decode("utf-8"))
#dbSerRec = sqlite3.connect(serienRecDataBase)
#dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))


try:
	default_before = int(config.recording.margin_before.value)
	default_after = int(config.recording.margin_after.value)
except Exception:
	default_before = 0
	default_after = 0

EPGTimeSpan = 10

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

config.plugins.serienRec = ConfigSubsection()
config.plugins.serienRec.savetopath = ConfigText(default = "/media/hdd/movie/", fixed_size=False, visible_width=80)
config.plugins.serienRec.databasePath = ConfigText(default = serienRecMainPath, fixed_size=False, visible_width=80)
#config.plugins.serienRec.fake_entry = NoSave(ConfigNothing())
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
config.plugins.serienRec.deltime = ConfigClock(default = 6*3600)
config.plugins.serienRec.maxWebRequests = ConfigInteger(1, (1,99))
config.plugins.serienRec.checkfordays = ConfigInteger(1, (1,14))
config.plugins.serienRec.fromTime = ConfigInteger(00, (0,23))
config.plugins.serienRec.toTime = ConfigInteger(23, (0,23))
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
config.plugins.serienRec.showNotification = ConfigYesNo(default = True)
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
config.plugins.serienRec.confirmOnDelete = ConfigYesNo(default = True)
config.plugins.serienRec.ActionOnNew = ConfigSelection(choices = [("0", _("keine")), ("1", _("nur Benachrichtigung")), ("2", _("nur Marker anlegen")), ("3", _("Benachrichtigung und Marker anlegen"))], default="0")
config.plugins.serienRec.deleteOlderThan = ConfigInteger(7, (1,99))
config.plugins.serienRec.NoOfRecords = ConfigInteger(1, (1,9))
config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default = True)
config.plugins.serienRec.showPicons = ConfigYesNo(default = True)
config.plugins.serienRec.intensiveTimersuche = ConfigYesNo(default = True)
config.plugins.serienRec.sucheAufnahme = ConfigYesNo(default = True)
config.plugins.serienRec.selectNoOfTuners = ConfigYesNo(default = True)
config.plugins.serienRec.tuner = ConfigInteger(4, (1,4))
config.plugins.serienRec.logScrollLast = ConfigYesNo(default = False)
config.plugins.serienRec.logWrapAround = ConfigYesNo(default = False)

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

# interne
config.plugins.serienRec.version = NoSave(ConfigText(default="023"))
config.plugins.serienRec.showversion = NoSave(ConfigText(default="2.4beta11"))
config.plugins.serienRec.screenmode = ConfigInteger(0, (0,2))
config.plugins.serienRec.screeplaner = ConfigInteger(1, (1,3))
config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))
config.plugins.serienRec.serienRecShowSeasonBegins_filter = ConfigYesNo(default = False)
config.plugins.serienRec.dbversion = NoSave(ConfigText(default="2.4beta11"))


logFile = "%slog" % serienRecMainPath
serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value

dbTmp = sqlite3.connect(":memory:")
#dbTmp = sqlite3.connect("%sSR_Tmp.db" % config.plugins.serienRec.databasePath.value)
dbTmp.text_factory = lambda x: str(x.decode("utf-8"))
dbSerRec = sqlite3.connect(serienRecDataBase)
dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))


autoCheckFinished = False

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

def iso8859_Decode(txt):
	##txt = txt.replace('\xe4','ä').replace('\xf6','ö').replace('\xfc','ü').replace('\xdf','ß')
	##txt = txt.replace('\xc4','Ä').replace('\xd6','Ö').replace('\xdc','Ü')
	#txt = txt.replace('\xe4','ae').replace('\xf6','oe').replace('\xfc','ue').replace('\xdf','ss')
	#txt = txt.replace('\xc4','Ae').replace('\xd6','Oe').replace('\xdc','Ue')
	#txt = txt.replace('...','').replace('..','').replace(':','').replace('\xb2','2')
	txt = unicode(txt, 'ISO-8859-1')
	txt = txt.encode('utf-8')
	txt = txt.replace('...','').replace('..','').replace(':','')

	# &apos;, &quot;, &amp;, &lt;, and &gt;
	txt = txt.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	return txt

def checkTimerAdded(sender, serie, staffel, episode, start_unixtime):
	#"Castle" "S03E20 - Die Pizza-Connection" "1392997800" "1:0:19:EF76:3F9:1:C00000:0:0:0:" "kabel eins"
	found = False
	cCursor = dbSerRec.cursor()
	sql = "SELECT * FROM AngelegteTimer WHERE LOWER(webChannel)=? AND LOWER(Serie)=? AND Staffel=? AND Episode=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
	cCursor.execute(sql, (sender.lower(), serie.lower(), staffel, episode, int(start_unixtime)-(int(EPGTimeSpan)*60), int(start_unixtime)+(int(EPGTimeSpan)*60)))
	row = cCursor.fetchone()
	if row:
		found = True
	cCursor.close()
	return found

def checkAlreadyAdded(serie, staffel, episode):
	Anzahl = 0
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?", (serie.lower(), staffel, episode))
	(Anzahl,) = cCursor.fetchone()	
	cCursor.close()
	return Anzahl

def allowedTimeRange(f,t):
	#liste = ['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23']
	liste = [str(x).zfill(2) for x in range(24)]
	if int(t) >= int(f):
		new = liste[int(f):int(t)+1]
	else:
		new = liste[int(f):len(liste)] + liste[0:int(t)+1]
		
	return new

def convertWunschlisteTimetoUnixtime(rawTime):
	year = rawTime[:+4]
	month = rawTime[+4]+rawTime[+5]
	day = rawTime[+6]+rawTime[+7]
	std = rawTime[+9]+rawTime[+10]
	min = rawTime[+11]+rawTime[+12]
	#print year, month, day, std, min
	#print datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")
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
	#print now.year, now.month, now.day, std, min
	return datetime.datetime(now.year, int(month), int(day), int(hour), int(min)).strftime("%s")
	
def getUnixTimeWithDayOffset(std, min, AddDays):
	now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	date = datetime.datetime(now.year, now.month, now.day, int(std), int(min))
	date += datetime.timedelta(days=AddDays)
	return date.strftime("%s")

def getRealUnixTime(min, std, day, month, year):
	return datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")

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
		if config.plugins.serienRec.seriensubdir.value:
			dirname = "%s%s/" % (dirname, serien_name)
			if config.plugins.serienRec.seasonsubdir.value:
				dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
	else: 
		(dirname, seasonsubdir) = row
		if dirname:
			if not re.search('.*?/\Z', dirname):
				dirname = "%s/" % dirname
			if ((seasonsubdir == -1) and config.plugins.serienRec.seasonsubdir.value) or (seasonsubdir == 1):
				dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
		else:
			dirname = config.plugins.serienRec.savetopath.value
			if config.plugins.serienRec.seriensubdir.value:
				dirname = "%s%s/" % (dirname, serien_name)
				if config.plugins.serienRec.seasonsubdir.value:
					dirname = "%sSeason %s/" % (dirname, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))
		
	cCursor.close()	
	return dirname	

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
	result = cCursor.fetchone()
	cCursor.close()
	return result[0]

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
			#TimerForSpecials = config.plugins.serienRec.TimerForSpecials.value
		#elif TimerForSpecials == -1:
		#	TimerForSpecials = config.plugins.serienRec.TimerForSpecials.value
	else:
		TimerForSpecials = False
		#TimerForSpecials = config.plugins.serienRec.TimerForSpecials.value
	cCursor.close()
	return bool(TimerForSpecials)
	
def getTimeSpan(serien_name):
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT AufnahmezeitVon, AufnahmezeitBis FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(), ))
	data = cCursor.fetchone()
	if data:
		(fromTime, toTime) = data
		if not fromTime:
			fromTime = config.plugins.serienRec.fromTime.value
		if not toTime:
			toTime = config.plugins.serienRec.toTime.value
	else:
		fromTime = config.plugins.serienRec.fromTime.value
		toTime = config.plugins.serienRec.toTime.value
	cCursor.close()
	return (fromTime, toTime)	
	
def getMarker():
	return_list = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT * FROM SerienMarker ORDER BY Serie")
	cMarkerList = cCursor.fetchall()
	for row in cMarkerList:
		(ID, serie, url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) = row
		if alleSender:
			sender = ['Alle',]
		else:
			sender = []
			cSender = dbSerRec.cursor()
			cSender.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=? ORDER BY ErlaubterSender", (ID,))
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
	#print title, starttime, channelref
	if not query or len(query) != 2:
		return

	epgmatches = []
	epgcache = eEPGCache.getInstance()
	allevents = epgcache.lookupEvent(query) or []

	for serviceref, eit, name, begin, duration, shortdesc, extdesc in allevents:
		#print name.lower(), title.lower(), int(begin), int(starttime)
		if channelref == serviceref: # and name.lower() == title.lower()
			if int(int(begin)-(int(EPGTimeSpan)*60)) <= int(starttime) <= int(int(begin)+(int(EPGTimeSpan)*60)):
				#print "MATCHHHHHHH", name
				epgmatches.append((serviceref, eit, name, begin, duration, shortdesc, extdesc))
	return epgmatches

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
	cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef FROM Channels WHERE Erlaubt=1")
	for row in cCursor:
		(webChannel, stbChannel, stbRef) = row
		fSender.append((webChannel))
	cCursor.close()
	return fSender

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

def getUrl(url):
	req = urllib2.Request(url)
	res = urllib2.urlopen(req)
	finalurl = res.geturl()
	return finalurl

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
			
class PicLoader:
	def __init__(self, width, height, sc=None):
		self.picload = ePicLoad()
		if(not sc):
			sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((width, height, sc[0], sc[1], False, 1, "#ff000000"))

	def load(self, filename):
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
		
		if not self.manuell and config.plugins.serienRec.update.value:
			self.refreshTimer = eTimer()
			self.refreshTimer.callback.append(self.startCheck)
			updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
			self.refreshTimer.start(updateZeit)
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer gestartet."+self.color_end
			writeLog(_("[Serien Recorder] AutoCheck Hour-Timer gestartet."), True)
		elif not self.manuell and config.plugins.serienRec.timeUpdate.value:
			loctime = localtime()
			acttime = (loctime[3] * 60 + loctime[4])
			deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
			if acttime < deltime:
				deltatime = deltime - acttime
			else:
				#print "Timeeerrrrrrrrrrrrrrrrrrr: + 1 day"
				deltatime = abs(1440 - acttime + deltime)
			self.refreshTimer = eTimer()
			self.refreshTimer.callback.append(self.startCheck)
			self.refreshTimer.start(deltatime * 60 * 1000, False)
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer gestartet."+self.color_end
			print self.color_print+"[Serien Recorder] Minutes left: " + str(deltatime)+self.color_end
			writeLog(_("[Serien Recorder] AutoCheck Clock-Timer gestartet."), True)
			writeLog(_("[Serien Recorder] Minutes left: %s") % str(deltatime), True)
			
		else:
			print "[Serien Recorder] checkRecTimer manuell."
			self.startCheck(True)

	def startCheck(self, amanuell=False):
		print self.color_print+"[Serien Recorder] settings:"+self.color_end
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
		
		try:
			self.refreshTimer.stop()
		except:
			pass
			
		print self.color_print+"[Serien Recorder] AutoCheck Timer stop."+self.color_end
		writeLog(_("[Serien Recorder] AutoCheck Timer stop."), True)
		if config.plugins.serienRec.update.value:
			self.refreshTimer = eTimer()
			self.refreshTimer.callback.append(self.startCheck)
			updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
			self.refreshTimer.start(updateZeit)
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer gestartet."+self.color_end
			writeLog(_("[Serien Recorder] AutoCheck Hour-Timer gestartet."), True)
				
		elif config.plugins.serienRec.timeUpdate.value:
			loctime = localtime()
			acttime = (loctime[3] * 60 + loctime[4])
			deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
			if acttime < deltime:
				deltatime = deltime - acttime
			else:
				deltatime = abs(1440 - acttime + deltime)
			self.refreshTimer = eTimer()
			self.refreshTimer.callback.append(self.startCheck)
			self.refreshTimer.start(deltatime * 60 * 1000, False)
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer gestartet."+self.color_end
			print self.color_print+"[Serien Recorder] Minutes left: " + str(deltatime)+self.color_end
			writeLog(_("[Serien Recorder] AutoCheck Clock-Timer gestartet."), True)
			writeLog(_("[Serien Recorder] Minutes left: %s") % str(deltatime), True)

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
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------") % (self.uhrzeit, str(self.page)), True)
		else:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------") % (self.uhrzeit, str(self.page)), True)
			if config.plugins.serienRec.showNotification.value:
				Notifications.AddPopup(_("[Serien Recorder]\nAutomatischer Suchlauf für neue Timer wurde gestartet."), MessageBox.TYPE_INFO, timeout=3, id="[Serien Recorder] Suchlauf wurde gestartet")

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
		if config.plugins.serienRec.ActionOnNew.value != "0":
			self.startCheck2(amanuell)
		else:
			self.startCheck3()

	def startCheck2(self, amanuell):
		if str(config.plugins.serienRec.maxWebRequests.value).isdigit():
			ds = defer.DeferredSemaphore(tokens=int(config.plugins.serienRec.maxWebRequests.value))
		else:
			ds = defer.DeferredSemaphore(tokens=1)
		downloads = [ds.run(self.readWebpageForNewStaffel, "http://www.wunschliste.de/serienplaner/%s/%s" % (str(config.plugins.serienRec.screeplaner.value), str(daypage))).addCallback(self.parseWebpageForNewStaffel, amanuell).addErrback(self.dataError) for daypage in range(int(config.plugins.serienRec.checkfordays.value))]
		finished = defer.DeferredList(downloads).addCallback(self.createNewMarker).addCallback(self.startCheck3).addErrback(self.checkError)
		
	def readWebpageForNewStaffel(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'})
		
	def parseWebpageForNewStaffel(self, data, amanuell):
		# read channels
		self.senderListe = {}
		for s in self.readSenderListe():
			self.senderListe[s[0].lower()] = s[:]
			
		head_datum = re.findall('<li class="datum">(.*?)</li>', data, re.S)
		txt = head_datum[0].split(",")
		(day, month, year) = txt[1].split(".")
		UTCDatum = getRealUnixTime(0, 0, day, month, year)
		raw = re.findall('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', data, re.S)
		if raw:
			for regional,paytv,neu,prime,time,url,serien_name,serien_id,sender,staffel,episode,title in raw:
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				#sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')

				if str(episode).isdigit() and str(staffel).isdigit():
					if int(episode) == 1:
						(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(self.senderListe, sender)
						if int(status) == 1:
							if not self.checkMarker(serien_name):
								cCursor = dbSerRec.cursor()
								cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND Staffel=?", (serien_name.lower(), staffel))
								row = cCursor.fetchone()
								if not row:
									data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id)
									cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url) VALUES (?, ?, ?, ?, ?, ?)", data)
									dbSerRec.commit()

									if not amanuell:
										if config.plugins.serienRec.ActionOnNew.value == "1" or config.plugins.serienRec.ActionOnNew.value == "3":
											Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] Neue Episode")
								cCursor.close()
								
							else:
								cCursor = dbSerRec.cursor()
								cCursor.execute("SELECT ID, AlleStaffelnAb FROM SerienMarker WHERE LOWER(Serie)=? AND AlleStaffelnAb>=0 AND AlleStaffelnAb<=?", (serien_name.lower(), staffel))				
								row = cCursor.fetchone()
								if row:
									staffeln = []
									(ID, AlleStaffelnAb) = row
									cCursor.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
									cStaffelList = cCursor.fetchall()
									if len(cStaffelList) > 0:
										staffeln = zip(*cStaffelList)[0]
									if not staffel in staffeln:
										cCursor = dbSerRec.cursor()
										cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE LOWER(Serie)=? AND Staffel=?", (serien_name.lower(), staffel))
										row = cCursor.fetchone()
										if not row:
											data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2") 
											cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
											dbSerRec.commit()

											if not amanuell:
												if config.plugins.serienRec.ActionOnNew.value == "1" or config.plugins.serienRec.ActionOnNew.value == "3":
													Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1, id="[Serien Recorder] Neue Episode")
								cCursor.close()
							
	def createNewMarker(self, result=True):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, StaffelStart FROM NeuerStaffelbeginn WHERE CreationFlag>0")
		for row in cCursor:
			(Serie, Staffel, StaffelStart) = row
			writeLog(_("[Serien Recorder] %d. Staffel von '%s' beginnt am %s") % (int(Staffel), Serie, StaffelStart), True) 

		if config.plugins.serienRec.ActionOnNew.value == "2" or config.plugins.serienRec.ActionOnNew.value == "3":
			cCursor.execute("SELECT Serie, MIN(Staffel), Sender, Url FROM NeuerStaffelbeginn WHERE CreationFlag=1 GROUP BY Serie")
			for row in cCursor:
				(Serie, Staffel, Sender, Url) = row
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, 0, -1)", (Serie, Url, Staffel))
				cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (cCursor.lastrowid, Sender))
				writeLog(_("[Serien Recorder] Neuer Marker für '%s' wurde angelegt") % Serie, True)
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
					for event_entry in event_matches:
						title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
						dirname = getDirname(serien_name, staffel)
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
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=? WHERE StartZeitstempel=? AND ServiceRef=? AND EventID=0"
										cTimer.execute(sql, (start_unixtime, eit, serien_time, stbRef))
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
											sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=? WHERE StartZeitstempel=? AND ServiceRef=? AND EventID=0"
											cTimer.execute(sql, (start_unixtime, eit, serien_time, stbRef))
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
						dirname = getDirname(serien_name, staffel)
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
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=? WHERE StartZeitstempel=? AND ServiceRef=? AND EventID=?"
										cTimer.execute(sql, (start_unixtime, serien_time, stbRef, eit))
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
											sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=? WHERE StartZeitstempel=? AND ServiceRef=? AND EventID=?"
											cTimer.execute(sql, (start_unixtime, serien_time, stbRef, eit))
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
		
	def startCheck3(self, result=True):
		self.cTmp = dbTmp.cursor()
		self.cTmp.execute("DELETE FROM GefundeneFolgen")
		
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
		downloads = [ds.run(self.download, SerieUrl).addCallback(self.parseWebpage,serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen).addErrback(self.dataError) for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode,AnzahlAufnahmen in self.urls]
		finished = defer.DeferredList(downloads).addCallback(self.createTimer).addErrback(self.dataError)
		
	def download(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, timeout=20, headers={'Content-Type':'application/x-www-form-urlencoded'})

	def parseWebpage(self, data, serien_name, SerieUrl, staffeln, allowedSender, AbEpisode, AnzahlAufnahmen):
		self.count_url += 1
		parsingOK = True
		#writeLog("[Serien Recorder] LOG READER: '%s/%s'" % (str(self.count_url), str(self.countSerien)))
		raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		
		#if raw:
		#	parsingOK = True
		#	#print "raw"
		#else:
		#	raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#	if raw2:
		#		raw = []
		#		for each in raw2:
		#			#print each
		#			each = list(each)
		#			each.insert(4, "0")
		#			raw.append(each)
		#		parsingOK = True
		#		#print "raw2"

		raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(.*?x))(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])
		if raw:
			parsingOK = True
			#print "raw"
		
		# check for parsing error
		if not parsingOK:
			# parsing error -> nothing to do
			return
			
		# read channels
		self.senderListe = {}
		for s in self.readSenderListe():
			self.senderListe[s[0].lower()] = s[:]
			
		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)
		
		(fromTime, toTime) = getTimeSpan(serien_name)
		if self.NoOfRecords < AnzahlAufnahmen:
			self.NoOfRecords = AnzahlAufnahmen
		
		# loop over all transmissions
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			# umlaute umwandeln
			#sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
			sender = iso8859_Decode(sender)
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
			title = iso8859_Decode(title)

			(margin_before, margin_after) = getMargins(serien_name, sender)
			
			# setze label string
			label_serie = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			sTitle = "%s - S%sE%s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2))

			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = startzeit.split('.')
			(end_hour, end_min) = endzeit.split('.')

			start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)

			if int(start_hour) > int(end_hour):
				end_unixtime = getNextDayUnixtime(end_min, end_hour, day, month)
				#print end_unixtime
			else:
				end_unixtime = getUnixTimeAll(end_min, end_hour, day, month)

			#print datum, startzeit, start_unixtime, endzeit, end_unixtime

			# setze die vorlauf/nachlauf-zeit
			# print startzeit, start_unixtime, endzeit, end_unixtime
			start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
			end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

			##############################
			#
			# CHECK
			#
			# ueberprueft welche sender aktiviert und eingestellt sind.
			#
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = self.checkSender(self.senderListe, sender)
			if stbChannel == "":
				#print "[Serien Recorder] ' %s ' - STB-Channel nicht gefunden -> ' %s '" % (label_serie, webChannel)
				writeLogFilter("channels", _("[Serien Recorder] ' %s ' - STB-Channel nicht gefunden ' -> ' %s '") % (label_serie, webChannel))
				continue
				
			if int(status) == 0:
				#print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (label_serie, webChannel)
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
							liste = staffeln[:]
							liste.sort()
							liste.reverse()
							if -1 in staffeln:
								liste.remove(-1)
								liste[0] = _("ab %s") % liste[0]
							liste.reverse()
							liste.insert(0, _("0 ab E%s") % str(AbEpisode).zfill(2))
							writeLogFilter("allowedEpisodes", _("[Serien Recorder] ' %s ' - Episode nicht erlaubt -> ' S%sE%s ' -> ' %s '") % (label_serie, str(staffel).zfill(2), str(episode).zfill(2), str(liste).replace("'", "").replace('"', "")))
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
				cCursorTmp.execute("SELECT * FROM Merkzettel WHERE LOWER(SERIE)=? AND Staffel=? AND Episode=?", (serien_name.lower(), staffel, episode))
				row = cCursorTmp.fetchone()
				if row:
					writeLog(_("[Serien Recorder] ' %s ' - Timer vom Merkzettel wird angelegt @ %s") % (label_serie, stbChannel), True)
					serieAllowed = True
					vomMerkzettel = True
				cCursorTmp.close()
				
			if not serieAllowed:
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
				writeLogFilter("allowedEpisodes", _("[Serien Recorder] ' %s ' - Staffel nicht erlaubt -> ' S%sE%s ' -> ' %s '") % (label_serie, str(staffel).zfill(2), str(episode).zfill(2), str(liste).replace("'", "").replace('"', "")))
				continue

			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit = 0
			new_start_unixtime = start_unixtime
			new_end_unixtime = end_unixtime
			if config.plugins.serienRec.eventid.value:
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_unixtime)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(start_unixtime)+(int(margin_before) * 60))
				#print "event matches %s" % len(event_matches)
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
						eit = int(event_entry[1])
						new_start_unixtime = int(event_entry[3]) - (int(margin_before) * 60)
						new_end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
						break
			alt_eit = 0
			alt_start_unixtime = start_unixtime
			alt_end_unixtime = end_unixtime
			if config.plugins.serienRec.eventid.value and stbRef != altstbRef:
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(altstbRef, 0, int(start_unixtime)+(int(margin_before) * 60), -1)], altstbRef, serien_name, int(start_unixtime)+(int(margin_before) * 60))
				#print "event matches %s" % len(event_matches)
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
						alt_eit = int(event_entry[1])
						alt_start_unixtime = int(event_entry[3]) - (int(margin_before) * 60)
						alt_end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
						break
						
			dirname = getDirname(serien_name, staffel)
				
			check_SeasonEpisode = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

			cCursorTmp = dbTmp.cursor()
			sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, Staffel, Episode, SeasonEpisode, Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, EventID, alternativStbChannel, alternativServiceRef, alternativStartTime, alternativEndTime, alternativEventID, DirName, AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
			cCursorTmp.execute(sql, (current_time, future_time, serien_name, staffel, episode, check_SeasonEpisode, title, label_serie, webChannel, stbChannel, stbRef, new_start_unixtime, new_end_unixtime, eit, altstbChannel, altstbRef, alt_start_unixtime, alt_end_unixtime, alt_eit, dirname, AnzahlAufnahmen, fromTime, toTime, int(vomMerkzettel)))
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
			#print "[Serien Recorder] gehe in Deep-Standby"
			#writeLog("[Serien Recorder] gehe in Deep-Standby")
			#self.session.open(TryQuitMainloop, 1)
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
			
			##############################
			#
			# erstellt das serien verzeichnis
			dirname = getDirname(serien_name, staffel)
			if not fileExists(dirname):
				print "[Serien Recorder] erstelle Subdir %s" % dirname
				writeLog(_("[Serien Recorder] erstelle Subdir: ' %s '") % dirname)
				os.makedirs(dirname)
			if fileExists("/var/volatile/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("/var/volatile/tmp/serienrecorder/%s.jpg" % serien_name):
				#print "vorhanden...:", "/var/volatile/tmp/serienrecorder/"+serien_name+".png"
				shutil.copy("/var/volatile/tmp/serienrecorder/%s.png" % serien_name, "%s%s.jpg" % (dirname, serien_name))

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
				cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), staffel, episode.lower()))
				row2 = cTimer.fetchone()
				if row2:
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
					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, timer_start_unixtime, timer_end_unixtime, timer_stbRef, timer_eit, dirname, serien_name, webChannel, timer_stbChannel, check_SeasonEpisode, optionalText, vomMerkzettel, True):
						cAdded = dbTmp.cursor()
						cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), staffel, episode.lower(), start_unixtime, stbRef.lower()))
						cAdded.close()
				cTimer.close()
				
				if len(self.konflikt) > 0:
					if config.plugins.serienRec.showMessageOnConflicts.value:
						Notifications.AddPopup(_("[Serien Recorder]\nACHTUNG!  -  %s") % self.konflikt, MessageBox.TYPE_INFO, timeout=-1)
						
		cTmp.close()
					
	def searchTimer2(self, serien_name, staffel, episode, optionalText, usedChannel, dirname):				
		# prepare postprocessing for forced recordings
		forceRecordings = []
		self.konflikt = ""

		TimerDone = False
		cTimer = dbTmp.cursor()
		cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (serien_name.lower(), staffel, episode.lower()))
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
				cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), staffel, episode.lower(), start_unixtime, stbRef.lower()))
				cAdded.close()
				continue

			# check anzahl timer
			if checkAlreadyAdded(serien_name, staffel, episode) >= AnzahlAufnahmen:
				writeLogFilter("added", _("[Serien Recorder] ' %s ' - Staffel/Episode%s bereits in added vorhanden -> ' %s '") % (label_serie, optionalText, check_SeasonEpisode))
				TimerDone = True
				break

			# check anzahl auf hdd
			bereits_vorhanden = 0
			if fileExists(dirname):
				dirs = os.listdir(dirname)
				for dir in dirs:
					if re.search(serien_name+'.*?'+check_SeasonEpisode+'.*?\.ts\Z', dir):
						bereits_vorhanden += 1

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
			if (int(fromTime) > 0) or (int(toTime) < 23):
				timeRangeList = allowedTimeRange(fromTime, toTime)
				timeRange = {}.fromkeys(timeRangeList, 0)
				
				start_hour = str(time.localtime(int(timer_start_unixtime)).tm_hour).zfill(2)
				if not start_hour in timeRange:
					writeLogFilter("timeRange", _("[Serien Recorder] ' %s ' - Zeitspanne %s nicht in %s") % (label_serie, start_hour, timeRangeList))
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
				cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), staffel, episode.lower(), start_unixtime, stbRef.lower()))
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
					cAdded.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (serien_name.lower(), staffel, episode.lower(), start_unixtime, stbRef.lower()))
					cAdded.close()
					TimerDone = True
					break
					
		return 	TimerDone
		
	def doTimer(self, current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode, optionalText = '', vomMerkzettel = False, disabled = False):
		##############################
		#
		# CHECK
		#
		# ueberprueft ob tage x  voraus passt und ob die startzeit nicht kleiner ist als die aktuelle uhrzeit
		#
		show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
		#print start_unixtime, future_time, current_time
		if int(start_unixtime) > int(future_time):
			show_future = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(future_time)))
			writeLogFilter("timeLimit", _("[Serien Recorder] ' %s ' - Timer wird später angelegt -> Sendetermin: %s - Erlaubte Zeitspanne bis %s") % (label_serie, show_start, show_future))
			return True
		if int(current_time) > int(start_unixtime):
			show_current = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
			writeLogFilter("timeLimit", _("[Serien Recorder] ' %s ' - Der Sendetermin liegt in der Vergangenheit: %s - Aktuelles Datum: %s") % (label_serie, show_start, show_current))
			return False

		# get VPS settings for channel
		vpsSettings = getVPS(webChannel)

		# versuche timer anzulegen
		# setze strings für addtimer
		if checkTuner(start_unixtime, end_unixtime):
			result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, False, dirname, vpsSettings, None, recordfile=".ts")
			if result["result"]:
				self.countTimer += 1
				# Eintrag in das timer file
				self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit)
				if vomMerkzettel:
					self.countTimerFromWishlist += 1
					writeLog(_("[Serien Recorder] ' %s ' - Timer (vom Merkzettel) wurde angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, label_serie, stbChannel), True)
					cCursor = dbSerRec.cursor()
					cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND Staffel=? AND LOWER(Episode)=?", (serien_name.lower(), staffel, episode.lower()))
					dbSerRec.commit()	
					cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND Staffel=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), staffel, episode.lower()))
					dbSerRec.commit()	
					cCursor.close()
				else:
					writeLog(_("[Serien Recorder] ' %s ' - Timer wurde angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, label_serie, stbChannel), True)
				return True
			elif not disabled:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog(_("[Serien Recorder] ' %s ' - Timer konnte nicht angelegt werden%s -> %s %s @ %s") % (label_serie, optionalText, show_start, label_serie, stbChannel), True)
			else:
				self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
				print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
				writeLog(_("[Serien Recorder] ' %s ' - ACHTUNG! -> %s") % (label_serie, result["message"]), True)
				dbMessage = result["message"].replace("Conflicting Timer(s) detected!", "").strip()
				
				result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), eit, True, dirname, vpsSettings, None, recordfile=".ts")
				if result["result"]:
					self.countNotActiveTimer += 1
					# Eintrag in das timer file
					self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit)
					cCursor = dbSerRec.cursor()
					cCursor.execute("INSERT OR IGNORE INTO TimerKonflikte (Message, StartZeitstempel, webChannel) VALUES (?, ?, ?)", (dbMessage, int(start_unixtime), webChannel))
					if vomMerkzettel:
						self.countTimerFromWishlist += 1
						writeLog(_("[Serien Recorder] ' %s ' - Timer (vom Merkzettel) wurde deaktiviert angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, label_serie, stbChannel), True)
						cCursor.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND Staffel=? AND LOWER(Episode)=?", (serien_name.lower(), staffel, episode.lower()))
						dbSerRec.commit()	
						cCursor.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND Staffel=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (serien_name.lower(), staffel, episode.lower()))
						dbSerRec.commit()
					else:
						writeLog(_("[Serien Recorder] ' %s ' - Timer wurde deaktiviert angelegt%s -> %s %s @ %s") % (label_serie, optionalText, show_start, label_serie, stbChannel), True)
					cCursor.close()
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

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit):
		(margin_before, margin_after) = getMargins(serien_name, webChannel)
		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ServiceRef=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		#sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ?<=StartZeitstempel<=?"
		cCursor.execute(sql, (serien_name.lower(), stbRef, int(start_time) + (int(margin_before) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(margin_before) * 60) + (int(EPGTimeSpan) * 60)))
		row = cCursor.fetchone()
		if row:
			sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=? WHERE LOWER(Serie)=? AND ServiceRef=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
			cCursor.execute(sql, (eit, serien_name.lower(), stbRef, int(start_time) + (int(margin_before) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(margin_before) * 60) + (int(EPGTimeSpan) * 60)))
			print "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", _("[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			print "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", _("[Serien Recorder] Timer angelegt: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		dbSerRec.commit()
		cCursor.close()
		
	def dataError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog(_("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)") % error, True)

	def checkError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog(_("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)") % error, True)
		self.close()

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
				if vpsSettings == 0:
					timer.vpsplugin_enabled = False
					timer.vpsplugin_overwrite = False
				elif vpsSettings == 1:
					timer.vpsplugin_enabled = True
					timer.vpsplugin_overwrite = True
				elif vpsSettings == 2:
					timer.vpsplugin_enabled = True
					timer.vpsplugin_overwrite = False

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

class serienRecMain(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()
		
		# Skin
		self.skinName = "SerienRecorderMain"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRMain.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["HelpActions", "OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions", "SerienRecorderActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"red"	: self.keyRed,
			"green"	: self.keyGreen,
			"yellow": self.keyYellow,
			"blue"	: self.keyBlue,
			"info" 	: self.keyCheck,
			"menu"	: self.recSetup,
			"nextBouquet" : self.nextPage,
			"prevBouquet" : self.backPage,
			"displayHelp" : self.youtubeSearch,
			"about" : self.showAbout,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB,
			"4"		: self.serieInfo,
			"6"		: self.showConflicts,
			"9"     : self.importFromFile,
			"5"		: self.test
		}, -2)

		initDB()
	
		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
		self['list'] = self.chooseMenuList
		self.modus = "list"
		self.ErrorMsg = _("unbekannt")
		
		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList_popup.l.setItemHeight(30)
		self['popup'] = self.chooseMenuList_popup
		self['popup'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()
		
		self['exit'] = Pixmap()
		#self['exit'].hide()
		self['epg'] = Pixmap()
		#self['epg'].hide()
		self['info'] = Pixmap()
		#self['info'].hide()
		self['menu'] = Pixmap()
		#self['menu'].hide()
		self['0'] = Pixmap()
		self['1'] = Pixmap()
		self['3'] = Pixmap()
		self['4'] = Pixmap()
		self['6'] = Pixmap()
		
		self.displyTimer = eTimer()
		self.displyTimer.callback.append(self.updateMenuKeys)
		self.displyTimer.start(10000)
		self.displayMode = 0
		
		if config.plugins.serienRec.updateInterval.value == 24:
			config.plugins.serienRec.timeUpdate.value = True
			config.plugins.serienRec.update.value = False
		elif config.plugins.serienRec.updateInterval.value == 0: 
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = False
		else:
			config.plugins.serienRec.timeUpdate.value = False
			config.plugins.serienRec.update.value = True

		if int(config.plugins.serienRec.screenmode.value) == 0:
			self.pNeu = 0
		elif int(config.plugins.serienRec.screenmode.value) == 1:
			self.pNeu = 1
		elif int(config.plugins.serienRec.screenmode.value) == 2:
			self.pNeu = 2

		self.pRegional = 0
		self.pPaytv = 1		
		self.pPrime = 1
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.color_print = "\033[93m"
		self.color_end = "\33[0m"
		self.page = 0

		self['cover'] = Pixmap()
		self['title'] = Label(_("Lade infos from Web..."))
		self['headline'] = Label("")
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['red'] = Label(_("Anzeige-Modus"))
		self['green'] = Label(_("Channels zuweisen"))
		self['ok'] = Label(_("Marker hinzufügen"))
		self['yellow'] = Label(_("Serien Marker"))
		self['blue'] = Label(_("Timer-Liste"))
		self['text0'] = Label(_("Zeige Log"))
		self['text1'] = Label(_("Added Liste"))
		self['text3'] = Label(_("Neue Serienstarts"))
		self['text4'] = Label(_("Serien Beschreibung"))
		self['text6'] = Label(_("Konflikt-Liste"))

		#self.onLayoutFinish.append(self.startScreen)
		self.onFirstExecBegin.append(self.startScreen)

	def updateMenuKeys(self):	
		if self.displayMode == 0:
			self['0'].hide()
			self['1'].hide()
			self['3'].hide()
			self['4'].hide()
			self['6'].hide()
			#self['exit'].show()
			#self['epg'].show()
			#self['info'].show()
			#self['menu'].show()
			self['text0'].setText(_("Abbrechen"))
			self['text1'].hide()
			self['text3'].setText(_("Timer suchen"))
			if epgTranslatorInstalled:
				self['text4'].setText(_("YouTube-Suche"))
			else:
				self['text4'].setText(_("About"))
			self['text6'].setText(_("globale Einstellungen"))
			self.displayMode = 1
		else:
			#self['exit'].hide()
			#self['epg'].hide()
			#self['info'].hide()
			#self['menu'].hide()
			self['0'].show()
			self['1'].show()
			self['3'].show()
			self['4'].show()
			self['6'].show()
			self['text0'].setText(_("Zeige Log"))
			self['text1'].show()
			self['text3'].setText(_("Neue Serienstarts"))
			self['text4'].setText(_("Serien Beschreibung"))
			self['text6'].setText(_("Konflikt-Liste"))
			self.displayMode = 0
		
	def test(self):
		check = self['list'].getCurrent()
		if check == None:
			return

		serien_id = self['list'].getCurrent()[0][14]
		url = "http://www.wunschliste.de/%s/links" % serien_id
		print url
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink2).addErrback(self.dataError)
			
	def getImdblink2(self, data):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			print ilink
			self.session.open(serienRecShowImdbVideos, ilink[0])

	def importFromFile(self):
		initDB()
		self['title'].setText(_("File-Import erfolgreich ausgeführt"))
		self['title'].instance.setForegroundColor(parseColor("white"))

	def serieInfo(self):
		check = self['list'].getCurrent()
		if check == None:
			return
		serien_url = self['list'].getCurrent()[0][5]
		serien_name = self['list'].getCurrent()[0][6]
		serien_id = self['list'].getCurrent()[0][14]

		self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de%s" % serien_url)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def youtubeSearch(self):
		if epgTranslatorInstalled:
			if self.modus == "list":
				if self.loading:
					return

			check = self['list'].getCurrent()
			if check == None:
				return

			serien_name = self['list'].getCurrent()[0][6]
			print "[Serien Recorder] starte youtube suche für %s" % serien_name
			self.session.open(searchYouTube, serien_name)
		else:
			self.session.open(serienRecAboutScreen)

	def showAbout(self):
		self.session.open(serienRecAboutScreen)
	
	def setHeadline(self):
		# aktuelle internationale Serien
		if int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 0
			self['headline'].setText(_("Alle Serien (aktuelle internationale Serien)"))
		elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 1
			self['headline'].setText(_("Neue Serien aktuelle (internationale Serien)"))
		elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 2
			self['headline'].setText(_("Nach aktivierten Sendern (aktuelle internationale Serien)"))
		## E01
		elif int(config.plugins.serienRec.screenmode.value) == 3 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 3
			self['headline'].setText(_("Alle Serienstarts"))
		# soaps
		#elif int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 0
		#	self['headline'].setText(_("Alle Serien (Soaps)"))
		#elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 1
		#	self['headline'].setText(_("Neue Serien ((Soaps)"))
		#elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 2
		#	self['headline'].setText(_("Nach aktivierten Sendern (Soaps)"))
		# internationale Serienklassiker
		elif int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 0
			self['headline'].setText(_("Alle Serien (internationale Serienklassiker)"))
		elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 1
			self['headline'].setText(_("Neue Serien (internationale Serienklassiker)"))
		elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 2
			self['headline'].setText(_("Nach aktivierten Sendern (internationale Serienklassiker)"))
		self['headline'].instance.setForegroundColor(parseColor("red"))

	def recSetup(self):
		self.session.openWithCallback(self.setupClose, serienRecSetup)

	def setupClose(self, result):
		if result and config.plugins.serienRec.update.value:
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer: %s" % config.plugins.serienRec.update.value +self.color_end
			serienRecCheckForRecording(self.session, False)
		elif result and config.plugins.serienRec.timeUpdate.value:
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer: %s" % config.plugins.serienRec.timeUpdate.value +self.color_end
			serienRecCheckForRecording(self.session, False)
		elif result and not config.plugins.serienRec.update.value:
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer: %s" % config.plugins.serienRec.update.value +self.color_end
		elif result and not config.plugins.serienRec.timeUpdate.value:
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer: %s" % config.plugins.serienRec.timeUpdate.value +self.color_end
		
	def startScreen(self):
		print "[Serien Recorder] version %s is running..." % config.plugins.serienRec.showversion.value
		if config.plugins.serienRec.Autoupdate.value:
			checkupdate(self.session).checkforupdate()
		self.dayChache = {}
		if self.isChannelsListEmpty():
			print "[Serien Recorder] Channellist is empty !"
			self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		else:
			self.readWebpage()

	def readWebpage(self, answer=True):
		if answer:
			self['title'].instance.setForegroundColor(parseColor("white"))
			self['title'].setText(_("Lade Infos vom Web..."))
			self.loading = True
			url = "http://www.wunschliste.de/serienplaner/%s/%s" % (str(config.plugins.serienRec.screeplaner.value), str(self.page))
			print url
			self.setHeadline()

			#date = datetime.datetime.now()
			#date += datetime.timedelta(days=self.page)
			#key = '%s.%s.' % (str(date.day).zfill(2), str(date.month).zfill(2))
			#if key in self.dayChache:
			#	self.parseWebpage(self.dayChache[key])
			#else:
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseWebpage).addErrback(self.dataError)

	def parseWebpage(self, data):
		self.daylist = []
		head_datum = re.findall('<li class="datum">(.*?)</li>', data, re.S)
		#if head_datum:
		#	d = head_datum[0].split(',')
		#	d.reverse()
		#	d = d[0].split('.')
		#	key = '%s.%s.' % (d[0].strip().zfill(2), d[1].strip().zfill(2))
		#	self.dayChache.update({key:data})
		raw = re.findall('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', data, re.S)
		if raw:
			for regional,paytv,neu,prime,time,url,serien_name,serien_id,sender,staffel,episode,title in raw:
				if not str(staffel).isdigit():
					continue
				
				aufnahme = False
				serieAdded = False
				start_h = time[:+2]
				start_m = time[+3:]
				start_time = getUnixTimeWithDayOffset(start_h, start_m, self.page)
				
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				#sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				title = iso8859_Decode(title)
				self.ErrorMsg = "%s - S%sE%s - %s (%s)" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title, sender)
				
				cSender_list = self.checkSender(sender)
				
				if self.checkTimer(serien_name, staffel, episode, title, start_time, sender):
					aufnahme = True
				else:
					##############################
					#
					# try to get eventID (eit) from epgCache
					#
					if config.plugins.serienRec.intensiveTimersuche.value:
						if len(cSender_list) != 0:
							(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSender_list[0]

							(margin_before, margin_after) = getMargins(serien_name, webChannel)
							
							# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
							event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_time)+(int(margin_before) * 60), -1)], stbRef, serien_name, int(start_time)+(int(margin_before) * 60))
							#print "event matches %s" % len(event_matches)
							if event_matches and len(event_matches) > 0:
								for event_entry in event_matches:
									print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
									start_time_eit = int(event_entry[3])
									if self.checkTimer(serien_name, staffel, episode, title, start_time_eit, sender):
										aufnahme = True
										break

							if not aufnahme and (stbRef != altstbRef):
								event_matches = getEPGevent(['RITBDSE',(altstbRef, 0, int(start_time)+(int(margin_before) * 60), -1)], altstbRef, serien_name, int(start_time)+(int(margin_before) * 60))
								#print "event matches %s" % len(event_matches)
								if event_matches and len(event_matches) > 0:
									for event_entry in event_matches:
										print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
										start_time_eit = int(event_entry[3])
										if self.checkTimer(serien_name, staffel, episode, title, start_time_eit, sender):
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
				bereits_vorhanden = False
				if config.plugins.serienRec.sucheAufnahme.value:
					dirname = getDirname(serien_name, staffel)
					check_SeasonEpisode = "S%sE%s" % (staffel, episode)
					# check hdd
					if fileExists(dirname):
						dirs = os.listdir(dirname)
						for dir in dirs:
							if re.search('%s.*?%s.*?\.ts\Z' % (serien_name, check_SeasonEpisode), dir):
								bereits_vorhanden = True
								break

				title = "S%sE%s - %s" % (staffel, episode, title)
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
		self.loading = False
		
	def buildList(self, entry):
		(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id) = entry
		#entry = [(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id)]
		
		imageNone = "%simages/black.png" % serienRecMainPath
		imageNeu = "%simages/neu.png" % serienRecMainPath
		imageTimer = "%simages/timer.png" % serienRecMainPath
		imageHDD = "%simages/hdd_24x24.png" % serienRecMainPath
		
		if serieAdded:
			setFarbe = self.green
		else:
			setFarbe = self.white
			if str(episode).isdigit():
				if int(episode) == 1:
					setFarbe = self.red

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
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 5, 80, 40, picon),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340, 7, 30, 22, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 340, 30, 30, 22, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 110, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 110, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 7, 30, 22, loadPNG(imageNeu)),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 30, 30, 22, loadPNG(imageHDDTimer)),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]

	def keyOK(self):
		if self.modus == "list":
			if self.loading:
				return

			check = self['list'].getCurrent()
			if check == None:
				return

			serien_neu = self['list'].getCurrent()[0][2]
			serien_url = self['list'].getCurrent()[0][5]
			serien_name = self['list'].getCurrent()[0][6]
			serien_id = self['list'].getCurrent()[0][14]

			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (serien_name.lower(),))
			row = cCursor.fetchone()
			if not row:
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (serien_name, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id))
				self['title'].setText(_("Serie '- %s -' zum Serien Marker hinzugefügt.") % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
			else:
				self['title'].setText(_("Serie '- %s -' existiert bereits im Serien Marker.") % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))
			dbSerRec.commit()
			cCursor.close()

		elif self.modus == "popup":
			status = self['popup'].getCurrent()[0][0]
			planer_id = self['popup'].getCurrent()[0][1]
			name = self['popup'].getCurrent()[0][2]
			print status, planer_id, name

			self['popup'].hide()
			self['popup_bg'].hide()
			self['list'].show()
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
		
		check = self['list'].getCurrent()
		if check == None:
			return

		url = self['list'].getCurrent()[0][5]
		serien_name = self['list'].getCurrent()[0][6]

		serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name

		if not fileExists("/tmp/serienrecorder/"):
			shutil.os.mkdir("/tmp/serienrecorder/")
		if fileExists(serien_nameCover):
			self.showCover(serien_nameCover, serien_nameCover)
		else:
			url = "http://www.wunschliste.de%s/links" % url
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink, serien_nameCover).addErrback(self.dataError)

	def getImdblink(self, data, serien_nameCover):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			getPage(ilink[0], headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.loadImdbCover, serien_nameCover).addErrback(self.dataError)
		else:
			print "[Serien Recorder] es wurde kein imdb-link für ein cover gefunden."

	def loadImdbCover(self, data, serien_nameCover):
		imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
		if imageLink_raw:
			#imageLink = re.findall('(http://ia.media-imdb.com/.*?)\.', imageLink_raw[0])
			print imageLink_raw
			extra_imdb_convert = "@._V1_SX320.jpg"
			aufgeteilt = imageLink_raw[0].split('._V1._')
			imdb_url = "http://ia.media-imdb.com/%s._V1._SX420_SY420_.jpg" % aufgeteilt[0]
			print imdb_url
			downloadPage(imdb_url, serien_nameCover).addCallback(self.showCover, serien_nameCover).addErrback(self.dataError)

	def showCover(self, data, serien_nameCover):
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("Coverfile not found: %s" %  serien_nameCover)

	def keyRed(self):
		if self.modus == "list":
			self.popup_list = []
			# aktuelle internationale Serien
			self.popup_list.append(('0', '1', _('Alle Serien (aktuelle internationale Serien)')))
			self.popup_list.append(('1', '1', _('Neue Serien (aktuelle internationale Serien)')))
			self.popup_list.append(('2', '1', _('Nach aktivierten Sendern (aktuelle internationale Serien)')))
			# soaps
			#self.popup_list.append(('0', '2', _('Alle Serien (Soaps)')))
			#self.popup_list.append(('1', '2', _('Neue Serien (Soaps)')))
			#self.popup_list.append(('2', '2', _('Nach aktivierten Sendern (Soaps)')))
			# internationale Serienklassiker
			self.popup_list.append(('0', '3', _('Alle Serien (internationale Serienklassiker)')))
			self.popup_list.append(('1', '3', _('Neue Serien (internationale Serienklassiker)')))
			self.popup_list.append(('2', '3', _('Nach aktivierten Sendern (internationale Serienklassiker)')))
			# E01
			self.popup_list.append(('3', '1', _('Alle Serienstarts')))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.popup_list))
			self['popup_bg'].show()
			self['popup'].show()
			self['list'].hide()
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

	def checkTimer(self, serie, staffel, episode, title, start_time, webchannel):
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
		#self.session.open(serienRecMainChannelEdit)
		self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		
	def keyYellow(self):
		#self.session.open(serienRecMarker)
		self.session.openWithCallback(self.readWebpage, serienRecMarker)
		
	def keyBlue(self):
		#self.session.open(serienRecTimer)
		self.session.openWithCallback(self.readWebpage, serienRecTimer)

	def keyCheck(self):
#		self.session.open(serienRecLogReader, True)
		self.session.openWithCallback(self.readWebpage, serienRecLogReader, True)
		
	def keyLeft(self):
		if self.modus == "list":
			self['list'].pageUp()
			self.getCover()
		else:
			self['popup'].pageUp()

	def keyRight(self):
		if self.modus == "list":
			self['list'].pageDown()
			self.getCover()
		else:
			self['popup'].pageDown()

	def keyDown(self):
		if self.modus == "list":
			self['list'].down()
			self.getCover()
		else:
			self['popup'].down()

	def keyUp(self):
		if self.modus == "list":
			self['list'].up()
			self.getCover()
		else:
			self['popup'].up()

	def nextPage(self):
		self.page += 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self.readWebpage()

	def backPage(self):
		if not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self.readWebpage()

	def keyCancel(self):
		if self.modus == "list":
			try:
				self.displyTimer.stop()
			except:
				pass
			self.close()
		elif self.modus == "popup":
			self['popup'].hide()
			self['popup_bg'].hide()
			self['list'].show()
			self.modus = "list"

	def dataError(self, error):
		self['title'].setText(_("Suche auf 'Wunschliste.de' erfolglos"))
		self['title'].instance.setForegroundColor(parseColor("white"))
		writeLog(_("[Serien Recorder] Fehler bei: %s") % self.ErrorMsg, True)
		print "[Serien Recorder] Fehler bei: %s" % self.ErrorMsg
		#print "[Serien Recorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
		print error

class serienRecMainChannelEdit(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()

		# Skin
		self.skinName = "SerienRecorderMainChannelEdit"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRMainChannelEdit.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"menu"  : self.channelSetup,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label(_("Lade Web-Channel / STB-Channels..."))
		self['red'] = Label(_("Sender An/Aus-Schalten"))
		self['ok'] = Label(_("Sender Auswählen"))
		self['green'] = Label(_("Reset Senderliste"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['0'] = Label(_("Zeige Log"))
		self['1'] = Label(_("Added Liste"))
		self['3'] = Label(_("Neue Serienstarts"))
		
		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		# popup2
		self.chooseMenuList_popup2 = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup2.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup2.l.setItemHeight(25)
		self['popup_list2'] = self.chooseMenuList_popup2
		self['popup_list2'].hide()
		
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()
		self.modus = "list"
		self.changesMade = False

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

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

	def channelSetup(self):
		webSender = self['list'].getCurrent()[0][0]
		self.session.open(serienRecChannelSetup, webSender)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showChannels(self):
		self.serienRecChlist = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels")
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
					#web_chlist.append((station.replace('\xdf','ß').replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')))
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
					#print webSender
					cCursor.execute("SELECT * FROM Channels WHERE LOWER(WebChannel)=?", (webSender.lower(),))
					row = cCursor.fetchone()
					if not row:
						found = False
						for servicename,serviceref in self.stbChlist:
							#print servicename
							if re.search(webSender.lower(), servicename.lower(), re.S):
								cCursor.execute(sql, (webSender, servicename, serviceref, 1))
								#print webSender, servicename
								self.serienRecChlist.append((webSender, servicename, "", "1"))
								found = True
								break
						if not found:
							cCursor.execute(sql, (webSender, "", "", 0))
							self.serienRecChlist.append((webSender, "", "", "0"))
						self.changesMade = True
				dbSerRec.commit()
				cCursor.close()
			else:
				print "[SerienRecorder] webChannel list leer.."

			if len(self.serienRecChlist) != 0:
				#self['title'].setText("Web-Channel / STB-Channels.")
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
			(eListboxPythonMultiContent.TYPE_TEXT, 600, 3, 250, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, altstbSender, self.yellow)
			]

	def buildList_popup(self, entry):
		(servicename,serviceref) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 100, 0, 250, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, servicename)
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
			cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE WebChannel=?", (self['list'].getCurrent()[0][0],))
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
				cCursor.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE WebChannel=?", (self['list'].getCurrent()[0][0],))
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
				if stbSender != "" and altstbSender != "":
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 1, chlistSender.lower()))
				else:
					cCursor.execute(sql, (stbSender, stbRef, altstbSender, altstbRef, 0, chlistSender.lower()))
				self.changesMade = True
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
					self['title'].setText("Sender '- %s -' wurde aktiviert." % webSender)
				else:
					cCursor.execute(sql, (0, chlistSender.lower()))
					print "[SerienRecorder] change to:",webSender, servicename, serviceref, "0"
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("")
					self['title'].setText(_("Sender '- %s -' wurde deaktiviert.") % webSender)
				self.changesMade = True
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

	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			#self['popup_list2'].hide()
			self['popup_bg'].hide()
		elif self.modus == "popup_list2":
			self.modus = "list"
			#self['popup_list'].hide()
			self['popup_list2'].hide()
			self['popup_bg'].hide()
		else:
			self.close(self.changesMade)
			
	def dataError(self, error):
		print error

class serienRecMarker(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()

		# Skin
		self.skinName = "SerienRecorderMarker"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRMarker.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"yellow": self.keyYellow,
			"blue"	: self.keyBlue,
			"info"	: self.keyCheck,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"menu" : self.markerSetup,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB,
			"4"		: self.addToWishlist
		}, -1)

		#normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(70)
		self['list'] = self.chooseMenuList

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()
		
		self.modus = "list"
		self['title'] = Label("")
		self['red'] = Label(_("Entferne Serie(n) Marker"))
		self['green'] = Label(_("Sender auswählen."))
		self['ok'] = Label(_("Staffel(n) auswählen."))
		self['yellow'] = Label(_("Sendetermine"))
		self['blue'] = Label(_("Serie Suchen"))
		self['cover'] = Pixmap()
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['0'] = Label(_("Zeige Log"))
		self['1'] = Label(_("Added Liste"))
		self['3'] = Label(_("Neue Serienstarts"))
		self['4'] = Label(_("Merkzettel"))

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

		self.changesMade = False
		self.searchTitle = ""
		self.serien_nameCover = "nix"
		self.loading = True
		self.onLayoutFinish.append(self.readSerienMarker)

	def markerSetup(self):
		serien_name = self['list'].getCurrent()[0][0]
		self.session.openWithCallback(self.SetupFinished, serienRecMarkerSetup, serien_name)

	def SetupFinished(self, result):
		self.readSerienMarker()
		return
		
	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def addToWishlist(self):
		self.session.open(serienRecWishlist)

	def getCover(self):
		if self.loading:
			return
		
		check = self['list'].getCurrent()
		if check == None:
			return

		serien_name = self['list'].getCurrent()[0][0]
		url = self['list'].getCurrent()[0][1]

		serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name

		if not fileExists("/tmp/serienrecorder/"):
			shutil.os.mkdir("/tmp/serienrecorder/")
		if fileExists(serien_nameCover):
			self.showCover(serien_nameCover, serien_nameCover)
		else:
			id = url.strip('http://www.wunschliste.de/epg_print.pl?s=')
			url = "http://www.wunschliste.de/%s/links" % id
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink, serien_nameCover).addErrback(self.dataError)

	def getImdblink(self, data, serien_nameCover):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			getPage(ilink[0], headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.loadImdbCover, serien_nameCover).addErrback(self.dataError)
		else:
			print "[Serien Recorder] es wurde kein imdb-link für ein cover gefunden."

	def loadImdbCover(self, data, serien_nameCover):
		imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
		if imageLink_raw:
			#imageLink = re.findall('(http://ia.media-imdb.com/.*?)\.', imageLink_raw[0])
			print imageLink_raw
			extra_imdb_convert = "@._V1_SX320.jpg"
			aufgeteilt = imageLink_raw[0].split('._V1._')
			imdb_url = "http://ia.media-imdb.com/%s._V1._SX420_SY420_.jpg" % aufgeteilt[0]
			print imdb_url
			downloadPage(imdb_url, serien_nameCover).addCallback(self.showCover, serien_nameCover).addErrback(self.dataError)

	def showCover(self, data, serien_nameCover):
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("Coverfile not found: %s" %  serien_nameCover)
		self.serien_nameCover = serien_nameCover

	def readSerienMarker(self):
		markerList = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker ORDER BY Serie")
		cMarkerList = cCursor.fetchall()
		for row in cMarkerList:
			(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlAufnahmen, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) = row
			if alleSender:
				sender = ['Alle',]
			else:
				sender = []
				cSender = dbSerRec.cursor()
				cSender.execute("SELECT ErlaubterSender FROM SenderAuswahl WHERE ID=? ORDER BY ErlaubterSender", (ID,))
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
			markerList.append((Serie, Url, str(staffeln).replace("[","").replace("]","").replace("'","").replace('"',""), str(sender).replace("[","").replace("]","").replace("'","").replace('"',""), AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, bool(useAlternativeChannel)))
				
		cCursor.close()
		self['title'].setText(_("Serien Marker - %s Serien vorgemerkt.") % len(markerList))
		if len(markerList) != 0:
			#markerList.sort()
			self.chooseMenuList.setList(map(self.buildList, markerList))
			self.loading = False
			self.getCover()

	def buildList(self, entry):
		(serie, url, staffeln, sendern, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel) = entry
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
				
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 750, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, self.yellow, self.yellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Staffel: %s") % staffeln),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Sender (%s): %s") % (SenderText, sendern)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 49, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Wdh./Vorl./Nachl.: %s / %s / %s") % (int(AnzahlAufnahmen) - 1, int(Vorlaufzeit), int(Nachlaufzeit))),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 49, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("Dir: %s") % AufnahmeVerzeichnis)
			]

	def keyCheck(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Marker leer."
			return

		if self.modus == "list":
			self.session.open(serienRecLogReader, True)

	def keyOK(self):
		if self.modus == "popup_list":
			self.select_serie = self['list'].getCurrent()[0][0]
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
			self.select_serie = self['list'].getCurrent()[0][0]
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
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return

			self.modus = "popup_list"
			self.select_serie = self['list'].getCurrent()[0][0]
			self['popup_list'].show()
			self['popup_bg'].show()
			
			staffeln = [_('Manuell'),_('Alle'),_('Specials'),_('folgende')]
			staffeln.extend(range(config.plugins.serienRec.max_season.value+1))
			mode_list = [0,]*len(staffeln)
			index_list = range(len(staffeln))
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
			row = cCursor.fetchone()
			if row:
				(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, self.AbEpisode, Staffelverzeichnis, TimerForSpecials) = row
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
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 4, 30, 17, loadPNG(imageMode)),
			(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 500, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(staffel).zfill(2))
			]

	def keyGreen(self):
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return

			getSender = getWebSenderAktiv()
			if len(getSender) != 0:
				self.modus = "popup_list2"
				self['popup_list'].show()
				self['popup_bg'].show()
				self.select_serie = self['list'].getCurrent()[0][0]

				getSender.insert(0, 'Alle')
				mode_list = [0,]*len(getSender)
				index_list = range(len(getSender))
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
				row = cCursor.fetchone()
				if row:
					(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) = row
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
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				return

			serien_name = self['list'].getCurrent()[0][0]
			serien_url = self['list'].getCurrent()[0][1]

			print "teestt"
			#serien_url = getUrl(serien_url.replace('epg_print.pl?s=',''))
			print serien_url
			#self.session.open(serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)
			self.session.openWithCallback(self.callTimerAdded, serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)

	def callSaveMsg(self, answer):
		if answer:
			self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Added Liste entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
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
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return
			else:
				self.selected_serien_name = self['list'].getCurrent()[0][0]
				cCursor = dbSerRec.cursor()
				cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.selected_serien_name.lower(),))
				row = cCursor.fetchone()
				if row:
					print "gefunden."
					if config.plugins.serienRec.confirmOnDelete.value:
						self.session.openWithCallback(self.callSaveMsg, MessageBox, _("Soll '%s' wirklich entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)
					else:
						self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Added Liste entfernt werden?") % self.selected_serien_name, MessageBox.TYPE_YESNO, default = False)

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
		cCursor.execute("UPDATE OR IGNORE SerienMarker SET alleSender=? WHERE LOWER(Serie)=?", (alleSender, self.select_serie.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.readSerienMarker()

	def keyBlue(self):
		if self.modus == "list":
			self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Serien Titel eingeben:")), text = self.searchTitle)

	def wSearch(self, serien_name):
		if serien_name:
			print serien_name
			self.changesMade = True
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

#	def getCover(self):
#		if self.modus == "list":
#			check = self['list'].getCurrent()
#			if check == None:
#				return
#
#			serien_name = self['list'].getCurrent()[0][0]
#			serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name
#
#			if fileExists(serien_nameCover):
#				self.showCover(serien_nameCover, serien_nameCover)
#
#	def showCover(self, data, serien_nameCover):
#		if fileExists(serien_nameCover):
#			self['cover'].instance.setPixmap(gPixmapPtr())
#			scale = AVSwitch().getFramebufferScale()
#			size = self['cover'].instance.size()
#			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
#			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
#				ptr = self.picload.getData()
#				if ptr != None:
#					self['cover'].instance.setPixmap(ptr)
#					self['cover'].show()
#		else:
#			print("Coverfile not found: %s" %  serien_nameCover)
#
#		self.serien_nameCover = serien_nameCover

	def selectEpisode(self, episode):
		if str(episode).isdigit():
			print episode
			cCursor = dbSerRec.cursor()
			cCursor.execute("UPDATE OR IGNORE SerienMarker SET AbEpisode=? WHERE LOWER(Serie)=?", (int(episode), self.select_serie.lower()))
			dbSerRec.commit()
			cCursor.close
		self.insertStaffelMarker()
			
	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			if (self.staffel_liste[0][1] == 0) and (self.staffel_liste[1][1] == 0) and (self.staffel_liste[4][1] == 1):		# nicht ('Manuell' oder 'Alle') und '00'
				self.session.openWithCallback(self.selectEpisode, VirtualKeyBoard, title = (_("Episode eingeben ab der Timer erstellt werden sollen:")), text = str(self.AbEpisode))
			else:
				self.insertStaffelMarker()
		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.insertSenderMarker()
		else:
			self.close(self.changesMade)

	def dataError(self, error):
		print error

class serienRecAddSerie(Screen):
	def __init__(self, session, serien_name):
		Screen.__init__(self, session)
		self.session = session
		self.serien_name = serien_name
		self.picload = ePicLoad()

		# Skin
		self.skinName = "SerienRecorderAddSerie"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRAddSerie.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"red"	: self.keyRed,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)

		# search
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label(_("Abbrechen"))
		self['green'] = Label("")
		self['ok'] = Label(_("Hinzufügen"))
		self['cover'] = Pixmap()
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['0'] = Label(_("Zeige Log"))
		self['1'] = Label(_("Added Liste"))
		self['3'] = Label(_("Neue Serienstarts"))

		self.loading = True

		self.onLayoutFinish.append(self.searchSerie)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

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
					#print name_Serie, year_Serie, id_Serie
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
			(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, name_Serie),
			(eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, year_Serie)
			]

	def keyOK(self):
		if self.loading:
			return

		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] keine infos gefunden"
			return

		Serie = self['list'].getCurrent()[0][0]
		Year = self['list'].getCurrent()[0][1]
		Id = self['list'].getCurrent()[0][2]
		print Serie, Year, Id

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (Serie.lower(),))
		row = cCursor.fetchone()	
		if not row:
			Url = 'http://www.wunschliste.de/epg_print.pl?s='+str(Id)
			cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, -2, 1, 1, -1, 0, -1, 0)", (Serie, Url))
			self['title'].setText(_("Serie '- %s -' zum Serien Marker hinzugefügt.") % Serie)
			self['title'].instance.setForegroundColor(parseColor("green"))
		else:
			self['title'].setText(_("Serie '- %s -' existiert bereits im Serien Marker.") % Serie)
			self['title'].instance.setForegroundColor(parseColor("red"))
		dbSerRec.commit()
		cCursor.close()

	def keyRed(self):
		self.close()

	def keyLeft(self):
		self['list'].pageUp()
		self.getCover()

	def keyRight(self):
		self['list'].pageDown()
		self.getCover()

	def keyDown(self):
		self['list'].down()
		self.getCover()

	def keyUp(self):
		self['list'].up()
		self.getCover()

	def getCover(self):
		if self.loading:
			return
		
		check = self['list'].getCurrent()
		if check == None:
			return

		serien_name = self['list'].getCurrent()[0][0]
		xId = self['list'].getCurrent()[0][2]
		serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name

		serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name
		if not fileExists("/tmp/serienrecorder/"):
			shutil.os.mkdir("/tmp/serienrecorder/")
		if fileExists(serien_nameCover):
			self.showCover(serien_nameCover, serien_nameCover)
		else:
			url = "http://www.wunschliste.de/%s/links" % xId
			getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink, serien_nameCover).addErrback(self.dataError)

	def getImdblink(self, data, serien_nameCover):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			getPage(ilink[0], headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.loadImdbCover, serien_nameCover).addErrback(self.dataError)
		else:
			print "[Serien Recorder] es wurde kein imdb-link für ein cover gefunden."

	def loadImdbCover(self, data, serien_nameCover):
		#imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
		#if imageLink_raw:
		#	#imageLink = re.findall('(http://ia.media-imdb.com/.*?)\.', imageLink_raw[0])
		#	print imageLink_raw
		#	extra_imdb_convert = "._V1_SX320.jpg"
		#	imdb_url = "http://ia.media-imdb.com/%s%s" % (imageLink_raw[0], extra_imdb_convert)
		#	print imdb_url
		#	downloadPage(imdb_url, serien_nameCover).addCallback(self.showCover, serien_nameCover).addErrback(self.dataError)
			
		imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
		if imageLink_raw:
			#imageLink = re.findall('(http://ia.media-imdb.com/.*?)\.', imageLink_raw[0])
			print imageLink_raw
			extra_imdb_convert = "@._V1_SX320.jpg"
			aufgeteilt = imageLink_raw[0].split('._V1._')
			imdb_url = "http://ia.media-imdb.com/%s._V1._SX420_SY420_.jpg" % aufgeteilt[0]
			print imdb_url
			downloadPage(imdb_url, serien_nameCover).addCallback(self.showCover, serien_nameCover).addErrback(self.dataError)

	def showCover(self, data, serien_nameCover):
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("Coverfile not found: %s" %  serien_nameCover)

	def keyCancel(self):
		self['title'].instance.setForegroundColor(parseColor("white"))
		self.close()

	def dataError(self, error):
		print error

class serienRecSendeTermine(Screen):
	def __init__(self, session, serien_name, serie_url, serien_cover):
		Screen.__init__(self, session)
		self.session = session
		self.serien_name = serien_name
		self.serie_url = serie_url
		self.serien_cover = serien_cover
		self.picload = ePicLoad()

		# Skin
		self.skinName = "SerienRecorderSendeTermine"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRSendeTermine.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"yellow": self.keyYellow,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)
		
		# termine
		self.chooseMenuList2 = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList2.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList2.l.setItemHeight(50)
		self['termine'] = self.chooseMenuList2
		#self['termine'].hide()

		self['title'] = Label(_("Lade Web-Channel / STB-Channels..."))
		self['red'] = Label("")
		self['green'] = Label("")
		self['yellow'] = Label("")
		self['ok'] = Label(_("Auswahl"))
		self['cover'] = Pixmap()
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['0'] = Label(_("Zeige Log"))
		self['1'] = Label(_("Added Liste"))
		self['3'] = Label(_("Neue Serienstarts"))

		self.changesMade = False

		self.sendetermine_list = []
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.loading = True
		self.FilterEnabled = True
		
		self.onLayoutFinish.append(self.searchSerie)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def searchSerie(self):
		if not self.serien_cover == "nix":
			self.showCover(self.serien_cover)
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText(_("Suche ' %s '") % self.serien_name)
		print self.serie_url
		getPage(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.resultsTermine, self.serien_name).addErrback(self.dataError)

	def resultsTermine(self, data, serien_name):
		parsingOK = False
		self.sendetermine_list = []

		raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		
		#if raw:
		#	parsingOK = True
		#	#print "raw"
		#else:
		#	raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#	if raw2:
		#		raw = []
		#		for each in raw2:
		#			#print each
		#			each = list(each)
		#			each.insert(4, "0")
		#			raw.append(each)
		#		parsingOK = True
		#		#print "raw2"

		raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((?!(.*?x))(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		raw.extend([(a,b,c,d,'0',f,g) for (a,b,c,d,e,f,g) in raw2])
		if raw:
			parsingOK = True
			#print "raw"

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
				#sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','')
				title = iso8859_Decode(title)

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
					
				self.sendetermine_list.append([serien_name, sender, datum, startzeit, endzeit, str(staffel).zfill(2), str(episode).zfill(2), title, "0"])

			self['green'].setText(_("Timer erstellen"))
			
		self['red'].setText(_("Abbrechen"))
		if self.FilterEnabled:
			self['yellow'].setText(_("Filter ausschalten"))
			txt = _("gefiltert")
		else:
			self['yellow'].setText(_("Filter einschalten"))
			txt = _("alle")
		
		self.chooseMenuList2.setList(map(self.buildList_termine, self.sendetermine_list))
		self.loading = False
		self['title'].setText(_("%s Sendetermine für ' %s ' gefunden. (%s)") % (str(len(self.sendetermine_list)), self.serien_name, txt))

	def buildList_termine(self, entry):
		#(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry
		(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry

		check_SeasonEpisode = "S%sE%s" % (staffel, episode)
		dirname = getDirname(serien_name, staffel)
		
		imageMinus = "%simages/minus.png" % serienRecMainPath
		imagePlus = "%simages/plus.png" % serienRecMainPath
		imageNone = "%simages/black.png" % serienRecMainPath
		imageHDD = "%simages/hdd.png" % serienRecMainPath
		imageTimer = "%simages/timerlist.png" % serienRecMainPath
		imageAdded = "%simages/added.png" % serienRecMainPath

		#check 1 (hdd)
		bereits_vorhanden = False
		rightImage = imageNone
		if fileExists(dirname):
			dirs = os.listdir(dirname)
			for dir in dirs:
				if re.search(serien_name+'.*?'+check_SeasonEpisode+'.*?\.ts\Z', dir):
					bereits_vorhanden = True
					rightImage = imageHDD
					break

		if not bereits_vorhanden:
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
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 15, 16, 16, loadPNG(leftImage)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "%s %s" % (datum, start), self.yellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S%sE%s - %s" % (staffel, episode, title), self.yellow),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, loadPNG(rightImage))
			]

	def getTimes(self):
		self.countTimer = 0
		if len(self.sendetermine_list) != 0:
			lt = time.localtime()
			self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)
			print "\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit
			writeLog(_("\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------") % self.uhrzeit, True)
			#writeLog("[Serien Recorder] LOG READER: '1/1'")
			for serien_name, sender, datum, startzeit, endzeit, staffel, episode, title, status in self.sendetermine_list:
				if int(status) == 1:
					# setze label string
					label_serie = "%s - S%sE%s - %s" % (serien_name, staffel, episode, title)
					
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
					# print startzeit, start_unixtime, endzeit, end_unixtime
					(margin_before, margin_after) = getMargins(serien_name, sender)
					start_unixtime = int(start_unixtime) - (int(margin_before) * 60)
					end_unixtime = int(end_unixtime) + (int(margin_after) * 60)

					# get VPS settings for channel
					vpsSettings = getVPS(sender)

					# erstellt das serien verzeichnis
					dirname = getDirname(serien_name, staffel)
					if not fileExists(dirname):
						print "[Serien Recorder] erstelle Subdir %s" % dirname
						writeLog(_("[Serien Recorder] erstelle Subdir: ' %s '") % dirname)
						os.makedirs(dirname)

					# überprüft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
					check_SeasonEpisode = "S%sE%s" % (staffel, episode)

					#check 1 (hdd)
					bereits_vorhanden = 0
					if fileExists(dirname):
						dirs = os.listdir(dirname)
						for dir in dirs:
							if re.search(serien_name+'.*?'+check_SeasonEpisode+'.*?\.ts\Z', dir):
								bereits_vorhanden += 1
					
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
						self.doTimer(params)
					else:
						writeLog(_("[Serien Recorder] Serie ' %s ' -> Staffel/Episode bereits vorhanden ' %s '") % (serien_name, check_SeasonEpisode))
						self.doTimer(params, config.plugins.serienRec.forceManualRecording.value)
						
			writeLog(_("[Serien Recorder] Es wurde(n) %s Timer erstellt.") % str(self.countTimer), True)
			print "[Serien Recorder] Es wurde(n) %s Timer erstellt." % str(self.countTimer)
			writeLog(_("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"), True)
			print "---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"
			self.session.open(serienRecLogReader, False)
		
		else:
			self['title'].setText(_("Keine Sendetermine ausgewählt."))
			print "[Serien Recorder] keine Sendetermine ausgewählt."

	def doTimer(self, params, answer=True):
		if answer:
			(serien_name, sender, startzeit, start_unixtime, margin_before, margin_after, end_unixtime, label_serie, staffel, episode, title, dirname, preferredChannel, useAlternativeChannel, vpsSettings) = params
			# check sender
			cSener_list = self.checkSender(sender)
			if len(cSener_list) == 0:
				webChannel = sender
				stbChannel = ""
				altstbChannel = ""
			else:
				(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = cSener_list[0]

			self.changesMade = True
			TimerOK = False
			if stbChannel == "":
				#print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel)
				writeLog(_("[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '") % (serien_name, webChannel))
			elif int(status) == 0:
				#print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel)
				writeLog(_("[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '") % (serien_name, webChannel))
			else:
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
				eit = 0
				start_unixtime_eit = start_unixtime
				end_unixtime_eit = end_unixtime
				if config.plugins.serienRec.eventid.value:
					# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
					event_matches = getEPGevent(['RITBDSE',(timer_stbRef, 0, int(start_unixtime_eit)+(int(margin_before) * 60), -1)], timer_stbRef, serien_name, int(start_unixtime_eit)+(int(margin_before) * 60))
					#print "event matches %s" % len(event_matches)
					if event_matches and len(event_matches) > 0:
						for event_entry in event_matches:
							print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
							eit = int(event_entry[1])
							start_unixtime_eit = int(event_entry[3]) - (int(margin_before) * 60)
							end_unixtime_eit = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
							break

				# versuche timer anzulegen
				if checkTuner(start_unixtime_eit, end_unixtime_eit):
					result = serienRecAddTimer.addTimer(self.session, timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), label_serie, "S%sE%s - %s" % (staffel, episode, title), eit, False, dirname, vpsSettings, None, recordfile=".ts")
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
					alt_eit = 0
					alt_start_unixtime_eit = start_unixtime
					alt_end_unixtime_eit = end_unixtime
					if config.plugins.serienRec.eventid.value:
						# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
						event_matches = getEPGevent(['RITBDSE',(timer_altstbRef, 0, int(alt_start_unixtime_eit)+(int(margin_before) * 60), -1)], timer_altstbRef, serien_name, int(alt_start_unixtime_eit)+(int(margin_before) * 60))
						#print "event matches %s" % len(event_matches)
						if event_matches and len(event_matches) > 0:
							for event_entry in event_matches:
								print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
								alt_eit = int(event_entry[1])
								alt_start_unixtime_eit = int(event_entry[3]) - (int(margin_before) * 60)
								alt_end_unixtime_eit = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
								break
				
					# versuche timer anzulegen
					if checkTuner(alt_start_unixtime_eit, alt_end_unixtime_eit):
						result = serienRecAddTimer.addTimer(self.session, timer_altstbRef, str(alt_start_unixtime_eit), str(alt_end_unixtime_eit), label_serie, "S%sE%s - %s" % (staffel, episode, title), alt_eit, False, dirname, vpsSettings, None, recordfile=".ts")
						if result["result"]:
							if self.addRecTimer(serien_name, staffel, episode, title, str(alt_start_unixtime_eit), timer_altstbRef, webChannel, alt_eit):
								self.countTimer += 1
								TimerOK = True
						else:
							writeLog(_("[Serien Recorder] ' %s ' - ACHTUNG! -> %s") % (label_serie, konflikt), True)
							result = serienRecAddTimer.addTimer(self.session, timer_stbRef, str(start_unixtime_eit), str(end_unixtime_eit), label_serie, "S%sE%s - %s" % (staffel, episode, title), eit, True, dirname, vpsSettings, None, recordfile=".ts")
							if result["result"]:
								if self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime_eit), timer_stbRef, webChannel, eit):
									self.countTimer += 1
									TimerOK = True
					else:
						print "[Serien Recorder] Tuner belegt: %s %s" % (label_serie, startzeit)
						writeLog(_("[Serien Recorder] Tuner belegt: %s %s") % (label_serie, startzeit), True)
					
	def keyOK(self):
		if self.loading:
			return

		check = self['termine'].getCurrent()
		if check == None:
			return

		sindex = self['termine'].getSelectedIndex()
		serie = self['termine'].getCurrent()[0][0]
		sender = self['termine'].getCurrent()[0][1]
		datum = self['termine'].getCurrent()[0][2]
		start = self['termine'].getCurrent()[0][3]
		staffel = self['termine'].getCurrent()[0][4]
		episode = self['termine'].getCurrent()[0][5]
		title = self['termine'].getCurrent()[0][6]

		if len(self.sendetermine_list) != 0:
			if int(self.sendetermine_list[sindex][8]) == 0:
				self.sendetermine_list[sindex][8] = "1"
			else:
				self.sendetermine_list[sindex][8] = "0"
			self.chooseMenuList2.setList(map(self.buildList_termine, self.sendetermine_list))

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

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit):
		result = False
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=?", (serien_name.lower(), start_time))
		row = cCursor.fetchone()
		if row:
			print "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLog(_("[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			dbSerRec.commit()
			print "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLog(_("[Serien Recorder] Timer angelegt: %s S%sE%s - %s") % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
			result = True
		cCursor.close()
		self.changesMade = True
		return result	
		
	def keyRed(self):
		self.close(self.changesMade)

	def keyGreen(self):
		self.getTimes()

	def keyYellow(self):
		self['red'].setText("")
		self['green'].setText("")
		self['yellow'].setText("")

		self.sendetermine_list = []
		self.loading = True
		self.chooseMenuList2.setList(map(self.buildList_termine, self.sendetermine_list))

		if self.FilterEnabled:
			self.FilterEnabled = False
		else:
			self.FilterEnabled = True
		
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText(_("Suche ' %s '") % self.serien_name)
		print self.serie_url
		getPage(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.resultsTermine, self.serien_name).addErrback(self.dataError)

	def showCover(self, serien_nameCover):
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("Coverfile not found: %s" %  serien_nameCover)

	def keyCancel(self):
		self.close(self.changesMade)

	def dataError(self, error):
		print error

class serienRecTimer(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderTimer"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRTimer.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.viewChange,
			"yellow": self.keyYellow,
			"blue"  : self.keyBlue,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB,
			"6"		: self.showConflicts
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label(_("Entferne Timer"))
		self['yellow'] = Label(_("Zeige auch alte Timer"))
		self['blue'] = Label(_("Entferne alle alten"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['0'] = Label(_("Zeige Log"))
		self['1'] = Label(_("Added Liste"))
		self['3'] = Label(_("Neue Serienstarts"))
		self['6'] = Label(_("Konflikt-Liste"))
		
		if config.plugins.serienRec.recordListView.value == 0:
			self['green'] = Label(_("Zeige früheste Timer zuerst"))
		elif config.plugins.serienRec.recordListView.value == 1:
			self['green'] = Label(_("Zeige neuste Timer zuerst"))

		self.changesMade = False

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.filter = True
		
		self.onLayoutFinish.append(self.readTimer)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowSeasonBegins)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showConflicts(self):
		self.session.open(serienRecShowConflicts)
		
	def viewChange(self):
		if config.plugins.serienRec.recordListView.value == 0:
			config.plugins.serienRec.recordListView.value = 1
			self['green'].setText(_("Zeige neuste Timer zuerst"))
		elif config.plugins.serienRec.recordListView.value == 1:
			config.plugins.serienRec.recordListView.value = 0
			self['green'].setText(_("Zeige früheste Timer zuerst"))
		config.plugins.serienRec.recordListView.save()
		self.readTimer()

	def readTimer(self, showTitle=True):
		current_time = int(time.time())
		deltimer = 0
		timerList = []

		cCursor = dbSerRec.cursor()
		if self.filter:
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE StartZeitstempel>=?", (current_time, ))
		else:
			cCursor.execute("SELECT * FROM AngelegteTimer")
		for row in cCursor:
			(serie, staffel, episode, title, start_time, sRef, webChannel, eit) = row
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

	def buildList(self, entry):
		(serie, title, start_time, webChannel, foundIcon, eit) = entry
		WochenTag=[_("Mo"), _("Di"), _("Mi"), _("Do"), _("Fr"), _("Sa"), _("So")]
		xtime = time.strftime(WochenTag[time.localtime(int(start_time)).tm_wday]+", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))

		if int(foundIcon) == 1:
			imageFound = "%simages/found.png" % serienRecMainPath
		else:
			imageFound = "%simages/black.png" % serienRecMainPath
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 8, 8, 32, 32, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 250, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, self.yellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie),
			(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow)
			]

	def keyOK(self):
		pass

	def callDeleteSelectedTimer(self, answer):
		if answer:
			serien_name = self['list'].getCurrent()[0][0]
			serien_title = self['list'].getCurrent()[0][1]
			serien_time = self['list'].getCurrent()[0][2]
			serien_channel = self['list'].getCurrent()[0][3]
			serien_eit = self['list'].getCurrent()[0][5]
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
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Timer leer."
			return
		else:
			serien_name = self['list'].getCurrent()[0][0]
			serien_title = self['list'].getCurrent()[0][1]
			serien_time = self['list'].getCurrent()[0][2]
			serien_channel = self['list'].getCurrent()[0][3]
			serien_eit = self['list'].getCurrent()[0][5]
			found = False
			print self['list'].getCurrent()[0]

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
			self['yellow'].setText(_("Zeige nur neue Timer"))
			self.filter = False
		else:
			self['yellow'].setText(_("Zeige auch alte Timer"))
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
			
	def keyCancel(self):
		self.close(self.changesMade)

	def dataError(self, error):
		print error

class serienRecSetup(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderSetup"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRSetup.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions", "KeyboardInputActions"], {
			"red"	: self.cancel,
			"green"	: self.save,
			"cancel": self.cancel,
			"ok"	: self.ok,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"deleteForward" : self.keyDelForward,
			"deleteBackward": self.keyDelBackward,
			"nextBouquet":	self.bouquetPlus,
			"prevBouquet":	self.bouquetMinus
		}, -1)

		self['title'] = Label(_("Serien Recorder - Einstellungen:"))
		self['red'] = Label(_("Abbrechen"))
		self['green'] = Label(_("Speichern"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self["config_information_text"] = Label(_("Das Verzeichnis auswählen und/oder erstellen, in dem die Aufnahmen gespeichert werden."))
		
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

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

		self.createConfigList()
		ConfigListScreen.__init__(self, self.list)
		
	def keyDelForward(self):
		self.changedEntry()

	def keyDelBackward(self):
		self.changedEntry()

	def bouquetPlus(self):
		self["config"].instance.moveSelection(self["config"].instance.pageUp)
		self.setInfoText()        

	def bouquetMinus(self):
		self["config"].instance.moveSelection(self["config"].instance.pageDown)
		self.setInfoText()        

	def keyDown(self):
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() >= (len(self.list) - 1):
			self["config"].instance.moveSelectionTo(0)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.setInfoText()        

	def keyUp(self):
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() <= 1:
			self["config"].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.setInfoText()        

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.changedEntry()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.changedEntry()

	def createConfigList(self):
		self.list = []
		self.list.append(getConfigListEntry(_("---------  SYSTEM:  -------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Speicherort der Aufnahmen:"), config.plugins.serienRec.savetopath))
		self.list.append(getConfigListEntry(_("Serien-Verzeichnis anlegen:"), config.plugins.serienRec.seriensubdir))
		self.list.append(getConfigListEntry(_("Staffel-Verzeichnis anlegen:"), config.plugins.serienRec.seasonsubdir))
		if config.plugins.serienRec.seasonsubdir.value:
			self.list.append(getConfigListEntry(_("    Mindestlänge der Staffelnummer im Verzeichnisnamen:"), config.plugins.serienRec.seasonsubdirnumerlength))
			self.list.append(getConfigListEntry(_("    Füllzeichen für Staffelnummer im Verzeichnisnamen:"), config.plugins.serienRec.seasonsubdirfillchar))
		self.list.append(getConfigListEntry(_("Intervall für autom. Suchlauf (in Std.) (00 = kein autom. Suchlauf, 24 = nach Uhrzeit):"), config.plugins.serienRec.updateInterval)) #3600000
		if config.plugins.serienRec.updateInterval.value == 24:
			self.list.append(getConfigListEntry(_("    Uhrzeit für automatischen Suchlauf (nur wenn Intervall = 24):"), config.plugins.serienRec.deltime))
		self.list.append(getConfigListEntry(_("Anzahl gleichzeitiger Web-Anfragen:"), config.plugins.serienRec.maxWebRequests))
		self.list.append(getConfigListEntry(_("Automatisches Plugin-Update:"), config.plugins.serienRec.Autoupdate))
		self.list.append(getConfigListEntry(_("Speicherort der Datenbank:"), config.plugins.serienRec.databasePath))
		self.list.append(getConfigListEntry(_("Erstelle Backup vor Suchlauf:"), config.plugins.serienRec.AutoBackup))
		if config.plugins.serienRec.AutoBackup.value:
			self.list.append(getConfigListEntry(_("    Speicherort für Backup:"), config.plugins.serienRec.BackupPath))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  AUTO-CHECK:  ---------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Timer für X Tage erstellen:"), config.plugins.serienRec.checkfordays))
		self.list.append(getConfigListEntry(_("Früheste Zeit für Timer (hh:00):"), config.plugins.serienRec.fromTime))
		self.list.append(getConfigListEntry(_("Späteste Zeit für Timer (hh:59):"), config.plugins.serienRec.toTime))
		self.list.append(getConfigListEntry(_("Versuche die Eventid vom EPGCACHE zu holen:"), config.plugins.serienRec.eventid))
		self.list.append(getConfigListEntry(_("Immer aufnehmen wenn keine Wiederholung gefunden wird:"), config.plugins.serienRec.forceRecording))
		if config.plugins.serienRec.forceRecording.value:
			self.list.append(getConfigListEntry(_("    maximal X Tage auf Wiederholung warten:"), config.plugins.serienRec.TimeSpanForRegularTimer))
		self.list.append(getConfigListEntry(_("Anzahl der Aufnahmen pro Episode:"), config.plugins.serienRec.NoOfRecords))
		self.list.append(getConfigListEntry(_("Anzahl der Tuner für Timer einschränken:"), config.plugins.serienRec.selectNoOfTuners))
		if config.plugins.serienRec.selectNoOfTuners.value:
			self.list.append(getConfigListEntry(_("    Anzahl der Tuner für Aufnahmen:"), config.plugins.serienRec.tuner))
		self.list.append(getConfigListEntry(_("Aktion bei neuer Serie/Staffel:"), config.plugins.serienRec.ActionOnNew))
		if config.plugins.serienRec.ActionOnNew.value != "0":
			self.list.append(getConfigListEntry(_("    Einträge löschen die älter sind als X Tage:"), config.plugins.serienRec.deleteOlderThan))
		self.list.append(getConfigListEntry(_("Aus Deep-StandBy aufwecken:"), config.plugins.serienRec.wakeUpDSB))
		self.list.append(getConfigListEntry(_("Nach dem automatischen Suchlauf in Deep-StandBy gehen:"), config.plugins.serienRec.afterAutocheck))
		if config.plugins.serienRec.afterAutocheck.value:
			self.list.append(getConfigListEntry(_("    Timeout für Deep-StandBy-Abfrage (in Sek.):"), config.plugins.serienRec.DSBTimeout))
			
		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  TIMER:  --------------------------------------------------------------------------------------------")))
		
		self.list.append(getConfigListEntry(_("Timer-Art:"), self.kindOfTimer))
		self.list.append(getConfigListEntry(_("Timervorlauf (in Min.):"), config.plugins.serienRec.margin_before))
		self.list.append(getConfigListEntry(_("Timernachlauf (in Min.):"), config.plugins.serienRec.margin_after))
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
		self.list.append(getConfigListEntry(_("---------  GUI:  ----------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Zeige Picons:"), config.plugins.serienRec.showPicons))
		self.list.append(getConfigListEntry(_("Intensive Suche nach angelegten Timern:"), config.plugins.serienRec.intensiveTimersuche))
		self.list.append(getConfigListEntry(_("Zeige ob die Episode als Aufnahem auf der HDD ist:"), config.plugins.serienRec.sucheAufnahme))
		self.list.append(getConfigListEntry(_("Anzahl der wählbaren Staffeln im Menü SerienMarker:"), config.plugins.serienRec.max_season))
		self.list.append(getConfigListEntry(_("Vor Löschen in SerienMarker und TimerList Benutzer fragen:"), config.plugins.serienRec.confirmOnDelete))
		self.list.append(getConfigListEntry(_("Zeige Nachricht wenn Suchlauf startet:"), config.plugins.serienRec.showNotification))
		self.list.append(getConfigListEntry(_("Zeige Nachricht bei Timerkonflikten:"), config.plugins.serienRec.showMessageOnConflicts))

		self.list.append(getConfigListEntry(""))
		self.list.append(getConfigListEntry(_("---------  LOG:  ----------------------------------------------------------------------------------------------")))
		self.list.append(getConfigListEntry(_("Speicherort für LogFile:"), config.plugins.serienRec.LogFilePath))
		self.list.append(getConfigListEntry(_("LogFile-Name mit Datum/Uhrzeit:"), config.plugins.serienRec.longLogFileName))
		if config.plugins.serienRec.longLogFileName.value:
			self.list.append(getConfigListEntry(_("    Log-Files löschen die älter sind als X Tage:"), config.plugins.serienRec.deleteLogFilesOlderThan))
		self.list.append(getConfigListEntry(_("DEBUG LOG aktivieren:"), config.plugins.serienRec.writeLog))
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
		self["config"].setList(self.list)

	def ok(self):
		ConfigListScreen.keyOK(self)
		if self["config"].getCurrent()[1] == config.plugins.serienRec.savetopath:
			#start_dir = "/media/hdd/movie/"
			start_dir = config.plugins.serienRec.savetopath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Aufnahme-Verzeichnis auswählen"))
		elif self["config"].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
			start_dir = config.plugins.serienRec.LogFilePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("LogFile-Verzeichnis auswählen"))
		elif self["config"].getCurrent()[1] == config.plugins.serienRec.BackupPath:
			start_dir = config.plugins.serienRec.BackupPath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Backup-Verzeichnis auswählen"))
		elif self["config"].getCurrent()[1] == config.plugins.serienRec.databasePath:
			start_dir = config.plugins.serienRec.databasePath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir, _("Datenbank-Verzeichnis auswählen"))

	def selectedMediaFile(self, res):
		if res is not None:
			if self["config"].getCurrent()[1] == config.plugins.serienRec.savetopath:
				print res
				config.plugins.serienRec.savetopath.value = res
				#config.plugins.serienRec.savetopath.save()
				#configfile.save()
				self.changedEntry()
			elif self["config"].getCurrent()[1] == config.plugins.serienRec.LogFilePath:
				print res
				config.plugins.serienRec.LogFilePath.value = res
				#config.plugins.serienRec.LogFilePath.save()
				#configfile.save()
				self.changedEntry()
			elif self["config"].getCurrent()[1] == config.plugins.serienRec.BackupPath:
				print res
				config.plugins.serienRec.BackupPath.value = res
				#config.plugins.serienRec.BackupPath.save()
				#configfile.save()
				self.changedEntry()
			elif self["config"].getCurrent()[1] == config.plugins.serienRec.databasePath:
				print res
				config.plugins.serienRec.databasePath.value = res
				#config.plugins.serienRec.databasePath.save()
				#configfile.save()
				
				#dbSerRec.close()
				#serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
				#dbSerRec = sqlite3.connect(serienRecDataBase)
				#dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
				
				self.changedEntry()

	def setInfoText(self):
		lt = time.localtime()
		self.HilfeTexte = {
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
			config.plugins.serienRec.fromTime :                (_("Die Uhrzeit, ab wann Aufnahmen erlaubt sind.\n"
							                                    "Die erlaubte Zeitspanne beginnt um %s:00 Uhr.")) % str(config.plugins.serienRec.fromTime.value).zfill(2),
			config.plugins.serienRec.toTime :                  (_("Die Uhrzeit, bis wann Aufnahmen erlaubt sind.\n"
						                                        "Die erlaubte Zeitspanne endet um %s:59 Uhr.")) % str(config.plugins.serienRec.toTime.value).zfill(2),
			config.plugins.serienRec.eventid :                 (_("Bei 'ja' wird beim Anlegen eines Timers versucht die Anfangs- und Endzeiten vom EPG zu holen. "
			                                                    "Außerdem erfolgt bei jedem Timer-Suchlauf ein Abgleich der Anfangs- und Endzeiten aller Timer mit den EPG-Daten.")),
			config.plugins.serienRec.forceRecording :          (_("Bei 'ja' werden auch Timer für Folgen erstellt, die ausserhalb der erlaubten Zeitspanne (%s:00 - %s:59) ausgestrahlt werden, "
			                                                    "wenn KEINE Wiederholung innerhalb der erlaubten Zeitspanne gefunden wird. Wird eine passende Wiederholung zu einem späteren Zeitpunkt gefunden, dann wird der Timer für diese Wiederholung erstellt.\n"
			                                                    "Bei 'nein' werden ausschließlich Timer für jene Folgen erstellt, die innerhalb der erlaubten Zeitspanne liegen.")) % (str(config.plugins.serienRec.fromTime.value).zfill(2), str(config.plugins.serienRec.toTime.value).zfill(2)),
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
			config.plugins.serienRec.deleteOlderThan :         (_("Staffel-/Serienstarts die älter als die hier eingestellte Anzahl von Tagen (also vor dem %s) sind, werden beim Timer-Suchlauf automatisch aus der Datenbank entfernt "
																"und auch nicht mehr angezeigt.")) % time.strftime("%d.%m.%Y", time.localtime(int(time.time()) - (int(config.plugins.serienRec.deleteOlderThan.value) * 86400))),
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
			config.plugins.serienRec.selectBouquets :          (_("Bei 'ja' werden 2 Bouquets (Standard und Alternativ) für die Channel-Zuordnung verwendet werden.\n"
			                                                    "Bei 'nein' wird das erste Bouquet für die Channel-Zuordnung benutzt.")),
			config.plugins.serienRec.MainBouquet :             (_("Auswahl, welches Bouquet bei der Channel-Zuordnung als Standard verwendet werden sollen.")),
			config.plugins.serienRec.AlternativeBouquet :      (_("Auswahl, welches Bouquet bei der Channel-Zuordnung als Alternative verwendet werden sollen.")),
			config.plugins.serienRec.useAlternativeChannel :   (_("Mit 'ja' oder 'nein' kann ausgewählt werden, ob versucht werden soll, einen Timer auf dem jeweils anderen Channel (Standard oder alternativ) zu erstellen, "
										                        "falls der Timer auf dem bevorzugten Channel nicht angelegt werden kann.")),
			config.plugins.serienRec.showPicons :              (_("Bei 'ja' werden in der Hauptansicht auch die Sender-Logos angezeigt.")),
			config.plugins.serienRec.intensiveTimersuche :     (_("Bei 'ja' wir in der Hauptansicht intensiver nach vorhandenen Timern gesucht, d.h. es wird vor der Suche versucht die Anfangszeit aus dem EPGCACHE zu aktualisieren was aber zeitintensiv ist.")),
			config.plugins.serienRec.sucheAufnahme :           (_("Bei 'ja' wir in der Hauptansicht ein Symbol für jede Episode angezeigt, die als Aufnahme auf der Festplatte gefunden wurde, diese Suche ist aber sehr zeitintensiv.")),
			config.plugins.serienRec.max_season :              (_("Die höchste Staffelnummer, die für Serienmarker in der Staffel-Auswahl gewählt werden kann.")),
			config.plugins.serienRec.confirmOnDelete :         (_("Bei 'ja' erfolt eine Sicherheitsabfrage ('Soll ... wirklich entfernt werden?') vor dem entgültigen Löschen von Serienmarkern oder Timern.")),
			config.plugins.serienRec.showNotification :        (_("Bei 'ja' wird für 3 Sekunden eine Nachricht auf dem Bildschirm eingeblendet, sobald der automatische Timer-Suchlauf startet.")),
			config.plugins.serienRec.showMessageOnConflicts :  (_("Bei 'ja' wird für jeden Timer, der beim automatische Timer-Suchlauf wegen eines Konflikts nicht angelegt werden konnte, eine Nachricht auf dem Bildschirm eingeblendet.\n"
			                                                    "Diese Nachrichten bleiben solange auf dem Bildschirm bis sie vom Benutzer quittiert (zur Kenntnis genommen) werden.")),
			config.plugins.serienRec.LogFilePath :             (_("Das Verzeichnis auswählen und/oder erstellen, in dem die log-Dateien gespeichert werden.")),
			config.plugins.serienRec.longLogFileName :         (_("Bei 'nein' wird bei jedem Timer-Suchlauf die log-Datei neu erzeugt.\n"
			                                                    "Bei 'ja' wird NACH jedem Timer-Suchlauf die soeben neu erzeugte log-Datei in eine Datei kopiert, deren Name das aktuelle Datum und die aktuelle Uhrzeit beinhaltet "
																"(z.B.\n%slog_%s%s%s%s%s")) % (config.plugins.serienRec.LogFilePath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)),
			config.plugins.serienRec.deleteLogFilesOlderThan : (_("log-Dateien, die älter sind als die hier angegebene Anzahl von Tagen, werden beim Timer-Suchlauf automatisch gelöscht.")),
			config.plugins.serienRec.writeLog :                (_("Bei 'nein' erfolgen nur grundlegende Eintragungen in die log-Datei, z.B. Datum/Uhrzeit des Timer-Suchlaufs, Beginn neuer Staffeln, Gesamtergebnis des Timer-Suchlaufs.\n"
			                                                    "Bei 'ja' erfolgen detaillierte Eintragungen, abhängig von den ausgewählten Filtern.")),
			config.plugins.serienRec.writeLogChannels :        (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn dem ausstrahlenden Sender in der Channel-Zuordnung kein STB-Channel zugeordnet ist, oder der STB-Channel deaktiviert ist.")),
			config.plugins.serienRec.writeLogAllowedSender :   (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der ausstrahlende Sender in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist.")),
			config.plugins.serienRec.writeLogAllowedEpisodes : (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn die zu timende Staffel oder Folge in den Einstellungen des Serien-Markers für diese Serie nicht zugelassen ist.")),
			config.plugins.serienRec.writeLogAdded :           (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Timern vorhanden ist.")),
			config.plugins.serienRec.writeLogDisk :            (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn für die zu timende Folge bereits die maximale Anzahl von Aufnahmen vorhanden ist.")),
			config.plugins.serienRec.writeLogTimeRange :       (_("Bei 'ja' erfolgen Einträge in die log-Datei, wenn die zu timende Folge nicht in der erlaubten Zeitspanne (%s:00 - %s:59) liegt, "
			                                                    "sowie wenn gemäß der Einstellung 'Immer aufnehmen wenn keine Wiederholung gefunden wird' = 'ja' "
																"ein Timer ausserhalb der erlaubten Zeitspanne angelegt wird.")) % (str(config.plugins.serienRec.fromTime.value).zfill(2), str(config.plugins.serienRec.toTime.value).zfill(2)),
			config.plugins.serienRec.writeLogTimeLimit :       (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der Sendetermin für die zu timende Folge in der Verganhenheit, \n"
			                                                    "oder mehr als die in 'Timer für X Tage erstellen' eingestellte Anzahl von Tagen in der Zukunft liegt (jetzt also nach %s).")) % time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(time.time()) + (int(config.plugins.serienRec.checkfordays.value) * 86400))),
			config.plugins.serienRec.writeLogTimerDebug :      (_("Bei 'ja' erfolgt ein Eintrag in die log-Datei, wenn der zu erstellende Timer bereits vorhanden ist, oder der Timer erfolgreich angelegt wurde.")),
			config.plugins.serienRec.logScrollLast :           (_("Bei 'ja' wird beim Anzeigen der log-Datei ans Ende gesprungen, bei 'nein' auf den Anfang.")),
			config.plugins.serienRec.logWrapAround :           (_("Bei 'ja' erfolgt die Anzeige der log-Datei mit Zeilenumbruch, d.h. es werden 3 Zeilen pro Eintrag angezeigt.\n"
			                                                    "Bei 'nein' erfolgt die Anzeige der log-Datei mit 1 Zeile pro Eintrag (Bei langen Zeilen sind dann die Enden nicht mehr sichbar!)")),
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
			
		try:
			text = self.HilfeTexte[self["config"].getCurrent()[1]]
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
			
		config.plugins.serienRec.savetopath.save()
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.seriensubdir.save()
		config.plugins.serienRec.seasonsubdir.save()
		config.plugins.serienRec.seasonsubdirnumerlength.save()
		config.plugins.serienRec.seasonsubdirfillchar.save()
		config.plugins.serienRec.update.save()
		config.plugins.serienRec.updateInterval.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.databasePath.save()

		global serienRecDataBase
		#global dbSerRec
		if serienRecDataBase != "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			dbSerRec.close()
			serienRecDataBase = "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value
			initDB()
			#dbSerRec = sqlite3.connect(serienRecDataBase)
			#dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))

		config.plugins.serienRec.AutoBackup.save()
		config.plugins.serienRec.BackupPath.save()
		config.plugins.serienRec.maxWebRequests.save()
		config.plugins.serienRec.margin_before.save()
		config.plugins.serienRec.margin_after.save()
		config.plugins.serienRec.max_season.save()
		config.plugins.serienRec.Autoupdate.save()
		config.plugins.serienRec.fromTime.save()
		config.plugins.serienRec.toTime.save()
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
		config.plugins.serienRec.confirmOnDelete.save()
		config.plugins.serienRec.ActionOnNew.save()
		config.plugins.serienRec.deleteOlderThan.save()
		config.plugins.serienRec.forceRecording.save()
		config.plugins.serienRec.forceManualRecording.save()
		if int(config.plugins.serienRec.checkfordays.value) > int(config.plugins.serienRec.TimeSpanForRegularTimer.value):
			config.plugins.serienRec.TimeSpanForRegularTimer.value = int(config.plugins.serienRec.checkfordays.value)
		config.plugins.serienRec.TimeSpanForRegularTimer.save()
		config.plugins.serienRec.showMessageOnConflicts.save()
		config.plugins.serienRec.showPicons.save()
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
		config.plugins.serienRec.justplay.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTPLAY__))
		config.plugins.serienRec.zapbeforerecord.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_ZAPBEFORERECORD__))
		config.plugins.serienRec.justremind.value = bool(int(self.kindOfTimer.value) & (1 << self.__C_JUSTREMIND__))
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.zapbeforerecord.save()
		config.plugins.serienRec.justremind.save()
		
		configfile.save()
		self.close(True)

	def cancel(self):
		self.close(False)

class SerienRecFileList(Screen):
	def __init__(self, session, initDir, title):
		Screen.__init__(self, session)
		
		# Skin
		self.skinName = "SerienRecorderFileList"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRFileList.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["title"] = Label(title)
		self["media"] = Label("")
		self["folderlist"] = FileList(initDir, inhibitMounts = False, inhibitDirs = False, showMountpoints = False, showFiles = False)
		self["cancel"] = Label(_("Abbrechen"))
		self["red"] = Label(_("Verzeichnis löschen"))
		self["green"] = Label(_("Speichern"))
		self['blue'] = Label(_("Verzeichnis anlegen"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)

		self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions", "EPGSelectActions"],
		{
			"back": self.cancel,
			"cancel": self.cancel,
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"ok": self.ok,
			"green": self.keyGreen,
			"red": self.keyRed,
			"blue": self.keyBlue
		}, -1)
		
		self.updateFile()

	def cancel(self):
		self.close(None)

	def keyRed(self):
		try:
			os.rmdir(self["folderlist"].getSelection()[0])
		except:
			pass
		self.updateFile()
		
	def keyGreen(self):
		directory = self["folderlist"].getSelection()[0]
		if (directory.endswith("/")):
			self.fullpath = self["folderlist"].getSelection()[0]
		else:
			self.fullpath = "%s/" % self["folderlist"].getSelection()[0]
		self.close(self.fullpath)

	def keyBlue(self):
		self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Verzeichnis-Name eingeben:")), text = "")

	def wSearch(self, Path_name):
		if Path_name:
			Path_name = "%s%s/" % (self["folderlist"].getSelection()[0], Path_name)
			print Path_name
			if not os.path.exists(Path_name):
				try:
					os.makedirs(Path_name)
				except:
					pass
		self.updateFile()
			
	def up(self):
		self["folderlist"].up()
		self.updateFile()

	def down(self):
		self["folderlist"].down()
		self.updateFile()

	def left(self):
		self["folderlist"].pageUp()
		self.updateFile()

	def right(self):
		self["folderlist"].pageDown()
		self.updateFile()

	def ok(self):
		if self["folderlist"].canDescent():
			self["folderlist"].descent()
			self.updateFile()

	def updateFile(self):
		currFolder = self["folderlist"].getSelection()[0]
		self["media"].setText(_("Auswahl: %s") % currFolder)

class serienRecReadLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderReadLog"
		skin = None
		#SRWide = getDesktop(0).size().width()
		if config.plugins.serienRec.logWrapAround.value:
			skin = "%sskins/SRReadLog.xml" % serienRecMainPath
		else:
			skin = "%sskins/SRReadLog2.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"cancel": self.keyCancel
		}, -1)

		self["list"] = ScrollLabel()
		self['title'] = Label(_("Lese LogFile: (%s)") % logFile)
		self['red'] = Label(_("Abbrechen"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.logliste = []

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		if config.plugins.serienRec.logWrapAround.value:
			self.chooseMenuList.l.setItemHeight(70)
		else:
			self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		
		self.onLayoutFinish.append(self.readLog)

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
			self['title'].setText(_("LogFile: (%s)") % logFile)
			self.chooseMenuList.setList(map(self.buildList, self.logliste))
			if config.plugins.serienRec.logScrollLast.value:
				count = len(self.logliste)
				if count != 0:
					self["list"].moveToIndex(int(count-1))

	def buildList(self, entry):
		(zeile) = entry
		if config.plugins.serienRec.logWrapAround.value:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 65, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER | RT_WRAP, zeile)]
		else:
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850, 20, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]
		
	def keyCancel(self):
		self.close()

class serienRecLogReader(Screen):
	def __init__(self, session, startAuto):
		Screen.__init__(self, session)
		self.session = session
		self.startAuto = startAuto

		# Skin
		self.skinName = "SerienRecorderLogReader"
		skin = None
		#SRWide = getDesktop(0).size().width()
		if config.plugins.serienRec.logWrapAround.value:
			skin = "%sskins/SRLogReader.xml" % serienRecMainPath
		else:
			skin = "%sskins/SRLogReader2.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			#"up" : self.pageUp,
			#"down" : self.pageDown,
			#"right" : self.pageDown,
			#"left" : self.pageUp,
			#"nextBouquet" : self.pageUp,
			#"prevBouquet" : self.pageDown,
			"cancel": self.keyCancel
		}, -1)

		self["list"] = ScrollLabel()
		self['title'] = Label(_("Suche nach neuen Timern läuft."))
		self['red'] = Label(_("Abbrechen"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.logliste = []
		self.points = ""

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		if config.plugins.serienRec.logWrapAround.value:
			self.chooseMenuList.l.setItemHeight(70)
		else:
			self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		
		self.onLayoutFinish.append(self.startCheck)
		self.onClose.append(self.__onClose)

	def startCheck(self):
		if self.startAuto:
			global autoCheckFinished
			autoCheckFinished = False
			serienRecCheckForRecording(self.session, True)

		# Log Reload Timer
		self.readLogTimer = eTimer()
		self.readLogTimer.callback.append(self.readLog)
		self.readLogTimer.start(2500)
		self.readLog()

	def readLog(self):
		global autoCheckFinished
		if autoCheckFinished or not self.startAuto:
			self.readLogTimer.stop()
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
					self["list"].moveToIndex(int(count-1))
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
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()
		
	def __onClose(self):
		print "[Serien Recorder] update log reader stopped."
		self.readLogTimer.stop()

	def keyCancel(self):
		self.close(self.startAuto)

class checkupdate():

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
			print "[Serien Recorder] kein update verfügbar."
			return

	def startUpdate(self,answer):
		if answer:
			self.session.open(SerienRecorderUpdateScreen,self.updateurl)
		else:
			return

class SerienRecorderUpdateScreen(Screen):
	def __init__(self, session, updateurl):
		self.session = session
		self.updateurl = updateurl

		# Skin
		self.skinName = "SerienRecorderUpdate"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRUpdate.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["mplog"] = ScrollLabel()
		Screen.__init__(self, session)
		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		sl = self["mplog"]
		sl.instance.setZPosition(1)
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
		initDB()
		self.session.openWithCallback(self.restartGUI, MessageBox, _("Serien Recorder wurde erfolgreich aktualisiert!\nWollen Sie jetzt Enigma2 GUI neu starten?"), MessageBox.TYPE_YESNO)

	def restartGUI(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)
		else:
			self.close()

	def mplog(self,str):
		self["mplog"].setText(str)

def initDB():
	global dbSerRec
	if not os.path.exists(serienRecDataBase):
		try:
			dbSerRec = sqlite3.connect(serienRecDataBase)
			dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
		except:
			return
	
	if os.path.getsize(serienRecDataBase) == 0:
		cCursor = dbSerRec.cursor()
		cCursor.execute('''CREATE TABLE IF NOT EXISTS dbInfo (Key TEXT NOT NULL UNIQUE, 
														   Value TEXT NOT NULL DEFAULT "")''') 

		cCursor.execute('''CREATE TABLE IF NOT EXISTS NeuerStaffelbeginn (Serie TEXT NOT NULL, 
																		  Staffel INTEGER, 
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

		cCursor.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer (Serie TEXT NOT NULL, 
																	  Staffel INTEGER, 
																	  Episode TEXT, 
																	  Titel TEXT, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  ServiceRef TEXT NOT NULL, 
																	  webChannel TEXT NOT NULL, 
																	  EventID INTEGER DEFAULT 0)''')
																	
		cCursor.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  webChannel TEXT NOT NULL)''')
																	
		cCursor.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																  Staffel INTEGER NOT NULL, 
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
																	  Staffel INTEGER NOT NULL, 
																	  Episode TEXT NOT NULL,
																	  AnzahlWiederholungen INTEGER DEFAULT NULL)''')
			dbSerRec.commit()
			cCursor.close()
						
			updateDB()

	dbSerRec.close()
	dbSerRec = sqlite3.connect(serienRecDataBase)
	dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))

			
	cTmp = dbTmp.cursor()
	cTmp.execute('''CREATE TABLE IF NOT EXISTS GefundeneFolgen (CurrentTime INTEGER,
																FutureTime INTEGER,
																SerieName TEXT,
																Staffel INTEGER, 
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

def updateDB():
	#dbSerRec.close()
	shutil.move(serienRecDataBase, "%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value)
	dbSerRec = sqlite3.connect("%sSerienRecorder_old.db" % config.plugins.serienRec.databasePath.value)

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

	cNew.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer (Serie TEXT NOT NULL, 
																  Staffel INTEGER, 
																  Episode TEXT, 
																  Titel TEXT, 
																  StartZeitstempel INTEGER NOT NULL, 
																  ServiceRef TEXT NOT NULL, 
																  webChannel TEXT NOT NULL, 
																  EventID INTEGER DEFAULT 0)''')
																
	cNew.execute('''CREATE TABLE IF NOT EXISTS NeuerStaffelbeginn (Serie TEXT NOT NULL, 
																	  Staffel INTEGER, 
																	  Sender TEXT NOT NULL, 
																	  StaffelStart TEXT NOT NULL, 
																	  UTCStaffelStart INTEGER, 
																	  Url TEXT NOT NULL, 
																	  CreationFlag INTEGER DEFAULT 1)''') 
																	
	cNew.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																  StartZeitstempel INTEGER NOT NULL, 
																  webChannel TEXT NOT NULL)''')
																
	cNew.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
															  Staffel INTEGER NOT NULL, 
															  Episode TEXT NOT NULL,
															  AnzahlWiederholungen INTEGER DEFAULT NULL)''')

	dbNew.commit()

	cNew.execute("ATTACH DATABASE '%sSerienRecorder_old.db' AS 'dbOLD'" % serienRecMainPath)
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
	cCursor.close()
	cNew.execute("DETACH DATABASE 'dbOLD'")
	cNew.execute("DELETE FROM dbInfo WHERE Key='Version'")	
	cNew.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('Version', ?)", (config.plugins.serienRec.dbversion.value,))	
	dbNew.commit()
	cNew.close()
	dbNew.close()
	
	dbSerRec.close()
	dbSerRec = sqlite3.connect(serienRecDataBase)
	dbSerRec.text_factory = lambda x: str(x.decode("utf-8"))
	
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
		cCursor.execute("SELECT * FROM Channels")
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
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND Staffel=? AND LOWER(Episode)=?", (serie.lower(), staffel, episode.lower()))
			if not cCursor.fetchone():
				sql = "INSERT OR IGNORE INTO AngelegteTimer (Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel) VALUES (?, ?, ?, ?, ?, ?, ?)"
				cCursor.execute(sql, (serie, staffel, episode, title, start_time, stbRef, webChannel))
			else:
				sql = "UPDATE OR IGNORE AngelegteTimer SET Titel=?, StartZeitstempel=?, ServiceRef=?, webChannel=? WHERE LOWER(Serie)=? AND Staffel=? AND LOWER(Episode)=?"
				cCursor.execute(sql, (title, start_time, stbRef, webChannel, serie.lower(), staffel, episode.lower()))
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

	# remove old Tables
	cCursor = dbSerRec.cursor()
	try:
		cCursor.execute("DROP TABLE NeueStaffel")
	except:
		pass
	dbSerRec.commit()
	cCursor.execute("VACUUM")
	dbSerRec.commit()
	cCursor.close()
	
	return True
		
class serienRecModifyAdded(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderModifyAdded"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRModifyAdded.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.save,
			"yellow" : self.keyYellow
		}, -1)

		#normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()

		self.modus = "list"
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label(_("Eintrag löschen"))
		self['green'] = Label(_("Speichern"))
		self['cancel'] = Label(_("Abbrechen"))
		self['yellow'] = Label(_("Sortieren"))
		self['ok'] = Label(_("Eintrag Anlegen"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		
		self.delAdded = False
		self.sortedList = False
		self.addedliste = []
		self.addedliste_tmp = []
		self.dbData = []
		
		self.onLayoutFinish.append(self.readAdded)

	def save(self):
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
		self.close()
			
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
			
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
		(Serie,) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 560, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
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
					cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (self.aSerie, self.aStaffel, str(i).zfill(2), "dump", 0, "dump", "dump", 0))
				dbSerRec.commit()
				cCursor.close()
				self.readAdded()

	def keyOK(self):
		if self.modus == "list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['list'].hide()
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
			self.modus = "list"
			self['list'].show()
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
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Added-File leer."
			return
		else:
			zeile = self['list'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), staffel, episode))
			self.addedliste_tmp.remove(zeile)
			self.addedliste.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			self.delAdded = True;
			
	def keyYellow(self):
		if len(self.addedliste_tmp) != 0:
			if self.sortedList:
				self.addedliste_tmp = self.addedliste[:]
				self['yellow'].setText(_("Sortieren"))
				self.sortedList = False
			else:
				self.addedliste_tmp.sort()
				self['yellow'].setText(_("unsortierte Liste"))
				self.sortedList = True

			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		
	def keyCancel(self):
		self.close()

class serienRecShowSeasonBegins(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderShowSeasonBegins"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRShowSeasonBegins.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyOK,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"yellow": self.keyYellow,
			"blue"	: self.keyBlue,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"4"		: self.serieInfo
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)

		self.picload = ePicLoad()
		self['cover'] = Pixmap()
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label(_("Eintrag löschen"))
		self['green'] = Label(_("Marker übernehmen"))
		self['cancel'] = Label(_("Abbrechen"))
		self['yellow'] = Label(_("Zeige nur neue"))
		self['blue'] = Label(_("Liste leeren"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['4'] = Label(_("Serien Beschreibung"))

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		
		self.filter = config.plugins.serienRec.serienRecShowSeasonBegins_filter.value
		if self.filter:
			self['yellow'].setText(_("Zeige alle"))
		else:
			self['yellow'].setText(_("Zeige nur neue"))
		self.proposalList = []

		self.onLayoutFinish.append(self.readProposal)

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
			Staffel = str(Staffel).zfill(2)
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
			setFarbe = self.red
		else:
			setFarbe = self.white
			
		Staffel = "S%sE01" % Staffel
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
				(eListboxPythonMultiContent.TYPE_TEXT, 110, 29, 200, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 375, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, self.yellow, self.yellow)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 15, 30, 30, loadPNG(imageFound)),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Sender),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 200, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Staffel, self.yellow, self.yellow)
				]

	def serieInfo(self):
		check = self['list'].getCurrent()
		if check == None:
			return
		url = self['list'].getCurrent()[0][5]
		id = re.findall('epg_print.pl\?s=([0-9]+)', url)
		serien_name = self['list'].getCurrent()[0][0]
		
		if id:
			self.session.open(serienRecShowInfo, serien_name, "http://www.wunschliste.de/"+id[0])

	def getCover(self):
		check = self['list'].getCurrent()
		if check == None:
			return

		url = self['list'].getCurrent()[0][5]
		id = re.findall('epg_print.pl\?s=([0-9]+)', url)
		serien_name = self['list'].getCurrent()[0][0]

		serien_nameCover = "/tmp/serienrecorder/%s.png" % serien_name

		if not fileExists("/tmp/serienrecorder/"):
			shutil.os.mkdir("/tmp/serienrecorder/")
		if fileExists(serien_nameCover):
			self.showCover(serien_nameCover, serien_nameCover)
		else:
			if id:
				url = "http://www.wunschliste.de/%s/links" % id[0]
				print url
				getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.getImdblink, serien_nameCover).addErrback(self.dataError)

	def getImdblink(self, data, serien_nameCover):
		ilink = re.findall('<a href="(http://www.imdb.com/title/.*?)"', data, re.S) 
		if ilink:
			getPage(ilink[0], headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.loadImdbCover, serien_nameCover).addErrback(self.dataError)
		else:
			print "[Serien Recorder] es wurde kein imdb-link für ein cover gefunden."

	def loadImdbCover(self, data, serien_nameCover):
		imageLink_raw = re.findall('<link rel="image_src" href="http://ia.media-imdb.com/(.*?)"', data, re.S)
		if imageLink_raw:
			print imageLink_raw
			extra_imdb_convert = "@._V1_SX320.jpg"
			aufgeteilt = imageLink_raw[0].split('._V1._')
			imdb_url = "http://ia.media-imdb.com/%s._V1._SX420_SY420_.jpg" % aufgeteilt[0]
			print imdb_url
			downloadPage(imdb_url, serien_nameCover).addCallback(self.showCover, serien_nameCover).addErrback(self.dataError)

	def showCover(self, data, serien_nameCover):
		if fileExists(serien_nameCover):
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
		else:
			print("Coverfile not found: %s" %  serien_nameCover)

	def keyRed(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['list'].getCurrent()[0]
			cCursor = dbSerRec.cursor()
			data = (Serie, Staffel, Sender, Datum) 
			cCursor.execute("DELETE FROM NeuerStaffelbeginn WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
			dbSerRec.commit()
			cCursor.close()
			self.readProposal()

	def keyGreen(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, UTCTime, Url, CreationFlag) = self['list'].getCurrent()[0]
			if CreationFlag:
				(ID, AbStaffel, AlleSender) = self.checkMarker(Serie)
				if ID > 0:
					cCursor = dbSerRec.cursor()
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
					
					if not AlleSender:
						cCursor.execute("SELECT * FROM SenderAuswahl WHERE ID=? AND ErlaubterSender=?", (ID, Sender))
						row = cCursor.fetchone()
						if not row:
							cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
					
					dbSerRec.commit()
					cCursor.close()
				else:
					cCursor = dbSerRec.cursor()
					cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, useAlternativeChannel) VALUES (?, ?, ?, ?, -1)", (Serie, Url, AbStaffel, AlleSender))
					ID = cCursor.lastrowid
					cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (ID, Sender))
					cCursor.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (ID, Staffel))
					dbSerRec.commit()
					cCursor.close()

				cCursor = dbSerRec.cursor()
				data = (Serie, Staffel, Sender, Datum) 
				cCursor.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET CreationFlag=0 WHERE Serie=? AND Staffel=? AND Sender=? AND StaffelStart=?", data)
				dbSerRec.commit()
				cCursor.close()
			self.readProposal()
		
	def keyYellow(self):
		if not self.filter:
			self.filter = True
			self['yellow'].setText(_("Zeige alle"))
		else:
			self.filter = False
			self['yellow'].setText(_("Zeige nur neue"))
		self.readProposal()
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.value = self.filter
		config.plugins.serienRec.serienRecShowSeasonBegins_filter.save()

	def keyBlue(self):
		check = self['list'].getCurrent()
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

	def keyOK(self):
		self.close()

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
		self['list'].pageUp()
		self.getCover()

	def keyRight(self):
		self['list'].pageDown()
		self.getCover()

	def keyDown(self):
		self['list'].down()
		self.getCover()

	def keyUp(self):
		self['list'].up()
		self.getCover()

	def dataError(self, error):
		print error

class serienRecMarkerSetup(Screen, ConfigListScreen):
	def __init__(self, session, Serie):
		Screen.__init__(self, session)
		self.session = session
		self.Serie = Serie
		
		# Skin
		self.skinName = "SerienRecorderSetup"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRSetup.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"red"	: self.cancel,
			"green"	: self.save,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"cancel": self.cancel,
			"ok"	: self.ok
		}, -1)

		self['title'] = Label(_("Serien Recorder - Einstellungen für '%s':") % self.Serie)
		self['red'] = Label(_("Abbrechen"))
		self['green'] = Label(_("Speichern"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self["config_information_text"] = Label(_("Das Verzeichnis auswählen oder erstellen, in dem die Aufnahmen von '%s' gespeichert werden.") % self.Serie)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

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
			self.fromTime = ConfigInteger(AufnahmezeitVon, (0,23))
			self.enable_fromTime = ConfigYesNo(default = True)
		else:
			self.fromTime = ConfigInteger(config.plugins.serienRec.fromTime.value, (0,23))
			self.enable_fromTime = ConfigYesNo(default = False)
			
		if str(AufnahmezeitBis).isdigit():
			self.toTime = ConfigInteger(AufnahmezeitBis, (0,23))
			self.enable_toTime = ConfigYesNo(default = True)
		else:
			self.toTime = ConfigInteger(config.plugins.serienRec.toTime.value, (0,23))
			self.enable_toTime = ConfigYesNo(default = False)

		self.preferredChannel = ConfigSelection(choices = [("1", _("Standard")), ("2", _("Alternativ"))], default=str(preferredChannel))
		self.useAlternativeChannel = ConfigSelection(choices = [("-1", _("gemäß Setup (dzt. %s)") % str(config.plugins.serienRec.useAlternativeChannel.value).replace('True', _('ja')).replace('False', _('nein'))), ("0", _("nein")), ("1", _("ja"))], default=str(useAlternativeChannel))
		
		self.createConfigList()
		ConfigListScreen.__init__(self, self.list)
		
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
			self.list.append(getConfigListEntry(_("      Früheste Zeit für Timer (hh:00):"), self.fromTime))
			self.toTime_index += 1

		self.list.append(getConfigListEntry(_("vom globalen Setup abweichende Späteste Zeit für Timer aktivieren:"), self.enable_toTime))
		if self.enable_toTime.value:
			self.list.append(getConfigListEntry(_("      Späteste Zeit für Timer (hh:59):"), self.toTime))

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
				self.fromTime.value = config.plugins.serienRec.fromTime.value
		elif self["config"].instance.getCurrentIndex() == self.toTime_index:
			if self.enable_toTime.value and not self.toTime.value:
				self.toTime.value = config.plugins.serienRec.toTime.value
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
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() >= (len(self.list) - 1):
			self["config"].instance.moveSelectionTo(0)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.setInfoText()        

	def keyUp(self):
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() < 1:
			self["config"].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.setInfoText()        

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
							              "Die erlaubte Zeitspanne beginnt um %s:00 Uhr.\n" 
							              "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die früheste Zeit für Timer.")) % (self.Serie, str(self.fromTime.value).zfill(2)),
			self.enable_toTime :         (_("Bei 'ja' kann die erlaubte Zeitspanne (bis Uhrzeit) für Aufnahmen von '%s' eingestellt werden.\n"
								          "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.\n"
								          "Bei 'nein' gilt die Einstellung vom globalen Setup.")) % self.Serie,
			self.toTime :                (_("Die Uhrzeit, bis wann Aufnahmen von '%s' erlaubt sind.\n"
						                  "Die erlaubte Zeitspanne endet um %s:59 Uhr.\n" 
						                  "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die späteste Zeit für Timer.") )% (self.Serie, str(self.toTime.value).zfill(2)),
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
			AufnahmezeitVon = self.fromTime.value
			
		if not self.enable_toTime.value:
			AufnahmezeitBis = None
		else:
			AufnahmezeitBis = self.toTime.value

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

class serienRecChannelSetup(Screen, ConfigListScreen):
	def __init__(self, session, webSender):
		Screen.__init__(self, session)
		self.session = session
		self.webSender = webSender
		
		# Skin
		self.skinName = "SerienRecorderSetup"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRSetup.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"red"	: self.cancel,
			"green"	: self.save,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"cancel": self.cancel,
			"ok"	: self.ok
		}, -1)

		self['title'] = Label(_("Serien Recorder - Einstellungen für '%s':") % self.webSender)
		self['red'] = Label(_("Abbrechen"))
		self['green'] = Label(_("Speichern"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self["config_information_text"] = Label((_("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n" 
		                                         "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n" 
												 "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
					                             "Bei 'nein' gilt die Einstellung im globalen Setup.")) % self.webSender)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Vorlaufzeit, Nachlaufzeit, vps FROM Channels WHERE LOWER(WebChannel)=?", (self.webSender.lower(),))
		row = cCursor.fetchone()
		if not row:
			row = (None, None)
		(Vorlaufzeit, Nachlaufzeit, vpsSettings) = row
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
			
		if vpsSettings == 2:
			self.enable_vps = ConfigYesNo(default = True)
			self.enable_vps_savemode = ConfigYesNo(default = True)
		elif vpsSettings == 1:
			self.enable_vps = ConfigYesNo(default = True)
			self.enable_vps_savemode = ConfigYesNo(default = False)
		else:
			self.enable_vps = ConfigYesNo(default = False)
			self.enable_vps_savemode = ConfigYesNo(default = False)
			
		self.createConfigList()
		ConfigListScreen.__init__(self, self.list)
		
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
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() >= (len(self.list) - 1):
			self["config"].instance.moveSelectionTo(0)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveDown)
		self.setInfoText()        

	def keyUp(self):
		self.changedEntry()
		if self["config"].instance.getCurrentIndex() < 1:
			self["config"].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
		self.setInfoText()        

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
			self.enable_vps :           (_("Bei 'ja' wird VPS für '%s' aktiviert, dann startet die Aufnahme erst, wenn der Sender angibt, dass die Sendung begonnen hat.\n"
				                         "Die Aufnahme endet, wenn angegeben wird, dass die Sendung vorbei ist.")) % self.webSender,
			self.enable_vps_savemode : (_("Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet, dann wird die programmierte Start- und Endzeit eingehalten.\n"
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

		vpsSettings = 0
		if self.enable_vps.value:
			vpsSettings += 1
		if self.enable_vps_savemode.value:
			vpsSettings += 1

		cCursor = dbSerRec.cursor()
		cCursor.execute("UPDATE OR IGNORE Channels SET Vorlaufzeit=?, Nachlaufzeit=?, vps=? WHERE LOWER(WebChannel)=?", (Vorlaufzeit, Nachlaufzeit, vpsSettings, self.webSender.lower()))
		dbSerRec.commit()
		cCursor.close()
		self.close()

	def cancel(self):
		self.close()

class serienRecShowConflicts(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderShowConflicts"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRShowConflicts.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"cancel": self.keyCancel,
			"red"	: self.keyCancel,
			"blue"	: self.keyBlue
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)

		self['list'] = self.chooseMenuList
		self['title'] = Label(_("Timer-Konflikte"))
		self['cancel'] = Label(_("Abbrechen"))
		self['red'] = Label(_("Abbrechen"))
		self['blue'] = Label(_("Liste leeren"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

		self.onLayoutFinish.append(self.readConflicts)

	def readConflicts(self):
		self.conflictsListe = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM TimerKonflikte ORDER BY StartZeitstempel")
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
		
	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()
		
	def keyBlue(self):
		check = self['list'].getCurrent()
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
			
	def keyCancel(self):
		self.close()

class serienRecWishlist(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		# Skin
		self.skinName = "SerienRecorderWishlist"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRWishlist.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"red"	: self.keyRed,
			"green" : self.save,
			"yellow": self.keyYellow,
			"blue"	: self.keyBlue
		}, -1)

		#normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()

		self.modus = "list"
		self['list'] = self.chooseMenuList
		self['title'] = Label(_("Diese Episoden sind zur Aufnahme vorgemerkt"))
		self['red'] = Label(_("Eintrag löschen"))
		self['green'] = Label(_("Speichern"))
		self['ok'] = Label(_("Eintrag anlegen"))
		self['yellow'] = Label(_("Sortieren"))
		self['blue'] = Label(_("Liste leeren"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		
		self.delAdded = False
		self.sortedList = False
		self.addedliste = []
		self.addedliste_tmp = []
		self.dbData = []
		
		self.onLayoutFinish.append(self.readWishlist)

	def save(self):
		if self.delAdded:
			cCursor = dbSerRec.cursor()
			cCursor.executemany("DELETE FROM Merkzettel WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?", self.dbData)
			dbSerRec.commit()
			cCursor.close()
		self.close()
			
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
			
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def buildList_popup(self, entry):
		(Serie,) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 10, 0, 560, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, Serie)
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
					cCursor.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?)", (self.aSerie, self.aStaffel, str(i).zfill(2), AnzahlAufnahmen))
				dbSerRec.commit()
				cCursor.close()
				self.readWishlist()

	def keyOK(self):
		if self.modus == "list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			self['list'].hide()
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
			self.modus = "list"
			self['list'].show()
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
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Merkzettel ist leer."
			return
		else:
			zeile = self['list'].getCurrent()[0]
			(title, serie, staffel, episode) = zeile
			self.dbData.append((serie.lower(), staffel, episode))
			self.addedliste_tmp.remove(zeile)
			self.addedliste.remove(zeile)
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			self.delAdded = True;
			
	def keyYellow(self):
		if len(self.addedliste_tmp) != 0:
			if self.sortedList:
				self.addedliste_tmp = self.addedliste[:]
				self['yellow'].setText(_("Sortieren"))
				self.sortedList = False
			else:
				self.addedliste_tmp.sort()
				self['yellow'].setText(_("unsortierte Liste"))
				self.sortedList = True
			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		
	def keyBlue(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Merkzettel ist leer."
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, _("Soll die Liste wirklich geleert werden?"), MessageBox.TYPE_YESNO, default = False)
			else:
				cCursor = dbSerRec.cursor()
				cCursor.execute("DELETE FROM Merkzettel")
				dbSerRec.commit()
				cCursor.close()
				self.readWishlist()

	def callDeleteMsg(self, answer):
		if answer:
			cCursor = dbSerRec.cursor()
			cCursor.execute("DELETE FROM Merkzettel")
			dbSerRec.commit()
			cCursor.close()
			self.readWishlist()
		else:
			return
			
	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def keyCancel(self):
		self.close()

class serienRecShowInfo(Screen):
	def __init__(self, session, serieName, serieUrl):
		Screen.__init__(self, session)
		self.session = session
		self.serieName = serieName
		self.serieUrl = serieUrl

		# Skin
		self.skinName = "SerienRecorderShowInfo"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sskins/SRShowInfo.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"up"	: self.pageUp,
			"down"	: self.pageDown,
			"cancel": self.keyCancel
		}, -1)

		self["list"] = ScrollLabel()
		self['title'] = Label(_("Serien Beschreibung: %s") % self.serieName)
		self['red'] = Label(_("Zurück"))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)
		self['cover'] = Pixmap()
		
		self.onLayoutFinish.append(self.getData)

	def getData(self):
		getPage(self.serieUrl, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseData).addErrback(self.dataError)
		self.showCover()

	def parseData(self, data):
		info = re.findall('<p class="mb4 credits">(.*?)</div>', data, re.S)
		if info:
			beschreibung = re.sub('<.*?>', '', info[0])
			#self["list"].setText(str(beschreibung.replace('&amp:','&')))
			beschreibung = unicode(beschreibung, 'ISO-8859-1')
			beschreibung = beschreibung.encode('utf-8')
			self["list"].setText(str(beschreibung).replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"'))

	def showCover(self):
		serien_nameCover = "/tmp/serienrecorder/%s.png" % self.serieName
		if fileExists(serien_nameCover):
			self.picload = ePicLoad()
			self['cover'].instance.setPixmap(gPixmapPtr())
			scale = AVSwitch().getFramebufferScale()
			size = self['cover'].instance.size()
			self.picload.setPara((size.width(), size.height(), scale[0], scale[1], False, 1, "#FF000000"))
			if self.picload.startDecode(serien_nameCover, 0, 0, False) == 0:
				ptr = self.picload.getData()
				if ptr != None:
					self['cover'].instance.setPixmap(ptr)
					self['cover'].show()
					del self.picload
		else:
			print("Coverfile not found: %s" %  serien_nameCover)

	def dataError(self, error):
		print error

	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()

	def keyCancel(self):
		self.close()

class serienRecShowImdbVideos(Screen):
	def __init__(self, session, ilink):
		Screen.__init__(self, session)
		self.session = session
		self.ilink = ilink

		# Skin
		self.skinName = "SerienRecorderShowImdbVideos"
		skin = None
		#SRWide = getDesktop(0).size().width()
		skin = "%sSRShowImdbVideos.xml" % serienRecMainPath
		if skin:
			SRSkin = open(skin)
			self.skin = SRSkin.read()
			SRSkin.close()
			
		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel
			#"red"	: self.keyRed,
			#"green" : self.keyGreen,
			#"yellow": self.keyYellow,
			#"blue"	: self.keyBlue,
			#"right" : self.keyRight,
			#"up"    : self.keyUp,
			#"down"  : self.keyDown
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)

		self.picload = ePicLoad()
		self['cover'] = Pixmap()
		self['list'] = self.chooseMenuList
		self['title'] = Label(_("Lade imdbVideos.."))
		self['version'] = Label(_("Serien Recorder v%s") % config.plugins.serienRec.showversion.value)

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		
		self.onLayoutFinish.append(self.getVideos)

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
		check = self['list'].getCurrent()
		if check == None:
			return

		url = self['list'].getCurrent()[0][0]
		image = self['list'].getCurrent()[0][1]
		print url
		
		stream = imdbVideo().stream_url(url)
		if stream != None:
			#sref = eServiceReference(0x1001, 0, stream)
			sref = eServiceReference(4097, 0, stream)
			self.session.open(MoviePlayer, sref)

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
		<screen name="SerienRecorderAbout" position="%d,%d" size="550,250" title="%s" >
			<widget name="pluginInfo"	position="5,5"   size="550,240" valign="center" halign="left"  zPosition="5" transparent="1" foregroundColor="white" font="Regular;14"/>       
		</screen>""" % ((DESKTOP_WIDTH - 550) / 2, (DESKTOP_HEIGHT - 250) / 2, _("Über SerienRecorder"),)

	def __init__(self,session):
		self.session = session
		Screen.__init__(self, session)

		self["actions"] = ActionMap(["OkCancelActions"], {
			"cancel": self.exit,
			"ok": self.exit
		}, -1)

		#self.info =("SerienRecorder for Enigma2 (v%s) (c) 2014 by einfall\n"
        #            "(in cooperation with w22754)\n"
		#			"\n"
		#			"For more info:\nhttp://www.vuplus-support.org/wbb3/index.php?page=Thread&threadID=60724\n"
		#			"(if you like this plugin, we would be pleased about a small donation!)\n") % config.plugins.serienRec.showversion.value

		self.info =("SerienRecorder for Enigma2 (v%s) (c) 2014 by einfall\n") % config.plugins.serienRec.showversion.value
		
		self["pluginInfo"] = Label(self.info)

	def exit(self):
		self.close()
        
def getNextWakeup():
	color_print = "\033[93m"
	color_end = "\33[0m"

	if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.timeUpdate.value:
		#writeLog(_("[Serien Recorder] Deep-Standby WakeUp: AN"))
		print color_print+"[Serien Recorder] Deep-Standby WakeUp: AN" +color_end
		now = time.localtime()
		current_time = int(time.time())
		
		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0], config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			#writeLog(_("[Serien Recorder] WakeUp-Timer + 1 day."))
			print color_print+"[Serien Recorder] WakeUp-Timer + 1 day."+color_end
			begin = begin + 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin = begin - 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		#writeLog(_("[Serien Recorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit))
		print color_print+"[Serien Recorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit +color_end

		return begin
	else:
		#writeLog(_("[Serien Recorder] Deep-Standby WakeUp: AUS"))
		print color_print+"[Serien Recorder] Deep-Standby WakeUp: AUS" +color_end

		#return

def autostart(reason, **kwargs):
	session = kwargs.get("session", None)
	color_print = "\033[93m"
	color_end = "\33[0m"
	initDB()
	if config.plugins.serienRec.update.value or config.plugins.serienRec.timeUpdate.value:
		print color_print+"[Serien Recorder] AutoCheck: AN"+color_end
		serienRecCheckForRecording(session, False)
		#autocheck = serienRecCheckForRecording(session, False)
	else:
		print color_print+"[Serien Recorder] AutoCheck: AUS"+color_end

def main(session, **kwargs):
	session.open(serienRecMain)

def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=autostart, wakeupfnc=getNextWakeup),
		#PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc = autostart, wakeupfnc=getNextWakeup,
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=main),
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=main)
		]
