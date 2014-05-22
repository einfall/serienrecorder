# -*- coding: utf-8 -*-
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

from enigma import eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER, loadPNG, RT_WRAP, eServiceReference, getDesktop, loadJPG, RT_VALIGN_CENTER, gPixmapPtr, ePicLoad, eTimer
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

config.plugins.serienRec = ConfigSubsection()
config.plugins.serienRec.savetopath = ConfigText(default = "/media/hdd/movie/",  fixed_size=False)
config.plugins.serienRec.fake_entry = NoSave(ConfigNothing())
config.plugins.serienRec.seriensubdir = ConfigYesNo(default = False)
config.plugins.serienRec.justplay = ConfigYesNo(default = False)
config.plugins.serienRec.eventid = ConfigYesNo(default = True)
config.plugins.serienRec.update = ConfigYesNo(default = False)
config.plugins.serienRec.updateInterval = ConfigInteger(0, (0,24))
config.plugins.serienRec.timeUpdate = ConfigYesNo(default = False)
config.plugins.serienRec.deltime = ConfigClock(default = 6*3600)
config.plugins.serienRec.checkfordays = ConfigInteger(1, (1,14))
config.plugins.serienRec.fromTime = ConfigInteger(00, (00,23))
config.plugins.serienRec.toTime = ConfigInteger(23, (00,23))
config.plugins.serienRec.forceRecording = ConfigYesNo(default = False)
config.plugins.serienRec.margin_before = ConfigInteger(default_before, (00,99))
config.plugins.serienRec.margin_after = ConfigInteger(default_after, (00,99))
config.plugins.serienRec.max_season = ConfigInteger(30, (01,999))
config.plugins.serienRec.Alternatetimer = ConfigYesNo(default = True)
config.plugins.serienRec.Autoupdate = ConfigYesNo(default = True)
#config.plugins.serienRec.pastTimer = ConfigYesNo(default = False)
config.plugins.serienRec.wakeUpDSB = ConfigYesNo(default = False)
config.plugins.serienRec.afterAutocheck = ConfigYesNo(default = False)
config.plugins.serienRec.writeLog = ConfigYesNo(default = True)
config.plugins.serienRec.showNotification = ConfigYesNo(default = True)
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
config.plugins.serienRec.recordAll = ConfigYesNo(default = False)
config.plugins.serienRec.showMessageOnConflicts = ConfigYesNo(default = True)

# interne
config.plugins.serienRec.version = NoSave(ConfigText(default="023"))
config.plugins.serienRec.showversion = NoSave(ConfigText(default="2.4beta5"))
config.plugins.serienRec.screenmode = ConfigInteger(0, (0,2))
config.plugins.serienRec.screeplaner = ConfigInteger(1, (1,3))
config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))

dbTmp = sqlite3.connect(":memory:")
#dbTmp = sqlite3.connect("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/SR_Tmp.db")
dbTmp.text_factory = str
dbSerRec = sqlite3.connect("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/SerienRecorder.db")
dbSerRec.text_factory = str
#dbSerRec.text_factory = unicode

def iso8859_Decode(txt):
	#txt = txt.replace('\xe4','ä').replace('\xf6','ö').replace('\xfc','ü').replace('\xdf','ß')
	#txt = txt.replace('\xc4','Ä').replace('\xd6','Ö').replace('\xdc','Ü')
	txt = txt.replace('\xe4','ae').replace('\xf6','oe').replace('\xfc','ue').replace('\xdf','ss')
	txt = txt.replace('\xc4','Ae').replace('\xd6','Oe').replace('\xdc','Ue')
	txt = txt.replace('...','').replace('..','').replace(':','').replace('\xb2','2')
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
	found = False
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?", (serie.lower(), staffel, episode))
	row = cCursor.fetchone()
	if row:
		found = True
	cCursor.close()
	return found

def allowedTimeRange(f,t):
	liste = ['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23']
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
	date = datetime.datetime(int(now.year),int(month),int(day),int(hour),int(min))
	date += datetime.timedelta(days=1)
	return date.strftime("%s")

def getUnixTimeAll(min, hour, day, month):
	now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	return datetime.datetime(now.year, int(month), int(day), int(hour), int(min)).strftime("%s")
	
def getUnixTime(std, min):
	now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	return datetime.datetime(now.year, now.month, now.day, int(std), int(min)).strftime("%s")

def getUnixTimeWithDayOffset(std, min, AddDays):
	now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	date = datetime.datetime(now.year, now.month, now.day, int(std), int(min))
	date += datetime.timedelta(days=AddDays)
	return date.strftime("%s")

def getRealUnixTime(min, std, day, month, year):
	#now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	return datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")

def getMarker():
	return_list = []
	cCursor = dbSerRec.cursor()
	cCursor.execute("SELECT * FROM SerienMarker ORDER BY Serie")
	cMarkerList = cCursor.fetchall()
	for row in cMarkerList:
		(ID, serie, url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode) = row
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
		
		return_list.append((serie, url, staffeln, sender, AbEpisode))
	cCursor.close()
	return return_list

def getServiceList(ref):
	root = eServiceReference(str(ref))
	serviceHandler = eServiceCenter.getInstance()
	return serviceHandler.list(root).getContent("SN", True)

def getTVBouquets():
	return getServiceList(service_types_tv + ' FROM BOUQUET "bouquets.tv" ORDER BY bouquet')

def buildSTBchannellist():
	serien_chlist = None
	serien_chlist = []
	print "[SerienRecorder] read STV Channellist.."
	tvbouquets = getTVBouquets()
	print "[SerienRecorder] found %s bouquet: %s" % (len(tvbouquets), tvbouquets)

	for bouquet in tvbouquets:
		bouquetlist = []
		bouquetlist = getServiceList(bouquet[0])
		for (serviceref, servicename) in bouquetlist:
			serien_chlist.append((servicename, serviceref))
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
			#if int(int(starttime)-60) == int(begin) or int(int(starttime)+60) == int(begin) or int(starttime) == int(begin):
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
		logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
		if not fileExists(logFile):
			open(logFile, 'w').close()

		writeLogFile = open(logFile, "a")
		writeLogFile.write('%s\n' % (text))
		writeLogFile.close()

def writeLogFilter(type, text, forceWrite=False):
	if config.plugins.serienRec.writeLog.value or forceWrite:
		logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
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

