# coding=utf-8

# This file contains the SerienRecoder Serien Server stuff

# Constants
SERIES_SERVER_URL = 'http://serienrecorder.lima-city.de/cache.php'

try:
	import xmlrpclib
except ImportError as ie:
	xmlrpclib = None

class SeriesServer:

	def __init__(self):
		# Check dependencies
		if xmlrpclib is not None:
			self.server = xmlrpclib.ServerProxy(SERIES_SERVER_URL, verbose=False)

	def getSeriesInfo(self, seriesID):
		seriesInfo = self.server.sp.cache.getSeriesInfo(seriesID)
		infoText = ""

		# Fan count
		if seriesInfo['fancount']:
			infoText += ("Die Serie hat %s Fans" % seriesInfo['fancount'])

		# Rating
		if seriesInfo['rating']:
			infoText += (" und eine Bewertung von %s / 5.0 Sternen" % seriesInfo['rating'])

		# Transmission info
		infoText += "\n\n"
		if seriesInfo['seasons_and_episodes']:
			glue = ', '
			infoText += "%s\n" % glue.join(seriesInfo['seasons_and_episodes'])

		if seriesInfo['transmissioninfo']:
			infoText += "%s\n" % seriesInfo['transmissioninfo']

		if seriesInfo['category']:
			infoText += "%s\n" % seriesInfo['category']

		infoText += "\n"
		# Description
		if seriesInfo['description']:
			infoText += seriesInfo['description'].encode('utf-8')

		# Cast / Crew
		if seriesInfo['cast']:
			glue = "\n"
			infoText += "\n\nCast und Crew:\n%s\n%s" % (glue.join(seriesInfo['cast']).encode('utf-8'), glue.join(seriesInfo['crew']).encode('utf-8'))
		return infoText

	def doSearch(self, searchString):
		resultList = []
		searchResults = self.server.sp.cache.searchSeries(searchString)
		for searchResult in searchResults['results']:
			resultList.append((searchResult['name'].encode('utf-8'), searchResult['country_year'], searchResult['id']))
		if 'more' in searchResults:
			resultList.append(("... %s%s'%s'" % (searchResults['more'], " weitere Ergebnisse für ", searchString.encode('utf-8')), str(searchResults['more']), "-1"))
		return resultList