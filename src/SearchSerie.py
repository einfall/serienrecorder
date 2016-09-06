# -*- coding: utf-8 -*-
from __init__ import _

import re

from twisted.web.client import getPage
from twisted.internet import defer

import socket
from urllib import urlencode, quote
from urllib2 import urlopen, Request, URLError

from SerienRecorderHelpers import *

class SearchSerie(object):
	def __init__(self, serien_name, user_callback=None, user_errback=None):
		self.serien_name = unicode(serien_name, "utf-8")
		#self.serien_name = serien_name
		self.user_callback = user_callback
		self.user_errback  = user_errback

	def	request(self):
		print "[SerienRecorder] request ' %s '" % self.serien_name
		url = "http://www.wunschliste.de/ajax/search_dropdown.pl?%s" % urlencode( { 'q': self.serien_name.encode('utf-8') } )
		getPage(getURLWithProxy(url), agent=getUserAgent(), headers=getHeaders()).addCallback(self.__callback).addErrback(self.__errback, url)

	def request_and_return(self):
		print "[SerienRecorder] request_and_return ' %s '" % self.serien_name
		url = "http://www.wunschliste.de/ajax/search_dropdown.pl?%s" % urlencode( { 'q': self.serien_name.encode('utf-8') } )
		req = Request(getURLWithProxy(url), headers=getHeaders())
		try:
			data = urlopen(req).read()
		except URLError as e:
			self.__errback(str(e), url)
		except socket.timeout as e:
			self.__errback(str(e), url)
		return self.__callback(data)

	def __errback(self, error, url=None):
		print error
		if (self.user_errback):
			self.user_errback(error, url)

	def __callback(self, data):
		serienlist = []
		count_lines = len(data.splitlines())
		if int(count_lines) >= 1:
			for line in data.splitlines():
				raw = re.findall('\+\+\+\t(.*?)\t%s\Z' % self.serien_name.encode('utf-8'), line, re.I | re.S)
				if raw:
					(more, ) = raw
					if more.isdigit(): 
						serienlist.append(("... %s%s'%s'" % (more, _(" weitere Ergebnisse für "), self.serien_name.encode('utf-8')), str(more), "-1"))
				else:
					infos = line.split('|',3)
					if len(infos) == 4:
						(name_Serie, year_Serie, id_Serie, unknown) = infos
						# encode utf-8
						#name_Serie = decodeISO8859_1(name_Serie, True)
						raw = re.findall('(.*?)(\[%s\])?\Z' % self.serien_name.encode('utf-8'), name_Serie, re.I | re.S)
						if raw:
							(name_Serie, x) = raw
							serienlist.append((name_Serie[0], year_Serie, id_Serie))
						else:
							serienlist.append((name_Serie, year_Serie, id_Serie))
		else:
			print "[SerienRecorder] keine Sendetermine für ' %s ' gefunden." % self.serien_name

		if (self.user_callback):
			self.user_callback(serienlist)

		return serienlist