class serienRecCheckForRecording():

	instance = None

	def __init__(self, session, manuell):
		assert not serienRecCheckForRecording.instance, "Go is a singleton class!"
		serienRecCheckForRecording.instance = self
		self.session = session
		self.manuell = manuell
		self.daylist = []
		self.page = 1
		self.timermode = False
		self.timermode2 = False
		self.color_print = "\033[93m"
		self.color_end = "\33[0m"
		self.logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"

		self.daypage = 0
		cCursor = dbSerRec.cursor()
		
		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		cCursor.execute("SELECT * FROM SerienMarker")
		row = cCursor.fetchone()
		if not row:
			writeLog("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[Serien Recorder] check: Tabelle SerienMarker leer."
			writeLog("[Serien Recorder] check: Tabelle SerienMarker leer.", True)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			cCursor.close()
			return

		cCursor.execute("SELECT * FROM Channels")
		row = cCursor.fetchone()
		if not row:
			writeLog("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[Serien Recorder] check: Tabelle Channels leer."
			writeLog("[Serien Recorder] check: Tabelle Channels leer.", True)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			cCursor.close()
			return
		cCursor.close()
		
		self.justplay = False
		if config.plugins.serienRec.justplay.value:
			self.justplay = True

		#self.dirname = config.plugins.serienRec.savetopath.value
		self.tags = None

		if not self.manuell and config.plugins.serienRec.update.value:
			self.refreshTimer = eTimer()
			self.refreshTimer.callback.append(self.startCheck)
			updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
			self.refreshTimer.start(updateZeit)
			self.timermode = True
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer gestartet."+self.color_end
			writeLog("[Serien Recorder] AutoCheck Hour-Timer gestartet.", True)
		elif not self.manuell and config.plugins.serienRec.timeUpdate.value:
			loctime = localtime()
			acttime = (loctime[3] * 60 + loctime[4])
			deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
			if acttime < deltime:
				deltatime = deltime - acttime
			else:
				#print "Timeeerrrrrrrrrrrrrrrrrrr: + 1 day"
				deltatime = abs(1440 - acttime + deltime)
			self.refreshTimer2 = eTimer()
			self.refreshTimer2.callback.append(self.startCheck)
			self.refreshTimer2.start(deltatime * 60 * 1000, False)
			self.timermode2 = True
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer gestartet."+self.color_end
			print self.color_print+"[Serien Recorder] Minutes left: " + str(deltatime)+self.color_end
			writeLog("[Serien Recorder] AutoCheck Clock-Timer gestartet.", True)
			writeLog("[Serien Recorder] Minutes left: %s" % str(deltatime), True)
			
		else:
			print "[Serien Recorder] checkRecTimer manuell."
			self.startCheck(True)

	def startCheck(self, amanuell=False):
		print self.color_print+"[Serien Recorder] settings:"+self.color_end
		print "manuell:", amanuell
		print "stunden check:", config.plugins.serienRec.update.value
		print "uhrzeit check:", config.plugins.serienRec.timeUpdate.value
		print "timermode:", self.timermode
		print "timermode2:", self.timermode2

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		if self.timermode:
			self.refreshTimer.stop()
			self.timermode2 = False
			print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer stop."+self.color_end
			if config.plugins.serienRec.update.value:
				self.refreshTimer = eTimer()
				self.refreshTimer.callback.append(self.startCheck)
				updateZeit = int(config.plugins.serienRec.updateInterval.value) * 3600000
				self.refreshTimer.start(updateZeit)
				self.timermode = True
				print self.color_print+"[Serien Recorder] AutoCheck Hour-Timer gestartet."+self.color_end
				writeLog("[Serien Recorder] AutoCheck Hour-Timer gestartet.", True)
		elif self.timermode2:
			self.refreshTimer2.stop()
			self.timermode2 = False
			print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer stop."+self.color_end
			writeLog("[Serien Recorder] [Serien Recorder] AutoCheck Clock-Timer stop.", True)
			if config.plugins.serienRec.timeUpdate.value:
				loctime = localtime()
				acttime = (loctime[3] * 60 + loctime[4])
				deltime = (config.plugins.serienRec.deltime.value[0] * 60 + config.plugins.serienRec.deltime.value[1])
				if acttime < deltime:
					deltatime = deltime - acttime
				else:
					deltatime = abs(1440 - acttime + deltime)
				self.refreshTimer2 = eTimer()
				self.refreshTimer2.callback.append(self.startCheck)
				self.refreshTimer2.start(deltatime * 60 * 1000, False)
				self.timermode2 = True
				print self.color_print+"[Serien Recorder] AutoCheck Clock-Timer gestartet."+self.color_end
				print self.color_print+"[Serien Recorder] Minutes left: " + str(deltatime)+self.color_end
				writeLog("[Serien Recorder] AutoCheck Clock-Timer gestartet.", True)
				writeLog("[Serien Recorder] Minutes left: %s" % str(deltatime), True)

		# logFile leeren (renamed to _old)
		if fileExists(self.logFile):
			shutil.copy(self.logFile,"%s_old" % self.logFile)
		open(self.logFile, 'w').close()

		if amanuell:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog("\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page)), True)
		else:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog("\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page)), True)
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
		ds = defer.DeferredSemaphore(tokens=100)
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
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)

				if str(episode).isdigit() and str(staffel).isdigit():
					if int(episode) == 1:
						(webChannel, stbChannel, stbRef, status) = self.checkSender(self.senderListe, sender)
						if int(status) == 1:
							if not self.checkMarker(serien_name):
								cCursor = dbSerRec.cursor()
								cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE Serie=? AND Staffel=?", (serien_name, staffel))
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
										cCursor.execute("SELECT * FROM NeuerStaffelbeginn WHERE Serie=? AND Staffel=?", (serien_name, staffel))
										row = cCursor.fetchone()
										if not row:
											data = (serien_name, staffel, sender, head_datum[0], UTCDatum, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id, "2") 
											cCursor.execute("INSERT OR IGNORE INTO NeuerStaffelbeginn (Serie, Staffel, Sender, StaffelStart, UTCStaffelStart, Url, CreationFlag) VALUES (?, ?, ?, ?, ?, ?, ?)", data)
											dbSerRec.commit()

											if not amanuell:
												if config.plugins.serienRec.ActionOnNew.value == "1" or config.plugins.serienRec.ActionOnNew.value == "3":
													Notifications.AddPopup(_("[Serien Recorder]\nSerien- / Staffelbeginn wurde gefunden.\nDetaillierte Information im SerienRecorder mit Taste '3'"), MessageBox.TYPE_INFO, timeout=-1)
								cCursor.close()
							
	def createNewMarker(self, result=True):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, StaffelStart FROM NeuerStaffelbeginn WHERE CreationFlag>0")
		for row in cCursor:
			(Serie, Staffel, StaffelStart) = row
			writeLog("[Serien Recorder] %d. Staffel von '%s' beginnt am %s" % (int(Staffel), Serie, StaffelStart), True) 

		if config.plugins.serienRec.ActionOnNew.value == "2" or config.plugins.serienRec.ActionOnNew.value == "3":
			cCursor.execute("SELECT Serie, MIN(Staffel), Sender, Url FROM NeuerStaffelbeginn WHERE CreationFlag=1 GROUP BY Serie")
			for row in cCursor:
				(Serie, Staffel, Sender, Url) = row
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender) VALUES (?, ?, ?, 0)", (Serie, Url, Staffel))
				cCursor.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (cCursor.lastrowid, Sender))
				writeLog("[Serien Recorder] Neuer Marker für '%s' wurde angelegt" % Serie, True)
			cCursor.execute("UPDATE OR IGNORE NeuerStaffelbeginn SET CreationFlag=0 WHERE CreationFlag=1")
			dbSerRec.commit()
		cCursor.close()
		return result

	def adjustEPGtimes(self, current_time):
		cTimer = dbSerRec.cursor()
		cCursor = dbSerRec.cursor()

		cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>? AND EventID=0", (current_time, ))
		for row in cCursor:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row
					
			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			if config.plugins.serienRec.eventid.value:
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(serien_time)+(int(config.plugins.serienRec.margin_before.value) * 60), -1)], stbRef, serien_name, int(serien_time)+(int(config.plugins.serienRec.margin_before.value) * 60))
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
						if config.plugins.serienRec.seriensubdir.value:
							dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
						else:
							dirname = config.plugins.serienRec.savetopath.value
						writeLog("[Serien Recorder] Versuche Timer zu aktualisieren: ' %s - %s '" % (title, dirname))
						eit = int(event_entry[1])
						new_start_unixtime = int(event_entry[3]) - (int(config.plugins.serienRec.margin_before.value) * 60)
						new_end_unixtime = int(event_entry[3]) + int(event_entry[4]) + (int(config.plugins.serienRec.margin_after.value) * 60)
						
						print "[Serien Recorder] try to modify enigma2 Timer:", title, serien_time
						recordHandler = NavigationInstance.instance.RecordTimer
						try:
							for timer in recordHandler.timer_list:
								if timer and timer.service_ref:
									if (timer.begin == int(serien_time)) and (timer.eit != eit):
										timer.begin = new_start_unixtime
										timer.end = new_end_unixtime
										timer.eit = eit
										NavigationInstance.instance.RecordTimer.timeChanged(timer)
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=? WHERE StartZeitstempel>? AND ServiceRef=? AND EventID=0"
										cTimer.execute(sql, (new_start_unixtime, eit, current_time, stbRef))
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(new_start_unixtime)))
										writeLog("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> %s %s @ %s" % (title, show_start, title, webChannel), True)
										self.countTimerUpdate += 1
										break
						except Exception:				
							print "[Serien Recorder] Modify enigma2 Timer failed:", title, serien_time
						break
						
		dbSerRec.commit()
					
		cCursor.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE StartZeitstempel>? AND EventID>0", (current_time, ))
		for row in cCursor:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row

			epgmatches = []
			epgcache = eEPGCache.getInstance()
			allevents = epgcache.lookupEvent(['IBD',(stbRef, 2, eit, -1)]) or []

			for eventid, begin, duration in allevents:
				if int(eventid) == int(eit):
					if int(begin) != (int(serien_time) + (int(config.plugins.serienRec.margin_before.value) * 60)):
						title = "%s - S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), serien_title)
						if config.plugins.serienRec.seriensubdir.value:
							dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
						else:
							dirname = config.plugins.serienRec.savetopath.value
						writeLog("[Serien Recorder] Versuche Timer zu aktualisieren: ' %s - %s '" % (title, dirname))
						start_unixtime = int(begin)
						start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
						end_unixtime = int(begin) + int(duration)
						end_unixtime = int(end_unixtime) + (int(config.plugins.serienRec.margin_after.value) * 60)
						
						print "[Serien Recorder] try to modify enigma2 Timer:", title, serien_time
						recordHandler = NavigationInstance.instance.RecordTimer
						try:
							for timer in recordHandler.timer_list:
								if timer and timer.service_ref:
									if timer.eit == eit:
										timer.begin = start_unixtime
										timer.end = end_unixtime
										NavigationInstance.instance.RecordTimer.timeChanged(timer)
										sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=? WHERE StartZeitstempel>? AND ServiceRef=? AND EventID=?"
										cTimer.execute(sql, (start_unixtime, current_time, stbRef, eit))
										show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
										writeLog("[Serien Recorder] ' %s ' - Timer wurde aktualisiert -> %s %s @ %s" % (title, show_start, title, webChannel), True)
										self.countTimerUpdate += 1
										break
						except Exception:				
							print "[Serien Recorder] Modify enigma2 Timer failed:", title, serien_time
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
		self.countSerien = self.countMarker()
		ds = defer.DeferredSemaphore(tokens=100)
		downloads = [ds.run(self.download, SerieUrl).addCallback(self.parseWebpage,serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode).addErrback(self.dataError) for serienTitle,SerieUrl,SerieStaffel,SerieSender,AbEpisode in self.urls]
		finished = defer.DeferredList(downloads).addCallback(self.createTimer).addErrback(self.dataError)
		
	def download(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, timeout=20, headers={'Content-Type':'application/x-www-form-urlencoded'})

	def parseWebpage(self, data, serien_name, SerieUrl, staffeln, allowedSender, AbEpisode):
		self.count_url += 1
		parsingOK = True
		#writeLog("[Serien Recorder] LOG READER: '%s/%s'" % (str(self.count_url), str(self.countSerien)))
		raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		if raw:
			parsingOK = True
			print "raw"
		else:
			raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
			if raw2:
				nlist = []
				for each in raw2:
					#print each
					each = list(each)
					each.insert(4, "0")
					nlist.append(each)
				parsingOK = True
				print "raw2"
				raw = nlist

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

		# loop over all transmissions
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			# umlaute umwandeln
			serien_name = iso8859_Decode(serien_name)
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
			sender = iso8859_Decode(sender)
			title = iso8859_Decode(title)

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
			start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
			end_unixtime = int(end_unixtime) + (int(config.plugins.serienRec.margin_after.value) * 60)

			##############################
			#
			# CHECK
			#
			# ueberprueft welche sender aktiviert und eingestellt sind.
			#
			(webChannel, stbChannel, stbRef, status) = self.checkSender(self.senderListe, sender)
			if stbChannel == "":
				#print "[Serien Recorder] ' %s ' - STB-Channel nicht gefunden -> ' %s '" % (label_serie, webChannel)
				writeLogFilter("channels", "[Serien Recorder] ' %s ' - STB-Channel nicht gefunden ' -> ' %s '" % (label_serie, webChannel))
				continue
				
			if int(status) == 0:
				#print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (label_serie, webChannel)
				writeLogFilter("channels", "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (label_serie, webChannel))
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
				writeLogFilter("allowedSender", "[Serien Recorder] ' %s ' - Sender nicht erlaubt -> %s -> %s" % (label_serie, sender, allowedSender))
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
								liste[0] = "ab %s" % liste[0]
							liste.reverse()
							liste.insert(0, "0 ab E%s" % str(AbEpisode).zfill(2))
							writeLogFilter("allowedEpisodes", "[Serien Recorder] ' %s ' - Episode nicht erlaubt -> ' S%sE%s ' -> ' %s '" % (label_serie, str(staffel).zfill(2), str(episode).zfill(2), str(liste).replace("'", "").replace('"', "")))
							continue
						else:
							serieAllowed = True
				elif int(staffel) in staffeln:
					serieAllowed = True
				elif -1 in staffeln:		# 'folgende'
					if int(staffel) >= max(staffeln):
						serieAllowed = True
					
			if not serieAllowed:
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
				writeLogFilter("allowedEpisodes", "[Serien Recorder] ' %s ' - Staffel nicht erlaubt -> ' S%sE%s ' -> ' %s '" % (label_serie, str(staffel).zfill(2), str(episode).zfill(2), str(liste).replace("'", "").replace('"', "")))
				continue

			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit = 0
			if config.plugins.serienRec.eventid.value:
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_unixtime)+(int(config.plugins.serienRec.margin_before.value) * 60), -1)], stbRef, serien_name, int(start_unixtime)+(int(config.plugins.serienRec.margin_before.value) * 60))
				print "event matches %s" % len(event_matches)
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
						eit = int(event_entry[1])
						start_unixtime = int(event_entry[3]) - (int(config.plugins.serienRec.margin_before.value) * 60)
						break
						
			if config.plugins.serienRec.seriensubdir.value:
				dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
			else:
				dirname = config.plugins.serienRec.savetopath.value
				
			check_SeasonEpisode = "S%sE%s" % (str(staffel).zfill(2), str(episode).zfill(2))

			self.cCursorTmp = dbTmp.cursor()
			sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, Title, Staffel, Episode, LabelSerie, StartTime, EndTime, ServiceRef, EventID, DirName, SerieName, webChannel, stbChannel, SeasonEpisode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
			self.cCursorTmp.execute(sql, (current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode))
			
	def createTimer(self, result=True):
		#dbTmp.commit()
		self.cCursorTmp.execute("VACUUM")
		dbTmp.commit()
		self.cCursorTmp.close()

		# jetzt die Timer erstellen		
		self.searchTimer()
		
		# gleiche alte Timer mit EPG ab
		current_time = int(time.time())
		if config.plugins.serienRec.eventid.value:
			self.adjustEPGtimes(current_time)
	
		# Datenbank aufräumen
		cCursor = dbSerRec.cursor()
		cCursor.execute("VACUUM")
		cCursor.close()

		# Statistik
		self.speedEndTime = time.clock()
		speedTime = (self.speedEndTime-self.speedStartTime)
		if config.plugins.serienRec.eventid.value:
			writeLog("[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate)), True)
			print "[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt und %s Timer aktualisiert." % (str(self.countSerien), str(self.countTimer), str(self.countTimerUpdate))
		else:
			writeLog("[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countSerien), str(self.countTimer)), True)
			print "[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countSerien), str(self.countTimer))
		writeLog("---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------" % str(speedTime), True)
		print "---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------" % str(speedTime)
		
		# in den deep-standby fahren.
		if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.afterAutocheck.value and not self.manuell:
			print "[Serien Recorder] gehe in Deep-Standby"
			writeLog("[Serien Recorder] gehe in Deep-Standby")
			self.session.open(TryQuitMainloop, 1)
		return result
				
	def searchTimer(self):
		# prepare valid time range
		timeRangeList = allowedTimeRange(config.plugins.serienRec.fromTime.value, config.plugins.serienRec.toTime.value)
		timeRange = {}.fromkeys(timeRangeList, 0)
		
		cTmp = dbTmp.cursor()
		cTmp.execute("SELECT * FROM (SELECT SerieName, Staffel, Episode, COUNT(*) AS Anzahl FROM GefundeneFolgen GROUP BY SerieName, Staffel, Episode) ORDER BY Anzahl")
		for row in cTmp:
			(serien_name, staffel, episode, anzahl) = row

			##############################
			#
			# erstellt das serien verzeichnis
			if config.plugins.serienRec.seriensubdir.value:
				if not fileExists("%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)):
					print "[Serien Recorder] erstelle Subdir %s" % config.plugins.serienRec.savetopath.value+serien_name+"/"
					writeLog("[Serien Recorder] erstelle Subdir: ' %s%s%s '" % (config.plugins.serienRec.savetopath.value, serien_name, "/"))
					os.makedirs("%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name))
					if fileExists("/var/volatile/tmp/serienrecorder/%s.png" % (serien_name)) and not fileExists("/var/volatile/tmp/serienrecorder/%s.jpg" % (serien_name)):
						#print "vorhanden...:", "/var/volatile/tmp/serienrecorder/"+serien_name+".png"
						shutil.copy("/var/volatile/tmp/serienrecorder/%s.png" % serien_name, "%s%s/%s.jpg" % (config.plugins.serienRec.savetopath.value, serien_name, serien_name))
				else:
					if fileExists("/var/volatile/tmp/serienrecorder/%s.png" % serien_name) and not fileExists("/var/volatile/tmp/serienrecorder/%s.jpg" % serien_name):
						#print "vorhanden...:", "/var/volatile/tmp/serienrecorder/"+serien_name+".png"
						shutil.copy("/var/volatile/tmp/serienrecorder/%s.png" % serien_name, "%s%s/%s.jpg" % (config.plugins.serienRec.savetopath.value, serien_name, serien_name))

			# prepare postprocessing for forced recordings
			forceRecordings = []
			self.konflikt = ""

			TimerDone = False
			cTimer = dbTmp.cursor()
			cTimer.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND Staffel=? AND LOWER(Episode)=? ORDER BY StartTime", (serien_name.lower(), staffel, episode.lower()))
			for row2 in cTimer:
				(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode) = row2
		
				##############################
				#
				# CHECK
				#
				# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
				#
				# check im added file
				if checkAlreadyAdded(serien_name, staffel, episode):
					writeLogFilter("added", "[Serien Recorder] ' %s ' - Staffel/Episode bereits in added vorhanden -> ' %s '" % (label_serie, check_SeasonEpisode))
					if not config.plugins.serienRec.recordAll.value: 
						TimerDone = True
						break

				# check hdd
				bereits_vorhanden = False
				if fileExists(dirname):
					dirs = os.listdir(dirname)
					for dir in dirs:
						if re.search(serien_name+'.*?'+check_SeasonEpisode, dir):
							bereits_vorhanden = True
							break

				if bereits_vorhanden:
					writeLogFilter("disk", "[Serien Recorder] ' %s ' - Staffel/Episode bereits auf hdd vorhanden -> ' %s '" % (label_serie, check_SeasonEpisode))
					if not config.plugins.serienRec.recordAll.value: 
						TimerDone = True
						break
					
				##############################
				#
				# CHECK
				#
				# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt und finde Wiederholungen auf dem gleichen Sender
				#
				start_hour = str(time.localtime(int(start_unixtime)).tm_hour).zfill(2)
				if not start_hour in timeRange:
					writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Zeitspanne %s nicht in %s" % (label_serie, start_hour, timeRangeList))
					# forced recording activated?
					if not config.plugins.serienRec.forceRecording.value:
						continue
						
					## already saved?
					#if serien_name+check_SeasonEpisode+webChannel in forceRecordings:
					#	continue
						
					# backup timer data for post processing
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
					writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Backup Timer -> %s" % (label_serie, show_start))
					forceRecordings.append((title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode))
					continue
					
				## time in time range - remove from forceRecordings
				#timer_backup = []
				#if serien_name+check_SeasonEpisode+webChannel in forceRecordings:
				#	show_start_old = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(forceRecordings[serien_name+check_SeasonEpisode+webChannel][4])))
				#	show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
				#	writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Wiederholung gefunden -> %s -> entferne Timer Backup -> %s" % (label_serie, show_start, show_start_old))
				#	timer_backup = forceRecordings.pop(serien_name+check_SeasonEpisode+webChannel)

				##############################
				#
				# Setze Timer
				#
				if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode):
					TimerDone = True
					break
				#else:
				#	if len(timer_backup) != 0:
				#		show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
				#		( title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode ) = timer_backup
				#		show_start_old = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
				#		writeLog("[Serien Recorder] ' %s ' - Wiederholung konnte nicht programmiert werden -> %s -> Versuche Timer Backup -> %s" % (label_serie, show_start, show_start_old), True)
				#		if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode):
				#			TimerDone = True
				#			break
					
			### end of for loop
			cTimer.close()
			
			if not TimerDone:
				# post processing for forced recordings
				for title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode in forceRecordings:
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
					writeLog("[Serien Recorder] ' %s ' - Keine Wiederholung gefunden! -> %s" % (label_serie, show_start), True)
					# programmiere Timer
					if self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode):
						TimerDone = True
						break
						
			if (not TimerDone) and (len(self.konflikt) > 0):
				if config.plugins.serienRec.showMessageOnConflicts.value:
					Notifications.AddPopup(_("[Serien Recorder]\nACHTUNG!  -  %s" % self.konflikt), MessageBox.TYPE_INFO, timeout=-1)
						
		cTmp.close()

	def doTimer(self, current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode):
		##############################
		#
		# CHECK
		#
		# ueberprueft ob tage x  voraus passt und ob die startzeit nicht kleiner ist als die aktuelle uhrzeit
		#
		show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
		if int(start_unixtime) > int(future_time) or int(current_time) > int(start_unixtime):
			#print start_unixtime, future_time, current_time
			if int(start_unixtime) > int(future_time):
				show_future = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(future_time)))
				writeLogFilter("timeLimit", "[Serien Recorder] ' %s ' - Timer wird spaeter angelegt -> Sendetermin: %s - Erlaubte Zeitspanne bis %s" % (label_serie, show_start, show_future))
			elif int(current_time) > int(start_unixtime):
				show_current = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(current_time)))
				writeLogFilter("timeLimit", "[Serien Recorder] ' %s ' - Der Sendetermin liegt in der Vergangenheit: %s - Aktuelles Datum: %s" % (label_serie, show_start, show_current))
			return True
			
		# versuche timer anzulegen
		# setze strings für addtimer
		result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, "S%sE%s - %s" % (str(staffel).zfill(2), str(episode).zfill(2), title), 0, self.justplay, 3, dirname, self.tags, 0, None, eit=eit, recordfile=".ts")
		if result["result"]:
			self.countTimer += 1
			# Eintrag in das timer file
			self.addRecTimer(serien_name, staffel, episode, title, start_unixtime, stbRef, webChannel, eit)
			# Eintrag in das added file
			writeLog("[Serien Recorder] ' %s ' - Timer wurde angelegt -> %s %s @ %s" % (label_serie, show_start, label_serie, stbChannel), True)
			return True
		
		self.konflikt = result["message"].replace("! ", "!\n").replace(" / ", "\n")
		#if config.plugins.serienRec.showMessageOnConflicts.value:
		#	Notifications.AddPopup(_("[Serien Recorder]\nACHTUNG!  -  %s" % self.konflikt), MessageBox.TYPE_INFO, timeout=-1)
		print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
		writeLog("[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"]), True)
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
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels")
		for row in cCursor:
			(webChannel, stbChannel, stbRef, status) = row
			fSender.append((webChannel, stbChannel, stbRef, status))
		cCursor.close()
		return fSender
		
	def checkSender(self, mSlist, mSender):
		if mSender.lower() in mSlist:
			(webChannel, stbChannel, stbRef, status) = mSlist[mSender.lower()]
		else:
			webChannel = mSender
			stbChannel = ""
			stbRef = ""
			status = "0"
		return (webChannel, stbChannel, stbRef, status)

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit):
		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ServiceRef=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		#sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND ?<=StartZeitstempel<=?"
		cCursor.execute(sql, (serien_name.lower(), stbRef, int(start_time) + (int(config.plugins.serienRec.margin_before.value) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(config.plugins.serienRec.margin_before.value) * 60) + (int(EPGTimeSpan) * 60)))
		row = cCursor.fetchone()
		if row:
			sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=? WHERE LOWER(Serie)=? AND ServiceRef=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
			cCursor.execute(sql, (eit, serien_name.lower(), stbRef, int(start_time) + (int(config.plugins.serienRec.margin_before.value) * 60) - (int(EPGTimeSpan) * 60), int(start_time) + (int(config.plugins.serienRec.margin_before.value) * 60) + (int(EPGTimeSpan) * 60)))
			print "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			print "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLogFilter("timerDebug", "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		dbSerRec.commit()
		cCursor.close()
		
	def dataError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error, True)

	def checkError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error, True)
		self.close()

