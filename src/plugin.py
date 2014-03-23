#-*- coding: utf-8 -*-
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

try:
	default_before = int(config.recording.margin_before.value)
	default_after = int(config.recording.margin_after.value)
except Exception:
	default_before = 0
	default_after = 0

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
config.plugins.serienRec.Alternatetimer = ConfigYesNo(default = True)
config.plugins.serienRec.Autoupdate = ConfigYesNo(default = True)
config.plugins.serienRec.pastTimer = ConfigYesNo(default = False)
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

# interne
config.plugins.serienRec.version = NoSave(ConfigText(default="023"))
config.plugins.serienRec.showversion = NoSave(ConfigText(default="2.3"))
config.plugins.serienRec.screenmode = ConfigInteger(0, (0,2))
config.plugins.serienRec.screeplaner = ConfigInteger(1, (1,3))
config.plugins.serienRec.recordListView = ConfigInteger(0, (0,1))

def iso8859_Decode(txt):
	#txt = txt.replace('\xe4','ä').replace('\xf6','ö').replace('\xfc','ü').replace('\xdf','ß')
	#txt = txt.replace('\xc4','Ä').replace('\xd6','Ö').replace('\xdc','Ü')
	txt = txt.replace('\xe4','ae').replace('\xf6','oe').replace('\xfc','ue').replace('\xdf','ss')
	txt = txt.replace('\xc4','Ae').replace('\xd6','Oe').replace('\xdc','Ue')
	txt = txt.replace('...','').replace('..','').replace(':','').replace('\xb2','2')
	return txt

def checkTimerAdded(name, seasonEpisode, start_unixtime):
	#"Castle" "S03E20 - Die Pizza-Connection" "1392997800" "1:0:19:EF76:3F9:1:C00000:0:0:0:" "kabel eins"
	addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
	readAddedFile = open(addedFile, "r")
	found = False
	for line in readAddedFile.readlines():
		#data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
		#(serie, se, startTimeUnix, sref, websender) = data[0]
		#serie_label = "%s %s" % (serie, se)
		if re.search(name+'.*?'+seasonEpisode+'.*?'+start_unixtime, line, re.S|re.I):
			found = True
			break

	readAddedFile.close()
	return found

def checkAlreadyAdded(dupeName):
	addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"
	readAddedFile = open(addedFile, "r")
	found = False
	for line in readAddedFile.readlines():
		if dupeName in line:
			found = True
			break

	readAddedFile.close()
	return found

def addAlreadyAdded(dupeName):
	addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"
	if not fileExists(addedFile):
		open(addedFile, 'w').close()

	writeAddedFile = open(addedFile, "a")
	writeAddedFile.write('%s\n' % (dupeName))
	writeAddedFile.close()

def allowedTimeRange(f,t):
	list = ['00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23']
	if int(t) >= int(f):
		new = list[int(f):int(t)+1]
	else:
		new = list[int(f):len(list)] + list[0:int(t)+1]
		
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

def getRealUnixTime(min, std, day, month, year):
	#now = datetime.datetime.now()
	#print now.year, now.month, now.day, std, min
	return datetime.datetime(int(year), int(month), int(day), int(std), int(min)).strftime("%s")

def getkMarker():
	list = []
	markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
	readMarker = open(markerFile, "r")
	for rawData in readMarker.readlines():
		data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
		(serie, url, staffel, sendern) = data[0]
		list.append((serie, url, staffel, sendern))
	readMarker.close()
	return list

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
			if int(int(begin)-600) <= int(starttime) <= int(int(begin)+600):
				#print "MATCHHHHHHH", name
				epgmatches.append((serviceref, eit, name, begin, duration, shortdesc, extdesc))
	return epgmatches

def getWebSender():
	fSender = []
	channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
	readChannel = open(channelFile, "r")
	for rawData in readChannel.readlines():
		data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
		(webChannel, stbChannel, stbRef, status) = data[0]
		fSender.append((webChannel))
	readChannel.close()
	return fSender

def getWebSenderAktiv():
	fSender = []
	channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
	readChannel = open(channelFile, "r")
	for rawData in readChannel.readlines():
		data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
		(webChannel, stbChannel, stbRef, status) = data[0]
		if int(status) == 1:
			fSender.append((webChannel))
	readChannel.close()
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

