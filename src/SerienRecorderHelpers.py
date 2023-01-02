# coding=utf-8

# This file contain some helper functions
# which called from other SerienRecorder modules
from Components.config import config
from Components.AVSwitch import AVSwitch

from enigma import eServiceReference, eTimer, eServiceCenter, eEPGCache, ePicLoad, iServiceInformation

from Screens.ChannelSelection import service_types_tv

from Tools.Directories import pathExists, fileExists, SCOPE_SKIN, resolveFilename

import datetime, os, re, sys, time, shutil

# ----------------------------------------------------------------------------------------------------------------------
#
# Common functions
#
# ----------------------------------------------------------------------------------------------------------------------

STBTYPE = None
SRVERSION = '4.6.1-beta'
SRDBVERSION = '4.6.0'
SRAPIVERSION = '2.8'
SRWEBAPPVERSION = '1.1.0'
SRMANUALURL = "https://einfall.github.io/serienrecorder/"
SRCOPYRIGHT = "©2014-23 einfall, w22754, egn und MacDisein"

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3
PY3_4 = sys.version_info[0] == 3 and sys.version_info[1] >= 4

def toBinary(s):
	if PY3 and isinstance(s, str):
		return s.encode('utf-8')
	else:
		return s

def toStr(s):
	if isinstance(s, str):
		return s
	if PY2 and isinstance(s, unicode):
		return s.encode("utf-8")
	elif PY3 and isinstance(s, bytes):
		return s.decode("utf-8")
	return s

def doReplaces(txt):
	non_allowed_characters = "/.\\:*?<>|\"'"
	cleanedString = ''

	for c in txt:
		if c in non_allowed_characters or ord(c) < 32:
			c = "_"
		cleanedString += c

	cleanedString = cleanedString.replace('&amp;','&').replace('&apos;',"'").replace('&gt;','>').replace('&lt;','<').replace('&quot;','"')
	cleanedString = re.sub(r"\[.*\]", "", cleanedString).strip()
	return cleanedString

def isDreamOS():
	try:
		from enigma import eMediaDatabase
	except ImportError:
		isDreamboxOS = False
	else:
		isDreamboxOS = True
	return isDreamboxOS

def hasAutoAdjust():
	try:
		from RecordTimer import RecordTimerEntry
		from ServiceReference import ServiceReference
		dummyTimerObject = RecordTimerEntry(ServiceReference("1:0:1:0:0:0:0:0:0:0"), 0, 0, None, None, 0)
		if hasattr(dummyTimerObject, "autoadjust"):
			return True
	except:
		pass
	return False

def getKindOfTimerChoices():
	from RecordTimer import RecordTimerEntry
	from ServiceReference import ServiceReference
	dummyTimerObject = RecordTimerEntry(ServiceReference("1:0:1:0:0:0:0:0:0:0"), 0, 0, None, None, 0)
	print("[SerienRecorder] RecordTimerEntry attributes", dir(dummyTimerObject))

	kindOfTimerChoices = [("0", "Aufnehmen")]
	if hasattr(dummyTimerObject, 'justplay'):
		print("[SerienRecorder] RecordTimerEntry has 'justplay'")
		kindOfTimerChoices.append(("1", "Umschalten"))
	if hasattr(dummyTimerObject, 'always_zap') or hasattr(dummyTimerObject, 'zapbeforerecord'):
		print("[SerienRecorder] RecordTimerEntry has 'always_zap' or 'zapbeforerecord'")
		kindOfTimerChoices.append(("2", "Umschalten und aufnehmen"))
	if hasattr(dummyTimerObject, 'justremind'):
		print("[SerienRecorder] RecordTimerEntry has 'justremind'")
		kindOfTimerChoices.append(("4", "Erinnerung"))

	return kindOfTimerChoices

def base64_encode(bytes_or_str):
	import base64

	input_bytes = toBinary(bytes_or_str)
	output_bytes = base64.urlsafe_b64encode(input_bytes)
	if PY3:
		return output_bytes.decode('ascii')
	else:
		return output_bytes

def base64_decode(bytes_or_str):
	import base64

	if PY3 and isinstance(bytes_or_str, str):
		input_bytes = bytes_or_str.encode('ascii')
	else:
		input_bytes = bytes_or_str

	output_bytes = base64.urlsafe_b64decode(input_bytes)
	return toStr(output_bytes)