class serienRecAddTimer():

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
				channel = getChannelByRef(serienRec,str(timer.service_ref))
				if channel:
					recordedfile = getRecordFilename(timer.name,timer.description,timer.begin,channel)
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
		return removed

	@staticmethod	
	def addTimer(session, serviceref, begin, end, name, description, disabled, justplay, afterevent, dirname, tags, repeated, logentries=None, eit=0, recordfile=None, forceWrite=True):

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
					disabled,
					0,
					afterevent,
					dirname=dirname,
					tags=tags,
					justremind=justplay)
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
					justplay,
					afterevent,
					dirname=dirname,
					tags=tags)

			timer.repeated = repeated

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
			writeLog("[Serien Recorder] Versuche Timer anzulegen: ' %s - %s '" % (name, dirname))
		return {
			"result": True,
			"message": "Timer '%s' added" % name,
			"eit" : eit
		}

class serienRecMain(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="headline" position="50,10" size="820,55" foregroundColor="red" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="center" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="popup_bg" position="170,130" size="600,480" backgroundColor="#000000" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/popup_bg.png" transparent="1" zPosition="4" />
			<widget name="popup" position="180,170" size="580,370" backgroundColor="#00181d20" scrollbarMode="showOnDemand" transparent="1" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="915,320" size="320,300" transparent="1" alphatest="blend" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_epg.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="info" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/blue_round.png" position="1060,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="blue" position="1100,656" size="250,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_0.png" position="20,685" zPosition="1" size="32,32" alphatest="on" />
			<widget name="0" position="60,691" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_1.png" position="310,685" zPosition="1" size="32,32" alphatest="on" />
			<widget name="1" position="350,691" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_3.png" position="560,685" zPosition="1" size="32,32" alphatest="on" />
			<widget name="3" position="600,691" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()

		self["actions"]  = ActionMap(["HelpActions", "OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
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
			"info"	: self.keyCheck,
			"menu"	: self.recSetup,
			"nextBouquet" : self.nextPage,
			"prevBouquet" : self.backPage,
			"displayHelp" : self.youtubeSearch,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB,
			"9"     : self.importFromFile
		}, -1)

		initDB()
	
		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
		self['list'] = self.chooseMenuList
		self.modus = "list"

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList_popup.l.setItemHeight(30)
		self['popup'] = self.chooseMenuList_popup
		self['popup'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()

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
		self.loading = True
		self.page = 0

		self['cover'] = Pixmap()
		self['title'] = Label("Loading infos from Web...")
		self['headline'] = Label("")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self['red'] = Label("Serientyp auswählen")
		self['green'] = Label("Channels zuweisen")
		self['info'] = Label("Timer suchen")
		self['yellow'] = Label("Serien Marker")
		self['blue'] = Label("Timer-Liste")
		self['0'] = Label("Zeige Log")
		self['1'] = Label("Added Liste")
		self['3'] = Label("Neue Serienstarts")

		#self.onLayoutFinish.append(self.startScreen)
		self.onFirstExecBegin.append(self.startScreen)

	def importFromFile(self):
		ImportFilesToDB()
		self['title'].setText("File-Import erfolgreich ausgeführt")
		self['title'].instance.setForegroundColor(parseColor("white"))
		
	def showProposalDB(self):
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

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

	def setHeadline(self):
		# aktuelle internationale Serien
		if int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 0
			self['headline'].setText("Alle Serien (aktuelle internationale Serien)")
		elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 1
			self['headline'].setText("Neue Serien aktuelle (internationale Serien)")
		elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 2
			self['headline'].setText("Nach aktivierten Sendern (aktuelle internationale Serien)")
		## E01
		elif int(config.plugins.serienRec.screenmode.value) == 3 and int(config.plugins.serienRec.screeplaner.value) == 1:
			self.pNeu = 3
			self['headline'].setText("Alle Serienstarts")
		# soaps
		#elif int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 0
		#	self['headline'].setText("Alle Serien (Soaps)")
		#elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 1
		#	self['headline'].setText("Neue Serien ((Soaps)")
		#elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 2:
		#	self.pNeu = 2
		#	self['headline'].setText("Nach aktivierten Sendern (Soaps)")
		# internationale Serienklassiker
		elif int(config.plugins.serienRec.screenmode.value) == 0 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 0
			self['headline'].setText("Alle Serien (internationale Serienklassiker)")
		elif int(config.plugins.serienRec.screenmode.value) == 1 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 1
			self['headline'].setText("Neue Serien (internationale Serienklassiker)")
		elif int(config.plugins.serienRec.screenmode.value) == 2 and int(config.plugins.serienRec.screeplaner.value) == 3:
			self.pNeu = 2
			self['headline'].setText("Nach aktivierten Sendern (internationale Serienklassiker)")
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
		if config.plugins.serienRec.Autoupdate.value:
			checkupdate(self.session).checkforupdate()
		if self.isChannelsListEmpty():
			print "[Serien Recorder] Channellist is empty !"
			self.session.openWithCallback(self.readWebpage, serienRecMainChannelEdit)
		else:
			self.readWebpage()

	def readWebpage(self):
		url = "http://www.wunschliste.de/serienplaner/%s/%s" % (str(config.plugins.serienRec.screeplaner.value), str(self.page))
		print url
		self.setHeadline()
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.parseWebpage).addErrback(self.dataError)

	def parseWebpage(self, data):
		self.daylist = []
		head_datum = re.findall('<li class="datum">(.*?)</li>', data, re.S)
		raw = re.findall('s_regional\[.*?\]=(.*?);\ns_paytv\[.*?\]=(.*?);\ns_neu\[.*?\]=(.*?);\ns_prime\[.*?\]=(.*?);.*?<td rowspan="3" class="zeit">(.*?) Uhr</td>.*?<a href="(/serie/.*?)">(.*?)</a>.*?href="http://www.wunschliste.de/kalender.pl\?s=(.*?)\&.*?alt="(.*?)".*?title="Staffel.*?>(.*?)</span>.*?title="Episode.*?>(.*?)</span>.*?target="_new">(.*?)</a>', data, re.S)
		if raw:
			for regional,paytv,neu,prime,time,url,serien_name,serien_id,sender,staffel,episode,title in raw:
				aufnahme = False
				serieAdded = False
				start_h = time[:+2]
				start_m = time[+3:]
				#start_time = getUnixTime(start_h, start_m)
				start_time = getUnixTimeWithDayOffset(start_h, start_m, self.page)
				
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)
				title = iso8859_Decode(title)

				if self.checkTimer(serien_name, staffel, episode, title, start_time, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')):
					aufnahme = True
				else:
					##############################
					#
					# try to get eventID (eit) from epgCache
					#
					if config.plugins.serienRec.eventid.value:
						cSener_list = self.checkSender(sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)',''))
						if len(cSener_list) != 0:
							(webChannel, stbChannel, stbRef, status) = cSener_list[0]

						# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
						event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_time)+(int(config.plugins.serienRec.margin_before.value) * 60), -1)], stbRef, serien_name, int(start_time)+(int(config.plugins.serienRec.margin_before.value) * 60))
						#print "event matches %s" % len(event_matches)
						if event_matches and len(event_matches) > 0:
							for event_entry in event_matches:
								print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
								start_time = int(event_entry[3])
								if self.checkTimer(serien_name, staffel, episode, title, start_time, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')):
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
				if config.plugins.serienRec.seriensubdir.value:
					dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
				else:
					dirname = config.plugins.serienRec.savetopath.value
				check_SeasonEpisode = "S%sE%s" % (staffel, episode)

				# check hdd
				bereits_vorhanden = False
				if fileExists(dirname):
					dirs = os.listdir(dirname)
					for dir in dirs:
						if re.search(serien_name+'.*?'+check_SeasonEpisode, dir):
							bereits_vorhanden = True
							break

				title = "S%sE%s - %s" % (staffel, episode, title)
				if self.pNeu == 0:
					self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 1:
					if int(neu) == 1:
						self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 2:
					cSener_list = self.checkSender(sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)',''))
					if len(cSener_list) != 0:
						(webChannel, stbChannel, stbRef, status) = cSener_list[0]
						if int(status) == 1:
							self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))
				elif self.pNeu == 3:
					if re.search('01', episode, re.S):
						self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id))

		print "[Serien Recorder] Es wurden %s Serie(n) gefunden" % len(self.daylist)
		
		if len(self.daylist) != 0:
			if head_datum:
				self['title'].setText("Es wurden für - %s - %s Serie(n) gefunden." % (head_datum[0], len(self.daylist)))
				self['title'].instance.setForegroundColor(parseColor("white"))
			else:
				self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist))
				self['title'].instance.setForegroundColor(parseColor("white"))
			self.chooseMenuList.setList(map(self.buildList, self.daylist))
			self.loading = False
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist))
			self['title'].instance.setForegroundColor(parseColor("white"))
			print "[Serien Recorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
			self.chooseMenuList.setList(map(self.buildList, self.daylist))

	def buildList(self, entry):
		(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id) = entry
		#entry = [(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,bereits_vorhanden,serien_id)]
		
		imageNone = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/black.png"
		imageNeu = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/neu.png"
		imageTimer = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/timer.png"
		imageHDD = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/hdd_24x24.png"
		
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
		
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 7, 30, 22, loadPNG(imageNeu)),
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 30, 30, 22, loadPNG(imageHDDTimer)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
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
				cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb) VALUES (?, ?, 0)", (serien_name, "http://www.wunschliste.de/epg_print.pl?s=%s" % serien_id))
				self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("green"))
			else:
				self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % serien_name)
				self['title'].instance.setForegroundColor(parseColor("red"))
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
			self['title'].instance.setForegroundColor(parseColor("white"))
			self['title'].setText("Loading infos from Web...")
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
			self.popup_list.append(('0', '1', 'Alle Serien (aktuelle internationale Serien)'))
			self.popup_list.append(('1', '1', 'Neue Serien (aktuelle internationale Serien)'))
			self.popup_list.append(('2', '1', 'Nach aktivierten Sendern (aktuelle internationale Serien)'))
			# soaps
			#self.popup_list.append(('0', '2', 'Alle Serien (Soaps)'))
			#self.popup_list.append(('1', '2', 'Neue Serien (Soaps)'))
			#self.popup_list.append(('2', '2', 'Nach aktivierten Sendern (Soaps)'))
			# internationale Serienklassiker
			self.popup_list.append(('0', '3', 'Alle Serien (internationale Serienklassiker)'))
			self.popup_list.append(('1', '3', 'Neue Serien (internationale Serienklassiker)'))
			self.popup_list.append(('2', '3', 'Nach aktivierten Sendern (internationale Serienklassiker)'))
			# E01
			self.popup_list.append(('3', '1', 'Alle Serienstarts'))
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
		cCursor = dbSerRec.cursor()
		sql = "SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=? AND LOWER(webChannel)=?"
		cCursor.execute(sql, (serie.lower(), (int(start_time) - (int(config.plugins.serienRec.margin_before.value) * 60)), webchannel.lower()))
		if cCursor.fetchone():
			cCursor.close()
			return True
		else:
			cCursor.close()
			return False

	def checkSender(self, mSender):
		fSender = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (mSender.lower(),))
		row = cCursor.fetchone()
		if row:
			(webChannel, stbChannel, stbRef, status) = row
			fSender.append((webChannel, stbChannel, stbRef, status))
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
		self.session.open(serienRecMainChannelEdit)
		#self.close()

	def keyYellow(self):
		self.session.open(serienRecMarker)

	def keyBlue(self):
		self.session.open(serienRecTimer)

	def keyCheck(self):
		self.session.open(serienRecLogReader, True)
		
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
		self['title'].instance.setForegroundColor(parseColor("white"))
		self['title'].setText("Loading infos from Web...")
		self.readWebpage()

	def backPage(self):
		if not self.page < 1:
			self.page -= 1
		self.chooseMenuList.setList(map(self.buildList, []))
		self['title'].instance.setForegroundColor(parseColor("white"))
		self['title'].setText("Loading infos from Web...")
		self.readWebpage()

	def keyCancel(self):
		if self.modus == "list":
			self.close()
		elif self.modus == "popup":
			self['popup'].hide()
			self['popup_bg'].hide()
			self['list'].show()
			self.modus = "list"

	def dataError(self, error):
		self['title'].setText("Suche auf 'Wunschliste.de' erfolglos")
		self['title'].instance.setForegroundColor(parseColor("white"))
		print "[Serien Recorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"
		print error

