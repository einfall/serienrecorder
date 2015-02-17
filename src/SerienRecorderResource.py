# -*- coding: utf-8 -*-
from __init__ import _

from twisted.internet import reactor
from twisted.web import http, resource, server
import threading
try:
	from urllib import unquote
except ImportError as ie:
	from urllib.parse import unquote

from SerienRecorderHelpers import *

import json

API_VERSION = "1.0"


def getApiList():
	root = ApiGetMarkerResource()
	childs = []
	childs.append( ('searchserie', ApiSearchSerieResource() ) )
	childs.append( ('stbchannels', ApiStbChannelsResource() ) )
	childs.append( ('webchannels', ApiWebChannelsResource() ) )
	childs.append( ('searchevents', ApiSearchEventsResource() ) )
	return ( root, childs )

def addWebInterfaceForDreamMultimedia(session):
	try:
		from Plugins.Extensions.WebInterface.WebChilds.Toplevel import addExternalChild
		#from Plugins.Extensions.WebInterface.WebChilds.Screenpage import ScreenPage
		from twisted.web import static
		#from twisted.python import util
		#from WebChilds.UploadResource import UploadResource

	except Exception, e: #ImportError as ie:
		print "SerienRecorder API Error #################"
		print str(e)
		pass
	else:
		if hasattr(static.File, 'render_GET'):
			class File(static.File):
				def render_POST(self, request):
					return self.render_GET(request)
		else:
			File = static.File

		# webapi
		(root, childs) = addWebInterfaceForOpenWebInterface()
		if childs:
			for name, api in childs:
				root.putChild(name, api)
		addExternalChild( ("serienrecorder", root , "SerienRecorder-Plugin", API_VERSION, False) )

		# webgui
		#session = kwargs["session"]
		#root = File(util.sibpath(__file__, "web-data"))
		#root.putChild("web", ScreenPage(session, util.sibpath(__file__, "web"), True) )
		#root.putChild('tmp', File('/tmp'))
		#root.putChild("uploadfile", UploadResource(session))
		#addExternalChild( ("autotimereditor", root, "AutoTimer", "1", True) )

def addWebInterfaceForOpenWebInterface():
	return getApiList()


class ApiBaseResource(resource.Resource):
	def returnResult(self, req, state, data):
		print "SerienRecorder API self.returnResult #################"
		req.setResponseCode(http.OK)
		req.setHeader('Content-type', 'application/json')
		req.setHeader('charset', 'UTF-8')

		return json.dumps(
					{
						'status' : 'True' if state else 'False',
						'data' : data
					},
					sort_keys=True, 
					indent=4, 
					separators=(',', ': ')
				)

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


class ApiGetMarkerResource(ApiBaseResource):
	def render(self, req):
		from SerienRecorder import getMarker
		data = []
		results = getMarker()
		if results:
			for marker in results:
				(serie, url, staffeln, sender, AbEpisode, AnzahlAufnahmen, SerieEnabled, excludedWeekdays) = marker
				data.append( {
						'serie': serie,
						'url': url,
						'staffeln': staffeln,
						'sender': sender,
						'AbEpisode': AbEpisode,
						'AnzahlAufnahmen': AnzahlAufnahmen
					} )
		
		return self.returnResult( req, True, data )

class ApiSearchSerieResource(ApiBackgroundingResource):
	def renderBackground(self, req):
		from SearchSerie import SearchSerie
		data = []
		if req:
			results = SearchSerie( 
									str(req.args.get("serien_name")[0]) 
								).request_and_return()
			if results:
				for serie in results:
					(name_Serie, year_Serie, id_Serie) = serie
					data.append( {
							'name_Serie': name_Serie,
							'year_Serie': year_Serie,
							'id_Serie': id_Serie
						} )
		
		return self.returnResult( req, True, data )

class ApiSearchEventsResource(ApiBackgroundingResource):
	def renderBackground(self, req):
		from SearchEvents import SearchEvents
		data = []
		if req:
			results = SearchEvents(
									#str(req.args.get("filter_enabled")[0]), 
									str(req.args.get("serien_name")[0]), 
									str(req.args.get("serien_id")[0])
									).request_and_return()
			if results:
				for sendetermin in results:
					(serien_name, sender, datum, start, end, staffel, episode, title, status) = sendetermin
					data.append( {
							'serien_name': serien_name,
							'sender': sender,
							'datum': datum,
							'start': start,
							'end': end,
							'staffel': staffel,
							'episode': episode,
							'title': title,
							'status': status
						} )
		
		return self.returnResult( req, True, data )

class ApiStbChannelsResource(ApiBaseResource):
	def render(self, req):
		data = []
		results = STBHelpers.buildSTBChannelList()
		if results:
			for channel in results:
				(servicename, serviceref) = channel
				data.append( {
						'servicename': servicename,
						'serviceref': serviceref
					} )
		
		return self.returnResult( req, True, data )

class ApiWebChannelsResource(ApiBackgroundingResource):
	def renderBackground(self, req):
		from WebChannels import WebChannels
		data = []
		results = WebChannels().request_and_return()
		print "ApiWebChannelsResource results"
		print results
		if results:
			for channel in results:
				#(webChannel, stbChannel, stbRef, status) = channel
				#data.append( {
				#		'webChannel': webChannel,
				#		'stbChannel': stbChannel,
				#		'stbRef': stbRef,
				#		'status': status
				data.append( {
						'webChannel': channel
					} )
		print "ApiWebChannelsResource data"
		print data
		return self.returnResult( req, True, data )
