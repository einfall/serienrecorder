# coding=utf-8

# This file contains the SerienRecoder Startup Info Screen
# showing the release notes of the latest version
from Screens.Screen import Screen
from Tools.Directories import fileExists
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from enigma import eListboxPythonMultiContent, gFont, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from skin import parseColor

from .SerienRecorderScreenHelpers import skinFactor

import os, re

class ShowStartupInfo(Screen):
	DESKTOP_WIDTH  = getDesktop(0).size().width()
	DESKTOP_HEIGHT = getDesktop(0).size().height()

	BUTTON_X = DESKTOP_WIDTH / 2
	BUTTON_Y = DESKTOP_HEIGHT - 220

	skin = """
		<screen name="SerienRecorderHints" position="%d,%d" size="%d,%d" title="%s" backgroundColor="#26181d20">
			<widget name="changelog" position="5,5" size="%d,%d" foregroundColor="yellow" foregroundColorSelected="yellow" scrollbarMode="showOnDemand" selectionDisabled="1"/>
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_ok.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_ok" position="%d,%d" size="%d,26" zPosition="1" font="Regular;19" halign="left" backgroundColor="#26181d20" transparent="1" />
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/serienrecorder/images/key_exit.png" position="%d,%d" zPosition="1" size="32,32" alphatest="on" />
			<widget name="text_exit" position="%d,%d" size="%d,26" zPosition="1" font="Regular; 19" halign="left" backgroundColor="#26181d20" transparent="1" />
		</screen>""" % (50, 100, DESKTOP_WIDTH - 100, DESKTOP_HEIGHT - 180, "SerienRecorder Changelog",
		                DESKTOP_WIDTH - 110, DESKTOP_HEIGHT - 235,
		                BUTTON_X + 50, BUTTON_Y,
		                BUTTON_X + 92, BUTTON_Y + 3, BUTTON_X - 100,
		                50, BUTTON_Y,
		                92, BUTTON_Y + 3, BUTTON_X - 100,
						)

	def __init__(self, session):
		self.session = session
		self.serienRecInfoFilePath = "%s/Changelog" % os.path.dirname(__file__)
		self.indent = False

		Screen.__init__(self, session)

		self["actions"] = ActionMap(["SerienRecorderActions",], {
			"ok"    : self.keyOK,
			"cancel": self.keyCancel,
			"left"  : self.keyLeft,
			"right" : self.keyRight,
			"up"    : self.keyUp,
			"down"  : self.keyDown,
		}, -1)

		self.changeLogList = MenuList([], enableWrapAround=False, content=eListboxPythonMultiContent)
		self.changeLogList.l.setFont(0, gFont('Regular', int(16 * skinFactor)))
		self.changeLogList.l.setFont(1, gFont('Regular', int(22 * skinFactor)))
		self.changeLogList.l.setFont(2, gFont('Regular', int(24 * skinFactor)))
		self.changeLogList.l.setItemHeight(int(28 * skinFactor))
		self['changelog'] = self.changeLogList

		self['text_ok'] = Label("Schließen und nicht mehr anzeigen")
		self['text_exit'] = Label("Schließen")

		self.onLayoutFinish.append(self.__onLayoutFinished)

	def __onLayoutFinished(self):
		if fileExists(self.serienRecInfoFilePath):
			readFile = open(self.serienRecInfoFilePath, "r")
			text = readFile.read()
			readFile.close()

			changelog_list = []
			for row in text.split('\n'):
				changelog_list.append(row)
			self.changeLogList.setList(list(map(self.buildList, changelog_list)))

	def buildList(self, entry):
		(row) = entry
		DESKTOP_WIDTH = getDesktop(0).size().width()

		if len(row) == 0:
			self.indent = False

		if row.startswith('##'):
			row = row.replace('#', '')
			color = parseColor('green').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 5, 2 * skinFactor, DESKTOP_WIDTH - 105, 28 * skinFactor, 2, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		elif row.startswith('**'):
			row = row.replace('*', '')
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 5, 2 * skinFactor, DESKTOP_WIDTH - 105, 28 * skinFactor, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row)]
		elif re.search('^[1-9-]', row):
			color = parseColor('foreground').argb()
			self.indent = True
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 20, 2 * skinFactor, DESKTOP_WIDTH - 90, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		elif self.indent:
			color = parseColor('foreground').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 40, 2 * skinFactor, DESKTOP_WIDTH - 70, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]
		else:
			color = parseColor('foreground').argb()
			return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 20, 2 * skinFactor, DESKTOP_WIDTH - 90, 28 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, row, color, color)]

	def keyLeft(self):
		self['changelog'].pageUp()

	def keyRight(self):
		self['changelog'].pageDown()

	def keyDown(self):
		self['changelog'].pageDown()

	def keyUp(self):
		self['changelog'].pageUp()

	def keyOK(self):
		if fileExists(self.serienRecInfoFilePath):
			os.remove(self.serienRecInfoFilePath)
		self.close()

	def keyCancel(self):
		self.close()