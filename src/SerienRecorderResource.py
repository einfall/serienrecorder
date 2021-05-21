# -*- coding: utf-8 -*-
from twisted.internet import reactor
from twisted.web import http, resource, server
import threading

from Components.config import config

from Tools.Directories import fileExists

from .SerienRecorderHelpers import SRAPIVERSION, SRWEBAPPVERSION, toBinary, toStr, PY2

import json, os, time

def getApiList():
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
	childs.append( ('cover', ApiGetCoverResource() ) )
	childs.append( ('picon', ApiGetPiconResource() ) )
	childs.append( ('tvdbcover', ApiGetTVDBCoverResource() ) )
	childs.append( ('tvdbcovers', ApiGetTVDBCoversResource() ) )
	childs.append( ('settvdbcover', ApiSetTVDBCoverResource()))
	childs.append( ('transmissions', ApiGetTransmissionsResource() ) )
	childs.append( ('searchseries', ApiSearchSeriesResource() ) )
	childs.append( ('activechannels', ApiGetActiveChannelsResource() ) )
	childs.append( ('channels', ApiGetChannelsResource() ) )
	childs.append( ('boxchannels', ApiGetBoxChannelsResource() ) )
	childs.append( ('changechannelstatus', ApiChangeChannelStatusResource() ) )
	childs.append( ('setchannel', ApiSetChannelResource() ) )
	childs.append( ('removeallchannels', ApiRemoveAllChannelsResource() ) )
	#childs.append( ('webchannels', ApiWebChannelsResource() ) )
	#childs.append( ('searchevents', ApiSearchEventsResource() ) )
	childs.append( ('timer', ApiGetTimerResource() ) )
	childs.append( ('markertimer', ApiGetMarkerTimerResource() ) )
	childs.append( ('addtimers', ApiAddTimersResource() ) )
	childs.append( ('removetimer', ApiRemoveTimerResource() ) )
	childs.append( ('removeallremainingtimer', ApiRemoveAllRemainingTimerResource() ) )
	childs.append( ('createtimer', ApiCreateTimerResource() ) )
	childs.append( ('seriesinfo', ApiGetSeriesInfoResource() ) )
	childs.append( ('autocheck', ApiExecuteAutoCheckResource() ) )
	childs.append( ('log', ApiGetLogResource() ) )
	childs.append( ('info', ApiGetInfoResource() ) )
	childs.append( ('checkforupdate', ApiCheckForUpdateResource() ) )
	childs.append( ('installupdate', ApiInstallUpdateResource() ) )
	return ( root, childs )

