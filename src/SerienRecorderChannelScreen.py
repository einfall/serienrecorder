# coding=utf-8

# This file contains the SerienRecoder Channel Screen
from Components import config
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList
from Components.ConfigList import ConfigList, ConfigListScreen
from Components.config import config, ConfigInteger, getConfigListEntry, ConfigYesNo

from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, loadPNG, RT_VALIGN_CENTER, eTimer
from skin import parseColor

import SerienRecorder
from SerienRecorderSeriesServer import SeriesServer
from SerienRecorderHelpers import isDreamOS, STBHelpers
from SerienRecorderScreenHelpers import serienRecBaseScreen, buttonText_na, longButtonText, InitSkin, skinFactor, updateMenuKeys, setMenuTexts
from SerienRecorderLogWriter import SRLogger

class serienRecMainChannelEdit(serienRecBaseScreen, Screen, HelpableScreen):
	def __init__(self, session):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.serienRecChannelList = []
		self.stbChannelList = []
		self.selected_sender = None
		self.skin = None
		self.displayMode = 2
		self.chooseMenuList = None
		self.chooseMenuList_popup = None
		self.chooseMenuList_popup2 = None

		from SerienRecorder import serienRecDataBaseFilePath
		from SerienRecorderDatabase import SRDatabase
		self.database = SRDatabase(serienRecDataBaseFilePath)

		from difflib import SequenceMatcher
		self.sequenceMatcher = SequenceMatcher(" ".__eq__, "", "")
		
		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"ok"       : (self.keyOK, "Popup-Fenster zur Auswahl des STB-Sender öffnen"),
			"cancel"   : (self.keyCancel, "zurück zur Serienplaner-Ansicht"),
			"red"	   : (self.keyRed, "umschalten ausgewählter Sender für Timererstellung aktiviert/deaktiviert"),
			"red_long" : (self.keyRedLong, "ausgewählten Sender aus der Channelliste endgültig löschen"),
			"green"    : (self.keyGreen, "Sender-Zuordnung aktualisieren"),
			"blue"     : (self.keyBlue, "Automatische Sender-Zuordnung"),
			"menu"     : (self.channelSetup, "Menü für Sender-Einstellungen öffnen"),
			"menu_long": (self.recSetup, "Menü für globale Einstellungen öffnen"),
			"left"     : (self.keyLeft, "zur vorherigen Seite blättern"),
			"right"    : (self.keyRight, "zur nächsten Seite blättern"),
			"up"       : (self.keyUp, "eine Zeile nach oben"),
			"down"     : (self.keyDown, "eine Zeile nach unten"),
			"0"		   : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		   : (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		   : (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		   : (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
			"8"		   : (self.checkChannels, "Sender prüfen"),
			"9"		   : (self.resetChannelList, "Alle Zuordnungen löschen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		self.setupSkin()

		self.modus = "list"
		self.changesMade = False

		self.timer_default = eTimer()
		if isDreamOS():
			self.timer_default_conn = self.timer_default.timeout.connect(self.showChannels)
		else:
			self.timer_default.callback.append(self.showChannels)

		self.onLayoutFinish.append(self.__onLayoutFinished)
		self.onClose.append(self.__onClose)
		self.onLayoutFinish.append(self.setSkinProperties)


	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_green'].setText("Aktualisieren")
		self['text_ok'].setText("Sender auswählen")

		self.num_bt_text[3][1] = "Sender prüfen"
		self.num_bt_text[4][1] = "Alle löschen"
		if longButtonText:
			self.num_bt_text[4][0] = ""
			self['text_red'].setText("An/Aus (lang: Löschen)")
			self.num_bt_text[4][2] = "Setup Sender (lang: global)"
		else:
			self.num_bt_text[4][0] = buttonText_na
			self['text_red'].setText("(De)aktivieren/Löschen")
			self.num_bt_text[4][2] = "Setup Sender/global"

		self['text_blue'].setText("Auto-Zuordnung")

		super(self.__class__, self).startDisplayTimer()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		# normal
		self.chooseMenuList = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList.l.setItemHeight(int(25*skinFactor))
		self['list'] = self.chooseMenuList
		self['list'].show()

		# popup
		self.chooseMenuList_popup = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup.l.setItemHeight(int(25*skinFactor))
		self['popup_list'] = self.chooseMenuList_popup
		self['popup_list'].hide()

		# popup2
		self.chooseMenuList_popup2 = MenuList([], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.chooseMenuList_popup2.l.setFont(0, gFont('Regular', 20 + int(config.plugins.serienRec.listFontsize.value)))
		self.chooseMenuList_popup2.l.setItemHeight(int(25*skinFactor))
		self['popup_list2'] = self.chooseMenuList_popup2
		self['popup_list2'].hide()

		self['title'].setText("Lade Wunschliste-Sender...")

		self['Web_Channel'].setText("Wunschliste")
		self['STB_Channel'].setText("STB-Sender")
		self['alt_STB_Channel'].setText("alt. STB-Sender")

		self['Web_Channel'].show()
		self['STB_Channel'].show()
		self['alt_STB_Channel'].show()
		self['separator'].show()

		if not config.plugins.serienRec.showAllButtons.value:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_blue'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			#self['bt_text'].show()
			self['bt_info'].show()
			self['bt_menu'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_blue'].show()
			self['text_ok'].show()
			self['text_0'].show()
			self['text_1'].show()
			self['text_2'].show()
			self['text_3'].show()
			self['text_4'].show()

	def updateMenuKeys(self):
		updateMenuKeys(self)

	def channelSetup(self):
		webSender = self['list'].getCurrent()[0][0]
		self.session.open(serienRecChannelSetup, webSender)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

		if result[1]:
			self.showChannels()

	def __onLayoutFinished(self):
		self['title'].setText("Lade Wunschliste-Sender...")
		self.timer_default.start(0)

	def checkChannels(self):
		channels = self.database.getChannels(True)
		if config.plugins.serienRec.selectBouquets.value:
			stbChannelList = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
		else:
			stbChannelList = STBHelpers.buildSTBChannelList()

		stbServiceRefs = [x[1] for x in stbChannelList]
		serviceRefs = [x[2] for x in channels]
		missingServiceRefs = []
		missingServices = []

		for serviceRef in serviceRefs:
			if serviceRef not in stbServiceRefs:
				missingServiceRefs.append(serviceRef)

		for missingServiceRef in missingServiceRefs:
			for channel in channels:
				(webSender, servicename, serviceref, altservicename, altserviceref, status) = channel
				if serviceref is missingServiceRef and servicename and int(status) != 0:
					missingServices.append(servicename)
					SRLogger.writeLog("%s => %s" % (missingServiceRef, servicename), True)
					break

		if missingServices:
			self.session.open(MessageBox, "Für folgende Sender existiert die ServiceRef nicht mehr,\nbitte die Sender neu zuweisen:\n\n" + "\n".join(missingServices), MessageBox.TYPE_INFO, timeout=0)
		else:
			self.session.open(MessageBox, "Alle zugewiesenen Sender sind noch vorhanden.", MessageBox.TYPE_INFO, timeout=7)

	def showChannels(self):
		self.timer_default.stop()
		self.serienRecChannelList = []
		channels = self.database.getChannels(True)
		for channel in channels:
			(webSender, servicename, serviceref, altservicename, altserviceref, status) = channel
			self.serienRecChannelList.append((webSender, servicename, altservicename, status))

		if len(self.serienRecChannelList) != 0:
			self['title'].setText("Sender zuordnen")
			self.chooseMenuList.setList(map(self.buildList, self.serienRecChannelList))
		else:
			self.channelReset(True)

	def readWebChannels(self):
		print "[SerienRecorder] call webpage.."
		self['title'].setText("Lade Wunschliste-Sender...")
		try:
			self.createWebChannels(SeriesServer().doGetWebChannels(), False)
		except:
			self['title'].setText("Fehler beim Laden der Wunschliste-Sender")

	def createWebChannels(self, webChannelList, autoMatch):
		if webChannelList:
			webChannelList.sort(key=lambda x: x.lower())
			self.serienRecChannelList = []

			if len(webChannelList) != 0:
				self['title'].setText("Erstelle Sender-Liste...")

				# Get existing channels from database
				dbChannels = self.database.getChannelPairs()

				if autoMatch:
					# Get all unassigned web channels and try to find the STB channel equivalent
					# Update only matching channels in list
					#sql = "UPDATE OR IGNORE Channels SET STBChannel=?, ServiceRef=?, Erlaubt=? WHERE LOWER(WebChannel)=?"
					unassignedWebChannels = self.getUnassignedWebChannels(dbChannels)

					channels = []
					for webChannel in unassignedWebChannels:
						# Unmapped web channel
						(servicename, serviceref) = self.findWebChannelInSTBChannels(webChannel)
						if servicename and serviceref:
							channels.append((servicename, serviceref, 1, webChannel.lower()))
							self.serienRecChannelList.append((webChannel, servicename, "", "1"))

						self.database.updateChannels(channels)
						self.changesMade = True
				else:
					# Get all new web channels (missing in SR database)
					(newWebChannels, removedWebChannels) = self.getMissingWebChannels(webChannelList, dbChannels)

					# Delete remove channels
					if removedWebChannels:
						self.session.open(MessageBox, "Folgende Sender wurden bei Wunschliste nicht mehr gefunden,\ndie Zuordnung im SerienRecorder wird gelöscht:\n\n" + "\n".join(removedWebChannels), MessageBox.TYPE_INFO, timeout=10)
						for webChannel in removedWebChannels:
							self.selected_sender = webChannel
							self.channelDelete(True)

					if not newWebChannels:
						self.session.open(MessageBox, "Die SerienRecorder Senderliste ist aktuell,\nes wurden keine neuen Sender bei Wunschliste gefunden.", MessageBox.TYPE_INFO, timeout=10)
						self.showChannels()
					else:
						channels = []
						for webChannel in newWebChannels:
							channels.append((webChannel, "", "", 0))
							self.serienRecChannelList.append((webChannel, "", "", "0"))
						self.database.addChannels(channels)

			else:
				print "[SerienRecorder] webChannel list leer.."

			if len(self.serienRecChannelList) != 0:
				self.chooseMenuList.setList(map(self.buildList, self.serienRecChannelList))
			else:
				print "[SerienRecorder] Fehler bei der Erstellung der SerienRecChlist.."

		else:
			print "[SerienRecorder] get webChannel error.."

		self['title'].setText("Wunschliste-Sender / STB-Sender")

	@staticmethod
	def getMissingWebChannels(webChannels, dbChannels):
		added = []
		removed = []

		dbWebChannels = [x[0] for x in dbChannels]

		# append missing (new) channels
		for webChannel in webChannels:
			if webChannel not in [dbWebChannel for dbWebChannel in dbWebChannels]:
				added.append(webChannel)

		# append removed channels
		for dbWebChannel in dbWebChannels:
			if dbWebChannel not in [webChannel for webChannel in webChannels]:
				removed.append(dbWebChannel)

		return added, removed

	@staticmethod
	def getUnassignedWebChannels(dbChannels):
		result = []

		#append unassigned
		for x in dbChannels:
			if not x[1]:
				result.append(x[0])

		return result

	def findWebChannelInSTBChannels(self, webChannel):
		result = (None, None)
		channelFound = False

		# First try to find the HD version
		webChannelHD = webChannel + " HD"
		for servicename,serviceref in self.stbChannelList:
			self.sequenceMatcher.set_seqs(webChannelHD.lower(), servicename.lower())
			ratio = self.sequenceMatcher.ratio()
			if ratio >= 0.98:
				result = (servicename, serviceref)
				channelFound = True
				break

		if not channelFound:
			for servicename,serviceref in self.stbChannelList:
				self.sequenceMatcher.set_seqs(webChannel.lower(), servicename.lower())
				ratio = self.sequenceMatcher.ratio()
				if ratio >= 0.98:
					result = (servicename, serviceref)
					break

		return result

	@staticmethod
	def buildList(entry):
		from SerienRecorder import serienRecMainPath
		(webSender, stbSender, altstbSender, status) = entry
		if int(status) == 0:
			imageStatus = "%simages/minus.png" % serienRecMainPath
		else:
			imageStatus = "%simages/plus.png" % serienRecMainPath

		return [entry,
			(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 10, 7 * skinFactor, 16 * skinFactor, 16 * skinFactor, loadPNG(imageStatus)),
			(eListboxPythonMultiContent.TYPE_TEXT, 40 * skinFactor, 0, 300 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, webSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 350 * skinFactor, 0, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, stbSender),
			(eListboxPythonMultiContent.TYPE_TEXT, 600 * skinFactor, 0, 250 * skinFactor, 26 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, altstbSender, parseColor('yellow').argb())
			]

	@staticmethod
	def buildList_popup(entry):
		(servicename,serviceref) = entry
		return [entry,
			(eListboxPythonMultiContent.TYPE_TEXT, 5, 1, 250 * skinFactor, 25 * skinFactor, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, servicename)
			]

	def keyOK(self):
		if self['list'].getCurrent() is None:
			print "[SerienRecorder] Sender-Liste leer."
			return

		if self.modus == "list":
			self.modus = "popup_list"
			self['popup_list'].show()
			self['popup_bg'].show()
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChannelList = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChannelList = STBHelpers.buildSTBChannelList()
			self.stbChannelList.insert(0, ("", ""))
			self.chooseMenuList_popup.setList(map(self.buildList_popup, self.stbChannelList))
			idx = 0
			(stbChannel, altstbChannel) = self.database.getSTBChannel(self['list'].getCurrent()[0][0])
			if stbChannel:
				try:
					idx = zip(*self.stbChannelList)[0].index(stbChannel)
				except:
					pass
			self['popup_list'].moveToIndex(idx)
			self['title'].setText("Standard STB-Sender für %s:" % self['list'].getCurrent()[0][0])
		elif config.plugins.serienRec.selectBouquets.value:
			if self.modus == "popup_list":
				self.modus = "popup_list2"
				self['popup_list'].hide()
				self['popup_list2'].show()
				self['popup_bg'].show()
				self.stbChannelList = STBHelpers.buildSTBChannelList(config.plugins.serienRec.AlternativeBouquet.value)
				self.stbChannelList.insert(0, ("", ""))
				self.chooseMenuList_popup2.setList(map(self.buildList_popup, self.stbChannelList))
				idx = 0
				(stbChannel, altstbChannel) = self.database.getSTBChannel(self['list'].getCurrent()[0][0])
				if stbChannel:
					try:
						idx = zip(*self.stbChannelList)[0].index(altstbChannel)
					except:
						pass
				self['popup_list2'].moveToIndex(idx)
				self['title'].setText("alternativer STB-Sender für %s:" % self['list'].getCurrent()[0][0])
			else:
				self.modus = "list"
				self['popup_list'].hide()
				self['popup_list2'].hide()
				self['popup_bg'].hide()

				check = self['list'].getCurrent()
				if check is None:
					print "[SerienRecorder] Sender-Liste leer (list)."
					return

				check = self['popup_list'].getCurrent()
				if check is None:
					print "[SerienRecorder] Sender-Liste leer (popup_list)."
					return

				chlistSender = self['list'].getCurrent()[0][0]
				stbSender = self['popup_list'].getCurrent()[0][0]
				stbRef = self['popup_list'].getCurrent()[0][1]
				altstbSender = self['popup_list2'].getCurrent()[0][0]
				altstbRef = self['popup_list2'].getCurrent()[0][1]
				print "[SerienRecorder] select:", chlistSender, stbSender, stbRef, altstbSender, altstbRef
				channels = []
				if stbSender != "" or altstbSender != "":
					channels.append((stbSender, stbRef, altstbSender, altstbRef, 1, chlistSender.lower()))
				else:
					channels.append((stbSender, stbRef, altstbSender, altstbRef, 0, chlistSender.lower()))
				self.database.updateChannels(channels, True)
				self.changesMade = True
				self['title'].setText("Sender zuordnen")
				self.showChannels()
		else:
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_list2'].hide()
			self['popup_bg'].hide()

			if self['list'].getCurrent() is None:
				print "[SerienRecorder] Sender-Liste leer (list)."
				return

			if self['popup_list'].getCurrent() is None:
				print "[SerienRecorder] Sender-Liste leer (popup_list)."
				return

			chlistSender = self['list'].getCurrent()[0][0]
			stbSender = self['popup_list'].getCurrent()[0][0]
			stbRef = self['popup_list'].getCurrent()[0][1]
			print "[SerienRecorder] select:", chlistSender, stbSender, stbRef
			channels = []
			if stbSender != "":
				channels.append((stbSender, stbRef, 1, chlistSender.lower()))
			else:
				channels.append((stbSender, stbRef, 0, chlistSender.lower()))
			self.database.updateChannels(channels)
			self.changesMade = True
			self['title'].setText("Sender zuordnen")
			self.showChannels()

	def keyRed(self):
		if self['list'].getCurrent() is None:
			print "[SerienRecorder] Sender-Liste leer."
			return

		if self.modus == "list":
			chlistSender = self['list'].getCurrent()[0][0]
			sender_status = self['list'].getCurrent()[0][2]
			print sender_status

			self.database.changeChannelStatus(chlistSender)
			self['title'].instance.setForegroundColor(parseColor("red"))
			self['title'].setText("")
			self['title'].setText("Sender '- %s -' wurde geändert." % chlistSender)

			self.changesMade = True
			self['title'].instance.setForegroundColor(parseColor("foreground"))
			self.showChannels()

	def keyGreen(self):
		self.session.openWithCallback(self.channelReset, MessageBox, "Senderliste aktualisieren?", MessageBox.TYPE_YESNO)

	def channelReset(self, execute):
		if execute:
			print "[SerienRecorder] channel-list reset..."

			if config.plugins.serienRec.selectBouquets.value:
				self.stbChannelList = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChannelList = STBHelpers.buildSTBChannelList()
			self['title'].setText("Lade Wunschliste-Sender...")
			try:
				self.createWebChannels(SeriesServer().doGetWebChannels(), False)
				self.database.setChannelListLastUpdate()
			except:
				self['title'].setText("Fehler beim Laden der Wunschliste-Sender")
		else:
			print "[SerienRecorder] channel-list ok."

	def keyBlue(self):
		self.session.openWithCallback(self.autoMatch, MessageBox, "Es wird versucht, für alle nicht zugeordneten Wunschliste-Sender, einen passenden STB-Sender zu finden, dabei werden zunächst HD Sender bevorzugt.\n\nDies kann, je nach Umfang der Senderliste, einige Zeit (u.U. einige Minuten) dauern - bitte haben Sie Geduld!\n\nAutomatische Zuordnung jetzt durchführen?", MessageBox.TYPE_YESNO)

	def autoMatch(self, execute):
		if execute:
			if config.plugins.serienRec.selectBouquets.value:
				self.stbChannelList = STBHelpers.buildSTBChannelList(config.plugins.serienRec.MainBouquet.value)
			else:
				self.stbChannelList = STBHelpers.buildSTBChannelList()
			self['title'].setText("Versuche automatische Zuordnung...")
			try:
				self.createWebChannels(SeriesServer().doGetWebChannels(), True)
			except:
				self['title'].setText("Fehler beim Laden der Wunschliste-Sender")

	def keyRedLong(self):
		check = self['list'].getCurrent()
		if check is None:
			print "[SerienRecorder] Serien Marker leer."
			return
		else:
			self.selected_sender = self['list'].getCurrent()[0][0]
			if config.plugins.serienRec.confirmOnDelete.value:
				self.session.openWithCallback(self.channelDelete, MessageBox, "Soll '%s' wirklich entfernt werden?" % self.selected_sender, MessageBox.TYPE_YESNO, default = False)
			else:
				self.channelDelete(True)

			self.showChannels()

	def channelDelete(self, answer):
		if not answer:
			return
		self.database.removeChannel(self.selected_sender)
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Sender '- %s -' entfernt." % self.selected_sender)

	def resetChannelList(self):
		if config.plugins.serienRec.confirmOnDelete.value:
			self.session.openWithCallback(self.channelDeleteAll, MessageBox,
			                              "Sollen wirklich alle Senderzuordnungen entfernt werden?",
			                              MessageBox.TYPE_YESNO, default=False)
		else:
			self.channelDeleteAll(True)

		self.showChannels()

	def channelDeleteAll(self, answer):
		if not answer:
			return
		self.database.removeAllChannels()
		self.changesMade = True
		self['title'].instance.setForegroundColor(parseColor("red"))
		self['title'].setText("Alle Senderzuordnungen entfernt.")

	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def __onClose(self):
		self.stopDisplayTimer()

	def keyCancel(self):
		if self.modus == "popup_list":
			self.modus = "list"
			self['popup_list'].hide()
			self['popup_bg'].hide()
		elif self.modus == "popup_list2":
			self.modus = "list"
			self['popup_list2'].hide()
			self['popup_bg'].hide()
		else:
			if config.plugins.serienRec.refreshViews.value:
				self.close(self.changesMade)
			else:
				self.close(False)

class serienRecChannelSetup(serienRecBaseScreen, Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, webSender):
		serienRecBaseScreen.__init__(self, session)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.webSender = webSender

		from SerienRecorder import serienRecDataBaseFilePath
		from SerienRecorderDatabase import SRDatabase
		self.database = SRDatabase(serienRecDataBaseFilePath)

		self["actions"] = HelpableActionMap(self, "SerienRecorderActions", {
			"red": (self.cancel, "Änderungen verwerfen und zurück zur Sender-Ansicht"),
			"green": (self.save, "Einstellungen speichern und zurück zur Sender-Ansicht"),
			"cancel": (self.cancel, "Änderungen verwerfen und zurück zur Sender-Ansicht"),
			"ok": (self.ok, "---"),
			"up": (self.keyUp, "eine Zeile nach oben"),
			"down": (self.keyDown, "eine Zeile nach unten"),
			"startTeletext": (self.showAbout, "Über dieses Plugin"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions", ], {
			"ok": self.ok,
			"displayHelp": self.showHelp,
			"displayHelp_long": self.showManual,
		}, 0)

		self.setupSkin()
		if config.plugins.serienRec.showAllButtons.value:
			setMenuTexts(self)

		(Vorlaufzeit, Nachlaufzeit, vps) = self.database.getChannelsSettings(self.webSender)

		if str(Vorlaufzeit).isdigit():
			self.margin_before = ConfigInteger(Vorlaufzeit, (0, 99))
			self.enable_margin_before = ConfigYesNo(default=True)
		else:
			self.margin_before = ConfigInteger(config.plugins.serienRec.margin_before.value, (0, 99))
			self.enable_margin_before = ConfigYesNo(default=False)

		if str(Nachlaufzeit).isdigit():
			self.margin_after = ConfigInteger(Nachlaufzeit, (0, 99))
			self.enable_margin_after = ConfigYesNo(default=True)
		else:
			self.margin_after = ConfigInteger(config.plugins.serienRec.margin_after.value, (0, 99))
			self.enable_margin_after = ConfigYesNo(default=False)

		if str(vps).isdigit():
			self.enable_vps = ConfigYesNo(default=bool(vps & 0x1))
			self.enable_vps_savemode = ConfigYesNo(default=bool(vps & 0x2))
		else:
			self.enable_vps = ConfigYesNo(default=False)
			self.enable_vps_savemode = ConfigYesNo(default=False)

		self.changedEntry()
		ConfigListScreen.__init__(self, self.list)
		self.setInfoText()
		self['config_information_text'].setText(self.HilfeTexte[self.enable_margin_before])
		self.onLayoutFinish.append(self.setSkinProperties)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

	def setupSkin(self):
		self.skin = None
		InitSkin(self)

		self['config'] = ConfigList([])
		self['config'].show()

		self['config_information'].show()
		self['config_information_text'].show()

		self['title'].setText("SerienRecorder - Einstellungen für '%s':" % self.webSender)
		self['text_red'].setText("Abbrechen")
		self['text_green'].setText("Speichern")
		if not config.plugins.serienRec.showAllButtons.value:
			self['text_0'].setText("Abbrechen")
			self['text_1'].setText("About")

			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_exit'].show()
			self['bt_text'].show()

			self['text_red'].show()
			self['text_green'].show()
			self['text_0'].show()
			self['text_1'].show()
		else:
			self.num_bt_text = ([buttonText_na, buttonText_na, "Abbrechen"],
			                    [buttonText_na, buttonText_na, buttonText_na],
			                    [buttonText_na, buttonText_na, buttonText_na],
			                    [buttonText_na, buttonText_na, "Hilfe"],
			                    [buttonText_na, buttonText_na, buttonText_na])

	def createConfigList(self):
		self.margin_after_index = 1
		self.list = []
		self.list.append(
			getConfigListEntry("vom globalen Setup abweichenden Timervorlauf aktivieren:", self.enable_margin_before))
		if self.enable_margin_before.value:
			self.list.append(getConfigListEntry("      Timervorlauf (in Min.):", self.margin_before))
			self.margin_after_index += 1

		self.list.append(
			getConfigListEntry("vom globalen Setup abweichenden Timernachlauf aktivieren:", self.enable_margin_after))
		if self.enable_margin_after.value:
			self.list.append(getConfigListEntry("      Timernachlauf (in Min.):", self.margin_after))

		from SerienRecorder import VPSPluginAvailable
		if VPSPluginAvailable:
			self.list.append(getConfigListEntry("VPS für diesen Sender aktivieren:", self.enable_vps))
			if self.enable_vps.value:
				self.list.append(getConfigListEntry("      Sicherheitsmodus aktivieren:", self.enable_vps_savemode))

	def UpdateMenuValues(self):
		if self['config'].instance.getCurrentIndex() == 0:
			if self.enable_margin_before.value and not self.margin_before.value:
				self.margin_before.value = config.plugins.serienRec.margin_before.value
		elif self['config'].instance.getCurrentIndex() == self.margin_after_index:
			if self.enable_margin_after.value and not self.margin_after.value:
				self.margin_after.value = config.plugins.serienRec.margin_after.value
		self.changedEntry()

	def changedEntry(self):
		self.createConfigList()
		self['config'].setList(self.list)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.UpdateMenuValues()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.UpdateMenuValues()

	def keyDown(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() >= (len(self.list) - 1):
			self['config'].instance.moveSelectionTo(0)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveDown)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

	def keyUp(self):
		# self.changedEntry()
		if self['config'].instance.getCurrentIndex() < 1:
			self['config'].instance.moveSelectionTo(len(self.list) - 1)
		else:
			self['config'].instance.moveSelection(self['config'].instance.moveUp)

		# self.setInfoText()
		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."
		self["config_information_text"].setText(text)

	def ok(self):
		ConfigListScreen.keyOK(self)

	def setInfoText(self):
		self.HilfeTexte = {
			self.enable_margin_before: ("Bei 'ja' kann die Vorlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
			                            "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
			                            "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
			                            "Bei 'nein' gilt die Einstellung im globalen Setup.") % self.webSender,
			self.margin_before: ("Die Vorlaufzeit für Aufnahmen von '%s' in Minuten.\n"
			                     "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Vorlaufzeit.\n"
			                     "Ist auch bei der aufzunehmenden Serie eine Vorlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.webSender,
			self.enable_margin_after: ("Bei 'ja' kann die Nachlaufzeit für Aufnahmen von '%s' eingestellt werden.\n"
			                           "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
			                           "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.\n"
			                           "Bei 'nein' gilt die Einstellung im globalen Setup.") % self.webSender,
			self.margin_after: ("Die Nachlaufzeit für Aufnahmen von '%s' in Minuten.\n"
			                    "Diese Einstellung hat Vorrang gegenüber der globalen Einstellung für die Nachlaufzeit.\n"
			                    "Ist auch bei der aufzunehmenden Serie eine Nachlaufzeit eingestellt, so hat der HÖHERE Wert Vorrang.") % self.webSender,
			self.enable_vps: (
				                 "Bei 'ja' wird VPS für '%s' aktiviert. Die Aufnahme startet erst, wenn der Sender den Beginn der Ausstrahlung angibt, "
				                 "und endet, wenn der Sender das Ende der Ausstrahlung angibt.") % self.webSender,
			self.enable_vps_savemode: (
				                          "Bei 'ja' wird der Sicherheitsmodus bei '%s' verwendet.Die programmierten Start- und Endzeiten werden eingehalten.\n"
				                          "Die Aufnahme wird nur ggf. früher starten bzw. länger dauern, aber niemals kürzer.") % self.webSender
		}

		try:
			text = self.HilfeTexte[self['config'].getCurrent()[1]]
		except:
			text = "Keine Information verfügbar."

		self["config_information_text"].setText(text)

	def save(self):
		if not self.enable_margin_before.value:
			Vorlaufzeit = None
		else:
			Vorlaufzeit = self.margin_before.value

		if not self.enable_margin_after.value:
			Nachlaufzeit = None
		else:
			Nachlaufzeit = self.margin_after.value

		vpsSettings = (int(self.enable_vps_savemode.value) << 1) + int(self.enable_vps.value)

		self.database.setChannelSettings(self.webSender, Vorlaufzeit, Nachlaufzeit, vpsSettings)
		self.close()

	def cancel(self):
		self.close()