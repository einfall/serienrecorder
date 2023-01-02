# -*- coding: utf-8 -*-
from twisted.internet import reactor
from twisted.web import http, resource, server
import threading

from Components.config import config

from Tools.Directories import fileExists

from .SerienRecorderHelpers import decrypt, encrypt, STBHelpers, SRAPIVERSION, SRWEBAPPVERSION, toBinary, toStr, PY2

import json, os, time, re

SERIENRECORDER_WEBINTERFACE_CHANGELOGPATH = '/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/web-data/Changelog.md'

def getApiList(session):
	root = ApiBaseResource()
	childs = []
	childs.append( ('markers', ApiGetMarkersResource() ) )
	childs.append( ('changemarkerstatus', ApiChangeMarkerStatusResource() ) )
	childs.append( ('setmarkerchannels', ApiSetMarkerChannelsResource() ) )
	childs.append( ('markerseasonsettings', ApiGetMarkerSeasonSettingsResource() ) )
	childs.append( ('setmarkerseasonsettings', ApiSetMarkerSeasonSettingsResource() ) )
	childs.append( ('markersettings', ApiGetMarkerSettingsResource() ) )
	childs.append( ('setmarkersettings', ApiSetMarkerSettingsResource() ) )
	childs.append( ('createmarker', ApiCreateMarkerResource() ) )
	childs.append( ('deletemarker', ApiDeleteMarkerResource() ) )
	childs.append( ('settings', ApiGetSettingsResource() ) )
	childs.append( ('setsettings', ApiSetSettingsResource(session)))
	childs.append( ('resetsettings', ApiResetSettingsResource()))
	childs.append( ('cover', ApiGetCoverResource() ) )
	childs.append( ('picon', ApiGetPiconResource() ) )
	childs.append( ('tvdbcover', ApiGetTVDBCoverResource() ) )
	childs.append( ('tvdbcovers', ApiGetTVDBCoversResource() ) )
	childs.append( ('settvdbcover', ApiSetTVDBCoverResource()))
	childs.append( ('settvdbid', ApiSetTVDBIDResource()))
	childs.append( ('transmissions', ApiGetTransmissionsResource() ) )
	childs.append( ('searchseries', ApiSearchSeriesResource() ) )
	childs.append( ('activechannels', ApiGetActiveChannelsResource() ) )
	childs.append( ('channels', ApiGetChannelsResource() ) )
	childs.append( ('boxchannels', ApiGetBoxChannelsResource() ) )
	childs.append( ('changechannelstatus', ApiChangeChannelStatusResource() ) )
	childs.append( ('setchannel', ApiSetChannelResource() ) )
	childs.append( ('removeallchannels', ApiRemoveAllChannelsResource() ) )
	childs.append( ('updatechannels', ApiUpdateChannelsResource() ) )
	childs.append( ('timer', ApiGetTimerResource() ) )
	childs.append( ('markertimer', ApiGetMarkerTimerResource() ) )
	childs.append( ('addtimers', ApiAddTimersResource() ) )
	childs.append( ('removetimer', ApiRemoveTimerResource() ) )
	childs.append( ('removetimerbyseason', ApiRemoveTimerBySeasonResource() ) )
	childs.append( ('removeallremainingtimer', ApiRemoveAllRemainingTimerResource() ) )
	childs.append( ('createtimer', ApiCreateTimerResource() ) )
	childs.append( ('seriesinfo', ApiGetSeriesInfoResource() ) )
	childs.append( ('autocheck', ApiExecuteAutoCheckResource() ) )
	childs.append( ('log', ApiGetLogResource() ) )
	childs.append( ('info', ApiGetInfoResource() ) )
	childs.append( ('getChangelog', ApiGetChangelogResource() ) )
	childs.append( ('removeChangelog', ApiRemoveChangelogResource() ) )
	childs.append( ('checkforupdate', ApiCheckForUpdateResource() ) )
	childs.append( ('installupdate', ApiInstallUpdateResource() ) )

	return ( root, childs )

def addWebInterface(session):
	use_openwebif = False
	if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/OpenWebif/pluginshook.src"):
		use_openwebif = True
	print("[SerienRecorder] addWebInterface for OpenWebif = %s" % str(use_openwebif))
	try:
		from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
		from twisted.web import static
		from twisted.python import util
		#from WebChilds.UploadResource import UploadResource

		# webapi
		(root, childs) = getApiList(session)
		if childs:
			for name, api in childs:
				root.putChild(toBinary(name), api)
		apiSuccessfulAdded = addExternalChild(("serienrecorderapi", root, "SerienRecorder-API", SRAPIVERSION, False))
		if apiSuccessfulAdded is not True:
			apiSuccessfulAdded = addExternalChild(("serienrecorderapi", root, "SerienRecorder-API", SRAPIVERSION))

		print("[SerienRecorder] addExternalChild for API [%s]" % str(apiSuccessfulAdded))

		# webgui
		root = static.File(util.sibpath(__file__, "web-data"))
		print("[SerienRecorder] WebUI root path: %s" % str(root))

		try:
			if use_openwebif or os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/WebInterface/web/external.xml"):
				uiSuccessfulAdded = addExternalChild(("serienrecorderui", root, "SerienRecorder", SRWEBAPPVERSION, True))
				if uiSuccessfulAdded is not True:
					addExternalChild(("serienrecorderui", root, "SerienRecorder", SRWEBAPPVERSION))
			else:
				uiSuccessfulAdded = addExternalChild(("serienrecorderui", root))
		except:
			uiSuccessfulAdded = addExternalChild(("serienrecorderui", root))

		print("[SerienRecorder] addExternalChild for UI [%s]" % str(uiSuccessfulAdded))

	except Exception as e:
		print("[SerienRecorder] Failed to addWebInterface [%s]" % str(e))
		pass

class ApiBaseResource(resource.Resource):
	def render_OPTIONS(self, req):
		print("[SerienRecorder] ApiBaseResource (render_OPTIONS)")
		req.setResponseCode(http.OK)
		req.setHeader('Access-Control-Allow-Origin', '*')
		req.setHeader('Access-Control-Allow-Headers', 'content-type')
		req.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
		req.write('')
		req.finish()
		return server.NOT_DONE_YET

	def returnResult(self, req, status, data):
		print("[SerienRecorder] ApiBaseResource (returnResult)")
		print("[SerienRecorder] URI: [%s] / Args: [%s] / Content: [%s] " % (toStr(req.uri), req.args, toStr(req.content.getvalue())))
		req.setResponseCode(http.OK)
		req.setHeader('Content-type', 'application/json')
		req.setHeader('Access-Control-Allow-Origin', '*')
		req.setHeader('Cache-Control', 'no-cache')
		req.setHeader('X-API-Version', SRAPIVERSION)
		req.setHeader('charset', 'UTF-8')

		return toBinary(json.dumps(
					{
						'status' : status,
						'payload' : data
					},
					sort_keys=True, 
					indent=4, 
					separators=(',', ': ')
				))

class ApiImageResource(resource.Resource):
	def returnResult(self, req, filepath):
		print("[SerienRecorder] ApiImageResource (returnResult)")
		print(filepath)
		req.setResponseCode(http.OK)
		req.setHeader('Access-Control-Allow-Origin', '*')
		req.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
		if filepath.endswith('.jpg'):
			req.setHeader('Content-type', 'image/jpeg')
		else:
			req.setHeader('Content-type', 'image/png')

		with open(filepath, 'rb') as filehandle:
			return filehandle.read()

class ApiBackgroundThread(threading.Thread):
	def __init__(self, req, fnc):
		threading.Thread.__init__(self)
		self.__req = req
		if hasattr(req, 'notifyFinish'):
			req.notifyFinish().addErrback(self.connectionLost)
		self.__stillAlive = True
		self.__fnc = fnc
		self.start()

	def connectionLost(self, err):
		self.__stillAlive = False

	def run(self):
		req = self.__req
		ret = self.__fnc(req)
		if self.__stillAlive and ret != server.NOT_DONE_YET:
			def finishRequest():
				req.write(ret)
				req.finish()
			reactor.callFromThread(finishRequest)

class ApiBackgroundingResource(ApiBaseResource, threading.Thread):
	def render(self, req):
		ApiBackgroundThread(req, self.renderBackground)
		return server.NOT_DONE_YET

	def renderBackground(self, req):
		pass

