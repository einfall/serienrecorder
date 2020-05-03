# coding=utf-8

# This file contains the SerienRecoder Series Info Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config

from enigma import ePicLoad

import SerienRecorder
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderDatabase import SRDatabase

class serienRecShowInfo(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, serien_name, serien_wlid, serien_fsid):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.picload = ePicLoad()
		self.serien_name = serien_name
		self.serien_wlid = serien_wlid
		self.serien_fsid = serien_fsid
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left"  : (self.pageUp, "zur vorherigen Seite blättern"),
			"right" : (self.pageDown, "zur nächsten Seite blättern"),
			"up"    : (self.pageUp, "zur vorherigen Seite blättern"),
			"down"  : (self.pageDown, "zur nächsten Seite blättern"),
			"menu"  : (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"startTeletext"  : (self.wunschliste, "Informationen zur ausgewählten Serie auf Wunschliste anzeigen"),
			"red"   : (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"0"		: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		: (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.onLayoutFinish.append(self.getData)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Zurück")
		self.num_bt_text[4][0] = buttonText_na

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		InitSkin(self)

		self['info'].show()
		self['title'].setText("Serien Beschreibung: %s" % self.serien_name)

		if config.plugins.serienRec.showCover.value:
			self['cover'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def wunschliste(self):
		super(self.__class__, self).wunschliste(self.serien_wlid)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

	def getData(self):
		try:
			infoText = SeriesServer().getSeriesInfo(self.serien_wlid)
		except:
			infoText = 'Es ist ein Fehler beim Abrufen der Serien-Informationen aufgetreten!'
		self['info'].setText(infoText)
		SerienRecorder.getCover(self, self.serien_name, self.serien_wlid, self.serien_fsid)

	def pageUp(self):
		self['info'].pageUp()

	def pageDown(self):
		self['info'].pageDown()

	def keyCancel(self):
		self.close(False)

	def __onClose(self):
		self.stopDisplayTimer()