def encrypt(key, clear):
	enc = []
	for i in range(len(clear)):
		key_c = key[i % len(key)]
		enc_c = chr((ord(clear[i]) + ord(key_c)) % 256)
		enc.append(enc_c)
	return base64_encode("".join(enc))

def decrypt(key, enc):
	dec = []
	enc = base64_decode(enc)
	for i in range(len(enc)):
		key_c = key[i % len(key)]
		dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
		dec.append(dec_c)
	return "".join(dec)

def testWebConnection():
	if PY2:
		import httplib
	else:
		import http.client as httplib

	conn = httplib.HTTPConnection("www.google.com", timeout=10)
	try:
		conn.request("GET", "/")
		#data = conn.getresponse()
		#print("[SerienRecorder] Status: %s   and reason: %s" % (data.status, data.reason))
		conn.close()
		return True
	except:
		conn.close()
	return False

def getChangedSeriesNames(markers):
	IDs = []
	for marker in markers:
		(markerID, name, info, wlID, fsID) = marker
		IDs.append(wlID)

	from .SerienRecorderSeriesServer import SeriesServer
	series = SeriesServer().getSeriesNamesAndInfoByWLID(IDs)

	result = {}
	#from SerienRecorderLogWriter import SRLogger
	for marker in markers:
		try:
			(markerID, name, info, wlID, fsID) = marker
			for serie in series:
				if str(wlID) == str(serie['id']):
					if name != serie['name'] or info != serie['info'] or fsID != serie['fs_id']:
						#SRLogger.writeTestLog("Found difference: %s [%s / %s]" % (name, serie['name'], serie['info']))
						result[str(wlID)] = dict( old_name = name, new_name = serie['name'], new_info = serie['info'], old_fsID = fsID, new_fsID = serie['fs_id'] )
					break
		except:
			continue
	return result

def createBackup(isManualAutoCheck):
	if not config.plugins.serienRec.backupAtManualCheck.value and isManualAutoCheck:
		return
	print("[SerienRecorder] Creating backup...")

	from .SerienRecorderLogWriter import SRLogger
	from .SerienRecorderTVPlaner import SERIENRECORDER_TVPLANER_HTML_FILENAME
	lt = time.localtime()

	# Remove old backups
	if config.plugins.serienRec.deleteBackupFilesOlderThan.value > 0:
		SRLogger.writeLog("\nEntferne alte Backup-Dateien und erzeuge neues Backup.", True)
		now = time.time()
		logFolderPattern = re.compile('\d{4}\d{2}\d{2}\d{2}\d{2}')
		for root, dirs, files in os.walk(config.plugins.serienRec.BackupPath.value, topdown=False):
			for name in dirs:
				if logFolderPattern.match(name) and os.stat(os.path.join(root, name)).st_ctime < (now - config.plugins.serienRec.deleteBackupFilesOlderThan.value * 24 * 60 * 60):
					shutil.rmtree(os.path.join(root, name), True)
					SRLogger.writeLog("Lösche Backup Ordner: %s" % os.path.join(root, name), True)
	else:
		SRLogger.writeLog("Erzeuge neues Backup", True)

	backup_path = "%s%s%s%s%s%s/" % (config.plugins.serienRec.BackupPath.value, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
	if not os.path.exists(backup_path):
		try:
			os.makedirs(backup_path)
		except:
			pass
	if os.path.isdir(backup_path):
		try:
			from .SerienRecorder import getDataBaseFilePath
			if fileExists(getDataBaseFilePath()):
				from .SerienRecorderDatabase import SRDatabase
				database = SRDatabase(getDataBaseFilePath())
				database.backup(backup_path)
			if fileExists(SRLogger.getLogFilePath()):
				shutil.copy(SRLogger.getLogFilePath(), backup_path)
			if fileExists("/etc/enigma2/timers.xml"):
				shutil.copy("/etc/enigma2/timers.xml", backup_path)
			if fileExists("/etc/enigma2/timers_vps.xml"):
				shutil.copy("/etc/enigma2/timers_vps.xml", backup_path)
			STBHelpers.saveEnigmaSettingsToFile(backup_path)
			htmlFilePath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_TVPLANER_HTML_FILENAME)
			if fileExists(htmlFilePath):
				shutil.copy(htmlFilePath, backup_path)

			for filename in os.listdir(backup_path):
				os.chmod(os.path.join(backup_path, filename), 0o777)
		except Exception as e:
			print("[SerienRecorder] Failed to create backup", e)
			SRLogger.writeLog("Backup konnte nicht erstellt werden: " + str(e), True)

	print("[SerienRecorder] Backup created")

