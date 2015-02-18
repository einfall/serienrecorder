# This file contain some helper functions
# which called from other SerienRecorder modules
from __init__ import _

from Components.config import config
from Components.AVSwitch import AVSwitch

from enigma import eServiceReference, eTimer, eServiceCenter, eEPGCache, ePicLoad

from Screens.ChannelSelection import service_types_tv

from Tools.Directories import fileExists

import datetime, random, os, re, urllib2

# ----------------------------------------------------------------------------------------------------------------------
#
# Common functions
#
# ----------------------------------------------------------------------------------------------------------------------

# the new API for the Dreambox DM7080HD changes the behavior
# of eTimer append - here are the changes
try:
	from enigma import eMediaDatabase
except ImportError as ie:
	isDreamboxOS = False
else:
	isDreamboxOS = True

def decodeISO8859_1(txt, doReplaces=False):
	txt = unicode(txt, 'ISO-8859-1')
	txt = txt.encode('utf-8')
	if doReplaces:
		txt = txt.replace('...','').replace('..','').replace(':','')
		# &apos;, &quot;, &amp;, &lt;, and &gt;
		txt = txt.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	return txt

def decodeCP1252(txt, doReplaces=False):
	txt = unicode(txt, 'cp1252')
	txt = txt.encode('utf-8')
	if doReplaces:
		txt = txt.replace('...','').replace('..','').replace(':','')
		# &apos;, &quot;, &amp;, &lt;, and &gt;
		txt = txt.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	return txt

	
def getUserAgent():
	userAgents = [
		"Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; de) Presto/2.9.168 Version/11.52",
	    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:29.0) Gecko/20120101 Firefox/29.0",
	    "Mozilla/5.0 (X11; Linux x86_64; rv:28.0) Gecko/20100101 Firefox/28.0",
	    "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)",
	    "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 7.1; Trident/5.0)",
	    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2",
	    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.67 Safari/537.36",
	    "Mozilla/5.0 (compatible; Konqueror/4.5; FreeBSD) KHTML/4.5.4 (like Gecko)",
	    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0"
	]
	today = datetime.date.today()
	random.seed(today.toordinal())
	return userAgents[random.randint(0, 8)]

# ----------------------------------------------------------------------------------------------------------------------
#
# TimeHelper - Time related helper functions
# All methods are "static" and the TimeHelper class is more or less a namespace only
#
# Use: TimeHelpers::getNextDayUnixtime(...)
#
# ----------------------------------------------------------------------------------------------------------------------

class TimeHelpers:
	@classmethod
	def getNextDayUnixtime(cls, minutes, hour, day, month):
		now = datetime.datetime.now()
		if int(month) < now.month:
			date = datetime.datetime(int(now.year) + 1,int(month),int(day),int(hour),int(minutes))
		else:
			date = datetime.datetime(int(now.year),int(month),int(day),int(hour),int(minutes))
		date += datetime.timedelta(days=1)
		return date.strftime("%s")

	@classmethod
	def getUnixTimeAll(cls, minutes, hour, day, month):
		now = datetime.datetime.now()
		if int(month) < now.month:
			return datetime.datetime(int(now.year) + 1, int(month), int(day), int(hour), int(minutes)).strftime("%s")
		else:
			return datetime.datetime(int(now.year), int(month), int(day), int(hour), int(minutes)).strftime("%s")

	@classmethod
	def getUnixTimeWithDayOffset(cls, hour, minutes, AddDays):
		now = datetime.datetime.now()
		date = datetime.datetime(now.year, now.month, now.day, int(hour), int(minutes))
		date += datetime.timedelta(days=AddDays)
		return date.strftime("%s")

	@classmethod
	def getRealUnixTime(cls, minutes, hour, day, month, year):
		return datetime.datetime(int(year), int(month), int(day), int(hour), int(minutes)).strftime("%s")

	@classmethod
	def allowedTimeRange(cls, fromTime, toTime, start_time, end_time):
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

# ----------------------------------------------------------------------------------------------------------------------
#
# STBHelpers - STB related helper functions
# All methods are "static" and the STBHelper class is more or less a namespace only
#
# Use: STBHelpers::getServiceList(...)
#
# ----------------------------------------------------------------------------------------------------------------------