class serienRecMainChannelEdit(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="3" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			<widget name="popup_bg" position="170,130" size="600,480" backgroundColor="#000000" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/popup_bg.png" transparent="1" zPosition="4" />
			<widget name="popup_list" position="180,170" size="580,370" backgroundColor="#00181d20" scrollbarMode="showOnDemand" transparent="1" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="ok" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label("Loading Web-Channel / STB-Channels...")
		self['red'] = Label("Sender An/Aus-Schalten")
		self['ok'] = Label("Sender Auswählen")
		self['green'] = Label("Reset Senderliste")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		
		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList_popup.l.setItemHeight(25)
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()
		self['popup_bg'] = Pixmap()
		self['popup_bg'].hide()
		self.modus = "list"

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
			self.stbChlist = buildSTBchannellist()
			self.onLayoutFinish.append(self.readWebChannels)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def showProposalDB(self):
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showChannels(self):
		self.serienRecChlist = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels")
		for row in cCursor:
			(webSender, servicename, serviceref, status) = row
			self.serienRecChlist.append((webSender, servicename, status))

		if len(self.serienRecChlist) != 0:
			self['title'].setText("Web-Channel / STB-Channels.")
			self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
		else:
			print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."
		cCursor.close()
		
	def readWebChannels(self):
		print "[SerienRecorder] call webpage.."
		self['title'].setText("Read Web-Channels...")
		url = "http://www.wunschliste.de/updates/stationen"
		getPage(url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.createWebChannels).addErrback(self.dataError)
		
	def createWebChannels(self, data):
		print "[SerienRecorder] get webchannels.."
		self['title'].setText("Read Web-Channels...")
		stations = re.findall('<option value=".*?>(.*?)</option>', data, re.S)
		if stations:
			web_chlist = []
			for station in stations:
				if station != 'alle':
					web_chlist.append((station.replace('\xdf','ß').replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','')))

			web_chlist.sort(key=lambda x: x.lower())
			print web_chlist
			self.serienRecChlist = []
			if len(web_chlist) != 0:
				self['title'].setText("Build Channels-List...")
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
								self.serienRecChlist.append((webSender, servicename, "1"))
								found = True
								break
						if not found:
							cCursor.execute(sql, (webSender, "", "", 0))
							self.serienRecChlist.append((webSender, "", "0"))
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
			
		self['title'].setText("Web-Channel / STB-Channels.")

	def buildList(self, entry):
		(webSender, stbSender, status) = entry
		if int(status) == 0:		
			imageStatus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		else:
			imageStatus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, loadPNG(imageStatus)),
			(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender)
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
			self.stbChlist = buildSTBchannellist()
			self.stbChlist.insert(0, ("", ""))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.stbChlist))
		else:
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()

			check = self['list'].getCurrent()
			if check == None:
				print "[Serien Recorder] Channel-List leer (list)."
				return

			check2 = self['popup_list'].getCurrent()
			if check2 == None:
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
			dbSerRec.commit()
			cCursor.close()
			self.showChannels()
				
	def keyRed(self):
		check = self['list'].getCurrent()
		if check == None:
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
					self['title'].setText("Sender '- %s -' wurde deaktiviert." % webSender)
				dbSerRec.commit()
				
			cCursor.close()	
			self['title'].instance.setForegroundColor(parseColor("white"))
			self.showChannels()

	def keyGreen(self):
		self.session.openWithCallback(self.channelReset, MessageBox, _("Sender-Liste zurücksetzen ?"), MessageBox.TYPE_YESNO)
		
	def channelReset(self, answer):
		if answer:
			print "[Serien Recorder] channel-list reset..."

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
			self['popup_bg'].hide()
		else:
			#self.session.open(serienRecMain)
			self.close()
			
	def dataError(self, error):
		print error

