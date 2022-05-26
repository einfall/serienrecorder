# coding=utf-8

# This file contains the SerienRecoder Conflicts Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.config import config

from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
import time

from . import SerienRecorder
from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, updateMenuKeys, InitSkin, skinFactor
from .SerienRecorderDatabase import SRDatabase

class serienRecShowConflicts(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.skin = None
		self.conflictsListe = []
		self.session = session
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "Zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "Zur vorherigen Seite blättern"),
			"right": (self.keyRight, "Zur nächsten Seite blättern"),
			"up": (self.keyUp, "Eine Zeile nach oben"),
			"down": (self.keyDown, "Eine Zeile nach unten"),
			"red": (self.keyCancel, "Zurück zur vorherigen Ansicht"),
			"blue": (self.keyBlue, "Alle Einträge aus der Liste endgültig löschen"),
			"menu": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"0"	: (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		: (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"7"		: (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions" ,], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.onLayoutFinish.append(self.readConflicts)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_red'].setText("Abbrechen")
		self['text_blue'].setText("Liste leeren")
		self.num_bt_text[1][1] = buttonText_na
		self.num_bt_text[4][0] = buttonText_na

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		InitSkin(self)

		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25 *skinFactor))
		self['menu_list'] = self.chooseMenuList
		self['menu_list'].show()

		self['title'].setText("Timer-Konflikte")

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)
		if result[1]:
			self.readConflicts()

	def readConflicts(self):
		conflicts = self.database.getTimerConflicts()
		for conflict in conflicts:
			(zeile, start_time, webChannel) = conflict
			data = zeile.split('/')
			if data:
				self.conflictsListe.append(("%s" % data[0].strip()))
				self.conflictsListe.append(("    @ %s (%s) in Konflikt mit:" %
				(webChannel, time.strftime("%d.%m.%Y - %H:%M", time.localtime(start_time)))))
				data = data[1:]
				for row2 in data:
					self.conflictsListe.append(("            -> %s" % row2.strip()))
				self.conflictsListe.append(("-" * 100))
				self.conflictsListe.append("")
		self.chooseMenuList.setList(list(map(self.buildList, self.conflictsListe)))

	@staticmethod
	def buildList(entry):
		(zeile) = entry
		return [entry, (eListboxPythonMultiContent.TYPE_TEXT, 00, 00, 850 * skinFactor, 20 * skinFactor, 0,
		                RT_HALIGN_LEFT | RT_VALIGN_CENTER, zeile)]

	def keyLeft(self):
		self['menu_list'].pageUp()

	def keyRight(self):
		self['menu_list'].pageDown()

	def keyDown(self):
		self['menu_list'].down()

	def keyUp(self):
		self['menu_list'].up()

	def keyBlue(self):
		if self['menu_list'].getCurrent() is None:
			print("[SerienRecorder] Conflict-List leer.")
			return
		else:
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.callDeleteMsg, MessageBox, "Soll die Liste wirklich geleert werden?",
				                              MessageBox.TYPE_YESNO, default=False)
			else:
				self.callDeleteMsg(True)

	def callDeleteMsg(self, answer):
		if answer:
			self.database.removeAllTimerConflicts()
			self.readConflicts()
		else:
			return

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		self.close()
