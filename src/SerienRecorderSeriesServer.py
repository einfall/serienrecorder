# coding=utf-8

# This file contains the SerienRecoder Serien Server stuff

from .SerienRecorderHelpers import toStr, PY2


# Constants
SERIES_SERVER_IP = 'www.serienserver.de'
SERIES_SERVER_BASE_URL = 'http://www.serienserver.de/cache/'

try:
	if PY2:
		import xmlrpclib
	else:
		import xmlrpc.client as xmlrpclib
except ImportError as ie:
	xmlrpclib = None


class TimeoutTransport (xmlrpclib.Transport):
	"""
	Custom XML-RPC transport class for HTTP connections, allowing a timeout in
	the base connection.
	"""
	def __init__(self, timeout=3, use_datetime=0):
		xmlrpclib.Transport.__init__(self, use_datetime)
		self._timeout = timeout

	def make_connection(self, host):
		if PY2:
			import httplib
		else:
			import http.client as httplib
		import ssl
		host, extra_headers, x509 = self.get_host_info(host)
		if hasattr(ssl, '_create_unverified_context'):
			ssl._create_default_https_context = ssl._create_unverified_context
		return httplib.HTTPSConnection(host, timeout=self._timeout)

class SeriesServer:

	def __init__(self):
		# Check dependencies
		if xmlrpclib is not None:
			t = TimeoutTransport(7)
			self.server = xmlrpclib.ServerProxy(SERIES_SERVER_BASE_URL + "/cache.php", transport=t)

	@staticmethod
	def getChannelListLastUpdate():
		remoteChannelListLastUpdated = None
		try:
			if PY2:
				import httplib
			else:
				import http.client as httplib
			conn = httplib.HTTPConnection(SERIES_SERVER_IP, timeout=5, port=80)
			conn.request(url="/cache/cllu.php", method="HEAD")
			rawData = conn.getresponse()
			remoteChannelListLastUpdated = rawData.getheader("x-last-updated")
		except Exception as e:
			print("[SerienRecorder] Error getting channel list last update time [%s]" % str(e))

		return remoteChannelListLastUpdated

	def getSeriesID(self, seriesName):
		try:
			return self.server.sp.cache.getID(seriesName)
		except:
			return 0

	def getIDByFSID(self, fsID):
		try:
			return self.server.sp.cache.getIDByFSID(fsID)
		except:
			return 0

	def getTVDBID(self, seriesID):
		try:
			return self.server.sp.cache.getTVDBID(seriesID)
		except:
			return False

	def setTVDBID(self, seriesID, tvdbID):
		try:
			self.server.sp.cache.setTVDBID(seriesID, tvdbID)
			return True
		except:
			return False

	def resetLastEPGUpdate(self, seriesID):
		try:
			self.server.sp.cache.resetEPGLastModified(seriesID)
			return True
		except:
			return False

	def getSeriesNamesAndInfoByWLID(self, wlIDs):
		try:
			return self.server.sp.cache.getNamesAndInfoByWLIDs(wlIDs)
		except:
			return {}

	def getSeriesInfo(self, seriesID, raw=False):
		infoText = ""
		try:
			seriesInfo = self.server.sp.cache.getSeriesInfo(seriesID)
		except:
			return infoText

		if raw:
			return seriesInfo

		# Title
		if 'title' in seriesInfo:
			infoText += toStr(seriesInfo['title'])

		# Year
		if 'year' in seriesInfo:
			infoText += " (%s)" % seriesInfo['year']

		# Info
		if 'info' in seriesInfo:
			infoText += "\n%s" % seriesInfo['info']

		# Fan count
		if 'fancount' in seriesInfo:
			infoText += ("\n\nDie Serie hat %s Fans" % seriesInfo['fancount'])

		# Rating
		if 'rating' in seriesInfo:
			infoText += (" und eine Bewertung von %.1f" % float(seriesInfo['rating']))

		# Sex
		if 'male' in seriesInfo and 'female' in seriesInfo and 'age' in seriesInfo:
			infoText += ("\nZielgruppe: %s (Männer: %s, Frauen: %s)" % (seriesInfo['age'], seriesInfo['male'], seriesInfo['female']))

		# Transmission info
		infoText += "\n\n"
		if 'seasons_and_episodes' in seriesInfo:
			infoText += "%s\n" % toStr(seriesInfo['seasons_and_episodes'])

		if 'transmissioninfo' in seriesInfo:
			infoText += "%s\n" % seriesInfo['transmissioninfo']

		infoText += "\n"
		# Description
		if 'description' in seriesInfo:
			infoText += toStr(seriesInfo['description'])

		# Upfronts
		if 'upfronts' in seriesInfo:
			infoText += "\n\n"
			glue = '\n'
			infoText += "%s\n" % toStr(glue.join(seriesInfo['upfronts']))

		# Cast / Crew
		if 'cast' in seriesInfo:
			glue = "\n"
			infoText += "\n\nCast:\n%s" % toStr(glue.join(seriesInfo['cast']))
		return infoText

	def getEpisodeInfo(self, seriesID):
		infoText = ""
		try:
			episodeInfo = self.server.sp.cache.getEpisodeInfo(seriesID)
		except:
			return infoText
		if 'season' in episodeInfo and 'episode' in episodeInfo:
			infoText += "Staffel: %s, Episode: %s\n" % (episodeInfo['season'], episodeInfo['episode'])

		# Title
		if 'title' in episodeInfo:
			infoText += "Titel: %s" % toStr(episodeInfo['title'])

		# Rating
		if 'rating' in episodeInfo and 'ratingCount' in episodeInfo:
			infoText += "\n\n"
			infoText += "Episodenbewertung: %.1f aus %s Stimmen" % (float(episodeInfo['rating']), episodeInfo['ratingCount'])

		# Transmissions
		infoText += "\n\n"
		if 'firstAired' in episodeInfo:
			infoText += "Erstausstrahlung: %s\n" % episodeInfo['firstAired']

		# Description
		if 'description' in episodeInfo:
			infoText += "\n"
			infoText += "%s\n" % toStr(episodeInfo['description'])

		# Cast / Crew
		if 'guestStars' in episodeInfo:
			glue = ", "
			infoText += "\n\nGaststars:\n%s" % toStr(glue.join(episodeInfo['guestStars']))
		if 'directors' in episodeInfo:
			glue = ", "
			infoText += "\n\nRegie:\n%s" % toStr(glue.join(episodeInfo['writers']))
		if 'writers' in episodeInfo:
			glue = ", "
			infoText += "\n\nDrehbuch:\n%s" % toStr(glue.join(episodeInfo['writers']))

		return infoText


	def doSearch(self, searchString, start = 0):
		more = 0
		resultList = []
		try:
			searchResults = self.server.sp.cache.searchSeries(searchString, start)
			for searchResult in searchResults['results']:
				resultList.append((toStr(searchResult['name']), toStr(searchResult['country_year']), str(searchResult['id']), searchResult['fs_id']))
			if 'more' in searchResults:
				more = int(searchResults['more'])
		except:
			resultList = []
		return start, more, resultList

	def doGetCoverURL(self, seriesID, fsID):
		try:
			return self.server.sp.cache.getCoverURL(int(seriesID), fsID)
		except:
			return ''

	def getCoverURLs(self, seriesID):
		try:
			results = self.server.sp.cache.getCoverURLs(int(seriesID))
			return results['covers']
		except Exception as e:
			print("[SerienRecorder] Fehler beim Abrufen der Cover [%s]" % str(e))
			return None
			
	def doGetWebChannels(self):
		return self.server.sp.cache.getWebChannels()

	def doGetPlannerData(self, offset, webChannels):
		return self.server.sp.cache.getNewPlanerData(int(offset), webChannels)

	def doGetTopThirty(self):
		return self.server.sp.cache.getTopTen()

	def doGetEpisodes(self, seriesID, page):
		return self.server.sp.cache.getEpisodes(int(seriesID), int(page))

	def doGetTransmissions(self, seriesID, offset, webChannels):
		resultList = []
		transmissions = self.server.sp.cache.getTransmissions(int(seriesID), int(offset), webChannels)
		seriesName = transmissions['series']

		for event in transmissions['events']:
			if event['season'] == '':
				event['season'] = '0'
			if event['episode'] == '':
				event['episode'] = '00'
			resultList.append([toStr(seriesName), toStr(event['channel']), event['start'], event['end'], event['season'], event['episode'], toStr(event['title']), "0"])

		return resultList

	def doGetSeasonBegins(self, webChannels):
		return self.server.sp.cache.getSeasonBegins(webChannels)