# -*- coding: utf-8 -*-
import pickle
import shutil
import sqlite3
import time

import SerienRecorderHelpers
import SerienRecorder
import SerienRecorderSeriesServer

class SRDatabase:
	def __init__(self, dbfilepath):
		self._dbfilepath = dbfilepath
		self._srDBConn = None
		self.connect()

	def __del__(self):
		self.close()

	def connect(self):
		self._srDBConn = sqlite3.connect(self._dbfilepath)
		self._srDBConn.isolation_level = None
		self._srDBConn.text_factory = lambda x: str(x.decode("utf-8"))

	def close(self):
		if self._srDBConn:
			self._srDBConn.close()
			self._srDBConn = None

	def initialize(self, version):
		"""
		Initialize the database by creating all necassary tables
		:param version:
		:type version:
		"""
		cur = self._srDBConn.cursor()
		cur.execute('''CREATE TABLE IF NOT EXISTS dbInfo (Key TEXT NOT NULL UNIQUE, 
																   Value TEXT NOT NULL DEFAULT "")''')

		cur.execute('''CREATE TABLE IF NOT EXISTS Channels (WebChannel TEXT NOT NULL UNIQUE,
																		STBChannel TEXT NOT NULL DEFAULT "", 
																		ServiceRef TEXT NOT NULL DEFAULT "", 
																		alternativSTBChannel TEXT NOT NULL DEFAULT "", 
																		alternativServiceRef TEXT NOT NULL DEFAULT "", 
																		Erlaubt INTEGER DEFAULT 0, 
																		Vorlaufzeit INTEGER DEFAULT NULL, 
																		Nachlaufzeit INTEGER DEFAULT NULL,
																		vps INTEGER DEFAULT 0)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS SerienMarker (ID INTEGER PRIMARY KEY AUTOINCREMENT, 
																			Serie TEXT NOT NULL, 
																			Url TEXT NOT NULL, 
																			AufnahmeVerzeichnis TEXT, 
																			AlleStaffelnAb INTEGER DEFAULT 0, 
																			alleSender INTEGER DEFAULT 1, 
																			Vorlaufzeit INTEGER DEFAULT NULL, 
																			Nachlaufzeit INTEGER DEFAULT NULL, 
																			AufnahmezeitVon INTEGER DEFAULT NULL,
																			AufnahmezeitBis INTEGER DEFAULT NULL, 
																			AnzahlWiederholungen INTEGER DEFAULT NULL,
																			preferredChannel INTEGER DEFAULT 1,
																			useAlternativeChannel INTEGER DEFAULT -1,
																			AbEpisode INTEGER DEFAULT 0,
																			Staffelverzeichnis INTEGER DEFAULT -1,
																			TimerForSpecials INTEGER DEFAULT 0,
																			vps INTEGER DEFAULT NULL,
																			excludedWeekdays INTEGER DEFAULT NULL,
																			tags TEXT,
																			addToDatabase INTEGER DEFAULT 1)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS SenderAuswahl (ID INTEGER, 
																			 ErlaubterSender TEXT NOT NULL, 
																			 FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS StaffelAuswahl (ID INTEGER, 
																			  ErlaubteStaffel INTEGER, 
																			  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																		  ErlaubteSTB INTEGER, 
																		  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer (Serie TEXT NOT NULL, 
																			  Staffel TEXT, 
																			  Episode TEXT, 
																			  Titel TEXT, 
																			  StartZeitstempel INTEGER NOT NULL, 
																			  ServiceRef TEXT NOT NULL, 
																			  webChannel TEXT NOT NULL, 
																			  EventID INTEGER DEFAULT 0,
																			  TimerAktiviert INTEGER DEFAULT 1)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																			  StartZeitstempel INTEGER NOT NULL, 
																			  webChannel TEXT NOT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																		  Staffel TEXT NOT NULL, 
																		  Episode TEXT NOT NULL,
																		  AnzahlWiederholungen INTEGER DEFAULT NULL)''')

		cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('Version', ?)", [version])
		cur.close()

	def getVersion(self):
		"""
		Returns the database version from dbInfo table
		:return:
		:rtype:
		"""
		dbVersion = None
		try:
			cur = self._srDBConn.cursor()
			cur.execute("SELECT Value FROM dbInfo WHERE Key='Version'")
			row = cur.fetchone()
			if row:
				(dbVersion,) = row
			cur.close()
		except:
			pass

		return dbVersion

	def update(self, version):
		"""
		Update database if too old
		:return:
		:rtype:
		"""
		try:
			cur = self._srDBConn.cursor()
			cur.execute('DROP TABLE NeuerStaffelbeginn')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD AbEpisode INTEGER DEFAULT 0')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD Staffelverzeichnis INTEGER DEFAULT -1')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD TimerForSpecials INTEGER DEFAULT 0')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE AngelegteTimer ADD TimerAktiviert INTEGER DEFAULT 1')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE Channels ADD vps INTEGER DEFAULT 0')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD vps INTEGER DEFAULT NULL')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD excludedWeekdays INTEGER DEFAULT NULL')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD tags TEXT')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute('ALTER TABLE SerienMarker ADD addToDatabase INTEGER DEFAULT 1')
			cur.close()
		except:
			pass

		try:
			cur = self._srDBConn.cursor()
			cur.execute("UPDATE AngelegteTimer SET Episode = '00' WHERE rowid IN (SELECT rowid  FROM AngelegteTimer WHERE Staffel='0' AND (Episode='' OR Episode='0'))")
			cur.close()
		except:
			pass

		try:
			# Update Series-Markers
			markers = self.getMarkerNamesAndWLID()
			changedMarkers = SerienRecorderHelpers.getChangedSeriesNames(markers)
			SerienRecorder.writeLog("Es wurden %d geänderte Seriennamen gefunden" % len(changedMarkers), True)

			cur = self._srDBConn.cursor()
			for key, val in changedMarkers.items():
				cur.execute("UPDATE SerienMarker SET Serie = ? WHERE Url = ?", (val[1], 'http://www.wunschliste.de/epg_print.pl?s=' + key))
				SerienRecorder.writeLog("SerienMarker Tabelle aktualisiert [%s] => [%s]: %d" % (val[0], val[1], cur.rowcount), True)
				cur.execute("UPDATE AngelegteTimer SET Serie = ? WHERE TRIM(Serie) = ?", (val[1], val[0]))
				SerienRecorder.writeLog("AngelegteTimer Tabelle aktualisiert [%s]: %d" % (val[1], cur.rowcount), True)
				cur.execute("UPDATE Merkzettel SET Serie = ? WHERE TRIM(Serie) = ?", (val[1], val[0]))
				SerienRecorder.writeLog("Merkzettel Tabelle aktualisiert [%s]: %d" % (val[1], cur.rowcount), True)
			cur.close()
		except:
			pass

		cur = self._srDBConn.cursor()
		cur.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  webChannel TEXT NOT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																  Staffel TEXT NOT NULL, 
																  Episode TEXT NOT NULL,
																  AnzahlWiederholungen INTEGER DEFAULT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																  ErlaubteSTB INTEGER, 
																  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute("UPDATE OR IGNORE dbInfo SET Value=? WHERE Key='Version'", [version])
		cur.close()

	def optimize(self):
		cur = self._srDBConn.cursor()
		cur.execute("ANALYZE")
		cur.execute("ANALYZE sqlite_master")
		cur.close()

	def rebuild(self):
		cur = self._srDBConn.cursor()
		cur.execute("VACUUM")
		cur.close()

	def backup(self, backupFilePath):
		cur = self._srDBConn.cursor()
		# Lock database
		cur.execute("begin immediate")
		shutil.copy(self._dbfilepath, backupFilePath)
		# Unlock
		self._srDBConn.rollback()

	def hasMarkers(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM SerienMarker")
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def hasChannels(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM Channels")
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def hasBookmark(self, series, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (series.lower(), str(season).lower(), str(episode).zfill(2).lower()))
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def getBookmarks(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT * FROM Merkzettel")
		rows = cur.fetchall()
		cur.close()
		return rows

	def addBookmark(self, series, fromEpisode, toEpisode, season, globalNumberOfRecordings):
		if int(fromEpisode) != 0 or int(toEpisode) != 0:
			numberOfRecordings = globalNumberOfRecordings
			cur = self._srDBConn.cursor()
			cur.execute("SELECT AnzahlWiederholungen FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
			row = cur.fetchone()
			if row:
				(AnzahlWiederholungen,) = row
				if str(AnzahlWiederholungen).isdigit():
					numberOfRecordings = int(AnzahlWiederholungen)
			for i in range(int(fromEpisode), int(toEpisode) + 1):
				print "[SerienRecorder] %s Staffel: %s Episode: %s " % (str(series), str(season), str(i))
				cur.execute("SELECT * FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (series.lower(), season.lower(), str(i).zfill(2).lower()))
				row = cur.fetchone()
				if not row:
					cur.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?)", (series, season, str(i).zfill(2), numberOfRecordings))
			cur.close()
			return True
		else:
			return False

	def updateBookmark(self, series, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (series.lower(), str(season).lower(), episode.lower()))
		cur.close()

	def removeBookmark(self, series, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM Merkzettel WHERE LOWER(SERIE)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (series.lower(), str(season).lower(), episode.lower()))
		cur.close()

	def removeBookmarks(self, data):
		cur = self._srDBConn.cursor()
		cur.executemany("DELETE FROM Merkzettel WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", data)
		cur.close()

	def removeAllBookmarks(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM Merkzettel")
		cur.close()


	def addTimerConflict(self, message, startUnixtime, channel):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT OR IGNORE INTO TimerKonflikte (Message, StartZeitstempel, webChannel) VALUES (?, ?, ?)", (message, int(startUnixtime), channel))
		cur.close()

	def removeExpiredTimerConflicts(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM TimerKonflikte WHERE StartZeitstempel<=?", [int(time.time())])
		cur.close()

	def removeAllTimerConflicts(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM TimerKonflikte")
		cur.close()

	def getTimerConflicts(self):
		conflicts = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT * FROM TimerKonflikte ORDER BY StartZeitstempel")
		rows = cur.fetchall()
		for row in rows:
			conflicts.append(row)
		cur.close()
		return conflicts

	def removeMovieMarkers(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM SerienMarker WHERE Url LIKE 'https://www.wunschliste.de/spielfilm%'")
		cur.close()


	def getRecordDirectories(self, defaultSavePath):
		directories = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT distinct(AufnahmeVerzeichnis) FROM SerienMarker WHERE AufnahmeVerzeichnis NOT NULL")
		rows = cur.fetchall()
		for row in rows:
			(AufnahmeVerzeichnis,) = row
			if AufnahmeVerzeichnis:
				directories.append(AufnahmeVerzeichnis)
		cur.close()
		if defaultSavePath not in directories:
			directories.append(defaultSavePath)
		return directories

	def getDirNames(self, series):
		result = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, Url FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			result = row
		cur.close()
		return result

	def getMargins(self, series, channel, globalMarginBefore, globalMarginAfter):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT MAX(IFNULL(SerienMarker.Vorlaufzeit, -1), IFNULL(Channels.Vorlaufzeit, -1)), MAX(IFNULL(SerienMarker.Nachlaufzeit, -1), IFNULL(Channels.Nachlaufzeit, -1)) FROM SerienMarker, Channels WHERE LOWER(SerienMarker.Serie)=? AND LOWER(Channels.WebChannel)=?", (series.lower(), channel.lower()))
		row = cur.fetchone()
		if not row:
			margin_before = globalMarginBefore
			margin_after = globalMarginAfter
		else:
			(margin_before, margin_after) = row

		if margin_before is None or margin_before is -1:
			margin_before = globalMarginBefore

		if margin_after is None or margin_after is -1:
			margin_after = globalMarginAfter

		cur.close()
		return margin_before, margin_after

	def getVPS(self, series, channel):
		result = 0
		cur = self._srDBConn.cursor()
		cur.execute("SELECT CASE WHEN SerienMarker.vps IS NOT NULL AND SerienMarker.vps IS NOT '' THEN SerienMarker.vps ELSE Channels.vps END as vps FROM Channels,SerienMarker WHERE LOWER(Channels.WebChannel)=? AND LOWER(SerienMarker.Serie)=?", (channel.lower(), series.lower()))
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		return bool(result & 0x1), bool(result & 0x2)

	def getTags(self, series):
		tags = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT tags FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(tagString,) = row
			if tagString is not None and len(tagString) > 0:
				tags = pickle.loads(tagString)
		cur.close()
		return tags

	def getAddToDatabase(self, series):
		result = True
		cur = self._srDBConn.cursor()
		cur.execute("SELECT addToDatabase FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		return bool(result)

	def getSpecialsAllowed(self, series):
		TimerForSpecials = False
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AlleStaffelnAb, TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(AlleStaffelnAb, TimerForSpecials,) = row
			if int(AlleStaffelnAb) == 0:
				TimerForSpecials = True
			elif not str(TimerForSpecials).isdigit():
				TimerForSpecials = False
		cur.close()
		return bool(TimerForSpecials)

	def getTimeSpan(self, series, globalTimeFrom, globalTimeTo):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmezeitVon, AufnahmezeitBis FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(fromTime, toTime) = row
			if not str(fromTime).isdigit():
				fromTime = (globalTimeFrom[0] * 60) + globalTimeFrom[1]
			if not str(toTime).isdigit():
				toTime = (globalTimeTo[0] * 60) + globalTimeTo[1]
		else:
			fromTime = (globalTimeFrom[0] * 60) + globalTimeFrom[1]
			toTime = (globalTimeTo[0] * 60) + globalTimeTo[1]
		cur.close()
		return fromTime, toTime

	def getAllMarkerStatusForBoxID(self, boxID):
		markers = {}
		cur = self._srDBConn.cursor()
		cur.execute("SELECT SUBSTR(Url, INSTR(Url, '=') + 1)  AS wl_id, ErlaubteSTB FROM SerienMarker LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID")
		rows = cur.fetchall()
		for row in rows:
			try:
				(wl_id, allowedSTB) = row
				seriesActivated = True
				if allowedSTB is not None and not (allowedSTB & (1 << (int(boxID) - 1))):
					seriesActivated = False
				markers[int(wl_id)] = seriesActivated
			except:
				continue
		cur.close()
		return markers

	def getMarkerNamesAndWLID(self):
		cur = self._srDBConn.cursor()
		sql = "SELECT Serie, SUBSTR(Url, INSTR(Url, '=') + 1)  AS wl_id FROM SerienMarker"
		cur.execute(sql)
		markers = cur.fetchall()
		cur.close()
		return markers

	def getAllMarkers(self, sortLikeWL):
		cur = self._srDBConn.cursor()
		sql = "SELECT SerienMarker.ID, Serie, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, COUNT(StaffelAuswahl.ID) AS ErlaubteStaffelCount FROM SerienMarker LEFT JOIN StaffelAuswahl ON StaffelAuswahl.ID = SerienMarker.ID LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID GROUP BY Serie"
		if sortLikeWL:
			sql += " ORDER BY REPLACE(REPLACE(REPLACE(REPLACE(LOWER(Serie), 'the ', ''), 'das ', ''), 'die ', ''), 'der ', '')"
		else:
			sql += " ORDER BY LOWER(Serie)"
		cur.execute(sql)
		markers = cur.fetchall()
		cur.close()
		return markers

	def getMarkerSettings(self, series):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if not row:
			row = (None, -1, None, None, None, None, None, 1, -1, None, None, "", 1)
		cur.close()
		return row

	def setMarkerSettings(self, series, settings):
		data = settings + (series.lower(), )
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE SerienMarker SET AufnahmeVerzeichnis=?, Staffelverzeichnis=?, Vorlaufzeit=?, Nachlaufzeit=?, AnzahlWiederholungen=?, AufnahmezeitVon=?, AufnahmezeitBis=?, preferredChannel=?, useAlternativeChannel=?, vps=?, excludedWeekdays=?, tags=?, addToDatabase=? WHERE LOWER(Serie)=?"
		cur.execute(sql, data)
		cur.close()

	def getTimer(self, dayOffset):
		timer = []
		cur = self._srDBConn.cursor()
		dayOffsetInSeconds = dayOffset * 86400
		sql = "SELECT LOWER(Serie), StartZeitstempel, LOWER(webChannel) FROM AngelegteTimer WHERE (StartZeitstempel >= STRFTIME('%s', CURRENT_DATE)+?) AND (StartZeitstempel < (STRFTIME('%s', CURRENT_DATE)+?+86399))"
		cur.execute(sql, (dayOffsetInSeconds, dayOffsetInSeconds))
		rows = cur.fetchall()
		for row in rows:
			(seriesName, startTimestamp, webChannel) = row
			timer.append((seriesName, startTimestamp, webChannel))
		cur.close()
		return timer

	def addMarker(self, url, name, boxID):
		result = False
		cur = self._srDBConn.cursor()
		cur.execute("SELECT * FROM SerienMarker WHERE LOWER(Serie)=?", [name.lower()])
		row = cur.fetchone()
		if not row:
			cur.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials) VALUES (?, ?, 0, 1, 1, -1, 0, -1, 0)", (name, url))
			if boxID:
				erlaubteSTB = 0xFFFF
				erlaubteSTB |= (1 << (int(boxID) - 1))
				cur.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)",(cur.lastrowid, erlaubteSTB))
			result = True
		cur.close()
		return result

	def markerExists(self, url):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM SerienMarker WHERE Url=?", [url])
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def updateMarkerURL(self, series, url):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE SerienMarker SET Url=? WHERE LOWER(Serie)=?", (url, series.lower()))
		cur.close()

	def getPreferredMarkerChannels(self, series, globalUseAlternativeChannel, globalNumberOfRecordings):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AnzahlWiederholungen, preferredChannel, useAlternativeChannel FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(numberOfRecordings, preferredChannel, useAlternativeChannel) = row
			if useAlternativeChannel == -1:
				useAlternativeChannel = globalUseAlternativeChannel
			useAlternativeChannel = bool(useAlternativeChannel)
			if not numberOfRecordings:
				numberOfRecordings = globalNumberOfRecordings
		else:
			preferredChannel = 1
			useAlternativeChannel = False
			numberOfRecordings = globalNumberOfRecordings
		return numberOfRecordings, preferredChannel, useAlternativeChannel

	def getMarkerURL(self, series):
		Url = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Url FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(Url, ) = row
		cur.close()
		return Url

	def getMarkerID(self, series):
		makerID = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		row = cur.fetchone()
		if row:
			(markerID, ) = row
		cur.close()
		return markerID

	def getMarkerNames(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Serie FROM SerienMarker ORDER BY Serie")
		rows = cur.fetchall()
		cur.close()
		return rows

	def getMarkerSeasonAndChannelSettings(self, name):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, AlleStaffelnAb, alleSender FROM SerienMarker WHERE LOWER(Serie)=?", [name.lower()])
		row = cur.fetchone()
		if not row:
			row = (0, 999999, 0)
		cur.close()
		return row

	def getMarkerSeasonSettings(self, name):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, AlleStaffelnAb, AbEpisode, TimerForSpecials FROM SerienMarker WHERE LOWER(Serie)=?", [name.lower()])
		row = cur.fetchone()
		cur.close()
		return row

	def updateMarkerSeasonAndChannelSettings(self, markerID, oldSeason, newSeason, oldChannel, newChannel):
		cur = self._srDBConn.cursor()
		if str(newSeason).isdigit():
			if oldSeason > newSeason:
				cur.execute("SELECT * FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel=?", (markerID, newSeason))
				row = cur.fetchone()
				if not row:
					self.setMarkerSeason(markerID, newSeason)
					cur.execute("SELECT * FROM StaffelAuswahl WHERE ID=? ORDER BY ErlaubteStaffel DESC", [markerID])
					seasons = cur.fetchall()
					for row in seasons:
						(ID, ErlaubteStaffel) = row
						if oldSeason == (ErlaubteStaffel + 1):
							oldSeason = ErlaubteStaffel
						else:
							break
					cur.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=? WHERE ID=?",(oldSeason, markerID))
					cur.execute("DELETE FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel>=?",(markerID, oldSeason))
		else:
			cur.execute("UPDATE OR IGNORE SerienMarker SET TimerForSpecials=1 WHERE ID=?", [markerID])

		if not oldChannel:
			cur.execute("SELECT * FROM SenderAuswahl WHERE ID=? AND ErlaubterSender=?", (markerID, newChannel))
			row = cur.fetchone()
			if not row:
				self.setMarkerChannel(markerID, newChannel)

		cur.close()

	def setMarkerChannel(self, markerID, channel):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", (markerID, channel))
		cur.close()

	def setMarkerChannels(self, data):
		cur = self._srDBConn.cursor()
		cur.executemany("INSERT OR IGNORE INTO SenderAuswahl (ID, ErlaubterSender) VALUES (?, ?)", data)
		cur.close()

	def setMarkerSeason(self, markerID, season):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT OR IGNORE INTO StaffelAuswahl (ID, ErlaubteStaffel) VALUES (?, ?)", (markerID, season))
		cur.close()

	def updateMarkerSeasonsSettings(self, series, fromSeason, fromEpisode, specials):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=?, AbEpisode=?, TimerForSpecials=? WHERE LOWER(Serie)=?", (fromSeason, fromEpisode, specials, series.lower()))
		cur.close()

	def setAllChannelsToMarker(self, series, allChannels):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET alleSender=? WHERE LOWER(Serie)=?", (allChannels, series.lower()))
		cur.close()

	def setMarkerEpisode(self, series, fromEpisode):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET AbEpisode=? WHERE LOWER(Serie)=?", (int(fromEpisode), series.lower()))
		cur.close()

	def changeMarkerStatus(self, name, boxID):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [name.lower()])
		row = cur.fetchone()
		if row:
			(ID, ErlaubteSTB) = row
			if ErlaubteSTB is not None:
				ErlaubteSTB ^= (1 << (int(boxID) - 1))
				cur.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=? WHERE ID=?", (ErlaubteSTB, ID))
		cur.close()

	def setMarkerStatus(self, name, boxID, state):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [name.lower()])
		row = cur.fetchone()
		if row:
			(ID, ErlaubteSTB) = row
			if ErlaubteSTB is not None:
				if state:
					# Switch on
					ErlaubteSTB |= (1 << (int(boxID) - 1))
				else:
					# Switch off
					ErlaubteSTB &= ~(1 << (int(boxID) - 1))
				cur.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=? WHERE ID=?", (ErlaubteSTB, ID))
		cur.close()

	def disableAllMarkers(self, boxID):
		cur = self._srDBConn.cursor()
		mask = (1 << (int(boxID) - 1))
		cur.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=ErlaubteSTB &(~?)", [mask])
		cur.close()

	def removeMarker(self, series, removeTimers):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [series.lower()])
		cur.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [series.lower()])
		cur.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [series.lower()])
		cur.execute("DELETE FROM SerienMarker WHERE LOWER(Serie)=?", [series.lower()])
		if removeTimers:
			cur.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=?", [series.lower()])
		cur.close()

	def removeAllMarkerSeasons(self, series):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [series.lower()])
		cur.close()

	def removeAllMarkerChannels(self, series):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE LOWER(Serie)=?)", [series.lower()])
		cur.close()

	def timerExists(self, channel, series, season, episode, startUnixtimeLowBound, startUnixtimeHighBound):
		cur = self._srDBConn.cursor()
		sql = "SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(webChannel)=? AND LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (channel.lower(), series.lower(), str(season).lower(), episode.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		found = (cur.fetchone()[0] > 0)
		cur.close()
		return found

	def timerExistsByServiceRef(self, series, stbRef, startUnixtimeLowBound, startUnixtimeHighBound):
		cur = self._srDBConn.cursor()
		sql = "SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (series.lower(), stbRef.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		found = (cur.fetchone()[0] > 0)
		cur.close()
		return found

	def getNumberOfTimers(self, series, season, episode, title=None, searchOnlyActiveTimers=False):
		cur = self._srDBConn.cursor()
		if searchOnlyActiveTimers:
			if title is None:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND TimerAktiviert=1", (series.lower(), str(season).lower(), str(episode).lower()))
			else:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND TimerAktiviert=1", (series.lower(), str(season).lower(), str(episode).lower(), title.lower()))
		else:
			if title is None:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (series.lower(), str(season).lower(), str(episode).lower()))
			else:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=?", (series.lower(), str(season).lower(), str(episode).lower(), title.lower()))
		(Anzahl,) = cur.fetchone()
		cur.close()
		return Anzahl

	def getTimerForSeries(self, series, searchOnlyActiveTimers=False):
		cur = self._srDBConn.cursor()
		if searchOnlyActiveTimers:
			cur.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE LOWER(Serie)=? AND TimerAktiviert=1 ORDER BY Staffel, Episode", [series.lower()])
		else:
			cur.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE LOWER(Serie)=? ORDER BY Staffel, Episode", [series.lower()])

		rows = cur.fetchall()
		cur.close()
		return rows

	def getAllTimer(self, startUnixtime):
		cur = self._srDBConn.cursor()
		if startUnixtime:
			cur.execute("SELECT * FROM AngelegteTimer WHERE StartZeitstempel>=?", [startUnixtime])
		else:
			cur.execute("SELECT * FROM AngelegteTimer")

		rows = cur.fetchall()
		cur.close()
		return rows


	def getActiveServiceRefs(self):
		serviceRefs = {}
		cur = self._srDBConn.cursor()
		cur.execute("SELECT WebChannel, ServiceRef FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
		rows = cur.fetchall()
		for row in rows:
			(webChannel, serviceRef) = row
			serviceRefs[webChannel] = serviceRef
		cur.close()
		return serviceRefs

	def getActiveChannels(self):
		channels = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT WebChannel FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
		rows = cur.fetchall()
		for row in rows:
			(webChannel,) = row
			channels.append(webChannel)
		cur.close()
		return channels

	def getSTBChannel(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT STBChannel, alternativSTBChannel FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		row = cur.fetchone()
		cur.close()
		return row

	def getChannelsSettings(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Vorlaufzeit, Nachlaufzeit, vps FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		row = cur.fetchone()
		if not row:
			row = (None, None, 0)
		(Vorlaufzeit, Nachlaufzeit, vps) = row
		cur.close()
		return Vorlaufzeit, Nachlaufzeit, vps

	def setChannelSettings(self, channel, leadTime, followUpTime, vps):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE Channels SET Vorlaufzeit=?, Nachlaufzeit=?, vps=? WHERE LOWER(WebChannel)=?", (leadTime, followUpTime, vps, channel.lower()))
		cur.close()

	def changeChannelStatus(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE Channels SET Erlaubt=(Erlaubt-1)*-1 WHERE LOWER(WebChannel)=?", [channel.lower()])
		cur.close()

	def updateChannels(self, data, withAlternativeChannels = False):
		cur = self._srDBConn.cursor()
		if withAlternativeChannels:
			cur.executemany("UPDATE Channels SET STBChannel=?, ServiceRef=?, alternativSTBChannel=?, alternativServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?", data)
		else:
			cur.executemany("UPDATE Channels SET STBChannel=?, ServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?", data)
		cur.close()

	def addChannels(self, data):
		cur = self._srDBConn.cursor()
		cur.executemany("INSERT OR IGNORE INTO Channels (WebChannel, STBChannel, ServiceRef, Erlaubt) VALUES (?, ?, ?, ?)", data)
		cur.close()

	def getChannelInfo(self, channel, seriesID, filterMode):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT DISTINCT alleSender, SerienMarker.ID FROM SenderAuswahl, SerienMarker WHERE SerienMarker.Url LIKE ?", ['%' + str(seriesID)])
		row = cur.fetchone()
		allChannels = True
		markerID = 0
		if row:
			(allChannels, markerID) = row

		if bool(allChannels) == True or filterMode == 1:
			cur.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels WHERE LOWER(WebChannel)=?", (channel.lower(),))
		else:
			cur.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels, SenderAuswahl WHERE LOWER(WebChannel)=? AND LOWER(SenderAuswahl.ErlaubterSender)=? AND SenderAuswahl.ID=?", (channel.lower(), channel.lower(), markerID))
		row = cur.fetchone()
		cur.close()
		if row:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
			if altstbChannel == "":
				altstbChannel = stbChannel
				altstbRef = stbRef
			elif stbChannel == "":
				stbChannel = altstbChannel
				stbRef = altstbRef
		else:
			webChannel = ""
			stbChannel = altstbChannel = ""
			stbRef = altstbRef = ""
			status = 0

		return webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status


	def getMarkerChannels(self, series, withActiveChannels = True):
		channels = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ErlaubterSender FROM SenderAuswahl INNER JOIN SerienMarker ON SenderAuswahl.ID=SerienMarker.ID WHERE SerienMarker.Serie=? ORDER BY LOWER(ErlaubterSender)", [series])
		rows = cur.fetchall()
		if len(rows) > 0:
			channels = list(zip(*rows)[0])

		if len(channels) == 0 and withActiveChannels:
			channels = self.getActiveChannels()
		cur.close()
		return channels

	def getChannels(self, sortByName = False):
		channels = []
		cur = self._srDBConn.cursor()
		if sortByName:
			cur.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels ORDER BY LOWER(WebChannel)")
		else:
			cur.execute("SELECT WebChannel, STBChannel, ServiceRef, alternativSTBChannel, alternativServiceRef, Erlaubt FROM Channels")
		rows = cur.fetchall()
		for row in rows:
			(webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status) = row
			channels.append((webChannel, stbChannel, stbRef, altstbChannel, altstbRef, status))
		cur.close()
		return channels

	def getChannelPairs(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT WebChannel, STBChannel FROM Channels")
		dbChannels = cur.fetchall()
		cur.close()
		return dbChannels

	def removeChannel(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM SenderAuswahl WHERE LOWER(ErlaubterSender)=?", [channel.lower()])
		cur.execute("DELETE FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		cur.close()

	def getAllowedSeasons(self, seriesID, fromSeason):
		seasons = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (seriesID, fromSeason))
		rows = cur.fetchall()
		if len(rows) > 0:
			seasons = list(zip(*rows)[0])
		cur.close()
		return seasons

	def getMarkers(self, boxID, numberOfRecordings, seriesFilter = None):
		result = []
		cur = self._srDBConn.cursor()
		where = ''
		if seriesFilter is not None and len(seriesFilter) > 0:
			where = ' WHERE Serie IN ('
			for i in range(len(seriesFilter) - 1):
				where += '"' + seriesFilter[i] + '",'
			where += '"' + seriesFilter[-1] + '")'

		cur.execute("SELECT ID, Serie, Url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays FROM SerienMarker" + where + " ORDER BY Serie")
		rows = cur.fetchall()
		for row in rows:
			(ID, serie, url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays) = row
			enabled = True
			cur.execute("SELECT ErlaubteSTB FROM STBAuswahl WHERE ID=?", [ID])
			rowSTB = cur.fetchone()
			if rowSTB:
				(ErlaubteSTB,) = rowSTB
				if ErlaubteSTB is not None and not (ErlaubteSTB & (1 << (int(boxID) - 1))):
					enabled = False
			else:
				cur.execute("INSERT INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)", (ID, 0xFFFF))

			if alleSender:
				channels = ['Alle', ]
			else:
				channels = self.getMarkerChannels(serie, False)

			if AlleStaffelnAb == -2:  # 'Manuell'
				seasons = [AlleStaffelnAb, ]
			else:
				seasons = self.getAllowedSeasons(ID, AlleStaffelnAb)
				if AlleStaffelnAb < 999999:
					seasons.insert(0, -1)
					seasons.append(AlleStaffelnAb)

			AnzahlAufnahmen = int(numberOfRecordings)
			if str(AnzahlWiederholungen).isdigit():
				AnzahlAufnahmen = int(AnzahlWiederholungen)

			result.append((serie, url, seasons, channels, AbEpisode, AnzahlAufnahmen, enabled, excludedWeekdays))
		cur.close()
		return result


	def addToTimerList(self, series, fromEpisode, toEpisode, season, episodeTitle, startUnixtime, stbRef, webChannel, eit, activated):
		# Es gibt Episodennummern die nicht nur aus Zahlen bestehen, z.B. 14a
		# um solche Folgen in die Datenbank zu bringen wird hier eine Unterscheidung gemacht.
		result = False
		cur = self._srDBConn.cursor()
		if fromEpisode == toEpisode:
			cur.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (series, season, str(fromEpisode).zfill(2), episodeTitle, int(startUnixtime), stbRef, webChannel, eit, int(activated)))
			result = True
		else:
			if int(fromEpisode) != 0 or int(toEpisode) != 0:
				for i in range(int(fromEpisode), int(toEpisode)+1):
					print "[SerienRecorder] %s Staffel: %s Episode: %s " % (str(series), str(season), str(i))
					cur.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (series, season, str(i).zfill(2), episodeTitle, int(startUnixtime), stbRef, webChannel, eit, int(activated)))
				result = True
		cur.close()
		return result

	def updateTimerEIT(self, series, stbRef, eit, startUnixtimeLowBound, startUnixtimeHighBound, activated):
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=?, TimerAktiviert=? WHERE LOWER(Serie)=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (eit, int(activated), series.lower(), stbRef.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		cur.close()

	def updateTimerStartTime(self, newStartUnixtime, eit, title, oldStartUnixtime, stbRef):
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=?, Titel=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=?"
		cur.execute(sql, (newStartUnixtime, eit, title, oldStartUnixtime, stbRef.lower()))
		cur.close()

	def removeTimer(self, series, season, episode, title, startUnixtime, channel, eit = None):
		cur = self._srDBConn.cursor()
		if not startUnixtime and not channel and not eit:
			if title:
				cur.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND (LOWER(Titel)=? OR Titel=? OR Titel='')", (series.lower(), season.lower(), str(episode).zfill(2).lower(), title.lower(), "dump"))
			else:
				cur.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (series.lower(), season.lower(), str(episode).zfill(2).lower()))
		else:
			if eit:
				cur.execute("DELETE FROM AngelegteTimer WHERE EventID=? AND StartZeitstempel>=?", (eit, int(time.time())))
			else:
				cur.execute("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND Episode=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (series.lower(), season.lower(), episode, startUnixtime, channel.lower()))
		cur.close()

	def removeTimers(self, data):
		cur = self._srDBConn.cursor()
		cur.executemany("DELETE FROM AngelegteTimer WHERE LOWER(Serie)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND StartZeitstempel=? AND LOWER(webChannel)=?", data)
		cur.close()

	def removeAllOldTimer(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM AngelegteTimer WHERE StartZeitstempel<?", [int(time.time())])
		cur.close()

	def getDeactivatedTimers(self):
		timers = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Serie, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE TimerAktiviert=0")
		rows = cur.fetchall()
		for row in rows:
			(serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row
			timers.append((serien_name, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit))
		cur.close()
		return timers

	def activateTimer(self, series, season, episode, title, startUnixtime, stbRef, channel, eit):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE LOWER(Serie)=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", (series.lower(), season, episode, title, startUnixtime, stbRef, channel, eit))
		cur.close()

# ----------------------------------------------------------------------------------------------------------------------

class SRTempDatabase:
	def __init__(self):
		self._tempDBConn = None
		self.connect()

	def __del__(self):
		self.close()

	def connect(self):
		self._tempDBConn = sqlite3.connect(":memory:")
		#self._tempDBConn = sqlite3.connect("/etc/enigma2/SerienRecorderTemp.db")
		self._tempDBConn.isolation_level = None
		self._tempDBConn.text_factory = lambda x: str(x.decode("utf-8"))

	def close(self):
		if self._tempDBConn:
			self._tempDBConn.close()
			self._tempDBConn = None

	def initialize(self):
		cur = self._tempDBConn.cursor()
		cur.execute('''CREATE TABLE IF NOT EXISTS GefundeneFolgen ( CurrentTime INTEGER,
																	FutureTime INTEGER,
																	SerieName TEXT,
																	Staffel TEXT, 
																	Episode TEXT, 
																	SeasonEpisode TEXT,
																	Title TEXT,
																	LabelSerie TEXT, 
																	webChannel TEXT, 
																	stbChannel TEXT, 
																	ServiceRef TEXT, 
																	StartTime INTEGER,
																	EndTime INTEGER,
																	EventID INTEGER,
																	alternativStbChannel TEXT, 
																	alternativServiceRef TEXT, 
																	alternativStartTime INTEGER,
																	alternativEndTime INTEGER,
																	alternativEventID INTEGER,
																	DirName TEXT,
																	AnzahlAufnahmen INTEGER,
																	AufnahmezeitVon INTEGER,
																	AufnahmezeitBis INTEGER,
																	vomMerkzettel INTEGER DEFAULT 0,
																	excludedWeekdays INTEGER DEFAULT NULL)''')

		cur.close()

	def cleanUp(self):
		cur = self._tempDBConn.cursor()
		cur.execute("DELETE FROM GefundeneFolgen")
		cur.close()

	def rebuild(self):
		cur = self._tempDBConn.cursor()
		cur.execute("VACUUM")
		cur.close()

	def addTransmission(self, transmission):
		cur = self._tempDBConn.cursor()
		sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, Staffel, Episode, SeasonEpisode, Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, EventID, alternativStbChannel, alternativServiceRef, alternativStartTime, alternativEndTime, alternativEventID, DirName, AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel, excludedWeekdays) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
		cur.execute(sql, transmission[0])
		cur.close()

	def getTransmissionForTimerUpdate(self, seriesName, season, episode):
		result = None
		cur = self._tempDBConn.cursor()
		cur.execute("SELECT SerieName, Staffel, Episode, Title, StartTime FROM GefundeneFolgen WHERE EventID > 0 AND LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (seriesName.lower(), season.lower(), episode.lower()))
		row = cur.fetchone()
		if row:
			result = row
		cur.close()
		return result

	def getTransmissionsOrderedByNumberOfRecordings(self, numberOfRecordings):
		result = []
		cur = self._tempDBConn.cursor()
		cur.execute("SELECT * FROM (SELECT SerieName, Staffel, Episode, Title, COUNT(*) AS Anzahl FROM GefundeneFolgen WHERE AnzahlAufnahmen>? GROUP BY SerieName, Staffel, Episode, Title) ORDER BY Anzahl", [numberOfRecordings])
		rows = cur.fetchall()
		for row in rows:
			result.append(row)
		cur.close()
		return result

	def getTransmissionsToCreateTimer(self, seriesName, season, episode, title = None):
		result = []
		cur = self._tempDBConn.cursor()
		if title:
			cur.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime>=CurrentTime ORDER BY StartTime", (seriesName.lower(), str(season).lower(), str(episode).lower(), title.lower()))
		else:
			cur.execute("SELECT * FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (seriesName.lower(), str(season).lower(), str(episode).lower()))
		rows = cur.fetchall()
		for row in rows:
			result.append(row)
		cur.close()
		return result

	def removeTransmission(self, seriesName, season, episode, title, startUnixtime, stbRef):
		cur = self._tempDBConn.cursor()
		if title:
			cur.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (seriesName.lower(), str(season).lower(), episode.lower(), title.lower(), startUnixtime, stbRef.lower()))
		else:
			cur.execute("DELETE FROM GefundeneFolgen WHERE LOWER(SerieName)=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (seriesName.lower(), str(season).lower(), episode.lower(), startUnixtime, stbRef.lower()))
		cur.close()

