# -*- coding: utf-8 -*-
import datetime, email, imaplib, os, re, shutil, time

from Components.config import config
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists

from .SerienRecorderHelpers import decrypt, STBHelpers, TimeHelpers, toStr, toBinary, PY2, PY3, PY3_4
from .SerienRecorderDatabase import SRDatabase
from .SerienRecorderSeriesServer import SeriesServer
from .SerienRecorderLogWriter import SRLogger

SERIENRECORDER_TVPLANER_HTML_FILENAME = "TV-Planer.html"
SERIENRECORDER_LONG_TVPLANER_HTML_FILENAME = "TV-Planer_%s%s%s%s%s.html"

def getMailSearchString(age, subject):
	date = datetime.date.today() - datetime.timedelta(age)
	months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
	searchstr = '(SENTSINCE {day:02d}-{month}-{year:04d} SUBJECT "' + subject + '")'
	searchstr = searchstr.format(day=date.day, month=months[date.month - 1], year=date.year)
	return searchstr


def getEmailData():
	# extract all html parts
	def get_html(email_message_instance):
		maintype = email_message_instance.get_content_maintype()
		if maintype == 'multipart':
			for part in email_message_instance.get_payload():
				if part.get_content_type() == 'text/html':
					return part.get_payload()

	print("[SerienRecorder] Loading TV-Planer e-mail")
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
		import socket
		socket.setdefaulttimeout(10)
		if config.plugins.serienRec.imap_server_ssl.value:
			mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)
		else:
			mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value, config.plugins.serienRec.imap_server_port.value)

	except (imaplib.IMAP4.abort, imaplib.IMAP4.error, imaplib.IMAP4.readonly) as e:
		SRLogger.writeLog("TV-Planer: Verbindung zum E-Mail Server fehlgeschlagen [%s]" % str(e), True)
		return None
	except:
		SRLogger.writeLog("TV-Planer: Verbindung zum E-Mail Server fehlgeschlagen [unbekannter Fehler]", True)
		return None

	try:
		mail.login(decrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value),
				   decrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value))
		print("[SerienRecorder] IMAP login ok")

	except imaplib.IMAP4.error as e:
		SRLogger.writeLog("TV-Planer: Anmeldung am Server fehlgeschlagen [%s]" % str(e), True)
		print("[SerienRecorder] IMAP login failed")
		return None

	try:
		result, data = mail.select(config.plugins.serienRec.imap_mailbox.value, False)
		if result != 'OK':
			SRLogger.writeLog("TV-Planer: Mailbox ' %s ' nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(result)))
			mail.logout()
			return None

	except imaplib.IMAP4.error as e:
		SRLogger.writeLog("TV-Planer: Mailbox ' %s ' nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(e)), True)
		mail.logout()
		return None

	searchstr = getMailSearchString(config.plugins.serienRec.imap_mail_age.value, config.plugins.serienRec.imap_mail_subject.value)
	try:
		result, data = mail.uid('search', None, searchstr)
		if result != 'OK':
			SRLogger.writeLog("TV-Planer: Fehler bei der Suche nach TV-Planer E-Mails", True)
			SRLogger.writeLog("TV-Planer: %s" % data, True)
			mail.logout()
			return None

	except imaplib.IMAP4.error as e:
		SRLogger.writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen [%s]" % (str(config.plugins.serienRec.imap_mail_age.value), str(e)), True)
		SRLogger.writeLog("TV-Planer: %s" % searchstr, True)
		mail.logout()
		return None

	if len(data[0]) == 0:
		SRLogger.writeLog("TV-Planer: Keine TV-Planer Nachricht in den letzten %s Tagen" % str(config.plugins.serienRec.imap_mail_age.value), True)
		SRLogger.writeLog("TV-Planer: %s" % searchstr, True)
		mail.logout()
		return None

	# get the latest email
	latest_email_uid = data[0].split()[-1]
	# fetch the email body (RFC822) for the given UID
	try:
		result, data = mail.uid('fetch', latest_email_uid, '(RFC822)')
	except Exception as e:
		SRLogger.writeLog("TV-Planer: Laden der E-Mail fehlgeschlagen [%s]" % str(e), True)
		return None

	mail.logout()
	# extract email message including headers and alternate payloads
	if PY3:
		email_message = email.message_from_bytes(data[0][1])
	else:
		email_message = email.message_from_string(data[0][1])
	if len(email_message) == 0:
		SRLogger.writeLog("TV-Planer: Leere E-Mail", True)
		return None

	# get html of wunschliste
	SRLogger.writeLog("Extrahiere HTML Part der TV-Planer E-Mail.", True)
	html = get_html(email_message)
	if html is None or len(html) == 0:
		SRLogger.writeLog("TV-Planer: Leeres HTML", True)
		return None

	if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_backupHTML.value:
		try:
			SRLogger.writeLog("Erstelle Backup der TV-Planer E-Mail.\n")
			htmlFilePath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_TVPLANER_HTML_FILENAME)
			writeTVPlanerHTML = open(htmlFilePath, "w")
			writeTVPlanerHTML.write(html)
			writeTVPlanerHTML.close()
		except:
			SRLogger.writeLog("TV-Planer: HTML konnte nicht für die Fehlersuche gespeichert werden.", True)

	# make one line and convert characters
	html = html.replace('=\r\n', '').replace('=\n', '').replace('=\r', '').replace('\n', '').replace('\r', '')
	html = html.replace('=3D', '=')

	# Repair incorrect tags in 'IM STREAM' table rows
	html = re.sub('(IM STREAM.*?)(<\/em><\/div>)', '\\1', html, flags=re.S)

	try:

		def getTextContentByTitle(node, titleValue, default):
			titleNodes = node.childNodes.getElementsByAttr('title', titleValue)
			if titleNodes:
				return toStr(titleNodes[0].textContent)
			else:
				return default

		def getEpisodeTitle(node):
			childNodes = node.childNodes.getElementsByTagName('a')
			if childNodes:
				return toStr(childNodes[0].textContent)
			else:
				# Movies does not a link to the episode => only country, year
				childNodes = node.childNodes.getElementsByTagName('span')
				if childNodes:
					return toStr(childNodes[0].textContent)
				else:
					return ''

		from . import AdvancedHTMLParser
		SRLogger.writeLog('Starte HTML Parsing der TV-Planer E-Mail.', True)
		print("[SerienRecorder] TV-Planer: Start HTML parsing")
		parser = AdvancedHTMLParser.IndexedAdvancedHTMLParser()

		if PY2:
			from HTMLParser import HTMLParser
			html = HTMLParser().unescape(html)
		if PY3:
			html = toStr(html)
			if PY3_4:
				import html as HTMLParser
				html = HTMLParser.unescape(html)
			else:
				from html.parser import HTMLParser
				html = HTMLParser().unescape(html)

		parser.parseStr(html)

		# Get tables from HTML
		tables = parser.getElementsByTagName('table')

		# Initialize regular expressions
		date_regexp = re.compile('.*TV-Planer.*?den ([0-3][0-9]\.[0-1][0-9]\.20[0-9][0-9])\s.(?:\(ab (.*?) Uhr\))?')
		url_title_regexp = re.compile('.*<a href="([^\?]+)(?:\?.*)?".*><strong.*>(.*)</strong>')
		endtime_regexp = re.compile('.*bis:\s(.*)\sUhr.*')

		# Get date and time of TV-Planer
		header = toStr(tables[1].getAllChildNodes().getElementsByTagName('div')[0].textContent)
		planerDateTime = date_regexp.findall(header)[0]
		print("[SerienRecorder] TV-Planer date/time: %s" % str(planerDateTime))

		# Get transmissions
		transmissions = []
		transmissionTable = tables[1].getAllChildNodes().getElementsByTagName('table')[0]
		transmissionRows = transmissionTable.childNodes
		for transmissionRow in transmissionRows:
			transmission = []
			if not transmissionRow.hasAttribute('style'):
				transmissionColumns = transmissionRow.childNodes
				# Each transmission row has three columns
				# [0]: Start time
				starttime = toStr(transmissionColumns[0].textContent)
				if starttime != 'Anzeige' and starttime != 'IM STREAM':
					transmission.append(starttime.replace(' Uhr', ''))
					# [1]: URL, Title, Season, Episode, Info
					transmissionColumn = transmissionColumns[1]
					# Season, Episode, Title, Episode info, End time
					episodeInfo = ['0', '00', '', '', '0.00']

					if transmissionColumn.firstChild:
						# First child is always URL + Title
						url_title = url_title_regexp.findall(toStr(transmissionColumn.firstChild.toHTML()))[0]
						transmission.extend(url_title)
					if transmissionColumn.lastChild:
						# Last element => End time (it has to be filled with a time because later on the time will be split)
						endtime = endtime_regexp.findall(toStr(transmissionColumn.lastChild.toHTML()))
						if endtime:
							episodeInfo[4] = endtime[0]

					divPartIndex = 0
					for transmissionPart in transmissionColumn.childNodes:
						if transmissionPart is transmissionColumn.lastChild:
							# Skip part if it is the "last" part
							continue
						if transmissionPart.tagName == 'div' and divPartIndex == 0:
							# First div element => Season / Episode / Title / e.g. NEU
							episodeInfo[0] = getTextContentByTitle(transmissionPart, 'Staffel', '0')
							episodeInfo[1] = getTextContentByTitle(transmissionPart, 'Episode', '00')
							episodeInfo[2] = getEpisodeTitle(transmissionPart)
							divPartIndex += 1
						elif transmissionPart.tagName == 'div' and divPartIndex == 1:
							# Second div element => Episode info
							episodeInfo[3] = toStr(transmissionPart.textContent)

					transmission.extend(episodeInfo)
					# [2] Channel
					transmission.append(toStr(transmissionColumns[2].textContent))
					#print("[SerienRecorder] " + transmission)
					transmissions.append(transmission)

	except Exception as e:
		print("[SerienRecorder] TV-Planer: Break HTML parsing [%s]" % str(e))
		SRLogger.writeLog("TV-Planer: HTML Parsing abgebrochen [%s]" % str(e), True)
		return None

	# prepare transmissions
	# [ ( seriesName, channel, start, end, season, episode, title, '0' ) ]
	# calculate start time and end time of list in E-Mail
	missingTime = False
	if len(planerDateTime) != 2:
		SRLogger.writeLog("TV-Planer: Falsches Datumsformat", True)
		return None
	(day, month, year) = planerDateTime[0].split('.')
	if len(planerDateTime[1]) == 0:
		if transmissions:
			# Get time of first transmission
			(hour, minute) = transmissions[0][0].split(':')
		else:
			missingTime = True
			(hour, minute) = ('00', '00')
	else:
		(hour, minute) = planerDateTime[1].split(':')
	liststarttime_unix = TimeHelpers.getRealUnixTime(minute, hour, day, month, year)
	# generate dictionary with final transmissions
	SRLogger.writeLog("Ab dem %s %s Uhr wurden die folgenden %d Sendungen gefunden:\n" % (planerDateTime[0], planerDateTime[1], len(transmissions)))
	print("[SerienRecorder] TV-Planer: Found %d transmissions from %s %s:" % (len(transmissions), planerDateTime[0], planerDateTime[1]))
	if missingTime:
		SRLogger.writeLog("In der Kopfzeile der TV-Planer E-Mail konnte keine Uhrzeit gefunden werden, bitte die angelegten Timer kontrollieren!\n")
	transmissiondict = dict()

	channels = set()
	import quopri
	for starttime, url, seriesname, season, episode, title, description, endtime, channel in transmissions:
		try:
			if url.startswith('https://www.wunschliste.de/spielfilm'):
				if not config.plugins.serienRec.tvplaner_movies.value:
					SRLogger.writeLog("' %s ' - Filmaufzeichnung ist deaktiviert" % seriesname, True)
					print("[SerienRecorder] TV-Planer: ' %s ' - Movie recording is disabled" % seriesname)
					continue
				transmissiontype = '[ Film ]'
			elif url.startswith('https://www.wunschliste.de/serie'):
				if not config.plugins.serienRec.tvplaner_series.value:
					SRLogger.writeLog("' %s ' - Serienaufzeichnung ist deaktiviert" % seriesname, True)
					print("[SerienRecorder] TV-Planer: ' %s ' - Series recording is disabled" % seriesname)
					continue
				transmissiontype = '[ Serie ]'
			else:
				SRLogger.writeLog("' %s ' - Ungültige URL [%s]" % (seriesname, str(url)), True)
				print("[SerienRecorder] TV-Planer: ' %s ' - Invalid URL [%s]" % seriesname, str(url))
				continue

			# get fernsehserie ID from URL
			fsID = url[str.rindex(url, '/') + 1:]

			# series
			transmission = [ seriesname ]
			# channel
			channel = channel.replace(' (Pay-TV)','').replace(' (Schweiz)','').replace(' (GB)','').replace(' (Österreich)','').replace(' (USA)','').replace(' (RP)','').replace(' (F)','').strip()
			channels.add(channel)
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
			transmission += [ toStr(quopri.decodestring(toBinary(title))) ]
			# last
			transmission += [ '0' ]
			# url
			transmission += [ url ]
			# store in dictionary transmissiondict[fsID] = [ seriesname: [ transmission 0 ], [ transmission 1], .... ]
			if fsID in transmissiondict:
				transmissiondict[fsID] += [ transmission ]
			else:
				transmissiondict[fsID] = [ transmission ]
			log = "' %s - S%sE%s - %s ' - %s - %s - %s - %s" % (transmission[0], str(transmission[4]).zfill(2), str(transmission[5]).zfill(2), transmission[6], transmission[1], time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionstart_unix))), time.strftime("%d.%m.%Y %H:%M", time.localtime(int(transmissionend_unix))), transmissiontype)
			SRLogger.writeLog(log, True)
			print("[SerienRecorder] TV-Planer: %s" % log)
		except Exception as e:
			print("[SerienRecorder] TV-Planer: Processing TV-Planer e-mail failed: [%s]" % str(e))
			SRLogger.writeLog("TV-Planer Verarbeitung fehlgeschlagen! [%s]" % str(e), True)

	# Check channels
	print("[SerienRecorder] TV-Planer: Check channels...")
	from .SerienRecorder import serienRecDataBaseFilePath
	database = SRDatabase(serienRecDataBaseFilePath)
	webChannels = database.getActiveChannels()
	for channel in channels:
		if channel not in webChannels:
			SRLogger.writeLogFilter("channels", "\nDer Sender ' %s ' wurde in der TV-Planer E-Mail gefunden, ist aber im SerienRecorder nicht zugeordnet." % channel)

	# Create marker
	SRLogger.writeLog("\n", True)
	print("[SerienRecorder] TV-Planer: Create markers...")
	for fsID in list(transmissiondict.keys()):
		print("[SerienRecorder] TV-Planer: Check whether or not a marker exists for fsid: [%s]" % str(fsID))
		# marker isn't in database, create new marker
		# url stored in marker isn't the final one, it is corrected later
		url = transmissiondict[fsID][0][-1]
		seriesname = transmissiondict[fsID][0][0]
		marker_type = "Serien-Marker"
		try:
			boxID = None
			seriesInfo = ""
			if url.startswith('https://www.wunschliste.de/serie'):
				seriesID = SeriesServer().getIDByFSID(fsID)
				if seriesID == 0:
					seriesID = SeriesServer().getSeriesIDBySearch(seriesname, fsID)

				if seriesID > 0:
					url = str(seriesID)
					data = SeriesServer().getSeriesNamesAndInfoByWLID([seriesID])
					if data:
						seriesInfo = data[0]['info']
				else:
					url = None
				if config.plugins.serienRec.tvplaner_series_activeSTB.value:
					boxID = config.plugins.serienRec.BoxID.value
			elif url.startswith('https://www.wunschliste.de/spielfilm'):
				marker_type = "temporärer Serien-Marker"
				if config.plugins.serienRec.tvplaner_movies_activeSTB.value:
					boxID = config.plugins.serienRec.BoxID.value
			else:
				url = None

			if url:
				if database.addMarker(url, seriesname, seriesInfo, fsID, boxID, 1 if url.startswith('https://www.wunschliste.de/spielfilm') else 0):
					if len(seriesInfo) == 0:
						SRLogger.writeLog("Ein %s für ' %s ' wurde angelegt" % (marker_type, seriesname), True)
					else:
						SRLogger.writeLog("Ein %s für ' %s ' (%s) wurde angelegt" % (marker_type, seriesname, seriesInfo), True)
					print("[SerienRecorder] TV-Planer: %s created ' %s ' (%s)" % (marker_type, seriesname, seriesInfo))
		except Exception as e:
			SRLogger.writeLog("%s für ' %s ' konnte wegen eines Fehlers nicht angelegt werden [%s]" % (marker_type, seriesname, str(e)), True)
			print("[SerienRecorder] TV-Planer: %s - %s could not been created [%s]" % (seriesname, marker_type, str(e)))

	return transmissiondict