class STBHelpers:
	EPGTimeSpan = 10

	@classmethod
	def getServiceList(cls, ref):
		root = eServiceReference(str(ref))
		serviceHandler = eServiceCenter.getInstance()
		return serviceHandler.list(root).getContent("SN", True)

	@classmethod
	def getTVBouquets(cls):
		return cls.getServiceList(service_types_tv + ' FROM BOUQUET "bouquets.tv" ORDER BY bouquet')

	@classmethod
	def buildSTBChannelList(cls, BouquetName=None):
		serien_chlist = None
		serien_chlist = []
		print "[SerienRecorder] read STV Channellist.."
		tvbouquets = cls.getTVBouquets()
		print "[SerienRecorder] found %s bouquet: %s" % (len(tvbouquets), tvbouquets)

		if not BouquetName:
			for bouquet in tvbouquets:
				bouquetlist = []
				bouquetlist = cls.getServiceList(bouquet[0])
				for (serviceref, servicename) in bouquetlist:
					serien_chlist.append((servicename, serviceref))
		else:
			for bouquet in tvbouquets:
				if bouquet[1] == BouquetName:
					bouquetlist = []
					bouquetlist = cls.getServiceList(bouquet[0])
					for (serviceref, servicename) in bouquetlist:
						serien_chlist.append((servicename, serviceref))
					break
		return serien_chlist

	@classmethod
	def getChannelByRef(cls, stb_chlist,serviceref):
		for (channelname,channelref) in stb_chlist:
			if channelref == serviceref:
				return channelname

	@classmethod
	def getEPGTimeSpan(cls):
		return int(cls.EPGTimeSpan)

	@classmethod
	def getEPGEvent(cls, query, channelref, title, starttime):
		if not query or len(query) != 2:
			return

		epgmatches = []
		epgcache = eEPGCache.getInstance()
		allevents = epgcache.lookupEvent(query) or []

		for serviceref, eit, name, begin, duration, shortdesc, extdesc in allevents:
			_name = name.strip().replace(".","").replace(":","").replace("-","").replace("  "," ").lower()
			_title = title.strip().replace(".","").replace(":","").replace("-","").replace("  "," ").lower()
			if (channelref == serviceref) and (_name.count(_title) or _title.count(_name)):
				if int(int(begin)-(int(cls.getEPGTimeSpan())*60)) <= int(starttime) <= int(int(begin)+(int(cls.getEPGTimeSpan())*60)):
					epgmatches.append((serviceref, eit, name, begin, duration, shortdesc, extdesc))
		return epgmatches

	@classmethod
	def getStartEndTimeFromEPG(cls, start_unixtime_eit, end_unixtime_eit, margin_before, margin_after, serien_name, STBRef):
		eit = 0
		if config.plugins.serienRec.eventid.value:
			# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
			event_matches = cls.getEPGEvent(['RITBDSE', (STBRef, 0, int(start_unixtime_eit) + (int(margin_before) * 60), -1)], STBRef, serien_name, int(start_unixtime_eit) + (int(margin_before) * 60))
			if event_matches and len(event_matches) > 0:
				for event_entry in event_matches:
					print "[Serien Recorder] found eventID: %s" % int(event_entry[1])
					eit = int(event_entry[1])
					start_unixtime_eit = int(event_entry[3]) - (int(margin_before) * 60)
					end_unixtime_eit = int(event_entry[3]) + int(event_entry[4]) + (int(margin_after) * 60)
					break

		return eit, end_unixtime_eit, start_unixtime_eit

	@classmethod
	def countEpisodeOnHDD(cls, dirname, seasonEpisodeString, serien_name, stopAfterFirstHit = False, title = None):
		count = 0
		if fileExists(dirname):
			if title is None:
				searchString = '%s.*?%s.*?\.ts\Z' % (re.escape(serien_name), re.escape(seasonEpisodeString))
			else:
				searchString = '%s.*?%s.*?%s.*?\.ts\Z' % (re.escape(serien_name), re.escape(seasonEpisodeString), re.escape(title))
			dirs = os.listdir(dirname)
			for dir in dirs:
				if re.search(searchString, dir):
					count += 1
					if stopAfterFirstHit:
						break

		return count

	@classmethod
	def getImageVersionString(cls):
		from Components.About import about

		creator = _("n/a")
		version = _("n/a")

		if hasattr(about,'getVTiVersionString'):
			creator = about.getVTiVersionString()
		else:
			creator = about.getEnigmaVersionString()
		version = about.getVersionString()

		return ' / '.join((creator, version))

	@classmethod
	def getSTBType(cls):
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

# ----------------------------------------------------------------------------------------------------------------------
#
# PicLoader
#
# ----------------------------------------------------------------------------------------------------------------------

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

# ----------------------------------------------------------------------------------------------------------------------
#
# imdbVideo
#
# ----------------------------------------------------------------------------------------------------------------------

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