# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists
import os
import SerienRecorder

serienRecMainPath = "/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/"

def SRstart(session, **kwargs):
	if fileExists(os.path.join(serienRecMainPath, "SerienRecorder.pyo")):
		if (int(os.path.getmtime(os.path.join(serienRecMainPath, "SerienRecorder.pyo"))) < int(os.path.getmtime(os.path.join(serienRecMainPath, "SerienRecorder.py")))):
			reload(SerienRecorder)
	else:	
		reload(SerienRecorder)
		
	try:
		session.open(SerienRecorder.serienRecMain)
	except:
		import traceback
		traceback.print_exc()

def Plugins(**kwargs):
	return [
		PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=SerienRecorder.autostart, wakeupfnc=SerienRecorder.getNextWakeup),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.",where = [PluginDescriptor.WHERE_PLUGINMENU], icon = "plugin.png", fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Record your favourite series.", where = [PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=SRstart)
		]