def checkInt(x):
	try:
		int(x)
		return True
	except:
		return False

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
		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
		self.channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
		self.timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
		self.logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
		self.addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"

		lt = time.localtime()
		self.uhrzeit = time.strftime("%d.%m.%Y - %H:%M:%S", lt)

		if not fileExists(self.markerFile):
			open(self.markerFile, 'w').close()

		if not fileExists(self.channelFile ):
			open(self.channelFile , 'w').close()

		if not fileExists(self.timerFile):
			open(self.timerFile, 'w').close()

		if not fileExists(self.addedFile):
			open(self.addedFile, 'w').close()

		markerFile_leer = os.path.getsize(self.markerFile)
		channelFile_leer = os.path.getsize(self.channelFile)

		if markerFile_leer == 0:
			writeLog("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[Serien Recorder] check: markerFile leer."
			writeLog("[Serien Recorder] check: markerFile leer.", True)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			return

		if channelFile_leer == 0:
			writeLog("\n---------' Starte AutoCheckTimer um %s '---------------------------------------------------------------------------------------" % self.uhrzeit, True)
			print "[Serien Recorder] check: channelFile leer."
			writeLog("[Serien Recorder] check: channelFile leer.", True)
			writeLog("---------' AutoCheckTimer Beendet '---------------------------------------------------------------------------------------", True)
			return

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
			shutil.copy(self.logFile,self.logFile+"_old")
		open(self.logFile, 'w').close()

		if amanuell:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog("\n---------' Starte AutoCheckTimer um %s - Page %s (manuell) '-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page)), True)
		else:
			print "\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page))
			writeLog("\n---------' Starte AutoCheckTimer um %s - Page %s (auto)'-------------------------------------------------------------------------------" % (self.uhrzeit, str(self.page)), True)
			if config.plugins.serienRec.showNotification.value:
				Notifications.AddPopup(_("[Serien Recorder]\nAutomatischer Suchlauf für neue Timer wurde gestartet."), MessageBox.TYPE_INFO, timeout=3)

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
		## hier werden die wunschliste urls eingelesen vom serien marker
		self.urls = getkMarker()
		self.count_url = 0
		self.countTimer = 0
		self.countSerien = self.countMarker()
		ds = defer.DeferredSemaphore(tokens=1)
		downloads = [ds.run(self.download, SerieUrl).addCallback(self.parseWebpage,serienTitle,SerieUrl,SerieStaffel,SerieSender).addErrback(self.dataError) for serienTitle,SerieUrl,SerieStaffel,SerieSender in self.urls]
		finished = defer.DeferredList(downloads).addErrback(self.dataError)

	def download(self, url):
		print "[Serien Recorder] call %s" % url
		return getPage(url, timeout=20, headers={'Content-Type':'application/x-www-form-urlencoded'})

	def parseWebpage(self, data, serien_name, SerieUrl, staffeln, allowedSender):
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
			
		# prepare valid time range
		timeRangeList = allowedTimeRange(config.plugins.serienRec.fromTime.value, config.plugins.serienRec.toTime.value)
		timeRange = {}.fromkeys(timeRangeList, 0)
		
		# prepare postprocessing for forced recordings
		forceRecordings = {}

		# get reference times
		current_time = int(time.time())
		future_time = int(config.plugins.serienRec.checkfordays.value) * 86400
		future_time += int(current_time)

		# loop over all transmissions
		for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
			# umlaute umwandeln
			serien_name = iso8859_Decode(serien_name)
			sender = iso8859_Decode(sender)
			sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
			title = iso8859_Decode(title)

			# replace S1 to S01
			if checkInt(staffel):
				if int(staffel) < 10 and len(staffel) == 1:
					staffel = str("0"+staffel)
			if checkInt(episode):
				if int(episode) < 10 and len(episode) == 1:
					episode = str("0"+episode)

			# setze label string
			label_serie = "%s - S%sE%s - %s" % (serien_name, staffel, episode, title)
			sTitle = "%s - S%sE%s" % (serien_name, staffel, episode)

			# formatiere start/end-zeit
			(day, month) = datum.split('.')
			(start_hour, start_min) = startzeit.split('.')
			(end_hour, end_min) = endzeit.split('.')

			start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)

			if int(start_hour) == 23 and int(end_hour) == 00:
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
			if stbChannel == "Nicht gefunden":
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
			serieAllowed2 = False
			if re.search(sender, str(allowedSender), re.S|re.I):
				serieAllowed2 = True
			elif re.search('Alle', str(allowedSender), re.S|re.I):
				serieAllowed2 = True

			if not serieAllowed2:
				writeLogFilter("allowedSender", "[Serien Recorder] ' %s ' - Sender nicht erlaubt -> %s -> %s" % (label_serie, sender, allowedSender))
				continue
				
			##############################
			#
			# CHECK
			#
			# ueberprueft welche staffel(n) erlaubt sind
			#
			serieAllowed = False
			if re.search(staffel, str(staffeln), re.S|re.I):
				serieAllowed = True
			elif re.search('Alle', str(staffeln), re.S|re.I):
				serieAllowed = True
			elif "folgende" in staffeln:
				staffeln2 = []
				staffeln1 = staffeln.replace("[","").replace("]","").replace("'","").split(",")
				for x in staffeln1:
					if x != "Alle" and x != "folgende":
						staffeln2.append(int(x))
				print staffel, max(staffeln2)
				if len(staffeln2) and int(staffel) >= max(staffeln2):
					serieAllowed = True

			elif re.search('Manuell', str(staffeln), re.S|re.I):
				serieAllowed = False

			if not serieAllowed:
				writeLogFilter("allowedEpisodes", "[Serien Recorder] ' %s ' - Staffel nicht erlaubt -> ' S%sE%s ' -> ' %s '" % (label_serie, staffel, episode, staffeln))
				continue
				

			##############################
			
			# erstellt das serien verzeichnis
			mkdir = False
			if config.plugins.serienRec.seriensubdir.value:
				dirname = config.plugins.serienRec.savetopath.value+serien_name+"/"
				if not fileExists(config.plugins.serienRec.savetopath.value+serien_name+"/"):
					print "[Serien Recorder] erstelle Subdir %s" % config.plugins.serienRec.savetopath.value+serien_name+"/"
					writeLog("[Serien Recorder] erstelle Subdir: ' %s%s%s '" % (config.plugins.serienRec.savetopath.value, serien_name, "/"))
					os.makedirs(config.plugins.serienRec.savetopath.value+serien_name+"/")
					if fileExists("/var/volatile/tmp/serienrecorder/"+serien_name+".png") and not fileExists("/var/volatile/tmp/serienrecorder/"+serien_name+".jpg"):
						#print "vorhanden...:", "/var/volatile/tmp/serienrecorder/"+serien_name+".png"
						shutil.copy("/var/volatile/tmp/serienrecorder/"+serien_name+".png",config.plugins.serienRec.savetopath.value+serien_name+"/"+serien_name+".jpg")
					mkdir = True
				else:
					if fileExists("/var/volatile/tmp/serienrecorder/"+serien_name+".png") and not fileExists("/var/volatile/tmp/serienrecorder/"+serien_name+".jpg"):
						#print "vorhanden...:", "/var/volatile/tmp/serienrecorder/"+serien_name+".png"
						shutil.copy("/var/volatile/tmp/serienrecorder/"+serien_name+".png",config.plugins.serienRec.savetopath.value+serien_name+"/"+serien_name+".jpg")
			else:
				dirname = config.plugins.serienRec.savetopath.value

			##############################
			#
			# CHECK
			#
			# ueberprueft anhand des Seriennamen, Season, Episode ob die serie bereits auf der HDD existiert
			#
			check_SeasonEpisode = "S%sE%s" % (staffel, episode)

			# check im added file
			if checkAlreadyAdded(serien_name+' '+check_SeasonEpisode):
				writeLogFilter("added", "[Serien Recorder] ' %s ' - Staffel/Episode bereits in added vorhanden -> ' %s '" % (label_serie, check_SeasonEpisode))
				continue

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
				continue
				
			##############################
			#
			# try to get eventID (eit) from epgCache
			#
			eit = 0
			if config.plugins.serienRec.eventid.value:
				# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
				event_matches = getEPGevent(['RITBDSE',(stbRef, 0, start_unixtime+config.plugins.serienRec.margin_before.value, -1)], stbRef, serien_name, start_unixtime+config.plugins.serienRec.margin_before.value)
				print "event matches %s" % len(event_matches)
				if event_matches and len(event_matches) > 0:
					for event_entry in event_matches:
						print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
						eit = int(event_entry[1])
						start_unixtime = int(event_entry[3])
						start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
						break

			##############################
			#
			# CHECK
			#
			# Ueberpruefe ob der sendetermin zwischen der fromTime und toTime liegt und finde Wiederholungen auf dem gleichen Sender
			#
			if not start_hour in timeRange:
				writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Zeitspanne %s nicht in %s" % (label_serie, start_hour, timeRangeList))
				# forced recording activated?
				if not config.plugins.serienRec.forceRecording:
					continue
					
				# already saved?
				if serien_name+check_SeasonEpisode+sender in forceRecordings:
					continue
					
				# backup timer data for post processing
				show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
				writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Backup Timer -> %s" % (label_serie, show_start))
				forceRecordings[serien_name+check_SeasonEpisode+sender] = ( title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode )
				continue
				
			# time in time range - remove from forceRecordings
			timer_backup = []
			if serien_name+check_SeasonEpisode+sender in forceRecordings:
				show_start_old = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(forceRecordings[serien_name+check_SeasonEpisode+sender][4])))
				show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
				writeLogFilter("timeRange", "[Serien Recorder] ' %s ' - Wiederholung gefunden -> %s -> entferne Timer Backup -> %s" % (label_serie, show_start, show_start_old))
				timer_backup = forceRecordings.pop(serien_name+check_SeasonEpisode+sender)

			##############################
			#
			# Setze Timer
			#
			if not self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode ):
				if timer_backup.size() != 0:
					show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
					( title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode ) = timer_backup
					show_start_old = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
					writeLog("[Serien Recorder] ' %s ' - Wiederholung konnte nicht programmiert werden -> %s -> Versuche Timer Backup -> %s" % (label_serie, show_start, show_start_old), True)
					self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode )
				
		### end of for loop
		
		# post processing for forced recordings
		for title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode in forceRecordings.itervalues():
			show_start = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(start_unixtime)))
			writeLog("[Serien Recorder] ' %s ' - Keine Wiederholung gefunden! -> %s" % (label_serie, show_start), True)
			# programmiere Timer
			self.doTimer(current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode)
			
		# Statistik
		if int(self.count_url) == int(self.countSerien):
			self.speedEndTime = time.clock()
			speedTime = (self.speedEndTime-self.speedStartTime)
			writeLog("[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countSerien), str(self.countTimer)), True)
			print "[Serien Recorder] %s Serie(n) sind vorgemerkt davon wurde(n) %s Timer erstellt." % (str(self.countSerien), str(self.countTimer))
			writeLog("---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------" % str(speedTime), True)
			print "---------' AutoCheckTimer Beendet ( took: %s sec.)'---------------------------------------------------------------------------------------" % str(speedTime)
			
			
			# in den deep-standby fahren.
			if config.plugins.serienRec.wakeUpDSB.value and config.plugins.serienRec.afterAutocheck.value and not self.manuell:
				print "[Serien Recorder] gehe in Deep-Standby"
				writeLog("[Serien Recorder] gehe in Deep-Standby")
				self.session.open(TryQuitMainloop, 1)

				
	def doTimer(self, current_time, future_time, title, staffel, episode, label_serie, start_unixtime, end_unixtime, stbRef, eit, dirname, serien_name, webChannel, stbChannel, check_SeasonEpisode ):
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
		title = "S%sE%s - %s" % (staffel, episode, title)
		result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, title, 0, self.justplay, 3, dirname, self.tags, 0, None, eit=eit, recordfile=".ts")
		if result["result"]:
			self.countTimer += 1
			# Eintrag in das timer file
			self.addRecTimer(serien_name, title, str(start_unixtime), stbRef, webChannel)
			# Eintrag in das added file
			addAlreadyAdded(serien_name+' '+check_SeasonEpisode)
			writeLog("[Serien Recorder] ' %s ' - Timer wurde angelegt -> %s %s @ %s" % (label_serie, show_start, label_serie, stbChannel), True)
			return True
			
		print "[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, result["message"])
		konflikt = result["message"]
		writeLog("[Serien Recorder] ' %s ' - ACHTUNG! -> %s" % (label_serie, str(konflikt)), True)
		return False
			
			
	def checkMarker(self, mSerie):
		readMarker = open(self.markerFile, "r")
		for rawData in readMarker.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, url, staffel, sender) = data[0]
			if serie.lower() == mSerie.lower():
				readMarker.close()
				return True
		readMarker.close()
		return False

	def checkMarkerStaffel(self, mSerie):
		readMarker = open(self.markerFile, "r")
		infos = []
		for rawData in readMarker.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, url, staffel, sender) = data[0]
			if serie.lower() == mSerie.lower():
				readMarker.close()
				staffel = eval(staffel)
				return staffel
		readMarker.close()

	def countMarker(self):
		count = 0
		readMarker = open(self.markerFile, "r")
		for rawData in readMarker.readlines():
			count += 1
		readMarker.close()
		return count

	def readSenderListe(self):
		fSender = []
		readChannel = open(self.channelFile, "r")
		for rawData in readChannel.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(webChannel, stbChannel, stbRef, status) = data[0]
			fSender.append((webChannel, stbChannel, stbRef, status))
		readChannel.close()
		return fSender
		
	def checkSender(self, mSlist, mSender):
		if mSender.lower() in mSlist:
			(webChannel, stbChannel, stbRef, status) = mSlist[mSender.lower()]
		else:
			webChannel = mSender
			stbChannel = "Nicht gefunden"
			stbRef = "serviceref"
			status = "0"
		return (webChannel, stbChannel, stbRef, status)

	def checkSender2(self, mSender):
		fSender = []
		readChannel = open(self.channelFile, "r")
		for rawData in readChannel.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(webChannel, stbChannel, stbRef, status) = data[0]
			if mSender == webChannel:
				fSender.append((webChannel, stbChannel, stbRef, status))
				break
		readChannel.close()
		return fSender

	def addRecTimer(self, serien_name, title, start_time, stbRef, webChannel):
		found = False
		readTimer = open(self.timerFile, "r")
		for rawData in readTimer.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			if data:
				(serie, tTitle, tStart_time, tRref, twebChannel) = data[0]
				if serie == serien_name and int(tStart_time) == int(start_time):
					found = True
					break
		readTimer.close()

		if not found:
			writeTimer = open(self.timerFile, "a")
			writeTimer.write('"%s" "%s" "%s" "%s" "%s"\n' % (serien_name, title, start_time, stbRef, webChannel))
			writeTimer.close()
			print "[Serien Recorder] Timer angelegt: %s %s" % (serien_name, title)
			writeLogFilter("timerDebug", "[Serien Recorder] Timer angelegt: %s %s" % (serien_name, title))
		else:
			print "[Serien Recorder] Timer bereits vorhanden: %s %s" % (serien_name, title)
			writeLogFilter("timerDebug", "[Serien Recorder] Timer bereits vorhanden: %s %s" % (serien_name, title))

	def dataError(self, error):
		print "[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error
		writeLog("[Serien Recorder] Wunschliste Timeout.. webseite down ?! (%s)" % error, True)

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
	def removeTimerEntry(serien_name, start_time):

		recordHandler = NavigationInstance.instance.RecordTimer
		timers = []
		removed = False
		print "[Serien Recorder] try to temove enigma2 Timer:", serien_name, start_time
		for timer in recordHandler.timer_list:
			if timer and timer.service_ref:
				if str(timer.name) == serien_name and int(timer.begin) == int(start_time):
					#if str(timer.service_ref) == entry_dict['channelref']:
					removed = "removed"
					recordHandler.removeEntry(timer)
					removed = True
		return removed

	@staticmethod	
	def addTimer(session, serviceref, begin, end, name, description, disabled, justplay, afterevent, dirname, tags, repeated, logentries=None, eit=0, recordfile=None):

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
			<widget name="headline" position="50,15" size="820,55" foregroundColor="red" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="center" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="version" position="850,15" size="400,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="right" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="popup_bg" position="170,130" size="600,480" backgroundColor="#000000" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/popup_bg.png" transparent="1" zPosition="4" />
			<widget name="popup" position="180,170" size="580,370" backgroundColor="#00181d20" scrollbarMode="showOnDemand" transparent="1" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="913,330" size="320,315" transparent="1" alphatest="blend" />
			
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
			"1"		: self.modifyAddedFile
		}, -1)

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

		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
		if not fileExists(self.markerFile):
			open(self.markerFile, 'w').close()

		self.channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
		if not fileExists(self.channelFile):
			open(self.channelFile, 'w').close()

		self.timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
		if not fileExists(self.timerFile):
			open(self.timerFile, 'w').close()

		self.addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"
		if not fileExists(self.addedFile):
			open(self.addedFile, 'w').close()

		self['cover'] = Pixmap()
		self['title'] = Label("Loading infos from Web...")
		self['headline'] = Label("")
		self['version'] = Label("Serien Recorder v%s" % config.plugins.serienRec.showversion.value)
		self['red'] = Label("Serientyp auswählen")
		self['green'] = Label("Channels zuweisen")
		self['info'] = Label("Timer suchen")
		self['yellow'] = Label("Serien Marker")
		self['blue'] = Label("Timer-Liste")

		self.onLayoutFinish.append(self.startScreen)

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
				start_time = getUnixTime(start_h, start_m)
				
				# encode utf-8
				serien_name = iso8859_Decode(serien_name)
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				title = iso8859_Decode(title)

				if checkInt(staffel):
					if int(staffel) < 10 and len(staffel) == 1:
						staffel = str("0"+staffel)
				if checkInt(episode):
					if int(episode) < 10 and len(episode) == 1:
						episode = str("0"+episode)
				title = "S%sE%s - %s" % (staffel, episode, title)
				if self.checkTimer(serien_name, title, start_time, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')):
					aufnahme = True
					
				if self.checkMarker(serien_name):
					serieAdded = True

				if self.pNeu == 0:
					self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,serien_id))
				elif self.pNeu == 1:
					if int(neu) == 1:
						self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,serien_id))
				elif self.pNeu == 2:
					cSener_list = self.checkSender(sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)',''))
					if len(cSener_list) != 0:
						(webChannel, stbChannel, stbRef, status) = cSener_list[0]
						if int(status) == 1:
							self.daylist.append((regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme, serieAdded,serien_id))

		print "[Serien Recorder] Es wurden %s Serie(n) gefunden" % len(self.daylist)
		if len(self.daylist) != 0:
			if head_datum:
				self['title'].setText("Es wurden für - %s - %s Serie(n) gefunden." % (head_datum[0], len(self.daylist)))
			else:
				self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist))
			self.chooseMenuList.setList(map(self.buildList, self.daylist))
			self.loading = False
			self.getCover()
		else:
			if int(self.page) < 1 and not int(self.page) == 0:
				self.page -= 1
			self.chooseMenuList.setList(map(self.buildList, self.daylist))
			self['title'].setText("Es wurden für heute %s Serie(n) gefunden." % len(self.daylist))
			print "[Serien Recorder] Wunschliste Serien-Planer -> LISTE IST LEER !!!!"

	def buildList(self, entry):
		(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,serien_id) = entry
		#entry = [(regional,paytv,neu,prime,time,url,serien_name,sender,staffel,episode,title,aufnahme,serieAdded,serien_id)]
		dirNeu = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/neu.png"
		imageNeu = loadPNG(dirNeu)
		dirTimer = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/timer.png"
		imageTimer = loadPNG(dirTimer)
		#folge = "S%sE%s" % (staffel,episode)
		
		if serieAdded:
			setFarbe = self.green
		else:
			setFarbe = self.white

		if int(neu) == 1 and aufnahme:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 5, 30, 17, imageNeu),
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 28, 30, 17, imageTimer),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]
		elif int(neu) == 1 and not aufnahme:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 5, 30, 17, imageNeu),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]
		elif int(neu) == 0 and aufnahme:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 15, 28, 30, 17, imageTimer),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]
		elif int(neu) == 0 and not aufnahme:
			return [entry,
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow)
				]
			#entry.append((eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')))
			#entry.append((eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, time, self.yellow, self.yellow))
			#entry.append((eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name, setFarbe, setFarbe))
			#entry.append((eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow, self.yellow))
			#return entry

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
			serien_id = self['list'].getCurrent()[0][13]

			if not fileExists(self.markerFile):
				open(self.markerFile, 'w').close()

			found = False
			readMarker = open(self.markerFile, "r")
			for rawData in readMarker.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				if data:
					(serie, url, staffel, sender) = data[0]
					if serie.lower() == serien_name.lower():
						found = True
						break
			readMarker.close()

			if not found:
				#if int(serien_neu) == 1:
				#	writeMarker = open(self.markerFile, "a")
				#	writeMarker.write('"%s" "%s" "%s"\n' % (serien_name, "http://www.wunschliste.de"+serien_url, "['Neu']"))
				#	writeMarker.close()
				#else:
				writeMarker = open(self.markerFile, "a")
				writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serien_name, "http://www.wunschliste.de/epg_print.pl?s="+serien_id, "['Alle']", "['Alle']"))
				#writeMarker.write('"%s" "%s" "%s"\n' % (serien_name, "http://www.wunschliste.de"+serien_url, "['Alle']"))
				writeMarker.close()
				self['title'].instance.setForegroundColor(parseColor("green"))
				self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % serien_name)
			else:
				self['title'].instance.setForegroundColor(parseColor("red"))
				self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % serien_name)

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
			self.readWebpage()

	def getCover(self):
		if self.loading:
			return
		
		check = self['list'].getCurrent()
		if check == None:
			return

		url = self['list'].getCurrent()[0][5]
		serien_name = self['list'].getCurrent()[0][6]

		serien_nameCover = "/tmp/serienrecorder/"+serien_name+".png"

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
			#self.popup_list.append(('2', '2', 'Nach ktivierten Sendern (Soaps)'))
			# internationale Serienklassiker
			self.popup_list.append(('0', '3', 'Alle Serien (internationale Serienklassiker)'))
			self.popup_list.append(('1', '3', 'Neue Serien (internationale Serienklassiker)'))
			self.popup_list.append(('2', '3', 'Nach aktivierten Sendern (internationale Serienklassiker)'))
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

	def checkTimer(self, xSerie, xTitle, xStart_time, xWebchannel):
		if not fileExists(self.timerFile):
			open(self.timerFile, 'w').close()

		#print xSerie, xStart_time, xWebchannel
		timerList = []
		timerFile_leer = os.path.getsize(self.timerFile)
		if not timerFile_leer == 0:
			readTimer = open(self.timerFile, "r")
			for rawData in readTimer.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie, title, start_time, sRef, webChannel) = data[0]
				#print serie, title, start_time, sRef, webChannel
				if xSerie.lower() == serie.lower() and int(xStart_time) == int(start_time) and webChannel.lower() == xWebchannel.lower():
					return True
			return False
		else:
			return False

	def checkSender(self, mSender):
		fSender = []
		readChannel = open(self.channelFile, "r")
		for rawData in readChannel.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(webChannel, stbChannel, stbRef, status) = data[0]
			if mSender == webChannel:
				fSender.append((webChannel, stbChannel, stbRef, status))
				readChannel.close()
				return fSender
		readChannel.close()
		return fSender

	def checkMarker(self, mSerie):
		readMarker = open(self.markerFile, "r")
		for rawData in readMarker.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, url, staffel, sender) = data[0]
			if serie.lower() == mSerie.lower():
				return True
		readMarker.close()
		return False

	def keyGreen(self):
		self.session.open(serienRecMainChannelEdit)
	
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
		self.readWebpage()

	def backPage(self):
		if not self.page < 1:
			self.page -= 1
		self.readWebpage()

	def keyCancel(self):
		self.close()

	def dataError(self, error):
		print error

