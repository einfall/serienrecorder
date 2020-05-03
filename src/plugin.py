# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists

import os
import SerienRecorder
import SerienRecorderMarkerScreen
import SerienRecorderSearchResultScreen
import SerienRecorderMainScreen

def SRstart(session, **kwargs):

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

	def handleSeriesSearchEnd(series_wlid=None):
		if series_wlid:
			session.open(SerienRecorderMarkerScreen.serienRecMarker, series_wlid)

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

	def handleSeriesSearchEnd(series_wlid=None):
		if series_wlid:
			session.open(SerienRecorderMarkerScreen.serienRecMarker, series_wlid)

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
