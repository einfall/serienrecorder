# -*- coding: utf-8 -*-

default_timer_patterns = [
		("{serie:s}", "Serienname"),
		("{serie:s} - S{staffel:s}E{episode:s}", "Serienname - S01E01"),
		("{serie:s} S{staffel:s}E{episode:s}", "Serienname S01E01"),
		("{serie:s} - S{staffel:s}E{episode:s} - {titel:s}", "Serienname - S01E01 - Episodenname"),
		("{serie:s} S{staffel:s}E{episode:s} {titel:s}", "Serienname S01E01 Episodenname"),
		("{serie:s} {titel:s}", "Serienname Episodenname"),
		("{serie:s} - {titel:s}", "Serienname - Episodenname"),

		("S{staffel:s}E{episode:s} - {titel:s}", "S01E01 - Episodenname"),
		("S{staffel:s}E{episode:s} - {titel:s}", "S01E01 Episodenname"),
		("S{staffel:s}E{episode:s}", "S01E01"),

		("{titel:s} S{staffel:s}E{episode:s}", "Episodenname - S01E01"),
		("{titel:s} S{staffel:s}E{episode:s}", "Episodenname S01E01"),
		("{titel:s}", "Episodenname"),
		("{titel:s} {serie:s}", "Episodenname Serienname"),
		("{titel:s} - {serie:s}", "Episodenname - Serienname")
	]

def readTimerPatterns():
	import os, json
	path = "/etc/enigma2/SerienRecorder.timer-pattern.json"
	patterns = None

	if os.path.exists(path):
		f = None
		try:
			f = open(path, 'rb')
			header, patterns = json.load(f)
			patterns = [tuple(p) for p in patterns]
		except Exception as e:
			from .SerienRecorderLogWriter import SRLogger
			print("Pattern file is corrupt [%s]" % str(e))
			SRLogger.writeLog("Muster-Datei %s konnte nicht verarbeitet werden: %s" % (path, str(e)), True)
		finally:
			if f is not None:
				f.close()
	return patterns or default_timer_patterns