def addWebInterface():
	use_openwebif = False
	if os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/OpenWebif/pluginshook.src"):
		use_openwebif = True
	print("[SerienRecorder] addWebInterface for OpenWebif = %s" % str(use_openwebif))
	try:
		from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
		from twisted.web import static
		from twisted.python import util
		#from WebChilds.UploadResource import UploadResource

	except Exception as e:
		print(str(e))
		pass

	# webapi
	(root, childs) = getApiList()
	if childs:
		for name, api in childs:
			root.putChild(toBinary(name), api)
	apiSuccessfulAdded = addExternalChild( ("serienrecorderapi", root, "SerienRecorder-API", SRAPIVERSION, False) )
	if apiSuccessfulAdded is not True:
		apiSuccessfulAdded = addExternalChild(("serienrecorderapi", root, "SerienRecorder-API", SRAPIVERSION))

	print("[SerienRecorder] addExternalChild for API [%s]" % str(apiSuccessfulAdded))

	# webgui
	root = static.File(util.sibpath(__file__, "web-data"))
	print("[SerienRecorder] WebUI root path: %s" % str(root))

	try:
		if use_openwebif or os.path.exists("/usr/lib/enigma2/python/Plugins/Extensions/WebInterface/web/external.xml"):
			uiSuccessfulAdded = addExternalChild( ("serienrecorderui", root, "SerienRecorder", SRWEBAPPVERSION, True) )
			if uiSuccessfulAdded is not True:
				addExternalChild(("serienrecorderui", root, "SerienRecorder", SRWEBAPPVERSION))
		else:
			uiSuccessfulAdded = addExternalChild( ("serienrecorderui", root) )
	except:
		uiSuccessfulAdded = addExternalChild(("serienrecorderui", root))

	print("[SerienRecorder] addExternalChild for UI [%s]" % str(uiSuccessfulAdded))

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

		fsID = req.args.get(toBinary("fsid"), None)
		if config.plugins.serienRec.showCover.value and fsID:
			cover_file_path = os.path.join(config.plugins.serienRec.coverPath.value, "%s.jpg" % toStr(fsID[0]))
		else:
			cover_file_path = None

		if config.plugins.serienRec.downloadCover.value and cover_file_path and not fileExists(cover_file_path):
			# Download cover
			from .SerienRecorderSeriesServer import SeriesServer
			try:
				posterURL = SeriesServer().doGetCoverURL(0, fsID)
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
		serviceRef = str(req.args["serviceRef"][0])
		channelName = str(req.args["channelName"][0])

		#serviceRef = req.args.get(toBinary("serviceRef"), None)
		#channelName = req.args.get(toBinary("channelName"), None)
		print("[SerienRecorder] ApiGetPiconResource: [%s] / [%s]" % (serviceRef, channelName))

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

		fs_id = str(req.args["fsid"][0])
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

		wl_id = str(req.args["wlid"][0])
		posterURLs = None
		if config.plugins.serienRec.downloadCover.value:
			from .SerienRecorderSeriesServer import SeriesServer
			try:
				posterURLs = SeriesServer().getCoverURLs(wl_id)
			except:
				posterURLs = None

		return self.returnResult(req, True, posterURLs)

class ApiSetTVDBCoverResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiSetTVDBCover")

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

class ApiGetMarkersResource(ApiBaseResource):
	def render_GET(self, req):
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

		# from SerienRecorder import getMarker
		# results = getMarker()
		# if results:
		# 	for marker in results:
		# 		(serie, url, staffeln, sender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays) = marker
		# 		data.append( {
		# 				'serie': serie,
		# 				'url': url,
		# 				'staffeln': staffeln,
		# 				'sender': sender,
		# 				'AbEpisode': AbEpisode,
		# 				'AnzahlAufnahmen': AnzahlAufnahmen
		# 			} )
		#
		return self.returnResult( req, True, data )

class ApiChangeMarkerStatusResource(ApiBaseResource):
	def render_GET(self, req):
		result = False
		wl_id = req.args.get(toBinary("wlid"), None)
		if wl_id:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			database.changeMarkerStatus(toStr(wl_id[0]), config.plugins.serienRec.BoxID.value)
			result = True
		return self.returnResult(req, result, None)

class ApiCreateMarkerResource(ApiBaseResource):
	def render_POST(self, req):
		result = False
		data = json.loads(req.content.getvalue())
		if 'fsid' in data:
			from .SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			if serienRecSearchResultScreen.createMarker(data['wlid'], data['name'], data['info'], data['fsid']):
				from .SerienRecorder import getCover
				getCover(None, data['name'], data['wlid'], data['fsid'], False, True)
				result = True
		return self.returnResult(req, result, None)

class ApiDeleteMarkerResource(ApiBaseResource):
	def render_POST(self, req):
		result = False
		data = json.loads(req.content.getvalue())
		if 'fsid' in data:
			from .SerienRecorderMarkerScreen import serienRecMarker
			serienRecMarker.doRemoveSerienMarker(data['fsid'], data['name'], data['info'], data['removeTimer'])
			result = True
		return self.returnResult(req, result, None)

class ApiSetMarkerChannelsResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiSetMarkerChannels")
		print(data)
		channels = []
		if 'wlid' in data:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			database.removeAllMarkerChannels(data['wlid'])
			markerID = database.getMarkerID(data['wlid'])

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

			database.setAllChannelsToMarker(data['wlid'], allChannels)

			if allChannels:
				channels = ['Alle',]
			else:
				channels = database.getMarkerChannels(data['wlid'], False)
			channels = str(channels).replace("[", "").replace("]", "").replace("'", "").replace('"', "")

		return self.returnResult(req, True, channels)