def imaptest(session):
	import ssl

	try:
		SRLogger.writeLog("IMAP Check: Versuche Verbindung zum IMAP Server [%s:%s] aufzubauen..." % (str(config.plugins.serienRec.imap_server.value), str(config.plugins.serienRec.imap_server_port.value)))
		import socket
		socket.setdefaulttimeout(10)
		if config.plugins.serienRec.imap_server_ssl.value:
			mail = imaplib.IMAP4_SSL(config.plugins.serienRec.imap_server.value,
									 config.plugins.serienRec.imap_server_port.value)
		else:
			mail = imaplib.IMAP4(config.plugins.serienRec.imap_server.value,
								 config.plugins.serienRec.imap_server_port.value)


	except (imaplib.IMAP4.abort, imaplib.IMAP4.error, imaplib.IMAP4.readonly, ssl.SSLError) as e:
		session.open(MessageBox, "Verbindung zum E-Mail Server fehlgeschlagen [%s]" % str(e), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Verbindung zum Server fehlgeschlagen [%s]" % str(e), True)
		return None
	except:
		import sys
		e = sys.exc_info()[0]
		session.open(MessageBox, "Verbindung zum E-Mail Server fehlgeschlagen [%s]" % str(e), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Verbindung zum E-Mail Server fehlgeschlagen [%s]" % str(e), True)
		return None

	try:
		username = decrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_login_hidden.value)
		blured_username = "".join("*" if i % 2 == 0 else char for i, char in enumerate(username, 1))
		password = decrypt(STBHelpers.getmac("eth0"), config.plugins.serienRec.imap_password_hidden.value)
		blured_password = "".join("*" if i % 2 == 0 else char for i, char in enumerate(password, 1))

		SRLogger.writeLog("IMAP Check: Versuche Anmeldung am Server mit [%s] und Kennwort [%s]..." % (blured_username, blured_password))
		mail.login(username, password)

	except imaplib.IMAP4.error as e:
		session.open(MessageBox, "Anmeldung am E-Mail Server fehlgeschlagen [%s]" % str(e), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Anmeldung auf Server fehlgeschlagen [%s]" % str(e), True)
		return None

	try:
		def parse_mailbox(data):
			import re
			matches = re.match('\((.*?)\)\s"?(.*?)"?\s"?(.*?)"?$', data)
			return matches.group(1), matches.group(2), matches.group(3)

		SRLogger.writeLog("Versuche Postfächer vom E-Mail Server abzurufen...", True)
		result, data = mail.list('""', '*')
		if result == 'OK':
			print("[SerienRecorder] Mailboxes %s" % data)
			SRLogger.writeLog("Postfächer:", True)
			for item in data:
				flags, separator, name = parse_mailbox(toStr(item))
				print("[SerienRecorder] %30s : Flags = [%s], Separator = [%s]" % (toStr(name), toStr(flags), toStr(separator)))
				SRLogger.writeLog(toStr(name), True)

	except imaplib.IMAP4.error as e:
		session.open(MessageBox, "Abrufen der Postfächer vom E-Mail Server fehlgeschlagen [%s]" % str(e), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Abrufen der Postfächer fehlgeschlagen [%s]" % str(e), True)

	try:
		SRLogger.writeLog("IMAP Check: Versuche Postfach [%s] auszuwählen..." % str(config.plugins.serienRec.imap_mailbox.value))

		result, data = mail.select(config.plugins.serienRec.imap_mailbox.value, True)
		if result != 'OK':
			session.open(MessageBox, "Postfach [%s] nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(result)), MessageBox.TYPE_INFO, timeout=10)
			SRLogger.writeLog("IMAP Check: Postfach %s nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(result)), True)
			mail.logout()
			return None

	except imaplib.IMAP4.error as e:
		session.open(MessageBox, "Postfach [%s] nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(e)), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Postfach %s nicht gefunden [%s]" % (config.plugins.serienRec.imap_mailbox.value, str(e)), True)
		mail.logout()
		return None

	searchstr = getMailSearchString(config.plugins.serienRec.imap_mail_age.value, config.plugins.serienRec.imap_mail_subject.value)
	SRLogger.writeLog("IMAP Check: %s" % searchstr, True)
	try:
		result, data = mail.uid('search', None, searchstr)
		mail_count = 0
		if len(data[0]) > 0:
			mail_count = len(toStr(data[0]).split(' '))

		SRLogger.writeLog("IMAP Check: %s (%d)" % (result, mail_count), True)
		if result != 'OK':
			SRLogger.writeLog("IMAP Check: %s" % data, True)

	except imaplib.IMAP4.error as e:
		session.open(MessageBox, "Fehler beim Abrufen der TV-Planer E-Mails [%s]" % str(e), MessageBox.TYPE_INFO, timeout=10)
		SRLogger.writeLog("IMAP Check: Fehler beim Abrufen der TV-Planer E-Mails [%s]" % str(e), True)
		SRLogger.writeLog("IMAP Check: %s" % mail.error.message, True)

	mail.logout()
	session.open(MessageBox, "IMAP Test abgeschlossen - siehe Log", MessageBox.TYPE_INFO, timeout=10)


def resetTVPlanerHTMLBackup():
	if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_backupHTML.value:
		backup_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_TVPLANER_HTML_FILENAME)

		if not config.plugins.serienRec.longLogFileName.value:
			# logFile leeren (renamed to .old)
			if fileExists(backup_filepath):
				shutil.move(backup_filepath, "%s.old" % backup_filepath)
		else:
			lt = datetime.datetime.now() - datetime.timedelta(days=config.plugins.serienRec.deleteLogFilesOlderThan.value)
			for filename in os.listdir(config.plugins.serienRec.LogFilePath.value):
				long_backup_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, filename)
				if (filename.find('TV-Planer_') == 0) and (int(os.path.getmtime(long_backup_filepath)) < int(lt.strftime("%s"))):
					try:
						os.remove(long_backup_filepath)
					except:
						SRLogger.writeLog("TV-Planer HTML Backup konnte nicht gelöscht werden: %s" % long_backup_filepath, True)

		open(backup_filepath, 'w').close()

def backupTVPlanerHTML():
	if config.plugins.serienRec.tvplaner.value and config.plugins.serienRec.tvplaner_backupHTML.value and config.plugins.serienRec.longLogFileName.value:
		lt = time.localtime()
		backup_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_TVPLANER_HTML_FILENAME)
		long_backup_filepath = os.path.join(config.plugins.serienRec.LogFilePath.value, SERIENRECORDER_LONG_TVPLANER_HTML_FILENAME % (str(lt.tm_year), str(lt.tm_mon).zfill(2), str(lt.tm_mday).zfill(2), str(lt.tm_hour).zfill(2), str(lt.tm_min).zfill(2)))
		shutil.copy(backup_filepath, long_backup_filepath)
