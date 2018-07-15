# coding=utf-8

# This file contains the SerienRecoder Channel Screen
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.MenuList import MenuList

from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, loadPNG, RT_VALIGN_CENTER, eTimer
from skin import parseColor

from SerienRecorderHelpers import *
from SerienRecorderAboutScreen import *
from SerienRecorderScreenHelpers import *
from SerienRecorderSeriesServer import *
from SerienRecorderDatabase import *
import SerienRecorder

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
		self.displayTimer = eTimer()
		self.displayTimer_conn = None
		self.chooseMenuList = None
		self.chooseMenuList_popup = None
		self.chooseMenuList_popup2 = None
		self.database = SRDatabase(SerienRecorder.serienRecDataBaseFilePath)

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
			"startTeletext"       : (self.youtubeSearch, "Trailer zum ausgewählten Sender auf YouTube suchen"),
			"startTeletext_long"  : (self.WikipediaSearch, "Informationen zum ausgewählten Sender auf Wikipedia suchen"),
			"0"		   : (self.readLogFile, "Log-File des letzten Suchlaufs anzeigen"),
			"3"		   : (self.showProposalDB, "Liste der Serien/Staffel-Starts anzeigen"),
			"6"		   : (self.showConflicts, "Liste der Timer-Konflikte anzeigen"),
			"7"		   : (self.showWishlist, "Merkzettel (vorgemerkte Folgen) anzeigen"),
		}, -1)
		self.helpList[0][2].sort()

		self["helpActions"] = ActionMap(["SerienRecorderActions",], {
			"displayHelp"      : self.showHelp,
			"displayHelp_long" : self.showManual,
		}, 0)

		global showAllButtons
		if config.plugins.serienRec.SkinType.value in ("", "AtileHD"):
			showAllButtons = False
		else:
			showAllButtons = True

		self.setupSkin()

		self.modus = "list"
		self.changesMade = False

		self.timer_default = eTimer()
		if isDreamOS():
			self.timer_default_conn = self.timer_default.timeout.connect(self.showChannels)
		else:
			self.timer_default.callback.append(self.showChannels)

		self.onLayoutFinish.append(self.setSkinProperties)
		self.onLayoutFinish.append(self.__onLayoutFinished)
		self.onClose.append(self.__onClose)

	def callHelpAction(self, *args):
		HelpableScreen.callHelpAction(self, *args)

	def setSkinProperties(self):
		super(self.__class__, self).setSkinProperties()

		self['text_green'].setText("Aktualisieren")
		self['text_ok'].setText("Sender auswählen")

		self.num_bt_text[4][0] = buttonText_na
		if longButtonText:
			self['text_red'].setText("An/Aus (lang: Löschen)")
			self.num_bt_text[4][2] = "Setup Sender (lang: global)"
		else:
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

		global showAllButtons
		if not showAllButtons:
			self['bt_red'].show()
			self['bt_green'].show()
			self['bt_blue'].show()
			self['bt_ok'].show()
			self['bt_exit'].show()
			self['bt_text'].show()
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
		self.session.open(SerienRecorder.serienRecChannelSetup, webSender)

	def youtubeSearch(self):
		sender_name = self['list'].getCurrent()[0][0]
		super(self.__class__, self).youtubeSearch(sender_name)

	def WikipediaSearch(self):
		sender_name = self['list'].getCurrent()[0][0]
		super(self.__class__, self).WikipediaSearch(sender_name)

	def setupClose(self, result):
		super(self.__class__, self).setupClose(result)

		if result[1]:
			self.showChannels()

	def __onLayoutFinished(self):
		self['title'].setText("Lade Wunschliste-Sender...")
		self.timer_default.start(0)

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
						global runAutocheckAtExit
						runAutocheckAtExit = True
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
			if webChannel.lower() not in [dbWebChannel.lower() for dbWebChannel in dbWebChannels]:
				added.append(webChannel)

		# append removed channels
		for dbWebChannel in dbWebChannels:
			if dbWebChannel.lower() not in [webChannel.lower() for webChannel in webChannels]:
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

		# First try to find the HD version
		webChannelHD = webChannel + " HD"
		for servicename,serviceref in self.stbChannelList:
			self.sequenceMatcher.set_seqs(webChannelHD.lower(), servicename.lower())
			ratio = self.sequenceMatcher.ratio()
			if ratio >= 0.98:
				result = (servicename, serviceref)
				break

		if not result:
			for servicename,serviceref in self.stbChannelList:
				self.sequenceMatcher.set_seqs(webChannel.lower(), servicename.lower())
				ratio = self.sequenceMatcher.ratio()
				if ratio >= 0.98:
					result = (servicename, serviceref)
					break

		return result

	@staticmethod
	def buildList(entry):
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

		global runAutocheckAtExit
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
				runAutocheckAtExit = True
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
			runAutocheckAtExit = True
			self['title'].setText("Sender zuordnen")
			self.showChannels()

	def keyRed(self):
		global runAutocheckAtExit
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
			runAutocheckAtExit = True

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
			except:
				self['title'].setText("Fehler beim Laden der Wunschliste-Sender")
		else:
			print "[SerienRecorder] channel-list ok."

	def keyBlue(self):
		self.session.openWithCallback(self.autoMatch, MessageBox, "Es wird versucht für alle nicht zugeordneten Wunschliste-Sender einen passenden STB-Sender zu finden, dabei werden zunächst HD Sender bevorzugt.\n\nDies kann, je nach Umfang der Senderliste, einige Zeit (u.U. einige Minuten) dauern - bitte haben Sie Geduld!\n\nAutomatische Zuordnung jetzt durchführen?", MessageBox.TYPE_YESNO)

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

	def keyLeft(self):
		self[self.modus].pageUp()

	def keyRight(self):
		self[self.modus].pageDown()

	def keyDown(self):
		self[self.modus].down()

	def keyUp(self):
		self[self.modus].up()

	def __onClose(self):
		if self.displayTimer:
			self.displayTimer.stop()
			self.displayTimer = None

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