class serienRecMainChannelEdit(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="3" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
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
			"red"	: self.keyBlue,
			"green" : self.keyGreen,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile
		}, -1)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label("Loading Web-Channel / STB-Channels...")
		self['red'] = Label("Sender An/Aus-Schalten")
		self['ok'] = Label("Sender Auswählen")
		self['green'] = Label("Sender-Liste Zurücksetzen")
		
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

		self.channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"

		if fileExists(self.channelFile):
			channelFile_leer = os.path.getsize(self.channelFile)
			if not channelFile_leer == 0:
				self.onLayoutFinish.append(self.showChannels)
			else:
				self.stbChlist = buildSTBchannellist()
				self.onLayoutFinish.append(self.readWebChannels)
		else:
			self.stbChlist = buildSTBchannellist()
			self.onLayoutFinish.append(self.readWebChannels)

	def readLogFile(self):
		self.session.open(serienRecReadLog)

	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def showChannels(self):
		if fileExists(self.channelFile):
			self.serienRecChlist = []
			openChannels = open(self.channelFile, "r")
			for rawData in openChannels.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				if data:
					(webSender, servicename, serviceref, status) = data[0]
					self.serienRecChlist.append((webSender, servicename, status))

			openChannels.close()

			if len(self.serienRecChlist) != 0:
				self['title'].setText("Web-Channel / STB-Channels.")
				self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
			else:
				print "[SerienRecorder] fehler bei der erstellung der serienRecChlist.."
		else:
			print "[SerienRecorder] fehler beim erstellen der showChannels.."

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
					web_chlist.append((station.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','')))

			web_chlist.sort(key=lambda x: x[0][0])
			print web_chlist
			self.serienRecChlist = []
			writeChannels = open(self.channelFile, "w")
			dupecheck = []
			if len(web_chlist) != 0:
				self['title'].setText("Build Channels-List...")
				for webSender in web_chlist:
					#print webSender
					found = False
					for servicename,serviceref in self.stbChlist:
						#print servicename
						if re.search(webSender.lower(), servicename.lower(), re.S) and webSender.lower() not in dupecheck:
							dupecheck.append(webSender.lower())
							#print webSender, servicename
							found = True
							self.serienRecChlist.append((webSender, servicename, "1"))
							writeChannels.write('"%s" "%s" "%s" "%s"\n' % (webSender, servicename, serviceref, "1"))
					if not found:
						self.serienRecChlist.append((webSender, "Nicht gefunden", "0"))
						writeChannels.write('"%s" "%s" "%s" "%s"\n' % (webSender, "Nicht gefunden", "serviceref", "0"))

				writeChannels.close()

			else:
				print "[SerienRecorder] webChannel list leer.."

			if len(self.serienRecChlist) != 0:
				self['title'].setText("Web-Channel / STB-Channels.")
				self.chooseMenuList.setList(map(self.buildList, self.serienRecChlist))
			else:
				print "[SerienRecorder] fehler bei der erstellung der serienRecChlist.."

		else:
			print "[SerienRecorder] get webChannel error.."

	def buildList(self, entry):
		(webSender, stbSender, status) = entry
		minus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		plus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"
		imageMinus = loadPNG(minus)
		imagePlus = loadPNG(plus)
		if int(status) == 0:		
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imageMinus),
				(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
				(eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 350, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imagePlus),
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
			if fileExists(self.channelFile):
				readChannelFile = open(self.channelFile, "r")
				writeChannelFile = open(self.channelFile+".tmp", "w")
				for rawData in readChannelFile.readlines():
					data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
					if data:
						(webSender, servicename, serviceref, status) = data[0]
						if webSender == chlistSender:
							writeChannelFile.write('"%s" "%s" "%s" "%s"\n' % (webSender, stbSender, stbRef, "1"))
							print "[SerienRecorder] change to:", webSender, stbSender, stbRef, "1"
						else:
							writeChannelFile.write('"%s" "%s" "%s" "%s"\n' % (webSender, servicename, serviceref, status))
				readChannelFile.close()
				writeChannelFile.close()
				shutil.move(self.channelFile+".tmp", self.channelFile)
				self.showChannels()

	def keyBlue(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Channel-List leer."
			return

		if self.modus == "list":
			chlistSender = self['list'].getCurrent()[0][0]
			sender_status = self['list'].getCurrent()[0][2]
			print sender_status

			if fileExists(self.channelFile):
				readChannelFile = open(self.channelFile, "r")
				writeChannelFile = open(self.channelFile+".tmp", "w")
				for rawData in readChannelFile.readlines():
					data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
					if data:
						(webSender, servicename, serviceref, status) = data[0]
						if webSender == chlistSender:
							if int(status) == 0:
								writeChannelFile.write('"%s" "%s" "%s" "%s"\n' % (webSender, servicename, serviceref, "1"))
								print "[SerienRecorder] change to:", webSender, servicename, serviceref, "1"
								self['title'].instance.setForegroundColor(parseColor("red"))
								self['title'].setText("")
								self['title'].setText("Sender '- %s -' wurde aktiviert." % webSender)
							else:
								writeChannelFile.write('"%s" "%s" "%s" "%s"\n' % (webSender, servicename, serviceref, "0"))
								print "[SerienRecorder] change to:",webSender, servicename, serviceref, "0"
								self['title'].instance.setForegroundColor(parseColor("red"))
								self['title'].setText("")
								self['title'].setText("Sender '- %s -' wurde deaktiviert." % webSender)
						else:
							writeChannelFile.write('"%s" "%s" "%s" "%s"\n' % (webSender, servicename, serviceref, status))
				readChannelFile.close()
				writeChannelFile.close()
				shutil.move(self.channelFile+".tmp", self.channelFile)
				self.showChannels()

	def keyGreen(self):
		self.session.openWithCallback(self.channelReset, MessageBox, _("Sender-Liste zurücksetzen ?"), MessageBox.TYPE_YESNO)
		
	def channelReset(self, answer):
		if answer == True:
			print "[Serien Recorder] channel-list reset..."
			#if fileExists(self.channelFile):
			#	os.remove(self.channelFile)

			self.stbChlist = buildSTBchannellist()
			self.readWebChannels()
			#self.stbChlist = buildSTBchannellist()
			#self.readWebChannels()
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
			self.close()

	def dataError(self, error):
		print error

class serienRecMarker(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="913,330" size="320,315" transparent="1" alphatest="blend" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="3" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			<widget name="popup_bg" position="170,130" size="600,480" backgroundColor="#000000" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/popup_bg.png" transparent="1" zPosition="4" />
			<widget name="popup_list" position="180,170" size="580,370" backgroundColor="#00181d20" scrollbarMode="showOnDemand" transparent="1" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />

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
			"1"		: self.modifyAddedFile
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

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff

		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
		self.searchTitle = ""
		self.serien_nameCover = "nix"
		self.loading = True
		self.onLayoutFinish.append(self.readSerienMarker)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
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

		serien_nameCover = "/tmp/serienrecorder/"+serien_name+".png"

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
		if not fileExists(self.markerFile):
			open(self.markerFile, 'w').close()

		markerList = []
		markerFile_leer = os.path.getsize(self.markerFile)
		if not markerFile_leer == 0:
			readMarker = open(self.markerFile, "r")
			for rawData in readMarker.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie, url, staffeln, sendern) = data[0]
				markerList.append((serie, url, staffeln, sendern))

			self['title'].setText("Serien Marker - %s Serien vorgemerkt." % len(markerList))
			if len(markerList) != 0:
				markerList.sort()
				self.chooseMenuList.setList(map(self.buildList, markerList))
				self.loading = False
				self.getCover()
		else:
			self['title'].setText("Serien Marker - 0 Serien vorgemerkt.")

	def buildList(self, entry):
		(serie, url, staffeln, sendern) = entry
		dirNeu = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/neu.png"
		imageNeu = loadPNG(dirNeu)

		#if "Neu" in staffeln:
		return [entry,
			#(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 4, 30, 17, imageNeu),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 750, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie, self.yellow, self.yellow),
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 350, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Staffel: "+staffeln),
			(eListboxPythonMultiContent.TYPE_TEXT, 400, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "Sender: "+sendern)
			]

		#else:
		#	return [entry,
		#		(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 450, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie),
		#		(eListboxPythonMultiContent.TYPE_TEXT, 520, 0, 300, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffeln),
		#		(eListboxPythonMultiContent.TYPE_TEXT, 520, 0, 300, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sendern)
		#		]

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
			tmp_staffel_liste = []
			print select_staffel, select_mode
			for staffel,mode in self.staffel_liste:
				if checkInt(select_staffel):
					if checkInt(staffel):
						if int(staffel) == int(select_staffel):
							if int(mode) == 1:
								tmp_staffel_liste.append((staffel, "0"))
							else:
								tmp_staffel_liste.append((staffel, "1"))
						else:
							tmp_staffel_liste.append((staffel, mode))
					else:
						tmp_staffel_liste.append((staffel, mode))
				else:
					if str(select_staffel) == str(staffel):
						if int(mode) == 1:
							tmp_staffel_liste.append((staffel, "0"))
						else:
							tmp_staffel_liste.append((staffel, "1"))
					else:
						tmp_staffel_liste.append((staffel, mode))

			self.staffel_liste = tmp_staffel_liste
			self.chooseMenuList_popup.setList(map(self.buildList2, self.staffel_liste))
		elif self.modus == "popup_list2":
			self.select_serie = self['list'].getCurrent()[0][0]
			select_sender = self['popup_list'].getCurrent()[0][0]
			select_mode = self['popup_list'].getCurrent()[0][1]
			tmp_sender_liste = []
			print select_sender, select_mode
			for sender,mode in self.sender_liste:
				#if checkInt(select_sender):
					#if checkInt(staffel):
				if sender.lower() == select_sender.lower():
					if int(mode) == 1:
						tmp_sender_liste.append((sender, "0"))
					else:
						tmp_sender_liste.append((sender, "1"))
				else:
					tmp_sender_liste.append((sender, mode))

			self.sender_liste = tmp_sender_liste
			self.chooseMenuList_popup.setList(map(self.buildList2, self.sender_liste))
			print "selected sender:"
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
			serien_staffeln = self['list'].getCurrent()[0][2]
			print serien_staffeln
			self.staffel_liste = []
			staffeln = ['Manuell','Alle','folgende','00','01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30']
			for staffel in staffeln:
				if staffel in serien_staffeln:
					self.staffel_liste.append((staffel, "1"))
				else:
					self.staffel_liste.append((staffel, "0"))
			self.chooseMenuList_popup.setList(map(self.buildList2, self.staffel_liste))

	def buildList2(self, entry):
		(staffel, mode) = entry
		minus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		plus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"
		imageMinus = loadPNG(minus)
		imagePlus = loadPNG(plus)
		if int(mode) == 0:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 4, 30, 17, imageMinus),
				(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 500, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffel)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 4, 30, 17, imagePlus),
				(eListboxPythonMultiContent.TYPE_TEXT, 65, 0, 500, 25, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, staffel)
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
				self.sender_liste = []
				self.serie_select = self['list'].getCurrent()[0][0]
				self.serie_sender = self['list'].getCurrent()[0][3]

				for sender in getSender:
					if sender in self.serie_sender:
						self.sender_liste.append((sender, "1"))
					else:
						self.sender_liste.append((sender, "0"))
				
				# bisschen magic damit 'Alle' oben in der liste auftaucht..
				self.sender_liste.sort()
				self.sender_liste.reverse()
				if "Alle" in self.serie_sender:
					self.sender_liste.append(("Alle", "1"))
				else:
					self.sender_liste.append(("Alle", "0"))
				self.sender_liste.reverse()

				self.chooseMenuList_popup.setList(map(self.buildList2, self.sender_liste))

	def keyYellow(self):
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				return

			serien_name = self['list'].getCurrent()[0][0]
			serien_url = self['list'].getCurrent()[0][1]
			serien_staffeln = self['list'].getCurrent()[0][2]

			print "teestt"
			#serien_url = getUrl(serien_url.replace('epg_print.pl?s=',''))
			print serien_url
			self.session.open(serienRecSendeTermine, serien_name, serien_url, serien_staffeln, self.serien_nameCover)

	def keyRed(self):
		if self.modus == "list":
			check = self['list'].getCurrent()
			if check == None:
				print "[Serien Recorder] Serien Marker leer."
				return
			else:
				serien_name = self['list'].getCurrent()[0][0]
				found = False
				markerFile_leer = os.path.getsize(self.markerFile)
				if not markerFile_leer == 0:
					readMarker = open(self.markerFile, "r")
					for rawData in readMarker.readlines():
						data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
						(serie1, url1, staffel1, sendern1) = data[0]
						print serie1, serien_name, staffel1, sendern1, url1
						if serien_name.lower() == serie1.lower():
							found = True
							print "gefunden."
							break
				if found:
					markerList = []
					markerFile_leer = os.path.getsize(self.markerFile)
					if not markerFile_leer == 0:
						readMarker = open(self.markerFile, "r")
						writeMarker = open(self.markerFile+".tmp", "w")
						for rawData in readMarker.readlines():
							data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
							(serie2, url2, staffel2, sendern2) = data[0]
							if not serien_name.lower() == serie2.lower():
								markerList.append((serie2, url2, staffel2, sendern2))
								writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serie2, url2, staffel2, sendern2))

						readMarker.close()
						writeMarker.close()
						markerList.sort()
						self.chooseMenuList.setList(map(self.buildList, markerList))
						shutil.move(self.markerFile+".tmp", self.markerFile)
						self['title'].instance.setForegroundColor(parseColor("red"))
						self['title'].setText("Serie '- %s -' entfernt." % serien_name)

	def insertStaffelMarker(self):
		print self.select_serie
		markerList = []
		markerFile_leer = os.path.getsize(self.markerFile)
		if not markerFile_leer == 0:
			readMarker = open(self.markerFile, "r")
			writeMarker = open(self.markerFile+".tmp", "w")
			for rawData in readMarker.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie2, url2, staffel2, sendern2) = data[0]
				if not self.select_serie.lower() == serie2.lower():
					markerList.append((serie2, url2, staffel2, sendern2))
					writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serie2, url2, staffel2, sendern2))
				else:
					markerList.append((serie2, url2, self.return_staffe_list, sendern2))
					writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serie2, url2, self.return_staffe_list, sendern2))

			readMarker.close()
			writeMarker.close()
			#if len(markerList) != 0:
			#	self.chooseMenuList.setList(map(self.buildList, markerList))
			shutil.move(self.markerFile+".tmp", self.markerFile)
			self.readSerienMarker()

	def insertSenderMarker(self):
		print self.serie_select
		markerList = []
		markerFile_leer = os.path.getsize(self.markerFile)
		if not markerFile_leer == 0:
			readMarker = open(self.markerFile, "r")
			writeMarker = open(self.markerFile+".tmp", "w")
			for rawData in readMarker.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie2, url2, staffel2, sendern2) = data[0]
				if not self.serie_select.lower() == serie2.lower():
					markerList.append((serie2, url2, staffel2, sendern2))
					writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serie2, url2, staffel2, sendern2))
				else:
					markerList.append((serie2, url2, staffel2, self.return_sender_list))
					writeMarker.write('"%s" "%s" "%s" "%s"\n' % (serie2, url2, staffel2, self.return_sender_list))

			readMarker.close()
			writeMarker.close()
			#if len(markerList) != 0:
			#	self.chooseMenuList.setList(map(self.buildList, markerList))
			shutil.move(self.markerFile+".tmp", self.markerFile)
			self.readSerienMarker()

	def keyBlue(self):
		if self.modus == "list":
			self.session.openWithCallback(self.wSearch, VirtualKeyBoard, title = (_("Serien Title eingeben:")), text = self.searchTitle)

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
#			serien_nameCover = "/tmp/serienrecorder/"+serien_name+".png"
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

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			self.return_staffe_list = []
			for staffel,mode in self.staffel_liste:
				if int(mode) == 1:
					self.return_staffe_list.append((staffel))

			if len(self.return_staffe_list) == 0:
				self.return_staffe_list.append("Alle")
			elif len(self.return_staffe_list) == 1 and 'folgende' in self.return_staffe_list:
				self.return_staffe_list.append(('01'))
			elif len(self.return_staffe_list) == 2 and 'folgende' in self.return_staffe_list and 'Alle' in self.return_staffe_list:
				self.return_staffe_list.remove('folgende')
			self.insertStaffelMarker()

		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
			print "ok"
			self.return_sender_list = []
			for sender,mode in self.sender_liste:
				if int(mode) == 1:
					self.return_sender_list.append((sender))

			if len(self.return_sender_list) == 0:
				self.return_sender_list.append(("Alle"))
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
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="913,330" size="320,315" transparent="1" alphatest="blend" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="3" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
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
			"1"		: self.modifyAddedFile
		}, -1)

		# search
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 23))
		self.chooseMenuList.l.setItemHeight(25)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label("Exit")
		self['green'] = Label("")
		self['ok'] = Label("Hinzufügen")
		self['cover'] = Pixmap()

		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
		self.loading = True

		self.onLayoutFinish.append(self.searchSerie)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
	def modifyAddedFile(self):
		self.session.open(serienRecModifyAdded)

	def searchSerie(self):
		print "[SerienRecorder] suche ' %s '" % self.serien_name
		self['title'].setText("Suche nach ' %s '" % self.serien_name)
		url = "http://www.wunschliste.de/ajax/search_dropdown.pl?"+urlencode({'q': self.serien_name})
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

		xSerie = self['list'].getCurrent()[0][0]
		xYear = self['list'].getCurrent()[0][1]
		xId = self['list'].getCurrent()[0][2]
		print xSerie, xYear, xId

		if not fileExists(self.markerFile):
			open(self.markerFile, 'w').close()

		found = False
		readMarker = open(self.markerFile, "r")
		for rawData in readMarker.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			if data:
				(serie, url, staffel, sender) = data[0]
				if serie.lower() == xSerie.lower():
					found = True
					break
		readMarker.close()

		if not found:
			link = 'http://www.wunschliste.de/epg_print.pl?s='+str(xId)
			writeMarker = open(self.markerFile, "a")
			writeMarker.write('"%s" "%s" "%s" "%s"\n' % (xSerie, link, "['Manuell']", "['Alle']"))
			writeMarker.close()
			self['title'].setText("Serie '- %s -' zum Serien Marker hinzugefügt." % xSerie)
			self['title'].instance.setForegroundColor(parseColor("green"))
		else:
			self['title'].setText("Serie '- %s -' existiert bereits im Serien Marker." % xSerie)
			self['title'].instance.setForegroundColor(parseColor("red"))

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
		serien_nameCover = "/tmp/serienrecorder/"+serien_name+".png"

		serien_nameCover = "/tmp/serienrecorder/"+serien_name+".png"
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
		self.close()

	def dataError(self, error):
		print error

