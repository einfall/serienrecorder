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
import SerienRecorderCoverSelectorScreen

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
					  ('SerienRecorderLogWriter', SerienRecorderLogWriter),
	                  ('SerienRecorderCoverSelectorScreen', SerienRecorderCoverSelectorScreen)):
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
		from Screens.MessageBox import MessageBox
		from Components.config import config, configfile
		traceback.print_exc()
		session.popCurrent()
		config.plugins.serienRec.SkinType.value = ""
		config.plugins.serienRec.SkinType.save()
		configfile.save()
		session.open(MessageBox, "Der SerienRecorder Skin kann nicht geladen werden!\n\nDer SerienRecorder Skin wird zurückgesetzt, versuchen Sie den SerienRecorder erneut zu starten.", MessageBox.TYPE_INFO, timeout=0)

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

# EventView or EPGSelection
def eventview(session, event, ref):

	def handleSeriesSearchEnd(seriesName=None):
		if seriesName:
			session.open(SerienRecorderMarkerScreen.serienRecMarker, seriesName)

	if ref.getPath() and ref.getPath()[0] == "/":
		from enigma import eServiceReference
		movielist(session, eServiceReference(str(ref)))
	else:
		seriesName = event and event.getEventName() or ""
		if seriesName:
			from SerienRecorderSearchResultScreen import serienRecSearchResultScreen
			session.openWithCallback(handleSeriesSearchEnd, serienRecSearchResultScreen, seriesName)


def Plugins(**kwargs):
	try:
		from enigma import eMediaDatabase
	except ImportError:
		isDreamboxOS = False
	else:
		isDreamboxOS = True

	pluginDescriptors = [
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

	if isDreamboxOS and hasattr(PluginDescriptor, "WHERE_EVENTVIEW"):
		pluginDescriptors.append(PluginDescriptor(name="Serien-Marker hinzufügen...", where=[PluginDescriptor.WHERE_EVENTVIEW, PluginDescriptor.WHERE_EPG_SELECTION_SINGLE_BLUE], fnc=eventview, needsRestart=False, weight=100))

	return pluginDescriptors
