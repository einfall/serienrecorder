# coding=utf-8

# This file contains the SerienRecoder Season Begin Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.config import config
from Components.FileList import FileList
from Tools.Directories import fileExists

from .SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, setMenuTexts, InitSkin
import os

if fileExists("/usr/lib/enigma2/python/Plugins/SystemPlugins/Toolkit/NTIVirtualKeyBoard.pyo"):
	from Plugins.SystemPlugins.Toolkit.NTIVirtualKeyBoard import NTIVirtualKeyBoard
else:
	from Screens.VirtualKeyBoard import VirtualKeyBoard as NTIVirtualKeyBoard

class serienRecFileListScreen(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session, initDir, title, seriesName=''):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.fullpath = ""
		self.initDir = initDir
		self.title = title
		self.seriesNames = seriesName
		self.skin = None

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"cancel": (self.keyCancel, "zurück zur vorherigen Ansicht"),
			"left": (self.keyLeft, "zur vorherigen Seite blättern"),
			"right": (self.keyRight, "zur nächsten Seite blättern"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"ok": (self.keyOk, "ins ausgewählte Verzeichnis wechseln"),
			"green": (self.keyGreen, "ausgewähltes Verzeichnis übernehmen"),
			"red": (self.keyRed, "ausgewähltes Verzeichnis löschen"),
			"yellow": (self.keyYellow, "auf globales Aufnahmeverzeichnis zurücksetzen"),
			"blue": (self.keyBlue, "neues Verzeichnis anlegen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions", ], {
			"displayHelp": self.showHelp,
			"displayHelp_long": self.showManual,
		}, 0)

		self.setupSkin()

		if config.plugins.serienRec.showAllButtons.value:
			setMenuTexts(self)
		self.updateFile()
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()
		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['menu_list'] = FileList(self.initDir, inhibitMounts=False, inhibitDirs=False, showMountpoints=False, showFiles=False)
		self['menu_list'].show()
		self['title'].hide()
		self['path'].show()

		self['text_red'].setText("Verzeichnis löschen")
		self['text_green'].setText("Speichern")
		self['text_ok'].setText("Auswahl")
		self['text_yellow'].setText("Zurücksetzen")
		self['text_blue'].setText("Verzeichnis anlegen")

		self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, buttonText_na],
		                    [buttonText_na, buttonText_na, "Hilfe"],
		                    [buttonText_na, buttonText_na, buttonText_na])

		if not config.plugins.serienRec.showAllButtons.value:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_ok'].show()
			self['bt_yellow'].show()
			self['bt_blue'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_ok'].show()
			self['text_yellow'].show()
			self['text_blue'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()


	def keyCancel(self):
		self.close(None)

	def keyRed(self):
		currentDirectory = self['menu_list'].getSelection()[0]
		self.session.openWithCallback(self.confirmDeleteCallback, MessageBox, "Das Verzeichnis '%s' wirklich löschen?" % currentDirectory, MessageBox.TYPE_YESNO, default=False)

	def confirmDeleteCallback(self, answer):
		if answer:
			directoryToBeDeleted = self['menu_list'].getSelection()[0]
			try:
				os.rmdir(directoryToBeDeleted)
				self['menu_list'].refresh()
				self.updateFile()
			except OSError as error:
				print("Das Verzeichnis '%s' konnte nicht gelöscht werden. %s" % (directoryToBeDeleted, str(error)))
				self.session.open(MessageBox, "Das Verzeichnis %s konnte nicht gelöscht werden.\n\n%s" % (directoryToBeDeleted, error), MessageBox.TYPE_INFO, timeout=10)

	def keyGreen(self):
		currentDirectory = self['menu_list'].getCurrentDirectory()
		if currentDirectory.endswith("/"):
			self.fullpath = currentDirectory
		else:
			self.fullpath = "%s/" % currentDirectory

		if self.fullpath == config.plugins.serienRec.savetopath.value:
			self.fullpath = ""
		self.close(self.fullpath)

	def keyYellow(self):
		self.fullpath = ""
		self.close(self.fullpath)

	def keyBlue(self):
		self.session.openWithCallback(self.newFolderNameCallback, NTIVirtualKeyBoard, title="Verzeichnisname eingeben:", text=self.seriesNames)

	def newFolderNameCallback(self, path_name):
		if path_name:
			path_name = "%s/%s/" % (self['menu_list'].getCurrentDirectory(), path_name)
			print(path_name)
			if not os.path.exists(path_name):
				try:
					os.makedirs(path_name)
				except:
					pass
		self['menu_list'].refresh()
		self.updateFile()

	def keyUp(self):
		self['menu_list'].up()
		self.updateFile()

	def keyDown(self):
		self['menu_list'].down()
		self.updateFile()

	def keyLeft(self):
		self['menu_list'].pageUp()
		self.updateFile()

	def keyRight(self):
		self['menu_list'].pageDown()
		self.updateFile()

	def keyOk(self):
		if self['menu_list'].canDescent():
			self['menu_list'].descent()
			self.updateFile()

	def updateFile(self):
		currentFolder = self['menu_list'].getCurrentDirectory()
		self['path'].setText("Auswahl:\n%s" % currentFolder)

	def __onClose(self):
		self.stopDisplayTimer()