class serienRecMarker(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="915,320" size="320,300" transparent="1" alphatest="blend" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="popup_bg" position="170,130" size="600,480" backgroundColor="#000000" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/popup_bg.png" transparent="1" zPosition="4" />
			<widget name="popup_list" position="180,170" size="580,370" backgroundColor="#00181d20" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="ok" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/blue_round.png" position="1060,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="blue" position="1100,656" size="250,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.picload = ePicLoad()

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
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)

		#normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
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
		self['red'] = Label("Entferne Serie(n) Marker")
		self['green'] = Label("Sender auswählen.")
		self['ok'] = Label("Staffel(n) auswählen.")
		self['yellow'] = Label("Sendetermine")
		self['blue'] = Label("Serie Suchen")
		self['cover'] = Pixmap()
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

		self.searchTitle = ""
		self.serien_nameCover = "nix"
		self.loading = True
		self.onLayoutFinish.append(self.readSerienMarker)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

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
			(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode) = row
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
				cStaffel.close()
			
			markerList.append((Serie, Url, str(staffeln).replace("[","").replace("]","").replace("'","").replace('"',""), str(sender).replace("[","").replace("]","").replace("'","").replace('"',"")))
				
		cCursor.close()
		self['title'].setText("Serien Marker - %s Serien vorgemerkt." % len(markerList))
		if len(markerList) != 0:
			#markerList.sort()
			self.chooseMenuList.setList(map(self.buildList, markerList))
			self.loading = False
			self.getCover()

	def buildList(self, entry):
		(serie, url, staffeln, sendern) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 750, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, self.yellow, self.yellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Staffel: %s" % staffeln),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Sender: %s" % sendern)
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
			
			staffeln = ['Manuell','Alle','folgende']
			staffeln.extend(range(config.plugins.serienRec.max_season.value+1))
			mode_list = [0,]*len(staffeln)
			index_list = range(len(staffeln))
			cCursor = dbSerRec.cursor()
			cCursor.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
			row = cCursor.fetchone()
			if row:
				(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, self.AbEpisode) = row
				if AlleStaffelnAb == -2:		# 'Manuell'
					mode_list[0] = 1
				else:	
					if AlleStaffelnAb == 0:		# 'Alle'
						mode_list[1] = 1
					else:
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
								mode_list[staffel + 3] = 1
						elif (AlleStaffelnAb > 0) and (AlleStaffelnAb <= (len(staffeln)-4)):
							cStaffelList = []
							mode_list[AlleStaffelnAb + 3] = 1
							mode_list[2] = 1
							cStaffel = dbSerRec.cursor()
							cStaffel.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (ID, AlleStaffelnAb))
							cStaffelList = cStaffel.fetchall()
							if len(cStaffelList) > 0:
								cStaffelList = zip(*cStaffelList)[0]
							for staffel in cStaffelList:
								mode_list[staffel + 3] = 1
								if (staffel + 1) == AlleStaffelnAb:
									mode_list[AlleStaffelnAb + 3] = 0
									AlleStaffelnAb = staffel
						if self.AbEpisode > 0:
							mode_list[3] = 1
							
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
			imageMode = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		else:
			imageMode = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"

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

			#getSender = getWebSender()
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
					(ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AufnahmezeitVon, AufnahmezeitBis, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode) = row
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
			self.session.open(serienRecSendeTermine, serien_name, serien_url, self.serien_nameCover)

	def callSaveMsg(self, answer):
		if answer:
			self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Added Liste entfernt werden?" % self.selected_serien_name), MessageBox.TYPE_YESNO, default = False)
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
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Serie '- %s -' entfernt." % serien_name)
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
						self.session.openWithCallback(self.callSaveMsg, MessageBox, _("Soll '%s' wirklich entfernt werden?" % self.selected_serien_name), MessageBox.TYPE_YESNO, default = False)
					else:
						self.session.openWithCallback(self.callDelMsg, MessageBox, _("Sollen die Einträge für '%s' auch aus der Added Liste entfernt werden?" % self.selected_serien_name), MessageBox.TYPE_YESNO, default = False)

	def insertStaffelMarker(self):
		print self.select_serie
		AlleStaffelnAb = 999999
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT ID, AbEpisode FROM SerienMarker WHERE LOWER(Serie)=?", (self.select_serie.lower(),))
		row = cCursor.fetchone()
		if row:
			(ID, AbEpisode) = row
			cCursor.execute("DELETE FROM StaffelAuswahl WHERE ID=?", (ID,))
			liste = self.staffel_liste[1:]
			liste = zip(*liste)
			if 1 in liste[1]:
				for row in self.staffel_liste:
					(staffel, mode, index) = row
					if (index == 0) and (mode == 1):		# 'Manuell'
						AlleStaffelnAb = -2
						AbEpisode = 0
						break
					elif (index == 1) and (mode == 1):		# 'Alle'
						AlleStaffelnAb = 0
						AbEpisode = 0
						break
					elif (index == 2) and (mode == 1):		#'folgende'
						liste = self.staffel_liste[4:]
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
					elif (index > 3) and mode == 1:
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
			
		cCursor.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=?, AbEpisode=? WHERE LOWER(Serie)=?", (AlleStaffelnAb, AbEpisode, self.select_serie.lower()))
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
			if (self.staffel_liste[0][1] == 0) and (self.staffel_liste[1][1] == 0) and (self.staffel_liste[3][1] == 1):		# nicht ('Manuell' oder 'Alle') und '00'
				self.session.openWithCallback(self.selectEpisode, VirtualKeyBoard, title = (_("Episode eingeben ab der Timer erstellt werden sollen:")), text = str(self.AbEpisode))
			else:
				self.insertStaffelMarker()
		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.insertSenderMarker()
		else:
			self.close()

	def dataError(self, error):
		print error