class ApiGetMarkerSeasonSettingsResource(ApiBaseResource):
	def render_GET(self, req):
		data = {}
		wl_id = req.args.get(toBinary("wlid"), None)
		if wl_id:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			(ID, allSeasonsFrom, fromEpisode, timerForSpecials) = database.getMarkerSeasonSettings(toStr(wl_id[0]))
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
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiSetMarkerSeasonSettings")
		print(data)

		results = []
		if 'wlid' in data:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)
			database.removeAllMarkerSeasons(data['wlid'])

			AbEpisode = data['episode']
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

			database.updateMarkerSeasonsSettings(data['wlid'], AlleStaffelnAb, AbEpisode, TimerForSpecials)

		results = ', '.join(str(staffel) for staffel in results)
		return self.returnResult(req, True, results)

class ApiGetMarkerSettingsResource(ApiBaseResource):
	def render_GET(self, req):
		data = {}
		marker_id = req.args.get(toBinary("markerid"), None)
		if marker_id:
			from .SerienRecorderHelpers import hasAutoAdjust
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath, VPSPluginAvailable
			database = SRDatabase(serienRecDataBaseFilePath)

			(AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon,
			 AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase, updateFromEPG, skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer) = database.getMarkerSettings(toStr(marker_id[0]))

			if not AufnahmeVerzeichnis:
				AufnahmeVerzeichnis = ""

			if not epgSeriesName:
				epgSeriesName = ""

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
				if PY2:
					import cPickle as pickle
				else:
					import pickle
				serienmarker_tags = pickle.loads(tags)

			data = {
				'recordDir': {
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
				}
			}

		return self.returnResult(req, True, data)

class ApiSetMarkerSettingsResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiSetMarkerSettings")
		print(data)

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
				if PY2:
					import cPickle as pickle
				else:
					import pickle
				tags = pickle.dumps(data['settings']['tags'])

			database.setMarkerSettings(int(data['markerid']),
			                           (AufnahmeVerzeichnis, int(Staffelverzeichnis), Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen,
			                           AufnahmezeitVon, AufnahmezeitBis, int(data['settings']['preferredChannel']), int(data['settings']['useAlternativeChannel']['value']),
			                           vpsSettings, excludedWeekdays, tags, int(data['settings']['addToDatabase']), updateFromEPG, skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer))

			results = {
				'recordfolder': AufnahmeVerzeichnis if AufnahmeVerzeichnis else config.plugins.serienRec.savetopath.value,
				'numberOfRecords': data['settings']['numberOfRecordings']['value'] if data['settings']['numberOfRecordings']['value'] else config.plugins.serienRec.NoOfRecords,
				'leadtime': data['settings']['leadTime']['value'] if data['settings']['leadTime']['value'] else config.plugins.serienRec.margin_before,
				'followuptime': data['settings']['followupTime']['value'] if data['settings']['followupTime']['value'] else config.plugins.serienRec.margin_after,
				'preferredChannel': int(data['settings']['preferredChannel']),
				'useAlternativeChannel': bool(data['settings']['useAlternativeChannel']['value'])
			}

		return self.returnResult(req, True, results)

