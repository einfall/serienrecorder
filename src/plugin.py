# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists
import os
import SerienRecorder
#import SerienRecorderResource
import SerienRecorderHelpers
import SerienRecorderSeriesServer
import SerienRecorderScreenHelpers
import SerienRecorderUpdateScreen
import SerienRecorderAboutScreen
import SerienRecorderChannelScreen
import SerienRecorderSplashScreen
import SerienRecorderStartupInfoScreen
import SerienRecorderMarkerScreen
import SerienRecorderSeasonBeginsScreen
import SerienRecorderSeriesInfoScreen
import SerienRecorderConflictsScreen
import SerienRecorderFileListScreen
import SerienRecorderLogScreen
import SerienRecorderSearchResultScreen
import SerienRecorderSetupScreen
import SerienRecorderTimerListScreen
import SerienRecorderWishlistScreen
import SerienRecorderMainScreen
import SerienRecorderTVPlaner
import SerienRecorderLogWriter

def SRstart(session, **kwargs):

	for file_name in (('SerienRecorder', SerienRecorder),
					  #('SerienRecorderResource', SerienRecorderResource),
					  ('SerienRecorderSeriesServer', SerienRecorderSeriesServer),
					  ('SerienRecorderScreenHelpers', SerienRecorderScreenHelpers),
					  ('SerienRecorderHelpers', SerienRecorderHelpers),
					  ('SerienRecorderUpdateScreen', SerienRecorderUpdateScreen),
					  ('SerienRecorderAboutScreen', SerienRecorderAboutScreen),
					  ('SerienRecorderChannelScreen', SerienRecorderChannelScreen),
					  ('SerienRecorderSplashScreen', SerienRecorderSplashScreen),
					  ('SerienRecorderStartupInfoScreen', SerienRecorderStartupInfoScreen),
					  ('SerienRecorderMarkerScreen', SerienRecorderMarkerScreen),
					  ('SerienRecorderSeasonBeginScreen', SerienRecorderSeasonBeginsScreen),
					  ('SerienRecorderSeriesInfoScreen', SerienRecorderSeriesInfoScreen),
					  ('SerienRecorderConflictsScreen', SerienRecorderConflictsScreen),
					  ('SerienRecorderFileListScreen', SerienRecorderFileListScreen),
					  ('SerienRecorderLogScreen', SerienRecorderLogScreen),
					  ('SerienRecorderSearchResultScreen', SerienRecorderSearchResultScreen),
					  ('SerienRecorderSetupScreen', SerienRecorderSetupScreen),
					  ('SerienRecorderTimerListScreen', SerienRecorderTimerListScreen),
					  ('SerienRecorderWishlistScreen', SerienRecorderWishlistScreen),
					  ('SerienRecorderMainScreen', SerienRecorderMainScreen),
					  ('SerienRecorderTVPlaner', SerienRecorderTVPlaner),
					  ('SerienRecorderLogWriter', SerienRecorderLogWriter)):
		if fileExists(os.path.join(SerienRecorder.serienRecMainPath, "%s.pyo" % file_name[0])):
			if (int(os.path.getmtime(os.path.join(SerienRecorder.serienRecMainPath, "%s.pyo" % file_name[0]))) < int(
					os.path.getmtime(os.path.join(SerienRecorder.serienRecMainPath, "%s.py" % file_name[0])))):
				reload(file_name[1])
		else:
			reload(file_name[1])

	try:
		session.open(SerienRecorderMainScreen.serienRecMainScreen)
	except:
		import traceback
		traceback.print_exc()


# Movielist
def movielist(session, service, **kwargs):
	from enigma import eServiceCenter

	def handleSeriesSearchEnd(seriesName=None):
		if seriesName:
			session.open(SerienRecorderMarkerScreen.serienRecMarker, seriesName)

	serviceHandler = eServiceCenter.getInstance()
	info = serviceHandler.info(service)
	seriesName = info and info.getName(service) or ""
	if seriesName:
		SerienRecorder.initDB()
		session.open(SerienRecorderSearchResultScreen.serienRecSearchResultScreen, seriesName)
		session.openWithCallback(handleSeriesSearchEnd, SerienRecorderSearchResultScreen.serienRecSearchResultScreen, seriesName)

# Event Info
def eventinfo(session, servicelist, **kwargs):
	SerienRecorder.initDB()
	ref = session.nav.getCurrentlyPlayingServiceReference()
	session.open(SerienRecorder.serienRecEPGSelection, ref)

def Plugins(**kwargs):
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
						 fnc=SerienRecorder.autostart, wakeupfnc=SerienRecorder.getNextWakeup),
		PluginDescriptor(name="SerienRecorder", description="Nie wieder eine Folge deiner Lieblingsserie verpassen",
						 where=[PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Nie wieder eine Folge deiner Lieblingsserie verpassen",
						 where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Serien-Marker hinzufügen...",
						 where=[PluginDescriptor.WHERE_MOVIELIST], fnc=movielist, needsRestart=False),
		PluginDescriptor(name="Serien-Marker hinzufügen...", where=[PluginDescriptor.WHERE_EVENTINFO], fnc=eventinfo,
						 needsRestart=False),

	]