class serienRecAddSerie(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="915,320" size="320,300" transparent="1" alphatest="blend" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="3" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="ok" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session, serien_name):
		Screen.__init__(self, session)
		self.session = session
		self.serien_name = serien_name
		self.picload = ePicLoad()

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
		self['red'] = Label("Abbrechen")
		self['green'] = Label("")
		self['ok'] = Label("Hinzufügen")
		self['cover'] = Pixmap()
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)

		self.loading = True

		self.onLayoutFinish.append(self.searchSerie)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def showProposalDB(self):
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def searchSerie(self):
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche nach ' %s '" % self.serien_name)
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
					print name_Serie, year_Serie, id_Serie
					self.serienlist.append((name_Serie, year_Serie, id_Serie))
		else:
			print "[Serien Recorder] keine Sendetermine für ' %s ' gefunden." % self.serien_name

		self.chooseMenuList.setList(map(self.buildList, self.serienlist))
		self['title'].setText("Die Suche für ' %s ' ergab %s Teffer." % (self.serien_name, str(len(self.serienlist))))
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
			cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender) VALUES (?, ?, -2, 1)", (Serie, Url))
			self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % Serie)
			self['title'].instance.setForegroundColor(parseColor("green"))
		else:
			self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % Serie)
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
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="915,320" size="320,300" transparent="1" alphatest="blend" />
			<widget name="termine" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="ok" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session, serien_name, serie_url, serien_cover):
		Screen.__init__(self, session)
		self.session = session
		self.serien_name = serien_name
		self.serie_url = serie_url
		self.serien_cover = serien_cover
		self.picload = ePicLoad()

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

		self['title'] = Label("Loading Web-Channel / STB-Channels...")
		self['red'] = Label("")
		self['green'] = Label("")
		self['yellow'] = Label("")
		self['ok'] = Label("Auswahl")
		self['cover'] = Pixmap()
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)

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
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def searchSerie(self):
		if not self.serien_cover == "nix":
			self.showCover(self.serien_cover)
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche ' %s '" % self.serien_name)
		print self.serie_url
		getPage(self.serie_url, headers={'Content-Type':'application/x-www-form-urlencoded'}).addCallback(self.resultsTermine, self.serien_name).addErrback(self.dataError)

	def resultsTermine(self, data, serien_name):
		self.sendetermine_list = []
		raw = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)x(.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
		#('RTL Crime', '09.02', '22.35', '23.20', '6', '20', 'Pinocchios letztes Abenteuer')
		if raw:
			parsingOK = True
			#print "raw"
		else:
			raw2 = re.findall('<tr><td>(.*?)</td><td><span class="wochentag">.*?</span><span class="datum">(.*?).</span></td><td><span class="startzeit">(.*?).Uhr</span></td><td>(.*?).Uhr</td><td>\((.*?)\).<span class="titel">(.*?)</span></td></tr>', data)
			if raw2:
				raw = []
				for each in raw2:
					print each
					each = list(each)
					each.insert(4, "0")
					raw.append(each)
				parsingOK = True
				#print "raw2"

		if parsingOK:
			for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
				# umlaute umwandeln
				serien_name = iso8859_Decode(serien_name)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				sender = iso8859_Decode(sender)
				title = iso8859_Decode(title)

				if self.FilterEnabled:
					# filter sender
					cSender_list = self.checkSender(sender)
					if len(cSender_list) == 0:
						webChannel = sender
						stbChannel = ""
					else:
						(webChannel, stbChannel, stbRef, status) = cSender_list[0]

					if stbChannel == "":
						print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel)
						continue
						
					if int(status) == 0:
						print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel)
						continue
					
				self.sendetermine_list.append([serien_name, sender, datum, startzeit, endzeit, str(staffel).zfill(2), str(episode).zfill(2), title, "0"])

			self['red'].setText("Abbrechen")
			self['green'].setText("Timer erstellen")
			if self.FilterEnabled:
				self['yellow'].setText("Filter ausschalten")
				txt = "gefiltert"
			else:
				self['yellow'].setText("Filter einschalten")
				txt = "alle"

			self.chooseMenuList2.setList(map(self.buildList_termine, self.sendetermine_list))
			self.loading = False
			self['title'].setText("%s Sendetermine für ' %s ' gefunden. (%s)" % (str(len(self.sendetermine_list)), self.serien_name, txt))

	def buildList_termine(self, entry):
		#(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry
		(serien_name, sender, datum, start, end, staffel, episode, title, status) = entry

		check_SeasonEpisode = "S%sE%s" % (staffel, episode)
		if config.plugins.serienRec.seriensubdir.value:
			dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
		else:
			dirname = config.plugins.serienRec.savetopath.value
		
		imageMinus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		imagePlus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"
		imageNone = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/black.png"
		imageHDD = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/hdd.png"
		imageTimer = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/timerlist.png"
		imageAdded = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/added.png"
		#imageAdded = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/found.png"

		#check 1 (hdd)
		bereits_vorhanden = False
		rightImage = imageNone
		if fileExists(dirname):
			dirs = os.listdir(dirname)
			for dir in dirs:
				if re.search(serien_name+'.*?'+check_SeasonEpisode, dir):
					bereits_vorhanden = True
					rightImage = imageHDD
					break

		if not bereits_vorhanden:
			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = start.split('.')

			# check 2 (im timer file)
			start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)
			start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
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
			writeLog("\n---------' Starte AutoCheckTimer um %s - (manuell) '-------------------------------------------------------------------------------" % self.uhrzeit, True)
			#writeLog("[Serien Recorder] LOG READER: '1/1'")
			for serien_name, sender, datum, startzeit, endzeit, staffel, episode, title, status in self.sendetermine_list:
				if int(status) == 1:
					# setze label string
					label_serie = "%s - S%sE%s - %s" % (serien_name, staffel, episode, title)
					self.tags = None
					self.justplay = False
					
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
					start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
					end_unixtime = int(end_unixtime) + (int(config.plugins.serienRec.margin_after.value) * 60)

					# erstellt das serien verzeichnis
					mkdir = False
					if config.plugins.serienRec.seriensubdir.value:
						dirname = "%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)
						if not fileExists("%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name)):
							print "[Serien Recorder] erstelle Subdir %s" % config.plugins.serienRec.savetopath.value+serien_name+"/"
							writeLog("[Serien Recorder] erstelle Subdir: ' %s%s%s '" % (config.plugins.serienRec.savetopath.value, serien_name, "/"))
							os.makedirs("%s%s/" % (config.plugins.serienRec.savetopath.value, serien_name))
							mkdir = True
					else:
						dirname = config.plugins.serienRec.savetopath.value

					# überprüft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
					check_SeasonEpisode = "S%sE%s" % (staffel, episode)
					bereits_vorhanden = False

					#check 1 (hdd)
					if fileExists(dirname):
						dirs = os.listdir(dirname)
						for dir in dirs:
							if re.search(serien_name+'.*?'+check_SeasonEpisode, dir):
								bereits_vorhanden = True
								break

					# check 2 (im added file)
					#if checkAlreadyAdded(serien_name, staffel, episode):
					#	bereits_vorhanden = True

					if not bereits_vorhanden:
						# check sender
						cSener_list = self.checkSender(sender)
						if len(cSener_list) == 0:
							webChannel = sender
							stbChannel = ""
						else:
							(webChannel, stbChannel, stbRef, status) = cSener_list[0]

						if stbChannel == "":
							#print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel)
							writeLog("[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel))
						elif int(status) == 0:
							#print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel)
							writeLog("[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel))
						else:
							# try to get eventID (eit) from epgCache
							eit = 0
							if config.plugins.serienRec.eventid.value:
								# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
								event_matches = getEPGevent(['RITBDSE',(stbRef, 0, int(start_unixtime)+(int(config.plugins.serienRec.margin_before.value) * 60), -1)], stbRef, serien_name, int(start_unixtime)+(int(config.plugins.serienRec.margin_before.value) * 60))
								#print "event matches %s" % len(event_matches)
								if event_matches and len(event_matches) > 0:
									for event_entry in event_matches:
										print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
										eit = int(event_entry[1])
										start_unixtime = int(event_entry[3]) - (int(config.plugins.serienRec.margin_before.value) * 60)
										break

							# versuche timer anzulegen
							result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, "S%sE%s - %s" % (staffel, episode, title), 0, self.justplay, 3, dirname, self.tags, 0, None, eit, recordfile=".ts")
							if result["result"]:
								self.countTimer += 1
								self.addRecTimer(serien_name, staffel, episode, title, str(start_unixtime), stbRef, webChannel, eit)
							else:
								print "[Serien Recorder] Attention !!! -> %s" % result["message"]
								konflikt = result["message"]
								writeLog("[Serien Recorder] Attention -> %s" % str(konflikt))
					else:
						writeLog("[Serien Recorder] Serie ' %s ' -> Staffel/Episode bereits vorhanden ' %s '" % (serien_name, check_SeasonEpisode))

			writeLog("[Serien Recorder] Es wurde(n) %s Timer erstellt." % str(self.countTimer), True)
			print "[Serien Recorder] Es wurde(n) %s Timer erstellt." % str(self.countTimer)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			print "---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------"
			self.session.open(serienRecLogReader, False)
		
		else:
			self['title'].setText("Keine Sendetermine ausgewählt.")
			print "[Serien Recorder] keine Sendetermine ausgewählt."

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
		cCursor.execute("SELECT WebChannel, STBChannel, ServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (mSender.lower(),))
		row = cCursor.fetchone()
		if row:
			(webChannel, stbChannel, stbRef, status) = row
			fSender.append((webChannel, stbChannel, stbRef, status))
		cCursor.close()
		return fSender

	def addRecTimer(self, serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit):
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND StartZeitstempel=?", (serien_name.lower(), start_time))
		row = cCursor.fetchone()
		if row:
			print "[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLog("[Serien Recorder] Timer bereits vorhanden: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		else:
			cCursor.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (serien_name, staffel, episode, title, start_time, stbRef, webChannel, eit))
			dbSerRec.commit()
			print "[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title)
			writeLog("[Serien Recorder] Timer angelegt: %s S%sE%s - %s" % (serien_name, str(staffel).zfill(2), str(episode).zfill(2), title))
		cCursor.close()
		
	def keyRed(self):
		self.close()

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
		self['title'].setText("Suche ' %s '" % self.serien_name)
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
		self.close()

	def dataError(self, error):
		print error

class serienRecTimer(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="250,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/blue_round.png" position="1060,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="blue" position="1100,656" size="250,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.viewChange,
			"yellow": self.keyYellow,
			"blue"  : self.keyBlue,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile,
			"3"		: self.showProposalDB
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label("Entferne Timer")
		self['yellow'] = Label("Zeige auch alte Timer")
		self['blue'] = Label("Entferne alle alten")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		
		if config.plugins.serienRec.recordListView.value == 0:
			self['green'] = Label("Zeige früheste Timer zuerst")
		elif config.plugins.serienRec.recordListView.value == 1:
			self['green'] = Label("Zeige neuste Timer zuerst")

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
		self.session.open(serienRecShowProposal)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def viewChange(self):
		if config.plugins.serienRec.recordListView.value == 0:
			config.plugins.serienRec.recordListView.value = 1
			self['green'].setText("Zeige neuste Timer zuerst")
		elif config.plugins.serienRec.recordListView.value == 1:
			config.plugins.serienRec.recordListView.value = 0
			self['green'].setText("Zeige früheste Timer zuerst")
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
				self['title'].setText("TimerList: %s Timer sind vorhanden." % len(timerList))
			else:
				self['title'].setText("TimerList: %s Aufnahme(n) und %s Timer sind vorhanden." % (deltimer, len(timerList)-deltimer))

		if config.plugins.serienRec.recordListView.value == 0:
			timerList.sort(key=lambda t : t[2])
		elif config.plugins.serienRec.recordListView.value == 1:
			timerList.sort(key=lambda t : t[2])
			timerList.reverse()

		self.chooseMenuList.setList(map(self.buildList, timerList))
		if len(timerList) == 0:
			if showTitle:			
				self['title'].instance.setForegroundColor(parseColor("white"))
				self['title'].setText("Serien Timer - 0 Serien in der Aufnahmeliste.")

	def buildList(self, entry):
		(serie, title, start_time, webChannel, foundIcon, eit) = entry
		WochenTag=["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		xtime = time.strftime(WochenTag[time.localtime(int(start_time)).tm_wday]+", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))

		if int(foundIcon) == 1:
			imageFound = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/found.png"
		else:
			imageFound = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/black.png"
			
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 8, 8, 32, 32, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
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
		
		self.readTimer(False)
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Timer '- %s -' entfernt." % serien_name)

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
					self.session.openWithCallback(self.callDeleteSelectedTimer, MessageBox, _("Soll '%s - %s' wirklich entfernt werden?" % (serien_name, serien_title)), MessageBox.TYPE_YESNO, default = False)				
				else:
					self.removeTimer(serien_name, serien_title, serien_time, serien_channel, serien_eit)
			else:
				print "[Serien Recorder] keinen passenden timer gefunden."
			cCursor.close()
			
	def keyYellow(self):
		if self.filter:
			self['yellow'].setText("Zeige nur neue Timer")
			self.filter = False
		else:
			self['yellow'].setText("Zeige auch alte Timer")
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
			self['title'].setText("Alle alten Timer wurden entfernt.")
		else:
			return

	def keyBlue(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.removeOldTimerFromDB, MessageBox, _("Sollen wirklich alle alten Timer entfernt werden?"), MessageBox.TYPE_YESNO, default = False)				
		else:
			self.removeOldTimerFromDB(True)
			
	def keyCancel(self):
		self.close()

	def dataError(self, error):
		print error

class serienRecSetup(Screen, ConfigListScreen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="config" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"red"	: self.cancel,
			"green"	: self.save,
			"cancel": self.cancel,
			"ok"	: self.ok
		}, -1)

		self['title'] = Label("Serien Recorder - Einstellungen:")
		self['red'] = Label("Abbrechen")
		self['green'] = Label("Speichern")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.createConfigList()
		ConfigListScreen.__init__(self, self.list, session = self.session)

	def createConfigList(self):
		self.list = []
		self.get_media = getConfigListEntry("Speicherort der Aufnahmen:" + "   " + config.plugins.serienRec.savetopath.value, config.plugins.serienRec.fake_entry)
		self.list.append(self.get_media)
		self.list.append(getConfigListEntry("Nur zum Sender zappen:", config.plugins.serienRec.justplay))
		self.list.append(getConfigListEntry("Serien-Verzeichnis anlegen:", config.plugins.serienRec.seriensubdir))
		self.list.append(getConfigListEntry("Zeige Nachricht wenn Suchlauf startet:", config.plugins.serienRec.showNotification))
		#self.list.append(getConfigListEntry("Automatischen Suchlauf stundenweise ausführen:", config.plugins.serienRec.update))
		self.list.append(getConfigListEntry("Intervall für autom. Suchlauf (in Std.) (00 = kein autom. Suchlauf, 24 = nach Uhrzeit):", config.plugins.serienRec.updateInterval)) #3600000
		#self.list.append(getConfigListEntry("Automatischen Suchlauf nach Uhrzeit ausführen:", config.plugins.serienRec.timeUpdate))
		self.list.append(getConfigListEntry("Uhrzeit für automatischen Suchlauf (nur wenn Intervall = 24):", config.plugins.serienRec.deltime))
		self.list.append(getConfigListEntry("Versuche die Eventid vom EPGCACHE zu holen:", config.plugins.serienRec.eventid))
		#self.list.append(getConfigListEntry("Suche nach alternativer Sendezeit bei Konflikten:", config.plugins.serienRec.Alternatetimer))
		self.list.append(getConfigListEntry("Timer für X Tage erstellen:", config.plugins.serienRec.checkfordays))
		self.list.append(getConfigListEntry("Früheste Zeit für Timer (hh:00):", config.plugins.serienRec.fromTime))
		self.list.append(getConfigListEntry("Späteste Zeit für Timer (hh:59):", config.plugins.serienRec.toTime))
		self.list.append(getConfigListEntry("Immer aufnehmen wenn keine Wiederholung gefunden wird:", config.plugins.serienRec.forceRecording))
		self.list.append(getConfigListEntry("Timervorlauf (in Min.):", config.plugins.serienRec.margin_before))
		self.list.append(getConfigListEntry("Timernachlauf (in Min.):", config.plugins.serienRec.margin_after))
		self.list.append(getConfigListEntry("Anzahl der wählbaren Staffeln im Menü SerienMarker:", config.plugins.serienRec.max_season))
		#self.list.append(getConfigListEntry("Entferne alte Timer aus der Record-List:", config.plugins.serienRec.pastTimer))
		self.list.append(getConfigListEntry("Automatisches Plugin-Update:", config.plugins.serienRec.Autoupdate))
		self.list.append(getConfigListEntry("Aus Deep-StandBy aufwecken:", config.plugins.serienRec.wakeUpDSB))
		self.list.append(getConfigListEntry("Nach dem automatischen Suchlauf in Deep-StandBy gehen:", config.plugins.serienRec.afterAutocheck))
		self.list.append(getConfigListEntry("Vor Löschen in SerienMarker und TimerList Benutzer fragen:", config.plugins.serienRec.confirmOnDelete))
		self.list.append(getConfigListEntry("Zeige Nachricht bei Timerkonflikten:", config.plugins.serienRec.showMessageOnConflicts))
		self.list.append(getConfigListEntry("Aktion bei neuer Serie/Staffel:", config.plugins.serienRec.ActionOnNew))
		self.list.append(getConfigListEntry("DEBUG LOG (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log):", config.plugins.serienRec.writeLog))
		self.list.append(getConfigListEntry("DEBUG LOG - Senderliste:", config.plugins.serienRec.writeLogChannels))
		self.list.append(getConfigListEntry("DEBUG LOG - Seriensender:", config.plugins.serienRec.writeLogAllowedSender))
		self.list.append(getConfigListEntry("DEBUG LOG - Episoden:", config.plugins.serienRec.writeLogAllowedEpisodes))
		self.list.append(getConfigListEntry("DEBUG LOG - Added:", config.plugins.serienRec.writeLogAdded))
		self.list.append(getConfigListEntry("DEBUG LOG - Festplatte:", config.plugins.serienRec.writeLogDisk))
		self.list.append(getConfigListEntry("DEBUG LOG - Tageszeit:", config.plugins.serienRec.writeLogTimeRange))
		self.list.append(getConfigListEntry("DEBUG LOG - Zeitbegrenzung:", config.plugins.serienRec.writeLogTimeLimit))
		self.list.append(getConfigListEntry("DEBUG LOG - Timer Debugging:", config.plugins.serienRec.writeLogTimerDebug))
		#self.list.append(getConfigListEntry("Timer für ALLE Wiederholungen erstellen:", config.plugins.serienRec.recordAll))

	def changedEntry(self):
		self.createConfigList()
		self["config"].setList(self.list)

	def ok(self):
		if self["config"].getCurrent() == self.get_media:
			#start_dir = "/media/hdd/movie/"
			start_dir = config.plugins.serienRec.savetopath.value
			self.session.openWithCallback(self.selectedMediaFile, SerienRecFileList, start_dir)

	def selectedMediaFile(self, res):
		if res is not None:
			if self["config"].getCurrent() == self.get_media:
				print res
				config.plugins.serienRec.savetopath.value = res
				config.plugins.serienRec.savetopath.save()
				configfile.save()
				self.changedEntry()

	def save(self):
		#for x in self["config"].list:
		#	x[1].save()
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

		config.plugins.serienRec.savetopath.save()
		config.plugins.serienRec.justplay.save()
		config.plugins.serienRec.seriensubdir.save()
		config.plugins.serienRec.update.save()
		config.plugins.serienRec.updateInterval.save()
		config.plugins.serienRec.checkfordays.save()
		config.plugins.serienRec.margin_before.save()
		config.plugins.serienRec.margin_after.save()
		config.plugins.serienRec.max_season.save()
		config.plugins.serienRec.Autoupdate.save()
		config.plugins.serienRec.fromTime.save()
		config.plugins.serienRec.toTime.save()
		config.plugins.serienRec.timeUpdate.save()
		config.plugins.serienRec.deltime.save()
		#config.plugins.serienRec.pastTimer.save()
		config.plugins.serienRec.wakeUpDSB.save()
		config.plugins.serienRec.afterAutocheck.save()
		config.plugins.serienRec.eventid.save()
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
		#config.plugins.serienRec.recordAll.save()
		config.plugins.serienRec.showMessageOnConflicts.save()
		
		configfile.save()
		self.close(True)

	def cancel(self):
		self.close(False)

class SerienRecFileList(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,10" size="820,55" foregroundColor="red" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="center" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget name="media" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="folderlist" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session, initDir):
		Screen.__init__(self, session)
		
		self["title"] = Label("Aufnahme-Verzeichnis auswählen")
		self["media"] = Label("")
		self["folderlist"] = FileList(initDir, inhibitMounts = False, inhibitDirs = False, showMountpoints = False, showFiles = False)
		self["red"] = Label("Abbrechen")
		self["green"] = Label("Speichern")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)

		self["actions"] = ActionMap(["WizardActions", "DirectionActions", "ColorActions", "EPGSelectActions"],
		{
			"back": self.cancel,
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"ok": self.ok,
			"green": self.green,
			"red": self.cancel
		}, -1)
		
		self.updateFile()

	def cancel(self):
		self.close(None)

	def green(self):
		directory = self["folderlist"].getSelection()[0]
		if (directory.endswith("/")):
			self.fullpath = self["folderlist"].getSelection()[0]
		else:
			self.fullpath = "%s/" % self["folderlist"].getSelection()[0]
	  	self.close(self.fullpath)

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
		self["media"].setText("Auswahl: %s" % currFolder)

class serienRecReadLog(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;24" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"cancel": self.keyCancel
		}, -1)

		self["list"] = ScrollLabel()
		self['title'] = Label("Lese LogFile: (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log)")
		self['red'] = Label("Abbrechen")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
		self.logliste = []

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		
		self.onLayoutFinish.append(self.readLog)

	def readLog(self):
		if not fileExists(self.logFile):
			open(self.logFile, 'w').close()

		logFile_leer = os.path.getsize(self.logFile)
		if not logFile_leer == 0:
			readLog = open(self.logFile, "r")
			self.logliste = []
			for zeile in readLog.readlines():
					self.logliste.append((zeile.replace('[Serien Recorder]','')))
			readLog.close()
			self['title'].setText("LogFile: (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log)")
			self.chooseMenuList.setList(map(self.buildList, self.logliste))

	def buildList(self, entry):
		(zeile) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def keyCancel(self):
		self.close()