def createCompressedBackup(isManualAutoCheck):
	if not config.plugins.serienRec.backupAtManualCheck.value and isManualAutoCheck:
		return
	print("[SerienRecorder] Creating compressed backup...")

	from .SerienRecorderLogWriter import SRLogger
	from .SerienRecorderTVPlaner import SERIENRECORDER_TVPLANER_HTML_FILENAME
	lt = time.localtime()

	backup_path = config.plugins.serienRec.BackupPath.value
	if not os.path.exists(backup_path):
		try:
			os.makedirs(backup_path)
		except:
			pass

	# Remove old backups
	if config.plugins.serienRec.deleteBackupFilesOlderThan.value > 0:
		SRLogger.writeLog("\nEntferne alte Backup-Dateien und erzeuge neues Backup.", True)
		now = time.time()
		logFilePattern = re.compile('\d{4}\d{2}\d{2}\d{2}\d{2}-SerienRecorder-Backup')
		for filename in os.listdir(backup_path):
			if logFilePattern.match(filename) and filename.endswith("tar.gz") and os.stat(os.path.join(backup_path, filename)).st_ctime < (now - config.plugins.serienRec.deleteBackupFilesOlderThan.value * 24 * 60 * 60):
				os.remove(os.path.join(backup_path, filename))
				SRLogger.writeLog("Lösche Backup: %s" % os.path.join(backup_path, filename), True)
	else:
		SRLogger.writeLog("Erzeuge neues Backup", True)

	if os.path.isdir(backup_path):
		try:
			import tarfile

			backup_filepath = "%s%s%s%s%s%s-SerienRecorder-Backup.tar.gz" % (backup_path, lt.tm_year, str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2))
			with tarfile.open(backup_filepath, "w:gz") as tar:
				from .SerienRecorder import getDataBaseFilePath
				serienRecMainPath = os.path.dirname(__file__)

				if fileExists(getDataBaseFilePath()):
					from .SerienRecorderDatabase import SRDatabase
					database = SRDatabase(getDataBaseFilePath())
					database_backup_filepath = "/tmp/SerienRecorder.db"
					database.backup("/tmp/")
					tar.add(database_backup_filepath, arcname=getDataBaseFilePath())
					os.remove(database_backup_filepath)
				if fileExists(SRLogger.getLogFilePath()):
					tar.add(SRLogger.getLogFilePath())
				if fileExists("/etc/enigma2/timers.xml"):
					tar.add("/etc/enigma2/timers.xml")
				if fileExists("/etc/enigma2/timers_vps.xml"):
					tar.add("/etc/enigma2/timers_vps.xml")
				STBHelpers.saveEnigmaSettingsToFile("/tmp/")
				tar.add(os.path.join("/tmp", "Config.backup"), arcname=os.path.join(serienRecMainPath, "Config.backup"))
				htmlFilePath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_TVPLANER_HTML_FILENAME)
				if fileExists(htmlFilePath):
					tar.add(htmlFilePath)
		except Exception as e:
			print("[SerienRecorder] Failed to create backup", e)
			SRLogger.writeLog("Backup konnte nicht erstellt werden: " + str(e), True)

	print("[SerienRecorder] Compressed backup created")