class ApiGetTransmissionsResource(ApiBaseResource):
	def render_GET(self, req):
		data = []
		wl_id = req.args.get(toBinary("wlid"), None)
		fs_id = req.args.get(toBinary("fsid"), None)
		filterMode = req.args.get(toBinary("filterMode"), None)

		if wl_id:
			wl_id = toStr(wl_id[0])
			fs_id = toStr(fs_id[0])
			filterMode = int(toStr(filterMode[0]))

			from .SerienRecorderSeriesServer import SeriesServer
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)

			if filterMode == 0:
				webChannels = []
			elif filterMode == 1:
				webChannels = database.getActiveChannels()
			else:
				webChannels = database.getMarkerChannels(wl_id)

			try:
				transmissions = SeriesServer().doGetTransmissions(wl_id, 0, webChannels)
			except:
				transmissions = None
			
			if transmissions:
				from .SerienRecorderTransmissionsScreen import serienRecSendeTermine

				addedEpisodes = database.getTimerForSeries(fs_id, False)
				# TODO: Check for allowed seasons
				# TODO: Search file on HDD

				marginList = {}

				for seriesName, channel, startTime, endTime, season, episode, title, status in transmissions:
					if not channel in marginList:
						marginList[channel] = database.getMargins(fs_id, channel, config.plugins.serienRec.margin_before.value, config.plugins.serienRec.margin_after.value)

					(margin_before, margin_after) = marginList[channel]
					start_unixtime = startTime - (int(margin_before) * 60)

					if serienRecSendeTermine.isTimerAdded(addedEpisodes, channel, season, episode, int(start_unixtime), title):
						addedType = 2
					elif serienRecSendeTermine.isAlreadyAdded(addedEpisodes, season, episode, title):
						addedType = 3
					else:
						addedType = 0

					data.append({
						'channel' : channel,
						'startTime' : startTime,
						'endTime' : endTime,
						'season' : season,
						'episode' : episode,
						'title' : title,
						'type' : addedType
					})

		return self.returnResult(req, True, data)