class serienRecSendeTermine(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="cover" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/no_cover.png" position="913,330" size="320,315" transparent="1" alphatest="blend" />
			<widget name="termine" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="560,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="ok" position="600,656" size="220,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />

			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/yellow_round.png" position="820,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="yellow" position="860,656" size="200,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session, serien_name, serie_url, serie_staffeln, serien_cover):
		Screen.__init__(self, session)
		self.session = session
		self.serien_name = serien_name
		self.serie_url = serie_url
		self.serie_staffeln = serie_staffeln
		self.serien_cover = serien_cover
		self.picload = ePicLoad()

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.keyGreen,
			"yellow": self.keyYellow,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile
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

		self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
		self.channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
		self.timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
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
			print "raw"
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
				print "raw2"

		if parsingOK:
			for sender,datum,startzeit,endzeit,staffel,episode,title in raw:
				# umlaute umwandeln
				serien_name = iso8859_Decode(serien_name)
				sender = iso8859_Decode(sender)
				sender = sender.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')
				title = iso8859_Decode(title)

				if self.FilterEnabled:
					# filter sender
					cSender_list = self.checkSender(sender)
					if len(cSender_list) == 0:
						webChannel = sender
						stbChannel = "Nicht gefunden"
					else:
						(webChannel, stbChannel, stbRef, status) = cSender_list[0]

					if stbChannel == "Nicht gefunden":
						print "[Serien Recorder] ' %s ' - No STB-Channel found -> ' %s '" % (serien_name, webChannel)
						continue
						
					if int(status) == 0:
						print "[Serien Recorder] ' %s ' - STB-Channel deaktiviert -> ' %s '" % (serien_name, webChannel)
						continue
					
				# replace S1 to S01
				if checkInt(staffel):
					if int(staffel) < 10 and len(staffel) == 1:
						staffel = str("0"+staffel)
				if checkInt(episode):
					if int(episode) < 10 and len(episode) == 1:
						episode = str("0"+episode)

				self.sendetermine_list.append((serien_name, sender, datum, startzeit, endzeit, staffel, episode, title, "0"))

			self['red'].setText("Verwerfen")
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
		bereits_vorhanden = 0
		dirname = config.plugins.serienRec.savetopath.value
		
		isTimer = False

		minus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/minus.png"
		imageMinus = loadPNG(minus)
		
		plus = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/plus.png"
		imagePlus = loadPNG(plus)
		
		hdd = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/hdd.png"
		imageHDD = loadPNG(hdd)
		
		itimer = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/timerlist.png"
		imageTimer = loadPNG(itimer)

		iadded = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/added.png"
		imageAdded = loadPNG(iadded)

		#check 1 (hdd)
		if fileExists(dirname):
			dirs = os.listdir(dirname)
			for dir in dirs:
				if re.search(serien_name+'.*?'+check_SeasonEpisode, dir):
					bereits_vorhanden = 1
					break

		# formatiere start/end-zeit
		(day, month) = datum.split('.')
		(start_hour, start_min) = start.split('.')

		# check 2 (im timer file)
		start_unixtime = getUnixTimeAll(start_min, start_hour, day, month)
		if checkTimerAdded(serien_name, check_SeasonEpisode, start_unixtime):
			isTimer = True
			bereits_vorhanden = 2

		# check 2 (im added file)
		if checkAlreadyAdded(serien_name+' '+check_SeasonEpisode) and not isTimer:
			print "3"
			bereits_vorhanden = 3

		if int(status) == 0:
			if bereits_vorhanden == 0:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imageMinus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow)
					]
			elif bereits_vorhanden == 1:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imageMinus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 450, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageHDD)
					]
			elif bereits_vorhanden == 2:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imageMinus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageTimer)
					]
			elif bereits_vorhanden == 3:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imageMinus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageAdded)
					]
		else:
			if bereits_vorhanden == 0:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imagePlus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow)
					]
			elif bereits_vorhanden == 1:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imagePlus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageHDD)
					]
			elif bereits_vorhanden == 2:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imagePlus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageTimer)
					]
			elif bereits_vorhanden == 3:
				return [entry,
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 20, 5, 16, 16, imagePlus),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, sender),
					(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 150, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, datum+" "+start, self.yellow),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serien_name),
					(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, "S"+staffel+"E"+episode+" - "+title, self.yellow),
					(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 750, 1, 48, 48, imageAdded)
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

					if int(start_hour) == 23 and int(end_hour) == 00:
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
						dirname = config.plugins.serienRec.savetopath.value+serien_name+"/"
						if not fileExists(config.plugins.serienRec.savetopath.value+serien_name+"/"):
							print "[Serien Recorder] erstelle Subdir %s" % config.plugins.serienRec.savetopath.value+serien_name+"/"
							writeLog("[Serien Recorder] erstelle Subdir: ' %s%s%s '" % (config.plugins.serienRec.savetopath.value, serien_name, "/"))
							os.makedirs(config.plugins.serienRec.savetopath.value+serien_name+"/")
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
					#if checkAlreadyAdded(serien_name+' '+check_SeasonEpisode):
					#	bereits_vorhanden = True

					if not bereits_vorhanden:
						# check sender
						cSener_list = self.checkSender(sender)
						if len(cSener_list) == 0:
							webChannel = sender
							stbChannel = "Nicht gefunden"
						else:
							(webChannel, stbChannel, stbRef, status) = cSener_list[0]

						if stbChannel == "Nicht gefunden":
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
								event_matches = getEPGevent(['RITBDSE',(stbRef, 0, start_unixtime+config.plugins.serienRec.margin_before.value, -1)], stbRef, serien_name, start_unixtime+config.plugins.serienRec.margin_before.value)
								print "event matches %s" % len(event_matches)
								if event_matches and len(event_matches) > 0:
									for event_entry in event_matches:
										print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
										eit = int(event_entry[1])
										start_unixtime = int(event_entry[3])
										start_unixtime = int(start_unixtime) - (int(config.plugins.serienRec.margin_before.value) * 60)
										break

							# setze strings für addtimer
							title = "S%sE%s - %s" % (staffel, episode, title)
							# versuche timer anzulegen
							result = serienRecAddTimer.addTimer(self.session, stbRef, str(start_unixtime), str(end_unixtime), label_serie, title, 0, self.justplay, 3, dirname, self.tags, 0, None, eit, recordfile=".ts")
							if result["result"]:
								self.countTimer += 1
								self.addRecTimer(serien_name, title, str(start_unixtime), stbRef, webChannel)
								addAlreadyAdded(serien_name+' '+check_SeasonEpisode)
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

		print serie, sender, datum, start, staffel, episode, title
		print sindex
		print self.changeIndex(sindex)

	def changeIndex(self, idx):
		count = 0
		self.sendetermine_list_tmp = []
		if len(self.sendetermine_list) != 0:
			for (serien_name, sender, datum, start, end, staffel, episode, title, status) in self.sendetermine_list:
				if int(count) == int(idx):
					if int(status) == 1:
						count += 1
						self.sendetermine_list_tmp.append((serien_name, sender, datum, start, end, staffel, episode, title, "0"))
					else:
						count += 1
						self.sendetermine_list_tmp.append((serien_name, sender, datum, start, end, staffel, episode, title, "1"))
				else:
					count += 1
					self.sendetermine_list_tmp.append((serien_name, sender, datum, start, end, staffel, episode, title, status))

			self.sendetermine_list = self.sendetermine_list_tmp
			self.chooseMenuList2.setList(map(self.buildList_termine, self.sendetermine_list))

	def checkMarkerStaffel(self, mSerie):
		readMarker = open(self.markerFile, "r")
		for rawData in readMarker.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(serie, url, staffel, sender) = data[0]
			if serie.lower() == mSerie.lower():
				readMarker.close()
				staffel = eval(staffel)
				return staffel
		readMarker.close()

	def checkSender(self, mSender):
		fSender = []
		readChannel = open(self.channelFile, "r")
		for rawData in readChannel.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			(webChannel, stbChannel, stbRef, status) = data[0]
			if mSender == webChannel:
				fSender.append((webChannel, stbChannel, stbRef, status))
				break
		readChannel.close()
		return fSender

	def addRecTimer(self, serien_name, title, start_time, stbRef, webChannel):
		found = False
		readTimer = open(self.timerFile, "r")
		for rawData in readTimer.readlines():
			data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
			if data:
				(serie, tTitle, tStart_time, tRref, twebChannel) = data[0]
				if serie == serien_name and int(tStart_time) == int(start_time):
					found = True
					break
		readTimer.close()

		if not found:
			writeTimer = open(self.timerFile, "a")
			writeTimer.write('"%s" "%s" "%s" "%s" "%s"\n' % (serien_name, title, start_time, stbRef, webChannel))
			writeTimer.close()
			print "[Serien Recorder] Timer angelegt: %s %s" % (serien_name, title)
			writeLog("[Serien Recorder] Timer angelegt: %s %s" % (serien_name, title))
		else:
			print "[Serien Recorder] Timer bereits vorhanden: %s %s" % (serien_name, title)
			writeLog("[Serien Recorder] Timer bereits vorhanden: %s %s" % (serien_name, title))

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
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/red_round.png" position="20,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="red" position="60,656" size="250,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
			
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/green_round.png" position="310,651" zPosition="1" size="32,32" alphatest="on" />
			<widget name="green" position="350,656" size="210,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session

		self["actions"]  = ActionMap(["OkCancelActions", "ShortcutActions", "WizardActions", "ColorActions", "SetupActions", "NumberActions", "MenuActions", "EPGSelectActions"], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"red"	: self.keyRed,
			"green" : self.viewChange,
			"0"		: self.readLogFile,
			"1"		: self.modifyAddedFile
		}, -1)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20))
		self.chooseMenuList.l.setItemHeight(50)
		self['list'] = self.chooseMenuList
		self['title'] = Label("")
		self['red'] = Label("Entferne Timer")
		
		if config.plugins.serienRec.recordListView.value == 0:
			self['green'] = Label("Zeige früheste Timer zuerst")
		elif config.plugins.serienRec.recordListView.value == 1:
			self['green'] = Label("Zeige neuste Timer zuerst")

		self.red = 0xf23d21
		self.green = 0x389416
		self.blue = 0x0064c7
		self.yellow = 0xbab329
		self.white = 0xffffff
		self.timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"

		self.onLayoutFinish.append(self.readTimer)

	def readLogFile(self):
		self.session.open(serienRecReadLog)
		
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

	def readTimer(self):
		if not fileExists(self.timerFile):
			open(self.timerFile, 'w').close()

		current_time = int(time.time())
		deltimer = 0
		timerList = []
		timerFile_leer = os.path.getsize(self.timerFile)
		
		if config.plugins.serienRec.pastTimer.value:
			writeNewTimer = open(self.timerFile+".tmp", "w")

		if not timerFile_leer == 0:
			readTimer = open(self.timerFile, "r")
			for rawData in readTimer.readlines():
				data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
				(serie, title, start_time, sRef, webChannel) = data[0]
				if config.plugins.serienRec.pastTimer.value:
					if int(current_time) > int(start_time):
						deltimer += 1
					else:
						writeNewTimer.write('"%s" "%s" "%s" "%s" "%s"\n' % (serie, title, start_time, sRef, webChannel))
						timerList.append((serie, title, start_time, webChannel, "0"))
				else:
					if int(current_time) > int(start_time):
						deltimer += 1
						timerList.append((serie, title, start_time, webChannel, "1"))
					else:
						timerList.append((serie, title, start_time, webChannel, "0"))

			readTimer.close()

			if config.plugins.serienRec.pastTimer.value:
				writeNewTimer.close()
				shutil.move(self.timerFile+".tmp", self.timerFile)
				if int(deltimer) != 0:
					self['title'].setText("TimerList: %s alte Aufnahme(n) entfernt." % deltimer)
				else:
					self['title'].setText("TimerList: %s Aufnahme(n) und %s Timer sind vorhanden." % (deltimer, len(timerList)))
			else:
				self['title'].setText("TimerList: %s Aufnahme(n) und %s Timer sind vorhanden." % (deltimer, len(timerList)))

			if config.plugins.serienRec.recordListView.value == 0:
				timerList.sort(key=lambda t : t[2])
			elif config.plugins.serienRec.recordListView.value == 1:
				timerList.sort(key=lambda t : t[2])
				timerList.reverse()

			self.chooseMenuList.setList(map(self.buildList, timerList))
		else:
			self['title'].setText("Serien Timer - 0 Serien in der Aufnahmeliste.")

	def buildList(self, entry):
		(serie, title, start_time, webChannel, foundIcon) = entry
		WochenTag=["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		xtime = time.strftime(WochenTag[time.localtime(int(start_time)).tm_wday]+", %d.%m.%Y - %H:%M", time.localtime(int(start_time)))

		if int(foundIcon) == 1:
			dirFound = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/found.png"
			imageFound = loadPNG(dirFound)
			return [entry,
				(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 8, 8, 32, 32, imageFound),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 250, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow)
				]
		else:
			return [entry,
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 3, 200, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webChannel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (Schweiz)','').replace(' (RP)','').replace(' (F)','').replace(' (\xd6sterreich)','')),
				(eListboxPythonMultiContent.TYPE_TEXT, 50, 29, 250, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, xtime, self.yellow),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 3, 500, 26, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, serie),
				(eListboxPythonMultiContent.TYPE_TEXT, 300, 29, 500, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, title, self.yellow)
				]

	def keyOK(self):
		pass

	def keyRed(self):
		check = self['list'].getCurrent()
		if check == None:
			print "[Serien Recorder] Serien Timer leer."
			return
		else:
			current_time = int(time.time())
			serien_name = self['list'].getCurrent()[0][0]
			serien_title = self['list'].getCurrent()[0][1]
			serien_time = self['list'].getCurrent()[0][2]
			serien_channel = self['list'].getCurrent()[0][3]
			found = False
			print self['list'].getCurrent()[0]
			timerFile_leer = os.path.getsize(self.timerFile)
			if not timerFile_leer == 0:
				readTimer = open(self.timerFile, "r")
				for rawData in readTimer.readlines():
					data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
					(serie, xtitle, xtime, xsref, webchannel) = data[0]
					if serien_name.lower() == serie.lower() and int(serien_time) == int(xtime) and serien_channel.lower() == webchannel.lower():
						found = True
						break
				readTimer.close()
			else:
				print "[Serien Recorder] keinen passenden timer gefunden."

			if found:
				timerList = []
				timerFile_leer = os.path.getsize(self.timerFile)
				if not timerFile_leer == 0:
					readTimer = open(self.timerFile, "r")
					writeTimer = open(self.timerFile+".tmp", "w")
					for rawData in readTimer.readlines():
						data = re.findall('"(.*?)" "(.*?)" "(.*?)" "(.*?)" "(.*?)"', rawData, re.S)
						(serie, xtitle, xtime, xsref, webchannel) = data[0]
						if serien_name.lower() == serie.lower() and int(serien_time) == int(xtime) and serien_channel.lower() == webchannel.lower():
							print "[Serien Recorder] Timer %s removed." % serie
							title = "%s - %s" % (serien_name, serien_title)
							removed = serienRecAddTimer.removeTimerEntry(title, serien_time)
							if removed:
								print "[Serien Recorder] enigma2 Timer removed."
							else:
								print "[Serien Recorder] enigma2 NOOOTTT removed"
						else:
							if int(current_time) > int(xtime):
								timerList.append((serie, xtitle, xtime, webchannel, "1"))
								writeTimer.write('"%s" "%s" "%s" "%s" "%s" "%s"\n' % (serie, xtitle, xtime, xsref, webchannel, "1"))
							else:
								writeTimer.write('"%s" "%s" "%s" "%s" "%s" "%s"\n' % (serie, xtitle, xtime, xsref, webchannel, "0"))
								timerList.append((serie, xtitle, xtime, webchannel, "0"))

					readTimer.close()
					writeTimer.close()

					if config.plugins.serienRec.recordListView.value == 0:
						timerList.sort(key=lambda t : t[2])
					elif config.plugins.serienRec.recordListView.value == 1:
						timerList.sort(key=lambda t : t[2])
						timerList.reverse()

					self.chooseMenuList.setList(map(self.buildList, timerList))
					shutil.move(self.timerFile+".tmp", self.timerFile)
					#self.readTimer()
					self['title'].instance.setForegroundColor(parseColor("red"))
					self['title'].setText("Timer '- %s -' entfernt." % serien_name)

	def keyCancel(self):
		self.close()

	def dataError(self, error):
		print error