def getDirname(database, serien_name, serien_fsid, staffel):
	if config.plugins.serienRec.seasonsubdirfillchar.value == '<SPACE>':
		seasonsubdirfillchar = ' '
	else:
		seasonsubdirfillchar = config.plugins.serienRec.seasonsubdirfillchar.value
	# This is to let the user configure the name of the Sesaon subfolder
	# If a file called 'Staffel' exists in SerienRecorder folder the folder will be created as "Staffel" instead of "Season"
	serienRecMainPath = os.path.dirname(__file__)
	germanSeasonNameConfig = "%s/Staffel" % serienRecMainPath
	seasonDirName = "Season"
	if fileExists(germanSeasonNameConfig):
		seasonDirName = "Staffel"

	dirname = None
	seasonsubdir = -1
	isMovie = False
	row = database.getDirNames(serien_fsid)
	if not row:
		# It is a movie (because there is no marker)
		isMovie = True
	else:
		(dirname, seasonsubdir, type) = row
		if type == 1:
			isMovie = True

	if isMovie:
		path = config.plugins.serienRec.tvplaner_movies_filepath.value
		isCreateSerienSubDir = config.plugins.serienRec.tvplaner_movies_createsubdir.value
		withYear = False
		isCreateSeasonSubDir = False
	else:
		path = config.plugins.serienRec.savetopath.value
		isCreateSerienSubDir = config.plugins.serienRec.seriensubdir.value
		withYear = config.plugins.serienRec.seriensubdirwithyear.value
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
			if withYear:
				info = database.getMarkerInfo(serien_fsid)
				if info:
					match = re.search("([0-9xX]{4})-?(?:[0-9xX]{4})?$", info)
					serien_name = "%s (%s)" % (serien_name, match.group(1))
			dirname = "%s%s/" % (dirname, "".join(i for i in serien_name if i not in "\/:*?<>|."))
			dirname_serie = dirname
			if isCreateSeasonSubDir:
				dirname = "%s%s %s/" % (dirname, seasonDirName, str(staffel).lstrip('0 ').rjust(config.plugins.serienRec.seasonsubdirnumerlength.value, seasonsubdirfillchar))

	return dirname, dirname_serie

def readTags(tagString):
	tags = []
	if tagString.startswith("(lp1"):
		# tags are pickled
		if PY2:
			import cPickle as pickle
			tags = pickle.loads(tagString)
		else:
			import pickle
			tags = pickle.loads(toBinary(tagString), encoding="utf-8")
	else:
		import json
		tags = [toStr(x) for x in json.loads(tagString)]

	return tags

# ----------------------------------------------------------------------------------------------------------------------
#
# TimeHelper - Time related helper functions
# All methods are "static" and the TimeHelper class is more or less a namespace only
#
# Use: TimeHelpers::getNextDayUnixtime(...)
#
# ----------------------------------------------------------------------------------------------------------------------

class TimeHelpers:
	def __init__(self):
		pass

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
	def getRealUnixTimeWithDayOffset(cls, minutes, hour, day, month, year, AddDays):
		date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minutes))
		date += datetime.timedelta(days=AddDays)
		return date.strftime("%s")
		
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

	@classmethod
	def td2HHMMstr(cls, td):
		# Convert timedelta objects to a HH:MM string with (+/-) sign
		if td < datetime.timedelta(seconds=0):
			sign='-'
			td = -td
		else:
			sign = ''

		if sys.version_info < (2, 7):
			def tts(timedelta):
				return (timedelta.microseconds + 0.0 + (timedelta.seconds + timedelta.days * 24 * 3600) * 10 ** 6) / 10 ** 6
			tdstr_s = '{0}{1:}:{2:02d}'
		else:
			def tts(timedelta):
				return timedelta.total_seconds()
			tdstr_s = '{}{:}:{:02d}'

		tdhours, rem = divmod(tts(td), 3600)
		tdminutes, rem = divmod(rem, 60)
		tdstr = tdstr_s.format(sign, int(tdhours), int(tdminutes))
		return tdstr

# ----------------------------------------------------------------------------------------------------------------------
#
# STBHelpers - STB related helper functions
# All methods are "static" and the STBHelper class is more or less a namespace only
#
# Use: STBHelpers::getServiceList(...)
#
# ----------------------------------------------------------------------------------------------------------------------

