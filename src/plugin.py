# -*- coding: utf-8 -*-
from Plugins.Plugin import PluginDescriptor
import SerienRecorder

def SRstart(session, **kwargs):
	reload(SerienRecorder)
	try:
		session.open(SerienRecorder.serienRecMain)
	except:
		import traceback
		traceback.print_exc()

def Plugins(**kwargs):
	return [
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.",where = [PluginDescriptor.WHERE_PLUGINMENU], icon = "plugin.png", fnc=SRstart),
		PluginDescriptor(name="SerienRecorder", description="Record your favorite series.", where = [PluginDescriptor.WHERE_EXTENSIONSMENU], fnc=SRstart)
		]