class ApiGetCoverResource(ApiImageResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetCover")
		print(req.args)

		fs_id = toStr(req.args[toBinary("fsid")][0])
		if config.plugins.serienRec.showCover.value:
			cover_file_path = os.path.join(config.plugins.serienRec.coverPath.value, "%s.jpg" % fs_id)
		else:
			cover_file_path = None

		if config.plugins.serienRec.downloadCover.value and cover_file_path and not fileExists(cover_file_path):
			# Download cover
			from .SerienRecorderSeriesServer import SeriesServer
			try:
				posterURL = SeriesServer().doGetCoverURL(0, fs_id)
				if posterURL:
					import requests
					response = requests.get(posterURL)
					if response.status_code == 200:
						with open(cover_file_path, 'wb') as f:
							f.write(response.content)
				else:
					if config.plugins.serienRec.createPlaceholderCover.value:
						open(cover_file_path, "a").close()
			except:
				if config.plugins.serienRec.createPlaceholderCover.value:
					open(cover_file_path, "a").close()

		if not cover_file_path or not fileExists(cover_file_path) or os.stat(cover_file_path).st_size == 0:
			# Dummy image
			cover_file_path = os.path.join(os.path.dirname(__file__), "images", "1x1#FFFFFF.png")
		return self.returnResult(req, cover_file_path)

	@staticmethod
	def returnFilename(result, filename):
		return filename

class ApiGetPiconResource(ApiImageResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetPicon")
		print(req.args)

		serviceRef = toStr(req.args[toBinary("serviceRef")][0])
		channelName = toStr(req.args[toBinary("channelName")][0])

		piconPath = None
		if config.plugins.serienRec.showPicons.value != "0":
			from .SerienRecorderHelpers import PiconLoader
			# Get picon by reference or by name
			if config.plugins.serienRec.showPicons.value == "1" and serviceRef:
				piconPath = PiconLoader().getPicon(serviceRef)
			elif config.plugins.serienRec.showPicons.value == "2" and channelName:
				piconPath = PiconLoader().getPicon(channelName)

		if not piconPath:
			# Dummy image
			piconPath = os.path.join(os.path.dirname(__file__), "images", "1x1#FFFFFF.png")
		print("[SerienRecorder] ApiGetPiconResource: <%s>" % piconPath)
		return self.returnResult(req, piconPath)

	@staticmethod
	def returnFilename(result, filename):
		return filename

class ApiGetTVDBCoverResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetTVDBCover")
		print(req.args)

		fs_id = toStr(req.args[toBinary("fsid")][0])
		posterURL = None
		if config.plugins.serienRec.downloadCover.value:
			from .SerienRecorderSeriesServer import SeriesServer
			try:
				posterURL = SeriesServer().doGetCoverURL(0, fs_id)
			except:
				posterURL = None

		return self.returnResult(req, True, posterURL)

class ApiGetTVDBCoversResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetTVDBCovers")
		print(req.args)
		wl_id = toStr(req.args[toBinary("wlid")][0])

		from .SerienRecorderSeriesServer import SeriesServer

		data = {}
		posterURLs = None
		if config.plugins.serienRec.downloadCover.value:
			try:
				posterURLs = SeriesServer().getCoverURLs(wl_id)
			except:
				posterURLs = None

		from .SerienRecorderScreenHelpers import EditTVDBID

		data['urls'] = posterURLs
		data['tvdbid'] = SeriesServer().getTVDBID(wl_id)
		data['allowChangeTVDBID'] = EditTVDBID.allowChangeTVDBID()

		return self.returnResult(req, True, data)

class ApiSetTVDBCoverResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetTVDBCover")
		print(req.content.getvalue())
		data = json.loads(req.content.getvalue())

		result = True
		targetPath = "%s%s.jpg" % (config.plugins.serienRec.coverPath.value, data['fsid'])

		import requests
		response = requests.get(data['url'].encode('utf-8'))
		if response.status_code == 200:
			with open(targetPath, 'wb') as f:
				f.write(response.content)
		else:
			result = False
		return self.returnResult(req, True, result)

class ApiSetTVDBIDResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetTVDBID")
		print(req.content.getvalue())
		data = json.loads(req.content.getvalue())

		from .SerienRecorderSeriesServer import SeriesServer
		SeriesServer().setTVDBID(data['wlid'], data['tvdbid'])

		return self.returnResult(req, True, True)

class ApiGetMarkersResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetMarkers")
		print(req.args)

		data = {}
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		from .SerienRecorderMarkerScreen import serienRecMarker
		database = SRDatabase(serienRecDataBaseFilePath)

		data['showCover'] = config.plugins.serienRec.showCover.value
		data['markers'] = []

		numberOfDeactivatedSeries, markerList = serienRecMarker.getMarkerList(database)
		for marker in markerList:
			(ID, serie, wlID, staffeln, sender, AufnahmeVerzeichnis, AnzahlAufnahmen, Vorlaufzeit, Nachlaufzeit, preferredChannel, useAlternativeChannel, SerieAktiviert, info, fsID) = marker

			data['markers'].append( {
					'id': ID,
					'name': serie,
					'wlid': wlID,
					'fsid': fsID,
					'seasons': staffeln.replace('Alle', 'Alle (inkl. Specials)'),
					'channels': sender,
					'recordfolder': AufnahmeVerzeichnis,
					'numberOfRecords': AnzahlAufnahmen,
					'leadtime': Vorlaufzeit,
					'followuptime': Nachlaufzeit,
					'preferredChannel': preferredChannel,
					'useAlternativeChannel': bool(useAlternativeChannel),
					'active': SerieAktiviert,
					'info': info,
					'coverid': int(wlID)
				} )

		return self.returnResult( req, True, data )

class ApiChangeMarkerStatusResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiChangeMarkerStatus")
		print(req.args)

		fs_id = toStr(req.args[toBinary("fsid")][0])
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		database.changeMarkerStatus(fs_id, config.plugins.serienRec.BoxID.value)
		result = True
		return self.returnResult(req, result, None)

class ApiCreateMarkerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiCreateMarker")
		print(req.content.getvalue())

		result = False
		data = json.loads(req.content.getvalue())

		if 'fsid' in data:
			from .SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			if serienRecSearchResultScreen.createMarker(data['wlid'], data['name'], data['info'], data['fsid']):
				from .SerienRecorder import getCover
				getCover(None, data['name'], data['fsid'], False, True)
				result = True
		return self.returnResult(req, result, None)

class ApiDeleteMarkerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiDeleteMarker")
		print(req.content.getvalue())

		result = False
		data = json.loads(req.content.getvalue())
		if 'fsid' in data:
			from .SerienRecorderMarkerScreen import serienRecMarker
			serienRecMarker.doRemoveSerienMarker(data['fsid'], data['name'], data['info'], data['removeTimer'])
			result = True
		return self.returnResult(req, result, None)

class ApiSetMarkerChannelsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetMarkerChannels")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		channels = []
		if 'fsid' in data:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			database.removeAllMarkerChannels(data['fsid'])
			markerID = database.getMarkerID(data['fsid'])

			allChannels = 0
			channelData = []
			for channel in data['channels']:
				if channel == 'Alle':
					channelData = []
					break
				else:
					channelData.append((markerID, channel))

			if len(data['channels']) == 0 or len(channelData) == 0:
				allChannels = 1
			else:
				database.setMarkerChannels(channelData)

			database.setAllChannelsToMarker(data['fsid'], allChannels)

			if allChannels:
				channels = ['Alle',]
			else:
				channels = database.getMarkerChannels(data['fsid'], False)
			channels = str(channels).replace("[", "").replace("]", "").replace("'", "").replace('"', "")

		return self.returnResult(req, True, channels)

class ApiGetMarkerSeasonSettingsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetMarkerSeasonSettings")
		print(req.args)

		fs_id = toStr(req.args[toBinary("fsid")][0])

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		(ID, allSeasonsFrom, fromEpisode, timerForSpecials) = database.getMarkerSeasonSettings(fs_id)
		markerSeasons = database.getAllowedSeasons(ID, allSeasonsFrom)
		data = {
			'id' : ID,
			'allSeasonsFrom' : allSeasonsFrom,
			'fromEpisode' : fromEpisode,
			'timerForSpecials' : timerForSpecials,
			'markerSeasons': markerSeasons,
			'maxSeasons' : config.plugins.serienRec.max_season.value
		}

		return self.returnResult(req, True, data)

class ApiSetMarkerSeasonSettingsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetMarkerSeasonSettings")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		results = []
		if 'fsid' in data:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			database.removeAllMarkerSeasons(data['fsid'])

			AbEpisode = int(data['episode'])
			TimerForSpecials = 0
			AlleStaffelnAb = 999999

			if 'Manuell' in data['options']:
				AlleStaffelnAb = -2
				AbEpisode = 0
				TimerForSpecials = 0
				results = ['Manuell', ]
			elif 'Alle (inkl. Specials)' in data['options']:
				AlleStaffelnAb = 0
				AbEpisode = 0
				TimerForSpecials = 0
				results = ['Alle (inkl. Specials)', ]
			elif 'Specials' in data['options']:
				TimerForSpecials = 1
				results.insert(0, 'Specials')

			if 'Staffeln ab' in data['options']:
				AlleStaffelnAb = max(data['seasons'])

			for season in data['seasons']:
				if season != AlleStaffelnAb:
					database.setMarkerSeason(data['markerid'], season)
					results.append(season)

			if len(data['seasons']) == 0 and len(data['options']) == 0 and data['episode'] == 0:
				AlleStaffelnAb = -2     # Manuell
				AbEpisode = 0

			if AbEpisode > 0:
				results.insert(0, '0 ab E%s' % AbEpisode)
			if 0 < AlleStaffelnAb < 999999:
				results.append('ab %s' % AlleStaffelnAb)

			database.updateMarkerSeasonsSettings(data['fsid'], AlleStaffelnAb, AbEpisode, TimerForSpecials)

		results = ', '.join(str(staffel) for staffel in results)
		return self.returnResult(req, True, results)

class ApiGetMarkerSettingsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetMarkerSettings")
		print(req.args)

		marker_id = toStr(req.args[toBinary("markerid")][0])
		from .SerienRecorderHelpers import hasAutoAdjust
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath, VPSPluginAvailable
		database = SRDatabase(serienRecDataBaseFilePath)

		(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon,
		 AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase, updateFromEPG,
		 skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer, forceRecording, timerSeriesName) = database.getMarkerSettings(marker_id)

		if not AufnahmeVerzeichnis:
			AufnahmeVerzeichnis = ""

		if not epgSeriesName:
			epgSeriesName = ""

		if not timerSeriesName:
			timerSeriesName = ""

		if str(Vorlaufzeit).isdigit():
			enable_lead_time = True
		else:
			Vorlaufzeit = config.plugins.serienRec.margin_before.value
			enable_lead_time = False

		if str(Nachlaufzeit).isdigit():
			enable_followup_time = True
		else:
			Nachlaufzeit = config.plugins.serienRec.margin_after.value
			enable_followup_time = False

		if str(AnzahlWiederholungen).isdigit():
			enable_NoOfRecords = True
		else:
			AnzahlWiederholungen = config.plugins.serienRec.NoOfRecords.value
			enable_NoOfRecords = False

		if str(AufnahmezeitVon).isdigit():
			t = time.localtime(int(AufnahmezeitVon) * 60 + time.timezone)
			AufnahmezeitVon = "%d:%d:00" % (t.tm_hour, t.tm_min)
			enable_fromTime = True
		else:
			t = time.localtime(((config.plugins.serienRec.globalFromTime.value[0] * 60) + config.plugins.serienRec.globalFromTime.value[1]) * 60 + time.timezone)
			AufnahmezeitVon = "%d:%d:00" % (t.tm_hour, t.tm_min)
			enable_fromTime = False

		if str(AufnahmezeitBis).isdigit():
			t = time.localtime(int(AufnahmezeitBis) * 60 + time.timezone)
			AufnahmezeitBis = "%d:%d:00" % (t.tm_hour, t.tm_min)
			enable_toTime = True
		else:
			t = time.localtime(((config.plugins.serienRec.globalToTime.value[0] * 60) + config.plugins.serienRec.globalToTime.value[1]) * 60 + time.timezone)
			AufnahmezeitBis = "%d:%d:00" % (t.tm_hour, t.tm_min)
			enable_toTime = False

		if str(vps).isdigit():
			override_vps = True
			enable_vps = bool(vps & 0x1)
			enable_vps_savemode = bool(vps & 0x2)
		else:
			override_vps = False
			enable_vps = False
			enable_vps_savemode = False

		if str(addToDatabase).isdigit():
			addToDatabase = bool(addToDatabase)
		else:
			addToDatabase = True

		if str(updateFromEPG).isdigit():
			updateFromEPG = bool(updateFromEPG)
			enable_updateFromEPG = True
		else:
			updateFromEPG = config.plugins.serienRec.eventid.value
			enable_updateFromEPG = False

		if str(forceRecording).isdigit():
			forceRecording = bool(forceRecording)
			enable_forceRecording = True
		else:
			forceRecording = config.plugins.serienRec.forceRecording.value
			enable_forceRecording = False

		if str(kindOfTimer).isdigit():
			kindOfTimer = int(kindOfTimer)
			enable_kindOfTimer = True
		else:
			kindOfTimer = int(config.plugins.serienRec.kindOfTimer.value)
			enable_kindOfTimer = False

		if str(skipSeriesServer).isdigit():
			skipSeriesServer = bool(skipSeriesServer)
			enable_skipSeriesServer = True
		else:
			skipSeriesServer = config.plugins.serienRec.tvplaner_skipSerienServer.value
			enable_skipSeriesServer = False

		if str(autoAdjust).isdigit():
			autoAdjust = bool(autoAdjust)
			enable_autoAdjust = True
		else:
			autoAdjust = False
			enable_autoAdjust = False

		if str(excludedWeekdays).isdigit():
			enable_excludedWeekdays = True
			weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
			excludedWeekdaysList = []
			for i in range(6, -1, -1):
				if excludedWeekdays >> i & 1:
					excludedWeekdaysList.append(weekdays[i])
		else:
			enable_excludedWeekdays = False
			excludedWeekdaysList = []

		# tags
		if tags is None or len(tags) == 0:
			serienmarker_tags = []
		else:
			# if tags.startswith('(lp1'):
			# 	if PY2:
			# 		import cPickle as pickle
			# 		serienmarker_tags = pickle.loads(tags)
			# 	else:
			# 		import pickle
			# 		serienmarker_tags = pickle.loads(toBinary(tags), encoding='utf-8')
			# else:
			# 	serienmarker_tags = json.loads(tags)
			from .SerienRecorderHelpers import readTags
			serienmarker_tags = readTags(tags)

		# Load all tags from file
		try:
			file = open("/etc/enigma2/movietags")
			all_tags = [x.rstrip() for x in file]
			while "" in all_tags:
				all_tags.remove("")
			file.close()
		except IOError as ioe:
			all_tags = []

		data = {
			'recordDir': {
				'global': config.movielist.videodirs.value,
				'enabled': len(AufnahmeVerzeichnis) > 0,
				'value': AufnahmeVerzeichnis
			},
			'seasonDir': {
				'global': config.plugins.serienRec.seasonsubdir.value,
				'value': Staffelverzeichnis
			},
			'epgSeriesName': {
				'enabled': len(epgSeriesName) > 0,
				'value': epgSeriesName
			},
			'timerSeriesName': {
				'enabled': len(timerSeriesName) > 0,
				'value': timerSeriesName
			},
			'leadTime': {
				'enabled': enable_lead_time,
				'value': Vorlaufzeit
			},
			'followupTime': {
				'enabled': enable_followup_time,
				'value': Nachlaufzeit
			},
			'numberOfRecordings': {
				'enabled': enable_NoOfRecords,
				'value': AnzahlWiederholungen
			},
			'recordFromTime': {
				'enabled': enable_fromTime,
				'value': str(AufnahmezeitVon)
			},
			'recordToTime': {
				'enabled': enable_toTime,
				'value': str(AufnahmezeitBis)
			},
			'preferredChannel': preferredChannel,
			'useAlternativeChannel': {
				'global': config.plugins.serienRec.useAlternativeChannel.value,
				'value': useAlternativeChannel
			},
			'vps': {
				'available': VPSPluginAvailable,
				'enabled': override_vps,
				'value': enable_vps,
				'savemode': enable_vps_savemode
			},
			'excludedWeekdays': {
				'enabled': enable_excludedWeekdays,
				'value': excludedWeekdaysList
			},
			'tags': serienmarker_tags,
			'allTags' : all_tags,
			'addToDatabase': addToDatabase,
			'updateFromEPG': {
				'available': config.plugins.serienRec.eventid.value,
				'enabled': enable_updateFromEPG,
				'value': updateFromEPG
			},
			'kindOfTimer': {
				'enabled': enable_kindOfTimer,
				'value': kindOfTimer
			},
			'skipSeriesServer': {
				'available': config.plugins.serienRec.tvplaner.value,
				'enabled': enable_skipSeriesServer,
				'value': skipSeriesServer
			},
			'autoAdjust': {
				'available': hasAutoAdjust(),
				'enabled': enable_autoAdjust,
				'value': autoAdjust
			},
			'forceRecording': {
				'enabled': enable_forceRecording,
				'value': forceRecording
			}
		}

		return self.returnResult(req, True, data)

class ApiSetMarkerSettingsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetMarkerSettings")
		print(req.content.getvalue)

		data = json.loads(req.content.getvalue())
		results = []
		if 'markerid' in data:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)

			if not data['settings']['leadTime']['enabled']:
				Vorlaufzeit = None
			else:
				Vorlaufzeit = data['settings']['leadTime']['value']

			if not data['settings']['followupTime']['enabled']:
				Nachlaufzeit = None
			else:
				Nachlaufzeit = data['settings']['followupTime']['value']

			if not data['settings']['numberOfRecordings']['enabled']:
				AnzahlWiederholungen = None
			else:
				AnzahlWiederholungen = data['settings']['numberOfRecordings']['value']

			if not data['settings']['recordFromTime']['enabled']:
				AufnahmezeitVon = None
			else:
				fromTime = time.strptime(data['settings']['recordFromTime']['value'], '%H:%M:%S')
				AufnahmezeitVon = (fromTime.tm_hour * 60) + fromTime.tm_min

			if not data['settings']['recordToTime']['enabled']:
				AufnahmezeitBis = None
			else:
				toTime = time.strptime(data['settings']['recordToTime']['value'], '%H:%M:%S')
				AufnahmezeitBis = (toTime.tm_hour * 60) + toTime.tm_min

			if not data['settings']['updateFromEPG']['enabled']:
				updateFromEPG = None
			else:
				updateFromEPG = data['settings']['updateFromEPG']['value']

			if not data['settings']['forceRecording']['enabled']:
				forceRecording = None
			else:
				forceRecording = data['settings']['forceRecording']['value']

			if not data['settings']['kindOfTimer']['enabled']:
				kindOfTimer = None
			else:
				kindOfTimer = data['settings']['kindOfTimer']['value']

			if not data['settings']['skipSeriesServer']['enabled']:
				skipSeriesServer = None
			else:
				skipSeriesServer = data['settings']['skipSeriesServer']['value']

			if not data['settings']['vps']['enabled']:
				vpsSettings = None
			else:
				vpsSettings = (int(data['settings']['vps']['savemode']) << 1) + int(data['settings']['vps']['value'])

			if not data['settings']['autoAdjust']['enabled']:
				autoAdjust = None
			else:
				autoAdjust = data['settings']['autoAdjust']['value']

			if (not data['settings']['recordDir']['enabled']) or (data['settings']['recordDir']['value'] == ""):
				AufnahmeVerzeichnis = None
				Staffelverzeichnis = -1
			else:
				AufnahmeVerzeichnis = data['settings']['recordDir']['value']
				Staffelverzeichnis = data['settings']['seasonDir']['value']

			if (not data['settings']['epgSeriesName']['enabled']) or (data['settings']['epgSeriesName']['value'] == ""):
				epgSeriesName = None
			else:
				epgSeriesName = data['settings']['epgSeriesName']['value']

			if (not data['settings']['timerSeriesName']['enabled']) or (data['settings']['timerSeriesName']['value'] == ""):
				timerSeriesName = None
			else:
				timerSeriesName = data['settings']['timerSeriesName']['value']

			if not data['settings']['excludedWeekdays']['enabled']:
				excludedWeekdays = None
			else:
				weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
				excludedWeekdays = 0
				for weekday in data['settings']['excludedWeekdays']['value']:
					excludedWeekdays |= 1 << weekdays.index(weekday)

			if len(data['settings']['tags']) == 0:
				tags = ""
			else:
				tags = json.dumps(data['settings']['tags'])

			database.setMarkerSettings(int(data['markerid']),
			                           (AufnahmeVerzeichnis, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen,
			                           AufnahmezeitVon, AufnahmezeitBis, int(data['settings']['preferredChannel']), int(data['settings']['useAlternativeChannel']['value']),
			                           vpsSettings, excludedWeekdays, tags, int(data['settings']['addToDatabase']), updateFromEPG, skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer, forceRecording, timerSeriesName))

			results = {
				'recordfolder': AufnahmeVerzeichnis if AufnahmeVerzeichnis else config.plugins.serienRec.savetopath.value,
				'numberOfRecords': data['settings']['numberOfRecordings']['value'] if data['settings']['numberOfRecordings']['value'] else config.plugins.serienRec.NoOfRecords,
				'leadtime': data['settings']['leadTime']['value'] if data['settings']['leadTime']['value'] else config.plugins.serienRec.margin_before,
				'followuptime': data['settings']['followupTime']['value'] if data['settings']['followupTime']['value'] else config.plugins.serienRec.margin_after,
				'preferredChannel': int(data['settings']['preferredChannel']),
				'useAlternativeChannel': bool(data['settings']['useAlternativeChannel']['value'])
			}

		return self.returnResult(req, True, results)

class ApiGetSettingsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetSettings")
		print(req.args)
		try:
			from Tools.HardwareInfoVu import HardwareInfoVu
			is_vu_plus = True
		except:
			is_vu_plus = False

		from .SerienRecorderPatterns import readTimerPatterns
		timer_patterns = readTimerPatterns()
		pattern_title_choices = timer_patterns
		pattern_description_choices = timer_patterns

		boxBouquets = STBHelpers.getTVBouquets()
		if len(boxBouquets) == 0:
			config.plugins.serienRec.selectBouquets.value = False

		from .SerienRecorderSetupScreen import getSRSkins
		skins = getSRSkins()

		from .SerienRecorderHelpers import getKindOfTimerChoices
		kindOfTimerChoices = getKindOfTimerChoices()

		data = {
			'system' : {
				'changed' : False,
				'boxid': config.plugins.serienRec.BoxID.value,
				'activateNewOnThisSTBOnly': config.plugins.serienRec.activateNewOnThisSTBOnly.value,
				'savetopath': config.plugins.serienRec.savetopath.value,
				'seriensubdir': config.plugins.serienRec.seriensubdir.value,
				'seriensubdirwithyear': config.plugins.serienRec.seriensubdirwithyear.value,
				'seasonsubdir': config.plugins.serienRec.seasonsubdir.value,
				'seasonsubdirnumerlength': config.plugins.serienRec.seasonsubdirnumerlength.value,
				'seasonsubdirfillchar': config.plugins.serienRec.seasonsubdirfillchar.value,
				'autoupdate': config.plugins.serienRec.Autoupdate.value,
				'databasePath': config.plugins.serienRec.databasePath.value,
				'autoBackup': config.plugins.serienRec.AutoBackup.value,
				'backupAtManualCheck': config.plugins.serienRec.backupAtManualCheck.value,
				'backupPath': config.plugins.serienRec.BackupPath.value,
				'deleteBackupFilesOlderThan': config.plugins.serienRec.deleteBackupFilesOlderThan.value,
				'createCompressedBackup' : config.plugins.serienRec.createCompressedBackup.value,
				'videoDirs': config.movielist.videodirs.value,
			},
			'autocheck' : {
				'changed' : False,
				'isVUPlus' : is_vu_plus,
				'type' : config.plugins.serienRec.autochecktype.value,
				'deltime' : "%s:%s" % (str(config.plugins.serienRec.deltime.value[0]).zfill(2), str(config.plugins.serienRec.deltime.value[1]).zfill(2)),
				'maxDelayForAutoCheck' : config.plugins.serienRec.maxDelayForAutocheck.value,
				'checkfordays' : config.plugins.serienRec.checkfordays.value,
				'globalFromTime' : "%s:%s" % (str(config.plugins.serienRec.globalFromTime.value[0]).zfill(2), str(config.plugins.serienRec.globalFromTime.value[1]).zfill(2)),
				'globalToTime' : "%s:%s" % (str(config.plugins.serienRec.globalToTime.value[0]).zfill(2), str(config.plugins.serienRec.globalToTime.value[1]).zfill(2)),
				'eventid' : config.plugins.serienRec.eventid.value,
				'epgTimeSpan': config.plugins.serienRec.epgTimeSpan.value,
				'forceRecording' : config.plugins.serienRec.forceRecording.value,
				'timeSpanForRegularTimer' : config.plugins.serienRec.TimeSpanForRegularTimer.value,
				'noOfRecords' : config.plugins.serienRec.NoOfRecords.value,
				'selectNoOfTuners': config.plugins.serienRec.selectNoOfTuners.value,
				'tuner' : config.plugins.serienRec.tuner.value,
				'wakeUpDSB' : config.plugins.serienRec.wakeUpDSB.value,
				'afterAutoCheck': config.plugins.serienRec.afterAutocheck.value,
				'dsbTimeout' : config.plugins.serienRec.DSBTimeout.value,
			},
			'tvplaner' : {
				'changed' : False,
				'enabled' : config.plugins.serienRec.tvplaner.value,
				'server' : config.plugins.serienRec.imap_server.value,
				'ssl' : config.plugins.serienRec.imap_server_ssl.value,
				'port' : config.plugins.serienRec.imap_server_port.value,
				'login': decrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
				'password': config.plugins.serienRec.imap_password_hidden.value,
				'mailbox' : config.plugins.serienRec.imap_mailbox.value,
				'mailSubject' : config.plugins.serienRec.imap_mail_subject.value,
				'mailAge' : config.plugins.serienRec.imap_mail_age.value,
				'fullCheck' : config.plugins.serienRec.tvplaner_full_check.value,
				'skipSerienServer' : config.plugins.serienRec.tvplaner_skipSerienServer.value,
				'series' : config.plugins.serienRec.tvplaner_series.value,
				'seriesActiveSTB' : config.plugins.serienRec.tvplaner_series_activeSTB.value,
				'movies' : config.plugins.serienRec.tvplaner_movies.value,
				'moviesActiveSTB' : config.plugins.serienRec.tvplaner_movies_activeSTB.value,
				'moviesFilepath' : config.plugins.serienRec.tvplaner_movies_filepath.value,
				'moviesCreateSubdir' : config.plugins.serienRec.tvplaner_movies_createsubdir.value,
				'videoDirs': config.movielist.videodirs.value,
			},
			'timer' : {
				'changed' : False,
				'kindOfTimer' : config.plugins.serienRec.kindOfTimer.value,
				'afterEvent' : config.plugins.serienRec.afterEvent.value,
				'marginBefore' : config.plugins.serienRec.margin_before.value,
				'marginAfter' : config.plugins.serienRec.margin_after.value,
				'timerName' : config.plugins.serienRec.TimerName.value,
				'timerNameOptions' : pattern_title_choices,
				'timerDescription' : config.plugins.serienRec.TimerDescription.value,
				'timerDescriptionOptions' : pattern_description_choices,
				'forceManualRecording' : config.plugins.serienRec.forceManualRecording.value,
				'forceBookmarkRecording' : config.plugins.serienRec.forceBookmarkRecording.value,
				'splitEventTimer' : config.plugins.serienRec.splitEventTimer.value,
				'splitEventTimerCompareTitle' : config.plugins.serienRec.splitEventTimerCompareTitle.value,
				'addSingleTimerForEvent' : config.plugins.serienRec.addSingleTimersForEvent.value,
				'selectBouquets' : config.plugins.serienRec.selectBouquets.value,
				'mainBouquet' : config.plugins.serienRec.MainBouquet.value,
				'alternativeBouquet' : config.plugins.serienRec.AlternativeBouquet.value,
				'useAlternativeChannel' : config.plugins.serienRec.useAlternativeChannel.value,
				'preferMainBouquet' : config.plugins.serienRec.preferMainBouquet.value,
				'boxBouquets' : [item[1] for item in boxBouquets],
				'kindOfTimerChoices' : kindOfTimerChoices
			},
			'optimization': {
				'changed' : False,
				'intensiveTimerSearch' : config.plugins.serienRec.intensiveTimersuche.value,
				'searchRecording' : config.plugins.serienRec.sucheAufnahme.value
			},
			'gui' : {
				'changed' : False,
				'skins' : skins,
				'skinType' : config.plugins.serienRec.SkinType.value,
				'showAllButtons' : config.plugins.serienRec.showAllButtons.value,
				'displayRefreshRate' : config.plugins.serienRec.DisplayRefreshRate.value,
				'firstScreen' : config.plugins.serienRec.firstscreen.value,
				'showPicons' : config.plugins.serienRec.showPicons.value,
				'piconPath' : config.plugins.serienRec.piconPath.value,
				'downloadCover' : config.plugins.serienRec.downloadCover.value,
				'coverPath' : config.plugins.serienRec.coverPath.value,
				'showCover' : config.plugins.serienRec.showCover.value,
				'createPlaceholderCover' : config.plugins.serienRec.createPlaceholderCover.value,
				'refreshPlaceholderCover' : config.plugins.serienRec.refreshPlaceholderCover.value,
				'copyCoverToFolder' : config.plugins.serienRec.copyCoverToFolder.value,
				'listFontsize' : config.plugins.serienRec.listFontsize.value,
				'markerColumnWidth' : config.plugins.serienRec.markerColumnWidth.value,
				'markerNameInset' : config.plugins.serienRec.markerNameInset.value,
				'seasonFilter' : config.plugins.serienRec.seasonFilter.value,
				'timerFilter' : config.plugins.serienRec.timerFilter.value,
				'markerSort' : config.plugins.serienRec.markerSort.value,
				'maxSeason' : config.plugins.serienRec.max_season.value,
				'openMarkerScreen' : config.plugins.serienRec.openMarkerScreen.value,
				'confirmOnDelete' : config.plugins.serienRec.confirmOnDelete.value,
				'alphaSortBoxChannels' : config.plugins.serienRec.alphaSortBoxChannels.value,
			},
			'notification' : {
				'changed' : False,
				'showNotification' : config.plugins.serienRec.showNotification.value,
				'showMessageOnConflicts' : config.plugins.serienRec.showMessageOnConflicts.value,
				'showMessageOnTVPlanerError' : config.plugins.serienRec.showMessageOnTVPlanerError.value,
				'showMessageOnEventNotFound' : config.plugins.serienRec.showMessageOnEventNotFound.value,
				'showMessageTimeout' : config.plugins.serienRec.showMessageTimeout.value,
				'channelUpdateNotification' : config.plugins.serienRec.channelUpdateNotification.value,
			},
			'logging' : {
				'changed' : False,
				'logFilePath' : config.plugins.serienRec.LogFilePath.value,
				'longLogFilename' : config.plugins.serienRec.longLogFileName.value,
				'deleteLogFilesOlderThan' : config.plugins.serienRec.deleteLogFilesOlderThan.value,
				'writeLog' : config.plugins.serienRec.writeLog.value,
				'writeLogVersion' : config.plugins.serienRec.writeLogVersion.value,
				'writeLogChannels' : config.plugins.serienRec.writeLogChannels.value,
				'writeLogAllowedEpisodes' : config.plugins.serienRec.writeLogAllowedEpisodes.value,
				'writeLogAdded' : config.plugins.serienRec.writeLogAdded.value,
				'writeLogDisk' : config.plugins.serienRec.writeLogDisk.value,
				'writeLogTimeRange' : config.plugins.serienRec.writeLogTimeRange.value,
				'writeLogTimeLimit' : config.plugins.serienRec.writeLogTimeLimit.value,
				'writeLogTimerDebug' : config.plugins.serienRec.writeLogTimerDebug.value,
				'tvplaner_backupHTML' : config.plugins.serienRec.tvplaner_backupHTML.value,
				'logScrollLast' : config.plugins.serienRec.logScrollLast.value,
				'logWrapAround' : config.plugins.serienRec.logWrapAround.value,
			}
		}

		return self.returnResult(req, True, data)

class ApiSetSettingsResource(ApiBaseResource):
	def __init__(self, session):
		self.session = session

	def render_POST(self, req):
		print("[SerienRecorder] ApiSetSettings")
		print(req)

		data = json.loads(req.content.getvalue())

		# System
		if 'system' in data and data['system']['changed']:
			config.plugins.serienRec.BoxID.value = data['system']['boxid']
			config.plugins.serienRec.activateNewOnThisSTBOnly.value = data['system']['activateNewOnThisSTBOnly']
			config.plugins.serienRec.savetopath.value = data['system']['savetopath']
			config.plugins.serienRec.seriensubdir.value = data['system']['seriensubdir']
			config.plugins.serienRec.seriensubdirwithyear.value = data['system']['seriensubdirwithyear']
			config.plugins.serienRec.seasonsubdir.value = data['system']['seasonsubdir']
			config.plugins.serienRec.seasonsubdirnumerlength.value = data['system']['seasonsubdirnumerlength']
			config.plugins.serienRec.seasonsubdirfillchar.value = data['system']['seasonsubdirfillchar']
			config.plugins.serienRec.Autoupdate.value = data['system']['autoupdate']
			config.plugins.serienRec.databasePath.value = data['system']['databasePath']
			config.plugins.serienRec.AutoBackup.value = data['system']['autoBackup']
			config.plugins.serienRec.backupAtManualCheck.value = data['system']['backupAtManualCheck']
			config.plugins.serienRec.BackupPath.value = data['system']['backupPath']
			config.plugins.serienRec.deleteBackupFilesOlderThan.value = data['system']['deleteBackupFilesOlderThan']
			config.plugins.serienRec.createCompressedBackup.value = data['system']['createCompressedBackup']

		if 'autocheck' in data and data['autocheck']['changed']:
			config.plugins.serienRec.autochecktype.value = data['autocheck']['type']
			config.plugins.serienRec.deltime.value = [int(x) for x in data['autocheck']['deltime'].split(':')]
			config.plugins.serienRec.maxDelayForAutocheck.value = data['autocheck']['maxDelayForAutoCheck']
			config.plugins.serienRec.checkfordays.value = data['autocheck']['checkfordays']
			config.plugins.serienRec.globalFromTime.value = [int(x) for x in data['autocheck']['globalFromTime'].split(':')]
			config.plugins.serienRec.globalToTime.value = [int(x) for x in data['autocheck']['globalToTime'].split(':')]
			config.plugins.serienRec.eventid.value = data['autocheck']['eventid']
			config.plugins.serienRec.epgTimeSpan.value = data['autocheck']['epgTimeSpan']
			config.plugins.serienRec.forceRecording.value = data['autocheck']['forceRecording']
			config.plugins.serienRec.TimeSpanForRegularTimer.value = data['autocheck']['timeSpanForRegularTimer']
			config.plugins.serienRec.NoOfRecords.value = data['autocheck']['noOfRecords']
			config.plugins.serienRec.selectNoOfTuners.value = data['autocheck']['selectNoOfTuners']
			config.plugins.serienRec.tuner.value = data['autocheck']['tuner']
			config.plugins.serienRec.wakeUpDSB.value = data['autocheck']['wakeUpDSB']
			config.plugins.serienRec.afterAutocheck.value = data['autocheck']['afterAutoCheck']
			config.plugins.serienRec.DSBTimeout.value = data['autocheck']['dsbTimeout']

		if 'tvplaner' in data and data['tvplaner']['changed']:
			config.plugins.serienRec.tvplaner.value = data['tvplaner']['enabled']
			config.plugins.serienRec.imap_server.value = data['tvplaner']['server']
			config.plugins.serienRec.imap_server_ssl.value = data['tvplaner']['ssl']
			config.plugins.serienRec.imap_server_port.value = data['tvplaner']['port']
			config.plugins.serienRec.imap_login_hidden.value = encrypt(STBHelpers.getmac("eth0"), data['tvplaner']['login'])
			config.plugins.serienRec.imap_login.value = "*"
			if config.plugins.serienRec.imap_password_hidden.value != data['tvplaner']['password']:
				config.plugins.serienRec.imap_password_hidden.value = encrypt(STBHelpers.getmac("eth0"), data['tvplaner']['password'])
			config.plugins.serienRec.imap_password.value = "*"
			config.plugins.serienRec.imap_mailbox.value = data['tvplaner']['mailbox']
			config.plugins.serienRec.imap_mail_subject.value = data['tvplaner']['mailSubject']
			config.plugins.serienRec.imap_mail_age.value = data['tvplaner']['mailAge']
			config.plugins.serienRec.tvplaner_full_check.value = data['tvplaner']['fullCheck']
			config.plugins.serienRec.tvplaner_skipSerienServer.value = data['tvplaner']['skipSerienServer']
			config.plugins.serienRec.tvplaner_series.value = data['tvplaner']['series']
			config.plugins.serienRec.tvplaner_series_activeSTB.value = data['tvplaner']['seriesActiveSTB']
			config.plugins.serienRec.tvplaner_movies.value = data['tvplaner']['movies']
			config.plugins.serienRec.tvplaner_movies_activeSTB.value = data['tvplaner']['moviesActiveSTB']
			config.plugins.serienRec.tvplaner_movies_filepath.value = data['tvplaner']['moviesFilepath']
			config.plugins.serienRec.tvplaner_movies_createsubdir.value = data['tvplaner']['moviesCreateSubdir']

		if 'timer' in data and data['timer']['changed']:
			config.plugins.serienRec.kindOfTimer.value = data['timer']['kindOfTimer']
			config.plugins.serienRec.afterEvent.value = data['timer']['afterEvent']
			config.plugins.serienRec.margin_before.value = data['timer']['marginBefore']
			config.plugins.serienRec.margin_after.value = data['timer']['marginAfter']
			config.plugins.serienRec.TimerName.value = data['timer']['timerName']
			config.plugins.serienRec.TimerDescription.value = data['timer']['timerDescription']
			config.plugins.serienRec.forceManualRecording.value = data['timer']['forceManualRecording']
			config.plugins.serienRec.forceBookmarkRecording.value = data['timer']['forceBookmarkRecording']
			config.plugins.serienRec.splitEventTimer.value = data['timer']['splitEventTimer']
			config.plugins.serienRec.splitEventTimerCompareTitle.value = data['timer']['splitEventTimerCompareTitle']
			config.plugins.serienRec.addSingleTimersForEvent.value = data['timer']['addSingleTimerForEvent']
			config.plugins.serienRec.selectBouquets.value = data['timer']['selectBouquets']
			config.plugins.serienRec.MainBouquet.value = data['timer']['mainBouquet']
			config.plugins.serienRec.AlternativeBouquet.value = data['timer']['alternativeBouquet']
			config.plugins.serienRec.useAlternativeChannel.value = data['timer']['useAlternativeChannel']
			config.plugins.serienRec.preferMainBouquet.value = data['timer']['preferMainBouquet']

		if 'optimization' in data and data['optimization']['changed']:
			config.plugins.serienRec.intensiveTimersuche.value = data['optimization']['intensiveTimerSearch']
			config.plugins.serienRec.sucheAufnahme.value = data['optimization']['searchRecording']

		if 'gui' in data and data['gui']['changed']:
			config.plugins.serienRec.SkinType.value = data['gui']['skinType']
			config.plugins.serienRec.showAllButtons.value = data['gui']['showAllButtons']
			config.plugins.serienRec.DisplayRefreshRate.value = data['gui']['displayRefreshRate']
			config.plugins.serienRec.firstscreen.value = data['gui']['firstScreen']
			config.plugins.serienRec.showPicons.value = data['gui']['showPicons']
			config.plugins.serienRec.piconPath.value = data['gui']['piconPath']
			config.plugins.serienRec.downloadCover.value = data['gui']['downloadCover']
			config.plugins.serienRec.coverPath.value = data['gui']['coverPath']
			config.plugins.serienRec.showCover.value = data['gui']['showCover']
			config.plugins.serienRec.createPlaceholderCover.value = data['gui']['createPlaceholderCover']
			config.plugins.serienRec.refreshPlaceholderCover.value = data['gui']['refreshPlaceholderCover']
			config.plugins.serienRec.copyCoverToFolder.value = data['gui']['copyCoverToFolder']
			config.plugins.serienRec.listFontsize.value = data['gui']['listFontsize']
			config.plugins.serienRec.markerColumnWidth.value = data['gui']['markerColumnWidth']
			config.plugins.serienRec.markerNameInset.value = data['gui']['markerNameInset']
			config.plugins.serienRec.seasonFilter.value = data['gui']['seasonFilter']
			config.plugins.serienRec.timerFilter.value = data['gui']['timerFilter']
			config.plugins.serienRec.markerSort.value = data['gui']['markerSort']
			config.plugins.serienRec.max_season.value = data['gui']['maxSeason']
			config.plugins.serienRec.openMarkerScreen.value = data['gui']['openMarkerScreen']
			config.plugins.serienRec.confirmOnDelete.value = data['gui']['confirmOnDelete']
			config.plugins.serienRec.alphaSortBoxChannels.value = data['gui']['alphaSortBoxChannels']

		if 'notification' in data and data['notification']['changed']:
			config.plugins.serienRec.showNotification.value = data['notification']['showNotification']
			config.plugins.serienRec.showMessageOnConflicts.value = data['notification']['showMessageOnConflicts']
			config.plugins.serienRec.showMessageOnTVPlanerError.value = data['notification']['showMessageOnTVPlanerError']
			config.plugins.serienRec.showMessageOnEventNotFound.value = data['notification']['showMessageOnEventNotFound']
			config.plugins.serienRec.showMessageTimeout.value = data['notification']['showMessageTimeout']
			config.plugins.serienRec.channelUpdateNotification.value = data['notification']['channelUpdateNotification']

		if 'logging' in data and data['logging']['changed']:
			config.plugins.serienRec.LogFilePath.value = data['logging']['logFilePath']
			config.plugins.serienRec.longLogFileName.value = data['logging']['longLogFilename']
			config.plugins.serienRec.deleteLogFilesOlderThan.value = data['logging']['deleteLogFilesOlderThan']
			config.plugins.serienRec.writeLog.value = data['logging']['writeLog']
			config.plugins.serienRec.writeLogVersion.value = data['logging']['writeLogVersion']
			config.plugins.serienRec.writeLogChannels.value = data['logging']['writeLogChannels']
			config.plugins.serienRec.writeLogAllowedEpisodes.value = data['logging']['writeLogAllowedEpisodes']
			config.plugins.serienRec.writeLogAdded.value = data['logging']['writeLogAdded']
			config.plugins.serienRec.writeLogDisk.value = data['logging']['writeLogDisk']
			config.plugins.serienRec.writeLogTimeRange.value = data['logging']['writeLogTimeRange']
			config.plugins.serienRec.writeLogTimeLimit.value = data['logging']['writeLogTimeLimit']
			config.plugins.serienRec.writeLogTimerDebug.value = data['logging']['writeLogTimerDebug']
			config.plugins.serienRec.tvplaner_backupHTML.value = data['logging']['tvplaner_backupHTML']
			config.plugins.serienRec.logScrollLast.value = data['logging']['logScrollLast']
			config.plugins.serienRec.logWrapAround.value = data['logging']['logWrapAround']

		from .SerienRecorderSetupScreen import saveSettings
		saveSettings()

		DBPathChanged = False
		from .SerienRecorder import getDataBaseFilePath
		if getDataBaseFilePath() != "%sSerienRecorder.db" % config.plugins.serienRec.databasePath.value:
			DBPathChanged = True

		if 'autocheck' in data and data['autocheck']['changed']:
			from .SerienRecorderCheckForRecording import checkForRecordingInstance
			checkForRecordingInstance.initialize(self.session, False, False)

		return self.returnResult(req, True, DBPathChanged)

class ApiResetSettingsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiResetSettings")

		from .SerienRecorderSetupScreen import resetSettings
		resetSettings()
		return self.returnResult(req, True, True)

class ApiGetTransmissionsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetTransmissions")
		print(req.args)

		transmission_data = []
		wl_id = toStr(req.args[toBinary("wlid")][0])
		fs_id = toStr(req.args[toBinary("fsid")][0])
		filterMode = int(req.args[toBinary("filterMode")][0])

		from .SerienRecorderSeriesServer import SeriesServer
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		if filterMode == 0:
			webChannels = []
		elif filterMode == 1:
			webChannels = database.getActiveChannels()
		else:
			webChannels = database.getMarkerChannels(fs_id)

		try:
			transmissions = SeriesServer().doGetTransmissions(wl_id, 0, webChannels)
		except:
			transmissions = None

		if transmissions:
			from .SerienRecorderTransmissionsScreen import serienRecSendeTermine

			addedEpisodes = database.getTimerForSeries(fs_id, False)
			filteredTransmissions = serienRecSendeTermine.getFilteredTransmissions(transmissions, addedEpisodes, database, fs_id)

			for seriesName, channel, startTime, endTime, season, episode, title, status, addedType, seasonAllowed in filteredTransmissions:

				transmission_data.append({
					'channel' : channel,
					'startTime' : startTime,
					'endTime' : endTime,
					'season' : season,
					'episode' : episode,
					'title' : title,
					'type' : addedType,
					'seasonAllowed' : seasonAllowed
				})

		data = {
			'seasonFilter': int(config.plugins.serienRec.seasonFilter.value),
			'transmissions': transmission_data
		}

		return self.returnResult(req, True, data)

class ApiSearchSeriesResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiSearchSeries")
		print(req.args)

		data = {}
		search_term = toStr(req.args[toBinary("searchTerm")][0])
		start = int(req.args[toBinary("start")][0])

		if len(search_term) > 0:
			from .SerienRecorderSearchResultScreen import downloadSearchResults
			searchResults = downloadSearchResults(search_term, start)
			searchResults.start()
			searchResults.join()

			items = []
			(startOffset, moreResults, searchResults) = searchResults.getData()
			for item in searchResults:
				items.append({
					'name': item[0],
					'info': item[1],
					'subtitle': item[2],
					'wlid': item[3],
					'fsid': item[4],
					'flag': item[5]
				})

			data = {
				'startOffset': startOffset,
				'nextOffset': moreResults,
				'searchResults': items,
				'showCover': config.plugins.serienRec.showCover.value
			}

		return self.returnResult( req, True, data )

class ApiSearchEventsResource(ApiBackgroundingResource):
	def renderBackground(self, req):
		print("[SerienRecorder] ApiSearchEvents")
		print(req.args)
		data = [{
			'serien_name': "serien_name",
			'sender': "sender",
			'datum': "datum",
			'start': "start",
			'end': "end",
			'staffel': "staffel",
			'episode': "episode",
			'title': "title",
			'status': "status"
		}]

		# from SearchEvents import SearchEvents
		# data = []
		# if req:
		# 	results = SearchEvents(
		# 							#str(req.args.get("filter_enabled")[0]),
		# 							str(req.args.get("serien_name")[0]),
		# 							str(req.args.get("seriesWLID")[0])
		# 							).request_and_return()
		# 	if results:
		# 		for sendetermin in results:
		# 			(serien_name, sender, datum, start, end, staffel, episode, title, status) = sendetermin
		# 			data.append( {
		# 					'serien_name': serien_name,
		# 					'sender': sender,
		# 					'datum': datum,
		# 					'start': start,
		# 					'end': end,
		# 					'staffel': staffel,
		# 					'episode': episode,
		# 					'title': title,
		# 					'status': status
		# 				} )
		#
		return self.returnResult( req, True, data )

class ApiGetActiveChannelsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetActiveChannels")
		print(req.args)

		data = []
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		activeChannels = database.getActiveServiceRefs()

		for webChannel in activeChannels:
			(serviceRef, stbChannel, alternativeServiceRef, alternativeSTBChannel) = activeChannels[webChannel]
			data.append({
				'webChannel' : webChannel,
				'standard' : {
					'serviceRef': serviceRef,
					'stbChannel': stbChannel,
				},
				'alternative' : {
					'serviceRef': alternativeServiceRef,
					'stbChannel': alternativeSTBChannel,
				}
			})

		return self.returnResult( req, True, data )

class ApiGetChannelsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetChannels")
		print(req.args)

		data = []
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		from .SerienRecorderHelpers import STBHelpers

		database = SRDatabase(serienRecDataBaseFilePath)
		channels = database.getChannels(True)
		stbChannelList = STBHelpers.buildSTBChannelList()

		for channel in channels:
			(webChannel, stbChannel, serviceRef, alternativeSTBChannel, alternativeServiceRef, enabled) = channel
			data.append({
				'webChannel': webChannel,
				'enabled': enabled,
				'standard': {
					'serviceRef': serviceRef,
					'stbChannel': STBHelpers.getChannelByRef(stbChannelList, serviceRef),
				},
				'alternative': {
					'serviceRef': alternativeServiceRef,
					'stbChannel': STBHelpers.getChannelByRef(stbChannelList, alternativeServiceRef),
				}
			})

		return self.returnResult(req, True, data)

class ApiGetBoxChannelsResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetBoxChannels")
		print(req.args)

		from .SerienRecorderHelpers import STBHelpers
		if config.plugins.serienRec.selectBouquets.value:
			useBouquets = True
			mainBouquetName = config.plugins.serienRec.MainBouquet.value
			boxChannels = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			altBouquetName = config.plugins.serienRec.AlternativeBouquet.value
			altBoxChannels = STBHelpers.buildSTBChannelList(config.plugins.serienRec.AlternativeBouquet.value)
		else:
			useBouquets = False
			mainBouquetName = None
			boxChannels = STBHelpers.buildSTBChannelList()
			altBouquetName = None
			altBoxChannels = []

		data = {
			'useBouquets': useBouquets,
			'mainBouquetName': mainBouquetName,
			'mainBouquetChannels': boxChannels,
			'altBouquetName': altBouquetName,
			'altBouquetChannels': altBoxChannels
		}

		return self.returnResult(req, True, data)

class ApiChangeChannelStatusResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiChangeChannelStatus")
		print(req.args)

		success = False
		webChannel = toStr(req.args[toBinary("webChannel")][0])

		if len(webChannel) > 0:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)

			database.changeChannelStatus(webChannel)
			success = True

		return self.returnResult(req, True, success)

class ApiSetChannelResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiSetChannel")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		channels = []
		for channel in data['channels']:
			if data['useBouquets']:
				if channel['mainChannel'] != "" or channel['altChannel'] != "":
					channels.append((channel['mainChannel'], channel['mainChannelRef'], channel['altChannel'], channel['altChannelRef'], 1, channel['webChannel'].lower()))
				else:
					channels.append((channel['mainChannel'], channel['mainChannelRef'], channel['altChannel'], channel['altChannelRef'], 0, channel['webChannel'].lower()))
			else:
				if channel['mainChannel'] != "":
					channels.append((channel['mainChannel'], channel['mainChannelRef'], 1, channel['webChannel'].lower()))
				else:
					channels.append((channel['mainChannel'], channel['mainChannelRef'], 0, channel['webChannel'].lower()))
		database.updateChannels(channels, data['useBouquets'])
		return self.returnResult(req, True, True)

class ApiRemoveAllChannelsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveAllChannels")
		print(req.content.getvalue())

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		database.removeAllChannels()

		return self.returnResult(req, True, True)

class ApiUpdateChannelsResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiUpdateChannels")
		print(req.content.getvalue())

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		from .SerienRecorderSeriesServer import SeriesServer
		from .SerienRecorderChannelScreen import serienRecMainChannelEdit
		webChannelList = SeriesServer().doGetWebChannels()
		newWebChannels = None
		removedWebChannels = None

		if webChannelList:
			from .SerienRecorderLogWriter import SRLogger

			webChannelList.sort(key=lambda x: x.lower())
			database = SRDatabase(serienRecDataBaseFilePath)

			dbChannels = database.getChannelPairs()
			(newWebChannels, removedWebChannels) = serienRecMainChannelEdit.getMissingWebChannels(webChannelList, dbChannels)

			# Delete remove channels
			if removedWebChannels:
				SRLogger.writeLog("Folgende Sender wurden bei Wunschliste nicht mehr gefunden, die Zuordnung im SerienRecorder wurde gelöscht:\n" + "\n".join(removedWebChannels), True)
				for webChannel in removedWebChannels:
					database.removeChannel(webChannel)

			if not newWebChannels:
				SRLogger.writeLog("Es wurden keine neuen Sender bei Wunschliste gefunden.")
			else:
				newChannelsMessage = "Folgende Sender wurden neu bei Wunschliste gefunden:\n" + "\n".join(newWebChannels)
				SRLogger.writeLog(newChannelsMessage, True)
				channels = []
				for webChannel in newWebChannels:
					channels.append((webChannel, "", "", 0))
				database.addChannels(channels)

			#database.removeAllChannels()
			database.setChannelListLastUpdate()

		return self.returnResult(req, True, { 'new': newWebChannels, 'removed': removedWebChannels})

class ApiGetTimerResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetTimer")
		print(req.args)

		remainingOnly = bool(req.args[toBinary("remaining")][0])
		current_time = None
		channelList = None
		showPicons = bool(config.plugins.serienRec.showPicons.value)
		enabledTVPlanner = bool(config.plugins.serienRec.tvplaner.value)
		if remainingOnly:
			current_time = int(time.time())
		else:
			showPicons = False

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorderHelpers import STBHelpers
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		timers = database.getAllTimer(current_time)

		if len(timers) > 0 and remainingOnly:
			channelList = STBHelpers.buildSTBChannelList()

		timerList = []
		for timer in timers:
			(row_id, series, season, episode, title, start_time, serviceRef, webChannel, eit, activeTimer, serien_fsid) = timer
			channelName = webChannel
			if serviceRef and channelList:
				channelName = STBHelpers.getChannelByRef(channelList, serviceRef)
			timerList.append(
				{
					'series': series,
					'season': season,
					'episode': episode,
					'title': title,
					'startTime': start_time,
					'serviceRef': serviceRef,
					'channel': channelName,
					'webChannel': webChannel,
					'eit': eit,
					'fsID': serien_fsid,
					'active': bool(activeTimer)
				})

		if config.plugins.serienRec.recordListView.value == 0:
			timerList.sort(key=lambda t: t['startTime'])
		elif config.plugins.serienRec.recordListView.value == 1:
			timerList.sort(key=lambda t: t['startTime'])
			timerList.reverse()



		return self.returnResult(req, True, { 'showPicons': showPicons, 'enabledTVPlanner': enabledTVPlanner, 'timer': timerList })

class ApiGetMarkerTimerResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetMarkerTimer")
		print(req.args)

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		timerList = None

		fs_id = toStr(req.args[toBinary("fsid")][0])
		if len(fs_id) > 0:
			timers = database.getTimerForSeries(fs_id)

			timerList = []
			for timer in timers:
				(season, episode, title, webChannel, start_time) = timer
				timerList.append(
					{
						'season': "0" if len(season) == 0 else season,
						'episode': episode,
					    'title': title,
					    'startTime': start_time,
					    'webChannel': webChannel,
						'eit': 0
				    })

			_nsre = re.compile('([0-9]+)')
			def natural_sort_key(s):
				return [int(text) if text.isdigit() else text.lower()
				        for text in re.split(_nsre, s)]

			timerList = sorted(timerList, key=lambda x: (natural_sort_key(x['season']), natural_sort_key(x['episode'])))

		return self.returnResult(req, True, timerList)

class ApiAddTimersResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiAddTimers")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		database.addToTimerList(data['series'], data['fsid'], data['fromEpisode'], data['toEpisode'], data['season'], "webdump", int(time.time()), "", "", 0, 1)
		return self.returnResult(req, True, None)

class ApiRemoveTimerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveTimer")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		from .SerienRecorderTimerListScreen import serienRecTimerListScreen
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		for timer in data['timers']:
			serienRecTimerListScreen.removeTimer(database, data['series'], data['fsid'], timer['season'], timer['episode'], timer['title'], timer['startTime'], timer['webChannel'], timer['eit'])
		return self.returnResult(req, True, None)

class ApiRemoveTimerBySeasonResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveTimerBySeason")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		(ID, allSeasonsFrom, fromEpisode, timerForSpecials) = database.getMarkerSeasonSettings(data['fsid'])
		seasonList = database.getAllowedSeasons(ID, allSeasonsFrom)
		print("[SerienRecorder] callCleanupTimer", ID, allSeasonsFrom, fromEpisode, timerForSpecials, seasonList)
		numberOfRemovedTimers = database.removeTimersBySeason(data['fsid'], allSeasonsFrom, fromEpisode, seasonList, bool(timerForSpecials))

		return self.returnResult(req, True, numberOfRemovedTimers)

class ApiRemoveAllRemainingTimerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveAllRemainingTimer")
		print(req.content.getvalue())

		from .SerienRecorderTimerListScreen import serienRecTimerListScreen
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		current_time = int(time.time())
		timers = database.getAllTimer(current_time)
		for timer in timers:
			(row_id, series, season, episode, title, start_time, serviceRef, webChannel, eit, activeTimer, series_fsid) = timer
			serienRecTimerListScreen.removeTimer(database, series, series_fsid, season, episode, title, start_time, webChannel, eit, row_id)

		return self.returnResult(req, True, None)

class ApiCreateTimerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiCreateTimer")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())
		transmissions = []
		for event in data['transmissions']:
			transmissions.append([data['name'], event['channel'], event['startTime'], event['endTime'], event['season'], event['episode'], event['title'], "1", event['type'], True])

		from .SerienRecorderTransmissionsScreen import serienRecSendeTermine
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		(activatedTimer, deactivatedTimer) = serienRecSendeTermine.prepareTimer(database, data['filterMode'], data['wlid'], data['fsid'], transmissions)
		return self.returnResult(req, True, { 'activatedTimer': activatedTimer, 'deactivatedTimer': deactivatedTimer })


class ApiGetSeriesInfoResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetSeriesInfo")
		print(req.args)

		wl_id = toStr(req.args[toBinary("wlid")][0])
		fs_id = toStr(req.args[toBinary("fsid")][0])
		data = {}

		if len(wl_id) > 0 and len(fs_id) > 0:
			from .SerienRecorderSeriesServer import SeriesServer

			posterURL = None
			if config.plugins.serienRec.downloadCover.value:
				try:
					posterURL = SeriesServer().doGetCoverURL(0, fs_id)
				except:
					posterURL = None

			seriesInfo = SeriesServer().getSeriesInfo(wl_id, True)

			data = { 'info': seriesInfo, 'coverURL': posterURL }

		return self.returnResult(req, True, data)

class ApiExecuteAutoCheckResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiExecuteAutoCheck")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())
		from .SerienRecorderCheckForRecording import checkForRecordingInstance

		checkForRecordingInstance.setAutoCheckFinished(False)
		checkForRecordingInstance.initialize(None, True, data['withTVPlanner'])

		return self.returnResult(req, True, None)


class ApiGetLogResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetLog")
		print(req.args)

		data = {}
		from .SerienRecorderLogWriter import SRLogger
		logFilePath = SRLogger.getLogFilePath()
		
		if fileExists(logFilePath):

			logFile = open(logFilePath, "r")
			content = logFile.read()
			logFile.close()

			data = { 'path': logFilePath, 'content' : content }
			
		return self.returnResult(req, True, data)

class ApiGetInfoResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetInfo")
		print(req.args)

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		from .SerienRecorderHelpers import STBHelpers
		from .SerienRecorderChannelScreen import checkChannelListTimelineness

		database = SRDatabase(serienRecDataBaseFilePath)
		channelListUpToDate = checkChannelListTimelineness(database)

		data = {
			'stbType': STBHelpers.getSTBType(),
			'image': STBHelpers.getImageVersionString(),
			'srVersion': config.plugins.serienRec.showversion.value,
			'dbVersion': str(database.getVersion()),
			'apiVersion': SRAPIVERSION,
			'channelListeUpToDate': bool(channelListUpToDate)
		}
		return self.returnResult(req, True, data)

class ApiGetChangelogResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiGetChangelog")

		content = None
		if fileExists(SERIENRECORDER_WEBINTERFACE_CHANGELOGPATH):
			changelogFile = open(SERIENRECORDER_WEBINTERFACE_CHANGELOGPATH, "r")
			content = changelogFile.read()
			changelogFile.close()

		return self.returnResult(req, True, content)

class ApiRemoveChangelogResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveChangelog")

		if fileExists(SERIENRECORDER_WEBINTERFACE_CHANGELOGPATH):
			os.remove(SERIENRECORDER_WEBINTERFACE_CHANGELOGPATH)

		return self.returnResult(req, True, True)

class ApiCheckForUpdateResource(ApiBaseResource):
	def render_GET(self, req):
		print("[SerienRecorder] ApiCheckForUpdate")
		print(req.args)

		from .SerienRecorderUpdateScreen import checkGitHubUpdate
		webapp_assets = checkGitHubUpdate.checkForWebinterfaceUpdate()
		return self.returnResult(req, True, webapp_assets)

class ApiInstallUpdateResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiInstallUpdate")
		print(req.content.getvalue())

		data = json.loads(req.content.getvalue())

		from .SerienRecorderUpdateScreen import checkGitHubUpdate
		successful = checkGitHubUpdate.installWebinterfaceUpdate(data['url'])
		return self.returnResult(req, True, successful)

