# -*- coding: utf-8 -*-
try:
	import simplejson as json
except ImportError:
	import json

import shutil, sqlite3, time, os

from .SerienRecorderHelpers import getChangedSeriesNames, PY2, toStr
from .SerienRecorderLogWriter import SRLogger

class SRDatabase:
	def __init__(self, dbfilepath):
		self._dbfilepath = dbfilepath
		self._srDBConn = None
		self.connect()

	def __del__(self):
		self.close()

	def connect(self):
		try:
			self._srDBConn = sqlite3.connect(self._dbfilepath)
			self._srDBConn.isolation_level = None
			self._srDBConn.text_factory = lambda x: str(x.decode("utf-8"))
		except Exception as e:
			print("[SerienRecorder] Unable to connect to database [%s]" % str(e))

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
																		vps INTEGER DEFAULT 0,
																		autoAdjust INTEGER DEFAULT NULL)''')

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
																			addToDatabase INTEGER DEFAULT 1,
																			updateFromEPG INTEGER DEFAULT NULL,
																			skipSeriesServer INTEGER DEFAULT NULL,
																			info TEXT NOT NULL DEFAULT "",
																			type INTEGER DEFAULT 0,
																			autoAdjust INTEGER DEFAULT NULL,
																			fsID TEXT DEFAULT NULL,
																			epgSeriesName TEXT DEFAULT NULL,
																			kindOfTimer INTEGER DEFAULT NULL,
																			forceRecording INTEGER DEFAULT NULL,
																			timerSeriesName TEXT DEFAULT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS SenderAuswahl (ID INTEGER, 
																			 ErlaubterSender TEXT NOT NULL, 
																			 FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS StaffelAuswahl (ID INTEGER, 
																			  ErlaubteStaffel INTEGER, 
																			  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																		  ErlaubteSTB INTEGER, 
																		  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')

		cur.execute('''CREATE TABLE IF NOT EXISTS AngelegteTimer ( 	Serie TEXT NOT NULL, 
																	Staffel TEXT, 
																	Episode TEXT, 
																	Titel TEXT, 
																	StartZeitstempel INTEGER NOT NULL, 
																	ServiceRef TEXT NOT NULL, 
																	webChannel TEXT NOT NULL, 
																	EventID INTEGER DEFAULT 0,
																	TimerAktiviert INTEGER DEFAULT 1,
																	fsID TEXT DEFAULT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																			  StartZeitstempel INTEGER NOT NULL, 
																			  webChannel TEXT NOT NULL)''')

		cur.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																		  Staffel TEXT NOT NULL, 
																		  Episode TEXT NOT NULL,
																		  AnzahlWiederholungen INTEGER DEFAULT NULL,
																		  fsID TEXT DEFAULT NULL)''')

		cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('Version', ?)", [version])
		cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('ChannelsLastUpdate', ?)", [int(time.time())])
		cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('MarkersLastUpdate', ?)", [int(time.time())])

		# Create index
		self.createIndex(cur)

		# Create trigger
		self.createTrigger(cur)
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

	def isMalformed(self):
		malformed = True
		try:
			cur = self._srDBConn.cursor()
			cur.execute("PRAGMA quick_check")
			row = cur.fetchone()
			if row:
				malformed = (row[0] != 'ok')
			cur.close()
		except:
			pass

		return malformed

	@staticmethod
	def createIndex(cur):
		cur.execute("CREATE INDEX IF NOT EXISTS serienmarker_url ON SerienMarker (Url ASC)")
		cur.execute("CREATE INDEX IF NOT EXISTS serienmarker_fsid ON SerienMarker (fsID ASC)")
		cur.execute("CREATE INDEX IF NOT EXISTS serienmarker_serie ON SerienMarker (Serie ASC)")
		cur.execute("CREATE INDEX IF NOT EXISTS channels_webchannel ON Channels (WebChannel ASC)")

	@staticmethod
	def createTrigger(cur):
		cur.execute('''CREATE TABLE IF NOT EXISTS undolog_timer (
									series TEXT,
									season TEXT,
									episode TEXT,
									title TEXT,
									starttime INTEGER,
									serviceref TEXT,
									webchannel TEXT,
									eventid INTEGER,
									active INTEGER,
									fsid TEXT,
									created	TEXT
								)
		''')
		cur.execute('''CREATE TRIGGER IF NOT EXISTS AngelegteTimer_dt BEFORE DELETE ON AngelegteTimer 
							BEGIN
							  INSERT INTO undolog_timer VALUES(old.Serie, old.Staffel, old.Episode, old.Titel, old.StartZeitstempel, old.ServiceRef, old.webChannel, old.EventID, old.TimerAktiviert, old.fsID, datetime('now','localtime'));
							END;
		''')

	@staticmethod
	def hasColumn(rows, columnName):
		if [item for item in rows if item[1] == columnName]:
			return True
		else:
			return False

	def update(self, version):
		"""
		Update database if too old
		:return:
		:rtype:
		"""
		SRLogger.writeLog("Datenbank wird auf die Version %s aktualisiert..." % str(version), True)

		cur = self._srDBConn.cursor()
		cur.execute("PRAGMA table_info(SerienMarker)")
		markerRows = cur.fetchall()
		cur.execute("PRAGMA table_info(AngelegteTimer)")
		timerRows = cur.fetchall()
		cur.execute("PRAGMA table_info(Channels)")
		channelRows = cur.fetchall()
		cur.execute("PRAGMA table_info(Merkzettel)")
		bookmarkRows = cur.fetchall()

		# Foreign key check
		try:
			cur.execute("PRAGMA foreign_key_check")
			foreignKeyChecks = cur.fetchall()
			if len(foreignKeyChecks) > 0:
				SRLogger.writeLog("Es muss eine Fremdschlüssel Korrektur durchgeführt werden.", True)
				cur.execute("BEGIN TRANSACTION")
				for foreignKeyCheck in foreignKeyChecks:
					cur.execute("DELETE FROM %s WHERE ROWID=?" % foreignKeyCheck[0], [foreignKeyCheck[1]])
				cur.execute("COMMIT")
				SRLogger.writeLog("Fremdschlüssel Korrektur wurde erfolgreich durchgeführt.", True)
		except Exception as e:
			cur.execute("ROLLBACK")
			SRLogger.writeLog("Fremdschlüssel Korrektur konnte nicht durchgeführt werden [%s]." % str(e), True)

		updateSuccessful = True

		# SerienMarker table updates
		if not self.hasColumn(markerRows, 'AbEpisode'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD AbEpisode INTEGER DEFAULT 0')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'AbEpisode' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'Staffelverzeichnis'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD Staffelverzeichnis INTEGER DEFAULT -1')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'Staffelverzeichnis' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'TimerForSpecials'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD TimerForSpecials INTEGER DEFAULT 0')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'TimerForSpecials' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'vps'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD vps INTEGER DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'vps' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'excludedWeekdays'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD excludedWeekdays INTEGER DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'excludedWeekdays' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'tags'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD tags TEXT')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'tags' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'addToDatabase'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD addToDatabase INTEGER DEFAULT 1')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'addToDatabase' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'updateFromEPG'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD updateFromEPG INTEGER DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'updateFromEPG' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'skipSeriesServer'):
			try:
				cur.execute('ALTER TABLE SerienMarker ADD skipSeriesServer INTEGER DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'skipSeriesServer' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'info'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD info TEXT NOT NULL DEFAULT ''")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'info' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'type'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD type INTEGER DEFAULT 0")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'type' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'autoAdjust'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD autoAdjust INTEGER DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'autoAdjust' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)
		else:
			try:
				cur.execute("SELECT COUNT(*) FROM SerienMarker WHERE autoAdjust IS NULL")
				hasNullValues = (cur.fetchone()[0] > 0)
				if not hasNullValues:
					cur.execute("UPDATE SerienMarker SET autoAdjust = NULL WHERE autoAdjust = 0")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'autoAdjust' konnte nicht korrigiert werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'fsID'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD fsID TEXT DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'fsID' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'epgSeriesName'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD epgSeriesName TEXT DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'epgSeriesName' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'kindOfTimer'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD kindOfTimer INTEGER DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'kindOfTimer' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'forceRecording'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD forceRecording INTEGER DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'forceRecording' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(markerRows, 'timerSeriesName'):
			try:
				cur.execute("ALTER TABLE SerienMarker ADD timerSeriesName TEXT DEFAULT NULL")
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'timerSeriesName' konnte nicht in der Tabelle 'SerienMarker' angelegt werden [%s]." % str(e), True)


		if not self.updateToWLID():
			updateSuccessful = False

		# Channels table updates
		if not self.hasColumn(channelRows, 'vps'):
			try:
				cur.execute('ALTER TABLE Channels ADD vps INTEGER DEFAULT 0')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'vps' konnte nicht in der Tabelle 'Channels' angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(channelRows, 'autoAdjust'):
			try:
				cur.execute('ALTER TABLE Channels ADD autoAdjust INTEGER DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'autoAdjust' konnte nicht in der Tabelle 'Channels' angelegt werden [%s]." % str(e), True)

		try:
			cur.execute('DROP TABLE IF EXISTS NeuerStaffelbeginn')
		except:
			updateSuccessful = False
			SRLogger.writeLog("Tabelle 'NeuerStaffelbeginn' konnte nicht gelöscht werden.", True)

		# AngelegteTimer table updates
		if not self.hasColumn(timerRows, 'TimerAktiviert'):
			try:
				cur.execute('ALTER TABLE AngelegteTimer ADD TimerAktiviert INTEGER DEFAULT 1')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'TimerAktiviert' konnte nicht in der Tabelle 'AngelegteTimer' angelegt werden [%s]." % str(e), True)

		hasFSIDColumn = self.hasColumn(timerRows, 'fsID')
		if not hasFSIDColumn:
			try:
				cur.execute('ALTER TABLE AngelegteTimer ADD fsID TEXT DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'fsID' konnte nicht in der Tabelle 'AngelegteTimer' angelegt werden [%s]." % str(e), True)

		try:
			cur.execute("UPDATE AngelegteTimer SET Episode = '00' WHERE rowid IN (SELECT rowid FROM AngelegteTimer WHERE Staffel='0' AND (Episode='' OR Episode='0'))")
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Der Standardwert für die Spalte 'Episode' in der Tabelle 'AngelegteTimer' konnte nicht neu gesetzt werden [%s]." % str(e), True)

		try:
			cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('MarkersLastUpdate', ?)", [int(time.time())])
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Der Zeitstempel für die letzte Aktualisierung der Serien-Marker konnte nicht gesetzt werden [%s]." % str(e), True)

		if self.updateSeriesMarker(hasFSIDColumn) is False:
			updateSuccessful = False

		if updateSuccessful and not hasFSIDColumn:
			if not self.updateTimers():
				updateSuccessful = False

		try:
			cur.execute('''CREATE TABLE IF NOT EXISTS TimerKonflikte (Message TEXT NOT NULL UNIQUE, 
																	  StartZeitstempel INTEGER NOT NULL, 
																	  webChannel TEXT NOT NULL)''')
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Die Tabelle 'TimerKonflikte' konnte nicht angelegt werden [%s]." % str(e), True)


		try:
			cur.execute('''CREATE TABLE IF NOT EXISTS Merkzettel (Serie TEXT NOT NULL, 
																  Staffel TEXT NOT NULL, 
																  Episode TEXT NOT NULL,
																  AnzahlWiederholungen INTEGER DEFAULT NULL,
																  fsID TEXT DEFAULT NULL)''')
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Die Tabelle 'Merkzettel' konnte nicht angelegt werden [%s]." % str(e), True)

		if not self.hasColumn(bookmarkRows, 'fsID'):
			try:
				cur.execute('ALTER TABLE Merkzettel ADD fsID TEXT DEFAULT NULL')
			except Exception as e:
				updateSuccessful = False
				SRLogger.writeLog("Spalte 'fsID' konnte nicht in der Tabelle 'Merkzettel' angelegt werden [%s]." % str(e), True)

		if not self.updateBookmarks():
			updateSuccessful = False

		try:
			cur.execute('''CREATE TABLE IF NOT EXISTS STBAuswahl (ID INTEGER, 
																  ErlaubteSTB INTEGER, 
																  FOREIGN KEY(ID) REFERENCES SerienMarker(ID))''')
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Die Tabelle 'STBAuswahl' konnte nicht angelegt werden [%s]." % str(e), True)

		try:
			cur.execute("INSERT OR IGNORE INTO dbInfo (Key, Value) VALUES ('ChannelsLastUpdate', ?)", [int(time.time())])
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Der Zeitstempel für die letzte Aktualisierung der Kanalliste konnte nicht gesetzt werden [%s]." % str(e), True)

		# Create indexes
		try:
			self.createIndex(cur)
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Indizes für Tabellen konnten nicht angelegt werden [%s]." % str(e), True)

		# Create trigger
		try:
			self.createTrigger(cur)
		except Exception as e:
			updateSuccessful = False
			SRLogger.writeLog("Trigger für Tabellen konnten nicht angelegt werden [%s]." % str(e), True)

		if updateSuccessful:
			SRLogger.writeLog("Datenbank wurde erfolgreich aktualisiert - aktualisiere Versionsnummer.", True)
			cur.execute("UPDATE OR IGNORE dbInfo SET Value=? WHERE Key='Version'", [version])
		else:
			SRLogger.writeLog("Fehler beim Aktualisieren der Datenbank - bitte wenden Sie sich mit diesem Log an die Entwickler.", True)


		cur.close()

		return updateSuccessful

	def updateToWLID(self):
		result = True
		cur = self._srDBConn.cursor()
		try:
			cur.execute("BEGIN TRANSACTION")
			cur.execute("SELECT ID, Serie, Url FROM SerienMarker")
			rows = cur.fetchall()
			for row in rows:
				(ID,name,url) = row
				# If URL starts with 'http' remove incorrect markers and convert URL to WL ID
				if str.startswith(url, 'http'):
					if str.rfind(url, '=') == -1:
						cur.execute("DELETE FROM STBAuswahl WHERE ID=?", [ID])
						cur.execute("DELETE FROM StaffelAuswahl WHERE ID=?", [ID])
						cur.execute("DELETE FROM SenderAuswahl WHERE ID=?", [ID])
						cur.execute("DELETE FROM SerienMarker WHERE ID=?", [ID])
						SRLogger.writeLog("Fehlerhafter SerienMarker musste gelöscht werden [%s → %s]" % (name, url), True)
					else:
						url = url[str.rindex(url, '=') + 1:]
						if not url.isdigit():
							from .SerienRecorderSeriesServer import SeriesServer
							url = SeriesServer().getIDByFSID(url)
						cur.execute("UPDATE SerienMarker SET Url=? WHERE ID=?", (url, ID))
			cur.execute("COMMIT")
		except Exception as e:
			result = False
			SRLogger.writeLog("Fehler beim Konvertieren der URLs [%s]." % str(e), True)
			cur.execute("ROLLBACK")
		cur.close()
		return result

	def updateSeriesMarker(self, hasFSIDColumn):
		result = []
		cur = self._srDBConn.cursor()
		try:
			# Update Series-Markers
			markers = self.getMarkerNamesAndWLID()
			changedMarkers = getChangedSeriesNames(markers)
			if len(changedMarkers) == 1:
				SRLogger.writeLog("Es wurde %d geänderter Serienname bzw. geänderte Serieninformationen gefunden" % len(changedMarkers), True)
			if len(changedMarkers) > 1:
				SRLogger.writeLog("Es wurden %d geänderte Seriennamen bzw. Serieninformationen gefunden" % len(changedMarkers), True)

			cur.execute("BEGIN TRANSACTION")
			for key, val in list(changedMarkers.items()):
				cur.execute("UPDATE SerienMarker SET Serie = ?, info = ?, fsID = ? WHERE Url = ?", (val['new_name'], val['new_info'], val['new_fsID'], key))
				SRLogger.writeLog("SerienMarker Tabelle aktualisiert:", True)
				SRLogger.writeLog("[%s] (%s) → [%s] (%s) / [%s]: %d" % (val['old_name'], val['old_fsID'], val['new_name'], val['new_fsID'], val['new_info'], cur.rowcount), True)
				if not hasFSIDColumn:
					# Update AngelegteTimer and Merkzettel table by name
					if val['new_name'] != val['old_name']:
						cur.execute("UPDATE AngelegteTimer SET Serie = ? WHERE TRIM(Serie) = ?", (val['new_name'], val['old_name']))
						SRLogger.writeLog("AngelegteTimer Tabelle aktualisiert [%s]: %d" % (val['new_name'], cur.rowcount), True)
						cur.execute("UPDATE Merkzettel SET Serie = ? WHERE TRIM(Serie) = ?", (val['new_name'], val['old_name']))
						SRLogger.writeLog("Merkzettel Tabelle aktualisiert [%s]: %d" % (val['new_name'], cur.rowcount), True)

				else:
					if val['new_name'] != val['old_name'] or val['old_fsID'] != val['new_fsID']:
						cur.execute("UPDATE AngelegteTimer SET Serie = ?, fsID = ? WHERE fsID = ?", (val['new_name'], val['new_fsID'], val['old_fsID']))
						SRLogger.writeLog("AngelegteTimer Tabelle aktualisiert [%s] (%s): %d" % (val['new_name'], val['new_fsID'], cur.rowcount), True)
						cur.execute("UPDATE Merkzettel SET Serie = ?, fsID = ? WHERE fsID = ?", (val['new_name'], val['new_fsID'], val['old_fsID']))
						SRLogger.writeLog("Merkzettel Tabelle aktualisiert [%s] (%s): %d" % (val['new_name'], val['new_fsID'], cur.rowcount), True)
				result.append(val['new_name'])
			cur.execute("UPDATE OR IGNORE dbInfo SET Value = ? WHERE Key='MarkersLastUpdate'", [int(time.time())])
			cur.execute("COMMIT")
		except Exception as e:
			result = False
			cur.execute("ROLLBACK")
			SRLogger.writeLog("Fehler beim Aktualisieren der Serien-Marker [%s]." % str(e), True)
		cur.close()
		return result

	def updateTimers(self):
		result = False
		cur = self._srDBConn.cursor()
		try:
			# Update AngelegteTimer table => set Fernsehserie ID
			cur.execute("BEGIN TRANSACTION")
			cur.execute("UPDATE AngelegteTimer SET fsID = (SELECT fsID FROM SerienMarker WHERE AngelegteTimer.Serie = SerienMarker.Serie)")
			cur.execute("COMMIT")
			result = True
		except Exception as e:
			result = False
			cur.execute("ROLLBACK")
			SRLogger.writeLog("Fehler beim Aktualisieren der angelegten Timer [%s]." % str(e), True)
		cur.close()
		return result

	def updateBookmarks(self):
		result = False
		cur = self._srDBConn.cursor()
		try:
			# Update Merkzettel table => set Fernsehserie ID
			cur.execute("BEGIN TRANSACTION")
			cur.execute("UPDATE Merkzettel SET fsID = (SELECT fsID FROM SerienMarker WHERE Merkzettel.Serie = SerienMarker.Serie)")
			cur.execute("COMMIT")
			result = True
		except Exception as e:
			result = False
			cur.execute("ROLLBACK")
			SRLogger.writeLog("Fehler beim Aktualisieren der Merkzettel [%s]." % str(e), True)
		cur.close()
		return result

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

	def hasBookmark(self, fsID, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM Merkzettel WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (fsID, str(season).lower(), str(episode).zfill(2).lower()))
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def getBookmarks(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT * FROM Merkzettel")
		rows = cur.fetchall()
		cur.close()
		return rows

	def addBookmark(self, series, fsID, fromEpisode, toEpisode, season, globalNumberOfRecordings):
		if int(fromEpisode) != 0 or int(toEpisode) != 0:
			numberOfRecordings = globalNumberOfRecordings
			cur = self._srDBConn.cursor()
			cur.execute("SELECT AnzahlWiederholungen FROM SerienMarker WHERE fsID=?", [fsID])
			row = cur.fetchone()
			if row:
				(AnzahlWiederholungen,) = row
				if str(AnzahlWiederholungen).isdigit():
					numberOfRecordings = int(AnzahlWiederholungen)
			for i in range(int(fromEpisode), int(toEpisode) + 1):
				print("[SerienRecorder] %s Staffel: %s Episode: %s " % (str(series), str(season), str(i)))
				cur.execute("SELECT * FROM Merkzettel WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (fsID, season.lower(), str(i).zfill(2).lower()))
				row = cur.fetchone()
				if not row:
					cur.execute("INSERT OR IGNORE INTO Merkzettel VALUES (?, ?, ?, ?, ?)", (series, season, str(i).zfill(2), numberOfRecordings, fsID))
			cur.close()
			return True
		else:
			return False

	def updateBookmark(self, fsID, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE Merkzettel SET AnzahlWiederholungen=AnzahlWiederholungen-1 WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (fsID, str(season).lower(), episode.lower()))
		cur.close()

	def removeBookmark(self, fsID, season, episode):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM Merkzettel WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND AnzahlWiederholungen<=0", (fsID, str(season).lower(), episode.lower()))
		cur.close()

	def removeBookmarks(self, data):
		cur = self._srDBConn.cursor()
		cur.executemany("DELETE FROM Merkzettel WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", data)
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
		cur.execute("DELETE FROM SerienMarker WHERE type = 1")
		cur.close()


	def getRecordDirectories(self, defaultSavePath):
		directories = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT distinct(AufnahmeVerzeichnis) FROM SerienMarker WHERE AufnahmeVerzeichnis NOT NULL")
		rows = cur.fetchall()
		for row in rows:
			(recordPath,) = row
			if recordPath:
				recordPath = os.path.normpath(recordPath)
				directories.append(recordPath)
		cur.close()
		defaultSavePath = os.path.normpath(defaultSavePath)
		if defaultSavePath not in directories:
			directories.append(defaultSavePath)
		return directories

	def getDirNames(self, fsID):
		result = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, type FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			result = row
		cur.close()
		return result

	def getMargins(self, fsID, channel, globalMarginBefore, globalMarginAfter):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM SerienMarker WHERE fsID=?", [fsID])
		markerExists = (cur.fetchone()[0] > 0)
		if markerExists:
			cur.execute("SELECT MAX(IFNULL(SerienMarker.Vorlaufzeit, -1), IFNULL(Channels.Vorlaufzeit, -1)), MAX(IFNULL(SerienMarker.Nachlaufzeit, -1), IFNULL(Channels.Nachlaufzeit, -1)) FROM SerienMarker, Channels WHERE SerienMarker.fsID=? AND LOWER(Channels.WebChannel)=?", (fsID, channel.lower()))
		else:
			cur.execute("SELECT IFNULL(Vorlaufzeit, -1), IFNULL(Nachlaufzeit, -1) FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		row = cur.fetchone()
		if not row:
			margin_before = globalMarginBefore
			margin_after = globalMarginAfter
		else:
			(margin_before, margin_after) = row

		if margin_before is None or margin_before == -1:
			margin_before = globalMarginBefore

		if margin_after is None or margin_after == -1:
			margin_after = globalMarginAfter

		cur.close()
		return margin_before, margin_after

	def getVPS(self, fsID, channel):
		result = 0
		cur = self._srDBConn.cursor()
		cur.execute("SELECT CASE WHEN SerienMarker.vps IS NOT NULL AND SerienMarker.vps IS NOT '' THEN SerienMarker.vps ELSE Channels.vps END as vps FROM Channels,SerienMarker WHERE LOWER(Channels.WebChannel)=? AND SerienMarker.fsID=?", (channel.lower(), fsID))
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		return bool(result & 0x1), bool(result & 0x2)

	def getTags(self, fsID):
		tags = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT tags FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(tagString,) = row
			if tagString is not None and len(tagString) > 0:
				try:
					# if tagString.startswith('(lp1'):
					# 	if PY2:
					# 		import cPickle as pickle
					# 		tags = pickle.loads(tagString)
					# 	else:
					# 		import pickle
					# 		from .SerienRecorderHelpers import toBinary
					# 		tags = pickle.loads(toBinary(tagString), encoding="utf-8")
					# else:
					# 	tags = [toStr(x) for x in json.loads(tagString)]
					from .SerienRecorderHelpers import readTags
					tags = readTags(tagString)
				except:
					SRLogger.writeLog("Fehler beim Lesen der gespeicherten Tags am Marker mit der Fernsehserie ID ' %s '" % fsID)

		cur.close()
		return tags

	def getAddToDatabase(self, fsID):
		result = True
		cur = self._srDBConn.cursor()
		cur.execute("SELECT addToDatabase FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		return bool(result)

	def getAutoAdjust(self, fsID, channel):
		result = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT CASE WHEN SerienMarker.autoAdjust IS NOT NULL THEN SerienMarker.autoAdjust ELSE Channels.autoAdjust END as autoAdjust FROM Channels,SerienMarker WHERE LOWER(Channels.WebChannel)=? AND SerienMarker.fsID=?", (channel.lower(), fsID))
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		return result

	def getKindOfTimer(self, fsID, default):
		result = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT kindOfTimer FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		if result is None:
			result = default
		return str(result)

	def getUpdateFromEPG(self, fsID, default):
		result = True
		cur = self._srDBConn.cursor()
		cur.execute("SELECT updateFromEPG FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		if result is None:
			result = default
		return bool(result)

	def getForceRecording(self, fsID, default):
		result = True
		cur = self._srDBConn.cursor()
		cur.execute("SELECT forceRecording FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(result,) = row
		cur.close()
		if result is None:
			result = default
		return bool(result)

	def getSpecialsAllowed(self, fsID):
		TimerForSpecials = False
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AlleStaffelnAb, TimerForSpecials FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(AlleStaffelnAb, TimerForSpecials,) = row
			if int(AlleStaffelnAb) == 0:
				TimerForSpecials = True
			elif not str(TimerForSpecials).isdigit():
				TimerForSpecials = False
		cur.close()
		return bool(TimerForSpecials)

	def getTimeSpan(self, fsID, globalTimeFrom, globalTimeTo):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmezeitVon, AufnahmezeitBis FROM SerienMarker WHERE fsID=?", [fsID])
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
		cur.execute("SELECT fsID, ErlaubteSTB FROM SerienMarker LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID")
		rows = cur.fetchall()
		for row in rows:
			try:
				(fsID, allowedSTB) = row
				seriesActivated = True
				if allowedSTB is not None and not (allowedSTB & (1 << (int(boxID) - 1))):
					seriesActivated = False
				markers[fsID] = seriesActivated
			except:
				continue
		cur.close()
		return markers

	def getMarkerNamesAndWLID(self):
		cur = self._srDBConn.cursor()
		sql = "SELECT ID, Serie, info, Url, fsID AS wl_id FROM SerienMarker"
		cur.execute(sql)
		markers = cur.fetchall()
		cur.close()
		return markers

	def getAllMarkers(self, sortLikeWL):
		cur = self._srDBConn.cursor()
		sql = "SELECT SerienMarker.ID, Serie, info, Url, AufnahmeVerzeichnis, AlleStaffelnAb, alleSender, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, preferredChannel, useAlternativeChannel, AbEpisode, TimerForSpecials, ErlaubteSTB, COUNT(StaffelAuswahl.ID) AS ErlaubteStaffelCount, fsID FROM SerienMarker LEFT JOIN StaffelAuswahl ON StaffelAuswahl.ID = SerienMarker.ID LEFT OUTER JOIN STBAuswahl ON SerienMarker.ID = STBAuswahl.ID GROUP BY fsID"
		if sortLikeWL:
			sql += " ORDER BY REPLACE(REPLACE(REPLACE(REPLACE(LOWER(Serie), 'the ', ''), 'das ', ''), 'die ', ''), 'der ', '')"
		else:
			sql += " ORDER BY LOWER(Serie)"
		cur.execute(sql)
		markers = cur.fetchall()
		cur.close()
		return markers

	def getNextMarker(self, currentIndex):
		fsID = None
		cur = self._srDBConn.cursor()
		sql = "SELECT DISTINCT LOWER(SUBSTR(Serie, 1, 1)) as fc, fsID FROM SerienMarker WHERE fc > ? ORDER BY LOWER(Serie)"
		sql += " LIMIT 1"
		cur.execute(sql, [currentIndex])
		row = cur.fetchone()
		if row:
			(fc, fsID) = row
		cur.close()
		return fsID

	def getPreviousMarker(self, currentIndex):
		result = None
		cur = self._srDBConn.cursor()
		sql = "SELECT DISTINCT LOWER(SUBSTR(Serie, 1, 1)) as fc, fsID FROM SerienMarker WHERE fc < ? ORDER BY LOWER(Serie) DESC"
		cur.execute(sql, [currentIndex])
		rows = cur.fetchall()
		for row in rows:
			(fc, fsID) = row
			if fc == rows[0][0]:
				result = fsID
			else:
				break
		cur.close()
		return result

	def getMarkerSettings(self, seriesID):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AufnahmeVerzeichnis, Staffelverzeichnis, Vorlaufzeit, Nachlaufzeit, AnzahlWiederholungen, AufnahmezeitVon, AufnahmezeitBis, preferredChannel, useAlternativeChannel, vps, excludedWeekdays, tags, addToDatabase, updateFromEPG, skipSeriesServer, autoAdjust, epgSeriesName, kindOfTimer, forceRecording, timerSeriesName FROM SerienMarker WHERE ID=?", [seriesID])
		row = cur.fetchone()
		if not row:
			row = (None, -1, None, None, None, None, None, 1, -1, None, None, "", 1, 1, 1, 1, None, None)
		cur.close()
		return row

	def setMarkerSettings(self, seriesID, settings):
		data = settings + (seriesID, )
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE SerienMarker SET AufnahmeVerzeichnis=?, Staffelverzeichnis=?, Vorlaufzeit=?, Nachlaufzeit=?, AnzahlWiederholungen=?, AufnahmezeitVon=?, AufnahmezeitBis=?, preferredChannel=?, useAlternativeChannel=?, vps=?, excludedWeekdays=?, tags=?, addToDatabase=?, updateFromEPG=?, skipSeriesServer=?, autoAdjust=?, epgSeriesName=?, kindOfTimer=?, forceRecording=?, timerSeriesName=? WHERE ID=?"
		cur.execute(sql, data)
		cur.close()

	def getTimer(self, dayOffset):
		timer = []
		cur = self._srDBConn.cursor()
		dayOffsetInSeconds = dayOffset * 86400
		sql = "SELECT fsID, StartZeitstempel, LOWER(webChannel) FROM AngelegteTimer WHERE (StartZeitstempel >= STRFTIME('%s', CURRENT_DATE)+?) AND (StartZeitstempel < (STRFTIME('%s', CURRENT_DATE)+?+86399))"
		cur.execute(sql, (dayOffsetInSeconds, dayOffsetInSeconds))
		rows = cur.fetchall()
		for row in rows:
			(fsID, startTimestamp, webChannel) = row
			timer.append((fsID, startTimestamp, webChannel))
		cur.close()
		return timer

	def addMarker(self, url, name, info, fsID, boxID, markerType):
		result = False
		cur = self._srDBConn.cursor()
		if not self.markerExists(fsID, markerType):
			cur.execute("INSERT OR IGNORE INTO SerienMarker (Serie, Url, info, AlleStaffelnAb, alleSender, preferredChannel, useAlternativeChannel, AbEpisode, Staffelverzeichnis, TimerForSpecials, type, autoAdjust, fsID) VALUES (?, ?, ?, 0, 1, 1, -1, 0, -1, 0, ?, NULL, ?)", (name, url, info, markerType, fsID))
			erlaubteSTB = 0xFFFF
			if boxID:
				erlaubteSTB |= (1 << (int(boxID) - 1))
			cur.execute("INSERT OR IGNORE INTO STBAuswahl (ID, ErlaubteSTB) VALUES (?,?)",(cur.lastrowid, erlaubteSTB))
			result = True
		cur.close()
		return result

	def markerExists(self, fsID, markerType):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT COUNT(*) FROM SerienMarker WHERE fsID=? AND type=?", (fsID, markerType))
		result = (cur.fetchone()[0] > 0)
		cur.close()
		return result

	def getPreferredMarkerChannels(self, fsID, globalUseAlternativeChannel, globalNumberOfRecordings):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT AnzahlWiederholungen, preferredChannel, useAlternativeChannel FROM SerienMarker WHERE fsID=?", [fsID])
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

	def getMarkerID(self, fsID):
		markerID = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(markerID, ) = row
		cur.close()
		return markerID

	def getMarkerFSID(self, wlID):
		fsID = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT fsID FROM SerienMarker WHERE Url=?", [wlID])
		row = cur.fetchone()
		if row:
			(fsID, ) = row
		cur.close()
		return fsID

	def getMarkerWLID(self, fsID):
		wlID = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Url FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(wlID, ) = row
		cur.close()
		return wlID

	def getMarkerInfo(self, fsID):
		info = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT info FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(info, ) = row
		cur.close()
		return info

	def getMarkerEPGName(self, fsID):
		epgSeriesName = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT epgSeriesName FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(epgSeriesName, ) = row
		cur.close()
		return "" if not epgSeriesName else epgSeriesName

	def getMarkerTimerName(self, fsID):
		timerSeriesName = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT timerSeriesName FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(timerSeriesName, ) = row
		cur.close()
		return "" if not timerSeriesName else timerSeriesName

	def getMarkerType(self, fsID):
		markerType = None
		cur = self._srDBConn.cursor()
		cur.execute("SELECT type FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if row:
			(markerType, ) = row
		cur.close()
		return markerType

	def getMarkerNames(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Serie, Url, info, fsID FROM SerienMarker ORDER BY Serie COLLATE NOCASE")
		rows = cur.fetchall()
		cur.close()
		return rows

	def getMarkerSeasonAndChannelSettings(self, fsID):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, AlleStaffelnAb, alleSender FROM SerienMarker WHERE fsID=?", [fsID])
		row = cur.fetchone()
		if not row:
			row = (0, 999999, 0)
		cur.close()
		return row

	def getMarkerSeasonSettings(self, fsID):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, AlleStaffelnAb, AbEpisode, TimerForSpecials FROM SerienMarker WHERE fsID=?", [fsID])
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

	def updateMarkerSeasonsSettings(self, fsID, fromSeason, fromEpisode, specials):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET AlleStaffelnAb=?, AbEpisode=?, TimerForSpecials=? WHERE fsID=?", (fromSeason, fromEpisode, specials, fsID))
		cur.close()

	def setAllChannelsToMarker(self, fsID, allChannels):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET alleSender=? WHERE fsID=?", (allChannels, fsID))
		cur.close()

	def setMarkerEpisode(self, fsID, fromEpisode):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE SerienMarker SET AbEpisode=? WHERE fsID=?", (int(fromEpisode), fsID))
		cur.close()

	def changeMarkerStatus(self, fsID, boxID):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		row = cur.fetchone()
		if row:
			(ID, ErlaubteSTB) = row
			if ErlaubteSTB is not None:
				ErlaubteSTB ^= (1 << (int(boxID) - 1))
				cur.execute("UPDATE OR IGNORE STBAuswahl SET ErlaubteSTB=? WHERE ID=?", (ErlaubteSTB, ID))
		cur.close()

	def setMarkerStatus(self, markerID, boxID, state):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ID, ErlaubteSTB FROM STBAuswahl WHERE ID=?", [markerID])
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

	def removeMarker(self, fsID, removeTimers):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM STBAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		cur.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		cur.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		cur.execute("DELETE FROM SerienMarker WHERE fsID=?", [fsID])
		if removeTimers:
			cur.execute("DELETE FROM AngelegteTimer WHERE fsID=?", [fsID])
		cur.close()

	def removeAllMarkerSeasons(self, fsID):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM StaffelAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		cur.close()

	def removeAllMarkerChannels(self, fsID):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM SenderAuswahl WHERE ID IN (SELECT ID FROM SerienMarker WHERE fsID=?)", [fsID])
		cur.close()

	def getMarkerLastUpdate(self):
		markerLastUpdated = 0
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Value FROM dbInfo WHERE Key='MarkersLastUpdate'")
		row = cur.fetchone()
		if row:
			(markerLastUpdated,) = row
		cur.close()
		return int(markerLastUpdated)

	def setMarkerLastUpdate(self):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE dbInfo SET Value = ? WHERE Key='MarkersLastUpdate'", [int(time.time())])
		cur.close()

	def timerExists(self, channel, fsID, season, episode, startUnixtimeLowBound, startUnixtimeHighBound):
		cur = self._srDBConn.cursor()
		sql = "SELECT COUNT(*) FROM AngelegteTimer WHERE LOWER(webChannel)=? AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (channel.lower(), fsID, str(season).lower(), episode.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		found = (cur.fetchone()[0] > 0)
		cur.close()
		return found

	def timerExistsByServiceRef(self, fsID, stbRef, startUnixtimeLowBound, startUnixtimeHighBound):
		cur = self._srDBConn.cursor()
		sql = "SELECT COUNT(*) FROM AngelegteTimer WHERE fsID=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (fsID, stbRef.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		found = (cur.fetchone()[0] > 0)
		cur.close()
		return found

	def getNumberOfTimersByBouquet(self, fsID, season, episode, title=None):
		cur = self._srDBConn.cursor()
		if title is None:
			cur.execute("SELECT COUNT(*), LENGTH(c.STBChannel) > 0, LENGTH(c.alternativSTBChannel) > 0 FROM AngelegteTimer as t, Channels AS c WHERE LOWER(c.webChannel) = LOWER(t.webChannel) AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND TimerAktiviert=1 AND c.Erlaubt=1", (fsID, str(season).lower(), str(episode).lower()))
		else:
			cur.execute("SELECT COUNT(*), LENGTH(c.STBChannel) > 0, LENGTH(c.alternativSTBChannel) > 0 FROM AngelegteTimer as t, Channels AS c WHERE LOWER(c.webChannel) = LOWER(t.webChannel) AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND TimerAktiviert=1 AND c.Erlaubt=1", (fsID, str(season).lower(), str(episode).lower(), title.lower()))

		rows = cur.fetchall()
		count_primary_bouquet = 0
		count_secondary_bouquet = 0
		for row in rows:
			(count, primary_bouquet, secondary_bouquet) = row
			if primary_bouquet and primary_bouquet > 0:
				count_primary_bouquet += count
			elif secondary_bouquet and secondary_bouquet > 0:
				count_secondary_bouquet += count

		if title is None:
			cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE webChannel='' AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND TimerAktiviert=1", (fsID, str(season).lower(), str(episode).lower()))
		else:
			cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE webChannel='' AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND TimerAktiviert=1", (fsID, str(season).lower(), str(episode).lower(), title.lower()))
		(count_manually,) = cur.fetchone()
		cur.close()

		return count_manually, count_primary_bouquet, count_secondary_bouquet

	def getNumberOfTimers(self, fsID, season, episode, title=None, searchOnlyActiveTimers=False):
		cur = self._srDBConn.cursor()
		if searchOnlyActiveTimers:
			if title is None:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND TimerAktiviert=1", (fsID, str(season).lower(), str(episode).lower()))
			else:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=? AND TimerAktiviert=1", (fsID, str(season).lower(), str(episode).lower(), title.lower()))
		else:
			if title is None:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (fsID, str(season).lower(), str(episode).lower()))
			else:
				cur.execute("SELECT COUNT(*) FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Titel)=?", (fsID, str(season).lower(), str(episode).lower(), title.lower()))
		(Anzahl,) = cur.fetchone()
		cur.close()
		return Anzahl

	def getTimerForSeries(self, fsID, searchOnlyActiveTimers=False):
		cur = self._srDBConn.cursor()
		if searchOnlyActiveTimers:
			cur.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE fsID=? AND TimerAktiviert=1 ORDER BY CAST(Staffel AS INTEGER), Episode", [fsID])
		else:
			cur.execute("SELECT Staffel, Episode, Titel, LOWER(webChannel), StartZeitstempel FROM AngelegteTimer WHERE fsID=? ORDER BY CAST(Staffel AS INTEGER), Episode", [fsID])

		rows = cur.fetchall()
		cur.close()
		return rows

	def getAllTimer(self, startUnixtime):
		cur = self._srDBConn.cursor()
		if startUnixtime:
			cur.execute("SELECT ROWID, * FROM AngelegteTimer WHERE StartZeitstempel>=?", [startUnixtime])
		else:
			cur.execute("SELECT ROWID, * FROM AngelegteTimer")

		rows = cur.fetchall()
		cur.close()
		return rows

	def isBouquetActive(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT LENGTH(STBChannel) > 0, LENGTH(alternativSTBChannel) > 0 FROM Channels WHERE LOWER(webChannel)=? AND Erlaubt=1", [channel.lower()])
		row = cur.fetchone()
		if not row:
			row = (0, 0)
		(is_stb_channel, is_alt_stb_channel) = row
		cur.close()
		return bool(is_stb_channel), bool(is_alt_stb_channel)

	def getActiveServiceRefs(self):
		serviceRefs = {}
		cur = self._srDBConn.cursor()
		cur.execute("SELECT WebChannel, ServiceRef, STBChannel, alternativServiceRef, alternativSTBChannel FROM Channels WHERE Erlaubt=1 ORDER BY LOWER(WebChannel)")
		rows = cur.fetchall()
		for row in rows:
			(webChannel, serviceRef, stbChannel, alternativeServiceRef, alternativeSTBChannel) = row
			serviceRefs[webChannel] = (serviceRef, stbChannel, alternativeServiceRef, alternativeSTBChannel)
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

	def getSTBChannelRef(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ServiceRef, alternativServiceRef FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		row = cur.fetchone()
		cur.close()
		return row

	def getChannelsSettings(self, channel):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Vorlaufzeit, Nachlaufzeit, vps, autoAdjust FROM Channels WHERE LOWER(WebChannel)=?", [channel.lower()])
		row = cur.fetchone()
		if not row:
			row = (None, None, 0, None)
		(Vorlaufzeit, Nachlaufzeit, vps, autoAdjust) = row
		cur.close()
		return Vorlaufzeit, Nachlaufzeit, vps, autoAdjust

	def setChannelSettings(self, channel, leadTime, followUpTime, vps, autoAdjust):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE Channels SET Vorlaufzeit=?, Nachlaufzeit=?, vps=?, autoAdjust=? WHERE LOWER(WebChannel)=?", (leadTime, followUpTime, vps, autoAdjust, channel.lower()))
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

	def setChannelListLastUpdate(self):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE dbInfo SET Value=? WHERE Key='ChannelsLastUpdate'", [int(time.time())])
		cur.close()

	def getChannelListLastUpdate(self):
		localChannelListLastUpdated = 0
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Value FROM dbInfo WHERE Key='ChannelsLastUpdate'")
		row = cur.fetchone()
		if row:
			(localChannelListLastUpdated,) = row
		cur.close()
		return localChannelListLastUpdated

	def getChannelInfo(self, channel, fsID, filterMode):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT DISTINCT alleSender, SerienMarker.ID FROM SenderAuswahl, SerienMarker WHERE SerienMarker.fsID = ?", [fsID])
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


	def getMarkerChannels(self, fsID, withActiveChannels = True):
		channels = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ErlaubterSender FROM SenderAuswahl INNER JOIN SerienMarker ON SenderAuswahl.ID=SerienMarker.ID WHERE SerienMarker.fsID=? ORDER BY LOWER(ErlaubterSender)", [fsID])
		rows = cur.fetchall()
		if len(rows) > 0:
			channels = [x[0] for x in rows]

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

	def removeAllChannels(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM SenderAuswahl")
		cur.execute("DELETE FROM Channels")
		cur.execute("VACUUM")
		cur.close()

	def getAllowedSeasons(self, seriesID, fromSeason):
		seasons = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ErlaubteStaffel FROM StaffelAuswahl WHERE ID=? AND ErlaubteStaffel<? ORDER BY ErlaubteStaffel", (seriesID, fromSeason))
		rows = cur.fetchall()
		if len(rows) > 0:
			seasons = [x[0] for x in rows]
		cur.close()
		return seasons

	def getMarkers(self, boxID, numberOfRecordings, seriesFilter = None):
		result = []
		cur = self._srDBConn.cursor()

		if seriesFilter:
			cur.execute("SELECT ID, Serie, Url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays, skipSeriesServer, type, fsID FROM SerienMarker WHERE fsID IN(%s) ORDER BY Serie" % ','.join('?' * len(seriesFilter)), seriesFilter)
		else:
			cur.execute("SELECT ID, Serie, Url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays, skipSeriesServer, type, fsID FROM SerienMarker ORDER BY Serie")
		rows = cur.fetchall()
		for row in rows:
			(ID, serie, url, AlleStaffelnAb, alleSender, AnzahlWiederholungen, AbEpisode, excludedWeekdays, skipSeriesServer, markerType, fsID) = row
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
				channels = self.getMarkerChannels(fsID, False)

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

			if str(skipSeriesServer).isdigit():
				skipSeriesServer = bool(skipSeriesServer)
			else:
				skipSeriesServer = None

			result.append((serie, url, seasons, channels, AbEpisode, AnzahlAufnahmen, enabled, excludedWeekdays, skipSeriesServer, markerType, fsID))
		cur.close()
		return result


	def addToTimerList(self, series, fsID, fromEpisode, toEpisode, season, episodeTitle, startUnixtime, stbRef, webChannel, eit, activated):
		# Es gibt Episodennummern die nicht nur aus Zahlen bestehen, z.B. 14a
		# um solche Folgen in die Datenbank zu bringen wird hier eine Unterscheidung gemacht.
		result = False
		cur = self._srDBConn.cursor()
		if fromEpisode == toEpisode:
			cur.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (series, season, str(fromEpisode).zfill(2), episodeTitle, int(startUnixtime), stbRef, webChannel, eit, int(activated), fsID))
			result = True
		else:
			if int(fromEpisode) != 0 or int(toEpisode) != 0:
				for i in range(int(fromEpisode), int(toEpisode)+1):
					print("[SerienRecorder] %s Staffel: %s Episode: %s " % (str(series), str(season), str(i)))
					cur.execute("INSERT OR IGNORE INTO AngelegteTimer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (series, season, str(i).zfill(2), episodeTitle, int(startUnixtime), stbRef, webChannel, eit, int(activated), fsID))
				result = True
		cur.close()
		return result

	def updateTimerEIT(self, fsID, stbRef, eit, startUnixtimeLowBound, startUnixtimeHighBound, activated):
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE AngelegteTimer SET EventID=?, TimerAktiviert=? WHERE fsID=? AND LOWER(ServiceRef)=? AND StartZeitstempel>=? AND StartZeitstempel<=?"
		cur.execute(sql, (eit, int(activated), fsID, stbRef.lower(), startUnixtimeLowBound, startUnixtimeHighBound))
		cur.close()

	def updateTimerStartTime(self, newStartUnixtime, eit, title, oldStartUnixtime, stbRef):
		cur = self._srDBConn.cursor()
		sql = "UPDATE OR IGNORE AngelegteTimer SET StartZeitstempel=?, EventID=?, Titel=? WHERE StartZeitstempel=? AND LOWER(ServiceRef)=?"
		cur.execute(sql, (newStartUnixtime, eit, title, oldStartUnixtime, stbRef.lower()))
		cur.close()

	def removeTimer(self, fsID, season, episode, title, startUnixtime, channel):
		cur = self._srDBConn.cursor()
		if not startUnixtime and not channel:
			if title:
				cur.execute("DELETE FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND (LOWER(Titel)=? OR Titel=? OR Titel='')", (fsID, season.lower(), str(episode).zfill(2).lower(), title.lower(), "dump"))
			else:
				cur.execute("DELETE FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=?", (fsID, season.lower(), str(episode).zfill(2).lower()))
		else:
			if not fsID:
				cur.execute("DELETE FROM AngelegteTimer WHERE LOWER(Staffel)=? AND Episode=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (season.lower(), episode, startUnixtime, channel.lower()))
			else:
				cur.execute("DELETE FROM AngelegteTimer WHERE fsID=? AND LOWER(Staffel)=? AND Episode=? AND StartZeitstempel=? AND LOWER(webChannel)=?", (fsID, season.lower(), episode, startUnixtime, channel.lower()))
		cur.close()

	def removeTimers(self, row_ids):
		cur = self._srDBConn.cursor()
		for row_id in row_ids:
			print("[SerienRecorder] RemoveTimers: %d" % row_id)
			cur.execute("DELETE FROM AngelegteTimer WHERE ROWID=?", [row_id])
		cur.close()

	def removeTimersBySeason(self, fsID, maxSeason, fromEpisode, allowedSeasons, allowSpecials):
		numberOfRemovedTimers = 0
		cur = self._srDBConn.cursor()
		if maxSeason == 999999:
			cur.execute("DELETE FROM AngelegteTimer WHERE fsID=? AND CAST(Staffel AS INT) = 0 AND CAST(Episode AS INT)<?", (fsID, int(fromEpisode)))
			numberOfRemovedTimers = cur.rowcount
		else:
			bindings = (fsID, int(maxSeason))
			sqlStatement = "DELETE FROM AngelegteTimer WHERE fsID=? AND CAST(Staffel AS INT)<? AND CAST(Staffel AS INT)"
			if len(allowedSeasons) > 0:
				sqlStatement += "  NOT IN (%s)" % ','.join('?' * len(allowedSeasons))
				bindings += tuple(allowedSeasons)
			if allowSpecials:
				sqlStatement += " AND Staffel == CAST(Staffel AS INTEGER)"
			cur.execute(sqlStatement, bindings)
			numberOfRemovedTimers = cur.rowcount
		cur.close()
		return numberOfRemovedTimers

	def removeAllOldTimer(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM AngelegteTimer WHERE StartZeitstempel<?", [int(time.time())])
		cur.close()

	def getDeactivatedTimers(self):
		timers = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT Serie, fsID, Staffel, Episode, Titel, StartZeitstempel, ServiceRef, webChannel, EventID FROM AngelegteTimer WHERE TimerAktiviert=0 AND StartZeitstempel>=?", [int(time.time())])
		rows = cur.fetchall()
		for row in rows:
			(serien_name, serien_fsid, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit) = row
			timers.append((serien_name, serien_fsid, staffel, episode, serien_title, serien_time, stbRef, webChannel, eit))
		cur.close()
		return timers

	def activateTimer(self, fsID, season, episode, title, startUnixtime, stbRef, channel, eit):
		cur = self._srDBConn.cursor()
		cur.execute("UPDATE OR IGNORE AngelegteTimer SET TimerAktiviert=1 WHERE fsID=? AND Staffel=? AND Episode=? AND Titel=? AND StartZeitstempel=? AND ServiceRef=? AND webChannel=? AND EventID=?", (fsID, season, episode, title, startUnixtime, stbRef, channel, eit))
		cur.close()

	def countOrphanTimers(self):
		cur = self._srDBConn.cursor()
		cur.execute("SELECT DISTINCT(Serie) AS name FROM AngelegteTimer WHERE (fsID NOT IN (SELECT fsID FROM SerienMarker) OR fsID IS NULL) AND Staffel != '0' AND Episode != '00'")
		rows = cur.fetchall()
		if len(rows):
			SRLogger.writeLog("\nFür folgende Serien wurden verwaiste Timereinträge gefunden:", True)
		for row in rows:
			(serien_name) = row
			SRLogger.writeLog("%s" % serien_name, True)
		cur.close()
		return len(rows)

	def removeOrphanTimers(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM AngelegteTimer WHERE (fsID NOT IN (SELECT fsID FROM SerienMarker) OR fsid IS NULL) AND Staffel != '0' AND Episode != '00'")
		cur.close()

# ----------------------------------------------------------------------------------------------------------------------

	def getUndoTimer(self):
		timers = []
		cur = self._srDBConn.cursor()
		cur.execute("SELECT ROWID, series, season, episode, title, fsid, STRFTIME('%d.%m.%Y - %H:%M', created) as created FROM undolog_timer ORDER BY created DESC")
		rows = cur.fetchall()
		for row in rows:
			(row_id, series_name, season, episode, title, fsID, created) = row
			timers.append((row_id, series_name, season, episode, title, fsID, created))
		cur.close()
		return timers

	def deleteUndoTimer(self, row_id):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM undolog_timer WHERE ROWID=?", [row_id])
		cur.close()

	def restoreUndoTimerByID(self, row_id):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT INTO AngelegteTimer SELECT series, season, episode, title, starttime, serviceref, webchannel, eventid, active, fsid FROM undolog_timer WHERE ROWID=?", [row_id])
		cur.execute("DELETE FROM undolog_timer WHERE ROWID=?", [row_id])
		cur.close()

	def restoreUndoTimerBySeries(self, fsid):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT INTO AngelegteTimer SELECT series, season, episode, title, starttime, serviceref, webchannel, eventid, active, fsid FROM undolog_timer WHERE fsid=?", [fsid])
		cur.execute("DELETE FROM undolog_timer WHERE fsid=?", [fsid])
		cur.close()

	def restoreUndoTimerByDate(self, date):
		cur = self._srDBConn.cursor()
		cur.execute("INSERT INTO AngelegteTimer SELECT series, season, episode, title, starttime, serviceref, webchannel, eventid, active, fsid FROM undolog_timer WHERE STRFTIME('%d.%m.%Y', created)=?", [date])
		cur.execute("DELETE FROM undolog_timer WHERE STRFTIME('%d.%m.%Y', created)=?", [date])
		cur.close()

	def removeExpiredUndoTimer(self):
		cur = self._srDBConn.cursor()
		cur.execute("DELETE FROM undolog_timer WHERE created < date('now', '-30 day')")
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

	def beginTransaction(self):
		self._tempDBConn.execute("begin")

	def commitTransaction(self):
		self._tempDBConn.execute("commit")

	def close(self):
		if self._tempDBConn:
			self._tempDBConn.close()
			self._tempDBConn = None

	def initialize(self):
		cur = self._tempDBConn.cursor()
		cur.execute('''CREATE TABLE IF NOT EXISTS GefundeneFolgen ( CurrentTime INTEGER,
																	FutureTime INTEGER,
																	SerieName TEXT,
																	wlID INTEGER,
																	fsID TEXT,
																	type INTEGER DEFAULT 0,
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
																	alternativStbChannel TEXT, 
																	alternativServiceRef TEXT, 
																	DirName TEXT,
																	AnzahlAufnahmen INTEGER,
																	AufnahmezeitVon INTEGER,
																	AufnahmezeitBis INTEGER,
																	vomMerkzettel INTEGER DEFAULT 0,
																	excludedWeekdays INTEGER DEFAULT NULL,
																	updateFromEPG INTEGER DEFAULT 1,
																	source INTEGER DEFAULT NULL)''')

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
		sql = "INSERT OR IGNORE INTO GefundeneFolgen (CurrentTime, FutureTime, SerieName, wlID, fsID, type, Staffel, Episode, SeasonEpisode," \
		      " Title, LabelSerie, webChannel, stbChannel, ServiceRef, StartTime, EndTime, alternativStbChannel, alternativServiceRef, DirName," \
		      " AnzahlAufnahmen, AufnahmezeitVon, AufnahmezeitBis, vomMerkzettel, excludedWeekdays, updateFromEPG, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
		cur.execute(sql, transmission[0])
		cur.close()

	def getTransmissionForTimerUpdate(self, fsID, season, episode, start_time, webChannel):
		result = None
		cur = self._tempDBConn.cursor()
		cur.execute("SELECT SerieName, wlID, fsID, Staffel, Episode, Title, StartTime, EndTime, updateFromEPG FROM GefundeneFolgen WHERE StartTime>=? AND fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(webChannel)=? ORDER BY StartTime", (start_time, fsID, season.lower(), episode.lower(), webChannel.lower()))
		row = cur.fetchone()
		if row:
			result = row
		cur.close()
		return result

	def getTransmissionsOrderedByNumberOfRecordings(self, numberOfRecordings):
		result = []
		cur = self._tempDBConn.cursor()
		cur.execute("SELECT * FROM (SELECT SerieName, wlID, fsID, type, Staffel, Episode, Title, COUNT(*) AS Anzahl FROM GefundeneFolgen WHERE AnzahlAufnahmen>? GROUP BY wlID, Staffel, Episode, Title) ORDER BY Anzahl", [numberOfRecordings])
		rows = cur.fetchall()
		for row in rows:
			result.append(row)
		cur.close()
		return result

	def getTransmissionsToCreateTimer(self, fsID, season, episode, title = None):
		result = []
		cur = self._tempDBConn.cursor()
		if title:
			cur.execute("SELECT * FROM GefundeneFolgen WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime>=CurrentTime ORDER BY StartTime", (fsID, str(season).lower(), str(episode).lower(), title.lower()))
		else:
			cur.execute("SELECT * FROM GefundeneFolgen WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime>=CurrentTime ORDER BY StartTime", (fsID, str(season).lower(), str(episode).lower()))
		rows = cur.fetchall()
		for row in rows:
			result.append(row)
		cur.close()
		return result

	def removeTransmission(self, fsID, season, episode, title, startUnixtime, stbRef):
		cur = self._tempDBConn.cursor()
		if title:
			cur.execute("DELETE FROM GefundeneFolgen WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND LOWER(Title)=? AND StartTime=? AND LOWER(ServiceRef)=?", (fsID, str(season).lower(), episode.lower(), title.lower(), startUnixtime, stbRef.lower()))
		else:
			cur.execute("DELETE FROM GefundeneFolgen WHERE fsID=? AND LOWER(Staffel)=? AND LOWER(Episode)=? AND StartTime=? AND LOWER(ServiceRef)=?", (fsID, str(season).lower(), episode.lower(), startUnixtime, stbRef.lower()))
		cur.close()

	def countTransmissions(self, source):
		cur = self._tempDBConn.cursor()
		cur.execute("SELECT COUNT(*), COUNT(DISTINCT wlID) FROM GefundeneFolgen WHERE source = ?", [source])
		(number_of_transmissions, number_of_series) = cur.fetchone()
		cur.close()
		return (number_of_transmissions, number_of_series)