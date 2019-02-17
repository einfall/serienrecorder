# -*- coding: utf-8 -*-
import email
import imaplib
import quopri
import re
import string
import time
from HTMLParser import HTMLParser

import SerienRecorder
from SerienRecorderHelpers import decrypt, getmac
from Components.config import config
from Screens.MessageBox import MessageBox
from SerienRecorderDatabase import SRDatabase
from SerienRecorderHelpers import TimeHelpers
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderLogWriter import SRLogger

def getEmailData():
	# extract all html parts
	def get_html(email_message_instance):
		maintype = email_message_instance.get_content_maintype()
		if maintype == 'multipart':
			for part in email_message_instance.get_payload():
				if part.get_content_type() == 'text/html':
					return part.get_payload()

	SRLogger.writeLog("\n---------' Lade TV-Planer E-Mail '---------\n", True)

	# get emails
	if len(config.plugins.serienRec.imap_server.value) == 0:
		SRLogger.writeLog("TV-Planer: imap_server nicht gesetzt", True)
		return None

	if len(config.plugins.serienRec.imap_login_hidden.value) == 0:
		SRLogger.writeLog("TV-Planer: imap_login nicht gesetzt", True)
		return None

	if len(config.plugins.serienRec.imap_password_hidden.value) == 0:
		SRLogger.writeLog("TV-Planer: imap_password nicht gesetzt", True)
		return None

	if len(config.plugins.serienRec.imap_mailbox.value) == 0:
		SRLogger.writeLog("TV-Planer: imap_mailbox nicht gesetzt", True)
		return None

	if len(config.plugins.serienRec.imap_mail_subject.value)  == 0:
		SRLogger.writeLog("TV-Planer: imap_mail_subject nicht gesetzt", True)
		return None

	if 1 > config.plugins.serienRec.imap_mail_age.value > 100:
		config.plugins.serienRec.imap_mail_age.value = 1

	try:
		if config.plugins.serienRec.imap_server_ssl.value:
			mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)
		else:
			mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)

	except imaplib.IMAP4.abort:
		SRLogger.writeLog("TV-Planer: Verbindung zum Server fehlgeschlagen", True)
		return None

	except imaplib.IMAP4.error:
		SRLogger.writeLog("TV-Planer: Verbindung zum Server fehlgeschlagen", True)
		return None

	try:
		mail.login(decrypt(getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
				   decrypt(getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))
		print "[serienrecorder]: imap login ok"

	except imaplib.IMAP4.error:
		SRLogger.writeLog("TV-Planer: Anmeldung auf Server fehlgeschlagen", True)
		print "[serienrecorder]: imap login failed"
		return None

	try:
		mail.select(config.plugins.serienRec.imap_mailbox.value)

	except imaplib.IMAP4.error:
		SRLogger.writeLog("TV-Planer: Mailbox %r nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, True)
		return None

	searchstr = TimeHelpers.getMailSearchString()
	try:
		result, data = mail.uid('search', None, searchstr)
		if result != 'OK':
			SRLogger.writeLog("TV-Planer: Fehler bei der Suche nach TV-Planer E-Mails", True)
			SRLogger.writeLog("TV-Planer: %s" % data, True)
			return None

	except imaplib.IMAP4.error:
		SRLogger.writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen" % str(config.plugins.serienRec.imap_mail_age.value), True)
		SRLogger.writeLog("TV-Planer: %s" % searchstr, True)
		return None

	if len(data[0]) == 0:
		SRLogger.writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen" % str(config.plugins.serienRec.imap_mail_age.value), True)
		SRLogger.writeLog("TV-Planer: %s" % searchstr, True)
		return None

	# get the latest email
	latest_email_uid = data[0].split()[-1]
	# fetch the email body (RFC822) for the given UID
	try:
		result, data = mail.uid('fetch', latest_email_uid, '(RFC822)')
	except:
		SRLogger.writeLog("TV-Planer: Laden der E-Mail fehlgeschlagen", True)
		return None

	mail.logout()
	# extract email message including headers and alternate payloads
	email_message = email.message_from_string(data[0][1])
	if len(email_message) == 0:
		SRLogger.writeLog("TV-Planer: leere E-Mail", True)
		return None

	# get html of wunschliste
	html = get_html(email_message)
	if html is None or len(html) == 0:
		SRLogger.writeLog("TV-Planer: leeres HTML", True)
		return None

	# class used for parsing TV-Planer html
	# States and Changes
	# ------------------
	# [error] || [finished] -> [state]
	# [start]: data && '.*TV-Planer.*?den (.*?)' -> <date> -> [time]
	# [time]: data && '\(ab (.*?) Uhr' -> <time> -> [transmission_table]
	# [time]: </div> -> 0:00 -> [transmission_table]
	# [transmission_table]: <table> -> [transmission]
	# [transmission]: <tr> -> [transmission_start]
	# [transmission]: </table> -> [finished]
	# [transmission_start]: >starttime< -> [transmission_url] | [error]
	# [transmission_url]: <a> -> url = href -> [transmission_serie]
	# [transmission_serie]: <strong> -> serie = ''
	# [transmission_serie]: serie += >serie<
	# [transmission_serie]: </strong> -> serie -> [transmission_serie_end]
	# [transmission_serie_end]: <span> -> title == 'Staffel' -> [transmission_season]
	# [transmission_serie_end]: <span> -> title == 'Episode' -> [transmission_episode]
	# [transmission_serie_end]: <span> -> title == 'xxx' -> [transmission_transmission_serie_end]
	# [transmission_serie_end]: <span> -> title != 'Staffel' and title != 'Episode' ->
	#                          save transmission, Staffel = Episode = '0' -> [transmission_title]
	# [transmission_title_end]: <span> -> title == 'Staffel' -> recover transmission, [transmission_season]
	# [transmission_title_end]: <span> -> title == 'Episode' -> recover transmission, [transmission_episode]
	# [transmission_title_end]: <span> -> title == 'xxx' -> -> recover transmission, [transmission_serie_end]
	# [transmission_season]: >season< -> [transmission_serie_end]
	# [transmission_episode]: >episode< -> [transmission_serie_end]
	# [transmission_title]: <span> -> title = ''
	# [transmission_title]: title += >title<
	# [transmission_title]: </span> -> [transmission_title_end]
	# [transmission_title_end]: </div> -> title -> [transmission_desc]
	# [transmission_desc]: <div> -> desc = ''
	# [transmission_desc]: >data< -> data == "bis ..." -> endtime = data -> [transmission_sender] | [error]
	# [transmission_desc]: >data< -> data == 'FREE-TV NEU' or data == 'NEU'
	# [transmission_desc]: desc += >desc<
	# [transmission_desc]: </div> -> desc -> [transmission_endtime]
	# [transmission_endtime]: >endtime< -> [transmission_sender] | [error]
	# [transmission_sender]: <img> sender = title -> [transmission_end]
	# [transmission_end]: </tr> -> [transmission]
	#
	class TVPlaner_HTMLParser(HTMLParser):
		def __init__(self):
			HTMLParser.__init__(self)
			self.state = 'start'
			self.date = ()
			self.transmission = []
			self.transmission_save = []
			self.transmissions = []
			self.season = '0'
			self.episode = '00'
			self.parser_data = ''
		def handle_starttag(self, tag, attrs):
			# print "Encountered a start tag:", tag, attrs
			if self.state == 'time' and tag == 'table':
				# no time - starting at 00:00 Uhr
				self.date = ( self.date, '00:00' )
				self.state = "transmission"
			elif self.state == 'transmission_table' and tag == 'table':
				self.state = 'transmission'
			elif self.state == 'transmission' and tag == 'tr':
				self.state = 'transmission_start'
			elif self.state == 'transmission_start' and tag == 'strong':
				# next day - reset
				self.state = 'transmission'
			elif self.state == 'transmission_url' and tag == 'a':
				href = ''
				for name, value in attrs:
					if name == 'href':
						href = value
						break
				self.transmission.append(href)
				self.state = 'transmission_serie'
			elif self.state == 'transmission_serie' and tag == 'strong':
				self.parser_data = ''
			elif self.state == 'transmission_title' and tag == 'span':
				self.parser_data = ''
			elif self.state == 'transmission_desc' and tag == 'div':
				self.parser_data = ''
			elif self.state == 'transmission_watched' and tag == 'span':
				self.data = ''
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_serie_end' and tag == 'span' :
				found = False
				for name, value in attrs:
					if name == 'title' and value == 'Staffel':
						found = True
						self.state = 'transmission_season'
						break
					elif name == 'title' and value == 'Episode':
						found = True
						self.state = 'transmission_episode'
						break
					elif name == 'title':
						found = True
						break
				if not found:
					# do copy by creating new object for later recovery
					self.transmission_save = self.transmission + []
					self.transmission.append(self.season)
					self.transmission.append(self.episode)
					self.season = '0'
					self.episode = '00'
					self.state = 'transmission_title'
			elif self.state == 'transmission_title_end' and tag == 'span' :
				found = False
				for name, value in attrs:
					if name == 'title' and value == 'Staffel':
						found = True
						self.state = 'transmission_season'
						break
					elif name == 'title' and value == 'Episode':
						found = True
						self.state = 'transmission_episode'
						break
					elif name == 'title':
						found = True
						break
				if found:
					# do copy by creating new object for recovery
					self.transmission = self.transmission_save + []
					self.transmission_save = []
			elif self.state == 'transmission_sender' and tag == 'img':
				# match sender
				for name, value in attrs:
					if name == 'title':
						self.transmission.append(value)
						break
				self.state = 'transmission_end'

		def handle_endtag(self, tag):
			# print "Encountered an end tag :", tag
			if self.state == 'transmission_end' and tag == 'tr':
				print self.transmission
				self.transmissions.append(tuple(self.transmission))
				self.transmission = []
				self.state = 'transmission'
			elif self.state == 'transmission_serie' and tag == 'strong':
				# append collected data
				self.transmission.append(self.parser_data)
				self.parser_data = ''
				self.state = 'transmission_watched'
			elif self.state == 'transmission_title' and tag == 'span':
				# append collected data
				self.transmission.append(self.parser_data)
				self.parser_data = ''
				self.state = 'transmission_title_end'
			elif self.state == 'transmission_title_end' and tag == 'div':
				# consume closing div
				self.state = 'transmission_desc'
			elif self.state == 'transmission_desc' and tag == 'div':
				# append collected data
				self.transmission.append(self.parser_data)
				self.parser_data = ''
				self.state = 'transmission_endtime'
			elif self.state == 'transmission' and tag == 'table':
				# processing finished without error
				self.state = 'finished'

		def handle_data(self, data):
			# print "Encountered some data  : %r" % data
			if self.state == 'finished' or self.state == 'error':
				# do nothing
				self.state = self.state
			elif self.state == 'start':
				# match date
				# 'TV-Planer f=C3=BCr Donnerstag, den 22.12.2016'
				date_regexp=re.compile('.*TV-Planer.*?den ([0-3][0-9]\.[0-1][0-9]\.20[0-9][0-9])')
				find_result = date_regexp.findall(data)
				if find_result:
					self.date = find_result[0]
					self.state = 'time'
			elif self.state == 'time':
				# match time
				# '(ab 05:00 Uhr)'
				time_regexp=re.compile('ab (.*?) Uhr')
				find_result = time_regexp.findall(data)
				if find_result:
					self.date = ( self.date, find_result[0] )
					self.state = 'transmission_table'
			elif self.state == 'transmission_start':
				# match start time
				time_regexp = re.compile('(.*?) Uhr')
				startTime = time_regexp.findall(data)
				if len(startTime) > 0:
					self.transmission.append(startTime[0])
					self.state = 'transmission_url'
				else:
					self.state = 'transmission'
			elif self.state == 'transmission_serie':
				# match serie
				self.parser_data += data
			elif self.state == 'transmission_season':
				# match season
				self.season = data
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_episode':
				# match episode
				self.episode = data
				self.state = 'transmission_serie_end'
			elif self.state == 'transmission_title':
				# match title
				self.parser_data += data
			elif self.state == 'transmission_desc':
				# match description
				if data.startswith('bis:'):
					# may be empty description
					time_regexp=re.compile('bis: (.*?) Uhr.*')
					endTime = time_regexp.findall(data)
					if len(endTime) > 0:
						self.transmission.append('')
						self.transmission.append(endTime[0])
						self.state = 'transmission_sender'
					else:
						self.state = 'error'
				elif data != 'FREE-TV NEU' and data != "NEU":
					self.parser_data += data
			elif self.state == 'transmission_endtime':
				# match end time
				time_regexp=re.compile('bis: (.*?) Uhr.*')
				endTime = time_regexp.findall(data)
				if len(endTime) > 0:
					self.transmission.append(endTime[0])
					self.state = 'transmission_sender'
				else:
					self.state = 'error'
			elif self.state == 'transmission_sender':
				# match sender
				self.transmission.append(data)
				self.state = 'transmission_end'

	# make one line and convert characters
	html = html.replace('=\r\n', '').replace('=\n','').replace('=\r', '').replace('\n', '').replace('\r', '')
	html = html.replace('=3D', '=')

	parser = TVPlaner_HTMLParser()
	html = parser.unescape(html).encode('utf-8')
	if html is None or len(html) == 0:
		SRLogger.writeLog("TV-Planer: leeres HTML nach HTMLParser", True)
		return None
	try:
		parser.feed(html)
		print parser.date
		print parser.transmissions
	except:
		SRLogger.writeLog("TV-Planer: HTML Parsing abgebrochen", True)
		return None

	if parser.state != "finished":
		SRLogger.writeLog("TV-Planer: HTML Parsing mit Fehler beendet", True)
		return None

	# prepare transmissions
	# [ ( seriesName, channel, start, end, season, episode, title, '0' ) ]
	# calculate start time and end time of list in E-Mail
	if len(parser.date) != 2:
		SRLogger.writeLog("TV-Planer: falsches Datumsformat", True)
		return None
	(day, month, year) = parser.date[0].split('.')
	(hour, minute) = parser.date[1].split(':')
	liststarttime_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
	# generate dictionary with final transmissions
	SRLogger.writeLog("Ab dem %s %s Uhr wurden die folgenden Sendungen gefunden:\n" % (parser.date[0], parser.date[1]))
	print "[SerienRecorder] Ab dem %s %s Uhr wurden die folgenden Sendungen gefunden:" % (parser.date[0], parser.date[1])
	transmissiondict = dict()
	for starttime, url, seriesname, season, episode, titel, description, endtime, channel in parser.transmissions:
		if url.startswith('https://www.wunschliste.de/spielfilm'):
			if not config.plugins.serienRec.tvplaner_movies.value:
				SRLogger.writeLog("' %s - Filmaufzeichnung ist deaktiviert '" % seriesname, True)
				print "' %s - Filmaufzeichnung ist deaktiviert '" % seriesname
				continue
			transmissiontype = '[ Film ]'
		elif url.startswith('https://www.wunschliste.de/serie'):
			if not config.plugins.serienRec.tvplaner_series.value:
				SRLogger.writeLog("' %s - Serienaufzeichnung ist deaktiviert '" % seriesname, True)
				print "' %s - Serienaufzeichnung ist deaktiviert '" % seriesname
				continue
			transmissiontype = '[ Serie ]'
		else:
			SRLogger.writeLog("' %s - Ungültige URL %r '" % (seriesname, url), True)
			print "' %s - Serienaufzeichnung ist deaktiviert '" % seriesname
			continue

		# series
		transmission = [ seriesname ]
		# channel
		channel = channel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').strip()
		transmission += [ channel ]
		# start time
		(hour, minute) = starttime.split(':')
		transmissionstart_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionstart_unix < liststarttime_unix:
			transmissionstart_unix = TimeHelpers.getRealUnixTimeWithDayOffset(minute, hour, day, month, year, 1)
		transmission += [ transmissionstart_unix ]
		# end time
		(hour, minute) = endtime.split('.')
		transmissionend_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
		if transmissionend_unix < transmissionstart_unix:
			transmissionend_unix = TimeHelpers.getRealUnixTimeWithDayOffset(minute, hour, day, month, year, 1)
		transmission += [ transmissionend_unix ]
		# season
		if season == '':
			season = '0'
		transmission += [ season ]
		# episode
		if episode == '':
			episode = '00'
		transmission += [ episode ]
		# title
		transmission += [ quopri.decodestring(titel) ]
		# last
		transmission += [ '0' ]
		# url
		transmission += [ url ]
		# store in dictionary transmissiondict[seriesname] = [ seriesname: [ transmission 0 ], [ transmission 1], .... ]
		if seriesname in transmissiondict:
			transmissiondict[seriesname] += [ transmission ]
		else:
			transmissiondict[seriesname] = [ transmission ]
			SRLogger.writeLog("' %s - S%sE%s - %s - %s - %s - %s - %s '" % (transmission[0], str(transmission[4]).zfill(2), str(transmission[5]).zfill(2), transmission[6], transmission[1], time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionstart_unix))), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionend_unix))), transmissiontype), True)
		print "[SerienRecorder] ' %s - S%sE%s - %s - %s - %s - %s - %s'" % (transmission[0], str(transmission[4]).zfill(2), str(transmission[5]).zfill(2), transmission[6], transmission[1], time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionstart_unix))), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionend_unix))), transmissiontype)

	if config.plugins.serienRec.tvplaner_create_marker.value:
		database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)
		for seriesname in transmissiondict.keys():
			# marker isn't in database, create new marker
			# url stored in marker isn't the final one, it is corrected later
			url = transmissiondict[seriesname][0][-1]
			try:
				boxID = None
				if url.startswith('https://www.wunschliste.de/serie'):
					seriesID = SeriesServer().getIDByFSID(url[str.rindex(url, '/') + 1:])
					if seriesID > 0:
						url = 'http://www.wunschliste.de/epg_print.pl?s=%s' % str(seriesID)
					else:
						url = None
					if config.plugins.serienRec.tvplaner_series_activeSTB.value:
						boxID = config.plugins.serienRec.BoxID.value

				if url.startswith('https://www.wunschliste.de/spielfilm') and config.plugins.serienRec.tvplaner_movies_activeSTB.value:
					boxID = config.plugins.serienRec.BoxID.value

				if url and not database.markerExists(url):
					if database.addMarker(url, seriesname, "", boxID):
						SRLogger.writeLog("\nSerien Marker für ' %s ' wurde angelegt" % seriesname, True)
						print "[SerienRecorder] ' %s - Serien Marker erzeugt '" % seriesname
					else:
						SRLogger.writeLog("Serien Marker für ' %s ' konnte nicht angelegt werden" % seriesname, True)
						print "[SerienRecorder] ' %s - Serien Marker konnte nicht angelegt werden '" % seriesname
			except:
				SRLogger.writeLog("Serien Marker für ' %s ' konnte nicht angelegt werden" % seriesname, True)
				print "[SerienRecorder] ' %s - Serien Marker konnte nicht angelegt werden '" % seriesname

	return transmissiondict