class serienRecLogReader(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session, startAuto):
		Screen.__init__(self, session)
		self.session = session
		self.startAuto = startAuto

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
		self['title'] = Label("Suche nach neuen Timern läuft.")
		self['red'] = Label("Abbrechen")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
		self.logliste = []
		self.points = ""

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		
		self.onLayoutFinish.append(self.startCheck)
		self.onClose.append(self.__onClose)

	def startCheck(self):
		if self.startAuto:
			serienRecCheckForRecording(self.session, True)

		# Log Reload Timer
		self.readLogTimer = eTimer()
		self.readLogTimer.callback.append(self.readLog)
		self.readLogTimer.start(2500)
		self.readLog()

	def readLog(self):
		if not fileExists(self.logFile):
			open(self.logFile, 'w').close()

		logFile_leer = os.path.getsize(self.logFile)
		if not logFile_leer == 0:
			readLog2 = open(self.logFile, "r")
			logData = readLog2.read()
			if re.search('AutoCheckTimer Beendet', logData, re.S):
				self.readLogTimer.stop()
				print "[Serien Recorder] update log reader stopped."
				self['title'].setText('Autocheck fertig !')
				readLog = open(self.logFile, "r")
				for zeile in readLog.readlines():
						self.logliste.append((zeile.replace('[Serien Recorder]','')))
				self.chooseMenuList.setList(map(self.buildList, self.logliste))
			else:
				self.points += " ."
				self['title'].setText('Suche nach neuen Timern läuft.%s' % self.points)
					
	def buildList(self, entry):
		(zeile) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 1280, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()
		
	def __onClose(self):
		print "[Serien Recorder] update log reader stopped."
		self.readLogTimer.stop()

	def keyCancel(self):
		self.close()

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
			self.session.openWithCallback(self.startUpdate,MessageBox,_("An update is available for the Serien Recorder Plugin!\nDo you want to download and install it now?"), MessageBox.TYPE_YESNO)
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

		skin = """
		<screen name="Serien Recorder Update" position="0,0" size="1280,720" title="Serien Recorder Update" backgroundColor="#26181d20" flags="wfNoBorder">
		<widget name="mplog" position="287,240" size="720,320" font="Regular;24" valign="top" halign="left" backgroundColor="#00000000" transparent="1" zPosition="1" />
		</screen>"""

		self.skin = skin
		self["mplog"] = ScrollLabel()
		Screen.__init__(self, session)
		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		sl = self["mplog"]
		sl.instance.setZPosition(1)
		self["mplog"].setText("Starting update, please wait...")
		self.startPluginUpdate()

	def startPluginUpdate(self):
		self.container=eConsoleAppContainer()
		self.container.appClosed.append(self.finishedPluginUpdate)
		self.container.stdoutAvail.append(self.mplog)
		#self.container.stderrAvail.append(self.mplog)
		#self.container.dataAvail.append(self.mplog)
		self.container.execute("opkg install --force-overwrite --force-depends %s" % str(self.updateurl))

	def finishedPluginUpdate(self,retval):
		self.session.openWithCallback(self.restartGUI, MessageBox, _("Serien Recorder successfully updated!\nDo you want to restart the Enigma2 GUI now?"), MessageBox.TYPE_YESNO)

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
		#writeLog("[Serien Recorder] Deep-Standby WakeUp: AN")
		print color_print+"[Serien Recorder] Deep-Standby WakeUp: AN" +color_end
		now = time.localtime()
		current_time = int(time.time())
		
		begin = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, config.plugins.serienRec.deltime.value[0], config.plugins.serienRec.deltime.value[1], 0, now.tm_wday, now.tm_yday, now.tm_isdst)))

		# überprüfe ob die aktuelle zeit größer ist als der clock-timer + 1 day.
		if int(current_time) > int(begin):
			#writeLog("[Serien Recorder] WakeUp-Timer + 1 day.")
			print color_print+"[Serien Recorder] WakeUp-Timer + 1 day."+color_end
			begin = begin + 86400
		# 5 min. bevor der Clock-Check anfängt wecken.
		begin = begin - 300

		wakeupUhrzeit = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
		#writeLog("[Serien Recorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit)
		print color_print+"[Serien Recorder] Deep-Standby WakeUp um %s" % wakeupUhrzeit +color_end

		return begin
	else:
		#writeLog("[Serien Recorder] Deep-Standby WakeUp: AUS")
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