class ApiSearchSeriesResource(ApiBaseResource):
	def render_GET(self, req):
		data = {}

		search_term = req.args.get(toBinary("searchTerm"), None)
		start = req.args.get(toBinary('start'), None)
		if search_term:
			from .SerienRecorderSearchResultScreen import downloadSearchResults
			searchResults = downloadSearchResults(toStr(search_term[0]), int(toStr(start[0])))
			searchResults.start()
			searchResults.join()

			items = []
			(startOffset, moreResults, searchResults) = searchResults.getData()
			for item in searchResults:
				items.append({
					'name': item[0],
					'info': item[1],
					'wlid': item[2],
					'fsid': item[3]
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
		data = []

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		channels = database.getChannels(True)

		for channel in channels:
			(webChannel, stbChannel, serviceRef, alternativeSTBChannel, alternativeServiceRef, enabled) = channel
			data.append({
				'webChannel': webChannel,
				'enabled': enabled,
				'standard': {
					'serviceRef': serviceRef,
					'stbChannel': stbChannel,
				},
				'alternative': {
					'serviceRef': alternativeServiceRef,
					'stbChannel': alternativeSTBChannel,
				}
			})

		return self.returnResult(req, True, data)

class ApiGetBoxChannelsResource(ApiBaseResource):
	def render_GET(self, req):

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
		success = False
		webChannel = req.args.get(toBinary("webChannel"), None)
		if webChannel:
			from .SerienRecorderDatabase import SRDatabase
			from .SerienRecorder import serienRecDataBaseFilePath
			database = SRDatabase(serienRecDataBaseFilePath)

			database.changeChannelStatus(toStr(webChannel[0]))
			success = True

		return self.returnResult(req, True, success)

class ApiSetChannelResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiSetChannel")

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

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		database.removeAllChannels()

		return self.returnResult(req, True, True)

class ApiGetTimerResource(ApiBaseResource):
	def render_GET(self, req):
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorderHelpers import STBHelpers
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		remainingOnly = req.args.get(toBinary("remaining"), None)
		if remainingOnly:
			remainingOnly = bool(toStr(remainingOnly[0]))

		current_time = None
		channelList = None
		showPicons = bool(config.plugins.serienRec.showPicons.value)
		enabledTVPlanner = bool(config.plugins.serienRec.tvplaner.value)
		if remainingOnly:
			current_time = int(time.time())
		else:
			showPicons = False

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
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)
		timerList = None

		fsID = req.args.get(toBinary("fsid"), None)
		if fsID:
			fsID = toStr(fsID[0])
			timers = database.getTimerForSeries(fsID)

			timerList = []
			for timer in timers:
				(season, episode, title, webChannel, start_time) = timer
				timerList.append(
					{
						'season': "0" if len(season) == 0 else season,
						'episode': episode,
					    'title': title,
					    'startTime': start_time,
					    'webChannel': webChannel
				    })

			timerList.sort(key=lambda x: (x['season'].lower(), x['episode'].lower()))

		return self.returnResult(req, True, timerList)

class ApiAddTimersResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiAddTimers")

		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		database.addToTimerList(data['series'], data['fsid'], data['fromEpisode'], data['toEpisode'], data['season'], "webdump", int(time.time()), "", "", 0, 1)
		return self.returnResult(req, True, None)

class ApiRemoveTimerResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiRemoveTimer")

		from .SerienRecorderTimerListScreen import serienRecTimerListScreen
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		serienRecTimerListScreen.removeTimer(database, data['series'], data['fsid'], data['season'], data['episode'], data['title'], data['startTime'], data['webChannel'], data['eit'])
		return self.returnResult(req, True, None)

class ApiRemoveAllRemainingTimerResource(ApiBaseResource):
	def render_POST(self, req):
		print("[SerienRecorder] ApiRemoveAllRemainingTimer")

		from .SerienRecorderTimerListScreen import serienRecTimerListScreen
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		current_time = int(time.time())
		timers = database.getAllTimer(current_time)
		for timer in timers:
			(row_id, serie, staffel, episode, title, start_time, serviceRef, webChannel, eit, activeTimer, serien_fsid) = timer
			serienRecTimerListScreen.removeTimer(database, serie, serien_fsid, staffel, episode, title, start_time, webChannel, eit)

		return self.returnResult(req, True, None)

class ApiCreateTimerResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiCreateTimer")
		print(data)

		transmissions = []
		for event in data['transmissions']:
			transmissions.append([data['name'].encode('utf-8'), event['channel'].encode('utf-8'), event['startTime'], event['endTime'], event['season'], event['episode'], event['title'].encode('utf-8'), "1", event['type']])

		from .SerienRecorderTransmissionsScreen import serienRecSendeTermine
		from .SerienRecorderDatabase import SRDatabase
		from .SerienRecorder import serienRecDataBaseFilePath
		database = SRDatabase(serienRecDataBaseFilePath)

		(activatedTimer, deactivatedTimer) = serienRecSendeTermine.prepareTimer(database, data['filterMode'], data['wlid'], data['fsid'], transmissions)
		return self.returnResult(req, True, { 'activatedTimer': activatedTimer, 'deactivatedTimer': deactivatedTimer })


class ApiGetSeriesInfoResource(ApiBaseResource):
	def render_GET(self, req):
		wl_id = req.args.get(toBinary("wlid"), None)
		fs_id = req.args.get(toBinary("fsid"), None)
		data = {}

		if wl_id and fs_id:
			from .SerienRecorderSeriesServer import SeriesServer

			posterURL = None
			if config.plugins.serienRec.downloadCover.value:
				try:
					posterURL = SeriesServer().doGetCoverURL(0, toStr(fs_id[0]))
				except:
					posterURL = None

			seriesInfo = SeriesServer().getSeriesInfo(toStr(wl_id[0]), True)

			data = { 'info': seriesInfo, 'coverURL': posterURL }

		return self.returnResult(req, True, data)

class ApiExecuteAutoCheckResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())
		print("[SerienRecorder] ApiExecuteAutoCheck")

		from .SerienRecorderCheckForRecording import checkForRecordingInstance

		checkForRecordingInstance.setAutoCheckFinished(False)
		checkForRecordingInstance.initialize(None, True, data['withTVPlanner'])

		return self.returnResult(req, True, None)


class ApiGetLogResource(ApiBaseResource):
	def render_GET(self, req):
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

class ApiCheckForUpdateResource(ApiBaseResource):
	def render_GET(self, req):

		from .SerienRecorderUpdateScreen import checkGitHubUpdate
		webapp_assets = checkGitHubUpdate.checkForWebinterfaceUpdate()
		return self.returnResult(req, True, webapp_assets)

class ApiInstallUpdateResource(ApiBaseResource):
	def render_POST(self, req):
		data = json.loads(req.content.getvalue())

		from .SerienRecorderUpdateScreen import checkGitHubUpdate
		successful = checkGitHubUpdate.installWebinterfaceUpdate(data['url'])
		return self.returnResult(req, True, successful)