class STBHelpers:

	def __init__(self):
		pass

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
		serien_chlist = []
		mask = (eServiceReference.isMarker | eServiceReference.isDirectory)
		print("[SerienRecorder] Read box channellist")
		tvbouquets = cls.getTVBouquets()
		print("[SerienRecorder] Found %d bouquet: %s" % (len(tvbouquets), tvbouquets))

		if not BouquetName:
			print("[SerienRecorder] Get channels from all bouquets")
			for bouquet in tvbouquets:
				bouquetlist = cls.getServiceList(bouquet[0])
				for (serviceref, servicename) in bouquetlist:
					playable = not (eServiceReference(serviceref).flags & mask)
					if playable:
						serien_chlist.append((servicename, serviceref))
		else:
			print("[SerienRecorder] Get channels for bouquet %s" % BouquetName)
			for bouquet in tvbouquets:
				if bouquet[1] == BouquetName:
					bouquetlist = cls.getServiceList(bouquet[0])
					for (serviceref, servicename) in bouquetlist:
						playable = not (eServiceReference(serviceref).flags & mask)
						if playable:
							serien_chlist.append((servicename, serviceref))
					break
		print("[SerienRecorder] Number of channels found: %d" % len(serien_chlist))

		if config.plugins.serienRec.alphaSortBoxChannels.value:
			serien_chlist.sort(key=lambda x: x[0])

		return serien_chlist

	@classmethod
	def getChannelByRef(cls, stb_chlist,serviceref):
		for (channelname,channelref) in stb_chlist:
			if channelref == serviceref:
				return channelname

	@classmethod
	def getEPGTimeSpan(cls):
		return int(config.plugins.serienRec.epgTimeSpan.value)

	@classmethod
	def getEPGEvent(cls, channelref, title, epg_title, starttime):
		starttime_str = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(starttime)))
		print("[SerienRecorder] getEPGEvent: Try to find: %s (%s) [%s (%d)]" % (title, epg_title, starttime_str, starttime))

		epg_timespan = int(cls.getEPGTimeSpan() * 60)

		epgmatches = []
		epgcache = eEPGCache.getInstance()
		query = ['ITBDS', (channelref, 0, int(starttime) - epg_timespan, -1)]
		allevents = epgcache.lookupEvent(query) or []

		import re
		regex = re.compile(r"\(\d+/?\d*\)$", re.IGNORECASE)
		normalized_title = regex.sub("", title.lower().replace(" ", ""))
		normalized_epg_title = regex.sub("", epg_title.lower().replace(" ", ""))

		lowEPGStartTime = int(starttime) - epg_timespan
		lowEPGStartTime_str = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(lowEPGStartTime)))
		highEPGStartTime = int(starttime) + epg_timespan
		highEPGStartTime_str = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(highEPGStartTime)))
		print("[SerienRecorder] getEPGEvent: Boundaries: [%s (%d)] - [%s (%d)]" % (lowEPGStartTime_str, lowEPGStartTime, highEPGStartTime_str, highEPGStartTime))

		for eit, name, begin, event_duration, shortdesc in allevents:
			normalized_name = regex.sub("", name.lower().replace(" ", ""))

			nameMatch = False
			begin_str = time.strftime("%d.%m.%Y - %H:%M", time.localtime(int(begin)))
			print("[SerienRecorder] getEPGEvent: (%s): [%s (%s)] (%s) [%s]/[%s] == [%s] (%s)" % (str(eit), begin_str, str(begin), str(event_duration), normalized_title, normalized_epg_title, normalized_name, shortdesc))
			if normalized_name == normalized_title or (normalized_name in normalized_title or normalized_title in normalized_name):
				nameMatch = True
			elif len(normalized_epg_title) > 0 and (normalized_name == normalized_epg_title or (normalized_name in normalized_epg_title or normalized_epg_title in normalized_name)):
				nameMatch = True

			if bool(lowEPGStartTime <= int(begin) <= highEPGStartTime) and nameMatch:
				print("[SerienRecorder] getEPGEvent: Event found")
				epgmatches.append((eit, name, begin, event_duration, shortdesc))
				break

			if begin > highEPGStartTime:
				break

		# no events found, epg matches
		return len(allevents) == 0, epgmatches

	@classmethod
	def getStartEndTimeFromEPG(cls, start_unixtime_eit, end_unixtime_eit, margin_before, series_name, epg_series_name, stbRef):
		eit = 0
		# event_matches = self.getEPGevent(['RITBDSE',("1:0:19:EF75:3F9:1:C00000:0:0:0:", 0, 1392755700, -1)], "1:0:19:EF75:3F9:1:C00000:0:0:0:", "2 Broke Girls", 1392755700)
		(noEventsFound, event_matches) = cls.getEPGEvent(stbRef, series_name, epg_series_name, int(start_unixtime_eit) + (int(margin_before) * 60))
		if event_matches and len(event_matches) > 0:
			for event_entry in event_matches:
				print("[SerienRecorder] found eventID: %s" % int(event_entry[0]))
				eit = int(event_entry[0])
				start_unixtime_eit = int(event_entry[2])
				end_unixtime_eit = int(event_entry[2]) + int(event_entry[3])
				break

		return eit, start_unixtime_eit, end_unixtime_eit

	@classmethod
	def countEpisodeOnHDD(cls, dirname, seasonEpisodeString, serien_name, stopAfterFirstHit = False, title = None):
		count = 0
		if fileExists(dirname):
			serien_name = doReplaces(serien_name)
			if title is None:
				searchString = '(%s){1}(\s|-)+(%s(?:\s.*|\.)){1}(ts|mkv|avi|mp4|divx|xvid|mpg|mov)$' % (re.escape(serien_name), re.escape(seasonEpisodeString))
			else:
				title = doReplaces(title)
				searchString = '(%s){1}(\s|-)+(%s(?:\s.*|\.)){1}(%s\.){1}(ts|mkv|avi|mp4|divx|xvid|mpg|mov)$' % (re.escape(serien_name), re.escape(seasonEpisodeString), re.escape(title))
			filenames = os.listdir(dirname)
			for filename in filenames:
				if re.search(searchString, filename):
					count += 1
					if stopAfterFirstHit:
						break

		return count

	@classmethod
	def getImageVersionString(cls):
		from Components.About import about
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
			from Tools.HardwareInfo import HardwareInfo
			try:
				STBType = HardwareInfo().get_device_model()
			except:
				try:
					STBType = HardwareInfo().get_device_name()
				except:
					STBType = "unknown"
		return STBType

	@classmethod
	def getmac(cls, interface):
		try:
			mac = open('/sys/class/net/' + interface + '/address').readline()
		except:
			mac = "00:00:00:00:00:00"
		return mac[0:17]

	@classmethod
	def saveEnigmaSettingsToFile(cls, path):
		writeConfFile = open(os.path.join(path, "Config.backup"), "w")
		readSettings = open("/etc/enigma2/settings", "r")
		for rawData in readSettings.readlines():
			data = re.findall('\Aconfig.plugins.serienRec.(.*?)=(.*?)\Z', rawData.rstrip(), re.S)
			if data:
				writeConfFile.write(rawData)
		writeConfFile.close()
		readSettings.close()

	@classmethod
	def createDirectory(cls, serien_fsid, markerType, dirname, dirname_serie, cover_only=False):
		from .SerienRecorderLogWriter import SRLogger

		if not fileExists(dirname) and not cover_only:
			print("[SerienRecorder] Erstelle Verzeichnis: %s" % dirname)
			SRLogger.writeLog("Erstelle Verzeichnis: ' %s '" % dirname)
			try:
				os.makedirs(dirname)
			except OSError as e:
				SRLogger.writeLog("Fehler beim Erstellen des Verzeichnisses: %s" % e.strerror)
		# if e.errno != 17:
		#	raise

		# Copy cover only if path exists and series sub dir is activated
		if markerType == 0 and fileExists(dirname) and config.plugins.serienRec.seriensubdir.value and config.plugins.serienRec.copyCoverToFolder.value:
			print("[SerienRecorder] Cover soll in Verzeichnis kopiert werden: %s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid))
			if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid)) and not fileExists("%sfolder.jpg" % dirname_serie):
				print("[SerienRecorder] Kopiere Cover in Verzeichnis: %sfolder.jpg" % dirname_serie)
				shutil.copyfile("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid), "%sfolder.jpg" % dirname_serie)
			if config.plugins.serienRec.seasonsubdir.value:
				print("[SerienRecorder] Staffel Unterverzeichnis vorhanden")
				covername = "series"
				if config.plugins.serienRec.copyCoverToFolder.value == "1":
					covername = "folder"

				if fileExists("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid)) and not fileExists("%s%s.jpg" % (dirname, covername)):
					print("[SerienRecorder] Kopiere Cover in Verzeichnis: %s%s.jpg" % (dirname, covername))
					shutil.copyfile("%s%s.jpg" % (config.plugins.serienRec.coverPath.value, serien_fsid), "%s%s.jpg" % (dirname, covername))

	@classmethod
	def checkTuner(cls, check_start, check_end, check_stbRef):
		if not config.plugins.serienRec.selectNoOfTuners.value:
			return True

		cRecords = 1
		lTuner = []
		lTimerStart = {}
		lTimerEnd = {}

		# Aufnahme Tuner braucht CI -1 -> nein, 1 - ja
		from ServiceReference import ServiceReference
		provider_ref = ServiceReference(check_stbRef)
		new_needs_ci_0 = STBHelpers.checkCI(provider_ref.ref, 0)
		new_needs_ci_1 = STBHelpers.checkCI(provider_ref.ref, 1)

		check_stbRef = check_stbRef.split(":")[4:7]

		from .SerienRecorderTimer import serienRecBoxTimer
		timers = serienRecBoxTimer.getTimersTime()
		for name, begin, end, service_ref in timers:
			# print(name, begin, end, service_ref)
			if not ((int(check_end) < int(begin)) or (int(check_start) > int(end))):
				# print("between")
				cRecords += 1

				# vorhandener Timer braucht CI -1 -> nein, 1 - ja
				# provider_ref = ServiceReference(service_ref)
				timer_needs_ci_0 = STBHelpers.checkCI(service_ref.ref, 0)
				timer_needs_ci_1 = STBHelpers.checkCI(service_ref.ref, 1)

				service_ref = str(service_ref).split(":")[4:7]
				# gleicher service
				if str(check_stbRef).lower() == str(service_ref).lower():
					if int(check_start) > int(begin): begin = check_start
					if int(check_end) < int(end): end = check_end
					lTimerStart.update({int(begin): int(end)})
					lTimerEnd.update({int(end): int(begin)})
				else:
					# vorhandener und neuer Timer benötigt ein CI
					if ((timer_needs_ci_0 != -1) or (timer_needs_ci_1 != -1)) and (
							(new_needs_ci_0 != -1) or (new_needs_ci_1 != -1)):
						return False
					# Anzahl der verwendeten Tuner um 1 erhöhen
					if not lTuner.count(service_ref):
						lTuner.append(service_ref)

		if int(check_start) in lTimerStart:
			l = list(lTimerStart.items())
			l.sort(key=lambda x: x[0])
			for each in l:
				if (each[0] <= lTimerStart[int(check_start)]) and (each[1] > lTimerStart[int(check_start)]):
					lTimerStart.update({int(check_start): each[1]})

			if int(check_end) in lTimerEnd:
				l = list(lTimerEnd.items())
				l.sort(key=lambda x: x[0], reverse=True)
				for each in l:
					if (each[0] >= lTimerEnd[int(check_end)]) and (each[1] < lTimerEnd[int(check_end)]):
						lTimerEnd.update({int(check_end): each[1]})

				if lTimerStart[int(check_start)] >= lTimerEnd[int(check_end)]:
					lTuner.append(check_stbRef)

		if lTuner.count(check_stbRef):
			return True
		else:
			return len(lTuner) < int(config.plugins.serienRec.tuner.value)

	@classmethod
	def checkCI(cls, servref=None, cinum=0):
		cifile = "/etc/enigma2/ci%d.xml" % cinum

		if servref is None or not os.path.exists(cifile):
			return -1

		serviceref = servref.toString()
		serviceHandler = eServiceCenter.getInstance()
		info = serviceHandler.info(servref)
		provider = "unknown"
		if info is not None:
			provider = info.getInfoString(servref, iServiceInformation.sProvider)

		sp = serviceref.split(":")
		namespace = ""
		if len(sp) > 6:
			namespace = sp[6]

		f = open(cifile, "r")
		assignments = f.read()
		f.close()
		if assignments.find(serviceref) != -1:
			# print("[AUTOPIN] CI Slot %d assigned to %s" % (cinum+1, serviceref))
			return cinum
		if assignments.find("provider name") == -1:
			return -1
		# service not found, but maybe provider ...
		providerstr = "provider name=\"%s\" dvbnamespace=\"%s\"" % (provider, namespace)
		if assignments.find(providerstr) != -1:
			# print("[AUTOPIN] CI Slot %d assigned to %s via provider %s" % (cinum+1, serviceref, provider))
			return cinum

		return -1


# ----------------------------------------------------------------------------------------------------------------------
#
# PicLoader
#
# ----------------------------------------------------------------------------------------------------------------------

class PicLoader:
	def __init__(self, width, height, sc=None):
		self.picload = ePicLoad()
		if not sc:
			sc = AVSwitch().getFramebufferScale()
		# max width, max height, aspect x, aspect y, cache, quality (0 = simple, 1 = better, 2 = fast), backgroundcolor
		# print("[SerienRecorder] PicLoader::__init__", width, height, sc)
		self.picload.setPara((int(width), int(height), sc[0], sc[1], False, 1, "#ff000000"))

	def load(self, filename):
		#print("[SerienRecorder] PicLoader::load: [%s]" % filename)
		if isDreamOS():
			self.picload.startDecode(filename, False)
		else:
			self.picload.startDecode(filename, 0, 0, False)
		data = self.picload.getData()
		return data

	def destroy(self):
		del self.picload

# ----------------------------------------------------------------------------------------------------------------------
#
# Picon loader
#
# ----------------------------------------------------------------------------------------------------------------------

class PiconLoader:
	def __init__(self):
		self.nameCache = { }

	def getPicon(self, sRef):
		print("[SerienRecorder] PiconLoader::getPicon: [%s]" % sRef)
		if not sRef:
			return None

		piconName, isPiconByServiceRef = self.getPiconName(sRef)
		pngname = self.nameCache.get(piconName, "")
		if pngname == "":
			pngname = self.findPicon(piconName, isPiconByServiceRef)
			if pngname != "":
				self.nameCache[piconName] = pngname
			if pngname == "": # no picon for service found
				pngname = self.nameCache.get("default", "")
				if pngname == "": # no default in cache yet
					pngname = resolveFilename(SCOPE_SKIN, "skin_default/picon_default.png")
					if pngname != "":
						self.nameCache["default"] = pngname
		if fileExists(pngname):
			return pngname
		else:
			return None

	@staticmethod
	def getPiconName(sRef):
		# remove the path and name fields, and replace ':' by '_'
		fields = sRef.split(':', 10)[:10]
		if not fields or 10 > len(fields) > 1:
			return "", False
		pngname = '_'.join(fields)
		if not pngname and not fields[6].endswith("0000"):
			# remove "subnetwork" from namespace
			fields[6] = fields[6][:-4] + "0000"
			pngname = '_'.join(fields)
		if not pngname and fields[0] != '1':
			# fallback to 1 for other reftypes
			fields[0] = '1'
			pngname = '_'.join(fields)
		if not pngname and fields[2] != '1':
			# fallback to 1 for services with different service types
			fields[2] = '1'
			pngname = '_'.join(fields)
		print("[SerienRecorder] PiconLoader::getPiconName: [%s] => [%s]" % (sRef, pngname))
		return pngname, True

	@staticmethod
	def findPicon(piconName, isPiconByServiceRef):
		pngname = "%s%s.png" % (config.plugins.serienRec.piconPath.value, piconName)
		print("[SerienRecorder] PiconLoader::findPicon: [%s]" % pngname)
		if not fileExists(pngname):
			if isPiconByServiceRef and pngname.startswith("4097_"):
				# Try to find with DVB reftype
				pngname = pngname.replace("4097_", "1_")
				print("[SerienRecorder] PiconLoader::findPicon: [%s] (DVB)" % pngname)
			elif not isPiconByServiceRef:
				# Try to normalize the name
				normalizedPiconName = piconName.replace(" ", "").lower()
				pngname = "%s%s.png" % (config.plugins.serienRec.piconPath.value, normalizedPiconName)
				print("[SerienRecorder] PiconLoader::findPicon: [%s] (normalized)" % pngname)
			if not fileExists(pngname):
				pngname = ""
		return pngname

	def piconPathChanged(self, configElement = None):
		self.nameCache.clear()