def imaptest(session):
	try:
		if config.plugins.serienRec.imap_server_ssl.value:
			mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value,
									 config.plugins.serienRec.imap_server_port.value)
		else:
			mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value,
								 config.plugins.serienRec.imap_server_port.value)

	except:
		session.open(MessageBox, "Verbindung zum E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Verbindung zum Server fehlgeschlagen", True)
		return None

	try:
		mail.login(decrypt(getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
				   decrypt(getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))

	except imaplib.IMAP4.error:
		session.open(MessageBox, "Anmeldung am E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Anmeldung auf Server fehlgeschlagen", True)
		return None

	try:
		import string

		SRLogger.writeLog("Postfächer:", True)
		result, data = mail.list('""', '*')
		if result == 'OK':
			for item in data[:]:
				x = item.split()
				mailbox = string.join(x[2:])
				SRLogger.writeLog("%s" % mailbox, True)
	except imaplib.IMAP4.error:
		session.open(MessageBox, "Abrufen der Postfächer vom E-Mail Server fehlgeschlagen", MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Abrufen der Postfächer fehlgeschlagen", True)

	try:
		mail.select(config.plugins.serienRec.imap_mailbox.value)

	except imaplib.IMAP4.error:
		session.open(MessageBox, "Postfach [%r] nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Mailbox %r nicht gefunden" % config.plugins.serienRec.imap_mailbox.value, True)
		mail.logout()
		return None

	searchstr = TimeHelpers.getMailSearchString()
	SRLogger.writeLog("IMAP Check: %s" % searchstr, True)
	try:
		result, data = mail.uid('search', None, searchstr)
		SRLogger.writeLog("IMAP Check: %s (%d)" % (result, len(data[0].split(' '))), True)
		if result != 'OK':
			SRLogger.writeLog("IMAP Check: %s" % data, True)

	except imaplib.IMAP4.error:
		session.open(MessageBox, "Fehler beim Abrufen der TV-Planer E-Mail", MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Fehler beim Abrufen der Mailbox", True)
		SRLogger.writeLog("IMAP Check: %s" % mail.error.message, True)

	mail.logout()
	session.open(MessageBox, "IMAP Test abgeschlossen - siehe Log", MessageBox.TYPE_INFO, timeout=10)