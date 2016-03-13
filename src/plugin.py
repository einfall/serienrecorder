# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists
import os
import SerienRecorder
import SearchEvents
import SearchSerie
import SerienRecorderResource
import SerienRecorderHelpers
import SerienRecorderSeriesServer
import SerienRecorderScreenHelpers
import SerienRecorderUpdateScreen
import SerienRecorderAboutScreen
import SerienRecorderChannelScreen
import SerienRecorderSplashScreen
import SerienRecorderStartupInfoScreen

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"

def SRstart(session, **kwargs):

	for file_name in (('SerienRecorder', SerienRecorder),
	                  ('SearchEvents', SearchEvents),
	                  ('SearchSerie', SearchSerie),
	                  ('SerienRecorderResource', SerienRecorderResource),
	                  ('SerienRecorderSeriesServer', SerienRecorderSeriesServer),
	                  ('SerienRecorderScreenHelpers', SerienRecorderScreenHelpers),
	                  ('SerienRecorderHelpers', SerienRecorderHelpers),
	                  ('SerienRecorderUpdateScreen', SerienRecorderUpdateScreen),
	                  ('SerienRecorderAboutScreen', SerienRecorderAboutScreen),
	                  ('SerienRecorderChannelScreen', SerienRecorderChannelScreen),
	                  ('SerienRecorderSplashScreen', SerienRecorderSplashScreen),
	                  ('SerienRecorderStartupInfoScreen', SerienRecorderStartupInfoScreen)):
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


def Plugins(**kwargs):
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
		                 fnc=SerienRecorder.autostart, wakeupfnc=SerienRecorder.getNextWakeup),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.",
		                 where=[PluginDescriptor.WHERE_PLUGINMENU], icon="plugin.png", fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.",
		                 where=[PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=SRstart)
	]