class serienRecSetup(Screen, ConfigListScreen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="config" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
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
		self.list.append(getConfigListEntry("Entferne alte Timer aus der Record-List:", config.plugins.serienRec.pastTimer))
		self.list.append(getConfigListEntry("Automatisches Plugin-Update:", config.plugins.serienRec.Autoupdate))
		self.list.append(getConfigListEntry("Aus Deep-StandBy aufwecken:", config.plugins.serienRec.wakeUpDSB))
		self.list.append(getConfigListEntry("Nach dem automatischen Suchlauf in Deep-StandBy gehen:", config.plugins.serienRec.afterAutocheck))
		self.list.append(getConfigListEntry("DEBUG LOG (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log):", config.plugins.serienRec.writeLog))
		self.list.append(getConfigListEntry("DEBUG LOG - Senderliste:", config.plugins.serienRec.writeLogChannels))
		self.list.append(getConfigListEntry("DEBUG LOG - Seriensender:", config.plugins.serienRec.writeLogAllowedSender))
		self.list.append(getConfigListEntry("DEBUG LOG - Episoden:", config.plugins.serienRec.writeLogAllowedEpisodes))
		self.list.append(getConfigListEntry("DEBUG LOG - Added:", config.plugins.serienRec.writeLogAdded))
		self.list.append(getConfigListEntry("DEBUG LOG - Festplatte:", config.plugins.serienRec.writeLogDisk))
		self.list.append(getConfigListEntry("DEBUG LOG - Tageszeit:", config.plugins.serienRec.writeLogTimeRange))
		self.list.append(getConfigListEntry("DEBUG LOG - Zeitbegrenzung:", config.plugins.serienRec.writeLogTimeLimit))
		self.list.append(getConfigListEntry("DEBUG LOG - Timer Debugging:", config.plugins.serienRec.writeLogTimerDebug))

	def changedEntry(self):
		self.createConfigList()
		self["config"].setList(self.list)

	def ok(self):
		if self["config"].getCurrent() == self.get_media:
			start_dir = "/media/hdd/movie/"
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
		config.plugins.serienRec.Autoupdate.save()
		config.plugins.serienRec.fromTime.save()
		config.plugins.serienRec.toTime.save()
		config.plugins.serienRec.timeUpdate.save()
		config.plugins.serienRec.deltime.save()
		config.plugins.serienRec.pastTimer.save()
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

		configfile.save()
		self.close(True)

	def cancel(self):
		self.close(False)

class SerienRecFileList(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,15" size="820,55" foregroundColor="red" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="center" />
			<widget name="media" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="folderlist" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
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
			self.fullpath = self["folderlist"].getSelection()[0] + "/"
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
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
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
		self['red'] = Label("Exit")
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
			(eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 1280, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
			]

	def keyCancel(self):
		self.close()

class serienRecLogReader(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel25_1200.png" />
			
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
		self['title'] = Label("Suchlauf für neue Timer läuft.")
		self['red'] = Label("Exit")
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
				self['title'].setText('Suchlauf für neue Timer läuft.%s' % self.points)
					
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
		if answer is True:
			if self.delete_files == "True":
				print "[Serien Recorder] lösche config files.."

				self.markerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/marker"
				if fileExists(self.markerFile):
					os.remove(self.markerFile)

				self.channelFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/channels"
				if fileExists(self.channelFile):
					os.remove(self.channelFile)

				self.timerFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/timer"
				if fileExists(self.timerFile):
					os.remove(self.timerFile)

				self.logFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/log"
				if fileExists(self.logFile):
					os.remove(self.logFile)

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
		self.container.execute("opkg install --force-overwrite --force-depends " + str(self.updateurl))

	def finishedPluginUpdate(self,retval):
		self.session.openWithCallback(self.restartGUI, MessageBox, _("Serien Recorder successfully updated!\nDo you want to restart the Enigma2 GUI now?"), MessageBox.TYPE_YESNO)

	def restartGUI(self, answer):
		if answer is True:
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
		
class serienRecModifyAdded(Screen):
	skin = """
		<screen position="center,center" size="1280,720" title="Serien Recorder">
			<ePixmap position="0,0" size="1280,720" zPosition="-1" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/bg.png" />
			<widget name="title" position="50,55" size="820,55" foregroundColor="#00ffffff" backgroundColor="#26181d20" transparent="1" font="Regular;26" valign="center" halign="left" />
			<widget source="global.CurrentTime" render="Label" position="850,55" size="400,55" font="Regular;26" valign="center" halign="right" backgroundColor="#26181d20" transparent="1">
				<convert type="ClockToText">Format:%A, %d.%m.%Y  %H:%M</convert>
			</widget>
			<widget source="session.VideoPicture" render="Pig" position="913,135" size="328,186" zPosition="3" backgroundColor="transparent" />
			<eLabel position="912,134" size="330,188" backgroundColor="#00ffffff" zPosition="0" name="Videoback" />
			<eLabel position="913,135" size="328,186" backgroundColor="#00000000" zPosition="1" name="Videofill" />
			<widget name="list" position="20,135" size="870,500" backgroundColor="#000000" scrollbarMode="showOnDemand" transparent="0" zPosition="5" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/sel40_1200.png" />
			
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
		
		self.delAdded = False
		self.sortedList = False
		self.addedliste = []
		self.addedliste_tmp = []
		self.addedFile = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added"

		self.onLayoutFinish.append(self.readAdded)

	def save(self):
		if self.delAdded:
			writeAddedFile = open(self.addedFile, 'w')
			for zeile in self.addedliste:
				writeAddedFile.write('%s\n' % (zeile))
			writeAddedFile.close()
			
		self.close()
			
	def readAdded(self):
		# copy addedFile to _old
		if fileExists(self.addedFile):
			shutil.copy(self.addedFile,self.addedFile+"_old")
		else:
			return

		addedFile_leer = os.path.getsize(self.addedFile)
		self.addedliste = []
		
		if not addedFile_leer == 0:
			readAddedFile = open(self.addedFile, "r")
			for zeile in readAddedFile.readlines():
				self.addedliste.append((zeile.replace('\n','')))
			readAddedFile.close()

		self['title'].setText("AddedFile: (/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/added)")
		self.addedliste_tmp = self.addedliste[:]
		self.chooseMenuList.setList(map(self.buildList, self.addedliste_tmp))
			
	def buildList(self, entry):
		(zeile) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 1280, 18, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)
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
			self.addedliste_tmp.remove((zeile))
			self.addedliste.remove((zeile))
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

	def dataError(self, error):
		print error