def initDB():
	#dbSerRec = sqlite3.connect("/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/SerienRecorder.db")
	#dbSerRec.text_factory = str
	cCursor = dbSerRec.cursor()
	#cCursor.execute('SELECT name FROM sqlite_master WHERE type = "table"')
	#tables = cCursor.fetchall()
	#for table in tables:
	#	if table[0] == "AngelegteTimer":
	#		cCursor.execute("DROP TABLE %s" % table[0])
	#	if table[0] == "SerienMarker":
	#		cCursor.execute("DROP TABLE %s" % table[0])
	#dbSerRec.commit()

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
															Nachlaufzeit INTEGER DEFAULT NULL)''')
															
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
																useAlternativeChannel INTEGER DEFAULT 0,
																AbEpisode INTEGER DEFAULT 0)''')
																
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
																  
	dbSerRec.commit()
	cCursor.close()


	try:
		cCursor = dbSerRec.cursor()
		cCursor.execute('ALTER TABLE SerienMarker ADD AbEpisode INTEGER DEFAULT 0')
		dbSerRec.commit()
		cCursor.close()
	except:
		pass

	
	cTmp = dbTmp.cursor()
	#def doTimer(self, current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode):
	cTmp.execute('''CREATE TABLE IF NOT EXISTS GefundeneFolgen (CurrentTime INTEGER,
	                                                            FutureTime INTEGER,
	                                                            Title TEXT,
	                                                            Staffel INTEGER, 
															    Episode TEXT, 
	                                                            LabelSerie TEXT, 
																StartTime INTEGER,
																EndTime INTEGER,
															    ServiceRef TEXT, 
															    EventID INTEGER,
																DirName TEXT,
																SerieName TEXT,
															    webChannel TEXT, 
															    stbChannel TEXT, 
															    SeasonEpisode TEXT)''')
	dbTmp.commit()
	cTmp.close()

	
def ImportFilesToDB():
	channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
	addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"
	timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
	markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"

	initDB()
	if fileExists(channelFile):
		cCursor = dbSerRec.cursor()
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
		dbSerRec.commit()
		cCursor.close()
		
		readChannel.close()
		shutil.move(channelFile, "%s_old" % channelFile)
		#os.remove(channelFile)
		
	if fileExists(addedFile):
		cCursor = dbSerRec.cursor()
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
		dbSerRec.commit()
		cCursor.close()
		
		readAdded.close()
		shutil.move(addedFile, "%s_old" % addedFile)
		#os.remove(addedFile)
		
	if fileExists(timerFile):
		cCursor = dbSerRec.cursor()
		readTimer = open(timerFile, "r")
		for rawData in readTimer.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, xtitle, start_time, stbRef, webChannel) = data[0]
			data = re.findall('"S(.*?)E(.*?) - (.*?)"', '"%s"' % xtitle, re.S)
			(staffel, episode, title) = data[0]
			cCursor.execute("SELECT * FROM AngelegteTimer WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?", (serie.lower(), staffel, episode))
			if not cCursor.fetchone():
				sql = "INSERT OR IGNORE INTO AngelegteTimer (Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel) VALUES (?, ?, ?, ?, ?, ?, ?)"
				cCursor.execute(sql, (serie, staffel, episode, title, start_time, stbRef, webChannel))
			else:
				sql = "UPDATE OR IGNORE AngelegteTimer SET Titel=?, StartZeitstempel=?, ServiceRef=?, webChannel=? WHERE LOWER(Serie)=? AND Staffel=? AND Episode=?"
				cCursor.execute(sql, (title, start_time, stbRef, webChannel, serie.lower(), staffel, episode))
		dbSerRec.commit()
		cCursor.close()
		
		readTimer.close()
		shutil.move(timerFile, "%s_old" % timerFile)
		#os.remove(timerFile)
		
	if fileExists(markerFile):
		cCursor = dbSerRec.cursor()
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

			cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender) VALUES (?, ?, ?, ?)", (serie, url, AlleStaffelnAb, alleSender))
			ID = cCursor.lastrowid
			if len(staffeln) > 0:
				IDs = [ID,]*len(staffeln)					
				staffel_list = zip(IDs, staffeln)
				cCursor.executemany("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", staffel_list)
			if len(sender) > 0:
				IDs = [ID,]*len(sender)					
				sender_list = zip(IDs, sender)
				cCursor.executemany("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", sender_list)
				
		dbSerRec.commit()
		cCursor.close()
		
		readMarker.close()
		shutil.move(markerFile, "%s_old" % markerFile)
		#os.remove(markerFile)
		
	return True
		
class serienRecModifyAdded(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;24" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_exit.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="cancel" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.save,
			"yellow" : self.keyYellow
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label("Eintrag löschen")
		self['green'] = Label("Speichern")
		self['cancel'] = Label("Abbrechen")
		self['yellow'] = Label("Sortieren")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		
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
		self['title'].setText("Diese Episoden werden nicht mehr aufgenommen !")
		self.addedliste_tmp = self.addedliste[:]
		self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			
	def buildList(self, entry):
		(zeile, Serie, Staffel, Episode) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 20, 00, 1280, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def keyOK(self):
		pass

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
				self['yellow'].setText("Sortieren")
				self.sortedList = False
			else:
				self.addedliste_tmp.sort()
				self['yellow'].setText("unsortierte Liste")
				self.sortedList = True

			self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
		
	def keyCancel(self):
		self.close()


class serienRecShowProposal(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,50" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;24" valign="center" halign="left" />
			<widget name="version" position="850,10" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,50" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="915,120" size="328,186" zPosition="3" backgroundColor="transparent" />
			<widget name="list" position="20,120" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_exit.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="cancel" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/blue_round.png" position="1060,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="blue" position="1100,656" size="250,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyOK,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"yellow": self.keyYellow,
			"blue"	: self.keyBlue
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(25)


		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label("Eintrag löschen")
		self['green'] = Label("Marker übernehmen")
		self['cancel'] = Label("Abbrechen")
		self['yellow'] = Label("Zeige nur neue")
		self['blue'] = Label("Liste leeren")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self.red = 0xf23d21
		self.white = 0xffffff
		
		self.filter = False
		self.proposalList = []
		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"

		self.onLayoutFinish.append(self.readProposal)

	def readProposal(self):
		self.proposalList = []
		cCursor = dbSerRec.cursor()
		cCursor.execute("SELECT Serie, Staffel, Sender, StaffelStart, Url, CreationFlag FROM NeuerStaffelbeginn WHERE CreationFlag=? OR CreationFlag>=1 GROUP BY Serie, Staffel", (self.filter, ))
		for row in cCursor:
			(Serie, Staffel, Sender, Datum, Url, CreationFlag) = row
			Staffel = str(Staffel).zfill(2)
			self.proposalList.append((Serie, Staffel, Sender, Datum, Url, CreationFlag))
		cCursor.close()
		
		self['title'].setText("Neue Serie(n) / Staffel(n):")
		
		self.proposalList.sort(key=lambda x: time.strptime(x[3].split(",")[1].strip(), "%d.%m.%Y"))
		self.chooseMenuList.setList(map(self.buildList, self.proposalList))
			
	def buildList(self, entry):
		(Serie, Staffel, Sender, Datum, Url, CreationFlag) = entry
		
		if CreationFlag == 0:
			imageFound = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/found.png"
		else:
			imageFound = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/black.png"
		
		if CreationFlag == 2:
			setFarbe = self.red
		else:
			setFarbe = self.white
		
		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 8, 0, 32, 32, loadPNG(imageFound)),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 1280, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, _("%s - S%sE01 - %s - %s" % (Serie, Staffel, Datum, Sender)))
			]
				
	def keyRed(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Proposal-DB leer."
			return
		else:
			(Serie, Staffel, Sender, Datum, Url, CreationFlag) = self['list'].getCurrent()[0]
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
			(Serie, Staffel, Sender, Datum, Url, CreationFlag) = self['list'].getCurrent()[0]
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
					cCursor.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender) VALUES (?, ?, ?, ?)", (Serie, Url, AbStaffel, AlleSender))
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
			self.readProposal()
			self['yellow'].setText("Zeige alle")
		else:
			self.filter = False
			self.readProposal()
			self['yellow'].setText("Zeige nur neue")

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

		
