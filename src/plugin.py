# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists
import os
import SerienRecorder
import SerienRecorderResource
import SerienRecorderHelpers
import SerienRecorderSeriesServer
import SerienRecorderScreenHelpers
import SerienRecorderUpdateScreen
import SerienRecorderAboutScreen
import SerienRecorderChannelScreen
import SerienRecorderSplashScreen
import SerienRecorderStartupInfoScreen
import SerienRecorderMarkerScreen
import SerienRecorderShowSeasonBeginsScreen

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/SerienRecorder/"

def SRstart(session, **kwargs):

	for file_name in (('SerienRecorder', SerienRecorder),
					  ('SerienRecorderResource', SerienRecorderResource),
					  ('SerienRecorderSeriesServer', SerienRecorderSeriesServer),
					  ('SerienRecorderScreenHelpers', SerienRecorderScreenHelpers),
					  ('SerienRecorderHelpers', SerienRecorderHelpers),
					  ('SerienRecorderUpdateScreen', SerienRecorderUpdateScreen),
					  ('SerienRecorderAboutScreen', SerienRecorderAboutScreen),
					  ('SerienRecorderChannelScreen', SerienRecorderChannelScreen),
					  ('SerienRecorderSplashScreen', SerienRecorderSplashScreen),
					  ('SerienRecorderStartupInfoScreen', SerienRecorderStartupInfoScreen),
					  ('SerienRecorderMarkerScreen', SerienRecorderMarkerScreen),
					  ('SerienRecorderShowSeasonBeginScreen', SerienRecorderShowSeasonBeginsScreen)):
		if fileExists(os.path.join(serienRecMainPath, "%s.pyo" % file_name[0])):
			if (int(os.path.getmtime(os.path.join(serienRecMainPath, "%s.pyo" % file_name[0]))) < int(
					os.path.getmtime(os.path.join(serienRecMainPath, "%s.py" % file_name[0])))):
				reload(file_name[1])
		else:
			reload(file_name[1])

	try:
		session.open(SerienRecorder.serienRecMain)
	except:
		import traceback
		traceback.print_exc()


# Movielist
def movielist(session, service, **kwargs):
	from enigma import eServiceCenter, eServiceReference, iServiceInformation

	def handleSeriesSearchEnd(seriesName=None):
		if seriesName:
			session.open(SerienRecorder.serienRecMarker, seriesName)

	serviceHandler = eServiceCenter.getInstance()
	info = serviceHandler.info(service)
	seriesName = info and info.getName(service) or ""
	if seriesName:
		SerienRecorder.initDB()
		session.open(SerienRecorder.serienRecAddSerie, seriesName)
		session.openWithCallback(handleSeriesSearchEnd, SerienRecorder.serienRecAddSerie, seriesName)

# Event Info
def eventinfo(session, servicelist, **kwargs):
	SerienRecorder.initDB()
	ref = session.nav.getCurrentlyPlayingServiceReference()
	session.open(SerienRecorder.serienRecEPGSelection, ref)

def Plugins(**kwargs):
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
						 fnc=SerienRecorder.autostart, wakeupfnc=SerienRecorder.getNextWakeup),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.",
						 where=[PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.",
						 where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Serien-Marker hinzufügen...",
						 where=[PluginDescriptor.WHERE_MOVIELIST], fnc=movielist, needsRestart=False),
		PluginDescriptor(name="Serien-Marker hinzufügen...", where=[PluginDescriptor.WHERE_EVENTINFO], fnc=eventinfo,
						 needsRestart=False),

	]
